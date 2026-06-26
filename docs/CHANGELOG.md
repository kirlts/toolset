# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-06-22

### Added
- Despliegue de instancia VM.Standard.A1.Flex (2 OCPU, 12 GB RAM, 100 GB boot, OL9 ARM64) en OCI Free Tier.
- Bootstrap automatizado via cloud-init: Docker 29.6.0, Docker Compose, Tailscale, keepalive anti-reclamation.
- Infisical self-hosted desplegado en Docker Compose con PostgreSQL 16 y Redis 7 como dependencias.
- Remote state de OpenTofu en OCI Object Storage (bucket `toolset-opentofu-state`) con sync via OCI CLI en pipeline.
- Despliegue de Hindsight self-hosted (`ghcr.io/vectorize-io/hindsight:latest`, modo standalone con pg0 embebido) en Docker Compose.
- `infrastructure/docker-compose.yml` canónico en repo con healthchecks en todos los servicios.
- `infrastructure/deploy.sh`: script de despliegue CI/CD con transferencia de compose + .env vía SSH.
- Job `deploy-services` en pipeline CI/CD: Tailscale → SSH → deploy.sh, con secrets inyectados desde GitHub Secrets.
- Migración del bank "toolset" desde Hindsight Cloud al self-hosted en OCI.
- Caddy reverse proxy multi-servicio (Hindsight API/MCP/CP, Infisical, landing page).
- Tailscale Funnel habilitado en OCI.

### Fixed
- Cloud-init reescrito como script bash con lock de dnf (race conditions con OCI monitoring agent).
- Puerto SSH público cerrado — solo accesible desde VCN (10.0.0.0/16).

### Changed
- Pipeline CI/CD renombrado a "Deploy OpenTofu + Services to OCI" con dos jobs paralelizables.
- Hindsight usa OpenCode Go (DeepSeek V4 Flash) como proveedor LLM.
- MCP self-hosted activado en Kilo Code, cloud desactivado.

## [0.3.0] - 2026-06-26

### Added
- SOUL.md refactorizado: reducido de 210 a 21 líneas (solo identidad/tono).
- hermes-context.md con contenido operacional extraído de SOUL.md (capacidades, arquitectura, banks, reglas).
- AGENTS.md en repo root para auto-descubrimiento de contexto por Hermes.
- preflight.sh: verificación post-deploy de invariantes MASTER-SPEC + MCP 3-Step con SSE handshake correcto.
- pre-commit hook: bloquea .env y secrets en commits.
- INFRA-04 en RULES.md: restart obligatorio de MCP gateway post-deploy.
- Skills externas via `external_skills_dirs`: toolset-ops, monitoring, kilo-code.
- MCP Lifecycle documentado en MASTER-SPEC §7.1.
- Script de consolidación de memoria (cron cada 30min).
- approvals.mode: smart configurado en inject-composio-key.py.

### Changed
- deploy.sh: toolset repo clone, context file sync, gateway restart dedicado + health check, memory cron.
- deploy.sh: Infisical sync batch en un solo SSH Python call.
- deploy.sh: eliminado `--force-recreate` en docker compose (usa change detection nativo).
- deploy.sh: reducidos sleeps de verificación (10→5s, 30→15s).
- deploy.sh: gateway health check reducido (3×3s).
- deploy.sh: Hindsight backup condicional (<1hr skip).
- inject-composio-key.py: approvals.mode smart, skills.external_dirs configurados.
- MASTER-SPEC.md §7.1: documentado MCP Lifecycle.
- MEMORY.md: Consolidation Protocol agregado como header.

### Fixed
- Gateway health check: corrige exit code 3 de systemctl (gateway inactivo cortaba el script).
- Cron path: consolidate-memory.sh ubicado correctamente tras extracción tar con --strip-components.
- AGENTS.md symlink en ~opc para auto-descubrimiento Hermes desde systemd.
- preflight.sh MCP 3-Step: ahora usa initialize SSE → session ID → tools/call (antes daba falso positivo).
- Landing page: actualizada referencia MCP.

### Removed
- Skills tar/scp block en deploy.sh (reemplazado por external_skills_dirs).
- autonomous-ai-agents/ directory (skills a estructura flat).
- `context_file_max_chars` duplicado en deploy.sh.
- MCP proxy revertido (no necesario — MCP servers ya estaban bien configurados).

## [Unreleased]

### Fixed
- **WebUI siempre actualizado**: deploy.sh ejecuta `git pull --ff-only` antes de restartear el servicio hermes-webui. En instalación inicial clona desde cero y configura `pull.ff only`. Ownership corregido tras cada pull.
- **Banks dinámicos**: deploy.sh descubre todos los banks desde infraestructura versionada en `infrastructure/hermes/banks/`. Lista expandida para incluir cl-concerts-db, hermes, toolset (antes solo kairos, yacv, evidencia-zero, witral).

### Added
- Hermes-integration.md: plan de integración completo con casos de uso, arquitectura CI/CD, deep dives técnicos verificados contra documentación oficial y comunidad (r/hermesagent).
- Implementación completa de Hermes Agent en OCI: instalación vía one-liner, systemd service, Docker backend, configuración runtime.
- WhatsApp integration: bot number dedicado, allowlist bidireccional, Baileys bridge vía Hermes nativo.
- WebUI: systemd service + SKIP_ONBOARDING + Funnel público :8787.
- Composio MCP conectado con `ck_` key via `x-consumer-api-key` header (7 tools registrados).
- Bank "hermes" en Hindsight con 30 facts de identidad seedeados.
- SOUL.md personalizada con contexto completo: identidad, memoria, herramientas, reglas INFRA, workflow mobile.
- Kilo Code CLI (`@kilocode/cli`) y gh CLI instalados y autenticados en VPS.
- Bidirectional secret sync GitHub ↔ Infisical con reverse sync automático.
- Bash syntax validation step en pipeline CI/CD.
- gh CLI install + GH_CLI_TOKEN auth en deploy.sh.
- `instructions` y `agent.build.prompt` en kilo.jsonc global para orquestación Kilo CLI → Hermes.
- Export automático de `OPENCODE_GO_API_KEY` a .bashrc en VPS para resolución `{env:...}` de Kilo CLI.
- `KAIROS-01` y `DOC-01` rules en Hermes-SOUL.md para gobernanza y documentación.

### Fixed
- **DT-004**: `ENCRYPTION_KEY` de Infisical corregida de base64 a `openssl rand -hex 16` (32 hex chars = 32 UTF-8 bytes). `$getBasicEncryptionKey()` lee la key como UTF-8 buffer; base64 producía 44+ bytes → `ERR_CRYPTO_INVALID_KEYLEN` en KMS migration.
- `DB_CONNECTION_URI`: Docker Compose v5.1.4 no expande multi-sustitución inline. Cambiado a variable simple `${DB_CONNECTION_URI}` definida en `.env`.
- CP bank routing: removido `rewrite * /dashboard` para `/banks/*` — ahora el request llega directo al CP (App Router) con la URL original.
- Catch-all `handle /api/*` de Infisical ya no intercepta rutas del CP (`/api/profile/*`, `/api/stats/*`).
- Caddy healthcheck ahora depende solo de Hindsight, no de Infisical.
- `COMPOSIO_REDDIT_CONNECTION_ID` escapado correctamente en deploy.sh (doble backslash → simple).

### Changed
- Caddyfile reestructurado: landing page en `/`, Infisical API en `/api/*` (después de rutas CP), Infisical UI bypasses Caddy via puerto Funnel independiente.
- `deploy.sh`: verificación de servicios críticos reducida a `caddy hindsight`. Lógica de `.env` simplificada (solo escribe si no existe). Funnel de Infisical en `:8443` asegurado post-deploy.
- `VERIFICATION.md`: `[DEV.CR.05.LLM]` actualizado a implementado (Infisical healthy via `/api/status`).
- `TODO.md`: TASK-008 subtareas de Funnel/Caddy actualizadas como completadas.
- `GITHUB SECRET` `INFISICAL_ENCRYPTION_KEY` actualizado con formato hex correcto.
- Service token permanente creado (`st.*`) para CI/CD y almacenado como GitHub Secret `INFISICAL_SERVICE_TOKEN`.
- `deploy.sh`: bootstrap automático de admin Infisical vía API en cada deploy (idempotente). Sync de secrets desde GitHub Secrets a Infisical.
- `deploy.sh`: agregada sección de export OPENCODE_GO_API_KEY a .bashrc del VPS.
- `infrastructure/kilo.jsonc` eliminado del repo — config migrado a `~/.config/kilo/kilo.jsonc` global con instructions, agent.build.prompt y provider sin npm field.
- `VERIFICATION.md`: `[DEV.CR.07.LLM]` duplicado corregido — la check de EPIC-004 renombrada a `[DEV.CR.13.LLM]` (servicio persistente de Hermes) y marcada como implementada.
- `TODO.md`: coverage summary corregido para reflejar conteo real de checks por epic.

## [0.1.0] - 2026-06-21

### Added
- Inicializacion del repositorio local git en /home/kirlts/toolset.
- Integracion del servidor MCP Composio para conectividad con Google Drive.
- Integracion del servidor MCP Hindsight para almacenamiento de memoria de contexto centralizado.
- Bootstrap inicial del sistema de documentacion de gobernanza de Kairos en el directorio docs/.
