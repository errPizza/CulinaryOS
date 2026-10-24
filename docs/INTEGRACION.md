> El contrato actual de backend/UI, IPC y claves está implementado y documentado en RUNTIME-SUCURSAL.md y CIFRADO-V1.md. Las tablas de este documento son requisitos de integración de la aplicación, todavía ausente.

# Integración futura

La aplicación del restaurante no está incluida. No hay base de datos, credenciales, cuentas de demostración, sockets ni puertos de aplicación abiertos.

| Área | Requisito |
|---|---|
| Identidad | Usuario dedicado sin shell ni sudo; no usar root ni operador como servicio |
| Ejecutables | Paquete versionado root, no escribible por servicio; ruta propuesta /opt/culinaryos-app |
| Datos | /var/lib/culinaryos-app, usuario del servicio y 0750; migraciones probadas |
| Configuración | /etc/culinaryos-app root; separar secretos |
| Secretos | LoadCredential o gestor evaluado; root 0600 fuera de ISO/Git; rotación y recuperación |
| Red | Inventario de listeners, localhost o interfaz explícita; nft sólo redes autorizadas |
| TLS | Nombres, confianza, renovación y caducidad probadas; declarar certificados públicos, nunca claves, al diagnóstico |
| Supervisión | Dependencias reales, disponibilidad, reinicios limitados y OnFailure sin shell root |
| Recursos | MemoryMax, TasksMax, CPUQuota y logs según mediciones |
| Confinamiento | Perfil AppArmor del ejecutable real, pruebas en laboratorio y enforce; mantener sandbox del navegador |
| Copias | Consistencia del motor de datos, protección, retención y restauración funcional |
| Actualización | Paquetes firmados, ventanas, compatibilidad y recuperación de migraciones |
| Licencias | Inventario y revisión antes de distribuir |

XSS, inyección SQL, autorización de operaciones, CSRF y seguridad de sesiones deben resolverse y probarse dentro de la aplicación futura. Firewall y endurecimiento Linux no solucionan esas vulnerabilidades. No añadir un servicio web ficticio para aparentar integración.

## Conexión de varias terminales

La infraestructura prevista está descrita en RED-LOCAL.md y CERTIFICADOS-LOCALES.md: un servidor local, terminales diferenciadas por ubicación y una CA privada por sitio. Los roles de meseros/cocina/gerente del inventario no autentican usuarios ni conceden permisos de negocio. La aplicación deberá implementar esas autorizaciones, TLS, chequeo funcional, reconexión, idempotencia y consistencia de órdenes. Internet no debe ser dependencia para operaciones locales; no se promete trabajo autónomo de las terminales cuando falte el servidor.


## Instalador de Culinary Restaurant preparado — 16 de octubre de 2026

El proyecto hermano MesaNexoNativo incluye ahora `deploy/culinaryos` y `docs/CULINARYOS-INSTALACION.md` con la integración del cliente Tauri Linux y el backend .NET real. El CD de aplicación `MesaNexoNativo/artifacts/CulinaryRestaurant-CulinaryOS-0.3.0.iso` está conectado a CulinaryOs_Test. Se compila el cliente en la VM y se utiliza register-app con readiness/TLS reales y el mismo almacén cifrado. Se conserva la política de login del sistema; el autostart existente abre la app al entrar en sesión.

El paquete fue verificado desde Windows; no se afirma todavía que la instalación, el llavero o el arranque de la app en Linux hayan pasado. El usuario ejecutará el instalador dentro del invitado. La imagen base del SO y los paquetes históricos no se sustituyen.


## Culinary Restaurant: sesión kiosco preparada (16 de octubre de 2026)

El usuario confirmó que Culinary Restaurant ya funciona y accede al restaurante en la VM CulinaryOs_Test. Se preparó una actualización incremental de kiosco, sin backend ni credenciales, en `MesaNexoNativo/artifacts/CulinaryRestaurant-CulinaryOS-0.3.0-r6.iso` (1 824 768 bytes). Todavía no está activada en el invitado.

La sesión exclusiva evita iniciar XFCE, mantiene una pantalla de carga hasta la confirmación de dibujo de la interfaz y supervisa el proceso y su heartbeat. Conserva la política existente de autenticación de Linux y la consola administrativa TTY2. El instalador compila como administrador sin root y exige una prueba gráfica real en un Xvfb/D-Bus/llavero privados antes de sustituir el ejecutable y seleccionar la sesión en LightDM. Incluye respaldo y restauración.

Validación en el anfitrión: 50 pruebas portables de instaladores, 11 pruebas web, comprobación Rust en Windows y lectura verificada de los 25 archivos de la ISO. La compilación y la prueba gráfica de Linux quedan pendientes de ejecutar el instalador en la VM. Antes de cambiar el CD deben desmontarse `/mnt/culinary-app` y `/media/cdrom0`.

Instrucciones y recuperación: [CULINARYOS-KIOSCO.md](../../MesaNexoNativo/docs/CULINARYOS-KIOSCO.md).
