# Fuentes y licencias

Consulta: 2026-10-14.

| Fuente primaria | Decisión |
|---|---|
| https://www.debian.org/releases/trixie/ | 13.7 vigente; amd64; soporte ordinario hasta 2028-08-09 y LTS anunciado hasta 2030-06-30, con alcance revisable |
| https://manpages.debian.org/trixie/live-build/lb_config.1.en.html | Opciones de construcción, BIOS/UEFI, Secure Boot firmado e instalador none |
| https://manpages.debian.org/trixie/live-config-doc/live-config.7.en.html | Componentes Live y noautologin; excluir usuario/sudo predeterminados |
| https://live-team.pages.debian.net/live-manual/html/live-manual.en.html | Hooks, includes y listas; contrastar ejemplos antiguos con manpages trixie |
| https://manpages.debian.org/trixie/nftables/nft.8.en.html | inet y comprobación -c; requiere prueba real con kernel |
| https://manpages.debian.org/trixie/needrestart/needrestart.1.en.html | Revisión de kernel/procesos después de actualizar |
| https://security-tracker.debian.org/tracker/ | Vulnerabilidades por componente |
| https://www.debian.org/security/ | Avisos y alcance del soporte |

## Inventario y distribución

config/packages contiene paquetes solicitados, no instalados. config/components.json resume componentes y familias de licencia; confirmar condiciones precisas de cada versión.

El hook exporta packages.tsv (paquete, versión, arquitectura, fuente) y copyrights.tar.gz con los avisos Debian. El constructor los copia a dist. No existe todavía un inventario exacto de dependencias transitivas instaladas.

No se ha elegido licencia de redistribución para las fuentes propias en nombre del usuario. Resolverla antes de publicar y cumplir obligaciones de cada componente, incluida disponibilidad de fuentes cuando proceda. No distribuir basándose sólo en el resumen de familias de licencia.

## Verificación local

Python embeddable Windows amd64 3.13.9, licencia PSF y avisos del ZIP. Fuente:

https://www.python.org/ftp/python/3.13.9/python-3.13.9-embed-amd64.zip

SHA-256 observado localmente:

91d828c2da3a029b41699e918674a0cb379c02cf20dab9c501306885f837402a

Este hash observado no equivale a comparar con una firma publicada por Python. El ZIP y sus avisos están en tools/python, fuera del payload del SO. Git Bash 5.3.15, GPLv3+, ya instalado.

## Fuentes de red local y PKI, consulta 2026-10-14

- NetworkManager trixie: https://manpages.debian.org/trixie/network-manager/nmcli.1.en.html (checkpoint, perfiles y solicitud interactiva de secretos).
- Ajustes de red: https://networkmanager.pages.freedesktop.org/NetworkManager/NetworkManager/nm-settings-nmcli.html.
- nftables trixie: https://manpages.debian.org/trixie/nftables/nft.8.en.html.
- chrony: https://chrony-project.org/doc/4.6/chrony.conf.html (referencia local y acceso NTP limitado).
- OpenSSL CA: https://manpages.debian.org/trixie/openssl/openssl-ca.1ssl.en.html.
- OpenSSL verify: https://manpages.debian.org/trixie/openssl/openssl-verify.1ssl.en.html.
- Reserva privada .internal: https://www.icann.org/en/board-activities-and-meetings/materials/preliminary-report-special-meeting-of-the-icann-board-29-07-2024-en.

chrony es un componente previsto adicional (familia GPL-2.0; verificar copyright del paquete exacto). Se utilizó OpenSSL de Git para pruebas locales; su versión se registra en el informe de ampliación.

## Ampliación 0.2, 2026-10-15

- Cifrado y nonce: https://doc.libsodium.org/secret-key_cryptography/aead/chacha20-poly1305/xchacha20-poly1305_construction.
- Argon2: https://www.rfc-editor.org/rfc/rfc9106.html.
- WAL/durabilidad: https://www.sqlite.org/wal.html y https://www.sqlite.org/atomiccommit.html.
- Readiness y credenciales: https://manpages.debian.org/trixie/systemd/systemd.service.5.en.html.
- Avahi: https://manpages.debian.org/trixie/avahi-daemon/avahi-daemon.conf.5.en.html.
- NUT: https://manpages.debian.org/trixie/nut-server/upsdrvsvcctl.8.en.html y https://networkupstools.org/docs/user-manual.chunked/Configuration_notes.html.
- Pruebas Windows: PyNaCl 1.6.2, cffi 2.1.1, pycparser 3.11; wheels oficiales PyPI, hashes comprobados y registrados. Producción usa python3-nacl de Debian y su libsodium mantenida.
- ShellCheck 0.11.0 portátil oficial, verificado contra digest publicado por GitHub; sólo herramienta de pruebas, excluido de imágenes.

Los inventarios de herramientas y hashes observados se conservan en results/crypto-dependencies.json y results/shellcheck-tool.json. No representan el inventario instalado de una ISO aún no construida.

## Logo del proyecto

CulinaryOsIcon1.png fue proporcionado/autorizado por el usuario para identificar este sistema. Se conserva sin cambios en branding/logo.png y dentro de las composiciones SVG. El permiso de uso en este proyecto no implica una licencia abierta ni autoría de Debian. La procedencia y hash constan en branding/origin.json.
