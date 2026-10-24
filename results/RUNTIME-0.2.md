# Verificación de CulinaryOs 0.2.0-dev

Fecha: 15 de octubre de 2026. Entorno: Windows, Python 3.13.9 portable, Git Bash y OpenSSL de Git.

## Implementado en fuentes

- Perfil sucursal con servicios de fondo y escritorio; lanzamiento de backend/UI reales mediante registro, readiness y unidades systemd separadas. No se incluye la aplicación del restaurante.
- Almacén SQLite local con WAL/FULL, cargas cifradas XChaCha20-Poly1305, control de versiones, outbox atómica, instantáneas consistentes y rotación de claves por sucursal. IPC exclusivamente Unix.
- Sincronizador saliente por mTLS, reintentos e idempotencia; retiene eventos hasta recibir ACK válido. No se ha configurado un central real; el receptor deberá cumplir SINCRONIZACION-V1.md.
- Planes de IP estable, despliegue con comprobaciones y recuperación parcial, firewall LAN, certificados locales, Avahi por interfaz y descubrimiento con verificación TLS. No se aplicó ninguna red al anfitrión Windows.
- Preparación de NUT para USB con configuración y habilitación del monitor en dos pasos. Sin monitor activo por defecto.
- Diagnóstico separado de LAN, servidor local y central/internet. Una cola vacía no se presenta como prueba de conexión al central.
- Documentación para la aplicación futura, aprovisionamiento, claves, copias y recuperación.

## Resultado ejecutado

La última ejecución de scripts/verify.ps1 registró 125 pruebas: **124 aprobadas y 1 omitida** porque AF_UNIX no existe en el Python de Windows disponible. Las ocho suites terminaron con código 0. Las 15 comprobaciones Bash y ShellCheck 0.11.0 finalizaron sin errores ni observaciones. Detalle: [local-verification.json](local-verification.json).

Se probaron cifrado, manipulación de cargas, aislamiento de claves/sucursal, persistencia y rollback SQLite, terminación de un proceso con transacción abierta, instantáneas, reintentos, idempotencia y un servidor HTTPS efímero con mTLS. Ese servidor se creó sólo en las pruebas; no es un backend de restaurante ni un central instalado. La terminación de proceso no equivale a un apagón físico.

Inventarios con versiones, origen y hashes de las herramientas portátiles: [crypto-dependencies.json](crypto-dependencies.json) y [shellcheck-tool.json](shellcheck-tool.json). Se excluyen del paquete de fuentes y de las imágenes. Las dependencias de Debian se instalan desde sus repositorios según los scripts.

## Pendiente de entorno o integración real

No se generó una ISO ni se arrancó Debian. No había una distribución WSL utilizable ni herramientas de VM disponibles en PATH; véase [environment-probe.json](environment-probe.json). No se habilitaron WSL/Hyper-V ni se alteraron discos o el arranque del anfitrión.

Quedan por ejecutar en Debian: systemd y LoadCredential, permisos/IPC Unix, nftables, NetworkManager, Avahi/D-Bus, inicio de sesión y GUI, el instalador de laboratorio y el arranque BIOS/UEFI. También requieren datos/equipo reales el registro de la aplicación, URL/credenciales y receptor central, UPS USB y pruebas de pérdida de alimentación. Los archivos de referencia de red no están aplicados.

Las claves operativas son propias de cada sucursal y no vienen en las fuentes. El cifrado de cargas no sustituye el cifrado completo del disco; metadatos técnicos permanecen visibles. Las operaciones de negocio, autenticación/roles, pagos y coherencia entre varios registros pertenecen a la aplicación futura. La sincronización implementada es saliente; no incluye replicación descendente ni resolución de conflictos de negocio.

## Entrega

[Runtime e instalación de laboratorio](../docs/RUNTIME-SUCURSAL.md), [cifrado y contrato para el agente de la app](../docs/CIFRADO-V1.md), [central](../docs/SINCRONIZACION-V1.md), [UPS](../docs/UPS-Y-APAGONES.md) y [pendientes](../docs/PENDIENTES.md).

El archivo dist/CulinaryOs-0.2.0-dev-source.zip contiene fuentes, documentación, pruebas y este informe; **no es una ISO ni incluye la aplicación**. El vector criptográfico es público, exclusivo de pruebas y no se instala en el SO. results/source-SHA256SUMS permite comprobar las fuentes.

## Identidad visual añadida

Logo original integrado en Plymouth, acceso LightDM, fondo XFCE, bienvenida e iconos. Original conservado byte por byte; PNG y fondos SVG comprobados. La suite completa continúa con 124 pruebas aprobadas, una omitida por AF_UNIX, 15 comprobaciones Bash y ShellCheck sin observaciones. Evidencia: [branding-resources.json](branding-resources.json); detalles: [IDENTIDAD-VISUAL.md](../docs/IDENTIDAD-VISUAL.md). La visualización y el arranque reales siguen pendientes de Linux.

## Corrección de paquetes observada en la VM

El instalador de laboratorio se detuvo en apt porque policykit-1-gnome no tiene candidato en Debian 13 trixie. Se sustituyó por lxpolkit en los perfiles terminal y sucursal. El overlay proporciona lxpolkit.desktop con OnlyShowIn=XFCE para iniciar el agente en la sesión correcta y usar el mismo nombre de entrada que el paquete, evitando dos autostarts del mismo agente. No se cambia la política de permisos: polkitd y la autenticación siguen siendo necesarios.

Fuente de disponibilidad: https://packages.debian.org/trixie/lxpolkit. La captura demuestra el fallo de resolución anterior a la copia del overlay; no demuestra una instalación completa de CulinaryOS. Puede corregirse la copia extraída de la VM y volver a ejecutar install-lab.sh. La resolución real y el inicio del agente se comprobarán en esa VM; el entorno de desarrollo sigue siendo Windows.

## Seguimiento del primer arranque

El usuario ya instaló Debian y ejecutó el instalador de laboratorio. El primer arranque alcanzó el alta de cuentas, que falló por confirmación de contraseña; recuperación indicada y corrección preparada. Véase [LAB-VM.md](LAB-VM.md). La suite local actual registra 131 pruebas aprobadas y una omitida por AF_UNIX, tras añadir siete escenarios del asistente. El estado de entorno sin Linux de este informe corresponde al entorno de herramientas del agente; la VM del usuario es una evidencia separada.

## Comprobaci?n previa de Chrony

Se conserva el motivo del fallo de Chrony y se valida la configuraci?n mediante directivas en argv, sin depender de un archivo temporal en /run ni desactivar AppArmor. Tres escenarios a?adidos: validaci?n sin archivo, rechazo con mensaje y l?mite de tiempo/configuraci?n vac?a. La suite actual suma 134 aprobaciones y una omisi?n de AF_UNIX (135 pruebas), m?s 15 comprobaciones Bash y ShellCheck sin observaciones. Causa exacta del fallo en la VM y aplicaci?n all? de la correcci?n todav?a pendientes; v?ase LAB-VM.md.

## CD de reparaci?n de red

Se prepar? CulinaryOs-reparacion-red.iso, CD de datos sin arranque, con el m?dulo de despliegue corregido, plan de laboratorio sin gateway y script atendido. Contenido ISO le?do y comparado byte por byte. El script rechaza Windows, exige el entorno de laboratorio y comprueba Chrony realmente antes de instalar el parche; su ejecuci?n Linux sigue pendiente. Suite local: 134 aprobadas, una omitida, 16 comprobaciones Bash y ShellCheck sin observaciones. V?ase network-repair.json.

## Credenciales del almac?n y CD de reparaci?n

El journal real identifica la validaci?n 0600 de la copia LoadCredential como fallo de arranque. Se conserva el cargador de archivos privados y se a?ade uno espec?fico para credenciales de las unidades previstas, en montaje protegido de s?lo lectura. Nueve escenarios de regresi?n cubren m?scara ACL, rechazo de escritura/otros, rutas, propietarios y selecci?n del cargador. Se prepara un CD de datos que prueba el contrato con systemd-run y el UID real antes de sustituir c?digo, sin regenerar claves ni volver a desplegar la red. Prueba real y arranque exitoso siguen pendientes de la VM. Suite local: 143 aprobadas, una omitida, 17 comprobaciones Bash y ShellCheck sin observaciones. V?ase data-repair.json.

## Pantalla de arranque animada

Se añadió actividad visual al tema Plymouth: ocho puntos dorados bajo el logo original, texto según arranque/reinicio/apagado y callbacks para mensajes y preguntas. El fragmento GRUB conserva los argumentos existentes y añade quiet splash sin duplicarlos. El hook actualiza el GRUB instalado si existe; live-build usa sus argumentos propios. El CD de datos CulinaryOs-pantalla-arranque.iso permite aplicar la actualización sin repetir el despliegue del sitio. Incluye copia anterior y restaurador; comprueba recursos en initramfs después de regenerarlo. Su prueba gráfica en la VM sigue pendiente.

Validación local: 145 pruebas, 144 aprobadas y una omitida por AF_UNIX en Windows; 19 scripts con sintaxis Bash válida y ShellCheck sin observaciones. Ocho archivos del CD comparados byte a byte contra la imagen Joliet y sus sumas verificadas. Detalles: results/boot-splash.json y docs/IDENTIDAD-VISUAL.md. La evidencia reciente de la VM (almacén listo, cero unidades fallidas después del reinicio e IP LAN persistente) está en results/LAB-VM.md.

## Arranque normal con pantallas intermedias ocultas

El CD CulinaryOs-arranque-limpio.iso incluye todos los recursos de Plymouth y añade menú GRUB oculto con ventana de un segundo para Esc/F4; loglevel=3 y systemd.show_status=error, respetando valores explícitos existentes; ajuste acotado de quiet_boot en el generador Debian; omisión de getty tty1 después del alta en perfiles gráficos y habilitación de tty2. Mantiene entradas de recuperación y registros. El actualizador respalda los nuevos destinos y su restaurador recupera también la habilitación previa de tty2. El aviso vmwgfx se investigó en la fuente oficial de VirtualBox; no se cambia ni bloquea el controlador.

Validación local: 147 pruebas, 146 aprobadas y una omisión AF_UNIX; 19 scripts con sintaxis Bash válida y ShellCheck sin observaciones. Diez archivos del CD comparados con su imagen Joliet y sumas verificadas. No se ejecutó el arranque ni systemd desde Windows. La prueba visual del paquete en la VM del usuario está pendiente. Detalles en results/quiet-boot.json y docs/IDENTIDAD-VISUAL.md.
