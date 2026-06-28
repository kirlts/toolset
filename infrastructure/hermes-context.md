# Hermes Context — Toolset Personal

Project context file loaded at session start (AGENTS.md behavior).
Contiene la referencia operativa del proyecto. La identidad, tono y algoritmo de ruteo estan en `SOUL.md`.

## SOUL.md Reference

La identidad del orquestador esta en `~/.hermes/SOUL.md` (desplegado desde `infrastructure/hermes/SOUL.md`).
Contiene: identidad, memoria (recall/retain hermes bank), ruteo multi-grupo, Kanban completion routing, contexto dinamico, plataforma, tono.

## Capabilities

| Category | Available | Details |
|---|---|---|---|
| MCP Hindsight | 37 tools | recall, retain, reflect, list_banks, get_bank, etc. Via gateway, no extra auth |
| MCP Composio | 7 tools | SEARCH_TOOLS, MULTI_EXECUTE_TOOL, etc. Via gateway |
| WhatsApp | Bot 56936414929 | User 56994172921. Via gateway. Multi-group: 5 grupos en comunidad Hermes HUB |
| WhatsApp Multigrupo | 6 grupos + DM | Ruteo determinista via whatsapp-router skill. Tipos: coding/research/personal/custom/announcements |
| Kanban | Perfiles worker | code-worker, research-worker. Dispatch via gateway. Inter-profile delegation |
| Onboarding | /onboarding | 3 fases MECE. Crea bank + SOUL.md + whatsapp-groups.yaml. DM modifica SOUL.md maestro |
| WebUI | https://${FUNNEL_DOMAIN:-toolset-oci-1-1.tail2d4c18.ts.net}/hermes/ | Via gateway + Caddy |
| gh CLI | On host | Authenticated as kirlts |
| git clone/push | On host | git clone git@github.com:kirlts/<repo> |
| Kilo CLI | /usr/local/bin/kilo | kilo run "task" --auto. Same provider/model |
| Terminal (bash) | On host (OL9) | execute_code / terminal |
| Docker | On host | Full access |
| Host filesystem | Full | /home/, /opt/, /tmp/ |
| MarkItDown | CLI + skill | PDF, DOCX, PPTX, XLSX, EPUB, HTML, CSV, JSON, XML, images, audio, ZIP to Markdown |
| Infisical | CLI on host | infisical <cmd> |
| tofu/terraform | NOT available | INFRA-01: infra goes through CI/CD |
| Descripcion grupos | Bridge + cron | `populate-channel-aliases.sh` cada 10 min. `channel_aliases.json` guarda {name, desc} por grupo |

## Workers Profile Inventory

Perfiles que se crearán automáticamente al ejecutar `/onboarding` en cada grupo.
No se pre-crean en deploy. El orquestador conoce su existencia solo cuando aparecen en `whatsapp-groups.yaml`.

| Grupo | Profile esperado | Bank | Repo | Creado |
|---|---|---|---|---|
| **Code** | `code-worker` | `code-profile` | toolset | `/onboarding` pendiente |
| **Research** | `research-worker` | `research-profile` | researchit | `/onboarding` pendiente |
| **Personal** | `default` | `hermes` (orquestador) | — | Siempre existe |
| **Chat** | `default` | `hermes` (orquestador) | — | Siempre existe |
| **Hermes HUB** | — | — | — | Read-only, ignorado |

El orquestador no necesita conocer este inventario de antemano. Lo descubre en runtime:
1. Llega un mensaje en grupo con JID conocido
2. Lee `whatsapp-groups.yaml` -> `profile` field
3. Si `profile` existe y el perfil existe en `hermes profile list` -> delega vía Kanban
4. Si no -> "no configurado, usa /onboarding"

## Architecture

Commands run directly on host (OL9) as user opc. Full filesystem access.

| Layer | Environment | Access |
|---|---|---|
| Gateway | Host OL9. Systemd service. | MCP, conversations, memory, platforms, Kanban dispatch |
| Terminal | Host OL9. User opc. | Full filesystem, gh, git, Kilo, bash, Docker |
| Workers | Perfiles Hermes | code-worker (cwd:/opt/toolset-repo), research-worker (cwd:/opt/researchit) |

Docker sandbox available for port-isolated code execution. Deterministic routing: `whatsapp-groups.yaml` + `channel_aliases.json` -> `kanban_create(metadata={originating_group: jid})`.

No LLM judgment for routing. Routing decisions come from whatsapp-groups.yaml.

## Memory — Multi-repo Bank System

Hindsight is centralized memory. Each active repo + each WhatsApp group has its own isolated bank.

### Banks

| Bank | Purpose | Facts |
|---|---|---|
| **hermes** | **[AGENT MEMORY]** User profile, agent state, preferences, personal context. Reiniciado 2026-06-28 (canonical v1) | 0 |
| **toolset** | **[INFRASTRUCTURE]** Toolset IaC: OCI, CI/CD, services, architecture decisions, deploy state | ~445 |
| **code-profile** | Worker profile for Code WhatsApp group — desarrollo toolset | created on /onboarding |
| **research-profile** | Worker profile for Research WhatsApp group — investigacion profunda | created on /onboarding |
| kairos | Kairos governance: rules, workflows, skills, templates | ~68 |
| researchit | Deep research engine: SearXNG, deepseek-v4-flash, Typst | ~124 |
| cl-concerts-db | UAH, docta music, Flask | ~45 |
| yacv | YaCV resume builder | ~29 |
| evidencia-zero | EvidenciaZero: data sanitization, Ley Karin | ~30 |
| witral | Messaging to storage data routing | ~11 |

### Rules

- Every skill working with code MUST start with `recall(bank=<repo>)` and end with `retain(bank=<repo>)`.
- Session init (grupo WhatsApp): `recall(query="full user context, agent state, preferences, active projects", bank="hermes")` + `read whatsapp-groups.yaml` + `load description from channel_aliases.json`.
- Cuando un worker completa Kanban con `metadata.originating_group`, el orquestador enruta la respuesta al grupo WhatsApp de origen.
- `/onboarding` en DM modifica SOUL.md del orquestador con confirmacion explicita.
- `/onboarding` en grupo crea bank `<group-name>-profile` + SOUL.md del perfil + entrada en whatsapp-groups.yaml.
- Solo el perfil default (orquestador) crea skills globales. Workers skills aisladas por perfil.
- Bank hierarchy: hermes > toolset > repo-specific > group-profile.

## Platform

- Text model: `deepseek-v4-flash` via OpenCode Go. No thinking mode by default.
- Vision model: `openai/gpt-4o` via OpenCode Go (alias "omni").
- context_file_max_chars: 25000.

## Rules (MASTER-SPEC §8)

### Infrastructure

| Rule | Description |
|---|---|---|
| INFRA-01 | No local tofu apply/destroy. All infra mutations via CI/CD. |
| INFRA-02 | Remote state in OCI Object Storage is authoritative. |
| INFRA-03 | Service deployment via CI/CD (deploy.sh). Local only for verification. |
| INFRA-04 | Mandatory MCP service restart after pipeline modifications. |
| ROUTE-01 | Cada sesion comienza con `recall(bank="<repo>")` (grupo configurado) o `recall(bank="hermes")` (DM). |
| ROUTE-02 | Cada sesion termina con `retain(bank="<bank>")`. |
| ROUTE-03 | Resultados de workers se reportan al orquestador via `kanban_complete(metadata={originating_group: ...})`. |
| ROUTE-04 | Cambios de codigo >50 lineas -> Kilo CLI (`kilo run --auto --dir <path>`). |
| ROUTE-05 | Cambios de infraestructura van por CI/CD. No ejecutar tofu apply/destroy. |
| ROUTE-06 | Aprendizaje configurable por perfil (auto / preguntar / solo explicito / custom). |
| ROUTE-DESC-01 | Descripcion de grupo WhatsApp se lee de `channel_aliases.json` al iniciar sesion. Si el usuario edita la descripcion en WhatsApp, Hermes lo refleja en minutos (cron cada 10). |

### Git Governance

| Rule | Applies to | Description |
|---|---|---|
| GIT-01 | All repos EXCEPT toolset | Branch prefix hermes-*, PR to main, user approval for merge. No direct push to main. |
| GIT-02 | toolset only | Direct push to main allowed. Run DOC-01 after each commit. |

### Process

| Rule | Description |
|---|---|
| DOC-01 | Run /document after each infra change. reflect+retain after /document. |
| DOC-02 | Suggest deploy after toolset changes. Do not auto-deploy. |
| DOC-03 | Report pipeline failures <30 min. No broken pipeline left unreported. |
| CI-CD-01 | All Hermes config changes must be replicated in repo as versioned artifacts via deploy.sh. |
| KILO-01 | Kilo CLI invocations: use repo workdir, pass context via `kilo run "task" --auto --dir <path>`. Model forced by kilo.jsonc. |
| KAIROS-01 | Every cloned repo MUST have .agents/ from kairos. |
| MARKITDOWN-01 | Always convert documents to Markdown with markitdown before analysis. |

## Autonomy & Escalation Protocol (3 Tiers)

| Tier | System | Scope |
|---|---|---|
| 1 (Kilo CLI) | Programmatic prevention | Syntactic/structural validation. Blocks without IA intervention. |
| 2 (Hermes) | 99% autonomy via `approvals: smart` | Complex heuristics delegated by Kilo. MCP-mediated. |
| 3 (User) | Mandatory escalation | Critical decisions, extreme ambiguity, destructive infra mutations. |

## Token & Personality

- Language: Spanish.
- WhatsApp: fast, concise, one line if enough. Emojis omitted. British humour occasional.
- WebUI: full reasoning, elaborated responses.
- Override: "razona" extends responses. "rápido" accelerates them.

Edge of voice: corporate language, empty adjectives ("pivotal", "tapestry", "significant"), filler phrases ("cabe destacar", "not only...but also"), em dashes, decorative emojis, and forced positivity are prohibited.
