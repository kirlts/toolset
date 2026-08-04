---
name: kanban-operations
description: "Kanban task lifecycle: create, monitor, and route completions. Kanban tools are only available via delegate_task() with toolsets=['kanban'] — they are NOT direct gateway tools."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [kanban, orchestration, delegation, routing]
    triggers: ["kanban", "kanban_create", "create task", "board"]
---

# Kanban Operations

## Tool Availability

**CRITICAL:** Kanban tools (`kanban_create`, `kanban_list`, `kanban_get_status`, `kanban_complete`, etc.) are NOT available as direct tools in the Hermes gateway session. They are only accessible via `delegate_task()` with `toolsets=["kanban"]`.

## Creating a Kanban Task

Use `delegate_task` to spawn a subagent with the kanban toolset:

```
delegate_task(
    goal="Create kanban task: <title> for <assignee>",
    context="Call kanban_create() with these exact parameters:\n" +
            "  title: <str>\n" +
            "  assignee: <str> (worker profile name)\n" +
            "  body: <str> (task description)\n" +
            "  skills: [<list of skill names>]\n" +
            "  metadata: {<key-value dict>}",
    toolsets=["kanban"]
)
```

The subagent executes `kanban_create()` and reports back the task ID and board status.

## Kanban Task Metadata (WhatsApp Routing)

When routing from WhatsApp groups, each kanban task MUST include:

```python
metadata = {
    "originating_group": "<chat_id>",
    "originating_channel": "whatsapp",
    "group_name": "<human name from channel_aliases.json>"
}
```

The orchestrator uses `originating_group` to route the kanban completion response back to the correct WhatsApp group.

## Completion Monitoring

The orchestrator monitors kanban completions via subagent reports. When a completion arrives with `metadata.originating_group`:

1. Resolve the JID to human name via `channel_aliases.json`
2. Send the summary to the originating WhatsApp group
3. If the summary exceeds WhatsApp limits, resumir a 2-3 lineas

## Related Skills

- **whatsapp-router** — defines the routing algorithm that triggers kanban creation from WhatsApp groups. The metadata schema for `originating_group`/`originating_channel`/`group_name` is defined there.

## Pitfalls

- Do NOT try to call `kanban_create` directly — it doesn't exist in the gateway tool list.
- The subagent's summary is a self-report; verify task creation was acknowledged.
- Kanban config lives in `~/.hermes/config.yaml` under `kanban:` key — check there for settings like `auto_decompose`, `dispatch_interval_seconds`, and `failure_limit`.
- Worker profile names (assignee) must match profiles defined in the config.
