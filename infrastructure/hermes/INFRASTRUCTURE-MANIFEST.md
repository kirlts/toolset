# Infrastructure Manifest — Toolset Personal

> Single source of truth for ALL Hermes configuration files.
> Cada archivo .md operativo de Hermes DEBE estar listado aqui.
> Creado: 2026-06-28. Se actualiza cada vez que se modifica un archivo de configuracion.

---

## Structure

| File | Purpose | Sync to VPS | Last Updated |
|---|---|---|---|
| `infrastructure/hermes/SOUL.md` | Identidad, tono, algoritmo de ruteo, memoria del orquestador. ~70 lineas. Sin contenido operativo. | deploy.sh (sobrescribe) | 2026-06-28 |
| `infrastructure/hermes-context.md` | Contexto operativo de Hermes (AGENTS.md): capacidades, arquitectura, banks, reglas, routing detallado | deploy.sh -> ~/.hermes/context.md + /opt/toolset-repo/AGENTS.md | 2026-06-28 |
| `infrastructure/hermes/config.yaml` | Config estructural: MCP servers, external_skills_dirs, modelo, proveedor | deploy.sh + inject-composio-key.py | 2026-06-26 |
| `infrastructure/hermes/CRONS.md` | Documentacion de cron jobs activos | Repo (documentacion, no ejecutable) | 2026-06-28 |
| `infrastructure/hermes/scripts/populate-channel-aliases.sh` | Consulta bridge GET /chat/:id, escribe channel_aliases.json con {name, desc} | deploy.sh (paso 1b) | 2026-06-28 |
| `infrastructure/hermes/scripts/patch-bridge.sh` | Parchea bridge.js para exponer metadata.desc desde Baileys groupMetadata | deploy.sh (paso 1b) | 2026-06-28 |
| `infrastructure/hermes/whatsapp-groups.yaml` | Mapeo JID -> {type, name, desc, repo, profile, skills} para ruteo determinista | deploy.sh (paso 1b) -> ~/.hermes/ | 2026-06-28 |
| `infrastructure/hermes-skills/whatsapp-router/SKILL.md` | Skill de ruteo determinista de mensajes WhatsApp segun tipo de grupo | external_skills_dirs (repo clone) | 2026-06-28 |
| `infrastructure/hermes-skills/group-onboarding/SKILL.md` | Onboarding 3 fases MECE: crea bank, SOUL.md, YAML, perfil worker | external_skills_dirs (repo clone) | 2026-06-28 |
| `infrastructure/hermes-skills/kilo-code/SKILL.md` | Integracion Kilo CLI: umbral 50 lineas, contexto, recall/retain | external_skills_dirs (repo clone) | Estable |
| `.agents/templates/profile-soul.md` | Template SOUL.md para perfiles worker. Placeholders: PROFILE_NAME, DOMAIN, TYPE, BANK_ID, etc. | Repo (referenciado por onboarding) | 2026-06-28 |
| `docs/MASTER-SPEC.md` | Especificacion fundacional del proyecto | No aplica (documentacion) | 2026-06-28 |
| `docs/Hermes-integration.md` | Plan de integracion Hermes. Puede estar desactualizado tras iteraciones | No aplica (documentacion) | 2026-06-23 |

---

## Sync Mechanisms

| Mechanism | Files Affected |
|---|---|
| **deploy.sh** (CI/CD) | SOUL.md, context.md, config.yaml, whatsapp-groups.yaml, scripts/, memories/ |
| **external_skills_dirs** | skills en infrastructure/hermes-skills/ (cargados desde /opt/toolset-repo) |
| **Cron (populate-channel-aliases)** | channel_aliases.json (cada 10 min) |
| **Cron (hermes-sync-files)** | backup de ~/.hermes/ config al repo (diario) |
| **Cron (hermes-sync-banks)** | exportacion de banks Hindsight al repo (diario) |

---

## Update Procedure

Cuando se modifica un archivo de configuracion:

1. **Editar en repo** (nunca editar solo en VPS).
2. **Actualizar esta fila** en el MANIFEST (cambiar Last Updated a la fecha de hoy).
3. **Si es SOUL.md, config.yaml, o .env**: commit + push -> deploy.sh lo sincroniza.
4. **Si es una skill en infrastructure/hermes-skills/**: commit + push -> external_skills_dirs refresca en proxima sesion.
5. **Si es un script en infrastructure/hermes/scripts/**: commit + push -> deploy.sh lo copia.
6. **Si es una plantilla .agents/templates/**: commit + push -> referenciado por onboarding.
7. **Ejecutar DOC-01** (`/document` workflow + `reflect` + `retain`).

---

## Current Session Changes (2026-06-28)

| File | Change |
|---|---|
| infrastructure/hermes/SOUL.md | REFACTORED: 254 -> 84 lineas. Routing sin tipos predefinidos — solo verifica si hay profile. |
| infrastructure/hermes-context.md | REFACTORED: referencia operativa completa. Workers Profile Inventory. Banks actualizados. |
| infrastructure/hermes/whatsapp-groups.yaml | LIMPIADO: sin type, sin profiles. Solo JID + name. Onboarding define todo. |
| infrastructure/deploy.sh | REMOVIDO: creacion de workers profiles. FIX: bridge patch independiente del populate. |
| infrastructure/hermes-skills/group-onboarding/SKILL.md | v4: sin tipos predefinidos. Mismas preguntas para todos los grupos. Sin defaults por categoria. |
| infrastructure/hermes-skills/whatsapp-router/SKILL.md | v4: sin tabla de tipos. Solo verifica profile field. |
| infrastructure/hermes-skills/group-onboarding/SKILL.md | v3: 3-phase MECE, DM handler, evolution preferences, dynamic description |
| .agents/templates/profile-soul.md | NEW: profile SOUL.md with placeholders, evolution + desc rules |
| docs/MASTER-SPEC.md | Updated 7.1 with multi-group routing, deterministic routing, onboarding |
| .github/workflows/deploy.yml | Removed **.md from paths-ignore (blocked SOUL.md + SKILL.md deploys) |
| infrastructure/deploy.sh | Added bridge patch, worker profiles, cron setup, whatsapp-groups.yaml deploy |
| infrastructure/deploy.sh | ADDED: GROQ_API_KEY to .env, ffmpeg static binary install for audio STT |
| infrastructure/hermes/config.yaml | CHANGED: stt.provider to groq, groq.model to whisper-large-v3-turbo |
| .github/workflows/deploy.yml | ADDED: GROQ_API_KEY secret to Deploy and Sync secrets steps |
| infrastructure/kilo.jsonc | ADDED: timeout 120000ms for hindsight-selfhosted MCP server |
| infrastructure/hermes/config.yaml | ADDED: timeout 120s for hindsight-selfhosted MCP server |
| infrastructure/hermes-skills/kilo-code/SKILL.md | REWRITTEN v2.0.0: governance-based delegation over line thresholds |
| infrastructure/hermes-skills/group-onboarding/SKILL.md | REWRITTEN v4.1.0: added Phase 0 Context Ingestion |
| .agents/templates/profile-soul.md | CHANGED: ROUTE-04 universal Kilo CLI (no line threshold) |
| infrastructure/hermes/cloned-repos.yaml | CREATED: manifest for repo cloning (native tools + cloned repos) |
| infrastructure/deploy.sh | REPLACED ad-hoc ResearchIt clone with clone_repos() reading cloned-repos.yaml |
| infrastructure/hermes/scripts/repo-pull-cron.sh | CREATED: silent git pull cron (5min, only notifies on conflict, max 1x/day) |
| **Session 2** | |
| infrastructure/hermes/SOUL.md | UPDATED: eliminada excepción hardcodeada de personal por regla universal de delegación según tarea. |
| infrastructure/hermes/whatsapp-groups.yaml | ADDED: grupo Toolset (JID 120363426816726918, profile: toolset, repo: kirlts/toolset). |
| infrastructure/hermes/profiles/toolset/SOUL.md | NEW: perfil toolset con dominio exclusivo, Kilo CLI obligatorio, Kanban para tareas multi-step. |
| infrastructure/hermes-skills/group-onboarding/SKILL.md | v4.2.0: agregada inferencia de criterio de delegación en Phase 0 + pregunta en Phase 3. |
| infrastructure/hermes/INFRASTRUCTURE-MANIFEST.md | UPDATED: registrados cambios de Session 2. |
