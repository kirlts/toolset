#!/usr/bin/env bash
set -euo pipefail

# provision-tenant.sh — creates a new Hermes tenant from a definition JSON.
# Reads tenant configuration from stdin or a file, creates the Hermes profile,
# writes config/SOUL/.env from templates, sets up WhatsApp Baileys, and outputs
# the QR code for pairing.
#
# Usage:
#   provision-tenant.sh tenant.json
#   cat tenant.json | provision-tenant.sh
#
# Environment:
#   INFISICAL_SERVICE_TOKEN -- required for Infisical API access
#   INFISICAL_PID            -- Infisical project ID (Toolset)
#   HERMES_HOME              -- default ~/.hermes

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
TEMPLATE_DIR="$(dirname "$0")/../tenants/template"
INFISICAL_API="${INFISICAL_API_URL:-http://localhost:8080}"
INFISICAL_PID="${INFISICAL_PID:-}"
INFISICAL_TOKEN="${INFISICAL_SERVICE_TOKEN:-${INFISICAL_TOKEN:-}}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[provision]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[error]${NC} $*"; exit 1; }

# ── Read JSON ──
JSON=""
if [ -n "${1:-}" ] && [ -f "$1" ]; then
    JSON=$(cat "$1")
elif [ ! -t 0 ]; then
    JSON=$(cat)
else
    err "No JSON input provided. Usage: provision-tenant.sh <file.json> or pipe JSON to stdin"
fi

# ── Parse fields ──
_name()    { echo "$JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['$1'])" 2>/dev/null || true; }
_list()    { echo "$JSON" | python3 -c "import sys,json; print('\n'.join(str(x) for x in json.load(sys.stdin)['$1']))" 2>/dev/null || true; }

TENANT_NAME=$(_name name)
TENANT_DESC=$(_name description)
TENANT_WA_NUMBER=$(_name whatsapp_number)
TENANT_ALLOWED=$(_list allowed_users)
TENANT_MODEL=$(_name "model['default']")
TENANT_PROVIDER=$(_name "model['provider']")
TENANT_FALLBACK=$(_name "model['fallback']")
TENANT_TOOLSETS=$(_list toolsets)
TENANT_MEM_PROVIDER=$(_name "memory['provider']")
TENANT_APPROVALS_MODE=$(_name "approvals['mode']")
TENANT_CRON_MODE=$(_name "approvals['cron_mode']")
TENANT_CWD=$(_name "terminal['cwd']")
TENANT_TIMEOUT=$(_name "terminal['timeout']")
TENANT_NOTIFY=$(_name "cron['gateway_notify_interval']")
TENANT_TTS_ENABLED=$(_name "tts['enabled']")
TENANT_TTS_VOICE=$(_name "tts['voice']")
TENANT_TTS_SCOPE=$(_name "tts['scope']")

TENANT_TTS_ENABLED_BOOL="false"
[ "$TENANT_TTS_ENABLED" = "True" ] && TENANT_TTS_ENABLED_BOOL="true"
TENANT_TTS_VOICE="${TENANT_TTS_VOICE:-es-CL-LorenzoNeural}"
TENANT_TTS_SCOPE="${TENANT_TTS_SCOPE:-all}"
TENANT_STT_ENABLED=$(_name "stt['enabled']")
TENANT_STT_PROVIDER=$(_name "stt['provider']")
TENANT_STT_MODEL=$(_name "stt['model']")

TENANT_STT_ENABLED_BOOL="false"
[ "$TENANT_STT_ENABLED" = "True" ] && TENANT_STT_ENABLED_BOOL="true"

# Detect if tenant has repos
TENANT_REPO_COUNT=$(echo "$JSON" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['repos']))" 2>/dev/null || echo "0")

[ -n "$TENANT_NAME" ] || err "Missing 'name' field in JSON"
[ -n "$TENANT_CWD" ] || err "Missing 'terminal.cwd' field in JSON"

TENANT_WORKSPACE=$(dirname "$TENANT_CWD")
TENANT_PROFILE_DIR="$HERMES_HOME/profiles/$TENANT_NAME"

log "Provisioning tenant: $TENANT_NAME"
log "  Workspace: $TENANT_WORKSPACE"
log "  Profile:   $TENANT_PROFILE_DIR"

# ── Check for existing tenant ──
if [ -d "$TENANT_PROFILE_DIR" ]; then
    warn "Profile directory already exists: $TENANT_PROFILE_DIR"
    warn "Use 'hermes profile delete $TENANT_NAME' to remove or choose a different name."
    exit 1
fi

# ── Infisical: store secrets ──
if [ -n "$INFISICAL_TOKEN" ] && [ -n "$INFISICAL_PID" ]; then
    log "Storing tenant secrets in Infisical (project: $INFISICAL_PID)..."
    INFISICAL_BASE="$INFISICAL_API/api/v3/secrets/raw"

    _set_secret() {
        local key="$1" val="$2"
        curl -sf -X POST "$INFISICAL_BASE/$key" \
            -H "Authorization: Bearer $INFISICAL_TOKEN" \
            -H "Content-Type: application/json" \
            -d "{\"secretValue\":\"$val\",\"workspaceId\":\"$INFISICAL_PID\",\"environment\":\"prod\",\"type\":\"shared\"}" \
            >/dev/null 2>&1 && log "  ✓ Infisical: $key" || warn "  ⚠ Infisical: $key (may already exist)"
    }

    _set_secret "tenants/${TENANT_NAME}/WHATSAPP_BOT_NUMBER" "$TENANT_WA_NUMBER"
    _set_secret "tenants/${TENANT_NAME}/WHATSAPP_ALLOWED_USERS" "$(echo "$TENANT_ALLOWED" | tr '\n' ',')"

    # Generate deploy keys for repos that need push access
    HAS_PUSH=false
    if [ "$TENANT_REPO_COUNT" -gt 0 ]; then
      REPO_COUNT=$TENANT_REPO_COUNT
      for i in $(seq 0 $((REPO_COUNT - 1))); do
        PUSH=$(echo "$JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['repos'][$i]['push'])")
        if [ "$PUSH" = "True" ]; then
            HAS_PUSH=true
            break
        fi
    done

    if [ "$HAS_PUSH" = "true" ]; then
        log "Generating SSH deploy key for GitHub..."
        KEY_DIR="$HERMES_HOME/profiles/$TENANT_NAME/.ssh"
        mkdir -p "$KEY_DIR"
        ssh-keygen -t ed25519 -C "${TENANT_NAME}@toolset-tenant" -f "$KEY_DIR/id_ed25519" -N "" -q
        PRIVATE_KEY=$(cat "$KEY_DIR/id_ed25519")
        PUBLIC_KEY=$(cat "$KEY_DIR/id_ed25519.pub")
        _set_secret "tenants/${TENANT_NAME}/GITHUB_DEPLOY_KEY_PRIVATE" "$PRIVATE_KEY"
        chmod 600 "$KEY_DIR/id_ed25519"
        log "  Deploy key generated. PUBLIC KEY (add to GitHub repo → Settings → Deploy keys):"
        echo ""
        echo "  $PUBLIC_KEY"
        echo ""
    fi
    fi
else
    warn "Infisical token/PID not found. Secrets will NOT be stored in Infisical."
    warn "Set INFISICAL_SERVICE_TOKEN and INFISICAL_PID to enable secret storage."
fi

# ── Create workspace directories ──
log "Creating workspace: $TENANT_WORKSPACE"
mkdir -p "$TENANT_CWD" "$TENANT_WORKSPACE"

# ── Build config.yaml from template ──
log "Generating config.yaml..."
CONFIG_TEMPLATE="$TEMPLATE_DIR/config.yaml"
TARGET_CONFIG="$TENANT_PROFILE_DIR/config.yaml"

# Build allowed users YAML list
ALLOWED_YAML=""
while IFS= read -r user; do
    [ -n "$user" ] && ALLOWED_YAML="${ALLOWED_YAML}  - ${user}\n"
done <<< "$TENANT_ALLOWED"

# Build toolsets YAML list
TOOLSETS_YAML=""
while IFS= read -r ts; do
    [ -n "$ts" ] && TOOLSETS_YAML="${TOOLSETS_YAML}- ${ts}\n"
done <<< "$TENANT_TOOLSETS"

# Build toolsets description
TOOLSETS_DESC=$(echo "$TENANT_TOOLSETS" | tr '\n' ', ' | sed 's/, $//' | sed 's/,$//')

# Build repo description
REPO_DESC=""
while IFS= read -r repo_line; do
    [ -n "$repo_line" ] && REPO_DESC="${REPO_DESC}- ${repo_line}\n"
done <<< "$(echo "$JSON" | python3 -c "
import sys, json
for r in json.load(sys.stdin)['repos']:
    push = ' (push enabled)' if r['push'] else ' (read-only)'
    print(f\"{r['url']} [{r['branch']}]{push}\")
")"

# Model fallback with provider prefix
FALLBACK_MODEL="${TENANT_PROVIDER}/${TENANT_FALLBACK}"

mkdir -p "$(dirname "$TARGET_CONFIG")"
sed \
    -e "s|<TENANT_NAME>|${TENANT_NAME}|g" \
    -e "s|<TENANT_MODEL>|${TENANT_MODEL}|g" \
    -e "s|<TENANT_PROVIDER>|${TENANT_PROVIDER}|g" \
    -e "s|<TENANT_FALLBACK_MODEL>|${FALLBACK_MODEL}|g" \
    -e "s|<TENANT_WORKSPACE>|${TENANT_WORKSPACE}|g" \
    -e "s|<TENANT_TTS_VOICE>|${TENANT_TTS_VOICE}|g" \
    -e "s|<TENANT_TTS_ENABLED>|${TENANT_TTS_ENABLED_BOOL}|g" \
    -e "s|<TENANT_STT_ENABLED>|${TENANT_STT_ENABLED_BOOL}|g" \
    "$CONFIG_TEMPLATE" > "$TARGET_CONFIG"

# Inject allowed_users
sed -i "/<TENANT_ALLOWED_USERS>/r /dev/stdin" "$TARGET_CONFIG" <<< "$(echo -e "$ALLOWED_YAML")"
sed -i "/<TENANT_ALLOWED_USERS>/d" "$TARGET_CONFIG"

# Inject toolsets
sed -i "/<TENANT_TOOLSETS>/r /dev/stdin" "$TARGET_CONFIG" <<< "$(echo -e "$TOOLSETS_YAML")"
sed -i "/<TENANT_TOOLSETS>/d" "$TARGET_CONFIG"

# Set approval and cron modes
sed -i "s/mode: smart/mode: ${TENANT_APPROVALS_MODE:-smart}/" "$TARGET_CONFIG"
sed -i "s/cron_mode: approve/cron_mode: ${TENANT_CRON_MODE:-approve}/" "$TARGET_CONFIG"

log "  config.yaml written."

# ── Build SOUL.md from template ──
log "Generating SOUL.md..."
cat "$TEMPLATE_DIR/SOUL.md" \
    | sed "s|<TENANT_NAME>|${TENANT_NAME}|g" \
    | sed "s|<TENANT_DESCRIPTION>|${TENANT_DESC}|g" \
    | sed "s|<TENANT_WORKSPACE>|${TENANT_WORKSPACE}|g" \
    | sed "s|<TENANT_TOOLSETS_DESCRIPTION>|${TOOLSETS_DESC}|g" \
    | sed "s|<TENANT_TTS_DESCRIPTION>||g" \
    > "$TENANT_PROFILE_DIR/SOUL.md"
echo -e "$REPO_DESC" >> "$TENANT_PROFILE_DIR/SOUL.md"

# Append TTS description
if [ "$TENANT_TTS_ENABLED" = "True" ]; then
  cat >> "$TENANT_PROFILE_DIR/SOUL.md" <<SOULTTS

## TTS
Tu TTS esta activado con voz ${TENANT_TTS_VOICE}. Alcance: ${TENANT_TTS_SCOPE}.
Cuando respondas mensajes que califiquen para audio (respuestas densas, >200 palabras),
genera un audio usando la herramienta TTS de Hermes con provider edge.
SOULTTS
else
  echo -e "\n## TTS\nTTS desactivado." >> "$TENANT_PROFILE_DIR/SOUL.md"
fi
log "  SOUL.md written."

# ── Build .env from template ──
log "Generating .env..."
# Try to read API key from Infisical or env, fallback to placeholder
API_KEY=""
if [ -n "$INFISICAL_TOKEN" ] && [ -n "$INFISICAL_PID" ]; then
    API_KEY=$(curl -sf "$INFISICAL_API/api/v3/secrets/raw/OPENCODE_GO_API_KEY?workspaceId=$INFISICAL_PID&environment=prod" \
        -H "Authorization: Bearer $INFISICAL_TOKEN" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('secret',{}).get('secretValue',''))" 2>/dev/null || echo "")
fi

ALLOWED_CSV=$(echo "$TENANT_ALLOWED" | tr '\n' ',' | sed 's/,$//')
GITHUB_TOKEN=""
GITHUB_USER=""
GROQ_API_KEY=""

# Read GROQ_API_KEY from Infisical (shared with main Hermes)
if [ -n "$INFISICAL_TOKEN" ] && [ -n "$INFISICAL_PID" ]; then
  GROQ_API_KEY=$(curl -sf "$INFISICAL_API/api/v3/secrets/raw/GROQ_API_KEY?workspaceId=$INFISICAL_PID&environment=prod" \
    -H "Authorization: Bearer $INFISICAL_TOKEN" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('secret',{}).get('secretValue',''))" 2>/dev/null || echo "")
  [ -n "$GROQ_API_KEY" ] && log "  ✓ GROQ_API_KEY read from Infisical" || warn "  ⚠ GROQ_API_KEY not found in Infisical"
fi

cat "$TEMPLATE_DIR/env.template" \
    | sed "s|<TENANT_NAME>|${TENANT_NAME}|g" \
    | sed "s|<TENANT_API_KEY>|${API_KEY:-OPENCODE_GO_API_KEY_PLACEHOLDER}|g" \
    | sed "s|<TENANT_WHATSAPP_NUMBER>|${TENANT_WA_NUMBER}|g" \
    | sed "s|<TENANT_ALLOWED_USERS_CSV>|${ALLOWED_CSV}|g" \
    | sed "s|<TENANT_GITHUB_TOKEN>|${GITHUB_TOKEN:-}|g" \
    | sed "s|<TENANT_GITHUB_USER>|${GITHUB_USER:-git}|g" \
    | sed "s|<TENANT_GROQ_API_KEY>|${GROQ_API_KEY:-}|g" \
    > "$TENANT_PROFILE_DIR/.env"
chmod 600 "$TENANT_PROFILE_DIR/.env"
log "  .env written."

# ── Clone repos ──
if [ "$TENANT_REPO_COUNT" -gt 0 ]; then
  log "Cloning repositories..."
  while IFS= read -r repo_line; do
    [ -z "$repo_line" ] && continue
    URL=$(echo "$repo_line" | python3 -c "import sys,json; print(json.load(sys.stdin)['url'])" 2>/dev/null || true)
    BRANCH=$(echo "$repo_line" | python3 -c "import sys,json; print(json.load(sys.stdin)['branch'])" 2>/dev/null || echo "main")
    REPO_NAME=$(basename "$URL" .git)
    TARGET_DIR="$TENANT_CWD/$REPO_NAME"

    if [ -d "$TARGET_DIR/.git" ]; then
        log "  $REPO_NAME: already cloned, pulling..."
        git -C "$TARGET_DIR" pull --ff-only origin "$BRANCH" 2>&1 | tail -1 || warn "  $REPO_NAME: pull failed"
    else
        log "  $REPO_NAME: cloning..."
        git clone -b "$BRANCH" "$URL" "$TARGET_DIR" 2>&1 | tail -1 || warn "  $REPO_NAME: clone failed"
    fi
done <<< "$(echo "$JSON" | python3 -c "
import sys, json
for r in json.load(sys.stdin)['repos']:
    print(json.dumps(r))
")"
fi

# ── Mark as tenant (marker file) ──
touch "$TENANT_PROFILE_DIR/.tenant"

# ── Create Hermes profile ──
log "Creating Hermes profile: $TENANT_NAME"
hermes profile create "$TENANT_NAME" 2>&1 || warn "hermes profile create failed (may need manual setup)"

# ── Install gateway systemd service ──
log "Installing gateway systemd service..."
systemctl --user enable "hermes-gateway-${TENANT_NAME}" 2>/dev/null || true
hermes -p "$TENANT_NAME" gateway install 2>&1 | tail -3 || warn "Gateway install may have failed"

# ── Output QR for WhatsApp pairing ──
log ""
log "============================================"
log "  WhatsApp pairing required for: $TENANT_NAME"
log "  Execute this on the VPS to get the QR code:"
log ""
log "    hermes -p $TENANT_NAME whatsapp"
log ""
log "  Or start the gateway and check logs:"
log "    systemctl --user start hermes-gateway-${TENANT_NAME}"
log "    journalctl -u hermes-gateway-${TENANT_NAME} -f"
log ""
log "  Tenant definition: $TENANT_PROFILE_DIR/"
log "============================================"

# ── Summary ──
log ""
log "✓ Tenant '$TENANT_NAME' provisioned successfully."
log "  Profile: $TENANT_PROFILE_DIR"
log "  Config:  $TENANT_PROFILE_DIR/config.yaml"
log "  SOUL:    $TENANT_PROFILE_DIR/SOUL.md"
log "  Env:     $TENANT_PROFILE_DIR/.env"
log "  Repos:   $TENANT_CWD"
log ""
log "Next step: pair WhatsApp by running 'hermes -p $TENANT_NAME whatsapp' on the VPS"
