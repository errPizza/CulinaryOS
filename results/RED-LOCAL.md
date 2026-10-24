> Registro histórico de la etapa de red. La ampliación actual está en [RUNTIME-0.2.md](RUNTIME-0.2.md).

# Preparación de red local — 14 de octubre de 2026

## Implementado

- Plan editable config/network/site-plan.json: LAN 10.77.0.0/24, servidor 10.77.0.10, culinaryos.internal y ejemplos meseros/cocina/gerente.
- Generador por nodo/interfaz de perfiles NetworkManager Ethernet/Wi-Fi, firewall, configuración chrony, hosts y diagnóstico. No activa perfiles ni modifica el anfitrión.
- Firewall de sitio con bloqueo entrante IPv4/IPv6 y puertos de aplicación vacíos. Sólo NTP local puede habilitarse en el servidor según el plan y la interfaz.
- Chrony sin fuentes públicas; servidor de hora de sitio opcional y clientes locales. La hora correcta depende de RTC/revisión administrativa.
- Diagnóstico COS-LAN separado para enlace, IP, nombre, equipo servidor, servicio futuro, TLS, router e internet. Sin sondas externas por defecto.
- CA offline cifrada por sitio, CSR propios, emisión con SAN autorizado, renovación, revocación/CRL e importación de raíz tras verificar huella.
- Manuales RED-LOCAL.md y CERTIFICADOS-LOCALES.md, con conexión posterior por rol y matriz de fallos.

## Pruebas reales

Suite completa: **70 pruebas aprobadas**.

| Grupo | Cantidad |
|---|---|
| Proyecto | 10 |
| Diagnóstico general | 16 |
| Respaldos | 10 |
| Red local y clasificación | 21 |
| Certificados y TLS | 13 |

Además, 11 comprobaciones bash -n aprobadas. Salidas completas en local-verification.json.

Entorno: Windows, Python portátil 3.13.9, Git Bash 5.3.15 y OpenSSL 3.5.7 de Git. Se realizaron firmas, validaciones, revocación por CRL y handshakes TLS reales en loopback con materiales efímeros. El handshake de confianza correcta pasó y el de nombre incorrecto fue rechazado. También se rechazaron certificados vencidos, cadena sin confianza y privilegios/SAN no autorizados del CSR.

Se ejecutó el generador para los cuatro nodos. Las carpetas vigentes para revisión están en build/site-preview-final-20261014. Se inspeccionaron JSON, reglas y perfil Wi-Fi resultantes. No hay aplicación, datos operativos, servidor web, CA de producción ni PSK distribuida.

## Sin ejecutar

No se probaron NetworkManager/checkpoint, nftables, chrony/NTP ni importación de CA en Debian; tampoco Ethernet/Wi-Fi físico, firmware, router/VLAN/AP, arranque o persistencia. No se generó una ISO. Los perfiles son propuestas que requieren ajustar interfaces/subred y validar en laboratorio antes de activar.

No se importó confianza en Windows, alteró la red anfitriona, habilitó un componente del anfitrión o publicó un puerto. El listener de la prueba TLS fue efímero, sólo loopback y sin protocolo de aplicación.

## Distinción de fallos

Internet ausente no se marca como caída del servidor. El fallo de una sonda ICMP al servidor no prueba que esté apagado. Si falta enlace/IP local, los indicadores remotos quedan desconocidos. Nombre incorrecto y TLS incorrecto se reportan aparte. Mientras application=null, no se afirma disponibilidad de una aplicación.

La infraestructura local puede funcionar sin WAN. La continuidad de operaciones frente a una caída del servidor no está implementada: corresponde a la futura aplicación y su estrategia de datos.
