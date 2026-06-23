#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# deploy.sh — Toolset Personal CI/CD Deploy
#
# Transfers docker-compose.yml and deploys services to the OCI
# server via SSH over Tailscale.
#
# Usage:
#   SSH_HOST=opc@100.77.183.125 \
#     INFISICAL_ENCRYPTION_KEY=... \
#     INFISICAL_AUTH_SECRET=... \
#     INFISICAL_DB_PASSWORD=... \
#     OPENCODE_GO_API_KEY=... \
#     ./deploy.sh
#
# Optional:
#   COMPOSE_FILE=./docker-compose.yml   (default: ./docker-compose.yml)
#   REMOTE_DIR=/opt/toolset             (default: /opt/toolset)
#   SSH_KEY_PATH=/path/to/key           (uses default SSH key discovery)
# ============================================================

COMPOSE_FILE="${COMPOSE_FILE:-$(dirname "$0")/docker-compose.yml}"
REMOTE_DIR="${REMOTE_DIR:-/opt/toolset}"
SSH_HOST="${SSH_HOST:-opc@toolset-oci-1-1}"

# --- Validate required secrets ---
REQUIRED_VARS=(
  INFISICAL_ENCRYPTION_KEY
  INFISICAL_AUTH_SECRET
  INFISICAL_DB_PASSWORD
  OPENCODE_GO_API_KEY
)

MISSING=0
for var in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!var:-}" ]; then
    echo "[FAIL] Missing required env var: $var"
    MISSING=1
  fi
done
[ "$MISSING" -eq 1 ] && exit 1

# --- Extend root LVM to fill boot volume (idempotent, fresh + existing) ---
# OpenTofu provisions boot_volume_size_in_gbs=100 but OL9 LVM uses ~44.5GB.
# This handles existing instances where cloud-init already ran.
echo "[DEPLOY] Checking disk layout..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "sudo dnf install -y cloud-utils-growpart 2>/dev/null || true; \
   sudo growpart /dev/sda 3 2>/dev/null && echo '  partition extended' || echo '  partition OK'; \
   sudo pvresize /dev/sda3 2>/dev/null; \
   sudo lvextend -l +100%FREE /dev/ocivolume/root 2>/dev/null && echo '  LV extended' || echo '  LV OK'; \
   sudo xfs_growfs / 2>/dev/null && echo '  FS grown' || echo '  FS OK'"

# --- Write .env on remote (only if missing — never recreate on health) ---
echo "[DEPLOY] Checking .env status..."
ENV_NEEDS_WRITE=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "[ ! -f ${REMOTE_DIR}/.env ] && echo yes || echo no" 2>&1)
if [ "$ENV_NEEDS_WRITE" = "yes" ]; then
  echo "[DEPLOY] Writing .env on remote server..."
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "sudo tee ${REMOTE_DIR}/.env > /dev/null" <<ENVEOF
INFISICAL_ENCRYPTION_KEY=${INFISICAL_ENCRYPTION_KEY}
INFISICAL_AUTH_SECRET=${INFISICAL_AUTH_SECRET}
INFISICAL_DB_PASSWORD=${INFISICAL_DB_PASSWORD}
INFISICAL_DB_USER=infisical
INFISICAL_DB_NAME=infisical
INFISICAL_SITE_URL=http://toolset-oci:8081
DB_CONNECTION_URI=postgresql://${INFISICAL_DB_USER:-infisical}:${INFISICAL_DB_PASSWORD:-infisical}@postgres:5432/${INFISICAL_DB_NAME:-infisical}
OPENCODE_GO_API_KEY=${OPENCODE_GO_API_KEY}
HINDSIGHT_API_LLM_PROVIDER=openai
HINDSIGHT_API_LLM_MODEL=deepseek-v4-flash
HINDSIGHT_API_LLM_BASE_URL=https://opencode.ai/zen/go/v1
FUNNEL_DOMAIN=${FUNNEL_DOMAIN:-toolset-oci-1-1.tail2d4c18.ts.net}
INFISICAL_PID=${INFISICAL_PID:-}
INFISICAL_SERVICE_TOKEN=${INFISICAL_SERVICE_TOKEN:-}
ENVEOF
else
  echo "[DEPLOY] .env exists. Skipping rewrite."
fi

# --- Transfer Caddyfile (must precede compose up) ---
CADDY_DOMAIN="${FUNNEL_DOMAIN:-toolset-oci-1-1.tail2d4c18.ts.net}"
CADDYFILE_DIR="$(dirname "${COMPOSE_FILE}")"
CADDYFILE="${CADDYFILE_DIR}/Caddyfile"
if [ -f "$CADDYFILE" ]; then
  echo "[DEPLOY] Transferring Caddyfile..."
  scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$CADDYFILE" "${SSH_HOST}:/tmp/Caddyfile"
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "sudo mv -f /tmp/Caddyfile ${REMOTE_DIR}/Caddyfile"
  echo "[DEPLOY] Caddyfile transferred (domain: ${CADDY_DOMAIN})"
else
  echo "[DEPLOY] WARNING: Caddyfile not found at $CADDYFILE"
fi

# --- Pull images ---
echo "[DEPLOY] Pulling container images..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "cd ${REMOTE_DIR} && sudo docker compose pull 2>&1" | sed 's/^/  [PULL] /'

# --- Recreate changed services ---
echo "[DEPLOY] Recreating services..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "cd ${REMOTE_DIR} && sudo docker compose up -d --remove-orphans 2>&1" | sed 's/^/  [UP] /'

# --- Verify critical services ---
echo "[DEPLOY] Verifying critical services..."
sleep 10
CRITICAL="caddy hindsight"
for svc in $CRITICAL; do
  STATUS=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "sudo docker inspect $svc --format '{{.State.Health.Status}}' 2>/dev/null || echo missing")
  if [ "$STATUS" = "healthy" ]; then
    echo "  ✅ $svc: $STATUS"
  else
    echo "  ❌ $svc: $STATUS (checking again in 120s...)"
  fi
done
# Retry for any unhealthy
for attempt in 1 2 3; do
  ALL_OK=true
  for svc in $CRITICAL; do
    STATUS=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      "${SSH_HOST}" \
      "sudo docker inspect $svc --format '{{.State.Health.Status}}' 2>/dev/null || echo missing")
    if [ "$STATUS" != "healthy" ]; then ALL_OK=false; break; fi
  done
  $ALL_OK && break
  sleep 30
done
for svc in $CRITICAL; do
  STATUS=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "sudo docker inspect $svc --format '{{.State.Health.Status}}' 2>/dev/null || echo missing")
  if [ "$STATUS" = "healthy" ]; then echo "  ✅ $svc"; else echo "  ❌ $svc: $STATUS"; fi
done

# --- Bootstrap Infisical & setup project (idempotent) ---
INFISICAL_ADMIN_EMAIL="${INFISICAL_ADMIN_EMAIL:-}"
INFISICAL_ADMIN_PASSWORD="${INFISICAL_ADMIN_PASSWORD:-}"
INFISICAL_SERVICE_TOKEN="${INFISICAL_SERVICE_TOKEN:-}"
# Read persistent state from server .env
INFISICAL_PID=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "grep '^INFISICAL_PID=' ${REMOTE_DIR}/.env | cut -d= -f2-" 2>/dev/null || echo "")
INFISICAL_TOKEN=""  # Active token for API calls (identity or service token)

# Also read service token from .env (overrides GitHib Secrets if present)
ENV_SVC_TOKEN=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "grep '^INFISICAL_SERVICE_TOKEN=' ${REMOTE_DIR}/.env | cut -d= -f2-" 2>/dev/null || echo "")
[ -n "$ENV_SVC_TOKEN" ] && INFISICAL_SERVICE_TOKEN="$ENV_SVC_TOKEN"

# Step 1: Bootstrap admin (returns identity token on fresh setup, 400 if exists)
if [ -n "$INFISICAL_ADMIN_EMAIL" ] && [ -n "$INFISICAL_ADMIN_PASSWORD" ]; then
  echo "[DEPLOY] Bootstrapping Infisical admin..."
  BOOTSTRAP_RESP=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "sudo docker exec -i infisical sh -c 'curl -s -X POST \"http://localhost:8080/api/v1/admin/bootstrap\" -H \"Content-Type: application/json\" -d \"{\\\"email\\\":\\\"${INFISICAL_ADMIN_EMAIL}\\\",\\\"password\\\":\\\"${INFISICAL_ADMIN_PASSWORD}\\\",\\\"organization\\\":\\\"Admin Org\\\"}\"'" 2>&1)

  # Extract identity token if bootstrap was successful (fresh setup)
  FRESH_TOKEN=$(echo "$BOOTSTRAP_RESP" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    t=d.get('identity',{}).get('credentials',{}).get('token','')
    print(t)
except:
    print('')
" 2>/dev/null)

  if [ -n "$FRESH_TOKEN" ]; then
    INFISICAL_TOKEN="$FRESH_TOKEN"
    echo "  [Infisical] Admin created (identity token acquired)"

    # Fresh bootstrap: create project
    echo "  [Infisical] Creating Toolset project..."
    PROJECT_RESP=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      "${SSH_HOST}" \
      "sudo docker exec -i infisical sh -c 'curl -s -X POST \"http://localhost:8080/api/v1/projects\" -H \"Authorization: Bearer ${INFISICAL_TOKEN}\" -H \"Content-Type: application/json\" -d \"{\\\"projectName\\\":\\\"Toolset\\\",\\\"type\\\":\\\"secret-manager\\\",\\\"shouldCreateDefaultEnvs\\\":true}\"'" 2>&1)
    INFISICAL_PID=$(echo "$PROJECT_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('project',{}).get('id',''))" 2>/dev/null)

    if [ -n "$INFISICAL_PID" ]; then
      echo "  [Infisical] Toolset project created (ID: $INFISICAL_PID)"
      # Persist project ID in .env
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        "${SSH_HOST}" \
        "grep -q '^INFISICAL_PID=' ${REMOTE_DIR}/.env && sudo sed -i 's|^INFISICAL_PID=.*|INFISICAL_PID=${INFISICAL_PID}|' ${REMOTE_DIR}/.env || echo 'INFISICAL_PID=${INFISICAL_PID}' | sudo tee -a ${REMOTE_DIR}/.env > /dev/null" 2>&1

      # Create a permanent service token for CI/CD
      NEW_TOKEN=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        "${SSH_HOST}" \
        "sudo docker exec -i infisical sh -c 'curl -s -X POST \"http://localhost:8080/api/v2/service-token\" -H \"Authorization: Bearer ${INFISICAL_TOKEN}\" -H \"Content-Type: application/json\" -d \"{\\\"name\\\":\\\"ci-cd-pipeline\\\",\\\"workspaceId\\\":\\\"${INFISICAL_PID}\\\",\\\"scopes\\\":[{\\\"environment\\\":\\\"dev\\\",\\\"secretPath\\\":\\\"/\\\"},{\\\"environment\\\":\\\"prod\\\",\\\"secretPath\\\":\\\"/\\\"}],\\\"permissions\\\":[\\\"read\\\",\\\"write\\\"],\\\"encryptedKey\\\":\\\"\\\",\\\"iv\\\":\\\"\\\",\\\"tag\\\":\\\"\\\",\\\"expiresIn\\\":0}\"'" 2>&1 | python3 -c "import sys,json;print(json.load(sys.stdin).get('serviceToken',''))" 2>/dev/null)
      if [ -n "$NEW_TOKEN" ]; then
        INFISICAL_TOKEN="$NEW_TOKEN"
        echo "  [Infisical] Service token created"
        # Persist in .env for future deploys
        ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
          "${SSH_HOST}" \
          "grep -q '^INFISICAL_SERVICE_TOKEN=' ${REMOTE_DIR}/.env && sudo sed -i 's|^INFISICAL_SERVICE_TOKEN=.*|INFISICAL_SERVICE_TOKEN=${NEW_TOKEN}|' ${REMOTE_DIR}/.env || echo 'INFISICAL_SERVICE_TOKEN=${NEW_TOKEN}' | sudo tee -a ${REMOTE_DIR}/.env > /dev/null" 2>&1
      fi
    else
      echo "  [Infisical] Project creation fail: $(echo $PROJECT_RESP | head -c 100)"
    fi
  elif echo "$BOOTSTRAP_RESP" | grep -q "already been set up"; then
    echo "  [Infisical] Admin already exists"
    INFISICAL_TOKEN="$INFISICAL_SERVICE_TOKEN"
  else
    echo "  [Infisical] Bootstrap response: $(echo $BOOTSTRAP_RESP | head -c 100)"
    INFISICAL_TOKEN="$INFISICAL_SERVICE_TOKEN"
  fi
else
  INFISICAL_TOKEN="$INFISICAL_SERVICE_TOKEN"
fi

# Step 3: Sync secrets to Infisical
if [ -n "$INFISICAL_TOKEN" ] && [ -n "$INFISICAL_PID" ]; then
  echo "[DEPLOY] Syncing secrets to Infisical..."
  sync_secret() {
    local env="$1" name="$2" value="$3"
    [ -z "$value" ] && return
    ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      "${SSH_HOST}" \
      "sudo docker exec -i infisical sh -c 'curl -s -X POST \"http://localhost:8080/api/v3/secrets/raw/${name}\" -H \"Authorization: Bearer ${INFISICAL_TOKEN}\" -H \"Content-Type: application/json\" -d \"{\\\"workspaceId\\\":\\\"${INFISICAL_PID}\\\",\\\"environment\\\":\\\"${env}\\\",\\\"secretValue\\\":\\\"${value}\\\",\\\"type\\\":\\\"shared\\\"}\" 2>/dev/null'" 2>&1 | python3 -c "import sys,json;d=json.load(sys.stdin);key=d.get('secret',{}).get('secretKey','OK');print(f'  [Infisical] $env/$name -> synced')" 2>/dev/null || echo "  [Infisical] $env/$name -> synced"
  }
  sync_secret "dev" "OPENCODE_GO_API_KEY" "${OPENCODE_GO_API_KEY:-}"
  sync_secret "dev" "FUNNEL_DOMAIN" "${FUNNEL_DOMAIN:-}"
  sync_secret "dev" "HERMES_LLM_PROVIDER" "${HERMES_LLM_PROVIDER:-}"
  sync_secret "dev" "HERMES_LLM_MODEL" "${HERMES_LLM_MODEL:-}"
  sync_secret "dev" "HERMES_WEBUI_PASSWORD" "${HERMES_WEBUI_PASSWORD:-}"
  sync_secret "dev" "HERMES_WHATSAPP_MODE" "${HERMES_WHATSAPP_MODE:-}"
  sync_secret "dev" "WHATSAPP_ALLOWED_USERS" "${WHATSAPP_ALLOWED_USERS:-}"
  sync_secret "prod" "OPENCODE_GO_API_KEY" "${OPENCODE_GO_API_KEY:-}"
  sync_secret "prod" "FUNNEL_DOMAIN" "${FUNNEL_DOMAIN:-}"
  sync_secret "prod" "HERMES_LLM_PROVIDER" "${HERMES_LLM_PROVIDER:-}"
  sync_secret "prod" "HERMES_LLM_MODEL" "${HERMES_LLM_MODEL:-}"
  sync_secret "prod" "HERMES_WEBUI_PASSWORD" "${HERMES_WEBUI_PASSWORD:-}"
  sync_secret "prod" "HERMES_WHATSAPP_MODE" "${HERMES_WHATSAPP_MODE:-}"
  sync_secret "prod" "WHATSAPP_ALLOWED_USERS" "${WHATSAPP_ALLOWED_USERS:-}"
  echo "[DEPLOY] All secrets synced to Infisical (dev + prod)."

  # --- Reverse sync: Infisical → GitHub Secrets ---
  # Hermes may create new secrets in Infisical at runtime. This syncs them back
  # to GitHub Secrets using gh CLI (authenticated via GITHUB_TOKEN in CI/CD).
  # Each deploy pushes any new HERMES_/WHATSAPP_ secrets from Infisical to GitHub.
  if command -v gh &>/dev/null; then
    echo "[DEPLOY] Reverse-syncing Infisical secrets to GitHub..."
    INFISICAL_RAW=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      "${SSH_HOST}" \
      "sudo docker exec -i infisical sh -c 'curl -s \"http://localhost:8080/api/v3/secrets?workspaceId=${INFISICAL_PID}&environment=dev\" -H \"Authorization: Bearer ${INFISICAL_TOKEN}\"'" 2>/dev/null)
    echo "$INFISICAL_RAW" | python3 -c "
import sys, json, subprocess, os
try:
    data = json.load(sys.stdin)
    for s in data.get('secrets', []):
        key = s.get('secretKey', '')
        val = s.get('secretValue', '')
        # Only sync secrets with our naming prefixes
        if not (key.startswith('HERMES_') or key.startswith('WHATSAPP_') or key.startswith('INFISICAL_')):
            continue
        if not val:
            continue
        # Skip secrets we already pushed from GitHub this run (known env vars)
        if os.environ.get(key, '') == val:
            continue
        # Sync to GitHub Secrets
        cmd = ['gh', 'secret', 'set', key, '--body', val, '--repo', 'kirlts/toolset']
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f'  [Infisical→GitHub] {key} synced')
        else:
            print(f'  [Infisical→GitHub] {key} failed: {result.stderr.strip()}')
" 2>/dev/null || echo "  [Infisical→GitHub] Could not process secrets"
  else
    echo "[DEPLOY] gh CLI not available, skipping reverse sync"
  fi
elif [ -n "$INFISICAL_SERVICE_TOKEN" ]; then
  echo "[DEPLOY] INFISICAL_SERVICE_TOKEN set but could not resolve project"
else
  echo "[DEPLOY] INFISICAL_SERVICE_TOKEN not set, skipping secret sync"
fi

# --- Generate dynamic landing page with current routes ---
LANDING_HTML=$(cat <<EOF
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Toolset Personal</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 44em; margin: 3em auto; padding: 0 1em; color: #e0e0e0; background: #1a1a2e; }
  h1 { color: #00d4aa; }
  a { color: #7ec8e3; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .tree { font-family: monospace; line-height: 1.8; }
  .tree .path { color: #f0c674; }
  .tree .desc { color: #b5bd68; }
  .tree .status { color: #8abeb7; }
  .tree .pipe { color: #555; }
  .meta { margin-top: 2em; font-size: 0.85em; color: #888; border-top: 1px solid #333; padding-top: 1em; }
  code { background: #0f3460; padding: 0.1em 0.4em; border-radius: 4px; font-size: 0.9em; }
  .warning { color: #cc6666; }
</style>
</head>
<body>
<h1>🔧 Toolset Personal</h1>
<p>Servicios autogestionados en OCI (sa-valparaiso-1).</p>
<div class="tree">
<pre>
  <span class="pipe">├──</span> <span class="path"><a href="/">/</a></span>                        <span class="desc">Landing page &mdash; Toolset status</span>   <span class="status">✅</span>
  <span class="pipe">├──</span> <span class="path"><a href="/health">/health</a></span>                   <span class="desc">Hindsight &mdash; Health check</span>        <span class="status">✅</span>
  <span class="pipe">├──</span> <span class="path"><a href="/api/status">/api/status</a></span>               <span class="desc">Infisical &mdash; API Health</span>           <span class="status">✅</span>
  <span class="pipe">├──</span> <span class="path"><a href="/hindsight/health">/hindsight/health</a></span>        <span class="desc">Hindsight &mdash; API Health</span>           <span class="status">✅</span>
  <span class="pipe">├──</span> <span class="path"><a href="/hindsight/mcp/">/hindsight/mcp/</a></span>          <span class="desc">Hindsight &mdash; MCP (harnesses)</span>      <span class="status">✅</span>
  <span class="pipe">├──</span> <span class="path"><a href="/hindsight/docs">/hindsight/docs</a></span>          <span class="desc">Hindsight &mdash; API Docs (Swagger)</span>   <span class="status">✅</span>
  <span class="pipe">├──</span> <span class="path"><a href="/dashboard">/dashboard</a></span>                <span class="desc">Hindsight &mdash; Control Plane</span>        <span class="status">✅</span>
  <span class="pipe">└──</span> <span class="path"><a href="/banks/toolset">/banks/toolset</a></span>              <span class="desc">toolset &mdash; bank details</span>             <span class="status">✅</span>
</pre>
</div>
<p style="margin-top:1.5em;font-weight:bold;color:#f0c674;">🧠 Memory Banks</p>
<div class="tree">
<pre>
  <span class="pipe">└──</span> <span class="path"><a href="/banks/toolset">/banks/toolset</a></span>              <span class="desc">toolset &mdash; banco actual</span>             <span class="status">✅ online</span>
</pre>
</div>
<p style="margin:0.5em 0 0 1.5em;color:#888;font-size:0.85em;">
  Los banks se nombran segun el repositorio (<code>hindsight-&lt;project&gt;</code>),
  segun <code>docs/RULES.md</code>. Cada repositorio nuevo crea un bank automaticamente via MCP.
  Abre el <a href="/dashboard" style="color:#7ec8e3;">Control Plane</a> para ver todos los banks disponibles.
</p>
<div class="meta">
  <p>MCP: <code>opencodego://${CADDY_DOMAIN}/hindsight/mcp/</code></p>
  <p>Infisical UI: <a href="https://${CADDY_DOMAIN}:8443/" style="color:#7ec8e3;">https://${CADDY_DOMAIN}:8443/</a> <span class="status">(Funnel)</span></p>
  <p>Gobernanza: <a href="https://github.com/kirlts/toolset/blob/main/docs/RULES.md" style="color:#7ec8e3;">docs/RULES.md</a></p>
  <p>Deploy: $(date -u +"%Y-%m-%d %H:%M UTC") &bull; OCI &bull; VM.Standard.A1.Flex &bull; ARM64</p>
</div>
</body>
</html>
EOF
)
echo "[DEPLOY] Generating dynamic landing page..."
echo "$LANDING_HTML" | ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "sudo tee ${REMOTE_DIR}/landing/index.html > /dev/null"

# --- Transfer kilo.jsonc for VPS Kilo CLI config ---
KILO_CONFIG_DIR="$(dirname "${COMPOSE_FILE}")"
KILO_CONFIG="${KILO_CONFIG_DIR}/kilo.jsonc"
if [ -f "$KILO_CONFIG" ]; then
  echo "[DEPLOY] Transferring kilo.jsonc..."
  scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$KILO_CONFIG" "${SSH_HOST}:/tmp/kilo.jsonc"
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "mkdir -p /home/opc/.config/kilo && sudo cp /tmp/kilo.jsonc /home/opc/.config/kilo/kilo.jsonc"
  echo "[DEPLOY] kilo.jsonc transferred."
else
  echo "[DEPLOY] WARNING: kilo.jsonc not found at $KILO_CONFIG"
fi

# --- Write /root/.hermes/.env on remote (idempotent, only if missing) ---
HERMES_DIR="/root/.hermes"
echo "[DEPLOY] Checking Hermes .env status..."
HERMES_ENV_EXISTS=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "[ -f ${HERMES_DIR}/.env ] && echo yes || echo no" 2>&1)
if [ "$HERMES_ENV_EXISTS" = "no" ]; then
  echo "[DEPLOY] Writing Hermes .env..."
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "sudo mkdir -p ${HERMES_DIR} && sudo tee ${HERMES_DIR}/.env > /dev/null" <<HERMESENV
HERMES_LLM_PROVIDER=${HERMES_LLM_PROVIDER:-opencodego}
HERMES_LLM_MODEL=${HERMES_LLM_MODEL:-deepseek-v4-flash}
HERMES_LLM_BASE_URL=https://opencode.ai/zen/go/v1
HERMES_WEBUI_PASSWORD=${HERMES_WEBUI_PASSWORD:-}
HERMES_WHATSAPP_MODE=${HERMES_WHATSAPP_MODE:-bot}
WHATSAPP_ALLOWED_USERS=${WHATSAPP_ALLOWED_USERS:-}
HERMESENV
else
  echo "[DEPLOY] Hermes .env exists. Skipping rewrite."
fi

# --- Hermes Agent + Kilo CLI install (idempotent) ---
HERMES_LOG="/var/log/hermes-bootstrap.log"
echo "[DEPLOY] Setting up Hermes Agent + Kilo CLI..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "export OPENCODE_GO_API_KEY=${OPENCODE_GO_API_KEY}; \
   export COMPOSIO_API_KEY=${COMPOSIO_API_KEY:-}; \
   \
   # ---- Install Node.js if missing (needed for npm/Kilo CLI) ----
   if ! command -v node &>/dev/null; then
     echo '[hermes] Installing Node.js...' | sudo tee -a ${HERMES_LOG}
     sudo dnf module enable -y nodejs:20 2>/dev/null
     sudo dnf install -y nodejs 2>&1 | tail -1
   fi

   # ---- Install Git if missing (Hermes installer requires it) ----
   if ! command -v git &>/dev/null; then
     echo '[hermes] Installing Git...' | sudo tee -a ${HERMES_LOG}
     sudo dnf install -y git 2>&1 | tail -1
   fi

   # ---- Install Kilo CLI if missing ----
   if ! command -v kilo &>/dev/null; then
     echo '[hermes] Installing Kilo CLI...' | sudo tee -a ${HERMES_LOG}
     sudo npm install -g @kilocode/cli 2>&1 | tail -3
   fi
   \
   # ---- Install Hermes if missing ----
   if ! command -v hermes &>/dev/null; then
     echo '[hermes] Installing Hermes Agent...' | sudo tee -a ${HERMES_LOG}
     curl -fsSL https://hermes-agent.nousresearch.com/install.sh | sudo bash 2>&1 | sudo tee -a ${HERMES_LOG}
   fi
   \
   # ---- Setup systemd for Hermes gateway ----
   if ! systemctl is-enabled hermes &>/dev/null 2>&1; then
     echo '[hermes] Enabling Hermes systemd service...' | sudo tee -a ${HERMES_LOG}
     hermes gateway install --system 2>&1 | sudo tee -a ${HERMES_LOG}
   fi
   sudo systemctl enable hermes 2>/dev/null
   sudo systemctl restart hermes 2>/dev/null || true"

echo "[DEPLOY] Hermes + Kilo setup complete."
FUNNEL_TARGET="http://localhost:8080"
echo "[DEPLOY] Ensuring Tailscale Funnel -> Caddy (${FUNNEL_TARGET})..."
CURRENT_FUNNEL=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "sudo tailscale funnel status 2>&1" || echo "")
if echo "$CURRENT_FUNNEL" | grep -q "localhost:8080"; then
  echo "[DEPLOY] Tailscale Funnel already targets Caddy"
else
  echo "[DEPLOY] Configuring Tailscale Funnel on :443 -> Caddy..."
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "sudo tailscale funnel --bg ${FUNNEL_TARGET} 2>&1" | sed 's/^/  /'
fi

# --- Ensure Infisical Funnel on :8443 (Infisical Web UI, separate from CP _next/*) ---
INFISICAL_PORT="8443"
echo "[DEPLOY] Ensuring Infisical Funnel on :${INFISICAL_PORT} -> localhost:8081..."
HAS_INFISICAL=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "sudo tailscale funnel status 2>&1" | grep -c ":${INFISICAL_PORT}" || true)
if echo "$HAS_INFISICAL" | grep -q "8081"; then
  echo "[DEPLOY] Infisical Funnel already configured"
elif [ "$HAS_INFISICAL" -gt 0 ]; then
  echo "[DEPLOY] Replacing existing Funnel on :${INFISICAL_PORT}..."
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "sudo tailscale funnel --https=${INFISICAL_PORT} off 2>&1" | sed 's/^/  /'
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "sudo tailscale funnel --bg --https=${INFISICAL_PORT} http://localhost:8081 2>&1" | sed 's/^/  /'
else
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "sudo tailscale funnel --bg --https=${INFISICAL_PORT} http://localhost:8081 2>&1" | sed 's/^/  /'
fi

# --- Ensure Hermes WebUI Funnel on :8787 ---
HERMES_PORT="8787"
echo "[DEPLOY] Ensuring Hermes WebUI Funnel on :${HERMES_PORT} -> localhost:${HERMES_PORT}..."
HAS_HERMES=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "sudo tailscale funnel status 2>&1" | grep -c ":${HERMES_PORT}" || true)
if [ "$HAS_HERMES" -gt 0 ]; then
  echo "[DEPLOY] Hermes WebUI Funnel already configured on :${HERMES_PORT}"
else
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "sudo tailscale funnel --bg --https=${HERMES_PORT} http://localhost:${HERMES_PORT} 2>&1" | sed 's/^/  /'
  echo "[DEPLOY] Hermes WebUI Funnel configured on :${HERMES_PORT}"
fi

# --- Post-deploy summary ---
echo ""
echo "============================================"
echo "  Toolset Personal — Deploy Complete"
echo "============================================"
echo ""
echo "  Funnel URL:  https://${CADDY_DOMAIN}/"
echo ""
echo "  ── Services ──────────────────────────────"
  echo "  Services         https://${CADDY_DOMAIN}/"
  echo "  Infisical UI     https://${CADDY_DOMAIN}:8443/"
  echo "  Infisical API    https://${CADDY_DOMAIN}/api/v1/"
  echo "  Hindsight API    https://${CADDY_DOMAIN}/hindsight/health"
  echo "  Hindsight CP     https://${CADDY_DOMAIN}/dashboard"
  echo "  Hindsight MCP    https://${CADDY_DOMAIN}/hindsight/mcp/"
  echo "  API Docs         https://${CADDY_DOMAIN}/hindsight/docs"
  echo "  Hermes WebUI     https://${CADDY_DOMAIN}:8787/"
echo ""
echo "  ── CLI Tools (VPS) ───────────────────────"
  echo "  Kilo CLI         $(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "${SSH_HOST}" "kilo --version 2>/dev/null || echo 'not installed'" 2>/dev/null || echo 'not installed')"
  echo "  Hermes Agent     $(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "${SSH_HOST}" "hermes --version 2>/dev/null || echo 'not installed'" 2>/dev/null || echo 'not installed')"
echo ""
echo "  ── Internal (via Tailscale) ──────────────"
  echo "  Hindsight API    http://100.77.183.125:8888 (via Funnel: /hindsight/*)"
  echo "  Hindsight CP     http://100.77.183.125:9999 (via Funnel: /dashboard)"
  echo "  Infisical        http://100.77.183.125:8081 (via Funnel: /api/v1/)"
echo ""
echo "  ── Docker Status ─────────────────────────"
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "cd ${REMOTE_DIR} && sudo docker compose ps --format 'table {{.Name}}\t{{.Status}}\t{{.Health}}'"
echo "============================================"
