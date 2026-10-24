> Operación actual del runtime 0.2.0-dev: RUNTIME-SUCURSAL.md. Almacén, outbox y sincronización sí tienen implementación; la aplicación de negocio sigue ausente.

# Operación

Herramientas candidatas del invitado; ejecución Linux pendiente según VALIDACION.md.

## Alta y uso

Controlar físicamente la consola durante primer alta. passwd establece contraseñas propias sin guardarlas en el proyecto. Root queda bloqueado; operador no tiene sudo. No agregue operador a disk, adm, systemd-journal o sudo. En Live todas las cuentas y cambios se pierden al reiniciar.

El panel muestra «CulinaryOs preparado. Aplicación pendiente de integración», indicadores COS, gravedad, parte afectada y acción. Un resultado ausente o vencido se muestra como desconocido. No hay una aplicación ficticia detrás.

El apagado y reinicio usan systemd/logind con autorización polkit. Ctrl+Alt+F2 es un login normal, no una consola root. Esc permite ver mensajes de arranque.

## Administración

~~~bash
sudo culinaryos-maintenance
sudo systemctl --failed
sudo journalctl -b -p warning
sudo dpkg-reconfigure locales keyboard-configuration tzdata
sudo nmtui
~~~

Mantener registros técnicos en canales administrativos; el panel no recibe stdout/stderr de estos comandos. El menú permite retirar el aviso tras corregir el problema; reaparece si persiste.

El diagnóstico consulta servicios, enlaces y rutas, DNS declarado, espacio, raíz RO en namespace PID 1, permisos, memoria/PSI, carga, logs, errores de kernel, firewall, caché APT, paquetes pendientes, marcador de reinicio, certificados declarados y copias. No consulta internet por defecto ni detecta todos los fallos físicos.

SMART sólo cuando lo soporte el dispositivo: primero sudo smartctl --scan-open; luego sudo smartctl -a RUTA sobre el dispositivo identificado. No hay smartd permanente ni pruebas extensas durante uso.

## Firewall y red

Tabla inet para IPv4/IPv6. input y forward drop; output accept. Se conservan loopback, established/related, DHCP cliente e ICMP/ICMPv6 para errores, PMTU, ND/RA. Logs de descarte limitados. No hay puerto SSH o de aplicación abierto.

Desde consola local:

~~~bash
sudo culinaryos-firewall-apply /ruta/administrativa/candidato.nft
~~~

Valida y conserva reglas/archivo anterior. Programa reversión independiente a 90 segundos y exige CONSERVAR antes de 60. Un fallo normal revierte; una muerte brusca conserva el snapshot para el watchdog. Este camino está preparado, todavía debe probarse con nft/systemd.

El archivo administra todo el ruleset. Docker, VPN u otros administradores de reglas exigen rediseñar la integración.

SSH no se instala y queda enmascarado. Para habilitarlo en el futuro se requiere necesidad y alcance autorizados: openssh-server, PasswordAuthentication no, KbdInteractiveAuthentication no, PermitRootLogin no, claves verificadas, sshd -t y nft limitado a interfaz/CIDR administrativos. No hay claves ni regla abierta de demostración. Evaluar Fail2ban sólo con registros reales y pruebas limitadas.

Separar redes operativa, administrativa e invitados mediante VLAN/ACL del router. El invitado no implementa esa separación física ni absorbe DDoS volumétrico.

## Actualizaciones

Revisar seguridad Debian y tracker al menos semanalmente con responsable definido. Caché reciente no equivale a ausencia de vulnerabilidades.

~~~bash
sudo culinaryos-update
~~~

Actualiza índices firmados, simula upgrade y exige confirmaciones. No usa full-upgrade ni reboot automático. Paquetes pueden reiniciar servicios durante la ventana. needrestart informa kernel y bibliotecas; revisar sus resultados antes de programar systemctl reboot.

El panel sólo conoce marcadores de reinicio cuando existen: no se garantiza detectar todo reinicio necesario en Debian. Completar ese indicador es un pendiente explícito. Los timers APT periódicos están desactivados; sin responsable, esta política es insuficiente.

## Respaldos y medición

Copias desactivadas hasta disponer de otro volumen montado, protegido y propiedad root 0700. Destino previsto: /mnt/culinaryos-backup. El script no cifra: evaluar LUKS/protección del destino por separado. Ajustar /etc/culinaryos/backup.json con enabled=true y retención 2-100. Ejecutar la copia desde el menú. Se valida antes de eliminar copias antiguas.

Se respaldan configuraciones seleccionadas, no cuentas, claves, /home ni datos del restaurante. No hay copia completa ni tarea pesada automática durante uso. Programación requiere una ventana real.

~~~bash
sudo culinaryos-benchmark
~~~

Guarda hardware invitado, virtualización, CPU/RAM durante diez segundos, disco, systemd-analyze y coste del diagnóstico en /var/lib/culinaryos. Comparar ambos perfiles tras estabilizar. Medir también respuesta de UI en VM; no se publican cifras sin ejecutarlo.

## Red y certificados de sitio

Consultar RED-LOCAL.md para despliegue de perfiles y diagnóstico COS-LAN; CERTIFICADOS-LOCALES.md para CA offline y confianza. No se generan identidades de sitio al compilar. Chrony sustituye a systemd-timesyncd: la base no escucha NTP; el perfil de sitio puede servir hora local sólo a la LAN.

El respaldo selectivo ahora incluye site.json, hosts, chrony y la política de conectividad NetworkManager. Excluye perfiles con PSK, claves TLS y CA privada; deben protegerse mediante procedimientos de credenciales/copia cifrada separados.
