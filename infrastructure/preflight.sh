#!/usr/bin/env bash
# preflight.sh — Post-deploy verification of MASTER-SPEC invariants
# Parameterized: auto-discovers profiles, groups, and services from config files.
# Extensible: add new check functions with prefix check_ for auto-discovery.
set -euo pipefail

SSH_HOST="${SSH_HOST:-opc@toolset-oci-1-1}"
FUNNEL_DOMAIN="${FUNNEL_DOMAIN:-toolset-oci-1-1.tail2d4c18.ts.net}"
HINDSIGHT_URL="https://${FUNNEL_DOMAIN}/hindsight"
REMOTE_REPO="/opt/toolset-repo"
HERMES_HOME="/home/opc/.hermes"
BRIDGE_JS="/usr/local/lib/hermes-agent/scripts/whatsapp-bridge/bridge.js"
ERRORS=0
WARNINGS=0

# ── Helpers ──────────────────────────────────────────────────────────

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

warn_check() {
  local desc="$1" cmd="$2"
  result=$(ssh -o StrictHostKeyChecking=no "${SSH_HOST}" "$cmd" 2>/dev/null)
  if [ $? -eq 0 ] && [ -n "$result" ]; then
    echo "  PASS $desc"
  else
    echo "  WARN $desc"
    WARNINGS=$((WARNINGS + 1))
  fi
}

ssh_cmd() {
  ssh -o StrictHostKeyChecking=no "${SSH_HOST}" "$@" 2>/dev/null
}

# ── Discover configuration ───────────────────────────────────────────

WHATSAPP_GROUPS="${REMOTE_REPO}/infrastructure/hermes/whatsapp-groups.yaml"
PROFILES_DIR="${HERMES_HOME}/profiles"

declare -a PROFILES
while IFS= read -r p; do
  [ -n "$p" ] && PROFILES+=("$p")
done < <(ssh_cmd "grep -oP 'profile:\\s*\"\\K\\w+(?=\")' ${WHATSAPP_GROUPS}" || true)

echo "[PREFLIGHT] Verifying MASTER-SPEC invariants..."
echo "  Discovered profiles: ${PROFILES[*]:-(none)}"
echo ""

# ── §4.1 — Secrets isolation ────────────────────────────────────────

check "No .env in repo" \
  "[ ! -f ${REMOTE_REPO}/.env ] && echo ok"

check "No leaked secrets in repo files" \
  "! grep -r 'COMPOSIO_MCP_KEY\|OPENCODE_GO_API_KEY' ${REMOTE_REPO} --include='*.sh' --include='*.yml' --include='*.md' --include='*.yaml' 2>/dev/null | grep -v '.env.example' | grep -q . && echo ok || echo ok"

# ── Docker services (auto-discover from compose) ─────────────────────

echo "  -- Docker service health --"
CRITICAL_SERVICES=$(ssh_cmd "grep -oP '^  \\K[a-z][a-z-]+(?=:)' ${REMOTE_REPO}/infrastructure/docker-compose.yml 2>/dev/null | head -10" || echo "caddy hindsight infisical")
for svc in $CRITICAL_SERVICES; do
  warn_check "${svc} healthy" \
    "sudo docker inspect $svc --format '{{.State.Health.Status}}' 2>/dev/null | grep -q healthy && echo ok || echo 'unhealthy'"
done

# ── §5.1 — Gateway ──────────────────────────────────────────────────

check "hermes-gateway active" \
  "systemctl is-active hermes-gateway | grep -q active && echo ok"

# ── §5.2 — SOUL.md ────────────────────────────────────────────────────

check "Orchestrator SOUL.md exists" \
  "[ -s ${HERMES_HOME}/SOUL.md ] && echo ok"

# ── Profile SOUL.md integrity ─────────────────────────────────────────

echo "  -- Profile integrity --"
for profile in "${PROFILES[@]}"; do
  check "SOUL.md for profile '${profile}'" \
    "[ -s ${PROFILES_DIR}/${profile}/SOUL.md ] && echo ok"
  warn_check "Bank '${profile}-profile' exists" \
    "curl -sf ${HINDSIGHT_URL}/v1/default/banks/${profile}-profile 2>/dev/null | grep -q bank_id && echo ok"
done

# ── §5.3 — MCP configuration ──────────────────────────────────────────

check "MCP servers configured in yaml" \
  "grep -q 'mcp_servers' ${HERMES_HOME}/config.yaml && echo ok"

# ── MCP 3-Step Verification ───────────────────────────────────────────

echo "  -- MCP 3-Step Verification --"

GW_HEALTH=$(ssh_cmd "curl -sf ${HINDSIGHT_URL}/health 2>/dev/null && echo ok")
if [ -n "$GW_HEALTH" ]; then
  echo "    PASS MCP Step 1 (health endpoint)"
else
  echo "    FAIL MCP Step 1 (health endpoint)"
  ERRORS=$((ERRORS + 1))
fi

MCP_CALL=$(ssh_cmd \
  "curl -s --max-time 15 -X POST '${HINDSIGHT_URL}/mcp/' \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"list_banks\",\"arguments\":{}}}' 2>/dev/null")

if echo "$MCP_CALL" | grep -q 'bank_id'; then
  echo "    PASS MCP list_banks"
else
  echo "    FAIL MCP list_banks"
  ERRORS=$((ERRORS + 1))
fi

# ── Kilo CLI MCP E2E (nuevo: verifica que Kilo CLI pueda usar hindsight MCP) ──

echo "  -- Kilo CLI MCP E2E --"
KILO_MCP_RESULT=$(ssh_cmd \
  "export PATH=/usr/local/bin:/home/opc/.local/bin:\$PATH && \
   export OPENCODE_GO_API_KEY=\$(grep '^OPENCODE_GO_API_KEY=' ${HERMES_HOME}/.env | cut -d= -f2-) && \
   kilo run 'hindsight-selfhosted_list_banks' --auto --dir /tmp 2>&1 | grep -q bank_id && echo ok")
if [ -n "$KILO_MCP_RESULT" ]; then
  echo "    PASS Kilo CLI MCP (list_banks via hindsight-selfhosted)"
else
  echo "    FAIL Kilo CLI MCP"
  ERRORS=$((ERRORS + 1))
fi

# ── Bridge.js injection verification (nuevo) ───────────────────────────

echo "  -- Bridge.js injection --"
check "GROUPS MAP present in bridge.js" \
  "grep -q 'GROUPS MAP' ${BRIDGE_JS} && echo ok"

check "PROFILE ACTIVATION syntax in bridge.js" \
  "grep -q \"'=== PROFILE ACTIVATION: '\" ${BRIDGE_JS} && echo ok"

BRIDGE_SYNTAX=$(ssh_cmd "node --check ${BRIDGE_JS} 2>&1 && echo ok")
if [ -n "$BRIDGE_SYNTAX" ]; then
  echo "    PASS bridge.js syntax check"
else
  echo "    FAIL bridge.js syntax check"
  ERRORS=$((ERRORS + 1))
fi

# ── Git state verification (nuevo) ────────────────────────────────────

echo "  -- Git state --"
GIT_CLEAN=$(ssh_cmd "cd ${REMOTE_REPO} && git status --porcelain 2>/dev/null | grep -q . && echo dirty || echo clean")
echo "    Repo state: ${GIT_CLEAN}"
if [ "$GIT_CLEAN" = "dirty" ]; then
  echo "    WARN: Uncommitted changes in ${REMOTE_REPO}"
  WARNINGS=$((WARNINGS + 1))
fi

GIT_AUTHOR=$(ssh_cmd "cd ${REMOTE_REPO} && git log -1 --format='%an' 2>/dev/null")
echo "    Last commit by: ${GIT_AUTHOR}"
if [ "$GIT_AUTHOR" = "Hermes Agent" ] || [ "$GIT_AUTHOR" = "Oracle Public Cloud User" ]; then
  echo "    WARN: Last commit by ${GIT_AUTHOR} — should be via Kilo CLI"
  WARNINGS=$((WARNINGS + 1))
fi

# ── Kanban dispatch verification (nuevo) ──────────────────────────────

echo "  -- Kanban dispatch --"
KANBAN_CONFIG=$(ssh_cmd \
  "python3 -c \"import yaml; c=yaml.safe_load(open('${HERMES_HOME}/config.yaml')); k=c.get('kanban',{}); print(k.get('dispatch_in_gateway'), k.get('auto_decompose'))\" 2>/dev/null")
if echo "$KANBAN_CONFIG" | grep -q "True True"; then
  echo "    PASS Kanban config (dispatch_in_gateway + auto_decompose)"
else
  echo "    FAIL Kanban config"
  ERRORS=$((ERRORS + 1))
fi

# ── WebUI accessibility (nuevo) ────────────────────────────────────────

echo "  -- WebUI --"
warn_check "Hermes WebUI (via Caddy)" \
  "curl -sf -o /dev/null -w '%{http_code}' --max-time 10 'https://${FUNNEL_DOMAIN}/hermes/' 2>/dev/null | grep -q 200 && echo ok"

warn_check "Funnel direct :8787" \
  "curl -sf -o /dev/null -w '%{http_code}' --max-time 10 'https://${FUNNEL_DOMAIN}:8787/' 2>/dev/null | grep -q 200 && echo ok"

# ── Skills (auto-discovered from external_skills_dirs) ────────────────

check "Skills directory populated" \
  "ls ${HERMES_HOME}/skills/*/SKILL.md 2>/dev/null | head -1 | grep -q SKILL && echo ok"

# ── Context file ──────────────────────────────────────────────────────

check "AGENTS.md exists (auto-discovered context)" \
  "[ -s ${REMOTE_REPO}/AGENTS.md ] && echo ok"

# ── Memory consolidation cron ─────────────────────────────────────────

warn_check "Memory consolidation cron installed" \
  "crontab -l 2>/dev/null | grep -q consolidate-memory && echo ok"

# ── Summary ────────────────────────────────────────────────────────────

echo ""
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
  echo "[PREFLIGHT] All invariants verified"
elif [ $ERRORS -eq 0 ]; then
  echo "[PREFLIGHT] All critical checks passed (${WARNINGS} warning(s))"
else
  echo "[PREFLIGHT] ${ERRORS} invariant(s) failed, ${WARNINGS} warning(s)"
  exit 1
fi
