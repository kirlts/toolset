---
name: toolset-ops
description: "Infrastructure operations for Toolset Personal (OCI/Docker/CI)."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [Infrastructure, OCI, Docker, CI-CD, Deployment]
    triggers: ["deploy", "fix bug", "infrastructure", "run cd"]
---

# Toolset Infrastructure Operations

## Rules (MASTER-SPEC §8)

| Rule | Description |
|---|---|
| INFRA-01 | All infra mutations strictly via CI/CD. No local tofu apply/destroy. |
| INFRA-02 | Remote state in OCI Object Storage is authoritative. |
| INFRA-03 | Service deployment via CI/CD. Local execution for verification only. |
| INFRA-04 | Mandatory gateway restart after pipeline/SOUL/config changes. |

## Kilo CLI Execution Rules

Kilo CLI ejecuta workflows multi-step (Kairós: /document, /derive, integraciones) que pueden tomar 5+ minutos.

**Reglas:**
- NUNCA usar `terminal(timeout=N)` para Kilo CLI. Siempre `terminal(background=true, notify_on_complete=true, timeout=600)`.
- Foreground timeout menor a 600 mata el proceso. El workflow queda incompleto y puede corromper estado.
- Verificar que el proceso complete antes de continuar con otra tarea.
- REPORT-01 aplica: reportar resultado cuando el worker notifique.

## Cron Job Failure Diagnosis

When the user reports a cron job ("CRUN", "trabajo programado") failing:

1. **Identify failing jobs**: `cronjob(action='list')` → check `last_status` field
2. **Extract error**: Read `~/.hermes/cron/jobs.json` → find `last_error` field for each failing job (e.g. `[Errno 32] Broken pipe`)
3. **Check job output**: Read files under `~/.hermes/cron/output/<job_id>/` — contains prompt + response or error context
4. **Cross-reference gateway logs**:
   ```
   journalctl -u hermes-gateway --since "<run_time>" --until "<run_time + 15m>" --no-pager
   ```
   Filter for the job's API provider: `grep -i "cron\|<job_id>\|broken\|error\|provider=<provider>"`
5. **Determine root cause**:
   - `[Errno 32] Broken pipe` → API provider (OpenCode Go / deepseek-v4-flash) closed the HTTP connection mid-response. **Not a job logic bug.** This is intermittent — the provider drops the connection during streaming. The cron framework retries 3 times, then marks the job as error.
   - `TimeoutError: MCP call timed out` → MCP server unresponsive (see `systematic-debugging` skill, MCP section)
   - Rate limit / 429 → provider throttling
6. **Test current provider health**: `curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://opencode.ai/zen/go/v1/models`
7. **Resolution**: If provider-side intermittent, no code change needed. If persistent, suggest model fallback or increased retries in the cron job definition.
8. **Report**: State the job name, error class, and root cause clearly. Do not report "it failed" without telling the user why.

### Common Patterns

| Error | Likely Cause | Action |
|---|---|---|
| `[Errno 32] Broken pipe` | API provider connection drop | Verify provider health, retry later, or add retries |
| `MCP call timed out` | MCP server container issue | Check container logs |
| HTTP 4xx/5xx | Provider outage | Check provider status page |
| Job runs but output is empty | Job logic error | Read cron/output/<id>/ for the full trace |

## Documentation Governance (Kairós Compliance)

**IMPORTANT — Martín stated this explicitly: "cualquier cambio que se hace en la documentación siempre tiene que ser coherente con las reglas de Kairós, eso no puede saltarse jamás."**

All documentation changes in Kairós-governed repos MUST follow these rules:

### Format Conventions (TODO.md)

Toolset TODO.md uses a specific format. When adding new EPICs:

```
## [EPIC-00X] Epic Name

> Ref: _section reference or "Por definir"_

### [TASK-0XX] Task Name

> Ref: _section reference or "Por definir"_

**Covered checks:** `Transversal governance`

- [ ] 🔲 Por definir — brief description of what needs doing
```

- Symbol legend: 🔲 = Pendiente, ⏳ = En progreso, 🤖 = IA verificable, 🧑 = Humano, 🤖🧑 = Mixto
- Completed items: `- [x] Description timestamp [🤖 Verified by tool]`
- Update the Overall Coverage Summary table at the bottom after adding EPICs
- Leave EPIC-00X numbers sequential (next unused)
- For strategic ideas not yet defined, mark as "Por definir" with 🔲

### Repo Boundaries

| Repo | You CAN edit | You CANNOT edit | Profile |
|---|---|---|---|
| toolset | docs/ (TODO.md, RULES, etc.), infrastructure/, skills/ | — | orchestrator (default) |
| personal | NEVER | ANY file | personal-profile only |
| jarvis, dino, etc. | Only when the task explicitly requires it | Without context | code-worker |

- **Never touch the `personal` repo** unless the user is actively talking in the Personal WhatsApp group. The personal-profile is strictly isolated.
- Strategic ideas for the Hermes ecosystem go into toolset's `docs/TODO.md` as EPICs.
- Personal-domain ideas go into the personal-buffer (for Martín to classify in his review sessions).

### Strategic Ideation Workflow

When the user asks for "non-obvious use cases" or "creative applications":

1. **Explore full user context first** — read the personal KB (`/home/opc/personal/knowledge-base/`), not just memory banks. The KB contains Terreno (facts about Martín's life, skills, constraints) and Mito (campaigns, ego frameworks, adaptations).
2. **Think across ALL domains** — not just software engineering. Martín's life spans: karate (Itosu-Ryu 4x/week), música docta (CL-Concerts), fauna marina (DinoWiki), OSINT B2B (Prometeo), SaaS (Jarvis), digital forensics (BlinData), residential constraints (8x6 cycle), financial constraints (liquidez restringida), philosophy (Kairós framework).
3. **Present ideas organized by domain** (life/tech/business/physical), not as a flat list.
4. **Never assume which ideas the user wants** — ask, don't commit.
5. **Capture selected ideas only** — as EPICs in toolset's `docs/TODO.md` following the format above.

## Personal-Buffer Feed Configuration

See `references/ci-cd-repo-commit-detection.md` for the state-file approach used to detect commits in CI/CD-managed repos (like toolset) and feed them into `personal-buffer`. Applied via modification to `repo-pull-cron.sh`.

## WhatsApp Group Context Injection

See `references/whatsapp-groups-context-injection.md` for the bridge-level injection that gives every profile awareness of all WhatsApp groups, their profiles, and repos. This prevents cross-profile routing errors (suggesting the wrong group for delegation).

## Health Checks

### Services Quick-Reference

| Service | Command |
|---|---|
| All Docker containers | `docker ps --format "table {{.Names}}\t{{.Status}}"` |
| Hindsight (Docker) | `docker ps --filter name=hindsight --format "{{.Status}}"` |
| Infisical | `curl -sf http://localhost:8081/api/status` |
| Caddy | `curl -sf http://localhost:8080/` (serves landing page) |
| hermes-gateway | `systemctl is-active hermes-gateway` |
| hermes-webui | `systemctl is-active hermes-webui` |
| Hindsight MCP | Verify via MCP tool `list_banks` or `get_bank` |
| WhatsApp Bridge | `curl -sf http://localhost:3000/messages` (returns `[]` when up) |
| SearXNG | `curl -sf http://localhost:4000` |

### Comprehensive Health Check (5-axis)

Run this when asked for a "health check" or "revision de salud":

1. **CI/CD**: `gh run list --repo kirlts/toolset --limit 3` — check last 3 workflow conclusions
2. **WhatsApp**: Bridge log at `~/.hermes/whatsapp/bridge.log` — check `[routing]` lines for inbound messages. Bridge is push-only (Baileys Web, no queryable REST API). Query `curl -sf http://localhost:3000/messages` for liveness.
3. **Hindsight banks**: `recall(bank="toolset", query="pending, todo, pendiente, tarea")` + `recall(bank="hermes", query="pending, todo, pendiente, tarea")`. Cross-reference pending memory entries against actual filesystem/state — old entries (4+ days) that no longer reflect reality should be flagged as **stale** and optionally invalidated.
4. **Docker services**: `docker ps --format "table {{.Names}}\t{{.Status}}"` — all should be `Up` and `(healthy)`. Check systemd services separately.
5. **Host resources**: `free -h`, `df -h /`, `uptime`, `cat /proc/loadavg`

### Cron Mode Constraints

- `execute_code` is BLOCKED in cron mode (no user present to approve arbitrary Python). Use `terminal()` for data processing instead — pipe through `python3 -c '...'` inline.
- The WhatsApp bridge (`/usr/local/lib/hermes-agent/scripts/whatsapp-bridge/bridge.js`) uses Baileys (WhatsApp Web protocol). **No REST API for message querying exists** — it's a push-only system. For health checks, only liveness can be confirmed via HTTP.
- Bridge has a known non-critical: `link-preview-js` package missing from Baileys dependencies (URL preview generation fails, messaging works). Do not flag as service-down.

### Stale Memory Detection During Health Checks

When Hindsight memory recall returns pending/action items:

1. For each entry dated 4+ days ago, verify against current files/state
2. Common stale patterns:
   - `deploy.sh changes pending` when CI/CD runs pass clean
   - References to deleted files that were restored in later commits
   - TODO items marked complete in the repo but not cleaned from memory
3. If stale → note in report but do not delete. Flag for user review.
4. After the health check, `retain(bank="toolset")` with the check result for traceability
