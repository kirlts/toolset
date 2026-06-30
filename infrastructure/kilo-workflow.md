# Kilo CLI — Mandatory Workflow

> This file is loaded by Kilo CLI via `kilo.jsonc` `instructions` array.
> Applies to ALL agent modes: `kilo run`, `kilo run --auto`, `kilo run --build`.

## Mandatory Session Workflow

You MUST follow this workflow in EVERY session, regardless of the task.

### Session Start (before any modifications)
1. **Load context** — `recall(bank=<repo>)` to load project state, recent decisions, TODO.
2. **Execute `/document`** — synchronize MASTER-SPEC, TODO, MEMORY, USER-DECISIONS, CHANGELOG. This is mandatory even if you think nothing changed.
3. **Review repository governance** — confirm `.agents/rules/*.md` constraints and `docs/RULES.md`.

### During Work
4. **Execute `/document` after substantial changes** — refactor, architecture change, dependency update, or feature completion.

### Session End (before reporting to Hermes)
5. **Execute `/document`** — final documentary sync.
6. **Use `reflect`** — synthesize session outcomes via Hindsight.
7. **Use `retain(bank=<repo>)`** — persist session summary, key decisions, code changes, test results.

## Timeout Handling

If you anticipate a long-running operation (retain, reflect, large /document), inform the caller so they can use async invocation. The default terminal timeout is 180s.

## Quality

- Zero tolerance for: corporate filler, empty adjectives, mocked data, em dashes.
- Every deliverable backed by real tool output.
- Report concise summaries: what was done, what changed, test results, decisions needing human approval.
