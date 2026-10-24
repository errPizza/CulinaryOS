# ISO instalable: CulinaryOS con Culinary Restaurant

Imagen híbrida Debian 13 amd64, versión integrada 0.3.0-dev. Incluye el cliente Tauri, su puente local y el backend compilados para Linux, con una sesión de Culinary Restaurant a pantalla completa. El perfil genérico histórico `scripts/build.sh` permanece separado.

## Instalación

Arranca desde una VM nueva o desde el medio de instalacion. Elige "Instalar CulinaryOS". El instalador usa el nombre de maquina `RunTimeOSDev`, crea la cuenta administradora `devmode` (nombre visible `DevMode`) y configura la red por DHCP cuando esta disponible; si no hay servidor DHCP, continua sin red. La contrasena inicial se solicita al construir la ISO y se guarda solo como hash SHA-512 dentro del preseed.

La partición guiada usa el esquema atómico de Debian: los archivos del sistema van en una partición raíz. Debian puede añadir las particiones técnicas que necesite para el modo BIOS/UEFI y una partición de intercambio. No se preselecciona un dispositivo: con varios discos, el instalador permite elegirlo; si detecta uno solo, Debian puede seleccionarlo por defecto. La escritura conserva la confirmación final.

El menu de arranque muestra solo la marca CulinaryOS y las opciones de instalacion. La cabecera grafica del instalador muestra el logo y el nombre CulinaryOS. Los mensajes detallados de arranque quedan ocultos. La instalacion copia Debian 13 Trixie desde la ISO local.

En el primer inicio, la red del instalador permanece en DHCP si esta disponible y el asistente tecnico configura el modo local sin preguntas de consola: crea la sucursal, sus claves y certificados, y deja Culinary Restaurant en **modo Setup**.

## Modo Setup de Culinary Restaurant

Al abrirse por primera vez, la app muestra el asistente "Configura tu restaurante" en lugar del inicio de sesion:

1. Bienvenida.
2. Nombre del restaurante.
3. Cuenta del gerente: nombre, usuario y contrasena (minimo 12 caracteres, escrita dos veces).
4. Confirmacion. Al pulsar "Crear restaurante y entrar" se crea la sucursal y se entra directamente a la operacion con la cuenta del gerente.

Este equipo queda autorizado automaticamente con un codigo de alta de un solo uso que no hace falta copiar. Si el inicio automatico fallara, el asistente muestra ese codigo una vez y lleva al inicio de sesion con el usuario y el codigo ya escritos. Para autorizar otros dispositivos, el gerente genera un codigo nuevo desde la app.

El Setup solo funciona mientras la sucursal no tiene restaurante. El primer arranque genera un codigo de configuracion aleatorio: el backend lo recibe como credencial de systemd (`/etc/culinaryos/secrets/restaurant-setup.code`) y la cuenta `operador` del kiosco recibe una copia privada en `/var/lib/culinary-restaurant-setup/`, que la app borra al terminar. Una vez creado el restaurante, el backend rechaza cualquier nuevo Setup.

Cada instalación genera un identificador de sucursal, almacén, claves y certificados TLS propios. El sistema Live no trae cuentas, claves ni datos de CulinaryOs_Test; la cuenta local `devmode` se crea sólo al instalar esta imagen de desarrollo.

El modo inicial usa loopback con HTTPS verificado y no abre el puerto de la aplicacion en la LAN; funciona sin Internet. El alta del gerente y el codigo de un solo uso se completan en CulinaryRestaurant. La configuracion avanzada de servidor LAN requiere preparar la red durante mantenimiento.

Después del alta, el sistema abre la sesión exclusiva de Culinary Restaurant y oculta el escritorio XFCE. La consola local conserva las herramientas de administración. El cierre habitual de la ventana de la app está bloqueado y el sistema supervisa su proceso.

## Requisitos recomendados para VirtualBox

Usa Debian 13 de 64 bits, 4 GiB de RAM, 2 CPU y un disco virtual nuevo de al menos 32 GiB. La ISO arranca en BIOS y UEFI.

## Validación de esta imagen

El SHA-256 completo, las verificaciones de BIOS/UEFI, el inventario de paquetes y las huellas del sistema raíz y de los ejecutables están en `iso-audit.json` y `SHA256SUMS`. La auditoría confirma que la ISO no contiene cuentas personales, claves operativas, datos de restaurantes ni borrado automático del disco.

Se ejecutaron 156 pruebas del sistema operativo. El cliente Linux también pasó una prueba gráfica aislada en Xvfb que comprobó interfaz visible, pantalla completa, foco por clic, cierre bloqueado y heartbeat. Los menús de arranque BIOS y UEFI de la ISO final se comprobaron en VirtualBox.

La instalación en un VDI vacío de 32 GiB llegó a activar el asistente de primer inicio. La automatización de QA no completó el alta en su ejecución completa, así que no se declara verificado el acceso final a la app después de instalar. Esa limitación de prueba no cambia la auditoría de contenido ni la ISO distribuida.

## Construcción

El build integrado se genera con `scripts/build-appliance.sh`. Usa un constructor Debian 13 amd64 aislado, compila la aplicación nativa para Linux y crea un directorio nuevo para la imagen. El constructor solicita dos veces la contraseña inicial de `devmode` y guarda sólo su hash SHA-512 en el preseed de la ISO. Requiere `librsvg2-bin` para generar los gráficos del instalador. `scripts/prepare-appliance-input.py` usa una lista permitida y excluye discos, claves y datos operativos. Para recuperar una construcción se puede pasar el directorio previo como caché al script; la nueva imagen se genera en un directorio separado.
