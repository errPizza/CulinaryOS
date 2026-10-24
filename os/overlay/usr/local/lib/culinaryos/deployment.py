"""Despliegue local de un plan generado. Mutaciones sólo en Linux, root y consola."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from provision import admin,atomic,initialize
from apphost import secure_file

BEGIN="# BEGIN CulinaryOs site"
END="# END CulinaryOs site"
def hosts_content(original,fragment):
    lines=original.splitlines()
    result=[];inside=False
    for line in lines:
        if line==BEGIN:
            if inside:raise ValueError("Bloques hosts duplicados")
            inside=True;continue
        if line==END:
            if not inside:raise ValueError("Bloque hosts incompleto")
            inside=False;continue
        if not inside:result.append(line)
    if inside:raise ValueError("Bloque hosts incompleto")
    wanted=fragment.split()
    for line in result:
        values=line.split("#",1)[0].split()
        if len(values)>1 and set(values[1:]) & set(wanted[1:]) and values[0]!=wanted[0]:
            raise ValueError("Nombre local ya apunta a otra IP; revisar hosts")
    return "\n".join(result).rstrip()+"\n"+BEGIN+"\n"+fragment.rstrip()+"\n"+END+"\n"

def write_file(path,data,mode=0o644):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():raise ValueError("No sobrescribir un enlace")
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as file:
        file.write(data);file.flush();os.fsync(file.fileno());name=file.name
    os.chmod(name,mode);os.replace(name,path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def validate_chrony(config):
    # -p comprueba sintaxis y termina, sin ajustar el reloj ni abrir un servidor.
    # Las directivas como argumentos evitan depender de leer un temporal en /run
    # bajo el perfil AppArmor del binario. No se usa shell ni se desactiva AppArmor.
    directives=[line.strip() for line in config.splitlines()
                if line.strip() and not line.lstrip().startswith("#")]
    if not directives:raise ValueError("Configuración Chrony vacía")
    try:
        result=subprocess.run(["chronyd","-p",*directives],capture_output=True,
                              text=True,timeout=10,check=False)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("La validación de Chrony excedió 10 segundos") from error
    if result.returncode:
        detail=(result.stderr or result.stdout or "sin mensaje del programa").strip()
        raise RuntimeError("Chrony rechazó la configuración: "+detail[:2048])

def deploy(directory):
    admin()
    if not os.isatty(0):raise PermissionError("Usar consola local interactiva")
    directory=Path(directory)
    site=json.loads(secure_file(directory/"site.json").read_text())
    plan=json.loads(secure_file(directory/"site-plan.json").read_text())
    # Volver a generar desde datos validados; no ejecutar/copiar archivos arbitrarios del paquete.
    spec=importlib.util.spec_from_file_location("culinary_site",Path(__file__).with_name("site.py"))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    files=module.render(plan,site["node"],site["interface"],site.get("medium","ethernet"),site.get("ssid"))
    site=json.loads(files["site.json"])
    hostname=site["node"];interface=site["interface"]
    hosts=hosts_content(Path("/etc/hosts").read_text(),files["hosts.fragment"])
    branch=Path("/etc/culinaryos/branch.json")
    if branch.exists() and json.loads(branch.read_text())["site_id"]!=site["site_id"]:
        raise ValueError("No cambiar identidad de sucursal aprovisionada")
    if Path("/etc/culinaryos/application.json").exists():raise ValueError("Retirar app registrada antes de cambiar plan/interfaz")
    with tempfile.TemporaryDirectory(prefix="culinaryos-site-",dir="/run") as temp:
        temp=Path(temp)
        for name,text in files.items():write_file(temp/name,text.encode(),0o600)
        subprocess.run(["nft","--check","--file",str(temp/"nftables.conf")],check=True)
        validate_chrony(files["chrony.conf"])
        print(files["DEPLOY.txt"])
        print("Se cambiará la red de ESTE invitado y se conservarán copias de configuración.")
        if input("Escriba DESPLEGAR-SITIO: ")!="DESPLEGAR-SITIO":raise ValueError("Cancelado")
        backup=Path("/var/backups/culinaryos")/("network-"+str(time.time_ns()))
        backup.mkdir(parents=True,mode=0o700)
        targets={
            "/etc/hosts":hosts,
            "/etc/chrony/chrony.conf":files["chrony.conf"],
            "/etc/avahi/avahi-daemon.conf":files["avahi-daemon.conf"],
            "/etc/culinaryos/site.json":files["site.json"],
            "/etc/culinaryos/site-plan.json":files["site-plan.json"],
            "/etc/nftables.conf":files["nftables.conf"]}
        for destination in targets:
            p=Path(destination)
            if p.is_symlink():raise ValueError("Revisar destino que es enlace: "+destination)
            if p.exists():
                out=backup/p.relative_to("/")
                out.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                out.write_bytes(p.read_bytes());os.chmod(out,0o600)
        print("Copias de recuperación:",backup)
        profile=Path("/etc/NetworkManager/system-connections")/("culinaryos-"+site["site_id"]+"-"+site["node"]+".nmconnection")
        if profile.exists():raise FileExistsError("Perfil existente; no se sobrescribirá")
        write_file(profile,files["connection.nmconnection"].encode(),0o600)
        subprocess.run(["nmcli","connection","load",str(profile)],check=True)
        con="culinaryos-"+site["site_id"]+"-"+site["node"]+"-"+site.get("medium","ethernet")
        subprocess.run(["nmcli","device","checkpoint","--timeout","90",interface,"--",
                        "nmcli","--ask","--wait","45","connection","up","id",con],check=True)
        actual=subprocess.run(["ip","-j","-4","address","show","dev",interface],capture_output=True,text=True,check=True)
        links=json.loads(actual.stdout)
        if not any(a.get("local")==site["expected_address"] for x in links for a in x.get("addr_info",[])):
            raise RuntimeError("El checkpoint no conservó la IP esperada; no se continúa")
        subprocess.run(["/usr/local/sbin/culinaryos-firewall-apply",str(temp/"nftables.conf")],check=True)
        for destination,text in targets.items():
            if destination!="/etc/nftables.conf":write_file(destination,text.encode())
        subprocess.run(["hostnamectl","set-hostname",hostname],check=True)
        subprocess.run(["nmcli","connection","modify","id",con,"connection.autoconnect","yes","connection.autoconnect-priority","100"],check=True)
        subprocess.run(["systemctl","enable","avahi-daemon.service"],check=True)
        subprocess.run(["systemctl","restart","chrony.service","avahi-daemon.service"],check=True)
        if site["role"]=="servidor":initialize("/etc/culinaryos/site.json")
        print("Sitio desplegado; verificar desde otra terminal y reiniciar en mantenimiento.")
