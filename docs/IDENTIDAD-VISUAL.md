# Identidad visual de CulinaryOS

El original aportado por el usuario se conserva, sin redibujarlo, en os/overlay/usr/share/culinaryos/branding/logo.png. Se tomó de CulinaryOsIcon1.png del escritorio y se registraron dimensiones, procedencia y SHA-256 en origin.json. Los fondos SVG incrustan exactamente esos bytes; no necesitan internet ni rutas del equipo de desarrollo.

## Dónde aparece

- Arranque y apagado gráfico: tema Plymouth culinaryos. Logo centrado, tamaño proporcional a la pantalla, puntos animados y fondo blanco; se conservan los mensajes reales y Esc para la consola. No se inventa porcentaje de progreso.
- Acceso manual: LightDM GTK, fondo con logo a la izquierda y formulario a la derecha. En sucursal el autologin puede omitir esta pantalla tras el alta inicial.
- Escritorio XFCE: fondo centrado con el logo. El autostart de branding lo aplica una vez a propiedades de monitores detectados con fondos de distribución; respeta rutas personalizadas. Si XFCE no expone propiedades, sale y puede reintentar en otra sesión. No bloquea el inicio de la app.
- Bienvenida/diagnóstico: cabecera con logo, icono de ventana y alternativa textual si no puede cargar el PNG. Se mantienen los diagnósticos y controles existentes.
- Menú: acceso CulinaryOS — Estado del equipo con icono del sistema; la entrada de autostart también declara el icono.
- Identificación del SO: LOGO=culinaryos en os-release, con icono instalado en /usr/share/pixmaps/culinaryos.png.

El fondo claro conserva el contraste de las letras y del símbolo oscuro del original. No se cambiaron colores, proporciones ni texto del logo. El original conserva sus márgenes.

## Construcción

El hook copia el PNG al directorio del tema Plymouth **antes** de update-initramfs, para que viaje dentro del arranque temprano. Los perfiles terminal y sucursal incluyen librsvg2-common para que GTK/XFCE puedan cargar los fondos SVG. El perfil servidor mantiene el logo de arranque; su sesión sigue siendo de consola.

Las fuentes se usan mediante build.sh o install-lab.sh, según RUNTIME-SUCURSAL.md. El laboratorio instalado en Debian ya mostró el logo de bienvenida. La actualización animada del arranque requiere aplicar y probar el CD indicado más abajo. No se personalizó el firmware ni el menú del cargador de la ISO, todavía no generada. La app futura conserva su propia interfaz.

Para cambiar el fondo más adelante, usar la configuración de escritorio de XFCE. No se reimpone en cada inicio; el marcador de usuario es ~/.config/culinaryos/branding-v1 (o el directorio XDG_CONFIG_HOME correspondiente).

## Validación pendiente de Linux

Comprobar arranque gráfico en resoluciones pequeñas y pantallas HiDPI, Esc/consola, formulario LightDM sin solapar el logo, primer inicio y reinicio de XFCE, preferencias personalizadas y bienvenida. Los scripts y recursos se verificaron desde Windows; no se afirma haber arrancado estas pantallas en Linux.

Referencias de configuración: [LightDM GTK](https://raw.githubusercontent.com/Xubuntu/lightdm-gtk-greeter/master/data/lightdm-gtk-greeter.conf), [propiedades de fondo XFCE](https://sources.debian.org/src/xfdesktop4/4.20.2-2/src/xfdesktop-backdrop-manager.c/).

## Pantalla de carga animada (15 de octubre de 2026)

El tema ahora presenta el logo original sobre blanco y un círculo de ocho puntos dorados que cambia de intensidad. Muestra Iniciando CulinaryOS, Apagando CulinaryOS o Reiniciando CulinaryOS según el modo de Plymouth. La animación representa actividad, sin porcentaje estimado ni espera mínima artificial. Esc permite alternar los mensajes de arranque. Los diálogos de contraseña muestran asteriscos; también hay una devolución de llamada para preguntas del sistema.

El fragmento /etc/default/grub.d/60-culinaryos-splash.cfg añade quiet y splash sin reemplazar los demás argumentos ni duplicarlos. Solicita modo gráfico automático y conserva el framebuffer para el kernel. El hook regenera GRUB si detecta una instalación existente; live-build incorpora quiet splash en su propia línea de arranque. No se instala otro cargador. La revisión posterior descrita al final oculta el menú durante el arranque normal. El firmware y GRUB pueden aparecer antes de Plymouth.

### Aplicar al laboratorio ya instalado

El CD de datos dist/CulinaryOs-pantalla-arranque.iso contiene el tema, el logo original, los scripts de instalación/restauración y SHA256SUMS. No es una ISO arrancable ni un instalador del SO. En la terminal administrativa de la VM (laboratorio, no operador):

1. Desmontar el CD anterior con sudo umount /mnt/cd.
2. En VirtualBox, Dispositivos → Unidades ópticas → Seleccionar archivo de disco, elegir CulinaryOs-pantalla-arranque.iso.
3. Ejecutar sudo mount -o ro /dev/sr0 /mnt/cd.
4. Ejecutar sudo bash /mnt/cd/activar-arranque.sh.
5. Si termina con Pantalla preparada, ejecutar sudo reboot.

El script exige VM Debian trixie, consola local y CulinaryOS instalado. Verifica sumas y herramientas antes de modificar archivos; no descarga paquetes. Guarda configuración, recursos e initramfs anteriores en /var/backups/culinaryos/boot-FECHA-PID. Si falla la regeneración o la comprobación de recursos, restaura esos archivos. Para volver después, ejecutar sudo bash RUTA-DE-LA-COPIA/restaurar-arranque.sh usando la ruta impresa. No cambia la red, las claves, la base de datos ni los servicios operativos.

Si la pantalla gráfica queda negra, en el menú GRUB pulsar e, quitar quiet y splash de la línea linux, añadir plymouth.enable=0 y arrancar con Ctrl+X. Es una modificación temporal para ese arranque; permite entrar y restaurar la copia. No desactivar el cifrado ni cambiar las opciones de disco.

### Validación

Se verifican sintaxis Bash/ShellCheck, parámetros de GRUB conservados tras aplicar dos veces el fragmento y contenido del CD. No hay motor Plymouth ni kernel Linux disponibles en el entorno Windows del agente: renderizado, animación, Esc y transición al escritorio siguen pendientes de la prueba de este CD en la VM. La animación no confirma que la futura aplicación esté lista. La disponibilidad gráfica también depende del controlador de vídeo/KMS de la VM.

Fuentes técnicas: [Plymouth](https://wiki.freedesktop.org/www/Software/Plymouth/), [API usada por el tema script de Debian trixie](https://sources.debian.org/src/plymouth/24.004.60-5/themes/script/script.script).

## Ocultar las pantallas intermedias del Debian instalado

El CD actualizado dist/CulinaryOs-arranque-limpio.iso sustituye al CD inicial para esta tarea. Incluye todos los recursos del logo y la animación; no requiere haber aplicado antes el paquete inicial. Usar los mismos pasos de montaje y activar-arranque.sh indicados arriba, seleccionando esta nueva ISO.

| Pantalla observada | Ajuste |
| --- | --- |
| Menú azul de GRUB | GRUB_TIMEOUT_STYLE=hidden y GRUB_TIMEOUT=1. Esc o F4 durante ese segundo permite abrir el menú; se conservan las entradas avanzadas. |
| Loading Linux / Loading initial ramdisk | bootconfig.py ajusta únicamente quiet_boot a 1 en /etc/grub.d/10_linux. La lógica de generación de kernel, initrd y entradas avanzadas queda intacta. |
| Mensajes habituales del kernel | quiet splash y, si no hay valor administrativo explícito, loglevel=3. El kernel conserva sus registros; los errores de nivel 3 como los de vmwgfx no se imprimen por defecto en consola. Niveles críticos aún pueden aparecer. |
| Estados de servicios | systemd.show_status=error, salvo preferencia explícita existente. Muestra fallos, sin los estados rutinarios. |
| servidor-01 login en tty1 | En terminal y sucursal, una condición omite ese getty después de crear el marcador provisioned. Se habilita getty@tty2.service para la consola administrativa. El perfil servidor conserva su login normal. |

La consola administrativa se abre con Ctrl+Alt+F2; en VirtualBox, Ctrl derecho+F2. La configuración inicial todavía usa tty1 y, si falla antes de crear el marcador, el login de recuperación de tty1 permanece disponible. Esta revisión no cambia las dependencias de primer arranque ya instaladas: el equipo de laboratorio actual ya completó esa fase.

El instalador comprueba la asignación quiet_boot de Debian antes de cambiar nada. Si el formato es diferente o ambiguo, se detiene. La copia incluye ahora 10_linux, el módulo bootconfig y la condición de tty1; el restaurador también recupera el estado anterior de habilitación de tty2 cuando corresponde. Se comprueba la sintaxis de GRUB generado y los recursos de Plymouth en initramfs. No se modifica grub.cfg a mano ni se sustituye GRUB por otro cargador.

10_linux es una configuración de Debian modificada localmente. Al actualizar el paquete grub-common, revisar las preguntas sobre configuraciones locales. Si se acepta una versión nueva del mantenedor y reaparecen los mensajes de carga, ejecutar el ajuste compatible de bootconfig.py antes de update-grub; una versión desconocida debe revisarse en vez de forzar el reemplazo.

Plymouth empieza después del firmware y del cargador. Puede haber un instante negro o cambios de resolución; no se garantiza un logo continuo desde que se enciende el equipo. El firmware, una entrada de recuperación, una contraseña de disco, un fallo crítico o una demora pueden mostrar pantallas de diagnóstico. El objetivo es el arranque normal del sistema instalado. En una ISO Live, el menú propio de live-build no se ha personalizado ni probado.

El aviso exacto de vmwgfx mostrado por el usuario está documentado como inocuo por un colaborador de Oracle; por sí solo no demuestra que Plymouth haya fallado. No se cambia el controlador de vídeo ni se bloquea vmwgfx para ocultarlo. Si faltara el logo después de aplicar el CD, recoger desde laboratorio: cat /proc/cmdline, sudo plymouth-set-default-theme y sudo journalctl -b -u plymouth-start.service --no-pager. La prueba visual del CD sigue pendiente.

Referencias: [GRUB: menú oculto](https://www.gnu.org/software/grub/manual/grub/html_node/Simple-configuration.html), [generador de Debian 13](https://sources.debian.org/src/grub2/2.12-9%2Bdeb13u2/util/grub.d/10_linux.in), [niveles de consola del kernel](https://raw.githubusercontent.com/torvalds/linux/v6.12/Documentation/admin-guide/kernel-parameters.txt), [systemd: show_status](https://manpages.debian.org/trixie/systemd/systemd.1.en.html), [VirtualBox: diagnóstico de vmwgfx](https://github.com/VirtualBox/virtualbox/issues/67).
