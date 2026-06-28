---
name: whatsapp-router
description: "Deterministic routing of WhatsApp group messages to repo-specific worker profiles via Kanban. Zero LLM judgment for routing decisions."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [routing, whatsapp, kanban, multi-profile]
    triggers: ["message", "/onboarding"]
---

# WhatsApp Group Router

## When Activated

This skill fires on EVERY incoming WhatsApp group message. DMs route to the
default profile (orchestrator) without delegation.

## Files

- `~/.hermes/whatsapp-groups.yaml` — mapping: JID → repo → profile
- `~/.hermes/channel_aliases.json` — JID → human-readable name
- `~/.hermes/channel_directory.json` — auto-discovered channels

## Routing Algorithm (DETERMINISTIC)

1. Extract `chat_id` from session origin (`remoteJid`)
2. If DM (`chat_id` ends with `@lid` or `@s.whatsapp.net`): route to default profile
3. If message starts with `/onboarding` → trigger `group-onboarding` skill (separate SKILL.md)
4. Look up `chat_id` in `~/.hermes/whatsapp-groups.yaml`
5. If found:
   a. Execute `recall(bank="<repo>")` from Hindsight
   b. Create Kanban task: `kanban_create(
        title="<user message>",
        assignee="<profile>",
        body="<full message text>",
        skills=["<skills>"]
      )`
   c. Respond: "⏳ Delegando a <profile>..."
6. If NOT found: respond "Este grupo no está configurado. Usa /onboarding."

## Rules

- **No LLM judgment for routing.** Routing decisions come from whatsapp-groups.yaml.
- Every incoming group message triggers `recall(bank=repo)` before delegation.
- Kanban tasks use `--skill` from the mapping file for worker context.
