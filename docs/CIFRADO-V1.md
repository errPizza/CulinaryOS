# Contrato de cifrado CulinaryOs v1

Implementado en securedata.py con PyNaCl/libsodium. No es un algoritmo inventado ni comparte claves con TLS.

## Formato

Algoritmo: XChaCha20-Poly1305 IETF. Clave aleatoria de 32 bytes; nonce CSPRNG nuevo de 24 bytes por cifrado. No reutilizar un nonce con la misma clave. Etiqueta de autenticación de 16 bytes anexada al ciphertext por la función combined de libsodium.

Sobre JSON, exactamente estos campos:

~~~json
{"v":1,"alg":"xchacha20poly1305-ietf","kid":"IDENTIFICADOR","nonce":"BASE64","ciphertext":"BASE64"}
~~~

Base64 estándar con padding. La clave no forma parte del sobre. Header autenticado: v, alg y kid. AAD es UTF-8 JSON de {"header":HEADER,"context":CONTEXTO}, sin espacios, claves ordenadas, sin NaN/Infinity. El perfil utilizado por el almacén restringe identificadores a ASCII y versiones a enteros; no usar números flotantes ni nombres de campos Unicode en ese contexto.

Contexto de registro: site_id, purpose="record", record_id y version.
Contexto de evento: los anteriores, purpose="event" y event_id.
Comprobante del anillo: site_id y purpose="key-check-v1".

El texto plano es JSON UTF-8. Cambiar sucursal, versión, tipo de contexto, header, nonce o ciphertext debe impedir descifrar. No utilizar datos antes de verificar la etiqueta. El cifrado no autentica personas ni sustituye controles de autorización.

Vector de interoperabilidad: tests/vectors/crypto-v1.json. Incluye clave/nonce conocidos exclusivamente para pruebas, los bytes de AAD y texto plano y el ciphertext esperado. Jamás usar esa clave en producción; no se incluye en el overlay ni en ISO.

## Claves

Cada sucursal genera su propio anillo al aprovisionarse. Ubicación: /etc/culinaryos/secrets/branch.keys.json, root 0600, directorio 0700. systemd entrega una copia restringida al servicio de datos mediante LoadCredential. Ni la UI ni las terminales reciben ese anillo.

Las claves no se derivan de la IP, el nombre de sucursal, contraseñas universales o certificados TLS. kid permite rotación y recuperación con claves antiguas. El recifrado se hace en transacción; las claves históricas se conservan hasta verificar snapshots y política de retención.

La base conserva metadatos de índices en claro: identificadores, versiones, contadores, timestamps y hashes de entrega. No poner datos personales en identificadores. Esto es cifrado de cargas sensibles, no cifrado completo de todas las páginas del archivo.

La clave local está protegida por permisos del SO; no por hardware en este prototipo. Un atacante que obtiene todo el disco y el anillo puede descifrar. La protección frente a robo del equipo requiere cifrado de disco/TPM o desbloqueo según el hardware; LUKS y su recuperación siguen pendientes de instalación y prueba. Tampoco protege frente a root o un backend ya comprometido con acceso autorizado a los datos.

## Copia del anillo

backup-keys cifra el anillo con una clave derivada de una contraseña propia mediante Argon2id, parámetros INTERACTIVE de libsodium, salt aleatorio de 16 bytes, y el mismo AEAD. El formato incluye v=1, kdf="argon2id-interactive", site_id, salt y envelope. AAD de copia: purpose="key-backup-v1" y site_id.

La lectura acepta sólo ese perfil, no parámetros de coste suministrados por un archivo que puedan agotar recursos. La identidad debe coincidir con la sucursal prevista; contraseña equivocada o contenido alterado se rechazan. Perder todas las copias y contraseñas hace irrecuperable el anillo.

## Contraseñas y transporte

hash_password/verify_password usan Argon2id, salt por contraseña y parámetros INTERACTIVE como base medible. Ajustar coste y límites de intentos al integrar la autenticación real. No cifrar reversiblemente contraseñas de usuarios de la app. Las cuentas de Linux siguen usando PAM/passwd de Debian; no se cambia su algoritmo desde esta biblioteca.

Los datos salen al central dentro de TLS con certificado de cliente. Se descifran en memoria del emisor para ese envío; el central debe protegerlos con sus propias claves de almacenamiento. No se entrega el anillo local al central o a las terminales. Las claves TLS, las de datos y las de respaldo tienen funciones distintas.

Para pagos, guardar sólo referencias, importes, estado y tokens necesarios. No guardar CVV/PIN ni declarar un cobro autorizado sin la confirmación válida del proveedor. El cifrado no sustituye los requisitos del procesador.

## Texto para el agente que construya la app

~~~text
Integra la app con el runtime CulinaryOs 0.2 y su IPC, sin acceso
directo al archivo SQLite ni a claves maestras.

Implementa identidad/autorización por usuario y sucursal en la API
de red. Usa event_id estable y record_id estable en los reintentos;
put debe incluir expected_version. Sólo confirma al usuario cuando
la transacción local fue aceptada. Trata conflictos y disco lleno
como errores explícitos, no como operaciones exitosas.

Para interoperar criptográficamente, sigue CIFRADO-V1.md y el vector
tests/vectors/crypto-v1.json. Usa bindings mantenidos de libsodium
para XChaCha20-Poly1305 IETF, claves de 32 bytes, nonce aleatorio
nuevo de 24 bytes y etiqueta combined de 16 bytes.
AAD/header/context deben reproducir exactamente los bytes del perfil.
No inventes primitivas, no reutilices claves TLS ni distribuyas el
anillo de datos a clientes. Prueba alteración, claves equivocadas,
contexto de otra sucursal, rotación y restauración.

La UI nativa se ejecuta sin privilegios. El backend va en primer
plano, usa CREDENTIALS_DIRECTORY para secretos y comunica readiness
real por el socket reservado. Descubrimiento mDNS sólo encuentra
candidatos: valida CA/nombre de sitio aprovisionados antes de operar.

Implementa y prueba también XSS si procede, inyecciones, sesiones,
CSRF si procede, autorizaciones, idempotencia de pagos y manejo de
desconexiones. No afirmes que el firewall o el cifrado resuelven
esas vulnerabilidades.
~~~

Fuentes: https://doc.libsodium.org/secret-key_cryptography/aead/chacha20-poly1305/xchacha20-poly1305_construction y https://www.rfc-editor.org/rfc/rfc9106.html. En Debian se usa python3-nacl mantenido por la distribución; el Python portátil de pruebas tiene versiones/hash registrados por separado.

## Credenciales de systemd y permisos POSIX

Los archivos originales de claves siguen siendo privados (0600 o 0400). La copia temporal entregada por LoadCredential puede mostrar 0440 porque systemd añade una ACL de lectura para el UID del servicio y stat muestra la máscara de ACL como bits de grupo; eso no equivale necesariamente a dar lectura al grupo propietario. El cargador normal conserva su restricción. Un cargador separado sólo acepta el anillo keyring en las unidades CulinaryOs previstas dentro de /run/credentials, comprueba padres protegidos por root, archivos/directorios regulares sin enlaces ni escritura ni acceso de otros, propietario root o UID del servicio y montaje de sólo lectura. La unidad transitoria culinaryos-credential-check se reserva para comprobar este contrato sin abrir SQLite. No se cambia el formato criptográfico, las claves ni los datos.

Referencias: https://manpages.debian.org/trixie/systemd/systemd.exec.5.en.html y https://raw.githubusercontent.com/systemd/systemd/v257/src/core/exec-credential.c (write_credential y acquire_credentials). La política del cargador se prueba con metadatos simulados; la prueba real se ejecuta en la VM con el CD de reparación.
