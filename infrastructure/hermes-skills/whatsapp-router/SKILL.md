---
name: whatsapp-router
description: "Deterministic routing of WhatsApp group messages. Routes based on whatsapp-groups.yaml profile field. No predefined categories."
version: 4.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [routing, whatsapp, kanban]
    triggers: ["message"]
---

# WhatsApp Group Router

## Routing Algorithm

1. Extract `chat_id` from session origin.
2. DM (`@lid` or `@s.whatsapp.net`) → orchestrator. No delegation.
3. Group → lookup `chat_id` in `~/.hermes/whatsapp-groups.yaml`.

If the entry has a `profile`:
- `default` → orchestrator. No Kanban.
- Any other profile → `recall(bank=<name>-profile>)` + if repo: `recall(bank=<repo>)`. Kanban with `metadata.originating_group`.

If `readonly: true`: ignore.

If no profile or not found: "not configured, use /onboarding."

### Kanban Task Metadata

```
metadata = {
  "originating_group": "<chat_id>",
  "originating_channel": "whatsapp",
  "group_name": "<name from channel_aliases.json>"
}
```

The orchestrator uses `originating_group` to route completion responses back to the correct WhatsApp group.

## Inter-Profile Delegation

When a worker delegates to another profile, it must propagate the original `originating_group`:
```
kanban_create(assignee="<otro>", metadata={originating_group: "<original JID>"})
```
The response always returns to the WhatsApp group where the user sent the first message.

## Group Description

Every group loads `description` from `channel_aliases.json`. The user can edit the WhatsApp group description at any time; Hermes picks it up within 10 minutes via cron.
