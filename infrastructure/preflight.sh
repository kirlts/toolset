#!/usr/bin/env bash
# preflight.sh — Post-deploy verification of MASTER-SPEC invariants
# Runs on the VPS via single SSH session (deploy.sh copies it).
# Parameterized: auto-discovers services from the compose file.
set -euo pipefail

FUNNEL_DOMAIN="${FUNNEL_DOMAIN:-toolset-oci-1-1.tail2d4c18.ts.net}"
REMOTE_REPO="/opt/toolset-repo"
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

echo "[PREFLIGHT] Verifying MASTER-SPEC invariants..."
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

# ── Caddy ────────────────────────────────────────────────────────────

echo "  -- Caddy --"
warn_check "Caddy health (localhost)" bash -c \
  "curl -sf -o /dev/null -w '%{http_code}' --max-time 5 'http://localhost:8080/health' 2>/dev/null | grep -q 200"

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
