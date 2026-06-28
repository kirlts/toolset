# Toolset Personal

Infrastructure toolkit for a solo developer operating autonomously with fixed-cost cloud execution. The orchestrator is Hermes Agent (WhatsApp bot + Kanban dispatch), the code subagent is Kilo Code CLI, and the stack runs on OCI with Tailscale private networking.

## Architecture

```
WhatsApp (6 groups: Chat / Code / Research / Personal / Hermes HUB)
    │ DM = orchestrator, group = per-type routing
    ▼
Hermes Gateway (systemd) → SOUL.md (deterministic routing)
    │
    ├─ Kanban dispatch → code-worker (toolset repo)
    │                 → research-worker (researchit repo)
    │                 → default (personal orchestrator)
    │
    ├─ Hindsight (self-hosted MCP memory, per-repo + per-group banks)
    ├─ Composio (OAuth gateway: Gmail, Reddit, GitHub, Figma)
    └─ Kilo CLI (code subagent for >50-line tasks)
```

## Routing

Messages route by group type, not LLM judgment:

| Group | Type | Profile | Uses |
|---|---|---|---|
| Chat | personal | default | Orchestrator, general conversation |
| Code | coding | code-worker | toolset development, Kilo CLI |
| Research | research | research-worker | deep search, markitdown |
| Personal | personal | default | orchestrator, system status |
| Hermes HUB | announcements | — | read-only, ignored |

## Key Files

| File | Purpose |
|---|---|
| `infrastructure/hermes/SOUL.md` | Master orchestrator identity, routing rules, tone |
| `infrastructure/hermes/whatsapp-groups.yaml` | Group → type → profile mapping |
| `infrastructure/hermes/scripts/populate-channel-aliases.sh` | Resolves group JIDs to human names + descriptions |
| `infrastructure/hermes/scripts/patch-bridge.sh` | Exposes WhatsApp group descriptions via Baileys |
| `infrastructure/hermes/INFRASTRUCTURE-MANIFEST.md` | Tracks all configuration files |
| `infrastructure/hermes-skills/whatsapp-router/SKILL.md` | Deterministic routing instructions |
| `infrastructure/hermes-skills/group-onboarding/SKILL.md` | 3-phase /onboarding (Identity, Capabilities, Operations) |
| `.agents/templates/profile-soul.md` | Template for per-profile SOUL.md generation |
| `docs/RULES.md` | Agent operational rules (MANIFEST, ROUTE, ONBOARD) |

## /onboarding

```
En grupo nuevo: /onboarding → Phase 1 (Identity) → Phase 2 (Capabilities) → Phase 3 (Operations)
                               → Bank created → SOUL.md generated → YAML written → git pushed
En DM:          /onboarding → confirm → modifies master SOUL.md (backup automatico)
```

## CI/CD

GitHub Actions → `deploy.yml`:
1. OpenTofu provisions OCI infra
2. deploy.sh syncs config + whatsapp-groups.yaml + scripts + crons + profiles
3. inject-composio-key.py configures MCP servers
4. Preflight checks 15+ invariants

All configuration is in `infrastructure/`. No live dependency on OCI — everything recovers from a git clone + `gh workflow run`.

## First canonical version: 2026-06-28
