#!/bin/bash
set -Eeuo pipefail
umask 022
export PYTHONDONTWRITEBYTECODE=1
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
profile=${1:-}
case "$profile" in terminal|servidor|sucursal) ;; *) echo 'Uso: sudo bash scripts/build.sh terminal|servidor|sucursal' >&2; exit 2 ;; esac
[[ $(uname -s) == Linux && $EUID -eq 0 ]] || { echo 'Requiere root en VM Linux Debian 13; no modifica Windows.' >&2; exit 2; }
# shellcheck source=/dev/null
. /etc/os-release
[[ ${ID:-} == debian && ${VERSION_CODENAME:-} == trixie ]] || { echo 'Construir solamente en Debian 13 trixie.' >&2; exit 2; }
[[ $(dpkg --print-architecture) == amd64 ]] || exit 2
for tool in lb debootstrap xorriso mksquashfs python3 sha256sum; do command -v "$tool" >/dev/null || { echo "Falta $tool" >&2; exit 2; }; done
python3 "$project/tests/test_project.py"
python3 "$project/tests/test_diagnostics.py"
python3 "$project/tests/test_backup.py"
python3 "$project/tests/test_network.py"
python3 "$project/tests/test_pki.py"
python3 "$project/tests/test_data.py"
python3 "$project/tests/test_runtime.py"
python3 "$project/tests/test_firstboot.py"
python3 "$project/tests/test_sync_tls.py"
# Directorio nuevo y exclusivo: nunca reutilizar un chroot ajeno ni borrar rutas.
stamp=$(date -u +%Y%m%dT%H%M%SZ)
work="$project/build/$profile-$stamp-$$"
mkdir -p "$work" "$project/dist"
cd "$work"
exec > >(tee "$work/build.log") 2>&1
dpkg-query -W live-build debootstrap xorriso squashfs-tools > build-tools.tsv
lb config --ignore-system-defaults --mode debian --distribution trixie \
  --architecture amd64 --binary-image iso-hybrid --bootloaders 'syslinux,grub-efi' \
  --archive-areas main --apt-secure true --apt-recommends false \
  --security true --updates true --backports false --uefi-secure-boot enable \
  --mirror-bootstrap https://deb.debian.org/debian \
  --mirror-chroot https://deb.debian.org/debian \
  --mirror-binary https://deb.debian.org/debian \
  --mirror-chroot-security https://security.debian.org/debian-security \
  --mirror-binary-security https://security.debian.org/debian-security \
  --debian-installer none --firmware-chroot false --firmware-binary false \
  --checksums sha256 --iso-application CulinaryOs --iso-publisher CulinaryOs \
  --iso-volume CULINARYOS_DEV --image-name "culinaryos-$profile" \
  --bootappend-live 'boot=live components live-config.nocomponents=user-setup,sudo,polkit,lightdm live-config.noautologin locales=es_MX.UTF-8 keyboard-layouts=latam timezone=America/Mexico_City hostname=culinaryos quiet splash loglevel=3 systemd.show_status=error'
mkdir -p config/package-lists config/includes.chroot config/hooks/live
cat "$project/config/packages/base.list" "$project/config/packages/$profile.list" > config/package-lists/culinaryos.list.chroot
# Lista positiva: únicamente overlay del SO. No se copia la carpeta de proyecto.
cp -a "$project/os/overlay/." config/includes.chroot/
mkdir -p config/includes.chroot/etc/culinaryos
printf '%s\n' "$profile" > config/includes.chroot/etc/culinaryos/profile
cp "$project/config/project.json" config/includes.chroot/etc/culinaryos/build.json
mkdir -p config/includes.chroot/usr/share/culinaryos/examples
cp "$project/config/network/site-plan.json" config/includes.chroot/usr/share/culinaryos/examples/site-plan.json
cp "$project/os/hooks/0100-culinaryos.hook.chroot" config/hooks/live/
chown -R root:root config/includes.chroot
find config/includes.chroot -type d -exec chmod 0755 {} +
find config/includes.chroot -type f -exec chmod 0644 {} +
find config/includes.chroot/usr/local -type f -exec chmod 0755 {} +
chmod 0755 config/hooks/live/*.hook.chroot
lb build
iso=$(find . -maxdepth 1 -name '*.hybrid.iso' -type f -print -quit)
[[ -n "$iso" ]] || { echo 'live-build no produjo ISO'; exit 1; }
out="$project/dist/culinaryos-0.2.0-dev-$profile-$stamp"
mkdir "$out"
cp "$iso" "$out/CulinaryOs-$profile-amd64.iso"
cp build.log build-tools.tsv "$out/"
cp chroot/usr/share/culinaryos/packages.tsv "$out/"
cp chroot/usr/share/culinaryos/copyrights.tar.gz "$out/"
cp "$project/config/project.json" "$out/"
(cd "$out" && sha256sum -- ./*.iso > SHA256SUMS)
echo "ISO de desarrollo generada: $out. No equivale a validación de arranque."
