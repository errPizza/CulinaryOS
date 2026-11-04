> En 0.2.0-dev se admite issue --purpose client para credenciales mTLS y existe cifrado de datos separado en CIFRADO-V1.md. La CA sigue generándose sólo durante aprovisionamiento, nunca en imágenes.

# Certificados locales sin dependencia de internet

Mecanismo OpenSSL disponible con culinaryos-pki dentro del SO, o ejecutando python3 os/overlay/usr/local/lib/culinaryos/pki.py desde las fuentes. No hay ACME, portal web de CA ni aplicación. Ninguna clave se genera durante el build.

## Certificado del restaurante

El instalador crea en el servidor una CA de 10 años (`restaurant-ca.crt`, con su llave en `secrets/`) y un certificado de 365 días (`restaurant-tls.crt`). `culinaryos-renew-tls.timer` corre a diario a las 04:00. A menos de 35 días del vencimiento, `renew-tls.py` emite otro certificado con la misma llave de servidor, lo verifica contra la CA, lo reemplaza de forma atómica y reinicia el backend. Si el equipo estaba apagado a esa hora, corre al arrancar.

Las terminales confían en la CA, así que no se tocan. Si la renovación falla, la unidad queda como fallida en el journal y la app avisa al gerente desde 30 días antes, en rojo a 7 días y para todo el equipo en ese tramo.

Para renovar a mano: `sudo systemctl start culinaryos-renew-tls.service` y revisar `journalctl -u culinaryos-renew-tls.service`.

### Rotación de la CA, año 9

El journal avisa cada día desde 365 días antes del vencimiento. La rotación no detiene a las terminales: durante un tiempo confían en las dos CA. La hace `rotate-ca.py` (en la carpeta de la aplicación, junto a `renew-tls.py`), en tres pasos que corre un administrador. Cada paso queda en `/var/lib/culinaryos/ca-rotation.json`.

1. Hacer copia de `/etc/culinaryos` y del kit de recuperación.
2. `rotate-ca.py announce`: crea la CA nueva y publica las dos en `restaurant-ca-bundle.pem`. El servidor sigue con su certificado de la CA anterior. Cada terminal la aprende de `api/trust` la siguiente vez que alguien entra, por la conexión que ya valida, y guarda las dos huellas. Sólo adopta un conjunto que conserve al menos una CA que ya conoce.
3. Esperar a que todas las terminales hayan entrado al menos una vez.
4. `rotate-ca.py switch`: emite el certificado del servidor con la CA nueva, con la misma llave, y reinicia el backend. La CA anterior sigue publicada. Si algo falla, los archivos vuelven a su lugar.
5. `rotate-ca.py retire`, no antes de 30 días después del cambio: publica sólo la CA nueva y destruye la llave de la anterior. Antes de ese plazo exige `--force`.
6. Generar un kit de recuperación nuevo.

Una terminal apagada durante toda la ventana rechaza el servidor después del cambio. Es lo correcto: se vuelve a aprovisionar desde **Conexión** con la CA nueva y su huella, como una terminal nueva. La renovación diaria sigue funcionando en cualquier paso, porque siempre usa la CA que está en `restaurant-ca.crt`.

## Separación de materiales

- Estación administrativa offline: CA por sitio, clave cifrada, base de emisión, seriales y CRL.
- Servidor: su clave privada 0600 y CSR propios. Para un servicio desatendido esa clave no lleva contraseña interactiva; se protege con propietario/permisos o credenciales systemd al integrar.
- Terminales: sólo certificado público de CA y, si el cliente lo utiliza, CRL vigente. Nunca copiarles la clave de CA o la del servidor.

No generar materiales en os/overlay, config, dist ni una ISO. Crear la CA en un volumen externo cifrado, bajo custodia administrativa. Conservar copia cifrada de TODO el directorio de CA, su base y contadores, y la contraseña separadamente. La copia genérica del SO excluye estas claves.

## 1. Crear la CA offline

En la estación administrativa con Python y OpenSSL, usando una ruta nueva:

~~~bash
culinaryos-pki init-ca --directory /media/CA-CIFRADA/local-01
culinaryos-pki fingerprint --certificate /media/CA-CIFRADA/local-01/ca.crt
~~~

OpenSSL solicita la contraseña directamente; no se pasa por argumentos, variables de entorno ni archivos del proyecto. Clave EC P-256 cifrada AES-256-CBC; raíz de diez años, CA:true, pathlen:0. La herramienta no sobrescribe una CA existente. Un alta interrumpida se inspecciona y recupera manualmente; no se borra automáticamente.

La CA sólo se necesita para emitir, renovar o revocar. La LAN no depende de que esa estación esté encendida. Una CA es una autoridad poderosa: preferir almacén de confianza limitado a la aplicación futura cuando sea posible; importar globalmente sólo en equipos administrados expresamente para este sitio.

## 2. Generar clave y CSR en el servidor

Con hora y nombre/IP ya revisados:

~~~bash
sudo culinaryos-pki request --directory /var/lib/culinaryos/tls-request-01 \
  --name culinaryos.internal --address 10.77.0.10
~~~

Copiar únicamente server.csr a la estación offline por medio administrativo. La clave server.key permanece en el servidor. La ruta de salida debe ser nueva; la herramienta no reemplaza una clave existente.

## 3. Emitir offline

~~~bash
culinaryos-pki issue --directory /media/CA-CIFRADA/local-01 \
  --csr /media/TRANSFERENCIA/server.csr \
  --output /media/TRANSFERENCIA/server-01.crt \
  --name culinaryos.internal --address 10.77.0.10 --days 90
~~~

Se solicita la contraseña de CA. El nombre/IP se autorizan explícitamente, sin copiar privilegios o SAN arbitrarios del CSR. El resultado es CA:false, serverAuth, SAN DNS e IP. Se conserva registro en la base de CA y se bloquea emisión concurrente. Una .lock residual exige verificar que no hay proceso de emisión antes de retirarla.

Volver al servidor con server-01.crt y ca.crt públicos. Verificar correspondencia clave/certificado y cadena antes de instalarlos en el servicio futuro; todavía no existe servicio TLS. Mantener permisos root 0600 para la clave y otorgar acceso sólo mediante mecanismo del servicio dedicado. No distribuir la misma clave de servidor a terminales.

## 4. Verificar y establecer confianza

Comprobar la huella SHA-256 de ca.crt por un canal administrativo independiente del archivo recibido. Comparar sitio, SAN y vigencia, y comprobar reloj:

~~~bash
openssl verify -CAfile ca.crt -purpose sslserver \
  -verify_hostname culinaryos.internal server-01.crt
openssl verify -CAfile ca.crt -verify_ip 10.77.0.10 server-01.crt
openssl x509 -in server-01.crt -noout -dates -ext subjectAltName
~~~

Para los equipos Debian administrados, después de verificar la huella fuera de banda:

~~~bash
sudo culinaryos-pki trust --certificate ca.crt --fingerprint HUELLA_SHA256_VERIFICADA
~~~

La herramienta compara huella antes de escribir, exige root en el invitado, comprueba CA, cadena y vigencia, instala sólo el certificado público y ejecuta update-ca-certificates. No ejecutarla en el anfitrión Windows. Para retirar confianza, identificar el archivo culinaryos-HUELLA.crt exacto, retirarlo en una ventana administrativa y regenerar el almacén; revisar todos los clientes afectados.

Navegadores, aplicaciones con almacenes propios y dispositivos móviles pueden requerir importación o políticas adicionales. Probar cada cliente real; no afirmar confianza por haber instalado una raíz en Debian. Nunca usar --insecure, desactivar hostname checking ni aceptar advertencias TLS como operación normal.

## 5. Renovar y revocar

Renovar antes del vencimiento, generando otra clave/CSR en una carpeta nueva y firmando con la misma CA. La vida predeterminada es 90 días y puede limitarse explícitamente entre 1 y 397. Planificar un responsable y avisos; no hay renovación automática.

Para compromiso de clave:

~~~bash
culinaryos-pki revoke --directory /media/CA-CIFRADA/local-01 \
  --certificate /media/TRANSFERENCIA/server-01.crt
culinaryos-pki crl --directory /media/CA-CIFRADA/local-01 \
  --output /media/TRANSFERENCIA/local-01-nueva.crl.pem
openssl verify -CAfile ca.crt -CRLfile local-01-nueva.crl.pem \
  -crl_check server-01.crt
~~~

El último comando debe rechazar el certificado revocado. La CRL generada tiene vigencia de siete días y debe renovarse/distribuirse localmente si se adopta su comprobación. No hay distribución de CRL ni OCSP automática. El chequeo TLS básico del diagnóstico valida cadena, nombre y fechas; **no consume CRL automáticamente**. La aplicación/cliente futuro deberá definir y probar revocación. No anunciar que un certificado revocado dejará de funcionar en todos los navegadores sin esa integración.

Compromiso de CA: retirar la raíz de todos los almacenes, crear otra CA, emitir claves/certificados nuevos y repetir la verificación fuera de banda. Perder la contraseña/clave de CA impide renovar con esa autoridad; no hay contraseña maestra de recuperación.

## Evidencia y pendientes

Pruebas reales locales con OpenSSL: CA cifrada, firma de certificado, SAN DNS/IP, nombre erróneo rechazado, cadena no confiada rechazada y CRL que rechaza un certificado revocado. Materiales de prueba efímeros, eliminados al terminar.

Importación real de confianza en Debian, permisos POSIX, negociación con servicio de aplicación, dispositivos/navegadores, relojes y distribución de CRL siguen pendientes del laboratorio. No se importó ninguna CA en Windows ni se creó un listener TLS permanente.
