#!/usr/bin/env bash
# preflight.sh — Post-deploy verification of MASTER-SPEC invariants
# Runs on the VPS via single SSH session (deploy.sh copies it).
# Parameterized: auto-discovers profiles, groups, and services from config files.
set -euo pipefail

FUNNEL_DOMAIN="${FUNNEL_DOMAIN:-toolset-oci-1-1.tail2d4c18.ts.net}"
REMOTE_REPO="/opt/toolset-repo"
HERMES_HOME="/home/opc/.hermes"
BRIDGE_JS="/usr/local/lib/hermes-agent/scripts/whatsapp-bridge/bridge.js"
WHATSAPP_GROUPS="${REMOTE_REPO}/infrastructure/hermes/whatsapp-groups.yaml"
PROFILES_DIR="${HERMES_HOME}/profiles"
COMPOSE_FILE="${REMOTE_REPO}/infrastructure/docker-compose.yml"
ERRORS=0
WARNINGS=0

# ── Helpers ──────────────────────────────────────────────────────────

check() {
  local desc="$1"; shift
  if "$@" 2>/dev/null; then
    echo "  PASS $desc"
  else
    echo "  FAIL $desc"
    ERRORS=$((ERRORS + 1))
  fi
}

warn_check() {
  local desc="$1"; shift
  if "$@" 2>/dev/null; then
    echo "  PASS $desc"
  else
    echo "  WARN $desc"
    WARNINGS=$((WARNINGS + 1))
  fi
}

# ── Discover configuration ───────────────────────────────────────────

declare -a PROFILES
while IFS= read -r p; do
  [ -n "$p" ] && PROFILES+=("$p")
done < <(grep -oP 'profile:\s*"\K\w+(?=")' "${WHATSAPP_GROUPS}" 2>/dev/null || true)

echo "[PREFLIGHT] Verifying MASTER-SPEC invariants..."
echo "  Discovered profiles: ${PROFILES[*]:-(none)}"
echo ""

# ── §4.1 — Secrets isolation ────────────────────────────────────────

check "No .env in repo" test ! -f "${REMOTE_REPO}/.env"
check "No .env in non-ignored paths" \
  bash -c "! find ${REMOTE_REPO} -name '.env' -not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/venv/*' 2>/dev/null | grep -qv '^$'"

# ── Docker services (auto-discover from compose) ─────────────────────

echo "  -- Docker service health --"
CRITICAL_SERVICES=$(grep -B1 'healthcheck:' "${COMPOSE_FILE}" 2>/dev/null | grep -oP '^  \K[a-z][a-z-]+(?=:)' || echo "caddy infisical")
for svc in $CRITICAL_SERVICES; do
  warn_check "${svc} healthy" bash -c \
    "sudo docker inspect $svc --format '{{.State.Health.Status}}' 2>/dev/null | grep -q healthy"
done

# ── §5.1 — Gateway ──────────────────────────────────────────────────

check "hermes-gateway active" bash -c \
  "systemctl is-active hermes-gateway | grep -q active"

# ── §5.2 — SOUL.md ────────────────────────────────────────────────────

check "Orchestrator SOUL.md exists" test -s "${HERMES_HOME}/SOUL.md"

# ── Profile integrity ────────────────────────────────────────────────

echo "  -- Profile integrity --"
for profile in "${PROFILES[@]}"; do
  check "SOUL.md for profile '${profile}'" test -s "${PROFILES_DIR}/${profile}/SOUL.md"

done

# ── §5.3 — MCP configuration ──────────────────────────────────────────

check "MCP servers configured in yaml" \
  grep -q 'mcp_servers' "${HERMES_HOME}/config.yaml"

# ── Bridge.js injection verification ─────────────────────────────────

echo "  -- Bridge.js injection --"
check "GROUPS MAP present in bridge.js" grep -q "GROUPS MAP" "${BRIDGE_JS}"
check "PROFILE ACTIVATION syntax" grep -q "'=== PROFILE ACTIVATION: '" "${BRIDGE_JS}"
check "Bridge.js syntax check" bash -c "node --check ${BRIDGE_JS} 2>/dev/null"

# ── Git state verification ───────────────────────────────────────────

echo "  -- Git state --"
cd "${REMOTE_REPO}"
GIT_CLEAN=$(git status --porcelain 2>/dev/null | wc -l)
if [ "$GIT_CLEAN" -eq 0 ]; then
  echo "    PASS Repo is clean"
else
  echo "    WARN ${GIT_CLEAN} uncommitted file(s) in ${REMOTE_REPO}"
  WARNINGS=$((WARNINGS + 1))
fi

GIT_AUTHOR=$(git log -1 --format='%an' 2>/dev/null)
echo "    Last commit by: ${GIT_AUTHOR}"
if [ "$GIT_AUTHOR" = "Hermes Agent" ] || [ "$GIT_AUTHOR" = "Oracle Public Cloud User" ]; then
  echo "    WARN Last commit by ${GIT_AUTHOR} — should be via Kilo CLI"
  WARNINGS=$((WARNINGS + 1))
fi

# ── Kanban dispatch verification ─────────────────────────────────────

echo "  -- Kanban dispatch --"
KANBAN_OK=$(python3 -c "
import yaml
c = yaml.safe_load(open('${HERMES_HOME}/config.yaml'))
k = c.get('kanban', {})
print(k.get('dispatch_in_gateway') == True and k.get('auto_decompose') == True)
" 2>/dev/null)
if [ "$KANBAN_OK" = "True" ]; then
  echo "    PASS Kanban config (dispatch_in_gateway + auto_decompose)"
else
  echo "    FAIL Kanban config"
  ERRORS=$((ERRORS + 1))
fi

# ── WebUI accessibility ─────────────────────────────────────────────

echo "  -- WebUI --"
warn_check "Caddy health (localhost)" bash -c \
  "curl -sf -o /dev/null -w '%{http_code}' --max-time 5 'http://localhost:8080/health' 2>/dev/null | grep -q 200"
warn_check "Hermes WebUI via Caddy (localhost)" bash -c \
  "curl -sf -o /dev/null -w '%{http_code}' --max-time 5 'http://localhost:8080/hermes/' 2>/dev/null | grep -qE '200|302'"

# ── Skills ─────────────────────────────────────────────────────────

# Busca a cualquier profundidad, no solo `skills/*/SKILL.md`: las skills se organizan
# por categoria (skills/<categoria>/<skill>/SKILL.md), asi que a profundidad 2 no hay
# ninguna y el invariante fallaba SIEMPRE, con 94 SKILL.md instalados. Cada deploy
# terminaba en rojo por eso, y un rojo permanente deja de informar. Verificado 2026-07-24.
check "Skills directory populated" bash -c \
  "find ${HERMES_HOME}/skills -name SKILL.md -print -quit 2>/dev/null | grep -q SKILL"

# ── Context file ──────────────────────────────────────────────────

check "AGENTS.md exists" test -s "${REMOTE_REPO}/AGENTS.md"

# ── Summary ──────────────────────────────────────────────────────────

echo ""
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
  echo "[PREFLIGHT] All invariants verified"
elif [ $ERRORS -eq 0 ]; then
  echo "[PREFLIGHT] All critical checks passed (${WARNINGS} warning(s))"
else
  echo "[PREFLIGHT] ${ERRORS} invariant(s) failed, ${WARNINGS} warning(s)"
  exit 1
fi
