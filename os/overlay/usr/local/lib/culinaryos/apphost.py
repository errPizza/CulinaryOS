#!/usr/bin/python3
"""Registro y arranque de ejecutables reales, sin app de demostración."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from dataio import Client,notify

MANIFEST=Path("/etc/culinaryos/application.json")
def secure_file(value,executable=False,secret=False):
    p=Path(value)
    if not p.is_absolute() or not p.is_file() or p.is_symlink():raise ValueError("Ruta absoluta regular requerida")
    if executable and not os.access(p,os.X_OK):raise ValueError("Ejecutable no disponible")
    if secret and sys.platform=="linux" and p.stat().st_mode & 0o077:
        raise PermissionError("Credencial requiere permisos 0600")
    resolved=p.resolve(strict=True)
    if sys.platform=="linux":
        for entry in (p,*p.parents,resolved,*resolved.parents):
            st=entry.stat()
            if st.st_uid!=0 or st.st_mode & 0o022:raise PermissionError("Ruta debe pertenecer a root y no ser modificable por usuarios")
    return resolved
def manifest(path=MANIFEST,check_credentials=False):
    secure_file(path)
    cfg=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(cfg,dict) or cfg.get("version")!=1:raise ValueError("Manifiesto incompatible")
    if cfg.get("mode","server") not in ("server","terminal"):raise ValueError("Modo de aplicación no válido")
    for key in (("ui_argv","backend_argv") if cfg.get("mode","server")=="server" else ("ui_argv",)):
        args=cfg.get(key)
        if not isinstance(args,list) or not args or not all(isinstance(v,str) and "\0" not in v for v in args):
            raise ValueError("Argumentos no válidos")
        executable=secure_file(args[0],True)
        if not executable.is_relative_to("/opt/culinaryos-app") and sys.platform=="linux":
            raise ValueError("Instalar ejecutables en /opt/culinaryos-app")
    if type(cfg.get("port")) is not int or not 1024<=cfg["port"]<=65535:raise ValueError("Puerto no válido")
    expected="/run/culinaryos-app/ready.sock"
    if cfg.get("mode","server")=="server" and cfg.get("readiness_socket")!=expected:raise ValueError("Usar socket de readiness reservado")
    secure_file(cfg["tls_ca_file"])
    for key,value in cfg.get("credentials",{}).items():
        if not __import__("re").fullmatch(r"[a-z][a-z0-9-]{0,31}",key):raise ValueError("ID de credencial inválido")
        if not __import__("re").fullmatch(r"/[a-zA-Z0-9_./-]+",value):raise ValueError("Ruta de credencial no compatible")
        if check_credentials:secure_file(value,secret=True)
    return cfg

def backend_ready(cfg):
    # Contrato v1: servicio responde ready=true e identidad de sucursal por Unix socket.
    try:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
            conn.settimeout(.5);conn.connect(cfg["readiness_socket"])
            conn.sendall(b'{"op":"readiness","protocol":1}\n')
            with conn.makefile("rb") as f:raw=f.readline(4097)
        reply=json.loads(raw)
        site=json.loads(Path("/etc/culinaryos/site.json").read_text())["site_id"]
        return len(raw)<=4096 and reply.get("ready") is True and reply.get("site_id")==site
    except (OSError,ValueError,KeyError):return False

def backend(cfg):
    if not Client().call("health").get("ready"):raise RuntimeError("Almacén no disponible")
    child=subprocess.Popen(cfg["backend_argv"],shell=False)
    stopping=False
    def stop(signum,frame):
        nonlocal stopping
        stopping=True
        if child.poll() is None:child.terminate()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    started=time.monotonic()
    try:
        while not stopping and child.poll() is None:
            if backend_ready(cfg):
                notify("READY=1\nSTATUS=Backend de aplicación disponible")
                return child.wait()
            if time.monotonic()-started>30:raise TimeoutError("Backend no indicó disponibilidad")
            time.sleep(.25)
        return child.wait()
    finally:
        if child.poll() is None:
            child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()

def session():
    if not MANIFEST.exists():
        os.execv("/usr/bin/python3",["python3","/usr/local/lib/culinaryos/welcome.py"])
    try:
        cfg=manifest()
        if not Path("/etc/culinaryos/application.registered").exists():raise RuntimeError("Registro no completado")
        if cfg.get("mode","server")=="terminal":os.execv(cfg["ui_argv"][0],cfg["ui_argv"])
        for _ in range(30):
            p=subprocess.run(["systemctl","is-active","--quiet","culinaryos-backend.service"],timeout=2)
            if p.returncode==0:os.execv(cfg["ui_argv"][0],cfg["ui_argv"])
            time.sleep(.5)
        raise RuntimeError("COS-APP-NOT-READY")
    except Exception:
        # Pantalla real de diagnóstico; no aparentar app disponible si falló.
        os.execv("/usr/bin/python3",["python3","/usr/local/lib/culinaryos/welcome.py"])

def publish(cfg):
    from discovery import publish_arguments
    site=json.loads(Path("/etc/culinaryos/site.json").read_text())
    if not backend_ready(cfg):raise RuntimeError("No anunciar un backend no disponible")
    child=subprocess.Popen(publish_arguments(site,cfg["port"]),shell=False)
    def stop(signum,frame):
        if child.poll() is None:child.terminate()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    return child.wait()

def main():
    p=argparse.ArgumentParser();p.add_argument("mode",choices=("session","backend","publish","validate"));args=p.parse_args()
    if args.mode=="session":session();return
    cfg=manifest()
    if args.mode=="backend":raise SystemExit(backend(cfg))
    if args.mode=="publish":raise SystemExit(publish(cfg))
    print("Manifiesto y ejecutables comprobados")
if __name__=="__main__":main()
