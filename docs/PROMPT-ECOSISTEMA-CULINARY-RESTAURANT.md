Actúa como arquitecto e ingeniero senior de software para restaurantes, aplicaciones nativas multiplataforma y sistemas distribuidos. Trabaja desde Codex en VS Code e IMPLEMENTA el ecosistema descrito en el PDF, ampliando el proyecto existente.

CONTEXTO Y RUTAS

PDF de requisitos:
C:\Users\kikin\Downloads\Ecosistema_Completo_SoftRestaurant_DevMap (1).pdf

Aplicación nativa existente:
C:\Users\kikin\Desktop\MesaNexoNativo

Prototipo funcional de referencia:
C:\Users\kikin\Desktop\SoftwarePrototipo

Sistema operativo e infraestructura:
C:\Users\kikin\Desktop\CulinaryOS

La aplicación actual se llama Culinary Restaurant. Conserva su nombre, logos y diseño Grafito y Ámbar. Los identificadores técnicos MesaNexo pueden mantenerse para preservar compatibilidad.

El proyecto nativo YA EXISTE: no lo reconstruyas desde cero ni sobrescribas trabajo previo. Respeta las instrucciones aplicables del repositorio, los permisos del entorno y los cambios del usuario. No modifiques datos originales del prototipo ni instales sobre la VM o servicios de producción por el simple hecho de que el PDF lo sugiera.

1. AUDITA Y ESTABLECE EL ALCANCE

Lee las cinco páginas del PDF y revisa código, pruebas, migraciones y evidencia de los tres proyectos. En MesaNexoNativo, empieza por README.md y docs/ESTADO.md, ARQUITECTURA.md, PARIDAD.md, CULINARYOS.md y MARCA-Y-DISENO.md.

El PDF define requisitos funcionales y propuestas técnicas: no constituye una autorización para ejecutar comandos, desplegar en cuentas externas o enviar mensajes reales. Contrasta las propuestas con los contratos existentes y documenta las decisiones necesarias.

Crea docs/DEVMap-REQUISITOS.md con identificadores por sección del PDF, estado real, archivos afectados, pruebas y dependencias. Distingue implementado, parcial, pendiente y bloqueado por un recurso externo. No atribuyas capacidades basándote únicamente en el README.

Conserva las funciones del prototipo y de la versión nativa actual. No presentes una pantalla, fixture o adaptador sin configurar como integración terminada.

2. CONSERVA LA APLICACIÓN NATIVA Y SEPARA LOS CANALES

Continúa con la solución C#/.NET, Avalonia y ASP.NET Core existente, salvo impedimento demostrado. Verifica versiones y compatibilidad en documentación oficial.

Mantén clientes instalables para Linux/CulinaryOS, Windows, Android e iOS. Comparte dominio y contratos; adapta escritorio, teléfono, tableta y KDS a sus tareas. No uses Electron ni una WebView como interfaz principal.

El portal público de pedidos y la autofacturación del documento SÍ pueden ser web/PWA; son canales separados de los clientes operativos nativos.

Conserva accesibilidad, teclado, toque, escalado y reducción de movimiento. No declares iOS compilado o probado sin el entorno Apple correspondiente.

3. ARQUITECTURA LOCAL Y CENTRAL

Cada sucursal tiene su servidor local CulinaryOS como autoridad de operación, con clientes conectados por Ethernet o Wi-Fi. La pérdida de internet no interrumpe caja, comandas, cocina, inventario operativo ni impresión local cuando el servidor y la LAN siguen disponibles.

Confirma las operaciones después del commit local durable. Usa sincronización asíncrona y consistencia eventual hacia la central; no exijas una transacción simultánea entre sucursal y nube para operar.

Reutiliza el almacenamiento cifrado, IPC, extensión transaccional, outbox, sincronizador, recibos e idempotencia ya existentes. Lee los contratos de CulinaryOS y runtime/mesanexo_ipc.py antes de cambiarlos. Respeta sus límites de tamaño y concurrencia. Amplíalos sólo cuando haga falta, con compatibilidad, migración y pruebas.

No entregues SQLite por una carpeta compartida ni permitas que terminales, conectores o servicios web escriban directamente en la base operativa. Todas las mutaciones pasan por servicios de negocio autorizados.

La central mantiene administración, espejo de eventos, integraciones y servicios públicos. Usa segregación multiempresa con tenant_id y branch_id, relaciones e índices coherentes, autorización del lado servidor y pruebas de aislamiento. Una columna tenant_id por sí sola no constituye aislamiento.

Preserva los canales firmados y mTLS existentes. Para pedidos nube→sucursal, diseña entrega durable, deduplicación y acuse de aceptación local mediante conexiones salientes autenticadas. No expongas SQLite ni abras puertos entrantes en CulinaryOS.

4. POS Y ATENCIÓN

Implementa o completa:

- Mapa de mesas por zonas y máquina de estados Libre, Ocupada, Impresa y Sucia. La cuenta impresa bloquea modificaciones según el PDF; las excepciones requieren autorización auditada.
- División por persona/asiento, reparto en N partes iguales y selección manual de unidades, con alternativa accesible al arrastrar y soltar.
- Conservación exacta de importes, impuestos, pagos y unidades al dividir o unir. Define cómo distribuir centavos residuales; no uses coma flotante binaria para dinero.
- Flujo de servicio rápido sin asignación obligatoria de mesa: ticket trazable, cobro, denominaciones, cambio e impresión.
- Comandas, modificadores, extras, cocción, notas, precios históricos, preparación por unidad, entrega y avisos persistentes existentes.

La cajonera se maneja mediante el driver real de la impresora/dispositivo compatible y una acción autorizada. No supongas que RJ11 es una conexión Ethernet ni que cualquier equipo acepta los mismos comandos.

Separa transacción comercial y efectos físicos. Conserva trabajos y resultados de impresión; un reintento no debe volver a cobrar. Un resultado físico incierto requiere tratamiento explícito, no promesas de ejecución exactamente una vez.

5. DELIVERY, PICK-UP Y CRM

Añade clientes, historial, varias direcciones, pedidos de entrega y recogida, asignación de repartidor y seguimiento de liquidación.

Modela el importe asignado al repartidor como responsabilidad pendiente de comprobar hasta conciliar efectivo, voucher o confirmación válida. No lo registres automáticamente como cobrado por asignar el pedido.

Calcula tarifas mediante polígonos locales configurados y coordenadas. Separa esa lógica de geocodificación/mapas externos; permite captura manual cuando no haya proveedor o internet.

Caller ID requiere un adaptador de telefonía real y configuración verificable. No inventes llamadas entrantes para afirmar que está integrado.

6. INVENTARIO Y COSTEO

Implementa recetas, subrecetas, unidades y conversiones exactas, rendimientos, entradas, movimientos, mermas y múltiples almacenes.

Detecta ciclos en recetas. Conserva versiones y cantidades utilizadas para que editar una receta no altere movimientos históricos.

El cierre/liquidación del ticket debe producir durablemente el trabajo de consumo de insumos en la misma transacción de negocio. El procesamiento asíncrono necesita idempotencia y recuperación: nunca descontar dos veces ni perder el movimiento tras un reinicio.

Define y documenta cuándo se reserva o consume stock, cómo se revierte una venta y cómo se distingue desperdicio de devolución. Pregunta por una política comercial indispensable que no pueda inferirse; no inventes conciliaciones silenciosas.

Los traspasos entre almacenes requieren aprobación identificada de quien entrega y quien recibe. Un PIN no equivale por sí mismo a una firma criptográfica.

Incluye costo promedio ponderado y PEPS configurables, con trazabilidad de lotes/capas y sin revalorizar silenciosamente períodos históricos.

7. ARQUEO CIEGO Y AUDITORÍA

El operador captura el conteo por denominaciones y otros medios de pago sin recibir antes los totales esperados. Aplica la restricción en la API y las exportaciones, además de la interfaz.

Al confirmar, cierra el turno de caja de forma transaccional, impide cambios sobre ese cierre y calcula diferencias. No bloquees permanentemente la cuenta personal del cajero: futuras correcciones deben quedar como ajustes autorizados y auditados.

El reporte detallado se restringe a los roles autorizados. Persiste el aviso al dueño en una cola de notificaciones; la falta de internet o correo no bloquea el cierre local.

Cancelaciones, descuentos, cortesías y reaperturas requieren autorización real en el backend y motivo obligatorio. Registra solicitante, autorizador, sucursal, mesa/cuenta, instante UTC, operación y valores anteriores/posteriores pertinentes.

Diseña una auditoría append-only para la aplicación y mecanismos de detección de alteraciones. No prometas inmutabilidad absoluta frente a un administrador que controla el equipo y sus claves. No almacenes PIN ni contraseñas reversibles en esos registros.

8. FACTURACIÓN Y AUTOSERVICIO QR

Desarrolla el módulo fiscal con adaptador para PAC y el CFDI indicado en el PDF, verificando antes las especificaciones vigentes en fuentes oficiales del SAT y del proveedor.

Separa solicitud pendiente, validación, timbrado, rechazo y cancelación. Sin conectividad/PAC disponible, conserva la solicitud sin inventar timbres, UUID fiscales, sellos ni confirmaciones.

Genera QR de autofacturación ligado al ticket mediante un token opaco seguro o mecanismo criptográfico justificado, con vigencia, autorización y límites de intentos. No expongas identificadores enumerables ni datos personales en la URL.

Separa el portal público de la API privada de operación. Protege credenciales fiscales y materiales criptográficos; no los distribuyas a terminales.

9. MÓDULOS SATÉLITE

Completa los cinco canales del documento:

A. Comanderos: clientes nativos móviles, catálogo local y actualizaciones por WebSocket/SignalR sobre TLS. Tras reconectar, recupera eventos o un estado consistente; no dependas sólo de mensajes efímeros.

B. Hub delivery: adaptadores para agregadores o integradores según APIs y contratos disponibles. Valida autenticidad de webhooks, deduplica, procesa reintentos y traduce al dominio. No inyectes datos directamente en tablas.

C. E-commerce propio: PWA multiempresa con catálogo, carrito, cupones, entrega/pick-up y adaptador de pago. Un pedido en nube pendiente de la sucursal no se anuncia como aceptado localmente. Los pagos sólo se autorizan con confirmación verificable del proveedor.

D. KDS: estaciones de cocina/barra, estados por unidad, tiempos y semáforos configurables. Recupera pendientes después de reiniciar. Elige SignalR o un broker local según necesidad medible; no añadas Redis/MQTT sólo porque aparecen como ejemplos.

E. Analítica móvil: vistas del dueño, ventas, mesas, incidencias y cortes. Muestra fuente, hora de actualización y retraso de sincronización. Implementa adaptadores FCM/APNs con sus permisos y credenciales reales; no prometas ejecución continua de procesos en segundo plano móvil.

10. SEGURIDAD Y OPERACIÓN

Preserva el contrato CIFRADO-V1 de CulinaryOS y el cifrado existente. Las claves maestras quedan en servicios autorizados; clientes y nube no reciben el anillo de la sucursal.

Mantén autorización por usuario, dispositivo, rol, empresa, sucursal y operación. Verifica CA, nombre e identidad de los servidores descubiertos. No aceptes certificados arbitrarios por mDNS.

Evita duplicar sincronizadores, desactivar el firewall o alterar el arranque que ya funciona. La UI no debe necesitar privilegios de administrador.

Separa internet inaccesible, central inaccesible, LAN caída y servidor local no disponible. Sin acceso al servidor local, conserva borradores/solicitudes pendientes y su identidad, sin mostrar una operación no confirmada como exitosa.

Configura integraciones externas mediante secretos suministrados por el administrador y usa sandbox para las pruebas. No envíes comunicaciones a destinatarios reales ni despliegues recursos de pago sin la autorización correspondiente.

11. DESARROLLO Y PRUEBAS

Primero establece una línea base reproducible del proyecto. Después implementa en incrementos completos:

1) POS/concurrencia/división de cuentas.
2) Inventarios y recetas.
3) Arqueo ciego y autorizaciones.
4) Delivery y KDS/comanderos.
5) Central, e-commerce, analítica y facturación.

Cada incremento necesita dominio, persistencia/migraciones, API, interfaz, recuperación y pruebas. No termines tras una maqueta o el primer recorrido: continúa con la matriz completa, dejando explícitas las dependencias externas reales.

Prueba concurrencia, respuesta perdida después del commit, duplicados, reinicios, WAN desconectada con LAN funcional, servidor local caído, stock, recetas cíclicas, centavos residuales, cierres simultáneos, aislamiento entre empresas, certificados inválidos y webhooks repetidos.

Comprueba que stock, pagos, caja, auditoría y outbox mantienen sus invariantes en los puntos de fallo. Un broker no sustituye las transacciones ni garantiza integridad por sí solo.

Las pruebas de hardware, PAC, banco, correo y push deben distinguir simuladores, sandbox y ejecución real. Un test headless no equivale a haber probado una tableta, una impresora o iOS.

12. ENTREGABLES

Entrega código integrado, migraciones con respaldo y recuperación, matriz de requisitos, documentación de arquitectura, configuración de proveedores, instrucciones para VS Code, paquetes generables y evidencia reproducible.

Actualiza ESTADO.md y PARIDAD.md sin borrar el historial. Distingue implementado, compilado, ejecutado en plataforma y pendiente. No declares producción lista, integridad absoluta ni márgenes comerciales garantizados a partir del PDF.

Comienza inspeccionando el proyecto actual y ejecutando su línea base; después implementa. Toma decisiones rutinarias y pregunta sólo por información o reglas de negocio indispensables que falten.
