---
name: whatsapp-router
description: "Deterministic routing of WhatsApp group messages based on group type. Includes Kanban metadata for response routing back to originating group."
version: 3.0.0
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
3. Group → read `~/.hermes/whatsapp-groups.yaml`.
4. Lookup `chat_id`. Route by `type` field.

### Routing by type

| type | Action | Delegation | Bank |
|---|---|---|---|
| `coding` | `recall(bank=<repo>)` → Kanban to `<profile>` | Yes | `<repo>` + `<name>-profile` |
| `research` | `recall(bank=<name>-profile>)` → Kanban | Yes | `<name>-profile` |
| `personal` | Respond as orchestrator | No | `<name>-profile` |
| `custom` | Load `description` as context | No | `<name>-profile` |
| `announcements` | Ignore | No | — |

### Kanban Task Metadata

Every `kanban_create()` from this router includes:

```
metadata = {
  "originating_group": "<chat_id>",
  "originating_channel": "whatsapp",
  "group_name": "<human name from channel_aliases.json>"
}
```

The orchestrator uses `originating_group` to route the Kanban completion response back to the correct WhatsApp group.

## Group Description

Every group type loads `description` from `channel_aliases.json` (populated by `populate-channel-aliases.sh` via bridge `GET /chat/:id`). The description originates from WhatsApp group metadata (`groupMetadata().desc`).
