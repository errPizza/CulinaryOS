#!/bin/bash
set -Eeuo pipefail
project=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
cd "$project"
python3 tests/test_project.py
python3 tests/test_diagnostics.py
python3 tests/test_backup.py
python3 tests/test_network.py
python3 tests/test_pki.py
python3 tests/test_data.py
python3 tests/test_runtime.py
python3 tests/test_firstboot.py
python3 tests/test_sync_tls.py
while IFS= read -r -d '' file; do bash -n "$file"; done < <(find scripts os/hooks os/overlay/usr/local/sbin -type f \( -name '*.sh' -o -name '*.hook.chroot' -o -path '*/sbin/*' \) -print0)
if command -v shellcheck >/dev/null; then shellcheck scripts/*.sh os/hooks/*.hook.chroot os/overlay/usr/local/sbin/*; fi
echo 'Sintaxis y lógica verificadas. Para nft use sudo unshare -n nft -c -f os/overlay/etc/nftables.conf.'
