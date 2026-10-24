#!/bin/bash
# Sólo VM Debian 13 desechable. Sin particionado ni discos físicos.
set -Eeuo pipefail
umask 077
export PYTHONDONTWRITEBYTECODE=1
project=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
profile=${1:-}
case "$profile" in terminal|servidor|sucursal) ;; *) echo 'Uso: sudo bash scripts/install-lab.sh terminal|servidor|sucursal'; exit 2 ;; esac
[[ $(uname -s) == Linux && $EUID -eq 0 ]] || { echo 'Sólo root en una VM Linux de laboratorio.'; exit 2; }
# shellcheck source=/dev/null
. /etc/os-release
[[ ${ID:-} == debian && ${VERSION_CODENAME:-} == trixie ]] || { echo 'Se requiere Debian 13 trixie.'; exit 2; }
[[ $(dpkg --print-architecture) == amd64 ]] || exit 2
if systemd-detect-virt --container --quiet; then echo 'No instalar dentro de contenedor.'; exit 2; fi
[[ $(findmnt -n -o FSTYPE /) != overlay ]] || { echo 'Requiere Debian instalado, no Live/overlay.'; exit 2; }
systemd-detect-virt --vm --quiet || { echo 'Se exige una VM; no instalar sobre hardware anfitrión.'; exit 2; }
[[ -t 0 && -t 1 && -z ${SSH_CONNECTION:-} ]] || { echo 'Usar consola local de la VM, no SSH.'; exit 2; }
[[ ! -e /etc/culinaryos/profile ]] || { echo 'Ya existe CulinaryOs; no es un actualizador.'; exit 2; }
if systemctl is-active --quiet nut-monitor.service; then
    echo 'Hay monitor UPS activo; no reemplazar configuración.'; exit 2
fi
echo "CulinaryOs 0.2.0-dev — perfil $profile"
echo 'Se instalarán paquetes y archivos del overlay, servicios, identidad y arranque del invitado.'
echo 'No hay aplicación. Use sólo una VM desechable con snapshot.'
find "$project/os/overlay" -type f -printf '%P\n'
read -r -p 'Escriba INSTALAR-EN-VM: ' confirm
[[ $confirm == INSTALAR-EN-VM ]] || exit 2
mapfile -t packages < <(sed '/^[[:space:]]*#/d; /^[[:space:]]*$/d' "$project/config/packages/base.list" "$project/config/packages/$profile.list")
for package in "${packages[@]}"; do [[ $package =~ ^[a-z0-9][a-z0-9+.-]+$ ]] || exit 2; done
apt-get update
apt-get install --no-install-recommends "${packages[@]}"
bash "$project/scripts/verify-linux.sh"
backup="/var/backups/culinaryos-preinstall-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 0700 "$backup"
list="$backup/existing-files.txt"
: > "$list"
while IFS= read -r -d '' source; do
    relative=${source#"$project/os/overlay/"}
    target="/$relative"
    [[ ! -L $target ]] || { echo "Revisar enlace en destino: $target"; exit 2; }
    if [[ -e $target ]]; then printf '%s\n' "$relative" >> "$list"; fi
done < <(find "$project/os/overlay" -type f -print0)
[[ ! -f /etc/grub.d/10_linux ]] || printf '%s\n' etc/grub.d/10_linux >> "$list"
printf '%s\n' usr/lib/os-release etc/default/keyboard etc/locale.gen etc/issue etc/issue.net >> "$list"
tar -C / -czf "$backup/config-before.tar.gz" -T "$list"
while IFS= read -r -d '' source; do
    relative=${source#"$project/os/overlay/"}
    mode=0644
    case "$relative" in usr/local/*) mode=0755 ;; esac
    install -D -o root -g root -m "$mode" "$source" "/$relative"
done < <(find "$project/os/overlay" -type f -print0)
install -d -m 0755 /etc/culinaryos /usr/share/culinaryos/examples
printf '%s\n' "$profile" > /etc/culinaryos/profile
chmod 0644 /etc/culinaryos/profile
install -m 0644 "$project/config/project.json" /etc/culinaryos/build.json
install -m 0644 "$project/config/network/site-plan.json" /usr/share/culinaryos/examples/site-plan.json
# Exclusivamente dentro de la VM comprobada; no ejecutar este hook sobre otro equipo.
sh "$project/os/hooks/0100-culinaryos.hook.chroot"
systemctl daemon-reload
echo "Configuración anterior: $backup"
echo 'Preparado. No se reiniciará automáticamente.'
echo 'Reinicie la VM, complete cuentas propias y consulte docs/RUNTIME-SUCURSAL.md.'
