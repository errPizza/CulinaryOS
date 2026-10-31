#!/usr/bin/python3
"""Kit de recuperación y restauración de la sucursal en un equipo recién instalado.

El kit guarda, cifrado con contraseña, lo que no está en la base: llavero, identidad, CA local y credenciales. La base
llega aparte, como el pg_dump de culinaryos-snapshot.service, sellada con el llavero. La licencia y la identidad de
hardware no se copian: pertenecen al equipo y se reaprovisionan.

La copia se carga y se verifica en una base temporal. Hasta que pasa la verificación, el equipo no cambia.
"""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from nacl import pwhash
from securedata import Keyring,encode,decode

CONFIG=Path('/etc/culinaryos')
BACKUPS=Path('/var/backups/culinaryos')
SQLITE=Path('/var/lib/culinaryos-data')
HOSTS=Path('/etc/hosts')
DATABASE,SCRATCH='culinaryos','culinaryos_restore'
ROLE='culinaryos-app'
SERVICES=('culinaryos-publish.service','culinaryos-backend.service','culinaryos-data.service')
REQUIRED=('site.json','branch.json','secrets/branch.keys.json','restaurant-ca.crt','secrets/restaurant-ca.key',
          'restaurant-tls.crt','secrets/restaurant-tls.key','restaurant-connection.json')
OPTIONAL=('printer.json','fiscal.json','secrets/central-ca.crt','secrets/central-client.crt','secrets/central-client.key')
INTEGRATION=re.compile(r'integrations/[A-Za-z0-9_-]{1,64}\.json')
OPS,MEM=pwhash.argon2id.OPSLIMIT_MODERATE,pwhash.argon2id.MEMLIMIT_MODERATE


def allowed(name):
    return name in REQUIRED or name in OPTIONAL or INTEGRATION.fullmatch(name) is not None


def ring(password,salt):
    key=pwhash.argon2id.kdf(32,password.encode(),salt,opslimit=OPS,memlimit=MEM)
    return Keyring({'active':'kit','keys':{'kit':encode(key)}})


def seal_kit(files,password,site_id):
    if not isinstance(password,str) or not 16<=len(password)<=1024:raise ValueError('Contraseña del kit de 16 a 1024 caracteres')
    salt=os.urandom(pwhash.argon2id.SALTBYTES)
    # El límite de 64 KiB del sobre sobra para estos archivos; si no alcanza, seal lo rechaza.
    return {'v':1,'kdf':'argon2id-moderate','site_id':site_id,'created':int(time.time()),'salt':encode(salt),
            'envelope':ring(password,salt).seal(files,{'purpose':'recovery-kit-v1','site_id':site_id})}


def open_kit(kit,password):
    if kit.get('v')!=1 or kit.get('kdf')!='argon2id-moderate':raise ValueError('Kit incompatible')
    salt=decode(kit['salt'])
    if len(salt)!=pwhash.argon2id.SALTBYTES or not isinstance(password,str) or len(password)>1024:raise ValueError('Kit no válido')
    site=kit['site_id']
    files=ring(password,salt).open(kit['envelope'],{'purpose':'recovery-kit-v1','site_id':site})
    if not all(allowed(name) for name in files) or not all(name in files for name in REQUIRED):raise ValueError('Contenido del kit no válido')
    identity=json.loads(decode(files['site.json']['data']))
    branch=json.loads(decode(files['branch.json']['data']))
    if identity.get('site_id')!=site or branch.get('site_id')!=site:raise ValueError('El kit mezcla sucursales')
    Keyring(json.loads(decode(files['secrets/branch.keys.json']['data'])))
    return site,files


def read_files(config):
    files={}
    names=[*REQUIRED,*OPTIONAL,*sorted(p.relative_to(config).as_posix() for p in (config/'integrations').glob('*.json'))]
    for name in names:
        path=config/name
        if path.is_symlink():raise ValueError('No copiar un enlace: '+name)
        if path.is_file():files[name]={'data':encode(path.read_bytes()),'mode':path.stat().st_mode&0o777}
        elif name in REQUIRED:raise ValueError('Falta '+name)
    return files


def check_dump(dump):
    dump=Path(dump)
    expected=Path(str(dump)+'.sha256').read_text(encoding='ascii').split()[0]
    digest=hashlib.sha256()
    with open(dump,'rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    if digest.hexdigest()!=expected:raise ValueError('La copia no coincide con su SHA-256')


def psql(sql):
    subprocess.run(['runuser','-u','postgres','--','psql','-v','ON_ERROR_STOP=1','-At','-c',sql],stdout=subprocess.DEVNULL,check=True)


def load(dump):
    psql('DROP DATABASE IF EXISTS '+SCRATCH)
    psql('CREATE DATABASE '+SCRATCH+' OWNER "'+ROLE+"\" ENCODING 'UTF8' TEMPLATE template0")
    with open(dump,'rb') as stream:
        subprocess.run(['runuser','-u',ROLE,'--','pg_restore','--no-owner','--exit-on-error','--single-transaction','--dbname',SCRATCH],stdin=stream,check=True)


def verify(installer,site,files):
    # Cada comprobación corre con el llavero del kit, así que uno equivocado falla aquí.
    with tempfile.TemporaryDirectory(prefix='culinary-restore-',dir='/run') as tmp:
        keys=Path(tmp)/'keys';keys.write_bytes(decode(files['secrets/branch.keys.json']['data']));keys.chmod(0o600)
        reply=installer.app_command('--site',site,'--database','Host=/run/postgresql;Database='+SCRATCH+';Username='+ROLE,'--verify-store',keys=keys)
    if reply.returncode!=0:raise ValueError('La copia no pasó la verificación: '+reply.stdout.decode(errors='replace').strip())
    return json.loads(reply.stdout)


def save_current(destination,files):
    destination.mkdir(parents=True,mode=0o700)
    for name in dict.fromkeys([*files,*REQUIRED]):
        path=CONFIG/name
        if path.is_file() and not path.is_symlink():
            (destination/name).parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            shutil.copy2(path,destination/name)
    for path in SQLITE.glob('store.sqlite*'):
        (destination/'sqlite').mkdir(exist_ok=True,mode=0o700)
        shutil.copy2(path,destination/'sqlite'/path.name)


def put_back(saved,files):
    from deployment import write_file
    for name in files:
        original=saved/name
        if original.is_file():write_file(CONFIG/name,original.read_bytes(),original.stat().st_mode&0o777)
        else:(CONFIG/name).unlink(missing_ok=True)
    for path in (saved/'sqlite').glob('store.sqlite*'):shutil.copy2(path,SQLITE/path.name)


def install_files(files,site,group):
    from deployment import write_file
    for name,item in files.items():
        path=CONFIG/name
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700 if name.startswith('secrets/') else 0o750)
        write_file(path,decode(item['data']),item['mode'])
        # Lo que el backend lee como archivo normal va por grupo; lo demás llega como credencial de systemd.
        os.chown(path,0,group if item['mode']&0o070 else 0)
    manifest=CONFIG/'application.json'
    value=json.loads(manifest.read_text())
    argv=value['backend_argv'];argv[argv.index('--site')+1]=site
    write_file(manifest,(json.dumps(value,indent=2)+'\n').encode())


def create(output):
    from provision import admin
    admin()
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    files=read_files(CONFIG)
    site=json.loads(decode(files['site.json']['data']))['site_id']
    password=getpass.getpass('Contraseña del kit: ')
    if password!=getpass.getpass('Repita la contraseña: '):raise ValueError('No coincide')
    kit=seal_kit(files,password,site)
    with open(output,'x',encoding='utf-8') as stream:
        os.chmod(output,0o600);json.dump(kit,stream);stream.flush();os.fsync(stream.fileno())
    print('Kit de '+site+' escrito en '+str(output)+'. Guárdalo fuera del equipo y la contraseña en otro lugar.')


def restore(kit_file,dump):
    import pwd
    from provision import admin,central_credentials
    import appliance
    import appliance_install as installer
    admin()
    current=json.loads((CONFIG/'site.json').read_text())
    if installer.initialized(current).get('meta'):raise ValueError('Este equipo ya tiene un restaurante; no se escribe sobre sus datos')
    site,files=open_kit(json.loads(Path(kit_file).read_text()),getpass.getpass('Contraseña del kit: '))
    check_dump(dump)
    load(dump)
    try:report=verify(installer,site,files)
    except Exception:
        psql('DROP DATABASE IF EXISTS '+SCRATCH);raise
    saved=BACKUPS/('pre-restore-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()))
    save_current(saved,files)
    subprocess.run(['systemctl','stop',*SERVICES],check=True)
    try:
        install_files(files,site,pwd.getpwnam(ROLE).pw_gid)
        hosts=appliance.application_hosts(HOSTS.read_text(encoding='utf-8'),json.loads(decode(files['site.json']['data'])))
        appliance.write(HOSTS,hosts)
        central_credentials()
        # La identidad cambió, y el almacén SQLite de CulinaryOS sólo responde health: se recrea vacío.
        for path in SQLITE.glob('store.sqlite*'):path.unlink()
        psql('DROP DATABASE '+DATABASE)
        psql('ALTER DATABASE '+SCRATCH+' RENAME TO '+DATABASE)
    except Exception:
        put_back(saved,files)
        subprocess.run(['systemctl','start','culinaryos-data.service','culinaryos-backend.service'],check=False)
        raise
    subprocess.run(['systemctl','daemon-reload'],check=True)
    # La copia es anterior a lo último publicado, así que esos puntos de control ya no coinciden. Declararlo aquí evita una
    # alerta falsa al arrancar; sin red, la app avisa y se repite a mano.
    if (CONFIG/'integrations/checkpoints.json').exists():
        reply=installer.app_command('--site',site,'--accept-checkpoints','Restauración con culinaryos-restore')
        if reply.returncode:print('No se registró la restauración en los puntos de control; ver SIMULACRO-RESTAURACION.md',file=sys.stderr)
    subprocess.run(['systemctl','start','culinaryos-data.service','culinaryos-backend.service'],check=True)
    if not json.loads(decode(files['site.json']['data'])).get('local_only'):subprocess.run(['systemctl','start','culinaryos-publish.service'],check=True)
    print(json.dumps(report,ensure_ascii=False))
    print('Sucursal '+site+' restaurada. Configuración anterior en '+str(saved)+'.')
    print('Licencia pendiente: el proveedor restablece la activación y aquí se activa con el código nuevo.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('kit').add_argument('output')
    q=sub.add_parser('restore');q.add_argument('--kit',required=True);q.add_argument('--dump',required=True)
    args=parser.parse_args()
    try:
        if args.command=='kit':create(args.output)
        else:restore(args.kit,args.dump)
    except Exception as error:
        print('No se completó: '+str(error),file=sys.stderr)
        print('Conserva el kit y la copia. Revisa el error antes de repetir.',file=sys.stderr)
        raise SystemExit(1)


if __name__=='__main__':
    main()
