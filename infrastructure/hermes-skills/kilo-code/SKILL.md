---
name: kilo-code
description: "Delegate coding tasks to Kilo Code CLI (features, PRs, refactors, tests)."
version: 1.0.0
author: Toolset Personal
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Coding-Agent, Kilo, OpenCode, Code-Review, Refactoring, Automation]
    related_skills: [claude-code, codex, hermes-agent, opencode]
---

# Kilo Code — Hermes Orchestration Guide

Delegate coding tasks to [Kilo Code CLI](https://kilo.ai/docs/code-with-ai/platforms/cli) (`@kilocode/cli`) via the Hermes terminal. Uses the same `~/.config/kilo/kilo.jsonc` config as the local Kilo Code (VS Code extension).

## Prerequisites

- **Install:** `npm install -g @kilocode/cli` (installed — v7.3.54)
- **Auth:** uses `OPENCODE_GO_API_KEY` from .env. No additional login.
- **Config:** `~/.config/kilo/kilo.jsonc` with OpenCode Go provider, models, MCPs.
- **Verify:** `kilo --version`

## When to Delegate to Kilo Code

| Situation | Delegate to Kilo? |
|---|---|
| Task producing >50 lines of code | YES — `kilo run --auto` |
| Full module refactor | YES |
| Tests for a feature | YES |
| Simple bug fix (<50 lines) | NO — resolve directly or `delegate_task()` |
| Read files, analyze code | NO — terminal/read_file directly |
| Git operations (commit, push, PR) | NO — terminal/gh CLI directly |
| Changes requiring PR + merge | YES — `kilo run --auto` + gh CLI for PR |

General rule: if estimated output >50 lines or multi-file, delegate to `kilo run --auto`.

## Autonomous Mode

```
terminal(command="kilo run 'Task description' --auto", workdir="/path/to/repo", timeout=180)
```

**Flags:**
| Flag | Purpose |
|---|---|
| `--auto` | Autonomous mode. Exit 0 = success, 124 = timeout, 1 = error. |
| `--model <name>` | Specify model (only `deepseek-v4-flash` available). |
| `--continue` | Resume previous session. |
| `--file <path>` | Pass file(s) as context. |

## Strategy

1. Analyze the requirement.
2. If >50 lines or multi-file → `kilo run "task" --auto`.
3. Monitor progress. If timeout (exit 124), split into smaller subtasks.
4. Verify result and report.

## Quick Reference

```
# Feature task
kilo run "Implement GET /api/users endpoint in auth module, following existing pattern in src/auth/" --auto

# Refactor
kilo run "Refactor src/processor.py: extract validation logic to separate module, add type hints" --auto

# Tests
kilo run "Add unit tests for PaymentService class in tests/test_payment.py" --auto

# Bug fix
kilo run "Fix bug in src/inventory.py where stock does not update after return" --auto
```
