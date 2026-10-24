# Validación

scripts/verify.ps1 produce results/local-verification.json con salidas y códigos reales. Los datos sintéticos se usan sólo en tests, nunca como estado público.

## Pruebas locales

- Identidad/perfiles, exclusión de aplicación, ausencia de claves/contraseñas embebidas y codificación LF.
- Clasificación de red ausente, servicios fallidos, poco espacio, raíz RO, permisos, firewall, memoria, PSI, carga, logs, DNS opcional, certificados, copias, actualizaciones, reboot y evidencia desconocida.
- Timeout y error de comandos sin convertirlos en salud confirmada.
- Copia/restauración con archivos reales y rechazo de entradas peligrosas.
- Sintaxis Bash de scripts, hook y herramientas.

Las aserciones de texto no demuestran que nft acepte reglas. bash -n no ejecuta herramientas Linux. ast.parse no valida GUI ni kernel.

## Campaña Linux pendiente

Antes de fallos del invitado, snapshot del disco virtual desechable. Sin red puente, puertos publicados o cargas en redes ajenas.

| Caso | Método y aceptación | Estado |
|---|---|---|
| Construcción | verify-linux, shellcheck, nft en namespace, visudo/systemd en chroot | Pendiente |
| BIOS/UEFI | Ambos perfiles; alta, login, logs | Pendiente |
| Secure Boot | Claves de firmware, mokutil, shim/GRUB/kernel oficiales | Pendiente |
| Credenciales | Propias, sin eco, operador sin sudo, root bloqueado | Pendiente |
| Alta interrumpida | Reanudar sin marcador prematuro ni usuario universal | Pendiente |
| systemd | Sin ciclos y con fallo crítico visible | Pendiente |
| Servicio fallido | Unidad transitoria /bin/false; COS-SERVICES | Lógica probada; Linux pendiente |
| Sin internet | Arranque/login con NAT restringido | Lógica probada; Linux pendiente |
| Enlace perdido | Desconectar NIC virtual; aviso, no crítico | Lógica probada; Linux pendiente |
| DNS | Nombre de laboratorio inexistente, timeout | Lógica probada; Linux pendiente |
| Poco espacio/raíz RO | Inyección probada; luego clon con volumen acotado | Lógica probada; Linux pendiente |
| Permisos | Cambiar y restaurar una ruta controlada en clon | Lógica probada; Linux pendiente |
| Firewall | DHCP/DNS/PMTU/ND; sondeo limitado entre VMs bloquea entrada | Pendiente |
| Reversión nft | No confirmar y matar aplicador; comprobar reglas y archivo | Pendiente |
| AppArmor | aa-status, denegaciones y pruebas funcionales | Pendiente |
| Fuerza bruta | Diseñar PAM, máximo seis intentos en cuenta de laboratorio, recuperar admin | Implementación pendiente |
| Actualización | Firmas, simulación, ventana, sin reboot automático | Pendiente |
| Copia/restauración | Comparación de bytes, checksum y tar adversarial | Probado en Windows |
| Destino/retención | Otro volumen, dueño/modo, fallos y últimas N | Pendiente Linux |
| Apagado/reinicio | systemctl, sin corte abrupto; nuevo arranque | Pendiente |
| Persistencia | Instalador y dos reinicios conservan configuración | Instalador pendiente |
| Rescate completo | Medio verificado y segundo disco virtual | Pendiente |
| Rendimiento | CPU/RAM, disco, arranque, diagnóstico y UI | Sin medir |

Criterios provisionales de aviso: espacio libre <15 % (crítico <5 %), memoria disponible <10 %, PSI some avg10 >10, carga a cinco minutos >2 por CPU y logs >256 MiB. No son requisitos mínimos comerciales.

Registrar por campaña: versión, checksum ISO, packages.tsv, hipervisor, firmware, Secure Boot, vCPU/RAM/disco, aceleración, red, fecha, comandos y salidas. Guardar fallos, correcciones y repeticiones. No marcar una etapa probada sin evidencia.

## Red local y PKI

Se incorporan test_network.py y test_pki.py a ambos validadores y al build. Los casos incluyen direccionamiento único, inyección en perfiles, puertos cerrados, perfiles Wi-Fi sin PSK, independencia de sondas externas, clasificación LAN/servidor/nombre/TLS/internet y firma/revocación real con OpenSSL. No equivalen a pruebas de paquetes en Debian ni de AP físico. Detalles de despliegue y matriz de fallos en RED-LOCAL.md.

## Runtime 0.2

Nuevas suites: test_data.py (cifrado, WAL/FULL, outbox, snapshots, rotación, proceso interrumpido y vector), test_runtime.py (despliegue, UPS, descubrimiento y privacidad de estado) y test_sync_tls.py (mTLS real y ACK adversos en loopback). El caso AF_UNIX se omite explícitamente en Windows y debe pasar en Linux. ShellCheck portátil se añadió al verificador local y la instalación de laboratorio rechaza el anfitrión Windows. Resultados vigentes en results/local-verification.json; no equivalen a unidad systemd arrancada.
