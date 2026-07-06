# Kilo Hang Diagnosis — 2026-07-05

## Incident Summary

Kilo CLI v7.3.54 was invoked with a ~4,000-word prompt containing detailed line-by-line instructions for modifying 3 files in the toolset repo. The process ran for 8+ minutes, generated 359KB of log data (~35K tokens), but executed ZERO tool calls — no file edits, no git operations, no MCP calls.

## Evidence

- **Kilo log:** 4,449 lines, of which 4,419 were `message.part.updated` (streaming tokens from model)
- **Last real event:** `snapshot prune` at 16:50:29. After that: only streaming for 8+ minutes
- **Network:** Zero TCP connections in the final 8 minutes (lsof showed no ESTABLISHED)
- **File changes:** Zero — git status never changed during execution
- **Process state:** Child node process running at 20% CPU, 381MB RSS, with an "HTTP Client" thread but no sockets

## Root Cause Analysis

Two competing causes were identified:

### Cause 2 (confirmed trigger): Prompt too large
The prompt Hermes passed to Kilo was ~4,000 words with exact line-by-line replacements. deepseek-v4-flash treated this as a text generation task (produce analysis/explanation) rather than an execution task (produce tool calls). The model never reached the point of executing tool calls because it was busy generating explanatory text.

### Cause 1 (systemic risk): Hindsight recall flooding
Kilo's system prompt (`infrastructure/kilo-system-prompt.md`) instructs:
```
Al iniciar: hindsight-selfhosted_recall(bank=<nombre-del-repo>-profile)
```
This recall has NO max_tokens or budget parameters. Even though it didn't execute in this incident (Cause 2 prevented it), if it HAD executed against a large bank, the context could have been flooded.

**Conclusive test:** `recall(bank="toolset", max_tokens=16384, budget="high")` returned 629,549 characters (>600KB). If Kilo had executed this recall before processing the user prompt, the combined context would have exceeded the model's effective working memory.

### Additional contributing factor: Bank naming ambiguity
The system prompt says `bank=<...>-profile` but `docs/RULES.md` (loaded as a Kilo instructions file) says "use repo name as bank_id, kebab-case". These are contradictory. Depending on which instruction Kilo follows, it could recall from `toolset` (741 facts) or `toolset-profile` (2 facts).

## Protocol Established

1. Never pass Kilo prompts >500 words
2. For complex multi-file changes, use a Python script + git pattern
3. Never use bash sed on GitHub Actions YAML (${{ }} breaks sed)
4. Check git status after 30s — no changes = potential hang
5. Check Kilo log for `message.part.updated` without other events = hang
6. ALL recall calls must specify max_tokens and budget explicitly
7. Diagnose first, present findings, then act — never make changes during diagnosis

## Files Modified During Diagnosis

- `infrastructure/kilo-system-prompt.md` — needs: recall params, bank name disambiguation
- `infrastructure/kilo-prompt.md` — [DEPRECATED] should be removed
- `docs/RULES.md` — needs: bank naming convention updated to `<profile>-profile`
- `infrastructure/hermes/profiles/toolset/SOUL.md` — needs: recall/retain rules added
- Various skills referencing `bank="toolset"` → `bank="toolset-profile"`
- `.agents/templates/profile-soul.md` — needs: budget lowered from `high` to `mid`
