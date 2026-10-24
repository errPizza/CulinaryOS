#!/usr/bin/python3
"""Panel local sin servidor web, privilegios ni datos simulados."""
import json
from pathlib import Path
import subprocess
import time
import tkinter as tk
from tkinter import messagebox
root=tk.Tk()
root.title("CulinaryOs")
root.geometry("980x700")
root.configure(bg="#10252d")
header=tk.Frame(root,bg="#ffffff")
header.pack(fill="x",pady=(0,12))
try:
    original_logo=tk.PhotoImage(file="/usr/share/culinaryos/branding/logo.png")
    root.iconphoto(True,original_logo)
    divisor=max(1,(max(original_logo.width(),original_logo.height())+209)//210)
    root.logo=original_logo.subsample(divisor,divisor)
    tk.Label(header,image=root.logo,bg="#ffffff").pack(pady=0)
except (OSError,tk.TclError):
    tk.Label(header,text="CulinaryOS",font=("DejaVu Sans",30,"bold"),
             fg="#202730",bg="#ffffff").pack(pady=20)
message="CulinaryOs preparado. Aplicación pendiente de integración"
if Path("/etc/culinaryos/application.json").exists():
    message="CulinaryOs. No se pudo iniciar la aplicación registrada; consulte el diagnóstico."
tk.Label(root,text=message,font=("DejaVu Sans",14),
         fg="#eef6ed",bg="#10252d",wraplength=900).pack()
banner=tk.Label(root,text="",fg="#ffdca8",bg="#10252d",font=("DejaVu Sans",12))
banner.pack(pady=12)
body=tk.Text(root,wrap="word",font=("DejaVu Sans",11),bg="#f4f6f1",fg="#162c30",padx=18,pady=12)
body.pack(fill="both",expand=True,padx=24)
def refresh():
    try:
        status=json.loads(Path("/run/culinaryos/status.json").read_text(encoding="utf-8"))
        age=time.time()-status["generated_at"]
        banner.config(text=("SESIÓN LIVE: cambios temporales; se pierden al reiniciar. " if status.get("live") else "Sistema instalado. ")+
                      ("Diagnóstico vencido; solicite revisión." if age>300 or age<0 else "Última comprobación: "+time.strftime("%H:%M:%S",time.localtime(status["generated_at"]))))
        lines=[]
        for c in status["checks"]:
            lines.append(f'{c["id"]} · {c["gravedad"].upper()} · {c["parte"]}\n{c["mensaje"]}\n{c["accion"]}\n')
        text="\n".join(lines)
    except (OSError,ValueError,KeyError,TypeError):
        banner.config(text="Estado sin comprobar")
        text="COS-STATUS · DESCONOCIDO\nNo está disponible el diagnóstico del equipo. Solicite revisión administrativa."
    body.config(state="normal"); body.delete("1.0","end"); body.insert("end",text); body.config(state="disabled")
    root.after(10000,refresh)
def maintenance():
    messagebox.showinfo("Mantenimiento protegido","Cambie a una sesión de la cuenta administradora o a Ctrl+Alt+F2.\nEjecute: sudo culinaryos-maintenance\nLa cuenta operativa no tiene permiso sudo.")
def power(action):
    if messagebox.askyesno("CulinaryOs","¿Reiniciar ordenadamente?" if action=="reboot" else "¿Apagar ordenadamente?"):
        # logind/polkit mantienen la autorización del sistema; no hay sudo sin contraseña.
        p=subprocess.run(["systemctl",action],capture_output=True,timeout=15)
        if p.returncode:
            messagebox.showerror("CulinaryOs","COS-POWER: operación no autorizada o no disponible. Solicite al administrador.")
buttons=tk.Frame(root,bg="#10252d")
buttons.pack(pady=15)
for label,action in [("Mantenimiento",maintenance),("Reiniciar",lambda:power("reboot")),("Apagar",lambda:power("poweroff"))]:
    tk.Button(buttons,text=label,command=action,padx=15,pady=8).pack(side="left",padx=8)
refresh()
root.mainloop()
