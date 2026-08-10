# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

> Desplegado en el VPS, **pendiente de push** (ver [DT-012]).

### Changed
- **`/okos-mapa/` pasa de la maqueta v5 a la Torre v9 con el contrato vivo embebido** (2026-08-10). El `index.html` de `/opt/toolset/landing/okos-mapa/` ahora es la Torre OKOS v9 (857 KB): 292 piezas · 222 cintas · 4 días de historia, generado desde el repo `okos-mapa` (`prototype/generar_digest.py` produce el bloque de datos desde `data/mapa.json`; `prototype/ensamblar_v9.py` arma el HTML desde el esqueleto v8 con reemplazos de conteo exacto). `support.js` e `image-slot.js` quedan tal cual; **ni Caddyfile ni Funnel se tocaron**. Respaldo del anterior en `index.html.bak.1786393122`. Verificado desde fuera de la tailnet: 200 con el tamaño exacto del archivo (876 962 bytes), `/okos-mapa/no-existe.js` → 404, `/health` sin regresión, y un navegador real contra la URL pública renderiza sin errores de consola. **Cambio de exposición que la v5 no tenía**: la v9 embebe datos reales de la plataforma —nombres de espacios de clientes, cuotas y consumos por plan, evidencia literal de sondas—. Sigue público y sin `basic_auth` (decisión del usuario, igual que el 2026-08-08); si eso cambia, es una línea del Caddyfile. **Actualizado el mismo día con una pasada de rendimiento medida con perfil de CPU y tracing**: la cámara del gesto (rueda y paneo) vive en el compositor y el viewBox se asienta solo cuando el zoom acumulado supera ~1.4× o al reposar 450 ms — cero tormentas de raster por muesca de rueda—; la máscara SVG pasó de 222 aplicaciones (una por camino) a una sola sobre la capa, con el camino encendido duplicado en una capa sin máscara; el vestido de fichas es analítico (cero layouts forzados); y las animaciones se pausan durante el gesto. Bloqueo del hilo principal en 12 pasos de zoom con GPU: 0.46 s (antes ~8 s en la misma batería). También tres bugs de la v8: el panel de área ya no queda abierto tapando clics tras «Open the area», el botón ⑂ tiene un mínimo de 24 px en pantalla (medía 10), y los rótulos de bottleneck/worse del nivel 1 se encogen hasta caber con hover completo.

### Added
- **`/okos-mapa/`: el prototipo visual del mapa OKOS, servido estático y público** en `https://toolset-oci-1-1.tail2d4c18.ts.net/okos-mapa/`. Bloque `handle /okos-mapa*` en el `Caddyfile` con `root /usr/share/caddy/landing` + `file_server`, antes del catch-all y **sin `try_files`**: aquí no hay SPA que enrutar, y un 404 debe ser un 404 y no la landing con HTTP 200 —el mismo defecto que ya obligó al bloque `/.well-known/*`—. Los archivos (`index.html`, `support.js`, `image-slot.js`) viven en `/opt/toolset/landing/okos-mapa/` del VPS; el fuente es el repo `okos-mapa`, no éste. Queda público por el Funnel **ya encendido** en el 443: no se tocó su configuración, así que no hay superficie nueva más allá de esa ruta. Es una maqueta sin datos en vivo, para validar la forma del artefacto; sus rótulos igual se leen como estado real de la plataforma y hoy no lleva `basic_auth` (decisión del usuario). Verificado desde fuera de la tailnet: DNS público → ingress del Funnel, 200 y tamaño exacto del archivo; navegador real contra la IP pública renderiza sin errores de consola; sin regresiones en `/`, `/dashboard` ni `/health`, con `/okos-mapa/no-existe.js` → 404.
- **kb-mcp**: servidor MCP de solo lectura que publica bases de conocimiento de `kb-template` en `/kb/<slug>/mcp`. Multi-KB en un proceso, búsqueda híbrida (FTS5/BM25 + embeddings estáticos + grafo de wikilinks + recencia por historial git), tres herramientas sin escritura. Sirviendo `traza-ambiental` y `personal`. Ver MASTER-SPEC §7.2 y `infrastructure/kb-mcp/README.md`.
- Auto-descripción de cada KB: el servidor declara su dominio en las `instructions` y en la cabecera de las tres herramientas, combinando `kb/mcp.yaml` de la KB con los conceptos centrales deducidos del grafo. Basta la URL para que un agente sepa cuándo usarla.
- `sync-kb.sh` + cron (*/15 min) para actualizar las KB y reindexar solo si cambió el HEAD.
- **kb-mcp pasa de embeddings estáticos a un codificador real** (`paraphrase-multilingual-MiniLM-L12-v2`, horneado en la imagen). Medido sobre 81 preguntas juzgadas de `kb-okos`, mismo corpus y mismo puntaje: las preguntas cuyo documento correcto no aparece bajan de 28 a 20, y el top-3 sube de 43 a 49. Para el consumidor real —un agente, que puede volver a preguntar— es pasar de encontrar lo buscado el 83 % de las veces al 93 %. Se probaron cinco configuraciones: `e5-base` resultó el peor de todos y los prefijos canónicos de `e5` empeoran su número en este corpus. `KB_MODELO=/modelo` revierte al estático sin reconstruir la imagen; el montaje se conserva para eso.
- **Caché de vectores por hash del texto** (`KB_VECTORES`, volumen `/opt/kb-vectores`). Sin él el codificador sería indesplegable: el índice se reconstruye al arrancar y `sync-kb.sh` reinicia el contenedor en cada cambio de contenido —28 veces el 2026-08-07—, o sea ~14 min diarios de servicio caído. Con caché, un reinicio cuesta 8,7 s contra los 7,9 s que el índice ya costaba sin ningún modelo: el codificador agrega 0,8 s. Degrada bien: sin volumen de escritura se comporta como antes. Ver [HEU-013](MEMORY.md).
- **El modelo mal cargado ya no degrada en silencio**: si `KB_MODELO` pide un codificador y la biblioteca no está, el servidor lo dice por `stderr` y sigue sin capa semántica, en vez de intentar bajar 470 MB para leerlos como una tabla que no son —lo que colgaba el arranque— o de dejar que una batería midiera solo-léxico y reportara el número como si fuera el del buscador.

### Fixed
- **El conector de claude.ai fallaba con «no se pudo registrar con el servicio de inicio de sesión»**: el catch-all del `Caddyfile` respondía la landing con HTTP 200 en las rutas de descubrimiento OAuth, y un cliente MCP lo lee como «este recurso exige OAuth». Ahora devuelven 404, que es lo correcto para un servidor sin auth.
- `deploy.sh` transfería el `Caddyfile` con `mv`, rompiendo el inode del bind mount (el contenedor seguía viendo el archivo viejo), y nada recargaba Caddy —que corre con `admin off` y no admite reload en caliente. Un cambio de rutas se transfería sin surtir efecto, en silencio. Ahora: `tee`, detección de cambio, validación dentro del contenedor y reinicio solo si corresponde.
- Las KB son repos privados y git no traía credenciales: el clon inicial y el cron de sync fallaban con «could not read Username». `deploy.sh` corre `gh auth setup-git` (idempotente).
- **El fallback de modelo anunciado en 0.6.0 nunca estuvo activo**: `fallback_providers` se escribió como cadena (`opencodego/qwen3.7-plus`) y `hermes_cli/fallback_config.py` sólo acepta entradas `{provider, model}`, así que la descartaba en silencio. `hermes fallback list` respondía «No fallback providers configured» en el perfil principal y en el tenant `tito`. Corregido al formato dict, con cadena `qwen3.7-plus → minimax-m3`, y verificado con el propio CLI.
- **Tito cortaba conversaciones con «No response from provider for 180s» y «Broken pipe»**: el proveedor `opencode-go` tiene episodios de latencia al primer token muy alta (medido: 43 s en 1 de 3 llamadas idénticas, a veces >180 s). Sin fallback efectivo, el vigilante de stream esperaba 180 s × 3 intentos = 9 minutos antes de rendirse. Ahora `providers.opencode-go.stale_timeout_seconds: 90` en ambos perfiles.
- **Las tareas auxiliares cascadeaban a proveedores que no existen**: con `auxiliary.<tarea>.provider: auto`, si el proveedor principal falla el router prueba OpenRouter (sin saldo → 402) y Nous Portal (sin auth), ~90 s de timeout cada uno, y los marca «unhealthy» por 60 s. Las 13 tareas de texto (títulos, compresión de contexto, curador, aprobaciones, descomposición Kanban, extracción web…) quedaron fijadas a `opencode-go/deepseek-v4-flash`, el mismo modelo que `auto` elegía en el camino feliz, pero sin la cascada muerta; con proveedor explícito la única red de seguridad es el modelo principal del agente. `vision` ya estaba fijado a `mimo-v2-omni`. El tenant `tito` no tenía sección `auxiliary`; se le agregó completa.
- **La credencial `fallback-key` del pool de `opencode-go` estaba muerta**: responde `CreditsError` (saldo insuficiente) en todos los modelos y `RegionError` en `deepseek-v4-flash`. El pool rotaba a ella ante cualquier error transitorio y sumaba 403s (`marking fallback-key exhausted (status=403)` en los logs desde el 31 de julio). Removida de los dos pools con `hermes auth remove`.
- **La sesión de WhatsApp del tenant `tito` quedó deslogueada y su bridge en crashloop**: arrancaba en `:3001`, WhatsApp respondía `Logged out`, moría, y el gateway lo respawneaba. Como el monitor muestrea cada 5 minutos un punto cualquiera de ese ciclo, la caída permanente se veía intermitente. Sesión re-vinculada por QR con `--pair-only`; bridge estable y monitor en `EXIT=0`.

### Documentation
- **[DEV.CR.18] falsificada**: el `basicauth` que protegía las URLs de gestión de Hindsight fue removido en `1de879b`/`db17f50` sin actualizar la verificación ni [DT-002]. `/dashboard` y `/api/banks` responden 200 desde internet. [DT-002] reabierto.
- Procedimiento de re-pareo de sesión por tenant en `hermes-skills/toolset-ops/SKILL.md`: cómo distinguir un crashloop de un bridge caído, las tres fases de recuperación y las trampas ya cobradas, entre ellas un `pkill -f` que mata la propia sesión SSH que lo invoca.
- Nuevos: [DT-011] kb-mcp sin autenticación ni aislamiento entre KB; [DT-012] estado del VPS adelantado al repositorio; [DT-013] el monitor de tenants repite la misma alerta cada 5 minutos sin dedupe; [DT-014] el bridge de tenant se respawnea sin backoff ni tope.

## [0.6.0] - 2026-07-06

### Added
- TTS Edge Microsoft activado (voz es-CL-LorenzoNeural, masculina chilena). `tts.enabled: true`, per-group config via whatsapp-groups.yaml TTS block.
- Onboarding v5.0.0: Phase 4 TTS configuration + retrocompatibilidad (update vs full re-onboard).
- Fallback model qwen3.7-plus via Hermes `fallback_providers` y Kilo `models`.
- 3-layer recall safety net: server-side `recall_max_tokens=4096` en 10 bancos, `agent.build.prompt` enforcement, profile SOUL.md explicit params.
- WhatsApp auto-cleanup: populate-channel-aliases.sh remueve JIDs huérfanos de whatsapp-groups.yaml.
- Kilo workflow discovery: `.agents/workflows/` referenciado en system prompt como fuente de `/document`.
- Anti-corruption: regla `--file` para prompts >10 words en kilo-code SKILL.md (evita truncamiento por stream drop).
- `infrastructure/kilo-recall-policy.md`: documentación del incidente y política.

### Changed
- **CRITICAL:** deploy.sh ahora despliega `infrastructure/hermes/SOUL.md` en vez de `infrastructure/Hermes-SOUL.md` (archivo obsoleto en inglés). 
- Kilo CLI model default: `deepseek-v4-flash` → `deepseek-v4-pro` con `reasoning: true`.
- Hermes reasoning: `reasoning_full: true` (debugging aid, ya tenía `effort: xhigh`).
- Recency bias combat: Hermes preamble para Kilo ahora pone la tarea PRIMERO y el marco obligatorio DESPUÉS.
- repo-pull-cron.sh: todos los repos reciben `git pull --ff-only`, sin importar `sync` type.
- AGENTS.md + hermes-context.md: bank naming `<profile>-profile`, recall params con max_tokens/budget, ROUTE-07 agregado.
- docs/RULES.md: bank naming consistente. Sin excepciones.

### Fixed
- deploy.yml líneas 58, 109, 226 restauradas de corrupción sed.
- Banco `toolset` (741 facts históricos) eliminado. `toolset-profile` fresco con 0 facts.
- All 31 recall() calls now have explicit `max_tokens` and `budget`. PROHIBIDO `budget="high"`.
- `infrastructure/kilo-prompt.md` eliminado (DEPRECATED, se contradice a sí mismo línea 30-31).
- Sistema de perfiles: toolset SOUL.md ahora tiene Memory Cycle completo (antes 0 líneas recall/retain).
- 8 archivos de skills: bank naming unificado, `bank=` → `bank_id=`, max_tokens agregados.
- Herramientas MCP: tool definitions son ~5K tokens (aceptable, no hay tool search nativo en Hindsight).

### Removed
- `infrastructure/Hermes-SOUL.md`: archivo inglés obsoleto (22 líneas, junio 28). Reemplazado por `hermes/SOUL.md` (92 líneas, español, con fixes).
- Banco `toolset-profile`: eliminado (era shell con 0 facts después de migración).
- Context management step (step 8) de kilo-code SKILL.md: era iniciativa incorrecta, revertido.

### Added
- `infrastructure/kilo-system-prompt.md`: single source of truth for Kilo CLI system prompt (clean, minimal, no redundancy).
- `scripts/generate-kilo-config.py`: auto-generates kilo.jsonc from kilo-system-prompt.md — injects prompt into `agent.build.prompt` field.
- deploy.sh auto-regenerates kilo.jsonc if kilo-system-prompt.md changed; transfers to VPS for Kilo CLI config.
- Kilo CLI workflow simplified: `agent.build.prompt` replaces `instructions` array for system prompt delivery.
- Preflight Docker healthcheck filter: only checks services from docker-compose.yml (not external containers).
- Preflight bank check: uses list endpoint with grep -q profile name instead of brittle curl-pipe-jq.
- Preflight Hindsight API check via localhost:8888 (not Funnel URL) for reliability.
- Preflight WebUI check via Caddy proxy (port 8787 redirect, not direct container port).
- Hot backup resilience: deploy.sh hindsight backup tar handles file-changed-during-read without aborting.

### Changed
- `infrastructure/kilo.jsonc`: removed `kilo-prompt.md` from `instructions` array. System prompt delivered exclusively via `agent.build.prompt` field (auto-generated from kilo-system-prompt.md).
- `infrastructure/kilo-prompt.md`: deprecated. Replaced by `kilo-system-prompt.md` as canonical source. Removed from `kilo.jsonc` instructions list to eliminate redundancy between `instructions` and `agent.build.prompt`.
- Kilo CLI memory instructions: now embedded in agent.build.prompt — Hindsight async pattern (`retain` async, no `sync_retain`) to prevent timeouts.
- SOUL.md profile vs Kilo system prompt overlap eliminated — Kilo receives only its own identity (no profile SOUL.md bleeding).

### Fixed
- deploy.sh hindsight backup tar no longer fails when files change during hot backup (`--warning=no-file-changed`).
- Preflight Docker check uses `docker ps` directly instead of grepping `docker compose config` (catches real container state).
- Preflight MCP E2E: bank check uses `grep -q` on list output instead of fragile JSON parsing.

## [0.4.0] - 2026-06-28

### Added
- WhatsApp multi-group routing via 6 groups in Hermes HUB community (Chat, Code, Research, Personal, Hermes HUB, DM).
- Deterministic routing via whatsapp-groups.yaml — no LLM judgment, no predefined categories.
- 3-phase MECE onboarding (v4): category-free. Same questions for all groups. Group descriptions auto-suggested from WhatsApp via channel_aliases.json.
- Worker profiles created only by /onboarding. No pre-created workers in deploy.
- Inter-profile delegation: kanban with metadata.originating_group propagation. Responses return to originating WhatsApp group.
- INFRASTRUCTURE-MANIFEST.md: declarative tracking of all Hermes configuration files.
- group-onboarding SKILL.md (v4/v4.1.0): 3-phase onboarding, Phase 0 context ingestion (documents, URLs, voice, history).
- whatsapp-router SKILL.md (v4): deterministic routing, type-free.
- profile-soul.md template: SOUL.md generation with bank rules, evolution preferences, dynamic context.
- populate-channel-aliases.sh: bridge → channel_aliases.json with {name, desc} per group. Cron every 10 min.
- patch-bridge.sh: exposes metadata.desc from Baileys groupMetadata. CI/CD-managed.
- recall max_tokens=16384 universal — prevents truncation in banks with 445+ facts.
- RULES.md: MANIFEST-01 to 04, ROUTE-01 to 05, ONBOARD-01 to 03 rule groups.
- hermes-context.md: Workers Profile Inventory, per-group bank tracking.
- memory recall: max_tokens=16384 for all recall calls (toolset 445, researchit 124, hermes).
- README.md: rewritten with architecture, routing table, key files, /onboarding flow, CI/CD.
- GROQ_API_KEY integrado como GitHub Secret → CI/CD → .env en VPS para STT.
- ffmpeg binario estático ARM64 instalado en VPS para conversión de formato de audio.
- WHATSAPP_HOME_CHANNEL persistente en .env para entregas de cron y notificaciones autónomas.
- kilo-code/SKILL.md v2.0.0: delegación basada en gobernanza (repos con .agents/ → Kilo CLI exclusivo).
- cloned-repos.yaml: manifest de repos clonados (tools nativas + repos de usuario).
- deploy.sh clone_repos(): función genérica que lee el manifest y clona/pulea cada repo.
- repo-pull-cron.sh: cron silencioso cada 5min, solo notifica conflictos máx 1x/día.
- Hermes-integration.md: plan de integración completo con casos de uso, arquitectura CI/CD, deep dives técnicos.
- Implementación completa de Hermes Agent en OCI: instalación vía one-liner, systemd service, Docker backend.
- WhatsApp integration: bot number dedicado, allowlist bidireccional, Baileys bridge.
- WebUI: systemd service + SKIP_ONBOARDING + Funnel público :8787.
- Composio MCP conectado con 7 tools registrados.
- Bank "hermes" en Hindsight con 30 facts de identidad.
- SOUL.md personalizada, Kilo Code CLI, gh CLI instalados en VPS.
- Bidirectional secret sync GitHub ↔ Infisical.
- KAIROS-01 y DOC-01 rules para gobernanza.

### Changed
- STT provider cambiado de `local` (faster-whisper base) a `groq` (whisper-large-v3-turbo cloud).
- Pipeline CI/CD actualizado: GROQ_API_KEY en Deploy y Sync secrets steps.
- MCP timeout aumentado a 120s/120000ms para hindsight-selfhosted.
- profile-soul.md ROUTE-04: umbral de líneas reemplazado por delegación universal a Kilo CLI.
- group-onboarding/SKILL.md: preguntas de fases 1-3 se saltean si ya fueron inferidas en Fase 0.
- SOUL.md: refactored 254→79 lines. Clean identity/routing/memory/tone separation. No type-based routing. Routing checks profile field only.
- hermes-context.md: full operational reference. Banks updated (hermes: 0 facts canonical v1).
- whatsapp-groups.yaml: stripped types and profiles. JID-only until /onboarding.
- deploy.sh: removed worker profile creation. Added whatsapp-groups.yaml deploy, bridge patch, populate aliases, cron setup. Bridge patch block made independent.
- deploy.yml: removed `**.md` from paths-ignore (blocked SOUL.md, SKILL.md deploys).
- .gitignore: added transcript.txt.
- Caddyfile reestructurado con landing page en `/`, rutas CP antes que Infisical.
- deploy.sh: verificación de servicios reducida, .env simplificado.
- Service token permanente creado como GitHub Secret.

### Fixed
- Bridge was missing metadata.desc from Baileys groupMetadata. Now exposed via patch-bridge.sh.
- Channel_aliases stored only names, now stores {name, desc} per group.
- SOUL.md routing with `profile definido` check for groups without /onboarding.
- recall truncation: max_tokens=16384 for all calls.
- deploy.sh: bridge patch nested inside populate if block (broken). Made independent.
- DT-004: ENCRYPTION_KEY corregida de base64 a hex.
- DB_CONNECTION_URI: Docker Compose v5.1.4 no expande multi-sustitución.
- Caddy healthcheck ahora depende solo de Hindsight.

### Removed
- All predefined categories from onboarding (coding/research/personal/custom).
- Type-based routing from SOUL.md and whatsapp-router SKILL.md.
- Worker profile creation from deploy.sh (onboarding only).
- Pre-created code-worker and research-worker profiles from VPS.
- Channels/type system from whatsapp-groups.yaml.

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

## [0.1.0] - 2026-06-21

### Added
- Inicializacion del repositorio local git en /home/kirlts/toolset.
- Integracion del servidor MCP Composio para conectividad con Google Drive.
- Integracion del servidor MCP Hindsight para almacenamiento de memoria de contexto centralizado.
- Bootstrap inicial del sistema de documentacion de gobernanza de Kairos en el directorio docs/.
