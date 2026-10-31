#!/usr/bin/python3
"""Diagnóstico acotado. La interfaz pública recibe códigos y mensajes, nunca trazas."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time

CHECKS = {
    "SERVICES": ("Servicios", "Hay servicios fallidos.", "Solicite revisión al administrador."),
    "NETWORK": ("Red local", "No hay enlace de red activo.", "Revise el cable o la conexión Wi-Fi."),
    "ROUTE": ("Conectividad", "No hay ruta por defecto; el uso local puede continuar.", "Revise la red si necesita servicios externos."),
    "DNS": ("Resolución DNS", "No se pudo resolver el nombre configurado.", "Solicite revisar DNS; el arranque local continúa."),
    "DISK": ("Almacenamiento", "Queda poco espacio en el sistema.", "Solicite liberar espacio sin borrar datos operativos."),
    "READONLY": ("Almacenamiento", "La raíz está montada en modo de solo lectura.", "Solicite mantenimiento; no ejecute fsck sobre volúmenes montados."),
    "PERMISSIONS": ("Integridad de configuración", "Falta una ruta esencial o tiene permisos inseguros.", "Solicite restaurar los permisos desde la consola administrativa."),
    "MEMORY": ("Memoria", "Hay poca memoria disponible.", "Cierre tareas no esenciales y solicite revisión."),
    "PRESSURE": ("Memoria", "El kernel informa presión de memoria sostenida.", "Solicite revisar procesos y capacidad de la VM."),
    "LOAD": ("Procesador", "La carga sostenida supera la capacidad estimada.", "Solicite revisar las tareas en ejecución."),
    "LOGS": ("Registros", "Los registros ocupan más de 256 MiB.", "Solicite revisar la rotación y el origen del crecimiento."),
    "KERNEL": ("Kernel y dispositivos", "El kernel registró errores en este arranque.", "Solicite diagnóstico privado; este indicador no identifica todos los fallos físicos."),
    "FIREWALL": ("Firewall", "No se pudo confirmar la política de bloqueo entrante.", "Utilice la consola local y solicite revisar nftables."),
    "UPDATES": ("Actualizaciones", "La información de actualizaciones está desactualizada.", "Programe una ventana de mantenimiento con conexión a los repositorios oficiales."),
    "PACKAGES": ("Actualizaciones", "Hay paquetes con actualizaciones disponibles.", "El administrador debe revisar e instalar durante mantenimiento."),
    "REBOOT": ("Actualizaciones", "Hay un reinicio pendiente.", "Programe el reinicio al terminar el uso del equipo."),
    "CERTIFICATES": ("Certificados", "Un certificado configurado está vencido o vence en siete días.", "Solicite renovarlo y verificar su servicio."),
    "SMART": ("Disco", "El disco anuncia una falla.", "Copia los datos y cambia el disco cuanto antes; el kit de recuperación y la copia externa permiten pasar a otro equipo."),
    "TEMPERATURE": ("Temperatura", "El servidor está demasiado caliente.", "Revisa ventilación, polvo y que el equipo no esté encerrado."),
    "BACKUP": ("Respaldos", "No existe una copia verificada reciente o falló el último respaldo.", "Conecte el destino protegido y solicite revisar las copias."),
    "MAINTENANCE": ("Mantenimiento", "Un componente requiere revisión administrativa.", "Acceda con la cuenta administradora para consultar el registro."),
}
def run(argv, timeout=3):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return p.stdout if p.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None

def evaluate(e):
    """Evalúa evidencia; None significa desconocido, nunca saludable."""
    result = []
    def add(code, value, bad=False, severity="aviso", detail=None):
        part, problem, action = CHECKS[code]
        state = "desconocido" if value is None else severity if bad else "correcto"
        result.append({"id": "COS-" + code, "parte": part, "gravedad": state,
                       "mensaje": detail or ("No se pudo comprobar este indicador." if value is None else problem if bad else "Comprobación realizada sin avisos."),
                       "accion": action if bad or value is None else "No requiere acción por este indicador."})
    def optional(code, detail):
        result.append({"id":"COS-"+code, "parte":CHECKS[code][0], "gravedad":"no_aplica",
                       "mensaje":detail, "accion":"Configure este indicador si lo necesita."})
    n = e.get("failed_services")
    add("SERVICES", n, n is not None and n > 0)
    for code, key in (("NETWORK","network_up"), ("ROUTE","route")):
        v = e.get(key); add(code, v, v is False)
    if e.get("dns_configured"):
        add("DNS", e.get("dns"), e.get("dns") is False)
    else:
        optional("DNS", "No hay dependencia DNS declarada; internet no es requisito de arranque.")
    free = e.get("disk_free_ratio")
    add("DISK", free, free is not None and free < .15,
        "critico" if free is not None and free < .05 else "aviso")
    v = e.get("root_readonly"); add("READONLY", v, v is True, "critico")
    v = e.get("permissions"); add("PERMISSIONS", v, v is False, "critico")
    v = e.get("smart_passed")
    if v is None: optional("SMART", "Este equipo no informa el estado SMART de su disco.")
    else: add("SMART", v, v is False, "critico")
    v = e.get("temperature")
    if v is None: optional("TEMPERATURE", "Este equipo no informa su temperatura.")
    else: add("TEMPERATURE", v, v >= 85, "critico" if v >= 95 else "aviso")
    v = e.get("mem_available_ratio"); add("MEMORY", v, v is not None and v < .10)
    v = e.get("memory_pressure"); add("PRESSURE", v, v is not None and v > 10)
    v = e.get("load_per_cpu"); add("LOAD", v, v is not None and v > 2)
    v = e.get("journal_bytes"); add("LOGS", v, v is not None and v > 256*1024*1024)
    v = e.get("kernel_errors"); add("KERNEL", v, v is not None and v > 0)
    v = e.get("firewall"); add("FIREWALL", v, v is False, "critico")
    v = e.get("apt_age_hours"); add("UPDATES", v, v is not None and v > 168)
    v = e.get("upgradable"); add("PACKAGES", v, v is not None and v > 0)
    v = e.get("reboot"); add("REBOOT", v, v is True)
    if e.get("certificates_configured"):
        v = e.get("certificates"); add("CERTIFICATES", v, v is False)
    else:
        optional("CERTIFICATES", "No hay servicios TLS ni certificados declarados.")
    if e.get("backup_enabled"):
        age = e.get("backup_age_hours")
        failed = e.get("backup_failed", False)
        add("BACKUP", age, failed or age is None or age > e.get("backup_max_age_hours",48),
            detail=CHECKS["BACKUP"][1] if age is None or failed else None)
    else:
        optional("BACKUP", "Respaldo externo todavía no configurado; no hay protección por copias confirmada.")
    v = e.get("maintenance"); add("MAINTENANCE", v, v is True)
    return result

def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default

def disk_health():
    """False si algún disco anuncia una falla; None si ninguno informa, como en una VM."""
    raw = run(["lsblk","-dnpo","NAME,TYPE"])
    if raw is None:
        return None
    result = None
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) != 2 or parts[1] != "disk":
            continue
        try:
            # smartctl sale con error justo cuando el disco falla: el estado se lee del JSON, no del código.
            p = subprocess.run(["smartctl","-H","-j",parts[0]],capture_output=True,text=True,timeout=10,check=False)
            passed = json.loads(p.stdout).get("smart_status",{}).get("passed")
        except (OSError, ValueError, subprocess.TimeoutExpired):
            continue
        if passed is False:
            return False
        if passed is True:
            result = True
    return result

def temperature():
    """Grados de la lectura más alta del equipo, o None si no informa ninguna."""
    values = []
    for path in (*Path("/sys/class/hwmon").glob("hwmon*/temp*_input"), *Path("/sys/class/thermal").glob("thermal_zone*/temp")):
        try:
            values.append(int(path.read_text().strip())/1000)
        except (OSError, ValueError):
            pass
    return max(values) if values else None

def collect():
    e = {}
    e["smart_passed"] = disk_health()
    e["temperature"] = temperature()
    cfg = read_json("/etc/culinaryos/health.json", {})
    failed = run(["systemctl","--failed","--no-legend","--plain","--no-pager"])
    e["failed_services"] = len(failed.strip().splitlines()) if failed is not None else None
    for key,args in (("links",["ip","-j","link","show"]), ("routes4",["ip","-j","-4","route","show","default"]),
                     ("routes6",["ip","-j","-6","route","show","default"])):
        raw = run(args)
        try:
            e[key] = json.loads(raw) if raw is not None else None
        except ValueError:
            e[key] = None
    links = e.pop("links")
    e["network_up"] = any("LOWER_UP" in x.get("flags",[]) and x.get("ifname") != "lo" for x in links) if links is not None else None
    r4,r6=e.pop("routes4"),e.pop("routes6")
    e["route"] = bool(r4 or r6) if r4 is not None and r6 is not None else None
    # Resolver en proceso separado con timeout: nunca bloquear el diagnóstico ni el arranque.
    host = cfg.get("dns_host","")
    e["dns_configured"] = bool(host)
    if host:
        e["dns"] = run(["getent","ahosts",host]) is not None
    disk = shutil.disk_usage("/")
    e["disk_free_ratio"] = disk.free / disk.total
    # Leer el namespace de PID 1 evita confundir ProtectSystem=strict con raíz física RO.
    try:
        mounts = Path("/proc/1/mounts").read_text().splitlines()
        root = next(x.split()[3] for x in mounts if x.split()[1] == "/")
        e["root_readonly"] = "ro" in root.split(",")
    except (OSError, StopIteration, IndexError):
        e["root_readonly"] = None
    try:
        paths = [Path("/etc/nftables.conf"), Path("/usr/local/sbin/culinaryos-firstboot"), Path("/var/lib/culinaryos"), Path("/etc/culinaryos/health.json"), Path("/etc/culinaryos/backup.json")]
        e["permissions"] = all(p.stat().st_uid == 0 and not p.stat().st_mode & 0o022 for p in paths)
        e["permissions"] = e["permissions"] and all(not Path(p).stat().st_mode & 0o077 for p in ("/var/lib/culinaryos","/etc/culinaryos/backup.json"))
    except OSError:
        e["permissions"] = False
    try:
        mem = dict((x.split(":")[0],int(x.split()[1])) for x in Path("/proc/meminfo").read_text().splitlines())
        e["mem_available_ratio"] = mem["MemAvailable"] / mem["MemTotal"]
    except (OSError, ValueError, KeyError):
        e["mem_available_ratio"] = None
    try:
        psi = Path("/proc/pressure/memory").read_text().splitlines()[0].split()
        e["memory_pressure"] = float(dict(x.split("=") for x in psi[1:])["avg10"])
    except (OSError, ValueError, KeyError, IndexError):
        e["memory_pressure"] = None
    e["load_per_cpu"] = os.getloadavg()[1] / (os.cpu_count() or 1)
    raw = run(["du","-sb","/var/log"])
    e["journal_bytes"] = int(raw.split()[0]) if raw else None
    raw = run(["journalctl","-b","-k","-p","err","-n","100","--no-pager","--quiet"])
    e["kernel_errors"] = len(raw.strip().splitlines()) if raw is not None else None
    raw = run(["nft","-j","list","table","inet","culinaryos"])
    try:
        table=json.loads(raw)["nftables"]
        e["firewall"] = all(any(x.get("chain",{}).get("name")==name and x["chain"].get("policy")=="drop" for x in table) for name in ("input","forward"))
    except (TypeError, ValueError, KeyError):
        e["firewall"] = False
    lists = list(Path("/var/lib/apt/lists").glob("*InRelease"))
    e["apt_age_hours"] = (time.time()-min(p.stat().st_mtime for p in lists))/3600 if lists else None
    raw = run(["apt","list","--upgradable"])
    e["upgradable"] = max(0,len(raw.strip().splitlines())-1) if raw is not None else None
    e["reboot"] = Path("/var/run/reboot-required").exists()
    certs = cfg.get("certificates",[])
    e["certificates_configured"] = bool(certs)
    if certs:
        e["certificates"] = all(run(["openssl","x509","-checkend","604800","-noout","-in",p]) is not None for p in certs)
    backup=read_json("/etc/culinaryos/backup.json",{})
    e["backup_enabled"]=backup.get("enabled",False)
    status=read_json("/var/lib/culinaryos/backup-status.json",{})
    e["backup_age_hours"] = (time.time()-status["verified_at"])/3600 if isinstance(status.get("verified_at"),(int,float)) else None
    e["backup_failed"]=status.get("ok") is not True
    e["backup_max_age_hours"]=cfg.get("backup_max_age_hours",48)
    e["maintenance"]=Path("/run/culinaryos-maintenance-required").exists()
    return e

def main():
    start=time.monotonic()
    checks=evaluate(collect())
    import lan
    checks.extend(lan.from_file())
    import runtimehealth
    checks.extend(runtimehealth.checks())
    status={"system":"CulinaryOs","version":"0.2.0-dev","generated_at":time.time(),
            "diagnostic_seconds":round(time.monotonic()-start,3),
            "live": "boot=live" in Path("/proc/cmdline").read_text().split(),
            "checks":checks}
    directory=Path("/run/culinaryos")
    directory.mkdir(mode=0o755,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",dir=directory,delete=False) as f:
        json.dump(status,f,ensure_ascii=False,indent=2)
        f.flush(); os.fsync(f.fileno())
        temp=f.name
    os.chmod(temp,0o644)
    os.replace(temp,directory/"status.json")
    return 2 if any(c["gravedad"]=="critico" for c in checks) else 0
if __name__=="__main__":
    raise SystemExit(main())
