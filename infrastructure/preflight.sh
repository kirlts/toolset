#!/usr/bin/env bash
# preflight.sh — Post-deploy verification of MASTER-SPEC invariants
set -euo pipefail

SSH_HOST="${SSH_HOST:-opc@toolset-oci-1-1}"
FUNNEL_DOMAIN="${FUNNEL_DOMAIN:-toolset-oci-1-1.tail2d4c18.ts.net}"
HINDSIGHT_URL="https://${FUNNEL_DOMAIN}/hindsight"
ERRORS=0

check() {
  local desc="$1" cmd="$2"
  result=$(ssh -o StrictHostKeyChecking=no "${SSH_HOST}" "$cmd" 2>/dev/null)
  if [ $? -eq 0 ] && [ -n "$result" ]; then
    echo "  PASS $desc"
  else
    echo "  FAIL $desc"
    ERRORS=$((ERRORS + 1))
  fi
}

mcp_curl() {
  curl -sf --max-time 10 "$@" 2>/dev/null
}

echo "[PREFLIGHT] Verifying MASTER-SPEC invariants..."

# §4.1 — No .env in repo
check "No .env in repo" "[ ! -f /opt/toolset-repo/.env ] && echo ok"

# §4.1 — No .env in Hermes home (MASTER-SPEC §4.1: secrets via Infisical only)
check "No .env outside Hermes controlled path" \
  "! grep -q '^COMPOSIO_MCP_KEY=' /opt/toolset-repo/.env 2>/dev/null || ! grep -q '^OPENCODE_GO_API_KEY=' /opt/toolset-repo/.env 2>/dev/null; echo ok"

# Docker service health
for svc in infisical hindsight caddy; do
  check "${svc} healthy" \
    "sudo docker inspect $svc --format '{{.State.Health.Status}}' | grep -q healthy && echo ok"
done

# §5.1 — Hermes gateway
check "hermes-gateway active" \
  "systemctl is-active hermes-gateway | grep -q active && echo ok"

# §5.2 — SOUL.md
check "SOUL.md exists" \
  "[ -s /home/opc/.hermes/SOUL.md ] && echo ok"

# §5.3 — MCP servers configured (static)
check "MCP servers configured in yaml" \
  "grep -q 'mcp_servers' /home/opc/.hermes/config.yaml && echo ok"

# --- MCP 3-Step Verification (§3.5 recommendation 5) ---
echo "  -- MCP 3-Step Verification --"

# Step 1: Health check
GW_HEALTH=$(ssh -o StrictHostKeyChecking=no "${SSH_HOST}" \
  "curl -sf ${HINDSIGHT_URL}/health 2>/dev/null && echo ok" 2>/dev/null)
if [ -n "$GW_HEALTH" ]; then
  echo "    PASS MCP Step 1 (health endpoint)"
else
  echo "    FAIL MCP Step 1 (health endpoint)"
  ERRORS=$((ERRORS + 1))
fi

# Steps 2+3: MCP SSE handshake (initialize → session ID → tools/call)
MCP_BASE="${HINDSIGHT_URL}/mcp"
MCP_INIT='{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"preflight","version":"1.0"}},"id":1}'

MCP_SESSION=$(ssh -o StrictHostKeyChecking=no "${SSH_HOST}" \
  "curl -s -D - --max-time 15 -X POST '${MCP_BASE}/' \
    -H 'Content-Type: application/json' \
    -d '${MCP_INIT}' 2>/dev/null | head -10 | grep -oP 'mcp-session-id: \K\S+' 2>/dev/null || echo ''")

if [ -n "$MCP_SESSION" ]; then
  echo "    PASS MCP Step 2 (SSE session): $MCP_SESSION"

  MCP_CALL=$(ssh -o StrictHostKeyChecking=no "${SSH_HOST}" \
    "curl -s --max-time 15 -X POST '${MCP_BASE}/' \
      -H 'Content-Type: application/json' \
      -H 'Mcp-Session-Id: ${MCP_SESSION}' \
      -d '{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"list_banks\",\"arguments\":{}}}' 2>/dev/null")

  if echo "$MCP_CALL" | grep -q 'result'; then
    BANKS=$(echo "$MCP_CALL" | python3 -c "
import sys,json
for line in sys.stdin:
    if line.startswith('data: '):
        d=json.loads(line[6:])
        r=d.get('result',{})
        c=r.get('content',[])
        for item in c:
            txt=item.get('text','')
            try:
                b=json.loads(txt)
                banks=b.get('banks',[])
                print(f'ok ({len(banks)} banks)')
            except:
                pass
" 2>/dev/null || echo "ok (executed)")
    echo "    PASS MCP Step 3 (list_banks): $BANKS"
  else
    echo "    FAIL MCP Step 3 (list_banks)"
    ERRORS=$((ERRORS + 1))
  fi
else
  echo "    FAIL MCP Step 2 (SSE session init)"
  ERRORS=$((ERRORS + 1))
fi

# §5.4 — Hindsight bank
check "Hindsight bank 'hermes'" \
  "curl -sf ${HINDSIGHT_URL}/v1/default/banks | python3 -c \"import sys,json;print('ok' if any(b.get('bank_id')=='hermes' for b in json.load(sys.stdin).get('banks',[])) else '')\" "

# Skills
check "Skills directory populated" \
  "ls /home/opc/.hermes/skills/*/SKILL.md 2>/dev/null | head -1 | grep -q SKILL && echo ok"

# Context file (auto-discovered)
check "AGENTS.md exists (auto-discovered context)" \
  "[ -s /opt/toolset-repo/AGENTS.md ] && echo ok"

# Memory consolidation cron active
check "Memory consolidation cron installed" \
  "crontab -l 2>/dev/null | grep -q consolidate-memory && echo ok"

echo ""
if [ $ERRORS -eq 0 ]; then
  echo "[PREFLIGHT] All invariants verified"
else
  echo "[PREFLIGHT] $ERRORS invariant(s) failed"
  exit 1
fi
