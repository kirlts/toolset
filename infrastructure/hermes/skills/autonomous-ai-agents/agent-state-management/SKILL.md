---
name: agent-state-management
description: "Manage an autonomous agent's evolving state across sessions, deploys, and time — catalog auto-generated artifacts, sync to version control, consolidate Hindsight memory, and persist through CI/CD."
version: 1.0.0
author: Toolset Personal
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [state-management, versioning, hindsight, memory-lifecycle, ci-cd, persistence, sync]
    related_skills: [project-orientation, hindsight-memory-lifecycle]
---

# Agent State Management

Autonomous agents like Hermes generate, modify, and curate their own configuration, skills, memory, and identity files. This skill covers the lifecycle of those auto-generated artifacts — what they are, what to version, and how to keep them durable across sessions, rebuilds, and CI/CD deploys.

## Core Principle: The Agent as a Living System

An agent's state is not static. Skills grow, memory accumulates, identity adapts. Treating agent state as a deployable artifact (versioned, synced, recoverable) prevents knowledge loss on instance rebuild and keeps the agent consistent across environments.

## Auto-Generated Artifacts Catalog

### Tier 1: Always Version in Project Repo

| Artifact | Path | Content | Sync Direction |
|---|---|---|---|
| **SOUL.md** | `~/.hermes/SOUL.md` | Agent identity, capabilities, rules, tone | Bidirectional — repo → instance (deploy), instance → repo (cron) |
| **Skills (agent-created)** | `~/.hermes/skills/` | Procedural knowledge, one SKILL.md per skill | Instance → repo (periodic sync). Bundled/hub skills excluded. |
| **config.yaml** (structural) | `~/.hermes/config.yaml` | Provider, platform, toolset config (without secrets) | Bidirectional |
| **Scripts** | `~/.hermes/scripts/` | User/agent-created shell scripts | Instance → repo |
| **Hooks** | `~/.hermes/hooks/` | Event-driven gateway hooks | If used, instance → repo |

### Tier 2: Snapshot Periodically

| Artifact | Path | Content | Sync Cadence |
|---|---|---|---|
| **MEMORY.md** | `~/.hermes/memories/MEMORY.md` | Environment notes, tool quirks, conventions | Daily or per deploy |
| **USER.md** | `~/.hermes/memories/USER.md` | User profile, preferences, style | Daily or per deploy |
| **Hindsight banks** | PostgreSQL (Hindsight DB) | Durable memory store (facts, observations, experiences) | Weekly JSON export |
| **Cron job definitions** | `~/.hermes/cron/` | Scheduled job metadata | Document existence in repo |

### Tier 3: Don't Version (Runtime State)

Session DB (`state.db`), sessions/ (transcripts), cron/output/, logs/, caches, auth tokens, WhatsApp session data, gateway state, locks.

## Session Initialization Protocol

Every session must load context from Hindsight before reading files. Per `project-orientation` skill:

```
1. Recall project bank (broad query, high budget)
2. Recall user profile bank (bank "hermes", broad query, high budget)
3. Scan both for key categories
4. Proceed to repo docs (REPOMAP → MASTER-SPEC → RULES → ...)
```

## Session Awareness Protocol

When the user asks about your current status — e.g. "qué haces", "en qué estás", "what are you doing", "que estas haciendo" — do NOT assume idle. Follow these steps:

1. **Call `session_search()` with no arguments** — browse mode returns ALL active sessions with source, message count, last activity time
2. **Check background processes** via `process(action='list')`
3. **Check cron jobs** via `cronjob(action='list')`
4. **Synthesize results** — do NOT report just processes/cron; session_search may reveal active WebUI, CLI, or other sessions

**Correction (24 Jun 2026):** The agent responded "nada corriendo" while the user had a 305-message WebUI session active. The user explicitly corrected that ALL active sessions must be checked, not just OS processes.

### Example flow

```
session_search()        → 3 sessions (WhatsApp, 2x WebUI)
process(action='list')  → 0 running processes
cronjob(action='list')  → 2 cron jobs, both healthy
Result: WebUI session with 305 msgs active + 2 cron jobs scheduled. Not idle.
```

**Do NOT include**: `ps aux`, `systemctl`, `docker ps`, hardware metrics, or any info that wasn't asked for.

### Related pitfall

This protocol only applies when the user explicitly asks about your status. For routine work, session awareness is handled by the gateway — you don't need to poll session state on every turn.

## Lifecycle Automation Patterns

### Daily Hindsight Consolidation (Bank Sync)

A cron job that exports ALL Hindsight banks to JSON, synthesizes a daily summary via reflect+retain, and commits to version control. Runs daily (currently 2 AM UTC).

#### Workflow

```
1. list_banks()              → discover all banks, skip "default"
2. list_memories(limit=1000) → export every bank sequentially
   - Banks with <1000 facts: one call, no pagination
   - Banks with >1000 facts: paginate with offset=1000
3. Save each export as: infrastructure/hermes/banks/<BANK_ID>/YYYY-MM-DD.json
4. reflect(bank_id=BANK_ID, query="daily synthesis")   → per bank
5. retain(bank_id=BANK_ID, content=reflect_result,     → per bank
     tags=["daily-summary", "YYYY-MM-DD", "BANK_ID"])
6. git pull --rebase + add + commit + push
```

#### MCP Output Persistence

When calling `list_memories` (or any MCP tool that returns large data):

- **Output > ~200K chars** → auto-saved to `/tmp/hermes-results/call_*.txt`. Copy from there to the target path.
- **Output < ~200K chars** → returned inline in the tool result. Save via `write_file()` or `terminal()` with a Python script that constructs the JSON.
- **`execute_code` is BLOCKED in cron mode** (no user present to approve). Use `terminal()` with inline Python (`python3 << 'EOF'...EOF`) for data processing instead.

```yaml
# Cron definition (in ~/.hermes/cron/jobs.json):
schedule: "0 2 * * *"
prompt: >
  Ejecuta el workflow de sincronización diaria de TODOS los banks de Hindsight:
  1. list_banks() → descubre todos (ignora "default")
  2. list_memories(limit=1000) → exporta cada bank como JSON
  3. reflect + retain diario sobre cada bank
  4. git pull --rebase + add + commit + push
skill: agent-state-management
```

#### Pitfalls

- **Mismatched file format**: Some MCP tool outputs come as `{"result": "<escaped JSON string>", "structuredContent": {...}}`. All bank files use this exact wrapper format — not just the inner items array.
- **Partial dumps**: When the tool result is inline (small output), manually extracting all items into a file can miss items. If a bank has significant facts but the tool returned them inline, re-query or use a Python script via `terminal()` instead of `write_file()`.
- **Sequential required**: `list_memories` calls can be parallelized (independent reads), but `reflect` + `retain` must be sequential per bank (each reflect is stateful).

### Periodic Git Sync (Instance → Repo)

A script (`sync-hermes-to-repo.sh`) that runs on cron or pre-deploy:

```bash
#!/usr/bin/env bash
# sync-hermes-to-repo.sh — syncs auto-generated Hermes state to toolset repo
set -euo pipefail

REPO_DIR="/home/opc/workspace/toolset/infrastructure/hermes"

# SOUL.md
cp ~/.hermes/SOUL.md           "$REPO_DIR/SOUL.md"

# Config (strip secrets)
cp ~/.hermes/config.yaml       "$REPO_DIR/config.yaml"

# Memories
cp ~/.hermes/memories/MEMORY.md "$REPO_DIR/memory/MEMORY.md"
cp ~/.hermes/memories/USER.md   "$REPO_DIR/memory/USER.md"

# Skills (agent-created only — from hermes-skills/ directory)
rsync -a --delete ~/.hermes/skills/hermes-skills/ "$REPO_DIR/skills/"

# Scripts
rsync -a --delete ~/.hermes/scripts/ "$REPO_DIR/scripts/"

# Commit
cd "$REPO_DIR/../.."
git add infrastructure/hermes/
git commit -m "hermes-sync: $(date -I)"
git push
```

### Bank Export / Import (Versioning)

Export Hindsight banks to JSON for version control backup. The current approach uses MCP tools (not curl):

```bash
# Discovery + export via MCP tools (run in session or cron):
# 1. list_banks() → identifies all banks (skip "default")
# 2. For each bank: list_memories(bank_id=BANK_ID, limit=1000)
# 3. Save result to infrastructure/hermes/banks/BANK_ID/$(date -I).json
# 4. reflect + retain daily summary per bank
# 5. git add + commit + push
```

Full workflow documented in **Daily Hindsight Consolidation (Bank Sync)** section above.

**Legacy curl approach** (alternative, non-MCP path — not currently in use):
```bash
# Export all banks — requires Hindsight API key
for bank in hermes toolset; do
  curl -s "https://funnel/banks/$bank/export" \
    -H "Authorization: Bearer $HINDSIGHT_API_KEY" \
    > "infrastructure/hermes/banks/$bank-$(date -I).json"
done
```

### Deploy-time Post-Restore

After CI/CD deploy, restore agent state:

```bash
# In deploy.sh, after services are up:
cp infrastructure/hermes/SOUL.md     ~/.hermes/SOUL.md
cp infrastructure/hermes/config.yaml ~/.hermes/config.yaml
rsync -a infrastructure/hermes/skills/ ~/.hermes/skills/
rsync -a infrastructure/hermes/scripts/ ~/.hermes/scripts/

# Import bank snapshots (last 2 kept)
for f in infrastructure/hermes/banks/hermes-*.json; do
  curl -s -X POST "https://funnel/banks/hermes/import" \
    -H "Content-Type: application/json" \
    -d @"$f"
  break  # most recent only
done
```

## Pitfalls

1. **Sync only one direction** — if you sync repo → instance on deploy but never instance → repo, all agent learning since last deploy is lost. Always sync both ways.

2. **Versioning secrets** — `config.yaml` can contain platform tokens (WhatsApp session keys, etc.). Strip these before committing, or use a template with secrets injected via Infisical.

3. **Over-versioning runtime state** — session DB, logs, and caches change constantly and bloat the repo. Stick to the Tier 1/2 catalog above.

4. **Assuming bank export is a backup** — JSON exports capture the memory content but not the embeddings or vector index. Full disaster recovery requires PostgreSQL dump of the Hindsight database.

5. **Forgetting to restore skills post-deploy** — if deploy.sh overwrites `~/.hermes/skills/` without restoring from the repo, agent-created skills vanish. Always include a restore step.

## References

- `references/auto-generated-artifacts.md` — Official Hermes docs catalog (in hermes-agent skill)
- `references/kairos-governance-files.md` — Kairos file structure and bank naming (in project-orientation skill)
