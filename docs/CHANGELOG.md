# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-06-28

### Added
- GROQ_API_KEY integrado como GitHub Secret → CI/CD → .env en VPS para STT
- ffmpeg binario estático ARM64 instalado en VPS para conversión de formato de audio
- WHATSAPP_HOME_CHANNEL persistente en .env para entregas de cron y notificaciones autónomas

### Changed
- STT provider cambiado de `local` (faster-whisper base) a `groq` (whisper-large-v3-turbo cloud)
- Pipeline CI/CD actualizado: GROQ_API_KEY en Deploy y Sync secrets steps
- MCP timeout aumentado a 120s/120000ms para hindsight-selfhosted (evita timeouts en reflect/recall complejas)

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

## [0.4.0] - 2026-06-25

### Added
- Hermes-integration.md: plan de integración completo con casos de uso, arquitectura CI/CD, deep dives técnicos.
- Implementación completa de Hermes Agent en OCI: instalación vía one-liner, systemd service, Docker backend.
- WhatsApp integration: bot number dedicado, allowlist bidireccional, Baileys bridge.
- WebUI: systemd service + SKIP_ONBOARDING + Funnel público :8787.
- Composio MCP conectado con 7 tools registrados.
- Bank "hermes" en Hindsight con 30 facts de identidad.
- SOUL.md personalizada, Kilo Code CLI, gh CLI instalados en VPS.
- Bidirectional secret sync GitHub ↔ Infisical.
- KAIROS-01 y DOC-01 rules para gobernanza.

### Fixed
- DT-004: ENCRYPTION_KEY corregida de base64 a hex.
- DB_CONNECTION_URI: Docker Compose v5.1.4 no expande multi-sustitución.
- Caddy healthcheck ahora depende solo de Hindsight.

### Changed
- Caddyfile reestructurado con landing page en `/`, rutas CP antes que Infisical.
- deploy.sh: verificación de servicios reducida, .env simplificado.
- Service token permanente creado como GitHub Secret.

## [Unreleased]

### Added
- WhatsApp multi-group routing via 6 groups in Hermes HUB community (Chat, Code, Research, Personal, Hermes HUB, DM).
- Deterministic routing via whatsapp-groups.yaml — no LLM judgment, no predefined categories.
- 3-phase MECE onboarding (v4): category-free. Same questions for all groups. Group descriptions auto-suggested from WhatsApp via channel_aliases.json.
- worker profiles created only by /onboarding. No pre-created workers in deploy.
- Inter-profile delegation: kanban with metadata.originating_group propagation. Responses return to originating WhatsApp group.
- INFRASTRUCTURE-MANIFEST.md: declarative tracking of all Hermes configuration files.
- group-onboarding SKILL.md (v4): 3-phase onboarding without predefined types.
- whatsapp-router SKILL.md (v4): deterministic routing, type-free.
- profile-soul.md template: SOUL.md generation with bank rules, evolution preferences, dynamic context.
- populate-channel-aliases.sh: bridge → channel_aliases.json with {name, desc} per group. Cron every 10 min.
- patch-bridge.sh: exposes metadata.desc from Baileys groupMetadata. CI/CD-managed.
- recall max_tokens=16384 universal — prevents truncation in banks with 445+ facts.
- RULES.md: MANIFEST-01 to 04, ROUTE-01 to 05, ONBOARD-01 to 03 rule groups.
- hermes-context.md: Workers Profile Inventory, per-group bank tracking.
- memory recall: max_tokens=16384 for all recall calls (toolset 445, researchit 124, hermes).
- README.md: rewritten with architecture, routing table, key files, /onboarding flow, CI/CD.

### Changed
- SOUL.md: refactored 254→79 lines. Clean identity/routing/memory/tone separation. No type-based routing. Routing checks profile field only.
- hermes-context.md: full operational reference. Banks updated (hermes: 0 facts canonical v1).
- whatsapp-groups.yaml: stripped types and profiles. JID-only until /onboarding.
- deploy.sh: removed worker profile creation. Added whatsapp-groups.yaml deploy, bridge patch, populate aliases, cron setup. Bridge patch block made independent.
- deploy.yml: removed `**.md` from paths-ignore (blocked SOUL.md, SKILL.md deploys).
- .gitignore: added transcript.txt.

### Fixed
- Bridge was missing metadata.desc from Baileys groupMetadata. Now exposed via patch-bridge.sh.
- Channel_aliases stored only names, now stores {name, desc} per group.
- SOUL.md routing with `profile definido` check for groups without /onboarding.
- recall truncation: max_tokens=16384 for all calls.
- deploy.sh: bridge patch nested inside populate if block (broken). Made independent.

### Removed
- All predefined categories from onboarding (coding/research/personal/custom).
- Type-based routing from SOUL.md and whatsapp-router SKILL.md.
- Worker profile creation from deploy.sh (onboarding only).
- Pre-created code-worker and research-worker profiles from VPS.
- Channels/type system from whatsapp-groups.yaml.

## [0.1.0] - 2026-06-21

### Added
- Inicializacion del repositorio local git en /home/kirlts/toolset.
- Integracion del servidor MCP Composio para conectividad con Google Drive.
- Integracion del servidor MCP Hindsight para almacenamiento de memoria de contexto centralizado.
- Bootstrap inicial del sistema de documentacion de gobernanza de Kairos en el directorio docs/.
