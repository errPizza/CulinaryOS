#!/usr/bin/python3
"""Administración local del runtime; nunca modifica Windows ni se ejecuta al compilar."""
import argparse
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from securedata import Keyring,canonical,encode,decode
from dataio import persistent_root
from nacl import pwhash,utils
from apphost import manifest,secure_file

SECRETS=Path("/etc/culinaryos/secrets")
def admin():
    if sys.platform!="linux" or os.geteuid()!=0:raise PermissionError("Requiere root dentro del invitado Debian")
    persistent_root()
    os.umask(0o077)
def atomic(path,value,mode=0o600):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if path.is_symlink():raise ValueError("Destino no puede ser enlace")
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
        f.write(canonical(value)+b"\n");f.flush();os.fsync(f.fileno());temp=f.name
    os.chmod(temp,mode);os.replace(temp,path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def initialize(site_file,autologin=False):
    admin()
    site=json.loads(secure_file(site_file).read_text())
    if site["role"]!="servidor":raise ValueError("Aprovisionar datos sólo en servidor de sucursal")
    from store import identity
    identity(site["site_id"])
    SECRETS.mkdir(mode=0o700,exist_ok=True)
    os.chmod(SECRETS,0o700)
    keyfile=SECRETS/"branch.keys.json"
    branch=Path("/etc/culinaryos/branch.json")
    if branch.exists() and json.loads(branch.read_text())["site_id"]!=site["site_id"]:
        raise ValueError("No cambiar identidad de una sucursal con datos")
    if not keyfile.exists():
        # No regenerar claves sobre una base existente: quedaría irrecuperable.
        if Path("/var/lib/culinaryos-data/store.sqlite").exists():raise ValueError("Recuperar las claves originales antes de iniciar")
        atomic(keyfile,Keyring.generate())
    Keyring.load(keyfile)
    if not branch.exists():atomic(branch,{"version":1,"site_id":site["site_id"],"central":None},0o644)
    if autologin:
        if subprocess.run(["id","operador"],capture_output=True).returncode:raise ValueError("Completar primero el alta de operador")
        directory=Path("/etc/lightdm/lightdm.conf.d")
        directory.mkdir(parents=True,exist_ok=True)
        file=directory/"60-culinaryos-autologin.conf"
        expected="[Seat:*]\nautologin-user=operador\nautologin-user-timeout=0\n"
        if file.exists():
            if file.read_text()!=expected:raise FileExistsError("Existe otra política de login; revisar manualmente")
        else:
            with open(file,"x") as f:f.write(expected)
        os.chmod(file,0o644)
    subprocess.run(["systemctl","enable","--now","culinaryos-data.service","culinaryos-sync.timer"],check=True)
    configured=json.loads(branch.read_text()).get("central")
    print("Almacén aprovisionado; sincronización con el central configurado habilitada." if configured else "Almacén aprovisionado. Central sin configurar; no se envían datos.")

def register(source):
    admin()
    from deployment import write_file
    cfg=manifest(source,check_credentials=True)
    site=json.loads(Path("/etc/culinaryos/site.json").read_text())
    if Path("/etc/culinaryos/application.json").exists():raise FileExistsError("Ya existe app registrada; actualizar en mantenimiento")
    server=cfg.get("mode","server")=="server"
    if server and (site["role"]!="servidor" or not Path("/etc/culinaryos/branch.json").exists()):
        raise ValueError("Aprovisionar primero el servidor de sucursal")
    if not server and site["role"]=="servidor":raise ValueError("En servidor usar manifiesto server")
    if not server:
        if cfg.get("credentials"):raise ValueError("Las credenciales de servicio no se entregan a la UI")
        atomic("/etc/culinaryos/application.json",cfg,0o644)
        site["application"]={"port":cfg["port"],"ca_file":cfg["tls_ca_file"]}
        atomic("/etc/culinaryos/site.json",site,0o644)
        write_file("/etc/culinaryos/application.registered",b"1\n")
        return
    local_only=site.get("local_only") is True
    rules=Path("/etc/nftables.conf").read_text()
    if not local_only and ("set application_ports" not in rules or "tcp dport @application_ports" not in rules):
        raise ValueError("Instalar primero el firewall de sitio")
    candidate=rules if local_only else rules.replace("type inet_service;","type inet_service;\n        elements = { "+str(cfg["port"])+" };",1)
    dropin=Path("/etc/systemd/system/culinaryos-backend.service.d/credentials.conf")
    if dropin.exists():raise FileExistsError("Revisar credenciales anteriores")
    applied=False
    try:
        atomic("/etc/culinaryos/application.json",cfg,0o644)
        write_file("/etc/culinaryos/application.server",b"1\n")
        text="[Unit]\n"+("" if local_only else "Wants=culinaryos-publish.service\n")+"[Service]\n"+"".join("LoadCredential="+key+":"+value+"\n" for key,value in cfg.get("credentials",{}).items())
        write_file(dropin,text.encode())
        subprocess.run(["systemctl","daemon-reload"],check=True)
        subprocess.run(["systemctl","start","culinaryos-backend.service"],check=True)
        from lan import tls
        if tls(site["server_address"],cfg["port"],site["server_name"],cfg["tls_ca_file"]) is not True:
            raise RuntimeError("El backend real no superó TLS local; no se abrirá el puerto")
        if not local_only:
            with tempfile.NamedTemporaryFile(mode="w",dir="/run",suffix=".nft",delete=False) as file:
                file.write(candidate);name=file.name
            try:subprocess.run(["/usr/local/sbin/culinaryos-firewall-apply",name],check=True)
            finally:Path(name).unlink(missing_ok=True)
            applied=True
        site["application"]={"port":cfg["port"],"ca_file":cfg["tls_ca_file"]}
        atomic("/etc/culinaryos/site.json",site,0o644)
        write_file("/etc/culinaryos/application.registered",b"1\n")
        subprocess.run(["systemctl","enable","culinaryos-backend.service",*(() if local_only else ("culinaryos-publish.service",))],check=True)
        if not local_only:subprocess.run(["systemctl","start","culinaryos-publish.service"],check=True)
    except Exception:
        subprocess.run(["systemctl","stop","culinaryos-publish.service","culinaryos-backend.service"],check=False)
        for path in ("/etc/culinaryos/application.json","/etc/culinaryos/application.server","/etc/culinaryos/application.registered"):
            Path(path).unlink(missing_ok=True)
        dropin.unlink(missing_ok=True)
        if applied:
            with tempfile.NamedTemporaryFile(mode="w",dir="/run",suffix=".nft",delete=False) as file:
                file.write(rules);rollback=file.name
            try:subprocess.run(["nft","--file",rollback],check=True)
            finally:Path(rollback).unlink(missing_ok=True)
            write_file("/etc/nftables.conf",rules.encode())
        site["application"]=None;atomic("/etc/culinaryos/site.json",site,0o644)
        subprocess.run(["systemctl","daemon-reload"],check=False)
        raise
    print("Backend real y TLS verificados; acceso solo desde este equipo." if local_only else "Backend real y TLS verificados; puerto limitado a LAN y anuncio activados.")

def configure_central(source):
    admin()
    from syncworker import HTTPSCentral
    from deployment import write_file
    cfg=json.loads(secure_file(source).read_text())
    for key in ("ca_file","client_certificate","client_key"):secure_file(cfg[key])
    secure_file(cfg["client_key"],secret=True)
    HTTPSCentral(cfg)
    branch=Path("/etc/culinaryos/branch.json")
    value=json.loads(branch.read_text())
    subprocess.run(["systemctl","stop","culinaryos-sync.timer","culinaryos-sync.service"],check=True)
    try:
        destinations={"ca_file":"central-ca.crt","client_certificate":"central-client.crt","client_key":"central-client.key"}
        stored=dict(cfg)
        for key,name in destinations.items():
            target=SECRETS/name
            write_file(target,Path(cfg[key]).read_bytes(),0o600)
            stored[key]=str(target)
        value["central"]=stored;atomic(branch,value,0o644)
    finally:subprocess.run(["systemctl","start","culinaryos-sync.timer"],check=True)
    print("Central configurado; eventos persistidos se enviarán por mTLS.")

def key_backup(output,restore=False,site_id=None):
    admin()
    from securedata import protect_keyring,unprotect_keyring
    for path in ("/etc/culinaryos/branch.json","/etc/culinaryos/site.json"):
        if Path(path).exists():
            expected=json.loads(Path(path).read_text())["site_id"]
            if site_id and site_id!=expected:raise ValueError("Sucursal indicada no coincide")
            site_id=expected;break
    if not site_id:raise ValueError("Indicar --site-id para recuperación sin configuración")
    password=getpass.getpass("Contraseña de la copia de claves: ")
    if restore:
        original=unprotect_keyring(json.loads(Path(output).read_text()),password,site_id)
        if (SECRETS/"branch.keys.json").exists():raise FileExistsError("No sobrescribir claves existentes")
        atomic(SECRETS/"branch.keys.json",original)
    else:
        if password!=getpass.getpass("Repita la contraseña: "):raise ValueError("No coincide")
        if Path(output).exists():raise FileExistsError(output)
        original=json.loads((SECRETS/"branch.keys.json").read_text())
        atomic(output,protect_keyring(original,password,site_id))

def rotate():
    admin()
    # Mantener claves antiguas hasta comprobar datos, snapshots y copias.
    file=SECRETS/"branch.keys.json";value=json.loads(file.read_text())
    new=Keyring.generate();value["keys"].update(new["keys"]);value["active"]=new["active"]
    Keyring(value);atomic(file,value)
    subprocess.run(["systemctl","stop","culinaryos-sync.timer","culinaryos-sync.service","culinaryos-backend.service","culinaryos-data.service"],check=True)
    try:
        subprocess.run(["systemctl","start","culinaryos-rekey.service"],check=True)
    finally:
        subprocess.run(["systemctl","start","culinaryos-data.service","culinaryos-sync.timer"],check=True)
        if Path("/etc/culinaryos/application.json").exists():
            subprocess.run(["systemctl","start","culinaryos-backend.service","culinaryos-publish.service"],check=True)

def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="command",required=True)
    q=sub.add_parser("init");q.add_argument("--site",default="/etc/culinaryos/site.json");q.add_argument("--autologin",action="store_true")
    q=sub.add_parser("deploy-site");q.add_argument("directory")
    q=sub.add_parser("register-app");q.add_argument("manifest")
    q=sub.add_parser("central");q.add_argument("config")
    for name in ("backup-keys","restore-keys"):
        q=sub.add_parser(name);q.add_argument("file");q.add_argument("--site-id")
    sub.add_parser("rotate")
    args=p.parse_args()
    if args.command=="init":initialize(args.site,args.autologin)
    elif args.command=="deploy-site":
        from deployment import deploy
        deploy(args.directory)
    elif args.command=="register-app":register(args.manifest)
    elif args.command=="central":configure_central(args.config)
    elif args.command=="backup-keys":key_backup(args.file,site_id=args.site_id)
    elif args.command=="restore-keys":key_backup(args.file,True,args.site_id)
    elif args.command=="rotate":rotate()
if __name__=="__main__":main()
