# Technical Debt

> Temporary and self-liquidating file. It is deleted when 100% of the tasks are completed.

| Symbol | Meaning |
|---|---|
| 🚨 | Critical block / urgent technical debt |

---

## [DT-001] ~~OIDC Identity Propagation Trust~~ — Cerrado

**Severity:** ~~Medium~~ — Eliminado
**Status:** ❌ Cerrado. Se intentó token exchange con 6 combinaciones grant_type x token_type, todas fallaron con `invalid_request`. El pipeline funciona con API key estática. Los secrets OIDC (OCI_DOMAIN_URL, OCI_OAUTH_CLIENT_ID, OCI_OAUTH_CLIENT_SECRET) fueron eliminados de GitHub Secrets. Si se requiere OIDC en el futuro, habrá que rehacer la configuración desde OCI Console.

---

## [DT-002] Estrategia de autenticación para URLs de gestión expuestas por Tailscale Funnel

**Severity:** Low
**Origin:** planned (multi-service Funnel)
**Description:** Tailscale Funnel + Caddy expone servicios autogestionados vía HTTPS público en `https://toolset-oci-1.tail2d4c18.ts.net/`. Actualmente no hay autenticación en la capa de Funnel/Caddy. Algunas URLs permiten gestión (Infisical, Hindsight CP, Hermes en futuro) y otras son solo de observabilidad/MCP (health, API, MCP). Una vez Hermes esté operativo, se debe implementar una estrategia de auth que:

- Proteja las URLs de gestión (Infisical, Hindsight CP, Hermes) con autenticación.
- Mantenga públicas las URLs de observabilidad (health, API REST) y MCP (necesario para que harnesses se conecten sin auth).
- Opciones: Caddy `basicauth` (simple, global por path), forward auth con Infisical (más integrado), o `HINDSIGHT_CP_ACCESS_KEY` (específico de Hindsight).

**Remediation plan:** Definir e implementar post-TASK-006 (Hermes operativo).
**Status:** 🚨 **Reabierto (2026-07-23).** La resolución que registraba este ítem ya no existe.

- *Lo que decía (2026-06-26):* "✅ Parcialmente resuelto. Caddyfile actualizado con `basicauth` para rutas de gestión de Hindsight CP (`/dashboard`, `/banks/*`, `/api/banks/*`) usando `{$FUNNEL_AUTH_USER}` y `{$FUNNEL_AUTH_PASSWORD}`".
- *Realidad medida:* el `basicauth` fue removido del Caddyfile en `1de879b` («remove Hindsight basicauth, add URL verification como paso obligatorio de deploy») y `db17f50` («Caddyfile sin basicauth»), **sin actualizar este ítem ni [DEV.CR.18]**. Hoy el Caddyfile no contiene ninguna directiva `basicauth`; el bloque de Hindsight CP está anotado explícitamente como «no auth». `/dashboard` → 200 y `/api/banks` → 200 desde internet.
- *Además:* `docker-compose.yml` sigue declarando `FUNNEL_AUTH_USER` y `FUNNEL_AUTH_PASSWORD` al contenedor de Caddy, variables que **ninguna directiva consume**. Parecen dar una protección que no existe.
- *Consecuencia:* la gestión de los bancos de memoria de Hindsight es pública para cualquiera con la URL del Funnel.

**Remediation plan:** decisión del usuario, no automatizable. El basicauth se quitó a propósito porque rompía a los harnesses MCP, así que reponerlo global volvería a romperlos. La forma correcta es proteger solo las rutas de gestión (`/dashboard`, `/banks/*`, `/api/banks*`, `/api/profile/*`) dejando MCP y health abiertos, y **verificar el resultado con curl en el mismo deploy** para que no vuelva a divergir en silencio.

---

## [DT-003] Backup de volúmenes Docker de Hindsight (pg0)

**Severity:** Low
**Origin:** manual (session closure)
**Description:** Hindsight self-hosted almacena su banco de memoria en el volumen Docker `hindsight_data` (pg0 embebido en `/home/hindsight/.pg0`). Si la instancia OCI se redeploya o el contenedor se destruye con `docker compose down -v`, todos los datos de memoria se pierden. Actualmente no hay backup ni export programado.

**Remediation plan:** Implementar backup periódico vía API `document-transfer` y subir a OCI Object Storage. Cron diario o pre-deploy en el keepalive script.
**Status:** ☐ Pending

---

## [DT-004] Infisical no arranca — migración KMS `Invalid key length`

**Severity:** Medium
**Origin:** session 2026-06-22 (CI/CD loop)
**Description:** Infisical (todas las versiones probadas: latest, v0.161.4, v0.160.0, v0.158.0) falla durante migración `20250210101840_webhook-to-kms.mjs` con `ERR_CRYPTO_INVALID_KEYLEN`. Probados múltiples formatos de ENCRYPTION_KEY (hex 256-bit, hex 128-bit, base64 32-byte). Persiste con DB limpia (PostgreSQL y SQLite). KMS genera root key que no matchea el cipher esperado.

**Remediation plan:** Corregir ENCRYPTION_KEY: usar `openssl rand -hex 16` (32 hex chars = 32 UTF-8 bytes) en lugar de base64. La función `$getBasicEncryptionKey()` en Infisical lee ENCRYPTION_KEY como UTF-8 buffer. Base64 produce 44+ bytes → ERR_CRYPTO_INVALID_KEYLEN. Hex 32 chars = 32 bytes = AES-256-GCM válido. También se corrigió DB_CONNECTION_URI para compatibilidad con Docker Compose v5.1.4 (usar variable simple en .env en lugar de multi-sustitución inline).
**Status:** ✅ Resolved (2026-06-22)

---

## [DT-005] CI/CD Pipeline Hardening — Concurrencia, Rollback, Sync Bidireccional

**Severity:** Critical (was blocking)
**Origin:** audit (2026-06-26)
**Description:** El pipeline CI/CD carecía de control de concurrencia (push paralelos corrompían remote state), rollback automático (fallo post-deploy dejaba servicios caídos) y sync bidireccional de secrets (reverse sync Infisical→GitHub no funcional). Además, inline Python en SSH heredocs causaba bugs de quoting.
**Remediation plan:** Se implementaron:
- `concurrency.group` en deploy.yml
- `workflow_dispatch` con 4 skip-inputs
- `scripts/sync-infisical-secrets.py` standalone (push|verify|pull)
- Rollback: marker del compose anterior + restore on failure (service + preflight)
- Preflight integrado en deploy.sh con auto-revert
- `FUNNEL_DOMAIN` como GitHub variable, 36 referencias parametrizadas
- Docker layer caching con `docker/build-push-action@v6` + cache GHA
**Status:** ✅ Resolved (2026-06-26)

---

## [DT-006] Infisical Agent — Inyección de Secrets sin .env

**Severity:** Low
**Origin:** TODO.md EPIC-003
**Description:** Infisical CLI está disponible dentro del contenedor `infisical` y soporta `infisical run --command=...` que inyecta secrets como env vars directo al proceso sin archivo .env intermedio. Sin embargo, migrar los servicios existentes (docker compose) a este modelo requiere cambiar la entrad point de cada contenedor para usar `infisical run -- docker compose up` en lugar de leer el .env. Esto añade dependencia del contenedor Infisical y complica el startup sequence. Actualmente el .env se maneja correctamente via GitHub Secrets → deploy.sh → /opt/toolset/.env → docker compose.
**Status:** ☐ Pending — bajo prioridad. El modelo actual funciona y cumple MASTER-SPEC §4.1 (secrets via Infisical). El .env se escribe desde CI/CD, no es persistente en repo.

---

## [DT-007] Health Check autónomo — conectar con Hermes Agent

**Severity:** Low
**Origin:** Post-audit 2026-06-27
**Description:** El health check actual (`.github/workflows/healthcheck.yml`) corre cada 5 min desde GitHub Actions y verifica URLs. Si falla, crea un issue en el repo (notificación por correo). Pero no hay integración con Hermes Agent: no puede iniciar un deploy de recuperación, no reporta el estado a Hermes, y no hay un dashboard de uptime.
**Remediation plan:** En futura iteración, el health check debe notificar a Hermes vía WhatsApp (en lugar de/issues/además del issue de GitHub). Hermes podría gatillar un auto-deploy si detecta caída. Idealmente, el health check corre desde el propio Hermes (cron dentro del VPS) para no depender de GitHub Actions.
**Status:** ☐ Pending

---

## [DT-008] deploy.sh chown -R recursivo sobre /home/opc/.hermes/ rompe con immutable flags en profiles

**Severity:** Medium
**Origin:** session 2026-07-09 (pipeline failure)
**Description:** El paso "Writing Hermes .env" en deploy.sh ejecuta `sudo chown -R opc:opc ${HERMES_DIR}` que recorre TODO `/home/opc/.hermes/`. Los perfiles tenant como `tito` tienen `chattr +i` en sus `config.yaml`, lo que hace que `chown` falle con "Operation not permitted". Actualmente se mitiga con `2>/dev/null || true`, pero la solución correcta es cambiar a `sudo chown opc:opc ${HERMES_DIR}/.env` (solo el archivo recién escrito, no el directorio completo).
**Status:** 🚨 Pending — mitigado con || true, no corregido estructuralmente.

---

## [DT-009] Workspace repo (/home/opc/workspace/toolset) puede revertir archivos de infraestructura vía hermes-sync

**Severity:** Low
**Origin:** session 2026-07-09 (compute.tf revertido por hermes-sync)
**Description:** `sync-hermes-to-repo.sh` opera sobre `/home/opc/workspace/toolset`, un clon separado de `/opt/toolset-repo`. Si este workspace repo tiene archivos stale en staging (ej: `git add .` previo), `git commit` los incluye aunque el script solo haga `git add` de archivos específicos. El fix `git reset HEAD -- .` mitiga, pero el riesgo persiste si el workspace no se mantiene en sync con origin/main.
**Status:** ☐ Pending — mitigado con git reset HEAD en sync script, no eliminado estructuralmente.

---

## [DT-010] deploy.sh tiene set -e pero múltiples comandos sin || true

**Severity:** Medium
**Origin:** session 2026-07-09 (pipeline failure)
**Description:** deploy.sh arranca con `set -euo pipefail`, por lo que cualquier comando con salida no-cero rompe el pipeline. Comandos que pueden fallar por razones no críticas (permisos, immutable flags, registry auth) no siempre tienen `|| true`. Ejemplos: `sudo chattr -i` en perfiles tenant, `sudo docker compose pull`, `sudo chown -R` sobre directorios con immutable. Cada nuevo comando frágil añadido al deploy.sh es un riesgo de pipeline break.
**Status:** ☐ Pending — revisión manual de cada comando en deploy.sh para evaluar tolerancia a fallos.

---

## [DT-011] kb-mcp expuesto sin autenticación y sin aislamiento entre KB

**Severity:** Medium
**Origin:** session 2026-07-23 (publicación de KBs por MCP, MASTER-SPEC §7.2)
**Description:** `kb-mcp` sirve las bases de conocimiento en `https://<funnel>/kb/<slug>/mcp` sin ninguna capa de autorización. Consecuencias:

- Cualquiera con la URL puede leer **cualquier** KB publicada. Hoy conviven `traza-ambiental` (compartida con un colega externo) y `personal` (contenido privado del autor) en el mismo endpoint, **sin aislamiento entre ellas**: quien conoce una ruta puede probar la otra, y los slugs son predecibles por diseño.
- Tensiona MASTER-SPEC §4.2 («los puertos no deben exponerse públicamente»), aunque el tráfico curse por Funnel como el resto de los servicios.

El diseño ya contempla la solución: la ruta lleva el nombre del repositorio precisamente para que la autorización se aplique por KB sin mezclarse con el enrutamiento.

**Remediation plan:** capa de tokens por KB sobre `/kb/<slug>` en Caddy (un token por consumidor, revocable), o forward-auth. Mientras no exista, no publicar en este servidor ninguna KB cuyo contenido no se pueda asumir legible por quien tenga la URL.
**Status:** ☐ Pending. Conocido y aceptado a corto plazo; el servicio se levantó con este límite declarado.

---

## [DT-012] Estado del VPS adelantado al repositorio (kb-mcp desplegado a mano)

**Severity:** Medium
**Origin:** session 2026-07-23
**Description:** El servicio `kb-mcp`, sus correcciones del `Caddyfile` y del `deploy.sh`, y las credenciales `gh` para clonar las KB privadas, fueron aplicados directamente en el VPS por SSH mientras los commits correspondientes permanecen **sin pushear** en `toolset` (decisión explícita del usuario para no disparar el CI/CD completo). Esto tensiona [INFRA-03] («production deploys go through CI/CD») y [MANIFEST-03] («no configuration change lives only on the VPS»).

Riesgo concreto: si el VPS se recrea o si otro deploy corre desde `main` antes del push, el estado actual se pierde y el endpoint `/kb/*` deja de existir. El `sync-kb.sh` y su cron tampoco están instalados todavía (viven en el `deploy.sh` no pusheado), así que **las KB no se actualizan solas**: hoy se sincronizan a mano.

**Remediation plan:** pushear `toolset` cuando el usuario decida. El deploy resultante es idempotente y fue analizado paso a paso: el `Caddyfile` no cambiará (`cmp` da igual → no reinicia Caddy), las KB figuran como «ya clonada», `pull_policy: build` evita el aborto en `compose pull`, y `gh auth setup-git` es idempotente.
**Status:** ☐ Pending. Bloqueado por decisión del usuario (push manual).
