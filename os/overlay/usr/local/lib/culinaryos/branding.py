#!/usr/bin/python3
"""Fondo de primera sesión XFCE; sin privilegios, red ni cambio de fondos propios."""
import os
from pathlib import Path
import re
import subprocess
import time

WALLPAPER = "/usr/share/culinaryos/branding/desktop.svg"
DEFAULTS = ("/usr/share/backgrounds/xfce/", "/usr/share/images/desktop-base/", "/usr/share/desktop-base/")

def query(*args):
    return subprocess.run(["xfconf-query", "-c", "xfce4-desktop", *args],
                          capture_output=True, text=True, timeout=2, check=False)

def main():
    config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    marker = config / "culinaryos/branding-v1"
    if marker.exists() or not Path(WALLPAPER).is_file():
        return
    try:
        # XFDesktop crea propiedades con el nombre real del monitor al iniciar.
        for attempt in range(10):
            listing = query("-l")
            props = [p for p in listing.stdout.splitlines() if re.fullmatch(
                r"/backdrop/screen[0-9]+/monitor[^/]+/workspace-?[0-9]+/last-image", p)]
            if props:
                break
            time.sleep(0.5)
        if not props:
            return  # Un fallo de sesión nunca impide que arranque la aplicación.
        successful = True
        for prop in props:
            current = query("-p", prop)
            if current.returncode:
                successful = False
                continue
            value = current.stdout.strip()
            if value and value != WALLPAPER and not value.startswith(DEFAULTS):
                continue  # Conservar preferencias previas del usuario.
            if query("-p", prop, "-s", WALLPAPER).returncode:
                successful = False
                continue
            style = prop.rsplit("/", 1)[0] + "/image-style"
            if query("-p", style, "--create", "-t", "int", "-s", "4").returncode:
                successful = False
        if successful:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("1\n", encoding="ascii")
    except (OSError, subprocess.TimeoutExpired):
        return

if __name__ == "__main__":
    main()
