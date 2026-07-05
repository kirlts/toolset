---
name: hermes-sync-configure
description: "Set up or repair Hermes auto-sync infrastructure: cron jobs, repo sync script, SOUL.md rules, deploy.sh restoration."
version: 1.1.0
author: Toolset Personal
platforms: [linux]
metadata:
  hermes:
    tags: [infrastructure, cron, sync, hindsight-banks]
    triggers: [sync, banks, cron job, auto-sync, export banks]
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
| `hermes-sync-banks` | 02:00 UTC | Agent-driven: discovers ALL non-default banks (~13 active: toolset, hermes, personal-profile, personal-buffer, chat-profile, wwe-profile, toolset-profile, witral, yacv, evidencia-zero, cl-concerts-db, researchit, kairos), exports each as JSON dump, runs reflect + retain per bank, commits + pushes. |

### 3. SOUL.md updates
Adds to `~/.hermes/SOUL.md`:
- **Inicialización de sesión**: recall(bank_id="hermes", max_tokens=4096, budget="mid") mandatory at session start
- **Sincronización diaria automática**: documentation of both cron jobs
- Banks JSON = backup/audit only, agent uses live Hindsight MCP

### 4. deploy.sh changes
Adds restoration of config.yaml, memory files, and scripts from repo to `~/.hermes/` during CI/CD.

### 5. Reference: bank-sync-execution
See `references/bank-sync-execution.md` for the detailed step-by-step procedure used by the `hermes-sync-banks` cron job, including cron-mode constraints and data extraction techniques.

## Troubleshooting

- **Sync script fails**: check `REPO_DIR` and `HERMES_HOME` env vars
- **Cron not firing**: verify with `cronjob(action='list')`
- **Agent-driven cron fails**: check Hindsight MCP server is reachable
- **Duplicate skills**: remove the duplicate from `hermes-skills/` subdir
- **execute_code blocked in cron mode**: `approvals.cron_mode` prevents execute_code. Use `terminal()` with inline Python instead for data processing.

## Verification

```bash
cronjob(action='list')
ls infrastructure/hermes/
bash infrastructure/hermes/sync-hermes-to-repo.sh
```
