#!/bin/bash
# Restaurar sólo los archivos de arranque guardados por este paquete.
set -Eeuo pipefail
[[ $(uname -s) == Linux && $EUID -eq 0 ]] || exit 2
work=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
[[ $work == /var/backups/culinaryos/boot-* && -f $work/before.tar && -f $work/absent.txt ]] || exit 2
# Lista creada por root en un directorio 0700, antes de modificar el arranque.
while IFS= read -r relative; do
    case "$relative" in
        usr/local/lib/culinaryos/bootconfig.py|etc/systemd/system/getty@tty1.service.d/20-culinaryos-graphical.conf|etc/default/grub.d/60-culinaryos-splash.cfg|etc/plymouth/plymouthd.conf|usr/share/plymouth/themes/culinaryos/culinaryos.script|usr/share/plymouth/themes/culinaryos/culinaryos.plymouth|usr/share/plymouth/themes/culinaryos/dot.png|usr/share/plymouth/themes/culinaryos/logo.png) rm -f -- "/$relative" ;;
        *) echo 'Lista de restauración inesperada; revisar manualmente.'; exit 2 ;;
    esac
done < "$work/absent.txt"
tar -C / -xpf "$work/before.tar"
if [[ -f $work/disable-tty2-after-restore ]]; then
    systemctl disable getty@tty2.service
fi
systemctl daemon-reload
echo 'Archivos anteriores de GRUB, Plymouth e initramfs restaurados.'
echo 'No se reinicia automáticamente.'
