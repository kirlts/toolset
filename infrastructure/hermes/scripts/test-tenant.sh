#!/usr/bin/env bash
set -euo pipefail
# test-tenant.sh <tenant-name>
# Post-provision validation suite for a Hermes tenant.

TENANT="${1:-}"
[ -z "$TENANT" ] && { echo "Usage: test-tenant.sh <tenant-name>"; exit 2; }

PROFILE="$HOME/.hermes/profiles/$TENANT"
PASS=0
FAIL=0

check() { if eval "$1"; then echo "  ✓ $2"; PASS=$((PASS+1)); else echo "  ✗ $2"; FAIL=$((FAIL+1)); fi; }

echo "=== Tenant Test Suite: $TENANT ==="

# ── Profile structure ──
check "[ -d '$PROFILE' ]"                                       "profile directory exists"
check "[ -f '$PROFILE/config.yaml' ]"                           "config.yaml exists"
check "[ -f '$PROFILE/SOUL.md' ]"                               "SOUL.md exists"
check "[ -f '$PROFILE/.env' ]"                                  ".env exists"
check "[ -f '$PROFILE/.tenant' ]"                               ".tenant marker exists"

# ── Identity ──
check "grep -q '$TENANT' '$PROFILE/SOUL.md'"                    "SOUL.md mentions tenant name"
check "grep -q \"^name: $TENANT\" '$PROFILE/config.yaml'" "config.yaml has tenant name"

# ── Model ──
check "grep -q 'model:' '$PROFILE/config.yaml'"                  "model section exists"
check "grep -q 'opencode-go\\|openrouter\\|groq' '$PROFILE/config.yaml'" "model provider is valid"

# ── Memory: Holographic only, no Hindsight ──
check "grep -q 'holographic' '$PROFILE/config.yaml'"            "memory.provider set to holographic"
check "! grep -q 'hindsight' '$PROFILE/config.yaml'"            "no hindsight MCP reference"
check "! grep -q 'hindsight-selfhosted' '$PROFILE/config.yaml'" "no hindsight-selfhosted MCP"

# ── Toolsets: restricted ──
check "! grep -qw 'docker' '$PROFILE/config.yaml'"              "no 'docker' in config"
check "! grep -qw 'systemctl' '$PROFILE/config.yaml'"           "no 'systemctl' in config"
check "! grep -qw 'sudo' '$PROFILE/config.yaml'"                "no 'sudo' in config"
check "grep -q 'terminal' '$PROFILE/config.yaml'"               "terminal toolset present"

# ── WhatsApp ──
check "grep -q 'WHATSAPP_BOT_NUMBER' '$PROFILE/.env'"           "WHATSAPP_BOT_NUMBER in .env"
check "grep -q 'WHATSAPP_ALLOWED_USERS' '$PROFILE/.env'"        "WHATSAPP_ALLOWED_USERS in .env"
check "grep -q 'enabled: true' '$PROFILE/config.yaml'"          "whatsapp enabled in config"

# ── TTS ──
check "grep -q 'tts:' '$PROFILE/config.yaml'"                   "TTS section exists"
if grep -q 'es-CL-' "$PROFILE/config.yaml"; then
  check "true" "TTS voice configured (es-CL-*)"
else
  echo "  ⚡ TTS disabled or voice not set"
fi

# ── Workspace ──
if [ -d "/home/opc/workspace/tenants/$TENANT/repos" ]; then
  check "true" "workspace directory exists"
else
  echo "  ✗ workspace directory missing"
  FAIL=$((FAIL+1))
fi

# ── CI/CD backup ──
REPO_BACKUP="/opt/toolset-repo/infrastructure/hermes/tenants/backups/$TENANT"
if [ -f "$REPO_BACKUP/whatsapp-groups.yaml" ]; then
  check "true" "CI/CD backup: whatsapp-groups.yaml synced"
else
  echo "  ⚡ CI/CD backup not yet synced (cron hasn't run or tenant has no groups)"
fi

# ── Skills ──
SKILL_PATH="/opt/toolset-repo/infrastructure/hermes-skills/tenant-grupo/SKILL.md"
check "[ -f '$SKILL_PATH' ]"                                    "tenant-grupo skill available"

# ── Gateway ──
GW_SERVICE="hermes-gateway-${TENANT}.service"
if systemctl --user is-enabled "$GW_SERVICE" >/dev/null 2>&1; then
  check "true" "gateway systemd service enabled"
elif systemctl --user is-active "$GW_SERVICE" >/dev/null 2>&1; then
  check "true" "gateway systemd service active"
else
  echo "  ⚡ gateway service not yet installed (run 'hermes -p $TENANT gateway install')"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -gt 0 ] && exit 1 || exit 0
