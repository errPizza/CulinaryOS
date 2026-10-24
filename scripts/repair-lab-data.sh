#!/bin/bash
# Reparación local del cargador de credenciales. Conserva claves, datos y red.
set -Eeuo pipefail
umask 077
export PYTHONDONTWRITEBYTECODE=1
[[ $(uname -s) == Linux && $EUID -eq 0 ]] || { echo 'Sólo root en una VM Debian de laboratorio.'; exit 2; }
[[ -t 0 && -t 1 && -z ${SSH_CONNECTION:-} ]] || { echo 'Usar consola local del invitado.'; exit 2; }
# shellcheck source=/dev/null
. /etc/os-release
[[ ${ID:-} == debian && ${VERSION_CODENAME:-} == trixie ]] || exit 2
systemd-detect-virt --vm --quiet || { echo 'Se exige una VM de laboratorio.'; exit 2; }
[[ -f /etc/culinaryos/profile && -f /etc/culinaryos/branch.json ]] || { echo 'Se requiere la sucursal ya aprovisionada.'; exit 2; }
media=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
[[ -f $media/SHA256SUMS && -f $media/securedata.py && -f $media/dataio.py && -f $media/credential-check.py ]] || { echo 'Ejecutar desde el CD de reparación de datos.'; exit 2; }
(cd "$media" && sha256sum -c SHA256SUMS)
key_file=/etc/culinaryos/secrets/branch.keys.json
[[ -f $key_file && ! -L $key_file ]] || { echo 'Se necesitan las claves originales; no se crearán otras.'; exit 2; }
python3 - "$media" "$key_file" <<'PY'
import ast, importlib.util, sys
from pathlib import Path
sys.path.insert(0,"/usr/local/lib/culinaryos")
from dataio import persistent_root
persistent_root()
media=Path(sys.argv[1])
for name in ("securedata.py","dataio.py","credential-check.py"):
    ast.parse((media/name).read_text(encoding="utf-8"))
spec=importlib.util.spec_from_file_location("culinaryos_repaired_crypto",media/"securedata.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.Keyring.load(sys.argv[2])
print("Clave original verificada sin mostrar su contenido.")
PY
key_before=$(sha256sum "$key_file")
echo 'Prueba real de LoadCredential con el usuario del almacén, sin abrir la base de datos.'
systemd-run --unit=culinaryos-credential-check --wait --pipe --collect \
    --property=User=culinaryos-data --property=Group=culinaryos-app \
    --property=LoadCredential=keyring:/etc/culinaryos/secrets/branch.keys.json \
    --setenv=PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 "$media/credential-check.py"
work="/root/culinaryos-reparacion-datos-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 0700 "$work"
for module in securedata.py dataio.py; do
    target="/usr/local/lib/culinaryos/$module"
    [[ -f $target && ! -L $target ]] || exit 2
    cp -p -- "$target" "$work/$module.anterior"
    chmod 0600 "$work/$module.anterior"
done
cp -p /usr/local/sbin/culinaryos-firewall-apply "$work/firewall.anterior"
chmod 0600 "$work/firewall.anterior"
echo "Copias de código anterior: $work"
systemctl stop culinaryos-sync.timer culinaryos-sync.service culinaryos-data.service
for module in securedata.py dataio.py; do
    target="/usr/local/lib/culinaryos/$module"
    temporary=$(mktemp /usr/local/lib/culinaryos/.credential-repair.XXXXXX)
    install -m 0644 -o root -g root "$media/$module" "$temporary"
    mv -- "$temporary" "$target"
done
install -m 0755 -o root -g root "$media/culinaryos-firewall-apply" /usr/local/sbin/culinaryos-firewall-apply
[[ $(sha256sum "$key_file") == "$key_before" ]] || { echo 'La clave cambió durante la reparación; revisar antes de iniciar.'; exit 1; }
systemctl reset-failed culinaryos-data.service
if ! systemctl start culinaryos-data.service; then
    journalctl -u culinaryos-data.service -b -n 35 -o cat --no-pager
    exit 1
fi
systemctl enable --now culinaryos-sync.timer
[[ $(sha256sum "$key_file") == "$key_before" ]] || exit 1
systemctl is-active culinaryos-data.service
python3 /usr/local/lib/culinaryos/dataio.py health
ip -br address
ip route
systemctl --failed --no-pager
echo 'Reparación terminada. Claves originales conservadas; revisar la salida antes de reiniciar.'
