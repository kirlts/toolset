# TODO: [Project Name] v0.1.0

> Direct traceability: each task references checks from `VERIFICATION.md`.

## Kairós Symbol Legend

| Symbol | Meaning |
|---|---|
| 🤖 | Check verifiable by AI/automated tool |
| 🧑 | Check requiring human verification |
| 🤖🧑 | Check pre-verifiable by AI, final human validation |
| ⏳ | In progress |
| 🔲 | Pending |
| 🚨 | Critical block |

---

## [EPIC-001] [Descriptive epic name]

> Ref: MASTER-SPEC §[N]

### [TASK-001] [Descriptive task name]

> Ref: MASTER-SPEC §[N]

**Covered checks:** `[ACTOR.CAT.NN.LLM]`, `[ACTOR.CAT.NN.HUM]`

- [ ] [Atomic subtask 1]
- [ ] [Atomic subtask 2]

<!-- 
COMPLETION TIMESTAMP FORMAT:
- [x] Subtask completed `YYYY-MM-DD HH:MM:SS`

CLOSING RULE CONDITIONED BY VERIFIER TYPE:
- Tasks EXCLUSIVELY containing .LLM checks: the AI can close them autonomously with a timestamp.
  Format: - [x] [TASK-NNN]; YYYY-MM-DD HH:MM [🤖 Verified by tool]
- Tasks containing AT LEAST ONE .HUM or .MIX check: the AI CANNOT mark it as completed
  without explicit user confirmation.
  Format: - [x] [TASK-NNN]; YYYY-MM-DD HH:MM [🧑 Verified by user]
  Format: - [x] [TASK-NNN]; YYYY-MM-DD HH:MM [🤖🧑 Pre-verified + confirmed by user]

GENERAL RULES:
- Every TASK must have the "Covered checks:" field with VERIFICATION.md IDs (including .LLM/.HUM/.MIX suffix).
- If the task is purely governance: **Covered checks:** Transversal governance
- Timestamps are mandatory when marking a subtask as completed.
- It is FORBIDDEN to use generic terms like "active" or leave the field empty.
-->

---

## Overall Coverage Summary

| Epic | Tasks | Status | 🤖 .LLM | 🧑 .HUM | 🤖🧑 .MIX | Total Checks |
| --- | --- | --- | --- | --- | --- | --- |
| EPIC-001 | TASK-001 to NNN | ☐ In progress | [N] | [N] | [N] | [N] |
