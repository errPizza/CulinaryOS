# Entrega sucursal → central v1

Implementada la parte emisora en syncworker.py. No hay dirección, cuenta ni certificado central de ejemplo instalados. No se contacta ningún central hasta aprovisionarlo. No se implementa el servidor receptor ni lógica de pedidos/pagos.

## Propiedades

Las operaciones se guardan localmente SIEMPRE, con internet o sin él. put cambia el registro y añade su evento dentro de una misma transacción. La confirmación local no depende de WAN. El worker es independiente de UI y backend de negocio.

Entrega al menos una vez: una respuesta perdida causa reenvío. El central debe deduplicar durablemente por (site_id,event_id), verificar que un duplicado tiene el mismo digest y devolver el mismo resultado. No se promete exactamente una vez en el transporte.

FIFO por secuencia local, independiente del reloj. Un evento pendiente bloquea posteriores; los fallos usan espera exponencial 5 s hasta 1 h. Un salto grande hacia atrás del reloj no bloquea indefinidamente una entrega. No hay borrado automático, reparación de datos ni salto silencioso de eventos rechazados. Un rechazo persistente requiere resolver el contrato/contenido con soporte.

Cada ejecución trabaja como máximo un lote de 64 eventos y un presupuesto de 20 s entre envíos; cada conexión tiene timeout y la unidad completa un límite de 45 s. El timer vuelve a intentar. Medir y ajustar capacidad con el volumen real antes de producción.

## Transporte y autenticación

HTTPS sin redirecciones, validación de CA/nombre y certificado de cliente con su clave. No se usan credenciales en URL, HTTP sin TLS ni proxies de entorno. El central debe asociar el certificado autenticado con site_id y rechazar suplantación de sucursal.

Configuración administrativa de un central REAL:

~~~json
{
  "url": "https://NOMBRE-REAL-DEL-CENTRAL/v1/events",
  "ca_file": "/etc/culinaryos/central-source/ca.crt",
  "client_certificate": "/etc/culinaryos/central-source/client.crt",
  "client_key": "/etc/culinaryos/central-source/client.key"
}
~~~

Es sólo el formato; reemplazar nombre/rutas por los reales. El certificado de cliente requiere clientAuth. La herramienta de CA admite issue --purpose client; el central decide qué autoridad y credenciales acepta.

~~~bash
sudo culinaryos-runtime central /root/central-real.json
~~~

Valida los archivos/cadena de carga local, copia materiales a rutas root 0600 y los entrega al worker con LoadCredential. Se detiene el emisor durante ese cambio. La comprobación de configuración no demuestra conexión ni aprobación del central: eso se evalúa al enviar y recibir un ACK.

## Petición

POST a la URL configurada, Content-Type application/json. Cuerpo UTF-8, con estos campos:

~~~json
{
  "protocol": "culinaryos-events-v1",
  "site_id": "IDENTIDAD-APROVISIONADA",
  "event_id": "IDENTIFICADOR-ESTABLE",
  "record_id": "IDENTIFICADOR-ESTABLE",
  "version": 1,
  "data": {}
}
~~~

data es la carga real que definirá la aplicación; no se interpreta como un pedido o pago por el SO.

Cabeceras:
- Idempotency-Key: event_id.
- X-CulinaryOs-SHA256: SHA-256 hexadecimal de los bytes exactos del cuerpo.

El receptor debe calcular el hash sobre los bytes recibidos, no reserializar JSON con otra representación. TLS autentica el canal; el digest identifica el contenido pero no sustituye autenticación.

## Confirmación

Sólo HTTP 200/201 con JSON de tamaño máximo 8192 bytes, después de persistir durablemente en el central:

~~~json
{
  "site_id": "MISMA-SUCURSAL",
  "event_id": "MISMO-EVENTO",
  "sha256": "MISMO-DIGEST",
  "status": "committed"
}
~~~

Sólo entonces el emisor marca acked en una transacción local. No elimina el registro ni el histórico del evento. Un 202, 3xx, 5xx, respuesta no JSON, otro sitio/ID/digest o conexión cortada conserva el evento.

El receptor debe persistir evento, deduplicación y cambios de negocio de manera coherente. En un reenvío no debe volver a cobrar ni repetir efectos. La resolución de conflictos entre fuentes, cambios centrales hacia sucursales, catálogos y reglas financieras pertenecen a la aplicación y aún no están definidas.

## Estado y recuperación

COS-SYNC indica central sin configurar, eventos pendientes o cola vacía. Cola vacía no demuestra que el central esté conectado. Falta de internet y central caído son estados remotos diferentes, pero ambos conservan la operación local. No reiniciar ni borrar la base por una cola pendiente.

Después de restaurar un snapshot, pueden reenviarse eventos que el central ya recibió después de la fecha de esa copia: la deduplicación central es obligatoria. No cambiar site_id al restaurar la misma sucursal.

Pruebas ejecutadas: reintentos offline, ACK incorrecto, respuesta perdida tras supuesto commit, FIFO, persistencia, HTTPS mTLS real en loopback, cliente sin certificado rechazado y redirección rechazada. El receptor de prueba es efímero y no demuestra que un central externo esté implementado o sea durable.
