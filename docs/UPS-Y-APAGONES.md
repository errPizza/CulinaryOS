# Cortes de luz, UPS USB y recuperación

Se implementó preparación/activación NUT por dispositivo y almacenamiento transaccional. No se ha conectado ni probado un UPS físico; modelo/controlador y autonomía son datos indispensables antes de habilitar apagado real.

## Almacenamiento

SQLite local usa WAL y synchronous=FULL; registro y evento se confirman juntos. Las cargas están cifradas antes de escribir. Se probó matar un proceso con una transacción sin confirmar y reabrir la base correctamente, y restaurar snapshots consistentes.

Esto no garantiza ausencia de corrupción bajo todo apagón. Dependemos de sistema de archivos, barreras, caché/controlador que respete sincronización y hardware sano. No desactivar fsync, journaling o durabilidad para acelerar cifras. No ejecutar fsck sobre un volumen montado.

La raíz Live/overlay se rechaza para almacenar operaciones. No se ha fijado un esquema de particionado ni validado ext4/LUKS en una instalación final. La ruta install-lab opera sobre un Debian persistente ya instalado en una VM; no formatea discos.

Mantener copia externa de configuración, snapshot SQLite y copia cifrada de claves, con contraseña separada. El UPS no sustituye respaldos. Tras un corte real, revisar kernel/disco/servicios e integridad antes de confirmar operaciones nuevas si hay errores.

## UPS

Paquetes nut-server/nut-client incluidos; MODE=none en la base. No hay contraseña universal ni monitor de apagado activo. apcupsd no se instala junto con NUT para controlar el mismo dispositivo.

Identificar modelo compatible en documentación de NUT y vendor/product/serial USB reales, por ejemplo con lsusb y la documentación del equipo. En VM se requiere passthrough USB expresamente configurado por su administrador; no se modifica el anfitrión automáticamente.

Preparar en el invitado una carpeta nueva root protegida:

~~~bash
sudo culinaryos-ups prepare --driver usbhid-ups \
  --vendor ID_HEX_REAL --product ID_HEX_REAL \
  --serial SERIAL_REAL --output /root/ups-real-01
~~~

ID_HEX_REAL representa cuatro dígitos hexadecimales, no texto literal. Omitir serial sólo si hay un único dispositivo identificable. El generador acepta usbhid-ups o nutdrv_qx, pero no adivina cuál corresponde al modelo. Otros controladores requieren adaptación y pruebas; no usar dummy-ups para declarar protección.

La salida contiene un secreto aleatorio propio, no se sube a Git, ISO ni una carpeta pública. upsd escucha sólo loopback; no se abre 3493 a LAN ni se anuncia mediante Avahi.

## Primera fase: comunicación, sin apagado

~~~bash
sudo culinaryos-ups install /root/ups-real-01
~~~

Exige root en Linux, confirma un solo USB con esos IDs, conserva configuraciones previas y pide PREPARAR-UPS. Inicia enumerador/controlador como servicios y upsd; no inicia upsmon. Si ya existe un monitor activo o instalación previa con copias, obliga a revisar antes de modificar.

Comprobar:

~~~bash
upsc culinaryos@localhost ups.status
upsc culinaryos@localhost battery.charge
upsc culinaryos@localhost battery.runtime
~~~

No todos los equipos ofrecen todos los indicadores. Con datos de prueba y sin uso operativo, retirar únicamente la alimentación eléctrica de entrada del UPS: debe pasar OL a OB y volver a OL al restaurarla. No retirar el cable USB para simular corte de red eléctrica.

## Segunda fase: permitir apagado

Medir el tiempo de cierre y reservar autonomía suficiente; revisar el umbral bajo del dispositivo. Con alimentación presente y estado OL sin LB/OB/FSD:

~~~bash
sudo culinaryos-ups enable-monitor
~~~

Exige HABILITAR-APAGADO-UPS. Desde entonces upsmon puede iniciar shutdown cuando el UPS informe energía crítica según su política. El cierre de systemd detiene UI/backend/sync antes del almacén, que conserva transacciones confirmadas. La integración de killpower depende de NUT, su hook Debian y las capacidades reales del UPS.

El diagnóstico COS-UPS diferencia alimentación, batería, batería crítica, falta de comunicación y monitor inactivo. Una conexión USB sin un monitor funcional no se presenta como protección de apagado.

Probar el apagado COMPLETO sólo en laboratorio autorizado con snapshot/copias y sin datos reales. No ejecutar comandos FSD o apagado del UPS sobre el anfitrión ni un equipo operativo para una demostración. Verificar que el equipo realmente se apaga con margen y que puede recuperarse al volver la energía.

## Alcance físico

Alimentar servidor, switch y AP necesarios para la LAN; de otro modo puede haber servidor encendido pero terminales desconectadas. Capacidad, batería y carga deben medirse. La recuperación de encendido al volver corriente depende de firmware/hardware y no se cambia desde este proyecto.

Queda pendiente: UPS físico, passthrough en laboratorio, arranque de los servicios NUT, permisos/udev, umbrales, autonomía, apagado real y recuperación. No se promete protección completa antes de esas pruebas.

Fuentes: https://networkupstools.org/docs/user-manual.chunked/Configuration_notes.html y https://manpages.debian.org/trixie/nut-server/upsdrvsvcctl.8.en.html.
