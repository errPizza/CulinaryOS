# Restauración completa en otro equipo

Procedimiento y simulacro del hallazgo 3 de `MesaNexoNativo/docs/PLAN-AUDITORIA-0.3.0.md`. Objetivos: **RTO de 4 horas** y **RPO de 15 minutos**.

## Qué se respalda y qué se reaprovisiona

| Elemento | Dónde vive | Tratamiento |
|---|---|---|
| Llavero de datos (`secrets/branch.keys.json`) | `/etc/culinaryos` | Kit de recuperación. Sin él, la base no se puede leer |
| Identidad (`site.json`, `branch.json`) | `/etc/culinaryos` | Kit |
| CA local y certificado TLS, con sus llaves | `/etc/culinaryos` | Kit. Las terminales siguen confiando en el servidor sin tocarlas |
| `restaurant-connection.json` | `/etc/culinaryos` | Kit |
| Impresora, fiscal e integraciones | `/etc/culinaryos` | Kit, si existen |
| Credenciales de la central (`central-*`) | `/etc/culinaryos/secrets` | Kit, si existen |
| Base de la sucursal | PostgreSQL | `pg_dump` de `culinaryos-snapshot.service`, con su `.sha256`. Los datos van sellados con el llavero |
| Licencia | `/var/lib/culinaryos-app/license` | **Se reaprovisiona.** Pertenece al equipo |
| Identidad de hardware (TPM o huella) | El equipo | **Se reaprovisiona.** No se puede copiar |
| Cuentas de Linux y código de Setup | El sistema | Los crea la instalación nueva |
| Almacén SQLite de CulinaryOS | `/var/lib/culinaryos-data` | Se recrea vacío. En la imagen integrada sólo responde `health` |
| Red, firewall y `chrony` | El sistema | No van en el kit. `backup.py` copia esos archivos para revisarlos a mano |

## Preparar la copia en el equipo de origen

Crear el kit una vez, y otra vez cada vez que cambien certificados, integraciones, central o llavero:

```bash
sudo culinaryos-recovery-kit /media/custodia/sucursal.kit
```

La contraseña tiene de 16 a 1024 caracteres. Guarda el kit fuera del equipo y la contraseña en otro lugar. Sin contraseña no hay recuperación.

Tomar una copia de la base y sacarla del equipo, junto con su `.sha256`:

```bash
sudo systemctl start culinaryos-snapshot.service
```

La copia queda en `/var/lib/culinaryos-app/snapshots`.

Con `/etc/culinaryos/integrations/backups.json`, el backend envía una copia a R2 cada 15 minutos si hubo cambios, con su `.sha256`. Sin ese archivo, el RPO es el tiempo desde la última copia que se sacó a mano. Las filas van selladas con el llavero: en el bucket sólo se ven identificadores, tamaños y horas. Por eso la copia sola no sirve de nada sin el kit.

## Sustituir un servidor dañado

Necesitas el kit, su contraseña y la cuenta de R2. El tiempo objetivo para volver a vender es de 4 horas.

1. Instalar la ISO en el equipo nuevo y dejarlo en la red de la sucursal.
2. Descargar en un USB la copia más reciente de `SITIO/backups/`, con su `.sha256`:

   ```bash
   npx wrangler r2 object get culinary-copias-SITIO/SITIO/backups/ARCHIVO.dump --file ARCHIVO.dump --remote
   npx wrangler r2 object get culinary-copias-SITIO/SITIO/backups/ARCHIVO.dump.sha256 --file ARCHIVO.dump.sha256 --remote
   ```

3. Seguir **Restaurar**, con ese archivo como `--dump`.
4. Comprobar en la app ventas, caja e inventario, y hacer una venta de prueba.
5. Crear un kit nuevo si cambiaron certificados o llavero.

## Restaurar

1. Instalar la misma versión de la ISO, o una más nueva, y completar el primer arranque. **No crear un restaurante en Setup**: `culinaryos-restore` rechaza un equipo que ya tenga uno.
2. Copiar al equipo el kit, el `.dump` y su `.sha256`.
3. Desde la cuenta administradora:

   ```bash
   sudo culinaryos-restore --kit /media/custodia/sucursal.kit --dump /media/custodia/AAAAMMDDTHHMMSSZ.dump
   ```

4. En CulinaryAdmin, **Liberar equipo** en la licencia de la sucursal, con el motivo. Si el equipo anterior sigue encendido, se bloquea en su siguiente contacto. El panel entrega un código de activación nuevo.
5. Activar la licencia en el equipo nuevo con ese código. Hasta entonces la app muestra la pantalla de activación.
6. Si el sitio no es `local_only`, reaplicar la red y el firewall del plan de sitio. El comando sólo actualiza `/etc/hosts`.

### Qué hace el comando

1. Revisa que el equipo no tenga restaurante, abre el kit y compara el SHA-256 de la copia.
2. Carga la copia en la base temporal `culinaryos_restore`.
3. Ejecuta `MesaNexo.Api --verify-store` con el llavero del kit. Comprueba que se abran todos los registros y eventos, la cadena de auditoría y que `events + events_archive` cuadre con las transacciones.
4. Si algo falla, borra la base temporal y el equipo queda igual.

Si la sucursal publica puntos de control, el comando deja constancia en el bucket de que se restauró, porque lo publicado después de la copia ya no coincide. Sin red, la app muestra la alerta de bitácora y detiene las autorizaciones. Al volver la red, repetirlo con `MesaNexo.Api --site SITIO --accept-checkpoints "Restauración del DÍA"` como `culinaryos-app`, con el llavero en `CREDENTIALS_DIRECTORY`, y reiniciar el backend.
5. Si pasa, guarda la configuración actual en `/var/backups/culinaryos/pre-restore-*`, detiene los servicios, instala los archivos, cambia `--site` en `application.json` y reemplaza la base.
6. Si falla al instalar, vuelve a poner los archivos anteriores.

### Después de restaurar

- Lo vendido después de la copia no existe en el equipo restaurado. Conciliarlo con los cobros manuales, antes de abrir.
- Si la central ya recibió eventos posteriores a la copia, su espejo va adelante de la sucursal. Revisarlo antes de vender.

## Simulacro

Se hace en una VM nueva, con una copia realista, y se guarda la evidencia en `MesaNexoNativo/evidence/`. **Todavía no se ha hecho.**

| Paso | Inicio | Fin | Resultado |
|---|---|---|---|
| Instalar la ISO y completar el primer arranque | | | |
| `culinaryos-restore` | | | |
| Liberar y activar la licencia | | | |
| Primera venta de prueba | | | |
| **Tiempo total (objetivo: menos de 4 horas)** | | | |

Comparar contra el origen:

- [ ] Ventas y recibos
- [ ] Caja y arqueos
- [ ] Inventario
- [ ] Bitácora (`/api/audit/verify` responde `valid`)
- [ ] Facturas
- [ ] Outbox (mismos pendientes y la misma `outbox_acked_seq`)
- [ ] Una terminal existente se conecta sin reaprovisionarla
- [ ] La venta nueva llega a la central una sola vez
- [ ] Antigüedad de la copia usada (objetivo: menos de 15 minutos)
