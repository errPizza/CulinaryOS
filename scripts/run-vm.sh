#!/bin/bash
set -Eeuo pipefail
[[ $(uname -s) == Linux ]] || { echo 'Requiere laboratorio Linux independiente.'; exit 2; }
[[ $# -eq 2 ]] || { echo 'Uso: bash scripts/run-vm.sh ISO bios|uefi|secure'; exit 2; }
iso=$(realpath -- "$1")
[[ -f $iso && $iso == *.iso ]] || exit 2
mode=$2
case "$mode" in bios|uefi|secure) ;; *) exit 2 ;; esac
for command in qemu-system-x86_64 qemu-img; do command -v "$command" >/dev/null; done
project=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
mkdir -p "$project/build/vm"
vm=$(mktemp -d "$project/build/vm/lab.XXXXXX")
qemu-img create -f qcow2 "$vm/disk.qcow2" 24G
args=(-machine q35 -accel tcg -cpu max -smp 2 -m 3072
      -drive "file=$vm/disk.qcow2,format=qcow2,if=virtio"
      -cdrom "$iso" -boot d -nic "user,model=virtio-net-pci,restrict=on"
      -serial "file:$vm/serial.log")
if [[ $mode != bios ]]; then
    code=/usr/share/OVMF/OVMF_CODE_4M.fd
    vars=/usr/share/OVMF/OVMF_VARS_4M.fd
    if [[ $mode == secure ]]; then
        code=/usr/share/OVMF/OVMF_CODE_4M.secboot.fd
        vars=/usr/share/OVMF/OVMF_VARS_4M.ms.fd
        args+=(-machine smm=on -global "driver=cfi.pflash01,property=secure,value=on")
    fi
    [[ -f $code && -f $vars ]] || { echo 'Falta firmware OVMF.'; exit 2; }
    cp "$vars" "$vm/vars.fd"
    args+=(-drive "if=pflash,format=raw,readonly=on,file=$code"
           -drive "if=pflash,format=raw,file=$vm/vars.fd")
fi
printf 'VM: %s\nISO: %s\nModo: %s\n' "$vm" "$iso" "$mode" | tee "$vm/campaign.txt"
sha256sum "$iso" >> "$vm/campaign.txt"
qemu-system-x86_64 -version >> "$vm/campaign.txt"
exec qemu-system-x86_64 "${args[@]}"
