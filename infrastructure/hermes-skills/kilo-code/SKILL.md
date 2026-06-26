---
name: kilo-code
description: "Delegate heavy coding tasks to Kilo Code CLI autonomous mode."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [Coding, Kilo, Automation, Subagent]
    triggers: ["code", "implement", "feature", "fix bug", "refactor", "write test"]
---

# Kilo Code CLI — Autonomous Coding Subagent

## Overview

Kilo Code CLI (`kilo run --auto`) is the preferred subagent for heavy coding tasks.
It uses the same provider/model config as local Kilo (`~/.config/kilo/kilo.jsonc`).

## Invocation

```bash
kilo run "TASK DESCRIPTION" --auto --dir /path/to/repo
```

The `--auto` flag enables autonomous non-interactive mode. The `--dir` flag sets the working directory.

## When to Delegate

| Task Type | Threshold | Action |
|---|---|---|
| Simple (typo, comment, rename) | <5 lines | Edit directly |
| Moderate (small feature, single function) | 5-50 lines | Edit directly |
| Complex (multi-file, architecture change) | >50 lines | Delegate to `kilo run --auto` |
| Test suite | Any | Delegate |

## Workflow

1. User requests code change
2. If >50 lines expected: `kilo run "DESCRIPTION" --auto --dir /workspace/repo`
3. Wait for exit code (0=success, 124=timeout, 1=error)
4. Report summary to user — NOT the full kilo output

## Rules (MASTER-SPEC §8)

- **KILO-01**: Use repo workdir, pass context via `kilo run "task" --auto --dir <path>`
- **KILO-02**: Never pipe Kilo output raw to user — summarize

## Anti-patterns

❌ Delegating trivial changes (wastes time)
❌ Showing Kilo's full tool-call log to user
❌ Running `kilo` without `--auto` (blocks on prompts)
