# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Despliegue de instancia VM.Standard.A1.Flex (2 OCPU, 12 GB RAM, 100 GB boot, OL9 ARM64) en OCI Free Tier.
- Bootstrap automatizado via cloud-init: Docker 29.6.0, Docker Compose, Tailscale, keepalive anti-reclamation.
- Infisical self-hosted desplegado en Docker Compose con PostgreSQL 16 y Redis 7 como dependencias.
- Remote state de OpenTofu en OCI Object Storage (bucket `toolset-opentofu-state`) con sync via OCI CLI en pipeline.
- Generación de llave SSH ED25519 dedicada para Toolset (`.ssh/toolset-oci`).
- Customer Secret Key para acceso S3-compatible a OCI Object Storage.
- `terraform.tfvars` con secrets (Tailscale auth key, Infisical encryption key y auth secret) en `.gitignore`.
- EPIC-006 en TODO.md con tareas de investigación para Funnel, integración Infisical y hardening de seguridad.

### Fixed
- Cloud-init reescrito como script bash con lock de dnf para evitar race conditions con OCI monitoring agent.
- Repositorios Docker CE y Tailscale escritos como archivos `.repo` directos en lugar de usar `dnf config-manager`.
- Puerto SSH público cerrado — ahora solo accesible desde VCN (10.0.0.0/16). Acceso via Tailscale.
- `ENCRYPTION_KEY` de Infisical ajustada a 16 bytes (AES-128) para compatibilidad con la versión v0.161.3.

### Added
- Despliegue de Hindsight self-hosted (`ghcr.io/vectorize-io/hindsight:latest`, modo standalone con pg0 embebido) en Docker Compose.
- `infrastructure/docker-compose.yml` canónico en repo con healthchecks en todos los servicios (pg_isready, redis-cli ping, curl, wget).
- `infrastructure/deploy.sh`: script de despliegue CI/CD que transfiere compose + .env vía SSH, ejecuta docker compose pull/up, y verifica healthchecks (sin polling — aborta en unhealthy/exited).
- Job `deploy-services` en pipeline CI/CD: Tailscale → SSH → deploy.sh, con secrets inyectados desde GitHub Secrets.
- Configuración MCP `hindsight-selfhosted` en Kilo Code (`kilo.jsonc`, vía Funnel URL, deshabilitado hasta migración del bank toolset).
- `SSH_PRIVATE_KEY` como GitHub Secret para acceso CI/CD al servidor OCI.
- Tailscale Funnel habilitado en OCI: `https://toolset-oci-1.tail2d4c18.ts.net/` → `http://localhost:8888` (Hindsight API + MCP público vía HTTPS).
- `deploy.sh` ahora verifica y asegura que Tailscale Funnel esté activo post-deploy.

### Fixed
- Healthcheck de Hindsight corregido: usa `/health` en puerto 8888 en lugar de `/api/health` (404).
- `deploy.sh` maneja permisos sudo para `/opt/toolset/` (propiedad root) y usa base64 para transferencia segura de `.env`.

### Fixed
- Healthcheck de Hindsight corregido: usa `/health` en puerto 8888 en lugar de `/api/health` (404).
- `deploy.sh` maneja permisos sudo para `/opt/toolset/` (propiedad root) y usa base64 para transferencia segura de `.env`.

### Changed
- `TODO.md`: TASK-007 avanzado — 8/10 subtareas completadas. Totales de coverage actualizados.
- `VERIFICATION.md`: `[DEV.CR.08.MIX]` actualizado a implementación parcial.
- Pipeline CI/CD renombrado a "Deploy OpenTofu + Services to OCI" con dos jobs paralelizables.
- Hindsight usa OpenCode Go (DeepSeek V4 Flash) como proveedor LLM en lugar de API key directa.

## [0.1.0] - 2026-06-21

### Added
- Inicializacion del repositorio local git en /home/kirlts/toolset.
- Integracion del servidor MCP Composio para conectividad con Google Drive.
- Integracion del servidor MCP Hindsight para almacenamiento de memoria de contexto centralizado.
- Bootstrap inicial del sistema de documentacion de gobernanza de Kairos en el directorio docs/.
