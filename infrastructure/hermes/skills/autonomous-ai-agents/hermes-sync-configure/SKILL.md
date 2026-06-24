---
name: hermes-sync-configure
description: "Set up or repair Hermes auto-sync infrastructure: cron jobs, repo sync script, SOUL.md rules, deploy.sh restoration."
version: 1.0.0
author: Toolset Personal
platforms: [linux]
---

# Hermes Sync Configure

Configures the daily auto-sync pipeline that versions all Hermes Agent artifacts (SOUL.md, config, skills, memory, scripts, Hindsight bank dumps) into the toolset repo.

## What it creates

### 1. Sync script
`infrastructure/hermes/sync-hermes-to-repo.sh` — copies from `~/.hermes/` to the repo:
- `SOUL.md` → `infrastructure/hermes/SOUL.md`
- `config.yaml` → `infrastructure/hermes/config.yaml`
- `memories/MEMORY.md + USER.md` → `infrastructure/hermes/memory/`
- `skills/` (full snapshot, minus curator internals) → `infrastructure/hermes/skills/`
- `scripts/` → `infrastructure/hermes/scripts/`
- `hooks/` → `infrastructure/hermes/hooks/`

### 2. Cron jobs (2 daily)

| Cron | Time | What it does |
|---|---|---|
| `hermes-sync-files` | 01:00 UTC | Runs the bash sync script (no_agent). Commits + pushes file artifacts. |
| `hermes-sync-banks` | 02:00 UTC | Agent-driven: exports banks `hermes` + `toolset` as JSON dumps, runs reflect + retain, commits. |

### 3. SOUL.md updates
Adds to `~/.hermes/SOUL.md`:
- **Inicialización de sesión**: recall(bank="hermes") mandatory at session start
- **Sincronización diaria automática**: documentation of both cron jobs
- Banks JSON = backup/audit only, agent uses live Hindsight MCP

### 4. deploy.sh changes
Adds restoration of config.yaml, memory files, and scripts from repo to `~/.hermes/` during CI/CD.

## Troubleshooting

- **Sync script fails**: check `REPO_DIR` and `HERMES_HOME` env vars
- **Cron not firing**: verify with `cronjob(action='list')`
- **Agent-driven cron fails**: check Hindsight MCP server is reachable
- **Duplicate skills**: remove the duplicate from `hermes-skills/` subdir

## Verification

```bash
cronjob(action='list')
ls infrastructure/hermes/
bash infrastructure/hermes/sync-hermes-to-repo.sh
```
