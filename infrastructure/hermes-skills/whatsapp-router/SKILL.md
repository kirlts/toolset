---
name: whatsapp-router
description: "Deterministic routing of WhatsApp group messages based on group type. Zero LLM judgment for routing decisions."
version: 2.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [routing, whatsapp, kanban, multi-profile]
    triggers: ["message", "/onboarding"]
---

# WhatsApp Group Router

## When Activated

This skill fires when the SOUL.md routing algorithm determines a WhatsApp group
message needs processing. DMs route to default profile (orchestrator).

## Files

- `~/.hermes/whatsapp-groups.yaml` — mapping: JID → type + config
- `~/.hermes/channel_aliases.json` — JID → human-readable name
- `~/.hermes/channel_directory.json` — auto-discovered channels

## Routing by Group Type (DETERMINISTIC)

After SOUL.md identifies the group type from whatsapp-groups.yaml:

### `type: coding`
1. Execute `recall(bank="<repo>")`
2. Create Kanban: `kanban_create(title="<msg>", assignee="<profile>", body="<msg>", skills=["<skills>"])`
3. Respond "⏳ <profile> procesando..."

### `type: research`
1. Execute `recall(bank="<group-name>-profile")`
2. If repo specified: also `recall(bank="<repo>")`
3. Delegate via Kanban with research skills
4. Respond "🔬 Investigando..."

### `type: personal`
1. Respond as orchestrator (no delegation)
2. Use bank `<group-name>-profile` for memory
3. Load group `description` as context

### `type: custom`
1. Load `description` as context
2. No automatic delegation
3. Use bank `<group-name>-profile` for memory
4. Hermes decides based on context + description

### `type: announcements` or `readonly: true`
1. Ignore completely — no response

## Rules

- **No LLM judgment for routing.** Type and target come from whatsapp-groups.yaml.
- Every group has a bank: `<group-name>-profile`
- `description` field is loaded as context for every group type
- DMs ALWAYS route to orchestrator (SOUL.md default personality)
