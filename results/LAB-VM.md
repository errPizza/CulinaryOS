# Evidencia del laboratorio del usuario

Fecha de las capturas: 15 de octubre de 2026. Evidencia visual enviada por el usuario, sin acceso directo del agente al invitado.

- Debian 13 amd64 instalado en VirtualBox; sesión laboratorio operativa y sudo habilitado.
- ZIP transferido mediante CD de datos; sha256sum informó La suma coincide.
- Primer intento detenido por policykit-1-gnome sin candidato; corregido a lxpolkit.
- install-lab.sh llegó al mensaje Preparado; visudo informó parsed OK. No se conserva un log completo de esa ejecución Linux, por lo que no se asigna un conteo de pruebas Linux a partir de esa captura.
- Tras reiniciar, GRUB inició Debian y se ejecutó culinaryos-firstboot. La captura muestra contraseñas que no coinciden y salida fallida de passwd; firstboot falló y LightDM/getty tty1 quedaron bloqueados por dependencia. Hay un mensaje de clocksource mezclado con el diálogo.
- Recuperación desde tty2 indicada al usuario; finalización del alta y primer escritorio pendientes de confirmación.

La corrección en fuentes del alta agrega reintentos, reanudación y login de recuperación. Se verificó en Windows con siete escenarios de shell y comandos de cuentas simulados. La suite local suma 131 aprobaciones y una omisión AF_UNIX (132 pruebas), con 15 comprobaciones Bash y ShellCheck sin observaciones. Esa validación no comprueba PAM ni systemd reales.

## Avance posterior y comprobación de red

El usuario mostró el escritorio XFCE con el logo y la bienvenida, sesión operador y diagnóstico de sistema instalado. Otra captura muestra systemctl --failed sin unidades fallidas. Tras añadir un segundo adaptador: enp0s3 UP con 10.0.2.15/24 y ruta por defecto 10.0.2.2; enp0s8 UP sin IPv4, esperando DHCP bajo NetworkManager. La salida NAT está gestionada fuera de NetworkManager.

El intento de deploy-site falló en chronyd -p -f durante la comprobación previa. No llegó a la confirmación DESPLEGAR-SITIO ni a aplicar la red. El stderr no aparece en la excepción de la versión instalada: causa exacta pendiente de la orden diagnóstica solicitada. La edición sed de gateway quedó con comillas abiertas y se canceló; se debe corregir gateway a null y regenerar un paquete nuevo antes de desplegar.

En las fuentes se cambió la comprobación a chronyd -p con las directivas generadas como argumentos (sin shell ni acceso al temporal /run), con límite de tiempo y mensaje de error visible. No se afirma que la corrección ya esté aplicada en la VM ni que se haya confirmado una denegación de AppArmor.

## Diagnóstico de permiso y reparación preparada

El usuario corrigió el nombre del archivo y comunicó: Fatal error: Could not open /root/site-lab/chrony.conf: Permission denied. Esto confirma una lectura rechazada, sin demostrar qué mecanismo la denegó. La validación mediante directivas argv evita esa ruta; el CD de reparación la comprobará realmente en la VM antes de instalar el módulo corregido. El plan nuevo usa gateway null y una carpeta nueva para no reutilizar el paquete antiguo. No se ha confirmado aún una IP 10.77.0.10 activa ni el almacén en servicio.

## Resultado posterior del CD de reparación

El usuario mostró SHA256SUMS correcto para los tres archivos del CD y Comprobación real de Chrony aprobada en esta VM. El despliegue activó la conexión y continuó tras confirmar NetworkManager y CONSERVAR. Se habilitó Avahi y se alcanzó initialize, donde systemctl enable --now falló al iniciar culinaryos-data.service. Causa del almacén pendiente del journal solicitado; no se atribuye a permisos, claves ni SQLite sin ver el error del proceso. No repetir deploy-site: existe estado parcial de red/sitio y deben revisarse los servicios.

La advertencia Failed to stop ... timer not loaded concuerda con un segundo stop del temporizador en cleanup después de haberlo detenido al confirmar. Se elimina ese segundo stop en fuentes vaciando job tras el primero exitoso. Eso no confirma por sí solo las reglas activas ni soluciona el arranque del almacén.

## Causa identificada del fallo del almacén

Las capturas del journal muestran PermissionError: Las claves requieren permisos 0600 en securedata.Keyring.load, al cargar credentials/keyring desde configured_store. El proceso llegó a esa validación, por lo que no procede atribuir este fallo a /proc/1/mounts ni a la base SQLite. systemd concede lectura al UID mediante ACL; su máscara puede aparecer como bits de grupo. Se prepara un cargador específico que verifica el contexto protegido y un CD para probarlo realmente antes de sustituir código, conservando el anillo existente y sin repetir deploy-site. El arranque correcto del almacén sigue pendiente de confirmación.

## Reparación de datos y reinicio confirmados

Las capturas posteriores confirman la prueba real de LoadCredential con el UID del almacén y salida 0/SUCCESS. El servicio culinaryos-data.service quedó active; su IPC devolvió ready=true, schema=1, site_id=local-01, pending=0, events=0 y synchronous=FULL. El script informó que conservó las claves originales.

culinaryos-health.service mostró después Result=start-limit-hit aunque su última ejecución había terminado 0/SUCCESS. Tras reset-failed y start, systemctl --failed mostró 0 loaded units listed. Después de reiniciar, otra captura volvió a mostrar cero unidades fallidas, hostname servidor-01, enp0s3 UP con 10.0.2.15/24 y enp0s8 UP con 10.77.0.10/24. Quedan por probar otra terminal y pérdida de internet. No se deduce disponibilidad de una aplicación todavía ausente.

El usuario observó que no aparecía una pantalla de carga. Se prepara una actualización del tema Plymouth con animación y un fragmento GRUB quiet splash. Su ejecución y resultado visual en la VM todavía no se han confirmado.

## Pantallas intermedias observadas

El usuario mostró el menú de GRUB con espera de cinco segundos, los avisos Loading Linux / Loading initial ramdisk, tres mensajes vmwgfx sobre hipervisor no compatible y un login en tty1. Estas capturas no confirman que el CD inicial de Plymouth se haya aplicado ni permiten evaluar su animación. Se prepara CulinaryOs-arranque-limpio.iso para ocultar el menú normal, reducir la salida de consola, ajustar quiet_boot de forma compatible y omitir el getty de tty1 en perfiles gráficos ya aprovisionados, conservando tty2. La ejecución del paquete y la transición visual siguen pendientes.
