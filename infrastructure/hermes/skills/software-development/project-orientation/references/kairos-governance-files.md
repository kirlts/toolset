# Kairos Governance Files Reference

Condensed reference for files in a Kairos-governed project repository. This maps the documentary axis structure used across all of user's projects (toolset, kairos, cl-concerts-db, etc.).

## Top-Level Structure

```
<repo-root>/
  .agents/              ← Active governance layer (MANDATORY read)
  docs/                 ← Documentary axis (project documentation)
    MASTER-SPEC.md      ← Domain Axiom — architectural authority
    REPOMAP.md          ← Routing matrix — defines WHAT to read and WHEN
    RULES.md            ← Operational rules for AI agents
    TODO.md             ← Task tracking with coverage checks
    VERIFICATION.md     ← Verification matrix
    CHANGELOG.md        ← Change history
    TECHNICAL-DEBT.md   ← Known technical debt
    USER-DECISIONS.md   ← Explicit user decisions
    MEMORY.md           ← Agent memory notes
  infrastructure/       ← Infrastructure as code
  README.md             ← Project overview
  *.md (root)           ← Domain Axiom or Planning files
```

## .agents/ Structure

```
.agents/
  roles/                ← Agent role definitions (director.md, senior-coder.md, etc.)
  rules/                ← Behavior rules (01-behavior, 02-linguistics, etc.)
  skills/               ← Reusable skill definitions
  workflows/            ← Workflow scripts (fix, document, derive, release, etc.)
  templates/            ← Document templates (rules.md, todo.md, etc.)
  knowledge/            ← Knowledge base files (constitution.md, etc.)
```

## Reading Order (per REPOMAP)

| Order | File / Bank | Purpose |
|-------|-------------|---------|
| 0 | Hindsight bank `<project>` — `recall` | Project memory context — architecture, decisions, progress (MANDATORY first step per MEM-01) |
| 0a | Hindsight bank `hermes` — `recall` | User profile + agent preferences — style, corrections, conventions. Always recall BOTH. |
| 1 | `docs/REPOMAP.md` | Understand what to read and when |
| 2 | `docs/MASTER-SPEC.md` | Architecture, stack, constraints |
| 3 | `docs/RULES.md` | Operational rules for agents |
| 4 | `README.md` | Project overview |
| 5 | Domain Axiom files | Foundational specs (e.g., `Toolset Junio 2026.md`) |
| 6 | `infrastructure/` | Deployment configuration |
| 7 | `.github/workflows/` | CI/CD pipelines |
| 8 | `docs/TODO.md` | Current state and pending tasks |
| 9 | `.agents/` | Active governance (roles, rules, workflows) |

## Bank Naming Convention

Kairos convention: `hindsight-<project-name>`. Examples:
- `toolset` → bank `toolset` (115 memories as of June 2026)
- `kairos` → bank `kairos`
- `cl-concerts-db` → bank `cl-concerts-db`
The bank ID is the project directory/repo name. Use `recall` with `bank_id="<name>"` and `budget="high"`.

## User Profile / Cross-Project Memory

Bank `hermes` is the **user profile bank** — holds user preferences, environment conventions, style corrections, and meta-rules that apply across ALL projects. Always recall it alongside the project bank during session initialization:

```python
mcp_hindsight_selfhosted_recall(
    query="perfil del usuario preferencias contexto",
    bank_id="hermes",
    budget="high"
)
```

Use `reflect` to synthesize user-level patterns across multiple memories. Use `retain` with `bank_id="hermes"` when the user expresses a cross-project preference, correction, or learning.

## Memory Lifecycle Overview

Hindsight memory follows a lifecycle that requires periodic maintenance:

| Frequency | Action | Purpose |
|-----------|--------|---------|
| **Each session start** | `recall` (project + user banks) | Load context into working prompt |
| **Each session end / significant event** | `retain` (both banks) | Persist new facts immediately |
| **Daily** | `reflect` → `retain` consolidation | Synthesize session learnings into durable memories |
| **Weekly** | Bank export to JSON | Version control backup of all memory banks |
| **Per deploy** | Post-deploy import | Restore banks on fresh CI/CD deployment |

See skill `agent-state-management` for detailed lifecycle automation patterns.
The bank ID is the project directory/repo name. Use `recall` with `bank_id="<name>"` and `budget="high"`.

## Key Files Reference (Toolset Personal)

| File | Content |
|------|---------|
| `infrastructure/compute.tf` | VM.Standard.A1.Flex, 2 OCPU, 12GB RAM, 100GB boot, OL9, sa-valparaiso-1 |
| `infrastructure/network.tf` | VCN with subnet, security rules (SSH only from VCN 10.0.0.0/16) |
| `infrastructure/docker-compose.yml` | PostgreSQL 16, Redis 7, Infisical, Hindsight, Caddy |
| `infrastructure/Caddyfile` | Reverse proxy: /health, /api/*, /mcp/*, /dashboard, /banks/*, /hermes/* |
| `infrastructure/deploy.sh` | Full deployment script (LVM extend, .env, Docker Compose, Hermes, Funnel) |
| `infrastructure/cloud-init.yaml` | First-boot bootstrap |
| `infrastructure/Hermes-SOUL.md` | Hermes agent identity file (deployed as ~/.hermes/SOUL.md) |
| `infrastructure/kilo.jsonc` | Kilo Code CLI config (for coding subagent) |
| `.github/workflows/deploy.yml` | CI/CD: OpenTofu plan/apply + deploy-services |

## OCI Instance Details (from recall)

- Region: sa-valparaiso-1
- Shape: VM.Standard.A1.Flex (Ampere ARM64, 2 OCPU, 12GB)
- OS: Oracle Linux 9.7
- Boot volume: 100GB (LVM extended from ~44.5GB via growpart+pvresize+lvextend+xfs_growfs)
- Tailscale node: `toolset-oci-1` / `toolset-oci-1-1.tail2d4c18.ts.net`
- Docker: 29.6.0 with Compose plugin
- Hermes: v0.17.0 as systemd service
