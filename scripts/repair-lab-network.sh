#!/bin/bash
# Reparación atendida de la VM de laboratorio observada. No es un actualizador general.
set -Eeuo pipefail
umask 077
export PYTHONDONTWRITEBYTECODE=1
[[ $(uname -s) == Linux && $EUID -eq 0 ]] || { echo 'Sólo root en una VM Debian de laboratorio.'; exit 2; }
[[ -t 0 && -t 1 && -z ${SSH_CONNECTION:-} ]] || { echo 'Usar la terminal local del invitado.'; exit 2; }
# shellcheck source=/dev/null
. /etc/os-release
[[ ${ID:-} == debian && ${VERSION_CODENAME:-} == trixie ]] || { echo 'Se requiere Debian 13 trixie.'; exit 2; }
systemd-detect-virt --vm --quiet || { echo 'Se exige una VM.'; exit 2; }
[[ -f /etc/culinaryos/profile && $(cat /etc/culinaryos/profile) == sucursal ]] || { echo 'Se requiere el perfil sucursal instalado.'; exit 2; }
[[ ! -e /etc/culinaryos/application.json ]] || { echo 'Revisar la aplicación registrada antes de cambiar la red.'; exit 2; }
profile=/etc/NetworkManager/system-connections/culinaryos-local-01-servidor-01.nmconnection
[[ ! -e $profile ]] || { echo 'Ya hay un perfil desplegado: revisar el estado, no repetir esta reparación.'; exit 2; }
media=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
source_module="$media/deployment.py"
source_plan="$media/lab-site.json"
if [[ ! -f $source_module || ! -f $source_plan ]]; then
    source_module="$media/../os/overlay/usr/local/lib/culinaryos/deployment.py"
    source_plan="$media/../config/network/site-plan-lab-virtualbox.json"
fi
[[ -f $source_module && -f $source_plan ]] || { echo 'Paquete de reparación incompleto.'; exit 2; }
if [[ -f $media/SHA256SUMS ]]; then (cd "$media" && sha256sum -c SHA256SUMS); fi
ip link show dev enp0s3 >/dev/null
ip link show dev enp0s8 >/dev/null
echo 'Se comprobará Chrony sin leer un archivo de configuración bajo /root o /run.'
echo 'Se respaldará y corregirá deployment.py; después se propondrá 10.77.0.10/24 en enp0s8.'
echo 'La red interna no tendrá gateway; la salida NAT de enp0s3 se conserva.'
python3 - "$source_module" "$source_plan" <<'PY'
import ast, importlib.util, json, sys
from pathlib import Path
sys.path.insert(0,"/usr/local/lib/culinaryos")
from dataio import persistent_root
persistent_root()
source=Path(sys.argv[1]);ast.parse(source.read_text(encoding="utf-8"))
spec=importlib.util.spec_from_file_location("culinaryos_repaired_deployment",source)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
spec=importlib.util.spec_from_file_location("culinaryos_site","/usr/local/lib/culinaryos/site.py")
site=importlib.util.module_from_spec(spec);spec.loader.exec_module(site)
plan=json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
if plan.get("site_id")!="local-01" or plan.get("gateway") is not None:
    raise ValueError("Plan de laboratorio inesperado")
files=site.render(plan,"servidor-01","enp0s8")
expected=json.loads(files["site.json"])
if expected["expected_address"]!="10.77.0.10":raise ValueError("IP de laboratorio inesperada")
module.validate_chrony(files["chrony.conf"])
print("Comprobación real de Chrony aprobada en esta VM.")
PY
work="/root/culinaryos-reparacion-red-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 0700 "$work"
target=/usr/local/lib/culinaryos/deployment.py
[[ -f $target && ! -L $target ]] || { echo 'Revisar módulo de despliegue instalado.'; exit 2; }
cp -p -- "$target" "$work/deployment.py.anterior"
chmod 0600 "$work/deployment.py.anterior"
# Sustitución atómica en el mismo sistema de archivos, sin tocar otros módulos.
temporary=$(mktemp /usr/local/lib/culinaryos/.deployment.XXXXXX)
trap 'rm -f -- "$temporary"' EXIT
install -m 0644 -o root -g root "$source_module" "$temporary"
mv -- "$temporary" "$target"
install -m 0600 -o root -g root "$source_plan" "$work/plan.json"
echo "Copia anterior y plan: $work"
culinaryos-site-plan --plan "$work/plan.json" --node servidor-01 --interface enp0s8 --output "$work/site"
echo 'El despliegue pedirá DESPLEGAR-SITIO, confirmación de NetworkManager y CONSERVAR.'
culinaryos-runtime deploy-site "$work/site"
ip -br address
ip route
systemctl is-active culinaryos-data.service
echo 'Reparación y despliegue terminados. Verificar la salida antes de reiniciar.'
