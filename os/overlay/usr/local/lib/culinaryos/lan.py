#!/usr/bin/python3
"""Sondas limitadas de LAN y clasificación prudente; sin aplicación simulada."""
import ipaddress
import json
from pathlib import Path
import socket
import ssl
import subprocess

def run(argv,timeout=2):
    try:
        p=subprocess.run(argv,capture_output=True,text=True,timeout=timeout,check=False)
        return p.stdout if p.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired):
        return None

def ping(address):
    return run(["ping","-n","-c","1","-W","1",str(ipaddress.ip_address(address))]) is not None

def tcp(address,port):
    try:
        with socket.create_connection((address,port),timeout=1):return True
    except OSError:return False

def tls(address,port,name,ca_file):
    try:
        ctx=ssl.create_default_context(cafile=ca_file)
        with socket.create_connection((address,port),timeout=1) as conn:
            with ctx.wrap_socket(conn,server_hostname=name):pass
        return True
    except ssl.SSLCertVerificationError:return False
    except (OSError,ssl.SSLError):return None

def collect(cfg):
    e={"configured":True,"role":cfg["role"],"application_configured":bool(cfg.get("application")),
       "internet_configured":bool(cfg.get("internet_probes"))}
    raw=run(["ip","-j","address","show","dev",cfg["interface"]])
    try:
        links=json.loads(raw)
        e["link"]=any("LOWER_UP" in x.get("flags",[]) for x in links)
        e["address"]=any(a.get("local")==cfg["expected_address"] for x in links for a in x.get("addr_info",[]))
    except (TypeError,ValueError):
        e.update(link=None,address=None)
    if e["link"] is False or e["address"] is False:
        return e
    gateway=cfg.get("gateway")
    e["gateway_configured"]=bool(gateway)
    e["gateway"]=ping(gateway) if gateway else None
    if cfg["role"]!="servidor":e["server"]=ping(cfg["server_address"])
    raw=run(["getent","ahostsv4",cfg["server_name"]])
    e["name"]=cfg["server_address"] in {line.split()[0] for line in raw.splitlines()} if raw else False
    app=cfg.get("application")
    if app:
        e["service_tcp"]=tcp(cfg["server_address"],app["port"])
        if e["service_tcp"]:e["server"]=True
        e["tls"]=tls(cfg["server_address"],app["port"],cfg["server_name"],app["ca_file"]) if e["service_tcp"] else None
    probes=cfg.get("internet_probes",[])
    if probes:
        results=[tcp(p["address"],p["port"]) for p in probes[:2]]
        e["internet"]=any(results)
    return e

def evaluate(e):
    rows=[]
    def add(code,part,state,message,action):
        rows.append({"id":"COS-LAN-"+code,"parte":part,"gravedad":state,"mensaje":message,"accion":action})
    if not e or not e.get("configured"):
        add("CONFIG","Red del establecimiento","no_aplica","No hay un sitio desplegado en este equipo.","Prepare y revise el plan de red local.")
        return rows
    if e.get("config_error"):
        add("CONFIG","Red del establecimiento","aviso","La configuración local no es válida.","Solicite revisar site.json; no se ejecutaron sondas.")
        return rows
    link=e.get("link");address=e.get("address")
    if link is False:
        add("LINK","Red interna","aviso","No hay enlace en la interfaz operativa configurada.","Revise cable, switch, Wi-Fi o punto de acceso; no se puede atribuir el fallo a internet.")
    elif link is None:
        add("LINK","Red interna","desconocido","No se pudo comprobar la interfaz operativa.","Solicite revisar interfaz y NetworkManager.")
    else:
        add("LINK","Red interna","correcto","Hay enlace físico o asociación Wi-Fi; esto no prueba acceso al servidor.","Consulte los indicadores de acceso y nombre local.")
    if address is False:
        add("ADDRESS","Direccionamiento","aviso","La IP local no coincide con el plan.","Solicite revisar el perfil, conflictos IP y el inventario.")
    elif address is None:
        add("ADDRESS","Direccionamiento","desconocido","No se pudo comprobar la IP local.","Solicite revisar el perfil de red.")
    else:
        add("ADDRESS","Direccionamiento","correcto","La IP configurada coincide con el plan; no descarta una IP duplicada.","Investigue conflictos si la conexión es intermitente.")
    usable=link is True and address is True
    if e.get("role")=="servidor":
        add("SERVER","Equipo servidor","no_aplica","Este equipo es el servidor; consulte sus indicadores del sistema.","No se simula disponibilidad de una aplicación.")
    else:
        v=e.get("server") if usable else None
        state="correcto" if v is True else "aviso" if v is False else "desconocido"
        msg="El equipo servidor respondió a una sonda; no prueba que exista aplicación." if v is True else "El servidor no respondió desde esta terminal; puede ser equipo, ruta, aislamiento o firewall." if v is False else "No se pudo evaluar el acceso al servidor."
        add("SERVER","Acceso al servidor",state,msg,"Compare desde otra terminal y revise el servidor desde su consola.")
    v=e.get("name") if usable else None
    add("NAME","Nombre local","correcto" if v is True else "aviso" if v is False else "desconocido",
        "El nombre local resuelve a la IP prevista." if v is True else "El nombre local falta o no corresponde al servidor." if v is False else "Resolución local sin comprobar.",
        "Revise hosts administrado o DNS local; no cambie a DNS público para resolver un nombre privado.")
    if e.get("application_configured"):
        v=e.get("service_tcp") if usable else None
        add("SERVICE","Servicio futuro","correcto" if v is True else "aviso" if v is False else "desconocido",
            "Un puerto configurado acepta TCP; esto no prueba operaciones de la aplicación." if v is True else "El servicio configurado no acepta TCP o no pudo comprobarse.",
            "Revise la unidad y su disponibilidad desde administración.")
        v=e.get("tls") if usable else None
        add("TLS","Confianza TLS","correcto" if v is True else "aviso" if v is False else "desconocido",
            "La negociación TLS validó nombre, vigencia y cadena local." if v is True else "El certificado no pasó validación." if v is False else "TLS no pudo comprobarse.",
            "Revise CA, SAN, reloj y renovación; no desactive la validación.")
    else:
        add("SERVICE","Aplicación","no_aplica","Aplicación pendiente de integración; no hay servicio que comprobar.","La integración posterior añadirá un chequeo funcional real.")
    if e.get("gateway_configured"):
        v=e.get("gateway") if usable else None
        add("GATEWAY","Router local","correcto" if v is True else "aviso" if v is False else "desconocido",
            "El router respondió; esto no prueba acceso a internet." if v is True else "Router sin respuesta ICMP o sin comprobar; la comunicación directa en LAN puede continuar.",
            "Revise alimentación, VLAN y política ICMP; no reinicie el servidor sólo por este indicador.")
    if e.get("internet_configured"):
        v=e.get("internet") if usable else None
        msg="Al menos una sonda externa aceptó TCP; no demuestra acceso a todos los destinos." if v is True else "Las sondas externas no respondieron: posible caída de salida, filtrado o destinos externos." if v is False else "Internet sin comprobar por falta de evidencia de red interna."
        if v is False and e.get("server") is True:msg+=" El equipo servidor sigue accesible en la LAN."
        add("INTERNET","Salida a internet","correcto" if v is True else "aviso" if v is False else "desconocido",msg,
            "Mantenga el uso local cuando su servicio esté disponible; revise router y proveedor por separado.")
    else:
        add("INTERNET","Salida a internet","no_aplica","No se sondea internet: no es requisito del funcionamiento local.","Si necesita distinguir su caída, autorice hasta dos destinos externos en el plan.")
    return rows

def from_file(path="/etc/culinaryos/site.json"):
    p=Path(path)
    if not p.exists():return evaluate({})
    try:
        cfg=json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(cfg,dict):raise ValueError()
        if not cfg.get("enabled"):return evaluate({})
        if cfg["role"] not in ("servidor","meseros","cocina","gerente"):raise ValueError()
        net=ipaddress.ip_network(cfg["network"],strict=True)
        if net.version!=4 or not any(net.subnet_of(ipaddress.ip_network(n)) for n in ("10.0.0.0/8","172.16.0.0/12","192.168.0.0/16")):raise ValueError()
        for key in ("expected_address","server_address"):
            address=ipaddress.IPv4Address(cfg[key])
            if address not in net or address in (net.network_address,net.broadcast_address):raise ValueError()
        if cfg.get("gateway") and ipaddress.ip_address(cfg["gateway"]) not in net:raise ValueError()
        if not isinstance(cfg["interface"],str) or not cfg["interface"] or len(cfg["interface"])>15:raise ValueError()
        if not isinstance(cfg["server_name"],str) or not cfg["server_name"]:raise ValueError()
        if len(cfg.get("internet_probes",[]))>2:raise ValueError()
        for probe in cfg.get("internet_probes",[]):
            if not ipaddress.ip_address(probe["address"]).is_global or type(probe["port"]) is not int or not 1<=probe["port"]<=65535:raise ValueError()
        app=cfg.get("application")
        if app and (type(app["port"]) is not int or not 1<=app["port"]<=65535 or not Path(app["ca_file"]).is_absolute()):raise ValueError()
        return evaluate(collect(cfg))
    except (OSError,ValueError,KeyError,TypeError):
        return evaluate({"configured":True,"config_error":True})
