> Ruta adicional 0.2.0-dev: scripts/install-lab.sh sobre VM Debian 13 ya instalada y perfil sucursal. Añadir python3-nacl al constructor. No sustituye el instalador de disco de la ISO, que sigue pendiente. Detalles en RUNTIME-SUCURSAL.md.

# Construcción, Live e instalación

## Entorno observado

Windows con Git Bash. wsl.exe no ofreció una distribución utilizable. No se localizaron Docker/Podman/QEMU ni Python en PATH. Se descargó Python portátil al proyecto sólo para pruebas. No se habilitó ningún componente de Windows. CIM denegó la consulta de hardware: no hay inventario validado.

No se generó ISO ni checksum de ISO, ni se probó arranque.

## Constructor Linux independiente

Prepare una VM Debian 13 amd64 con sudo y sin datos reales. Asignación inicial sugerida para construir un perfil a la vez: 4 vCPU, 4 GiB RAM, 40 GiB disco; **no son mínimos medidos**. Necesita red hacia repositorios oficiales.

Copie config, os, scripts, tests, docs, README.md, VERSION y los archivos de control de texto a ~/CulinaryOS en ext4, excluyendo tools/python, build y dist. No construir en una carpeta NTFS compartida: permisos, enlaces y dispositivos importan.

Dentro de la VM:

~~~bash
sudo apt-get update
sudo apt-get install --no-install-recommends live-build debootstrap squashfs-tools xorriso \
  isolinux syslinux-common grub-pc-bin grub-efi-amd64-bin grub-efi-amd64-signed \
  shim-signed mtools dosfstools ca-certificates python3 shellcheck nftables \
  qemu-system-x86 qemu-utils ovmf
cd ~/CulinaryOS
bash scripts/verify-linux.sh
sudo unshare -n nft --check --file os/overlay/etc/nftables.conf
sudo bash scripts/build.sh terminal
sudo bash scripts/build.sh servidor
~~~

unshare valida en otra red sin aplicar reglas al constructor. El hook también valida nft, visudo y systemd; falla si no puede comprobar. No omita estos controles para obtener una ISO aparentemente correcta.

Cada build crea build/PERFIL-FECHA-PID sin borrar otro chroot. Sólo copia os/overlay, nunca toda la carpeta ni software del restaurante. Sólo admite Debian trixie amd64 y root; ejecutarlo exclusivamente en la VM de construcción.

Si lb build termina, dist/culinaryos-0.1.0-dev-PERFIL-FECHA contiene ISO, SHA256SUMS, versiones, licencias y log. Use la ruta real:

~~~bash
cd dist/culinaryos-0.1.0-dev-terminal-FECHA
sha256sum -c SHA256SUMS
~~~

Generar una ISO no demuestra que arranque.

## Probar Live

~~~bash
bash scripts/run-vm.sh ruta/a/CulinaryOs-terminal-amd64.iso bios
bash scripts/run-vm.sh ruta/a/CulinaryOs-terminal-amd64.iso uefi
bash scripts/run-vm.sh ruta/a/CulinaryOs-terminal-amd64.iso secure
~~~

El script crea un disco qcow2 desechable en build/vm; nunca usa discos físicos. La red emulada está restringida, sin puertos publicados. La emulación TCG evita exigir cambios de anfitrión; las mediciones de rendimiento deberán repetirse con aceleración y registrar esa diferencia.

Complete las cuentas en tty1. En Terminal use luego LightDM; en Servidor la consola. Los cambios Live, credenciales y logs del overlay se pierden al reiniciar. No se habilita persistencia Live.

Para Secure Boot, compruebe mokutil --sb-state dentro del invitado y la cadena shim/GRUB/kernel firmada por Debian. Tener firmware con capacidad Secure Boot no demuestra que la verificación esté activa.

## Instalador: pendiente

Esta versión fija debian-installer none. No es una imagen instalable ni demuestra persistencia en disco.

Después de validar Live, incorporar Debian Installer live o una ruta Debian seguida de paquete CulinaryOs. Preservar selección y resumen de disco, cifrado, particiones, confirmación final de borrado y credenciales propias. Sin preseed de contraseñas ni particionado automático. Probar sólo sobre discos virtuales nuevos y snapshots.

No copiar a mano el overlay completo sobre una instalación en uso. No usar discos de Windows ni alterar su cargador para este laboratorio.
