> Ampliación vigente 0.2.0-dev: consulte RUNTIME-SUCURSAL.md, CIFRADO-V1.md y SINCRONIZACION-V1.md para el almacenamiento, servicios y sincronización implementados.

# Arquitectura y modelo de amenazas

Referencia: 2026-10-14; versión 0.1.0-dev. Objetivo: VM amd64 con dispositivos virtuales estándar. Sin promesas de compatibilidad con terminales físicos, impresoras, lectores o Wi-Fi no evaluados.

## Decisiones

Debian 13 Stable, rama trixie, linux-image-amd64 y paquetes oficiales. Sin modificaciones de kernel. APT verifica firmas y utiliza sólo main. Repositorios mutables: el procedimiento es repetible, **no reproduce imágenes idénticas bit a bit**. Cada construcción exporta versiones, log, licencias y checksum.

Terminal: Xorg, XFCE, LightDM y panel Tk local. XFCE es una elección provisional, pendiente de comparación por mediciones. Sin navegador, servidor web o aplicación. Servidor: multi-user.target, sin escritorio ni SSH. NetworkManager es el único gestor de red previsto.

Se mantienen ID=debian y VERSION_ID de Debian para compatibilidad; NAME y PRETTY_NAME muestran CulinaryOs y CULINARYOS_VERSION registra la versión propia.

## Flujo candidato

1. Paquetes de arranque Debian: BIOS/syslinux y UEFI/GRUB. Secure Boot exige paquetes firmados; no se acepta caída silenciosa a un GRUB sin firma. Firmware y cadena real pendientes de probar.
2. Plymouth presenta identidad y mensajes recibidos, sin porcentaje inventado. Esc muestra mensajes técnicos.
3. Alta en tty1: administrador con contraseña propia mediante passwd/PAM, operador sin sudo y root bloqueado. Marcador sólo al completar. No hay autologin.
4. Getty y display-manager esperan el alta. LightDM requiere nftables. Los fallos generan aviso; no se abre shell root ni se entra automáticamente a un rescue.target inaccesible con root bloqueado.
5. Timer de diagnóstico sin dependencia de internet. Tiempo, memoria, CPU y tareas limitados; no reinicios indefinidos. Un resultado crítico activa el aviso de mantenimiento.
6. Panel sin privilegios, leyendo estado público en /run. Registros detallados sólo para administración.

Raíz RO, permisos inseguros y firewall ausente se consideran críticos. Internet, ruta externa, DNS opcional y actualizaciones generan avisos. Un fallo del colector produce estado ausente o vencido, nunca salud confirmada. El aviso de mantenimiento no paraliza automáticamente una aplicación futura inexistente.

## Fronteras y amenazas

| Frontera / activo | Amenaza | Mitigación y límite |
|---|---|---|
| Imagen/paquetes | Alteración de origen | APT firmado y checksum; firma propia del artefacto pendiente |
| Operador → administrador | Escalada | Sin sudo operativo; administrador separado y sudo autenticado |
| Red → VM | Escaneo e ingreso | inet input/forward drop; no listeners de aplicación ni SSH |
| Usuario → configuración | Borrado o modificación | Propiedad root; rutas sensibles 0700/0600 |
| Disco/corriente | Pérdida o corrupción | Apagado systemd, copias externas; sin fsck sobre volúmenes montados |
| Aplicación futura → SO | Compromiso y agotamiento | Contrato de identidad y recursos; todavía no existe aplicación |
| Consola → primer alta | Apropiación inicial | Custodia física; el alta no puede verificar una identidad previa |
| Hipervisor → invitado | Lectura de RAM/disco | Hipervisor fuera de la frontera defensiva; proteger anfitrión y snapshots |
| Copia → restauración | Tar malicioso | Lista positiva, checksum, sin enlaces ni sobrescritura; checksum no autentica |

AppArmor y perfiles mantenidos por Debian se incluyen, pero no se declara eficacia ni compatibilidad sin aa-status y pruebas reales. No se confina globalmente el intérprete Python con un perfil improvisado. Las restricciones systemd del diagnóstico también deben probarse en el kernel objetivo.

Se conserva PAM de Debian. Los límites progresivos y bloqueos temporales específicos de CulinaryOs están **pendientes de implementación y prueba**, con recuperación local que preserve al administrador. Fail2ban no se instala al no existir servicio expuesto y logs de autenticación validados.

syncookies, límites del diagnóstico y logs reducen ciertos agotamientos locales. No detienen un DDoS volumétrico: requiere router, operador o proveedor. No se realizan cargas contra redes ajenas.

## Cifrado y claves

Evaluar LUKS2 en la futura instalación sobre disco virtual desechable. El desbloqueo al arranque impide prometer funcionamiento cifrado desatendido. No se distribuyen claves privadas, contraseñas ni TPM enrolado. Mantener clave de recuperación y copia de encabezado LUKS offline, protegidas en destinos distintos y ensayadas. Perder todas las claves hace irrecuperables los datos. Secure Boot y pantalla completa no sustituyen cifrado ni seguridad física.

## Mantenimiento

Ventanas manuales con revisión semanal de seguridad, firmas APT y simulación antes de instalar. Timers APT automáticos desactivados y reboot automático desactivado. Los scripts no ordenan reinicio del equipo; maintainer scripts pueden reiniciar servicios durante actualizaciones, por lo que debe cerrarse el uso operativo.

La copia actual cubre una lista de configuración no secreta. No incluye cuentas, hashes, claves, /home o datos de restaurante y no equivale a imagen completa del disco.
