#!/bin/bash
# Actualización de la pantalla de arranque, sólo para el invitado de laboratorio.
set -Eeuo pipefail
umask 077
[[ $(uname -s) == Linux && $EUID -eq 0 ]] || { echo 'Sólo root dentro de la VM Debian.'; exit 2; }
[[ -t 0 && -t 1 && -z ${SSH_CONNECTION:-} ]] || { echo 'Ejecutar en una terminal local de la VM.'; exit 2; }
# shellcheck source=/dev/null
. /etc/os-release
[[ ${ID:-} == debian && ${VERSION_CODENAME:-} == trixie ]] || exit 2
systemd-detect-virt --vm --quiet || { echo 'Se requiere una VM de laboratorio.'; exit 2; }
[[ -f /etc/culinaryos/profile && -f /boot/grub/grub.cfg ]] || { echo 'Se requiere CulinaryOS instalado con GRUB.'; exit 2; }
for tool in plymouth-set-default-theme update-initramfs update-grub grub-script-check lsinitramfs; do
    command -v "$tool" >/dev/null || { echo "Falta $tool; no se cambió el arranque."; exit 2; }
done
media=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
(cd "$media" && sha256sum -c SHA256SUMS)
for name in culinaryos.script culinaryos.plymouth dot.png logo.png 60-culinaryos-splash.cfg restaurar-arranque.sh bootconfig.py 20-culinaryos-graphical.conf; do
    [[ -f $media/$name && ! -L $media/$name ]] || exit 2
done
bash -n "$media/restaurar-arranque.sh"
sh -n "$media/60-culinaryos-splash.cfg"
grub-script-check /boot/grub/grub.cfg
python3 "$media/bootconfig.py" check-generator
profile=$(cat /etc/culinaryos/profile)
case "$profile" in terminal|sucursal|servidor) ;; *) exit 2 ;; esac
if [[ $profile != servidor ]]; then
    tty2_state=$(systemctl is-enabled getty@tty2.service 2>/dev/null || true)
    [[ $tty2_state != masked* ]] || { echo 'Desenmascarar tty2 requiere revisión administrativa.'; exit 2; }
fi
work="/var/backups/culinaryos/boot-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 0700 "$work"
theme=/usr/share/plymouth/themes/culinaryos
targets=(etc/default/grub.d/60-culinaryos-splash.cfg etc/plymouth/plymouthd.conf boot/grub/grub.cfg etc/grub.d/10_linux usr/local/lib/culinaryos/bootconfig.py)
if [[ $profile != servidor ]]; then
    targets+=(etc/systemd/system/getty@tty1.service.d/20-culinaryos-graphical.conf)
    case "$tty2_state" in enabled*) ;; *) touch "$work/disable-tty2-after-restore" ;; esac
fi
for name in culinaryos.script culinaryos.plymouth dot.png logo.png; do
    targets+=("usr/share/plymouth/themes/culinaryos/$name")
done
kernels=0
for initrd in /boot/initrd.img-*; do
    [[ -f $initrd && ! -L $initrd ]] || continue
    targets+=("${initrd#/}")
    kernels=$((kernels+1))
done
(( kernels > 0 )) || { echo 'No se encontraron initramfs para respaldar.'; exit 2; }
: > "$work/existing.txt"
: > "$work/absent.txt"
for relative in "${targets[@]}"; do
    [[ ! -L /$relative ]] || { echo "Revisar enlace: /$relative"; exit 2; }
    if [[ -f /$relative ]]; then
        printf '%s\n' "$relative" >> "$work/existing.txt"
    elif [[ ! -e /$relative ]]; then
        printf '%s\n' "$relative" >> "$work/absent.txt"
    else
        echo "Destino inesperado: /$relative"; exit 2
    fi
done
tar -C / -cpf "$work/before.tar" -T "$work/existing.txt"
tar -tf "$work/before.tar" >/dev/null
install -m 0700 "$media/restaurar-arranque.sh" "$work/restaurar-arranque.sh"
echo "Copia anterior: $work"
# Si falla la regeneración, recuperar los archivos exactos anteriores.
rollback() {
    local rc=$?
    trap - ERR
    echo 'Falló la actualización; restaurando el arranque anterior.'
    if ! bash "$work/restaurar-arranque.sh"; then
        echo "Revisar restauración manual: $work/restaurar-arranque.sh"
    fi
    exit "$rc"
}
trap rollback ERR
install -d -m 0755 "$theme" /etc/default/grub.d
for name in culinaryos.script culinaryos.plymouth dot.png logo.png; do
    install -o root -g root -m 0644 "$media/$name" "$theme/$name"
done
install -o root -g root -m 0644 "$media/60-culinaryos-splash.cfg" /etc/default/grub.d/60-culinaryos-splash.cfg
install -o root -g root -m 0644 "$media/bootconfig.py" /usr/local/lib/culinaryos/bootconfig.py
python3 /usr/local/lib/culinaryos/bootconfig.py quiet-generator
if [[ $profile != servidor ]]; then
    install -D -o root -g root -m 0644 "$media/20-culinaryos-graphical.conf" /etc/systemd/system/getty@tty1.service.d/20-culinaryos-graphical.conf
    systemctl enable getty@tty2.service
fi
plymouth-set-default-theme culinaryos
update-initramfs -u -k all
update-grub
grub-script-check /boot/grub/grub.cfg
# Confirmar que el tema viaja en cada imagen de arranque regenerada.
for initrd in /boot/initrd.img-*; do
    [[ -f $initrd && ! -L $initrd ]] || continue
    lsinitramfs "$initrd" > "$work/initramfs-files.txt"
    for name in culinaryos.script culinaryos.plymouth logo.png dot.png; do
        grep -Fqx "usr/share/plymouth/themes/culinaryos/$name" "$work/initramfs-files.txt"
    done
done
systemctl daemon-reload
trap - ERR
echo 'Pantalla preparada: logo, puntos animados y Esc para ver los mensajes.'
echo 'Menú GRUB oculto en el arranque normal: Esc/F4 permite abrirlo durante el primer segundo.'
echo 'La consola administrativa sigue en F2 (Ctrl+Alt+F2; en VirtualBox, Ctrl derecho+F2).'
echo 'Se conservan registros, recuperación y avisos críticos; puede haber una transición negra breve.'
echo 'El indicador representa actividad; no calcula un porcentaje ni retrasa el inicio.'
echo "Restauración si hiciera falta: sudo bash $work/restaurar-arranque.sh"
echo 'Reinicie cuando termine de revisar la salida: sudo reboot'
