#!/bin/bash
# Build the integrated installable image in a dedicated Debian 13 amd64 builder.
set -Eeuo pipefail
umask 022
export PYTHONDONTWRITEBYTECODE=1
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
application=${1:?Ruta al paquete fuente/binarios de la aplicacion}
cache_source=${2:-}
[[ $(uname -s) == Linux && $EUID -eq 0 ]] || exit 2
# shellcheck source=/dev/null
. /etc/os-release
[[ ${ID:-} == debian && ${VERSION_CODENAME:-} == trixie && $(dpkg --print-architecture) == amd64 ]] || exit 2
[[ -f $application/payload/client/culinary-restaurant && -f $application/payload/backend/MesaNexo.Api ]] || exit 2
python3 "$project/tests/test_project.py"
python3 "$project/tests/test_appliance.py"
python3 "$project/tests/test_recovery.py"
for tool in lb debootstrap xorriso mksquashfs openssl; do command -v "$tool" >/dev/null; done
command -v rsvg-convert >/dev/null || { echo 'Falta rsvg-convert; instala librsvg2-bin en el constructor.' >&2; exit 2; }
work="$project/build/appliance-$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$work" "$project/dist"
# A previous isolated build can supply Debian package caches, never its root/state.
if [[ -n $cache_source ]]; then
  cache_source=$(realpath -- "$cache_source")
  [[ -f $cache_source/cache/bootstrap/etc/debian_version ]]
  [[ ! -e $cache_source/cache/bootstrap/etc/culinaryos/site.json ]]
  mkdir "$work/cache"
  for entry in bootstrap packages.bootstrap packages.chroot installer_debian-installer; do
    if [[ -d $cache_source/cache/$entry ]]; then cp -a "$cache_source/cache/$entry" "$work/cache/$entry"; fi
  done
fi
cd "$work"
exec > >(tee "$work/build.log") 2>&1
lb config --ignore-system-defaults --mode debian --distribution trixie \
  --cache-stages 'bootstrap chroot' --chroot-squashfs-compression-type gzip --architecture amd64 --binary-image iso-hybrid --bootloaders 'syslinux grub-efi' \
  --archive-areas 'main non-free-firmware' --apt-secure true --apt-recommends false \
  --security true --updates true --backports false --uefi-secure-boot enable \
  --mirror-bootstrap https://deb.debian.org/debian --mirror-chroot https://deb.debian.org/debian \
  --mirror-binary https://deb.debian.org/debian \
  --mirror-chroot-security https://security.debian.org/debian-security \
  --mirror-binary-security https://security.debian.org/debian-security \
  --debian-installer live --debian-installer-gui true --debian-installer-distribution trixie \
  --debian-installer-preseedfile preseed.cfg \
  --firmware-chroot true --firmware-binary true --checksums sha256 \
  --iso-application CulinaryOS --iso-publisher CulinaryOS \
  --iso-volume CULINARY_INSTALL --image-name culinaryos-restaurant \
  --bootappend-install 'locale=es_MX.UTF-8 keymap=latam quiet splash loglevel=3 systemd.show_status=error' \
  --bootappend-live 'boot=live components live-config.nocomponents=user-setup,sudo,polkit,lightdm live-config.noautologin locales=es_MX.UTF-8 keyboard-layouts=latam timezone=America/Mexico_City hostname=culinaryos quiet splash'
mkdir -p config/package-lists config/includes.chroot config/hooks/live
mkdir -p config/bootloaders config/preseed
read -r -s -p 'Contraseña inicial de devmode: ' dev_password
printf '\n'
read -r -s -p 'Confirma la contraseña: ' dev_password_confirm
printf '\n'
[[ -n $dev_password && $dev_password == "$dev_password_confirm" ]] || { echo 'La contraseña no coincide o está vacía.' >&2; exit 2; }
dev_password_hash=$(printf '%s' "$dev_password" | openssl passwd -6 -stdin)
unset dev_password dev_password_confirm
sed "s|@DEVMODE_PASSWORD_HASH@|$dev_password_hash|" "$project/config/appliance-preseed.cfg" > config/preseed/culinaryos.cfg
unset dev_password_hash
cp -a "$project/config/appliance-bootloaders/." config/bootloaders/
mkdir -p config/includes.installer/usr/share/graphics
python3 - "$project/config/installer-branding/banner.svg" "$project/os/overlay/usr/share/culinaryos/branding/logo.png" <<'PYCODE' > config/includes.installer/usr/share/graphics/logo_installer.png
from pathlib import Path
import base64,subprocess,sys
svg=Path(sys.argv[1]).read_text(encoding='utf-8').replace('LOGO_DATA_URI','data:image/png;base64,'+base64.b64encode(Path(sys.argv[2]).read_bytes()).decode('ascii'))
subprocess.run(['rsvg-convert','--width=800','--height=75'],input=svg.encode('utf-8'),stdout=sys.stdout.buffer,check=True)
PYCODE
cp config/includes.installer/usr/share/graphics/logo_installer.png config/includes.installer/usr/share/graphics/logo_installer_dark.png
python3 - "$project/config/installer-branding/boot.svg" "$project/os/overlay/usr/share/culinaryos/branding/logo.png" <<'PYCODE' > config/bootloaders/grub-pc/culinaryos-installer.png
from pathlib import Path
import base64,subprocess,sys
svg=Path(sys.argv[1]).read_text(encoding='utf-8').replace('LOGO_DATA_URI','data:image/png;base64,'+base64.b64encode(Path(sys.argv[2]).read_bytes()).decode('ascii'))
subprocess.run(['rsvg-convert','--width=1024','--height=768'],input=svg.encode('utf-8'),stdout=sys.stdout.buffer,check=True)
PYCODE
mkdir -p config/bootloaders/grub-efi
cp config/bootloaders/grub-pc/culinaryos-installer.png config/bootloaders/grub-efi/culinaryos-installer.png
python3 - "$project/config/installer-branding/boot.svg" "$project/os/overlay/usr/share/culinaryos/branding/logo.png" <<'PYCODE' > config/bootloaders/syslinux_common/culinaryos-installer.png
from pathlib import Path
import base64,subprocess,sys
svg=Path(sys.argv[1]).read_text(encoding='utf-8').replace('LOGO_DATA_URI','data:image/png;base64,'+base64.b64encode(Path(sys.argv[2]).read_bytes()).decode('ascii'))
subprocess.run(['rsvg-convert','--width=640','--height=480'],input=svg.encode('utf-8'),stdout=sys.stdout.buffer,check=True)
PYCODE
cat "$project/config/packages/base.list" "$project/config/packages/sucursal.list" "$project/config/packages/appliance.list" > config/package-lists/culinaryos.list.chroot
cp -a "$project/os/overlay/." config/includes.chroot/
cp -a "$project/os/appliance/." config/includes.chroot/
mkdir -p config/includes.chroot/etc/culinaryos config/includes.chroot/opt/culinaryos-app
printf 'sucursal\n' > config/includes.chroot/etc/culinaryos/profile
cp "$project/config/appliance.json" config/includes.chroot/etc/culinaryos/build.json
cp -a "$application/payload/backend" config/includes.chroot/opt/culinaryos-app/backend
cp -a "$application/payload/client" config/includes.chroot/opt/culinaryos-app/client
cp -a "$application/deploy/culinaryos/kiosk" config/includes.chroot/opt/culinaryos-app/kiosk
cp "$application/deploy/culinaryos/CulinaryRestaurant" config/includes.chroot/opt/culinaryos-app/client/CulinaryRestaurant
cp "$application/deploy/culinaryos/hardware-identity.py" "$application/deploy/culinaryos/renew-tls.py" "$application/deploy/culinaryos/license-server.txt" config/includes.chroot/opt/culinaryos-app/
cp "$application/deploy/culinaryos/install.py" config/includes.chroot/usr/local/lib/culinaryos/appliance_install.py
mkdir -p config/includes.chroot/usr/local/lib/culinary-update config/includes.chroot/etc/systemd/system config/includes.chroot/usr/lib/tmpfiles.d
cp "$application/deploy/culinaryos/update/apply.py" config/includes.chroot/usr/local/lib/culinary-update/
cp "$application/deploy/culinaryos/update/culinary-update.path" "$application/deploy/culinaryos/update/culinary-update.service" config/includes.chroot/etc/systemd/system/
cp "$application/deploy/culinaryos/update/culinary-update.tmpfiles" config/includes.chroot/usr/lib/tmpfiles.d/culinary-update.conf
mkdir -p config/includes.chroot/usr/share/xsessions config/includes.chroot/usr/share/icons/hicolor/256x256/apps
cp "$application/deploy/culinaryos/kiosk/culinary-restaurant.desktop" config/includes.chroot/usr/share/xsessions/
cp "$application/branding/icon-256.png" config/includes.chroot/usr/share/icons/hicolor/256x256/apps/culinary-restaurant.png
cp "$project/os/hooks/0100-culinaryos.hook.chroot" config/hooks/live/
cp "$project/os/hooks/0200-appliance.hook.chroot" config/hooks/live/
chown -R root:root config/includes.chroot
find config/includes.chroot -type d -exec chmod 0755 {} +
find config/includes.chroot -type f -exec chmod 0644 {} +
find config/includes.chroot/usr/local -type f -exec chmod 0755 {} +
chmod 0755 config/includes.chroot/opt/culinaryos-app/backend/MesaNexo.Api
chmod 0755 config/includes.chroot/opt/culinaryos-app/client/{CulinaryRestaurant,culinary-restaurant,culinary-bridge}
chmod 0755 config/includes.chroot/opt/culinaryos-app/kiosk/session.sh config/hooks/live/*.hook.chroot
lb build
iso=$(find . -maxdepth 1 -name '*.hybrid.iso' -type f -print -quit)
[[ -n $iso ]] || { echo 'live-build no genero ISO'; exit 1; }
out="$project/dist/CulinaryOS-CulinaryRestaurant-amd64-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir "$out"
cp "$iso" "$out/CulinaryOS-CulinaryRestaurant-amd64.iso"
cp build.log "$out/"
cp chroot/usr/share/culinaryos/{packages.tsv,copyrights.tar.gz} "$out/"
cp "$project/config/appliance.json" "$out/"
(cd "$out" && sha256sum ./*.iso > SHA256SUMS)
printf 'ISO integrada generada: %s\n' "$out"
