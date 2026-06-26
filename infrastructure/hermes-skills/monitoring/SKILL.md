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

"Monitor" does NOT mean sending periodic messages to the user. It means:

1. Run health checks (see skill `toolset-ops`)
2. Evaluate the result
3. **Only report to user on failure or state change**
4. If all OK, send NO message

## Update Frequency

Maximum one status update every 30 seconds per monitored service. If no state change, no message.

## Messages

| Situation | Action | Frequency |
|---|---|---|
| All OK | Silence. No report. | N/A |
| Service down | Report immediately via WhatsApp: "[Service] is down. Status: [detail]" | Immediate, then max 1/30s |
| Auto-recovery | Report: "[Service] recovered." | Immediate |
| Persistent failure (>3 consecutive checks) | Report + suggest remediation action. | Once per state transition |

## Anti-patterns

- Periodic "all OK" messages when nothing changed — noise. Do not send.
- "Everything is fine, I will keep monitoring" — noise. Do not send.
- "Do you want me to keep monitoring?" — the user already gave the order.
- Status updates faster than 30s per service — throttled.
- Re-reporting the same failure state without a state change.
