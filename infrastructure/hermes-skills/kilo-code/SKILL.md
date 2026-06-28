---
name: kilo-code
description: "Execute tasks in repositories with governance rules via Kilo Code CLI autonomous mode."
version: 2.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [Coding, Kilo, Automation, Subagent]
    triggers: ["code", "implement", "feature", "fix bug", "refactor", "write test"]
---

# Kilo Code CLI — Autonomous Coding Subagent

## Overview

Kilo Code CLI executes tasks inside cloned repositories. It reads each repository's local `.agents/` governance rules and applies them during execution. Hermes is the conversational orchestrator — it delegates repository work to Kilo CLI rather than editing files directly in governed repos.

## Invocation

```bash
kilo run "TASK" --auto --dir /path/to/repo
```

`--auto`: autonomous non-interactive mode. `--dir`: target repository working directory.

## Delegation Rules

| Condition | Execution path |
|---|---|
| Repository has `.agents/` directory | **Kilo CLI exclusively.** Hermes does not read or write files directly. Every operation — typo fix, refactor, architecture change — goes through Kilo CLI. |
| Repository has no `.agents/` | Hermes may edit directly. Kilo CLI recommended for changes exceeding 50 lines across multiple files. |
| Onboarding defined an explicit override | The override applies. The user was informed transparently during onboarding. |

**Rationale.** Repositories with `.agents/` contain governance rules (constraints, verification checklists, decision records) that Kilo CLI evaluates autonomously. Hermes lacks the internal agent system and rule-resolution pipeline that Kilo provides. Bypassing Kilo in governed repos would silently skip those rules — a governance violation.

## Workflow

1. User requests work in a governed repository.
2. Hermes constructs a task prompt with context: user intent, relevant files, change scope. The prompt does not include instructions on how to execute — Kilo CLI reads those from the repo's `.agents/`.
3. `kilo run "TASK" --auto --dir /workspace/repo`
4. Wait for exit code (0=success, 124=timeout, 1=error).
5. Report summary to user — NOT the full Kilo output.

## Rules

- **KILO-01**: Use repo workdir, pass context via `kilo run "task" --auto --dir <path>`.
- **KILO-02**: Never pipe Kilo output raw to user — summarize.
- **KILO-03**: If the repo has `.agents/`, Kilo CLI is the only path. No exceptions unless onboarding defined one transparently.

## Anti-patterns

- Delegating a governed-repo operation to Hermes directly (bypasses `.agents/` rules).
- Showing Kilo's full tool-call log to user.
- Running `kilo` without `--auto` (blocks on prompts).
