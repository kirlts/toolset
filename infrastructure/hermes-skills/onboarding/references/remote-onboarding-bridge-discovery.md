# Remote Onboarding — Bridge Group Discovery

## Context

Session 2026-07-09: Martín wanted to onboard "Equipo Trazambiental" (new WhatsApp group) from the Toolset group to avoid polluting the target group with configuration messages. This was the first time remote onboarding was executed.

## Bridge Discovery Sequence (proven from real session)

When Hermes is added to a new WhatsApp group and the bridge doesn't immediately detect it:

### Step 1: Check bridge health and directory

```bash
curl -s --max-time 3 http://127.0.0.1:3000/health
# Expected: {"status":"connected","queueLength":0,...}

cat ~/.hermes/channel_directory.json
# Check if the new group's JID appears under platforms.whatsapp[]

cat ~/.hermes/channel_aliases.json
# Check what's currently resolved
```

### Step 2: Run the sync script

```bash
bash ~/.hermes/scripts/populate-channel-aliases.sh
# Output: "Done: N WhatsApp group aliases"
# If N hasn't increased, the bridge doesn't have the group yet
```

### Step 3: Check bridge logs for new group activity

```bash
tail -100 /home/opc/.hermes/whatsapp/bridge.log | grep -iE "group|jid|remoteJid"
```

Look for a `remoteJid` matching the pattern `\d+@g.us` — if present, the bridge has received traffic from the group but may not have updated the directory yet.

### Step 4: Query bridge API directly (bypasses directory lag)

```bash
curl -s http://127.0.0.1:3000/chat/<JID>
# Returns: {"name":"Group Name","desc":"...","isGroup":true,"participants":["..."]}
```

This endpoint returns the group name, description, and participants even if `channel_directory.json` hasn't been updated. Use this to:
- Confirm the group exists and the JID is correct
- Get the group's name and description
- See who's in the group

### Step 5: Force directory and alias sync

After confirming the bridge has the group data (via API), re-run the populate script:

```bash
bash ~/.hermes/scripts/populate-channel-aliases.sh
# Should now show: "Added: <JID> -> Group Name\nDone: N+1 WhatsApp group aliases"
```

### Step 6: Verify alias was created

```bash
cat ~/.hermes/channel_aliases.json | python3 -c "import sys,json; d=json.load(sys.stdin)['whatsapp']; [print(f'{k}: {v[\"name\"]}') for k,v in d.items() if '<JID_PART>' in k]"
```

## Pitfalls Encountered

| Issue | Symptom | Fix |
|---|---|---|
| Bridge connection issues (503) | Repeated `stream errored out` in logs | Bridge auto-reconnects; group invite notifications may be lost during reconnection |
| Bridge restart (HUP) kills process | `bridge.js` disappears from ps aux | Gateway respawns it automatically within seconds with correct env vars |
| No session for group decryption | `"No session found to decrypt message"` in logs | Normal for new groups — the bridge hasn't established a Signal session yet. Messages still pass through once the gateway processes them |
| channel_directory.json doesn't update | Script says "Done: 10" instead of "Done: 11" | Bridge directory is updated on group join events — if the event was missed, restart bridge or have someone message in the group |
| channel_directory.json updated_at is stale | Value hasn't changed since before group was added | Bridge hasn't received the group join event. Check bridge logs for new JIDs |

## Gateway-Side Discovery

Even before the bridge directory updates, the gateway may create a session for the new group:

```bash
# Check session database
cat ~/.hermes/sessions/sessions.json | python3 -c "import sys,json; d=json.load(sys.stdin); [print(k) for k in d if '<JID_PART>' in k]"
```

The gateway creates a session when it receives a message from the group — this confirms the group is active and routing would work once the profile is configured in `whatsapp-groups.yaml`.

## Allowlist Verification

New group members may be silently blocked if their numbers aren't in either allowlist layer:

```bash
# Bridge allowlist (from process env)
cat /proc/<bridge_pid>/environ | tr '\0' '\n' | grep WHATSAPP_ALLOWED_USERS

# Gateway allowlist (from config)
grep -A5 'whatsapp:' ~/.hermes/config.yaml | grep allowed_users
```

Both must include the user's phone number (without `+`, without `@s.whatsapp.net`, just digits).

## Restoration Commands

If the bridge process is accidentally killed:

```bash
# Gateway respawns it automatically within 5s (RestartSec in systemd unit)
# To verify: ps aux | grep bridge.js | grep -v tito
# To force restart the gateway (which respawns the bridge):
sudo systemctl restart hermes-gateway
```
