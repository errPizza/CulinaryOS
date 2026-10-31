> En 0.2.0-dev se añadió Avahi/mDNS por interfaz, despliegue mediante culinaryos-runtime deploy-site y registro de app real para abrir su puerto. Consulte RUNTIME-SUCURSAL.md; se conserva aquí la descripción original del plan y diagnóstico.

# Servidor local y múltiples terminales

Preparación de infraestructura del SO, sin aplicación, base de datos ni servicio web. Los perfiles se generan para revisión y no cambian la red del anfitrión. La activación con NetworkManager, nftables y chrony todavía requiere prueba en Debian 13.

## Topología y funcionamiento sin internet

~~~mermaid
flowchart TD
    WAN["Internet opcional"] --- R["Router local 10.77.0.1"]
    R --- S["Switch de la red operativa"]
    S --- C["Servidor CulinaryOs 10.77.0.10 · Ethernet"]
    S --- K["Cocina · Ethernet"]
    S --- G["Gerente · Ethernet o Wi-Fi"]
    S --- AP["Punto de acceso local 10.77.0.2"]
    AP --- M["Terminales de meseros · Wi-Fi"]
~~~

El switch y el AP deben comunicar la LAN aunque falle el enlace WAN. Elegir/configurar AP que pueda operar y administrarse localmente, sin portal cautivo ni autorización de nube. El AP conecta el SSID operativo a la misma LAN del servidor. No activar aislamiento que impida llegar al servidor. Mantener aislamiento y ACL para invitados.

Servidor por Ethernet; terminales por Ethernet o Wi-Fi de infraestructura, nunca una red ad hoc improvisada. No se usa el servidor como router, puente, DHCP o punto de acceso. No hay NAT ni reenvío habilitado en CulinaryOs. La falta de router no impide comunicación entre IPs de la misma subred si switch y AP siguen funcionando; puede afectar DNS externo y salida a internet.

La arquitectura centralizada depende del servidor para la aplicación futura. Perder internet no debe interrumpir operaciones locales. Perder el servidor sí puede hacerlo: **no hay replicación, cola offline ni modo autónomo de aplicación implementado en las terminales**. El SO no inventa esas funciones.

## Direccionamiento de referencia

Revisar conflictos con las redes existentes antes de adoptar 10.77.0.0/24.

| Equipo / uso | Dirección propuesta |
|---|---|
| Red operativa | 10.77.0.0/24 |
| Router, opcional | 10.77.0.1 |
| AP de referencia | 10.77.0.2 |
| Servidor | 10.77.0.10 |
| Meseros | .101 a .119; ejemplo .101 |
| Cocina | .121 a .139; ejemplo .121 |
| Gerente | .141 a .159; ejemplo .141 |
| DHCP de equipos no inventariados | .180 a .230, si el router lo ofrece |
| Nombre del servidor | culinaryos.internal |

El archivo config/network/site-plan.json registra un ejemplo de cada rol. Para añadir terminales, agregar nodos únicos con IP fuera del pool DHCP. La herramienta rechaza IP duplicada, gateway duplicado, red pública, dirección de red/broadcast e interfaz con caracteres de control.

Se eligen IPs estáticas para no depender de DHCP durante operación. En un establecimiento con DHCP fiable también pueden usarse reservas, pero deben mantenerse y probarse en el router; este generador no las instala. Nunca asignar una IP estática dentro del pool dinámico ni clonar la misma identidad/IP en todas las terminales.

La interfaz debe indicarse por equipo después de consultar ip -br link. El generador no supone que todos los adaptadores se llamen eth0. No activar simultáneamente dos perfiles con la misma IP en cable y Wi-Fi. El hardware Wi-Fi y su firmware siguen sin validar; la imagen actual no añade firmware no libre.

## Nombre local

Se utiliza culinaryos.internal, dentro del espacio reservado para uso privado. No depende de DNS público ni de certificados públicos/ACME. Evitar .local, que se usa para mDNS.

Cada carpeta generada incluye hosts.fragment para mantener una resolución fija en /etc/hosts. También puede publicarse el registro A en el DNS local del router; si se usa, debe responder sin WAN y no reenviar .internal a DNS público. La entrada hosts fijada permite encontrar el servidor aunque falle el DNS del router.

El diagnóstico llama a getent: verifica la resolución efectiva del sistema, que puede provenir de hosts, y su correspondencia con la IP prevista. No afirma que el DNS del router respondió si lo resolvió hosts.

## Generar carpetas de despliegue

En la fuente del proyecto, sin root:

~~~bash
python3 os/overlay/usr/local/lib/culinaryos/site.py \
  --plan config/network/site-plan.json --node servidor-01 \
  --interface enp1s0 --output build/sitio/servidor-01

python3 os/overlay/usr/local/lib/culinaryos/site.py \
  --plan config/network/site-plan.json --node meseros-01 \
  --interface wlp1s0 --medium wifi --ssid CulinaryOperativa \
  --output build/sitio/meseros-01
~~~

Dentro de CulinaryOs la orden equivalente es culinaryos-site-plan y el ejemplo se conserva en /usr/share/culinaryos/examples/site-plan.json. Generar cocina y gerente con sus interfaces reales. La carpeta de salida debe ser nueva: no se sobrescriben archivos previos.

Cada carpeta contiene perfil NetworkManager, reglas nft, configuración de reloj, site.json, fragmento hosts y resumen. autoconnect=false impide activar automáticamente una propuesta sin revisar. No hay contraseñas Wi-Fi, claves privadas ni servicios de aplicación.

## Activar en el invitado, desde consola administrativa

No ejecutar estos pasos en Windows o en el constructor. Requieren un invitado ya validado con los paquetes del proyecto. Conservar copia root protegida de la configuración actual y anotar conexión activa, IP y UUID antes de cambiar.

1. Revisar el plan, nombre de interfaz, red del switch/AP y pool DHCP. Desde el invitado se puede usar arping -D -c 2 -I INTERFAZ IP_NUEVA como indicio de conflicto antes de asignar una IP; confirmar también el inventario. ARP no prueba ausencia absoluta de duplicados.
2. Validar las reglas con sudo nft --check --file RUTA/nftables.conf.
3. Instalar un perfil nuevo, con nombre propio, sin sobrescribir otro:

~~~bash
sudo install -o root -g root -m 0600 RUTA/connection.nmconnection \
  /etc/NetworkManager/system-connections/culinaryos-sitio.nmconnection
sudo nmcli connection load /etc/NetworkManager/system-connections/culinaryos-sitio.nmconnection
nmcli connection show
~~~

Si el destino ya existe, revisarlo y respaldarlo antes: no repetir install a ciegas. Con el ID mostrado en DEPLOY.txt:

~~~bash
sudo nmcli device checkpoint --timeout 90 INTERFAZ -- \
  nmcli --ask --wait 45 connection up id ID_DE_CONEXION
~~~

NetworkManager pide confirmación y revierte el checkpoint si no se confirma a tiempo. Comprobar IP y comunicación desde otra terminal antes de confirmar. La reversión real aún debe probarse en VM. El checkpoint no sustituye el respaldo de archivos ni revierte cambios en hosts, chrony o nft.

4. En Wi-Fi se solicita la clave por terminal, sin ponerla en argumentos, historial ni archivos del proyecto. La plantilla usa WPA2-RSN/CCMP y psk-flags=2 (no guardar); exige reintroducir la clave al reconectar. Para reconexión desatendida, configurar y guardar el secreto con nmtui como administrador en el perfil root 0600 de ese equipo; no distribuirlo en ISO ni backup genérico. Elegir WPA3/SAE sólo si hardware, AP y cliente lo soportan y se ha probado.
5. Revisar /etc/hosts con sudoedit, quitar registros antiguos de este nombre e incorporar hosts.fragment sin duplicados. No reemplazar el resto del archivo.
6. Aplicar el firewall revisado con sudo culinaryos-firewall-apply RUTA/nftables.conf; conservarlo sólo después de probar. El servidor permite NTP sólo desde la subred/interfaz operativa cuando local_time=true; las terminales no abren listeners.
7. Respaldar y sustituir /etc/chrony/chrony.conf por el archivo generado; validar con sudo chronyd -p -f RUTA/chrony.conf y reiniciar chrony en ventana de mantenimiento.
8. Instalar site.json como root 0644 en /etc/culinaryos/site.json y ejecutar sudo systemctl start culinaryos-health.service. El panel incorpora los indicadores COS-LAN.
9. Asignar un hostname único al equipo con sudo hostnamectl set-hostname NOMBRE_DEL_NODO y revisar su entrada local en hosts. No confundir este nombre con la identidad visible CulinaryOs ni con permisos de aplicación. No clonar identidades de equipos instalados sin validar también machine-id.
10. Tras validar todo, poner connection.autoconnect yes en el perfil propio y desactivar autoconnect de los perfiles anteriores de ESA interfaz. Reiniciar el invitado y verificar persistencia; el modo Live pierde estos cambios al reiniciar.

Nunca mostrar claves con nmcli --show-secrets en una pantalla pública. La CA y las credenciales Wi-Fi se aprovisionan por equipo/sitio, no al compilar una ISO común.

## Firewall y segmentación

input/forward drop en IPv4 e IPv6; output permite clientes locales. Se mantienen loopback, established/related, DHCP e ICMP necesarios. Sin SSH por defecto. El set application_ports se deja vacío; el generador rechaza habilitar puertos de aplicación en esta etapa.

La red funcional propuesta usa IPv4 y deja IPv6 link-local sin ruta predeterminada en la interfaz operativa. El firewall también bloquea servicios entrantes IPv6. No se declara un despliegue IPv6 global probado; añadir direccionamiento ULA, DNS AAAA y ACL explícitas si se decide usarlo.

Recomendación de infraestructura: VLAN operativa para terminales/servidor, VLAN administrativa separada y VLAN/SSID de invitados sin acceso al servidor, en ambas familias IP. El gerente que opera la aplicación es un cliente operativo; ese rol no concede acceso a sudo, router o administración de Linux. CIDR y nombre de rol no autentican personas. Las ACL del router/AP deben impedir suplantación y acceso lateral desde invitados; no basta con una regla del servidor si todos comparten capa 2.

## Reloj sin internet

chrony sustituye a systemd-timesyncd; un único daemon de hora. El servidor toma la hora de internet con NTS (time.cloudflare.com y nts.netnod.se, hora autenticada) y la sirve a la LAN con local stratum 10, que también lo mantiene como referencia cuando no hay internet; los clientes consultan sólo 10.77.0.10. El perfil base sin sitio usa las mismas fuentes NTS. Sin pools externos sin autenticar ni comandos chronyc expuestos por UDP. El servidor no fija bindaddress antes de que exista la IP para evitar una carrera de arranque; allow y el firewall restringen clientes a la LAN/interfaz prevista. El perfil base sin sitio no escucha NTP.

La licencia rechaza un reloj atrasado más de 15 minutos respecto de lo ya firmado, por eso la fuente de internet es autenticada: nadie en la LAN puede retrasar la hora con respuestas NTP falsas. NTS necesita salida a TCP 4460 y UDP 123 (el firewall permite toda la salida). nocerttimecheck 1 desactiva la revisión de fechas del certificado NTS sólo mientras el reloj no está sincronizado, para que un equipo muy atrasado pueda recuperarse. makestep 1.0 -1 permite corregir con un salto en cualquier momento, no sólo al arrancar, porque una VM reanudada desde un estado guardado vuelve con la hora vieja. Sin internet, el servidor depende de su RTC y de hora revisada por administración; una referencia local puede mantener a todos de acuerdo y aun así estar equivocada respecto de UTC.

La hora importa para vigencia TLS, logs y futuras operaciones. Verificar chronyc tracking, sources -v y fecha de cada equipo antes de emitir/importar certificados.

## Conexión futura por rol

| Rol | Conexión prevista | Responsabilidad futura de la aplicación |
|---|---|---|
| Meseros | Terminal Wi-Fi o cable → mismo servidor local por HTTPS | Autenticación individual, mesas y órdenes, permisos y manejo de desconexión |
| Cocina | Terminal preferentemente cableada → servidor local | Cola de preparación y confirmaciones autorizadas |
| Gerente | Terminal operativa → servidor local | Permisos de gestión/reportes; no permisos root por ser gerente |

Destino previsto: https://culinaryos.internal:8443, **aún inexistente**. Se definirá el puerto real al integrar, se limitará a LAN autorizada y se validará TLS con CA de sitio. No hay base de datos abierta directamente a terminales. No se necesitan nube, DNS público, licencias online, CDN o fuentes web externas para las futuras funciones locales; esa condición deberá probarse también dentro de la aplicación.

## Distinguir fallos

| Evidencia | Interpretación y acción |
|---|---|
| Sin enlace/asociación en interfaz operativa | Cable, switch, AP o Wi-Fi local. No culpar a internet ni al servidor todavía |
| IP incorrecta | Perfil o inventario/conflicto; corregir direccionamiento |
| Servidor responde; sondas externas fallan | Posible caída de internet/salida o filtrado externo. La LAN al servidor sigue disponible |
| IP del servidor accesible; nombre incorrecto | Resolución hosts/DNS local; no reiniciar servidor por ello |
| Router responde; servidor no responde | Problema específico de servidor, puerto del switch, ACL/ruta o firewall; comparar desde otra terminal |
| Una terminal falla y las demás llegan | Problema de esa terminal, enlace o AP, no evidencia de caída total del servidor |
| Todas fallan; servidor funciona en su consola | Revisar enlace del servidor, switch, VLAN y reglas antes de concluir fallo del SO |
| TCP funciona, TLS falla | CA, SAN, vigencia, reloj o configuración TLS; nunca desactivar validación |
| TLS funciona; operación futura falla | Disponibilidad/autorización/datos de aplicación; requiere su propio chequeo funcional |
| Sin sondas externas autorizadas | Internet queda sin comprobar; no se muestra como caído ni como disponible |

Los indicadores son COS-LAN-LINK, ADDRESS, SERVER, NAME, SERVICE, TLS, GATEWAY e INTERNET. No hay pruebas de servicio mientras application=null. Ping es un indicio de equipo accesible, no prueba de identidad o salud; su falta de respuesta también puede ser ICMP bloqueado.

internet_probes está vacío por defecto: no se contactan destinos públicos. Para supervisar salida, el administrador puede autorizar hasta dos IPs globales/puertos TCP de destinos estables bajo su política. Se consulta por IP para separar DNS de conectividad. Una sonda exitosa demuestra sólo ese destino; dos fallos no prueban por sí solos una caída del operador. Nunca bloquean el arranque ni convierten la ausencia de internet en fallo crítico.

## Validación pendiente en laboratorio

Probar servidor y tres terminales con switch virtual/LAN aislada; después AP real. Desconectar WAN dejando LAN, desconectar una terminal, desconectar servidor, alterar hosts, usar CA errónea, adelantar reloj, cortar NTP y reiniciar equipos. Verificar checkpoint, reglas, DHCP coexistente, IPs únicas y persistencia. No hay evidencia de Ethernet/Wi-Fi físico ni de arranque de esta configuración todavía.

## Descubrimiento implementado en 0.2

El despliegue instala Avahi por interfaz. El servidor publica servidor-restaurante.local; las terminales pueden consultar con culinaryos-discover --interface INTERFAZ. El servicio _culinaryos._tcp sólo se anuncia cuando se registra y arranca un backend real. No hay anuncio de puerto inexistente ni del servidor NUT de loopback.

La biblioteca discovery.verify_candidate valida interfaz, LAN y puerto, y exige TLS contra nombre y CA aprovisionados. Ignora TXT como fuente de confianza; una respuesta mDNS no crea confianza ni concede permisos. En dispositivos móviles la app debe usar DNS-SD de su plataforma y aplicar la misma verificación. Se conserva culinaryos.internal como identidad TLS y resolución fija de respaldo.
