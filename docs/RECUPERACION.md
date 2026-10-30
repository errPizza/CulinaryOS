> Se añadieron snapshots consistentes del almacén cifrado, copia cifrada del anillo y rotación. Recuperación actual y orden de claves en RUNTIME-SUCURSAL.md. El procedimiento anterior cubre sólo configuración.

# Recuperación y rescate

## Evidencia real

Se probó copia tar con archivos reales, SHA-256, extracción a carpeta nueva y comparación byte a byte. Se rechazaron alteración, rutas peligrosas, symlinks, archivos no permitidos, falta de checksum y destino existente. No se probó rescate arrancable, recuperación de paquetes, LUKS ni restauración completa. SHA-256 no autentica una copia si el atacante reemplaza también el checksum.

## Configuración

Conservar evidencia y copia del archivo afectado. Extraer a un directorio nuevo, nunca sobre raíz:

~~~bash
sudo python3 /usr/local/lib/culinaryos/backup.py \
  --restore-staging /mnt/culinaryos-backup/ARCHIVO.tar.gz /root/culinaryos-recuperacion
~~~

Comparar y restaurar únicamente archivos revisados usando install con propietario/modo explícitos. Validar nft --check para firewall y systemd-analyze verify para unidades. Verificar funcionamiento tras cada cambio. No hay restauración automática sobre el sistema activo.

La lista excluye contraseñas, claves, cuentas, /home y marcador de alta. No equivale a imagen completa.

## Firewall

Usar consola virtual. El aplicador deja snapshot en /run y watchdog a 90 segundos. Si falla, conservar el directorio y consultar journalctl de la unidad culinaryos-fw-rollback. Revisar /etc/nftables.conf antes de reaplicar con nft -c -f seguido de nft -f. Nunca hacerlo sobre el anfitrión.

## Paquetes

Durante una ventana y con fuentes oficiales:

~~~bash
sudo dpkg --audit
sudo dpkg --configure -a
sudo apt-get -f install
~~~

Revisar propuestas. Pueden modificar paquetes y reiniciar servicios. No son rollback. Downgrade depende de versiones disponibles y compatibilidad de datos; no se promete reversión automática.

## VM que no arranca

Conservar y clonar el disco virtual antes de cambios. Arrancar ISO oficial Debian verificada y usar Rescue mode. Identificar discos por tamaño, UUID y particiones con lsblk -f; no asumir /dev/sda. Desbloquear LUKS con las claves conservadas y montar inicialmente sólo lectura para inspección.

Consultar journal persistente del disco; Live sin persistencia puede haber perdido logs. Desmontar el sistema de archivos antes de cualquier reparación fsck. No hay reparación ni formateo automático. La reparación de GRUB debe diseñarse para BIOS/UEFI y el disco instalado cuando esa ruta se haya validado.

## Pérdida total

La imagen integrada se restaura en un equipo recién instalado con `culinaryos-recovery-kit` y `culinaryos-restore`. Ver SIMULACRO-RESTAURACION.md; el simulacro en VM sigue pendiente. Fuera de esa imagen, las copias requieren reinstalar un SO validado, reponer configuraciones revisadas y crear credenciales propias.

Para LUKS, conservar clave de recuperación y copia de encabezado offline en destinos protegidos distintos. Si se pierden todas las claves, los datos no se pueden recuperar.
