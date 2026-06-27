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
**Status:** ✅ Parcialmente resuelto. Caddyfile actualizado con `basicauth` para rutas de gestión de Hindsight CP (`/dashboard`, `/banks/*`, `/api/banks/*`, etc.) usando `{$FUNNEL_AUTH_USER}` y `{$FUNNEL_AUTH_PASSWORD}` desde env vars. Infisical y Hermes WebUI tienen auth propio. Pendiente: verificar que MCP harnesses (Kilo, Claude Code) sigan funcionando sin auth (solo /hindsight/mcp/ no tiene auth). 2026-06-26

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
