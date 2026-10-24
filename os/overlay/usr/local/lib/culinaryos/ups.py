#!/usr/bin/python3
"""Preparar NUT para UPS USB identificado; nunca inicia monitor ni apagado al generar."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

def render(driver,vendor,product,serial=None):
    if driver not in ("usbhid-ups","nutdrv_qx"):raise ValueError("Seleccionar controlador compatible verificado")
    for value in (vendor,product):
        if not re.fullmatch(r"[0-9a-fA-F]{4}",value):raise ValueError("ID USB debe tener cuatro dígitos hexadecimales")
    if serial and not re.fullmatch(r"[a-zA-Z0-9 ._-]{1,96}",serial):raise ValueError("Serial no válido")
    password=secrets.token_hex(32)
    config=f"[culinaryos]\n    driver = {driver}\n    port = auto\n    vendorid = {vendor.lower()}\n    productid = {product.lower()}\n"
    if serial:config+='    serial = "'+re.escape(serial)+'"\n'
    return {
        "nut.conf":"MODE=standalone\n",
        "ups.conf":config,
        "upsd.conf":"LISTEN 127.0.0.1 3493\nLISTEN ::1 3493\n",
        "upsd.users":"[culinaryos-monitor]\n    password = "+password+"\n    upsmon primary\n",
        "upsmon.conf":'MONITOR culinaryos@localhost 1 culinaryos-monitor '+password+' primary\nMINSUPPLIES 1\nSHUTDOWNCMD "/sbin/shutdown -h +0"\nPOWERDOWNFLAG /etc/killpower\nFINALDELAY 5\nHOSTSYNC 15\nPOLLFREQ 5\nPOLLFREQALERT 5\nDEADTIME 15\n',
        "device.json":json.dumps({"driver":driver,"vendor":vendor.lower(),"product":product.lower(),"serial":serial})+"\n"
    }

def check_device(config,sysfs="/sys/bus/usb/devices"):
    matches=[]
    for path in Path(sysfs).iterdir():
        try:
            if (path/"idVendor").read_text().strip().lower()!=config["vendor"]:continue
            if (path/"idProduct").read_text().strip().lower()!=config["product"]:continue
            if config.get("serial") and (path/"serial").read_text().strip()!=config["serial"]:continue
            matches.append(path.name)
        except OSError:continue
    if len(matches)!=1:raise ValueError("Debe identificarse exactamente un UPS USB")
    return matches[0]

def install(directory):
    if sys.platform!="linux" or os.geteuid()!=0:raise PermissionError("Requiere root en el invitado con UPS USB")
    from apphost import secure_file
    directory=Path(directory)
    device=json.loads(secure_file(directory/"device.json").read_text())
    matched=check_device(device)
    print("Dispositivo USB:",matched,"Controlador:",device["driver"])
    print("Esta fase inicia sólo driver/upsd. NO inicia upsmon.")
    if input("Escriba PREPARAR-UPS: ")!="PREPARAR-UPS":raise ValueError("Cancelado")
    import grp
    nut=grp.getgrnam("nut").gr_gid
    if subprocess.run(["systemctl","is-active","--quiet","nut-monitor.service"]).returncode==0:
        raise ValueError("Detener y revisar monitor existente antes de reconfigurar")
    for name in ("ups.conf","upsd.conf","upsd.users","upsmon.conf","nut.conf"):
        secure_file(directory/name)
        if (Path("/etc/nut")/(name+".before-culinaryos")).exists():raise FileExistsError("Revisar copias de configuración UPS anteriores")
    for name in ("ups.conf","upsd.conf","upsd.users","upsmon.conf","nut.conf"):
        source=secure_file(directory/name)
        destination=Path("/etc/nut")/name
        backup=destination.with_name(name+".before-culinaryos")
        if backup.exists():raise FileExistsError("Ya hay una instalación previa; revise copias")
        if destination.exists():backup.write_bytes(destination.read_bytes());os.chmod(backup,0o600)
        destination.write_bytes(source.read_bytes());os.chown(destination,0,nut);os.chmod(destination,0o640)
    subprocess.run(["systemctl","start","nut-driver-enumerator.service"],check=True)
    subprocess.run(["upsdrvsvcctl","start","culinaryos"],check=True,timeout=45)
    subprocess.run(["systemctl","start","nut-server.service"],check=True)
    result=subprocess.run(["upsc","culinaryos@localhost","ups.status"],capture_output=True,text=True,check=True,timeout=5)
    print("UPS status:",result.stdout.strip())
    print("Verifique OL con red eléctrica y OB al retirar sólo entrada eléctrica del UPS.")
    print("Todavía no se inició el monitor. Siga docs/UPS-Y-APAGONES.md.")

def enable_monitor():
    if sys.platform!="linux" or os.geteuid()!=0:raise PermissionError("Requiere root en el invitado")
    p=subprocess.run(["upsc","culinaryos@localhost","ups.status"],capture_output=True,text=True,check=True,timeout=5)
    if "OL" not in p.stdout.split() or any(x in p.stdout.split() for x in ("LB","FSD","OB")):
        raise ValueError("Verificar UPS con alimentación y batería suficiente antes de habilitar")
    print("Upsmon podrá apagar el equipo cuando el UPS indique batería crítica.")
    if input("Escriba HABILITAR-APAGADO-UPS: ")!="HABILITAR-APAGADO-UPS":raise ValueError("Cancelado")
    subprocess.run(["systemctl","enable","nut-driver-enumerator.path","nut-server.service","nut-monitor.service"],check=True)
    subprocess.run(["systemctl","start","nut-monitor.service"],check=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest="command",required=True)
    q=sub.add_parser("prepare");q.add_argument("--driver",choices=("usbhid-ups","nutdrv_qx"),required=True)
    q.add_argument("--vendor",required=True);q.add_argument("--product",required=True);q.add_argument("--serial");q.add_argument("--output",required=True)
    q=sub.add_parser("install");q.add_argument("directory")
    sub.add_parser("enable-monitor")
    args=p.parse_args()
    if args.command=="prepare":
        files=render(args.driver,args.vendor,args.product,args.serial)
        out=Path(args.output);out.mkdir(mode=0o700,parents=True,exist_ok=False)
        for name,data in files.items():
            with open(out/name,"x",encoding="utf-8",newline="\n") as f:f.write(data)
            os.chmod(out/name,0o600)
        print("Configuración con secreto propio preparada; no activada.")
    elif args.command=="install":install(args.directory)
    else:enable_monitor()
if __name__=="__main__":main()
