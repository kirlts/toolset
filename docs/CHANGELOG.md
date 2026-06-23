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

## [Unreleased]

### Added
- Infisical UI expuesta via Tailscale Funnel en puerto `:8443` (evita conflicto `/_next/*` entre Next.js de CP e Infisical).
- Rutas de API del CP de Hindsight: `/api/profile/*`, `/api/stats/*`, `/api/list`, `/api/recall`, `/api/reflect`, `/api/documents/*` agregadas al Caddyfile.
- Landing page dinámica con listing de banks, enlace a RULES.md y URLs de Infisical UI.
- Atajo `/status` → `/status/` via redirect 308.

### Fixed
- **DT-004**: `ENCRYPTION_KEY` de Infisical corregida de base64 a `openssl rand -hex 16` (32 hex chars = 32 UTF-8 bytes). `$getBasicEncryptionKey()` lee la key como UTF-8 buffer; base64 producía 44+ bytes → `ERR_CRYPTO_INVALID_KEYLEN` en KMS migration.
- `DB_CONNECTION_URI`: Docker Compose v5.1.4 no expande multi-sustitución inline. Cambiado a variable simple `${DB_CONNECTION_URI}` definida en `.env`.
- CP bank routing: removido `rewrite * /dashboard` para `/banks/*` — ahora el request llega directo al CP (App Router) con la URL original.
- Catch-all `handle /api/*` de Infisical ya no intercepta rutas del CP (`/api/profile/*`, `/api/stats/*`).
- Caddy healthcheck ahora depende solo de Hindsight, no de Infisical.

### Changed
- Caddyfile reestructurado: landing page en `/`, Infisical API en `/api/*` (después de rutas CP), Infisical UI bypasses Caddy via puerto Funnel independiente.
- `deploy.sh`: verificación de servicios críticos reducida a `caddy hindsight`. Lógica de `.env` simplificada (solo escribe si no existe). Funnel de Infisical en `:8443` asegurado post-deploy.
- `VERIFICATION.md`: `[DEV.CR.05.LLM]` actualizado a implementado (Infisical healthy via `/api/status`).
- `TODO.md`: TASK-008 subtareas de Funnel/Caddy actualizadas como completadas.
- `GITHUB SECRET` `INFISICAL_ENCRYPTION_KEY` actualizado con formato hex correcto.
- Service token permanente creado (`st.*`) para CI/CD y almacenado como GitHub Secret `INFISICAL_SERVICE_TOKEN`.
- `deploy.sh`: bootstrap automático de admin Infisical vía API en cada deploy (idempotente). Sync de secrets desde GitHub Secrets a Infisical.

## [0.1.0] - 2026-06-21

### Added
- Inicializacion del repositorio local git en /home/kirlts/toolset.
- Integracion del servidor MCP Composio para conectividad con Google Drive.
- Integracion del servidor MCP Hindsight para almacenamiento de memoria de contexto centralizado.
- Bootstrap inicial del sistema de documentacion de gobernanza de Kairos en el directorio docs/.
