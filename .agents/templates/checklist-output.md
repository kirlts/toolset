# Verification Checklist: [Subject Name]

> **Domain:** [Determined during Phase 0.5]
> **Audience:** [Determined during Phase 0.5]
> **Generated:** [Date]
> **Source:** [Brief description of the input that generated this checklist]

---

## Kairós Symbol Legend

| Symbol | Meaning |
|---|---|
| 🤖 `.LLM` | Automatable / deterministic verification |
| 🧑 `.HUM` | Requires human judgment |
| 🤖🧑 `.MIX` | Pre-filterable, final human validation |

## Source Context
<!-- One to two sentences describing the input that was analyzed. This provides traceability without exposing the working document. -->
[pending]

## Author-Provided Rules
<!-- If the input contained explicit acceptance criteria provided by the human, list them here verbatim. If none, delete this section entirely. -->
-

---

## Abbreviation Key
<!-- Include the abbreviation key from Phase 4 so readers can decode check IDs. -->
| Full Name | Abbreviation | Type |
|---|---|---|
| [pending] | [pending] | Actor / Category |
| Verifiable by automated tool | LLM | Verifier |
| Requires human verification | HUM | Verifier |
| Pre-verifiable, final human validation | MIX | Verifier |

## [Actor Name 1]
<!-- Extract checks from Phase 4 VERBATIM. Do NOT rephrase, soften, or generalize the check text. Semantic identity between Phase 4 and this document is mandatory. Group checks by actor. Use domain-native actor names. -->
- 🧑 `[ACTOR-CAT-NNN.HUM]` [Observable Action] → [Expected Result].
- 🤖 `[ACTOR-CAT-NNN.LLM]` [Observable Action] → [Expected Result].
- 🤖🧑 `[ACTOR-CAT-NNN.MIX]` [Observable Action] → [Expected Result].

## [Actor Name 2]
- 🧑 `[ACTOR-CAT-NNN.HUM]` [Observable Action] → [Expected Result].

---

## Summary
| Actor | 🤖 .LLM | 🧑 .HUM | 🤖🧑 .MIX | Total |
|---|---|---|---|---|
| [Actor 1] | [N] | [N] | [N] | [N] |
| [Actor 2] | [N] | [N] | [N] | [N] |
| **Total** | **[N]** | **[N]** | **[N]** | **[N]** |
