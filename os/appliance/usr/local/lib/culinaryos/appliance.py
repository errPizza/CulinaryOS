#!/usr/bin/python3
"""First boot of the integrated image. Creates fresh identities on installed disks only."""
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time

BASE=Path('/etc/culinaryos')
STATE=Path('/var/lib/culinaryos')
APP=Path('/opt/culinaryos-app')
# Kiosk copy of the one-time Setup code; Culinary Restaurant's bridge removes it after Setup.
SETUP=Path('/var/lib/culinary-restaurant-setup')


def run(*args,**kwargs):
    return subprocess.run(list(map(str,args)),check=True,**kwargs)


def write(path,data,mode=0o644):
    from deployment import write_file
    write_file(path,data.encode('utf-8') if isinstance(data,str) else data,mode)


def network_config(site_id):
    # Debian Installer already configures DHCP when a network is available.
    # Keep the application local until its own Setup flow configures a site.
    return {'enabled':True,'site_id':site_id,'node':'culinaryos','role':'servidor','interface':'lo',
            'network':'127.0.0.0/8','expected_address':'127.0.0.1','server_address':'127.0.0.1',
            'server_name':'culinaryos.internal','gateway':None,'application':None,'internet_probes':[],
            'mdns_name':'servidor-restaurante.local','local_only':True},None

def create_private(path,data,uid=0,gid=0):
    # New file only, never through a link; ownership is set before anything is written.
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_BINARY',0),0o600)
    try:
        if hasattr(os,'fchown'):os.fchown(fd,uid,gid)
        os.write(fd,data);os.fsync(fd)
    finally:os.close(fd)


def prepare_setup(operator):
    """One-time code for Culinary Restaurant's Setup mode.

    The backend receives the root copy through systemd LoadCredential and the kiosk
    account gets its own copy. The code only works while the branch has no restaurant.
    """
    code_file=BASE/'secrets'/'restaurant-setup.code'
    if code_file.is_symlink():raise ValueError('El codigo de Setup no puede ser un enlace')
    if not code_file.exists():create_private(code_file,(secrets.token_urlsafe(32)+'\n').encode('ascii'))
    if SETUP.is_symlink():raise ValueError('El directorio de Setup no puede ser un enlace')
    SETUP.mkdir(mode=0o700,exist_ok=True)
    os.chown(SETUP,operator.pw_uid,operator.pw_gid);os.chmod(SETUP,0o700)
    kiosk_copy=SETUP/'setup-code'
    if not kiosk_copy.exists():create_private(kiosk_copy,code_file.read_bytes(),operator.pw_uid,operator.pw_gid)
    return code_file


def application_hosts(original,site):
    from deployment import hosts_content
    # Debian Installer may use the service FQDN as a local machine alias.
    # Move only that name off loopback; preserve all other aliases/comments.
    lines=[]
    for line in original.splitlines():
        content,separator,comment=line.partition('#')
        values=content.split()
        try:loopback=bool(values) and ipaddress.ip_address(values[0]).is_loopback
        except ValueError:loopback=False
        if loopback and site['server_name'] in values[1:]:
            values=[values[0],*[name for name in values[1:] if name!=site['server_name']]]
            line=(' '.join(values) if len(values)>1 else '')
            if separator:line+=(' ' if line else '')+'#'+comment
            if not line:continue
        lines.append(line)
    return hosts_content('\n'.join(lines),site['server_address']+' '+site['server_name'])


def ensure_network(site,rendered):
    from deployment import validate_chrony
    hosts=application_hosts(Path('/etc/hosts').read_text(encoding='utf-8'),site)
    if rendered is not None:
        profile=Path('/etc/NetworkManager/system-connections')/('culinaryos-'+site['site_id']+'.nmconnection')
        if profile.exists():raise ValueError('El perfil ya existe; no se sustituye')
        write(profile,rendered['connection.nmconnection'],0o600)
        run('nmcli','connection','load',profile)
        name='culinaryos-'+site['site_id']+'-culinaryos-ethernet'
        run('nmcli','--wait','45','connection','up','id',name)
        run('nmcli','connection','modify','id',name,'connection.autoconnect','yes')
        validate_chrony(rendered['chrony.conf'])
        write('/etc/chrony/chrony.conf',rendered['chrony.conf'])
        write('/etc/avahi/avahi-daemon.conf',rendered['avahi-daemon.conf'])
        # Validate and atomically apply the generated LAN rules using the OS helper.
        candidate=Path('/run/culinaryos-appliance.nft')
        write(candidate,rendered['nftables.conf'],0o600)
        try:run('/usr/local/sbin/culinaryos-firewall-apply',candidate)
        finally:candidate.unlink(missing_ok=True)
        run('systemctl','enable','--now','avahi-daemon.service')
        run('systemctl','restart','chrony.service')
    write('/etc/hosts',hosts)
    write(BASE/'site.json',json.dumps(site,indent=2)+'\n')


def main():
    import pwd
    from dataio import persistent_root,Client
    from apphost import secure_file
    from provision import initialize,register
    import appliance_install as installer
    if sys.platform!='linux' or os.geteuid()!=0:raise PermissionError('Solo en el primer arranque instalado')
    persistent_root()
    if (STATE/'provisioned').exists():return
    if not os.isatty(0) or not os.isatty(1):raise PermissionError('Se requiere la consola local')
    os.umask(0o077)
    if not (STATE/'installer-complete').is_file():raise ValueError('Completa el instalador de disco desde el menu de arranque de la ISO')
    admin=secure_file(STATE/'setup-admin').read_text(encoding='ascii').strip()
    account=pwd.getpwnam(admin)
    if account.pw_uid<1000 or admin=='operador':raise ValueError('Cuenta administradora no valida')
    print('CulinaryOS · configuracion inicial')
    print('Administrador del sistema: '+admin+' (creado por ti durante la instalacion).')
    print('Cada equipo crea ahora sus propias claves, certificados y sucursal.')
    try:operator=pwd.getpwnam('operador')
    except KeyError:
        run('useradd','-m','-s','/bin/bash','-G','audio,video','operador');operator=pwd.getpwnam('operador')
    if 'sudo' in run('id','-nG','operador',capture_output=True,text=True).stdout.split():
        raise PermissionError('El operador no debe ser administrador')
    if not (STATE/'operator-password-set').exists():
        # LightDM uses this kiosk account only for autologin; do not block the
        # first boot before CulinaryRestaurant can display its Setup screen.
        password=secrets.token_urlsafe(48)
        run('chpasswd',input='operador:'+password+'\n',text=True)
        del password
        write(STATE/'operator-password-set','1\n',0o600)
    if not (BASE/'site.json').exists():
        site_id='site-'+secrets.token_hex(8)
        site,rendered=network_config(site_id)
        ensure_network(site,rendered)
    else:
        site=json.loads(secure_file(BASE/'site.json').read_text(encoding='utf-8'))
    initialize(BASE/'site.json')
    for attempt in range(40):
        try:
            if Client().call('health').get('ready'):break
        except (OSError,ValueError):pass
        time.sleep(.25)
    else:raise RuntimeError('El almacen no quedo disponible; conservar las claves y revisar el servicio')
    # The backend keeps the branch in PostgreSQL: its role and database exist before registration starts it.
    run('systemctl','start','postgresql.service')
    installer.postgres_database()
    ca,cert,key=installer.certificates(site)
    installer.write_new(BASE/'restaurant-connection.json',(json.dumps(installer.connection(site,ca),indent=2)+'\n').encode())
    installer.tls_renewal()
    # The restaurant and its manager are created in the app's Setup mode, not on this console.
    setup_code=prepare_setup(operator)
    if not (BASE/'application.registered').exists():
        manifest={'version':1,'mode':'server','ui_argv':[str(APP/'client/CulinaryRestaurant')],
                  'backend_argv':[str(APP/'backend/MesaNexo.Api'),'--site',site['site_id'],'--port','8443','--license-server',(APP/'license-server.txt').read_text(encoding='ascii').strip()],
                  'port':8443,'readiness_socket':'/run/culinaryos-app/ready.sock','tls_ca_file':str(ca),
                  'credentials':{'tls-key':str(key),'tls-cert':str(cert),'setup-code':str(setup_code),'keyring':str(installer.KEYRING)}}
        installer.write_new(APP/'application.json',(json.dumps(manifest,indent=2)+'\n').encode())
        register(APP/'application.json')
    write(STATE/'provisioned','1\n',0o600)
    print('Culinary Restaurant listo. Completa ahora la configuracion del gerente en pantalla.')


if __name__=='__main__':
    try:main()
    except Exception as error:
        print('Configuracion sin completar: '+str(error),file=sys.stderr)
        print('Conserva los datos y las claves. Usa tu cuenta administradora en Ctrl+Alt+F2.',file=sys.stderr)
        raise SystemExit(1)
