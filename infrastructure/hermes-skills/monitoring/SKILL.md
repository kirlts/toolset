---
name: monitoring
description: "Service monitoring and alert protocols for Toolset Personal."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [Monitoring, Alerts, Health, Status]
---

# Monitoring Protocol

## Definition

"Monitor" means state-transition reporting, not periodic messaging:

1. Run health checks (see skill `toolset-ops`)
2. Evaluate result against previous state
3. Report only on failure or state change
4. Silence when all OK

## Message Rules

| Situation | Action | Frequency |
|---|---|---|
| All OK | No message | Never |
| Service down | "[Service] is down. Status: [detail]" via WhatsApp | Immediate, then max 1/30s |
| Auto-recovery | "[Service] recovered." | Once per transition |
| Persistent failure (>3 consecutive) | Report + suggest remediation | Once per transition |

## Anti-patterns

- Periodic "all OK" messages when nothing changed
- "Everything is fine, I will keep monitoring"
- "Do you want me to keep monitoring?" — the order was already given
- Re-reporting the same failure without a state change
- Status updates faster than 30s per service
