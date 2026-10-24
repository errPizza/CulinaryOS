# Riesgos y pendientes actuales — 0.2.0-dev

## Implementado ahora

Almacén opaco cifrado y outbox transaccional, sincronizador emisor mTLS, perfil combinado sucursal, usuarios/unidades de servicio, registro/arranque de ejecutables reales, mDNS y selección con TLS, NUT por USB identificado, instalación de laboratorio y contratos para la app/central.

Ninguno de estos componentes incorpora el software del restaurante ni sus credenciales/datos. Los documentos/resultados del 14 de octubre corresponden a la primera etapa; RUNTIME-SUCURSAL.md y el informe más reciente describen el estado actual.

## Requiere entorno Linux

- Instalar en VM Debian 13 amd64, validar systemd-analyze, usuarios, LoadCredential, grupos y socket Unix.
- Probar nft con kernel real, DHCP/IPv6/mDNS, checkpoint, reversión y aislamiento VLAN.
- Arrancar los tres perfiles; validar Plymouth/LightDM/autologin opcional y shutdown.
- Probar Avahi/D-Bus, permisos del publicador y descubrimiento desde clientes reales.
- Validar chrony/RTC, rendimiento, límites de recursos y recuperación tras reinicio.
- Revisar AppArmor con aplicaciones reales y diseñar/probar límites PAM progresivos sin bloqueo irrecuperable.
- Construir ISO, BIOS/UEFI/Secure Boot y luego instalador de disco/persistencia/rescate.
- El instalador de laboratorio también debe ejecutarse en una VM desechable; sólo pasó sus controles estáticos y rechazo del anfitrión actual.

No se habilitó WSL, Hyper-V ni otros componentes del anfitrión para evitar este límite.

## Requiere aplicación real

- Binarios de UI/backend, API HTTPS de meseros/cocina/gerente, esquema y reglas de negocio.
- Autenticación, autorizaciones, sesiones, reintentos de UI, pagos y validación de operaciones.
- Readiness verdadero y adaptación al IPC; pruebas de carga, recursos y perfil AppArmor de sus ejecutables.
- Decidir si el almacén opaco por agregados encaja con sus transacciones/consultas. No se entrega un esquema relacional de restaurante ni transacciones multirregistro por IPC.
- Gestión de catálogos, conflictos y sincronización de cambios central → sucursal.
- Registro del ejecutable real y apertura del puerto sólo después de TLS válido.

## Requiere central real

URL, autoridad, certificado/clave de cliente aprobados y receptor que persista/deduplique antes de confirmar. Las pruebas usan un receptor efímero en loopback, no un central desplegado. Hasta aprovisionarlo no se contacta ningún destino.

Un rechazo persistente bloquea FIFO; requiere resolución administrativa/aplicativa y no se descarta silenciosamente. El transporte es al menos una vez; no garantiza por sí solo efectos de negocio exactamente una vez.

## Requiere hardware

Modelo/IDs/serial y controlador NUT compatibles, udev/passthrough, umbrales, autonomía y apagado completo. Wi-Fi y firmware reales. Disco/controlador que respete sincronización, pruebas de energía y cifrado LUKS/TPM según arranque desatendido.

La copia del anillo se cifra, pero el anillo de servicio está protegido por permisos y credenciales del SO en el disco local. Un robo de disco completo no queda resuelto sin cifrado del volumen/gestión de claves física apropiada. Perder todas las claves hace irrecuperables los datos.

## Otros límites

Sin requisitos mínimos ni cifras de rendimiento medidas. Sin rollback completo de paquetes o despliegue de red. Copias del mismo disco no protegen contra pérdida del dispositivo. Sin firma propia de ISO ni revisión final de redistribución de fuentes propias. Las versiones de paquetes del SO siguen las actualizaciones oficiales, no hashes inmóviles del entorno portátil.
