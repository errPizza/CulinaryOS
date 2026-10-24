"""Estado público del runtime: nunca incluye cargas, claves o URL del central."""
import json
from pathlib import Path
import subprocess
import time

def row(code,part,state,message,action):
    return {"id":"COS-"+code,"parte":part,"gravedad":state,"mensaje":message,"accion":action}
def run(args):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=3,check=False)
        return p.stdout.strip() if p.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired):return None

def checks():
    values=[]
    branch=Path("/etc/culinaryos/branch.json")
    if branch.exists():
        try:
            cfg=json.loads(branch.read_text())
            from dataio import Client
            status=Client().call("health")
            if status.get("ready") is not True:raise ValueError()
            values.append(row("DATA","Almacén de sucursal","correcto","El almacén local respondió y comprobó su estructura.","No implica disponibilidad de la aplicación."))
            pending=status["pending"]
            if not cfg.get("central"):
                values.append(row("SYNC","Servidor principal","aviso","Central sin configurar; los eventos permanecen en almacenamiento local.","El administrador debe aprovisionar URL y credenciales mTLS."))
            elif pending:
                values.append(row("SYNC","Sincronización","aviso",f"Hay {pending} eventos persistidos pendientes de confirmar por el central.","Revise salida a internet, disponibilidad del central y certificados; no borre la cola."))
            else:
                values.append(row("SYNC","Sincronización","correcto","No hay eventos pendientes en la cola local.","No prueba conectividad actual con el central."))
        except Exception:
            values.append(row("DATA","Almacén de sucursal","critico","No se pudo comprobar el almacén local.","Solicite revisión de servicio, claves, espacio y persistencia antes de confirmar operaciones."))
    else:
        values.append(row("DATA","Almacén de sucursal","no_aplica","El equipo no tiene un almacén de sucursal aprovisionado.","Aplicación y almacenamiento operativo pendientes de alta."))
    manifest=Path("/etc/culinaryos/application.json")
    if manifest.exists() and Path("/etc/culinaryos/application.server").exists():
        active=run(["systemctl","is-active","culinaryos-backend.service"])
        values.append(row("APP","Aplicación registrada","correcto" if active=="active" else "critico",
                          "El backend registrado completó su readiness." if active=="active" else "El backend registrado no está disponible.",
                          "Consulte el servicio administrativo; no confunda esto con una caída de internet."))
    mode=Path("/etc/nut/nut.conf")
    if mode.exists() and "MODE=standalone" in mode.read_text():
        state=run(["upsc","culinaryos@localhost","ups.status"])
        if state is None:
            values.append(row("UPS","Energía","aviso","No se pudo leer el UPS configurado.","Revise USB, controlador y servicios NUT; no hay batería confirmada."))
        else:
            flags=state.split()
            severity="critico" if "LB" in flags or "FSD" in flags else "aviso" if "OB" in flags else "correcto" if "OL" in flags else "desconocido"
            monitor=run(["systemctl","is-active","nut-monitor.service"])
            if monitor!="active":
                severity="critico" if "LB" in flags or "FSD" in flags else "aviso"
                message="UPS responde, pero el monitor de apagado automático no está activo."
            else:
                message="UPS con alimentación eléctrica." if "OL" in flags else "UPS funcionando con batería; puede requerir apagado ordenado."
            values.append(row("UPS","Energía",severity,message,"Cierre el uso si se anuncia batería crítica y revise la autonomía real."))
    else:
        values.append(row("UPS","Energía","no_aplica","No hay un UPS verificado y habilitado.","La preparación de NUT no garantiza protección física ante apagones."))
    return values
