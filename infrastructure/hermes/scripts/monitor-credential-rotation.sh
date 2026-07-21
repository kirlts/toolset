#!/usr/bin/env bash
# monitor-credential-rotation.sh
# Monitor credential pool in auth.json and notify via WhatsApp when rotation occurs.
# Runs as cron. Deployed by deploy.sh.

set -euo pipefail

AUTH_FILE="/home/opc/.hermes/auth.json"
STATE_FILE="/home/opc/.hermes/credential-rotation-state.txt"
TOOLSET_JID="120363426816726918@g.us"

export PATH="/usr/local/bin:/home/opc/.local/bin:$PATH"

[ -f "$AUTH_FILE" ] || exit 0

# Extract credential pool state: provider -> [(label, last_status, last_error_reason)]
CURRENT=$(python3 -c "
import json, sys
try:
    with open('$AUTH_FILE') as f:
        data = json.load(f)
    pool = data.get('credential_pool', {})
    for provider, creds in pool.items():
        for c in creds:
            label = c.get('label','?')
            status = c.get('last_status','ok')
            error = c.get('last_error_reason','')
            reset = c.get('last_error_reset_at', 0)
            print(f'{provider}|{label}|{status}|{error}|{reset}')
except: pass
" 2>/dev/null)

# Read previous state
PREVIOUS=""
[ -f "$STATE_FILE" ] && PREVIOUS=$(cat "$STATE_FILE")

# If state changed, notify
if [ "$CURRENT" != "$PREVIOUS" ]; then
    echo "$CURRENT" > "$STATE_FILE"
    
    # Check for exhausted/rate-limited credentials
    EXHAUSTED=$(echo "$CURRENT" | grep -c "|exhausted|GoUsageLimitError" || true)
    FALLBACK_ACTIVE=$(echo "$CURRENT" | grep "fallback-key" | grep -c "^opencode-go|fallback-key|ok" || true)
    
    if [ "$EXHAUSTED" -gt 0 ] && [ -n "$PREVIOUS" ]; then
        # Rotation just happened: main key exhausted, fallback active
        hermes send -t "whatsapp:${TOOLSET_JID}" \
            "⚠️ Hermes: OpenCode Go main key agotada (HTTP 429). Cambiado automáticamente a clave fallback. El pool rotará de vuelta cuando la principal se recupere." \
            2>/dev/null || true
    fi
    
    # Check if recovery happened (previously exhausted, now healthy)
    WAS_EXHAUSTED=$(echo "$PREVIOUS" | grep "OPENCODE_GO_API_KEY" | grep -c "|exhausted|" || true)
    NOW_HEALTHY=$(echo "$CURRENT" | grep "OPENCODE_GO_API_KEY" | grep -c "^opencode-go|OPENCODE_GO_API_KEY|ok" || true)
    
    if [ "$WAS_EXHAUSTED" -gt 0 ] && [ "$NOW_HEALTHY" -gt 0 ]; then
        hermes send -t "whatsapp:${TOOLSET_JID}" \
            "✅ Hermes: OpenCode Go main key recuperada. Pool restaurado a clave principal." \
            2>/dev/null || true
    fi
fi
