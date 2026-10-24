#!/usr/bin/python3
"""Copias de configuración no secreta; restauración exclusivamente a un directorio nuevo."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tarfile
import tempfile
import time

SOURCES=("etc/culinaryos/site.json","etc/hosts","etc/chrony/chrony.conf",
         "etc/NetworkManager/conf.d/20-culinaryos-local.conf","etc/culinaryos/health.json","etc/culinaryos/backup.json","etc/nftables.conf",
         "etc/default/keyboard","etc/default/locale","etc/timezone","etc/apt/apt.conf.d/52culinaryos",
         "etc/sysctl.d/60-culinaryos.conf","etc/systemd/journald.conf.d/culinaryos.conf")

def sync_directory(path):
    if os.name == "posix":
        fd=os.open(path,os.O_RDONLY | getattr(os,"O_DIRECTORY",0))
        try: os.fsync(fd)
        finally: os.close(fd)

def checksum(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def validate(archive):
    if Path(archive).stat().st_size > 64*1024*1024:
        raise ValueError("Copia demasiado grande")
    members=[]
    seen=set()
    with tarfile.open(archive,"r:gz") as t:
        for m in t:
            p=PurePosixPath(m.name)
            if p.is_absolute() or ".." in p.parts or m.name not in SOURCES or not m.isfile() or m.size>1024*1024:
                raise ValueError("Contenido fuera de la lista permitida")
            if m.name in seen:
                raise ValueError("Entradas duplicadas")
            seen.add(m.name)
            members.append(m)
            if len(members)>len(SOURCES):
                raise ValueError("Demasiadas entradas")
        if not members:
            raise ValueError("Copia vacía")
    return members

def create(root,destination):
    destination=Path(destination)
    name="culinaryos-"+time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())+"-"+str(time.time_ns())+".tar.gz"
    target=destination/name
    temp=destination/(name+".partial")
    try:
        with tarfile.open(temp,"w:gz") as t:
            for relative in SOURCES:
                p=Path(root)/relative
                if p.is_file() and not p.is_symlink():
                    t.add(p,arcname=relative,recursive=False)
        validate(temp)
        os.chmod(temp,0o600)
        with open(temp,"rb+") as f: os.fsync(f.fileno())
        digest=checksum(temp)
        os.replace(temp,target)
        sidecar=Path(str(target)+".sha256")
        with open(sidecar,"x",encoding="ascii") as f:
            f.write(digest+"\n"); f.flush(); os.fsync(f.fileno())
        os.chmod(sidecar,0o600)
        sync_directory(destination)
        return target
    except Exception:
        target.unlink(missing_ok=True)
        Path(str(target)+".sha256").unlink(missing_ok=True)
        raise
    finally:
        temp.unlink(missing_ok=True)

def restore_staging(archive,destination):
    archive=Path(archive)
    expected=Path(str(archive)+".sha256").read_text(encoding="ascii").strip()
    if checksum(archive)!=expected:
        raise ValueError("Checksum incorrecto")
    members=validate(archive)
    destination=Path(destination)
    # No sobrescribir y no seguir enlaces de un árbol preexistente.
    destination.mkdir(mode=0o700,exist_ok=False)
    with tarfile.open(archive,"r:gz") as t:
        for m in members:
            target=destination/m.name
            target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            data=t.extractfile(m)
            with open(target,"xb") as output:
                output.write(data.read())
            os.chmod(target,0o600)
    return destination

def backup():
    if os.geteuid()!=0:
        raise PermissionError("Requiere administrador")
    os.umask(0o077)
    cfg=json.loads(Path("/etc/culinaryos/backup.json").read_text())
    if not cfg.get("enabled"):
        raise ValueError("Respaldo externo no configurado")
    dest=Path(cfg["destination"]).resolve()
    if not dest.is_mount() or dest.stat().st_dev==Path("/").stat().st_dev:
        raise ValueError("Se requiere otro volumen montado y protegido")
    if dest.stat().st_uid!=0 or dest.stat().st_mode & 0o077:
        raise ValueError("Destino debe pertenecer a root y tener permisos 0700")
    keep=cfg.get("retention",7)
    if not isinstance(keep,int) or not 2<=keep<=100:
        raise ValueError("Retención permitida: 2 a 100")
    target=create("/",dest)
    # Verificación de extracción antes de retener o eliminar copias antiguas.
    with tempfile.TemporaryDirectory(prefix="culinaryos-verify-") as tmp:
        restore_staging(target,Path(tmp)/"restore")
    old=[]
    for p in dest.glob("culinaryos-*.tar.gz"):
        sidecar=Path(str(p)+".sha256")
        if sidecar.is_file() and sidecar.read_text(encoding="ascii").strip()==checksum(p):
            old.append(p)
    old.sort(key=lambda p:p.stat().st_mtime,reverse=True)
    for p in old[keep:]:
        p.unlink()
        Path(str(p)+".sha256").unlink(missing_ok=True)
    sync_directory(dest)
    return {"ok":True,"verified_at":time.time(),"archive":target.name}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--restore-staging",nargs=2,metavar=("ARCHIVO","DIRECTORIO_NUEVO"))
    args=parser.parse_args()
    if args.restore_staging:
        restore_staging(*args.restore_staging)
        return
    status_path=Path("/var/lib/culinaryos/backup-status.json")
    try:
        status=backup()
    except Exception:
        # No exponer rutas o datos sensibles en el panel.
        status_path.write_text(json.dumps({"ok":False,"failed_at":time.time()}))
        os.chmod(status_path,0o600)
        raise
    temp=status_path.with_suffix(".tmp")
    temp.write_text(json.dumps(status))
    os.chmod(temp,0o600)
    os.replace(temp,status_path)
if __name__=="__main__":
    main()
