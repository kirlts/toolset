# WhatsApp Group Activity Verification

Used by: daily consolidation cron jobs, health checks, and any scenario where
you need to determine if a WhatsApp group had messages today.

## Sources of truth (in order of reliability)

| Source | What it tells you | How to query |
|---|---|---|
| `gateway.log` | Inbound messages Hermes processed for the group | `grep "<JID>@g.us" /home/opc/.hermes/logs/gateway.log \| grep "inbound message"` |
| `agent.log` | Full conversation turns Hermes ran for the group | `grep "<JID>" /home/opc/.hermes/logs/agent.log \| grep "conversation turn"` |
| Bridge health endpoint | Liveness + queue depth | `curl -sf http://localhost:3000/health` |
| `channel_directory.json` | All discovered groups/chats + last update | `jq '.platforms.whatsapp[] \| select(.id | startswith("120363"))' ~/.hermes/channel_directory.json` |
| `channel_aliases.json` | Human-readable group names + descriptions | Direct read |
| `bridge.log` | Bridge connection state over time | `tail -50 ~/.hermes/whatsapp/bridge.log \| grep "✅\|❌\|stream errored"` |

## Procedure

### 1. Confirm the group exists and find its JID

Two registries:

- **`~/.hermes/channel_aliases.json`** — authoritative group names/descriptions from WhatsApp.
  The `desc` field has priority over `whatsapp-groups.yaml.description` for operational context.

- **`~/.hermes/whatsapp-groups.yaml`** — profile-to-group mapping. Not all groups are mapped here;
  many groups exist only in `channel_aliases.json`.

If the group JID you're looking for isn't in either file, the group hasn't been
discovered by the bridge yet (see toolset-ops: "New group discovery").

### 2. Check for activity today

```bash
# All inbound messages for a group (most reliable)
grep "<JID>@g.us" /home/opc/.hermes/logs/gateway.log | grep "inbound message" | tail -20

# All Hermes responses sent to the group
grep "<JID>@g.us" /home/opc/.hermes/logs/gateway.log | grep "Sending response" | tail -20

# Conversation turns processed
grep "<JID>@g.us" /home/opc/.hermes/logs/agent.log | grep "conversation turn" | tail -10
```

Each log line has a UTC timestamp. Convert to Chile time:
- **Winter (Abr-Sep, CLT):** UTC-4  → subtract 4h
- **Summer (Oct-Mar, CLST):** UTC-3 → subtract 3h

### 3. Verify bridge is running (to confirm the absence is real)

```bash
curl -sf http://localhost:3000/health
```

Expected response: `{"status":"connected","queueLength":N,"uptime":SECONDS}`

If the bridge is disconnected:
- Messages may exist that weren't processed — check `bridge.log` for reconnection gaps
- Group activity cannot be reliably determined — report "bridge disconnected, unable to verify"

### 4. If no activity, silent retain

Retain to `<profile>-profile` bank with tags `["daily-summary", "<profile>-profile", "YYYY-MM-DD"]`
and to `hermes` bank with tags `["cron", "<job-name>", "YYYY-MM-DD"]`.

### 5. If there WAS activity

The gateway.log shows message excerpts. For the full message content,
check the agent.log line for the conversation turn.

When activity exists, before analyzing:
1. Read the actual messages from gateway.log (they include truncated msg='...')
2. Recall from the profile bank for context on past sessions
3. Identify decisions, learnings, patterns

## Pitfalls

| Situation | What it means | Action |
|---|---|---|
| `bridge.log` shows constant reconnections (reason 428/503) | WhatsApp Web unstable, but messages may still arrive | Activity check is still valid — messages are processed when bridge is connected, but there may be gaps |
| `gateway.log` has no entries for the group | Either no messages OR the group was added after the gateway last restarted | Cross-check with `channel_directory.json` — if the group exists there, the bridge knows about it but no messages were sent |
| Group is in `channel_aliases.json` but NOT in `whatsapp-groups.yaml` | Valid — many groups exist without a profile mapping | The cron should still check the group; it just doesn't have a special profile configuration |
| Timestamps show messages in UTC but the user refers to Chile time | CLT/CLST conversion needed | Always do the UTC→Chile conversion when reporting dates |
| Cron ran but this is the first time for this group | The bank may have no prior entries | The initial recall will return nothing; first retain creates the bank history |
