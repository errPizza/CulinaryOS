# Runtime de sucursal — CulinaryOs 0.2.0-dev

Implementación de infraestructura, sin aplicación del restaurante. El almacenamiento es genérico y cifrado; no contiene tablas de pedidos, pagos ni usuarios de negocio. No hay API HTTP de demostración.

## Qué inicia y en qué orden

- culinaryos-firstboot: cuentas propias en la consola.
- culinaryos-data: SQLite local con transacciones y outbox, atendido por un usuario de servicio mediante socket Unix.
- culinaryos-sync.timer/service: entrega independiente al central cuando se configure.
- culinaryos-backend: ejecutable REAL registrado, después del almacén y nftables; Type=notify sólo tras comprobar readiness.
- LightDM/escritorio: después del alta y del intento de iniciar los servicios anteriores.
- apphost session: inicia la UI nativa registrada; mientras no exista, abre la bienvenida.
- culinaryos-publish: anuncia por DNS-SD sólo un backend registrado y disponible.

No hay dependencia de network-online.target para iniciar el almacén. Un error del central no impide confirmar operaciones locales persistidas. Cerrar la interfaz no cierra la base de datos ni el sincronizador. Los reinicios de servicios recuperables están limitados; los fallos repetidos generan aviso de mantenimiento.

El perfil nuevo sucursal incluye escritorio y servicios en el mismo Debian. terminal mantiene escritorio sin aprovisionar base local; servidor mantiene la base sin escritorio. Ninguna identidad, clave de sucursal o app se crea al compilar.

## Instalar y probar en una VM existente

Ruta adicional a la ISO todavía no construida: instalar sobre una VM Debian 13 amd64 desechable ya instalada, con snapshot, consola local y sin datos reales. No se particionan discos ni se altera Windows. El script exige VM, root, Debian trixie, consola interactiva y confirmación; rechaza una instalación CulinaryOs existente.

Dentro de esa VM:

~~~bash
sudo bash scripts/install-lab.sh sucursal
~~~

Muestra los archivos que cambiará, instala dependencias oficiales, ejecuta pruebas y conserva una copia en /var/backups/culinaryos-preinstall-FECHA-PID. Cambia identidad, servicios y configuración del invitado. No es un actualizador ni un instalador probado de producción. No reinicia automáticamente. Tras revisar el resultado, reiniciar la VM y completar el alta con nombres nuevos y contraseñas propias.

Para construir una imagen candidata:

~~~bash
sudo apt-get install python3-nacl
sudo bash scripts/build.sh sucursal
~~~

También se conservan los perfiles terminal y servidor. Consulte INSTALACION.md para dependencias completas del constructor. La instalación y el arranque todavía requieren validación Linux.

## Desplegar red de sitio

Revisar IPs, pool DHCP y nombre real de interfaz. El archivo de referencia está en config/network/site-plan.json o /usr/share/culinaryos/examples/site-plan.json dentro del SO.

Desde consola administrativa del invitado, generar una carpeta nueva:

~~~bash
sudo culinaryos-site-plan --plan /usr/share/culinaryos/examples/site-plan.json \
  --node servidor-01 --interface enp1s0 --output /root/culinaryos-site-01
sudo culinaryos-runtime deploy-site /root/culinaryos-site-01
~~~

El despliegue regenera archivos desde los datos validados, comprueba nft/chrony, conserva copias, usa checkpoint NetworkManager y el aplicador de firewall con reversión. Instala nombre/hosts, Avahi y reloj; en rol servidor aprovisiona también el almacén. Exige consola y confirmación. Una activación de varios componentes no es una transacción global: si falla a mitad, revisar la copia que imprime y el estado real antes de repetir. No existe rollback completo del despliegue.

No ejecutarlo en Windows. El runtime de datos rechaza una raíz Live/overlay volátil. Se requiere Debian instalado con almacenamiento persistente para operaciones.

El perfil sucursal configura autologin de operador después del alta inicial obligatoria, para arrancar el puesto sin otro login de Linux. No crea un administrador automático. En otros perfiles gráficos puede habilitarse expresamente:

~~~bash
sudo culinaryos-runtime init --autologin
~~~

No concede sudo ni acceso directo al socket de datos. La aplicación futura debe mantener su propia autenticación. En terminal, sin ese parámetro se conserva el login normal. Para exigir login también en sucursal, el administrador puede retirar 60-culinaryos-autologin.conf durante mantenimiento. La UI registrada arranca al entrar en la sesión de operador.

## Cifrado y persistencia

Datos: /var/lib/culinaryos-data/store.sqlite. SQLite WAL con synchronous=FULL y transacciones BEGIN IMMEDIATE. Cada put confirma tanto el registro cifrado como su evento cifrado, o ninguno. El cliente debe conservar event_id en los reintentos y proporcionar expected_version; no generar otro identificador por perder una respuesta.

No se accede al archivo SQLite desde terminales ni desde una carpeta compartida de red. El único escritor de operaciones es culinaryos-data mediante IPC local. No es una base de datos expuesta por TCP.

Socket: /run/culinaryos-data/store.sock, modo 0660, grupo culinaryos-app. Usuario de servicio culinaryos-data y directorio de datos 0700. El backend real usa culinaryos-app; operador no pertenece a ese grupo. El IPC confía en el backend autorizado: permisos y roles de negocio deben resolverse allí.

No se eliminan operaciones automáticamente por antigüedad. El histórico/retención se definirá con la aplicación. Si falta espacio, una operación nueva falla y no debe mostrarse como confirmada.

## Contrato para backend y UI nativos

Instalar ejecutables reales, root y sin escritura de otros usuarios, debajo de /opt/culinaryos-app. Se rechazan órdenes de shell en vez de listas de argumentos, rutas modificables y manifiestos incompatibles.

Crear un manifiesto propio root 0644 fuera del overlay. Forma para servidor:

~~~json
{
  "version": 1,
  "mode": "server",
  "ui_argv": ["/opt/culinaryos-app/bin/ui"],
  "backend_argv": ["/opt/culinaryos-app/bin/backend"],
  "port": 8443,
  "readiness_socket": "/run/culinaryos-app/ready.sock",
  "tls_ca_file": "/etc/culinaryos/site-ca.crt",
  "credentials": {
    "tls-key": "/etc/culinaryos/secrets/app-tls.key",
    "tls-cert": "/etc/culinaryos/secrets/app-tls.crt"
  }
}
~~~

Es un formato de configuración, no ejecutables incluidos. La CA pública debe poder leerse por el servicio; la clave privada se entrega mediante CREDENTIALS_DIRECTORY y LoadCredential. Los programas se ejecutan en primer plano y sin shell intermediaria.

El backend crea el socket de readiness reservado y responde a una línea JSON:

Solicitud: {"op":"readiness","protocol":1}
Respuesta: {"ready":true,"site_id":"local-01"}

Debe responder true únicamente después de poder atender operaciones reales. El wrapper también consulta el almacén. El registro verifica TLS local contra el nombre/CA del sitio ANTES de abrir el puerto. El firewall abre sólo el puerto registrado desde la interfaz/subred operativa; no hay apertura por internet.

~~~bash
sudo culinaryos-runtime register-app /root/aplicacion-real.json
~~~

Si falla el arranque, TLS o registro, se detiene la integración y se conservan los datos. Las modificaciones del manifiesto se hacen en mantenimiento; no se reemplaza silenciosamente una app existente. Los límites iniciales de memoria/CPU del backend son provisionales y deben medirse con la app real.

Para terminal sin backend local, usar mode=terminal, ui_argv, port y tls_ca_file; no requiere backend_argv. La UI arranca y gestiona conectividad con la sucursal mediante su propia lógica. No se implementa trabajo autónomo de meseros cuando no exista acceso al servidor de sucursal.

## API de almacenamiento local

Una conexión Unix, una petición JSON terminada en LF, una respuesta y cierre. Máximo de trama 128 KiB. Carga JSON cifrada/evento como máximo 64 KiB, incluyendo la sobrecarga correspondiente; cantidades monetarias de negocio deben representarse como enteros de unidades menores.

Operaciones:

- health: estructura, sucursal y recuento de cola; no devuelve registros.
- put: record_id, version, expected_version, event_id y data.
- get: record_id; devuelve versión y data sólo al backend autorizado.

Respuestas: {"ok":true,"result":...} o {"ok":false,"error":"COS-DATA-..."}.

Códigos: CONFLICT (versión), IDEMPOTENCY (mismo ID con otro contenido), FULL (espacio), INVALID y UNAVAILABLE. No se devuelven trazas, claves o SQL interno. La API de red para meseros/cocina debe implementar autenticación/autorización antes de usar este IPC.

Existe cliente Python en dataio.Client; una app nativa de otro lenguaje puede implementar la misma trama Unix. La especificación criptográfica está en CIFRADO-V1.md; la entrega central en SINCRONIZACION-V1.md.

## Copias y recuperación

~~~bash
sudo systemctl start culinaryos-snapshot.service
sudo culinaryos-runtime backup-keys /RUTA/EXTERNA/keys-local-01.enc
~~~

El snapshot SQLite consistente queda en /var/lib/culinaryos-data/snapshots, con checksum. Exportarlo a un volumen externo protegido; una copia en el mismo disco no protege contra perderlo. No copiar sólo store.sqlite mientras está activo, omitiendo WAL.

La copia de claves usa contraseña propia, Argon2id y AEAD. No la guardar junto a la contraseña ni sólo en el mismo disco. Sin claves, los registros cifrados no son recuperables.

Para recuperar en una instalación vacía: restaurar primero los archivos de configuración de identidad correctos (site.json/branch.json), sin ejecutar init para generar otro anillo. Detener los servicios, restaurar el snapshot verificado con propietario culinaryos-data y modo 0600, recuperar las claves originales mediante restore-keys y sólo entonces iniciar. No regenerar claves sobre datos existentes. El comprobante cifrado de la base detecta un anillo equivocado al abrir.

~~~bash
sudo culinaryos-runtime restore-keys /RUTA/EXTERNA/keys-local-01.enc --site-id local-01
sudo culinaryos-runtime rotate
~~~

restore-keys rechaza sobrescribir claves existentes. rotate detiene escritores/sync, conserva claves viejas, recifra en una transacción y reinicia. No retirar claves viejas hasta validar copias y recuperación histórica. No hay retiro automático.

## Estado y pruebas pendientes

COS-DATA comprueba el almacén; COS-SYNC distingue central sin configurar o cola pendiente; COS-APP indica backend registrado; COS-UPS consulta energía real cuando NUT está configurado. No confundir cola vacía con central conectado.

Probados localmente: cifrado, persistencia, outbox, reintentos, snapshots, recuperación tras matar un proceso y HTTPS mTLS en loopback. Pendientes: socket Unix/permisos POSIX, unidades systemd/credenciales, Avahi real, instalación/arranque, backend/UI reales y UPS físico. Un SIGKILL de prueba no equivale a probar un apagón eléctrico del disco.

## Corrección de paquetes observada en la VM

El instalador de laboratorio se detuvo en apt porque policykit-1-gnome no tiene candidato en Debian 13 trixie. Se sustituyó por lxpolkit en los perfiles terminal y sucursal. El overlay proporciona lxpolkit.desktop con OnlyShowIn=XFCE para iniciar el agente en la sesión correcta y usar el mismo nombre de entrada que el paquete, evitando dos autostarts del mismo agente. No se cambia la política de permisos: polkitd y la autenticación siguen siendo necesarios.

Fuente de disponibilidad: https://packages.debian.org/trixie/lxpolkit. La captura demuestra el fallo de resolución anterior a la copia del overlay; no demuestra una instalación completa de CulinaryOS. Puede corregirse la copia extraída de la VM y volver a ejecutar install-lab.sh. La resolución real y el inicio del agente se comprobarán en esa VM; el entorno de desarrollo sigue siendo Windows.

## Recuperar un alta inicial interrumpida

En VirtualBox, Host+F2 (Ctrl derecho+F2 con la configuración habitual) cambia a otra consola. Entrar con la cuenta administradora creada durante la instalación de Debian; en el laboratorio mostrado es laboratorio. Si la versión previa no retoma el nombre automáticamente, sudo cat /var/lib/culinaryos/setup-admin permite consultar el nombre de la cuenta que quedó a medio crear. No contiene la contraseña.

Ejecutar sudo culinaryos-firstboot desde esa consola. En las versiones previas debe introducirse el mismo nombre de setup-admin. Las contraseñas no producen eco en pantalla: ni letras, ni puntos ni asteriscos. Tras el mensaje CulinaryOs preparado puede reiniciarse con sudo reboot. No crear a mano el marcador provisioned ni saltarse el alta para iniciar LightDM.

Corrección en fuentes: el asistente retoma automáticamente la cuenta registrada, permite hasta tres intentos de passwd, rechaza nombres reservados y cuentas previas sin modificar estas últimas, y explica la entrada sin eco. El getty de tty1 pasa a depender con Wants/After, para permitir un login administrativo cuando el alta falla; LightDM conserva Requires y no salta la configuración. Se ordena el alta después de preparar el teclado de consola. No se ocultan errores PAM ni se habilita root sin contraseña.

Siete escenarios de shell se prueban con passwd/getent simulados sin crear cuentas reales. No sustituyen una prueba PAM/systemd en Debian. Los cambios en el proyecto Windows no actualizan por sí solos el sistema ya instalado en la VM.

## Laboratorio con NAT y red interna

En la VM observada, enp0s3 mantiene NAT (10.0.2.15/24) y enp0s8 corresponde a CulinaryLab. El plan de la red interna debe llevar gateway: null para generar never-default=true y conservar la salida NAT. Si cambia el plan original, regenerar otra carpeta de despliegue; deploy-site utiliza el site-plan.json de esa carpeta, no una copia externa modificada después.

El validador de Chrony usa -p con las directivas como argumentos para evitar depender del permiso de lectura del temporal /run. No inicia un segundo servidor ni cambia el reloj. Conserva los errores y falla antes de aplicar la red. Su funcionamiento real con Chrony/AppArmor sigue sujeto a la prueba en Debian; véase results/LAB-VM.md. Referencia: https://manpages.debian.org/trixie/chrony/chronyd.8.en.html.

## Reparación del laboratorio ante Permission denied de Chrony

La VM informó Permission denied al comprobar chrony.conf bajo /root. Se confirma el rechazo de lectura; sin registro de auditoría no se atribuye de forma definitiva a AppArmor. El parche evita esa lectura mediante chronyd -p con directivas generadas como argumentos, manteniendo el confinamiento y sin ajustar el reloj.

El CD de datos dist/CulinaryOs-reparacion-red.iso permite ejecutar sudo bash /mnt/reparacion/reparar-red.sh desde la VM. scripts/repair-lab-network.sh es su fuente: exige root, terminal local, Debian 13, VM, perfil sucursal, enp0s3 y enp0s8, ausencia de app registrada y de perfil de sitio previo. Antes de sustituir el módulo comprueba la sintaxis y ejecuta la validación real de Chrony con el plan. Respalda deployment.py en una carpeta nueva de /root, actualiza sólo ese módulo y genera un paquete de red nuevo para local-01, servidor-01, 10.77.0.10/24 en enp0s8 y gateway null. Después llama al despliegue existente y conserva sus confirmaciones/checkpoint/reversión de firewall. No es un actualizador general ni modifica el alta de cuentas. Su ejecución real y el aprovisionamiento de datos siguen pendientes de la VM.

## Reparación del almacén por permisos de LoadCredential

La captura del journal identificó PermissionError: Las claves requieren permisos 0600 en Keyring.load sobre la copia de credenciales. El CD dist/CulinaryOs-reparacion-datos.iso contiene scripts/repair-lab-data.sh y los módulos corregidos. Desde una terminal administrativa local de la VM se monta y ejecuta reparar-datos.sh. Comprueba la clave original sin imprimirla, prueba el cargador nuevo en una unidad transitoria con User=culinaryos-data y LoadCredential antes de instalarlo, respalda securedata.py/dataio.py y el aplicador de firewall, detiene los servicios de datos/sincronización y reemplaza su código. Mantiene las claves originales (compara su checksum antes y después), no borra ni reconfigura SQLite, no cambia la red ni vuelve a desplegar el sitio. Reinicia el almacén y su timer; muestra el estado y la salud IPC. Si falla, imprime el journal. La copia anterior está en /root/culinaryos-reparacion-datos-FECHA-PID. No es un actualizador de producción.
