> Registro histórico de la primera etapa. Estado actual: [RUNTIME-0.2.md](RUNTIME-0.2.md); local-verification.json contiene la suite más reciente.

# Estado de entrega — 14 de octubre de 2026

Se preparó CulinaryOs 0.1.0-dev en C:\Users\kikin\Desktop\CulinaryOS, inicialmente vacía.

## Evidencia ejecutada

- Python portátil 3.13.9: 36 pruebas aprobadas (10 proyecto, 16 diagnóstico, 10 respaldo).
- Git Bash 5.3.15: 9 comprobaciones bash -n aprobadas.
- Respaldo y recuperación con archivos temporales reales, comparando bytes; rechazo de checksum alterado, tar vacío, duplicados, tamaño excesivo, rutas peligrosas, enlaces y destinos existentes.
- Construcción y script de VM invocados desde Windows: ambos rechazaron el anfitrión con código 2, antes de crear chroot o disco virtual.
- Informe con salidas completas: local-verification.json.
- Checksum del código entregado: source-SHA256SUMS. Es un inventario de fuentes, no un checksum de ISO.

## Entorno y límite

No se dispone de un Linux utilizable ni herramientas VM localizadas. wsl.exe no permitió identificar una distribución Linux. La consulta de hardware CIM fue denegada; no se inventan especificaciones.

Se descargó un intérprete portátil oficial sólo dentro de tools/python. No se instaló en Windows, se habilitó WSL/Hyper-V, modificó el arranque, formateó disco ni abrió servicio externo.

## Entregado

Arquitectura y amenazas, perfiles Debian trixie amd64, fuentes de identidad/Plymouth/panel, diagnóstico, cuentas propias, nftables, servicios systemd, mantenimiento, respaldo selectivo, construcción y laboratorio preparados, inventario previsto y manuales.

## Pendiente

No hay ISO construida ni instalada. No se han ejecutado nft, systemd, AppArmor, PAM, GUI, BIOS, UEFI, Secure Boot, apagado/reinicio ni pruebas de rendimiento en Linux. Los límites PAM progresivos, detección completa de reinicio, instalador, persistencia final y rescate completo siguen pendientes. Detalle en docs/PENDIENTES.md.

La etapa siguiente requiere una VM Debian 13 amd64 independiente. Instrucciones exactas en docs/INSTALACION.md. Las fuentes de configuración no equivalen a un SO arrancado.
