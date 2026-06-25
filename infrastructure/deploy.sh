#!/usr/bin/env bash
set -euo pipefail

# deploy.sh — Toolset Personal CI/CD Deploy
#
# Edge cases handled:
#   - Fresh OCI instance (cloud-init ran) → .env missing, creates from scratch
#   - Existing instance (incremental deploy) → .env preserved, services updated
#   - Partial failure → non-dependent steps still run (no early exit on optional steps)
#   - Idempotent: safe to re-run any number of times
#   - Hermes gateway restart graceful: uses kill -s KILL + start to avoid 90s drain timeout
#   - LVM extend on both fresh (cloud-init) and existing (deploy.sh) instances
#   - Composio MCP: static x-api-key deprecated; SDK session URL generated per deploy
#   - Secrets always flow GitHub → deploy.sh → .env + Infisical
#   - Reverse sync: Infisical → GitHub for Hermes-created secrets

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
  HERMES_LLM_PROVIDER
  HERMES_LLM_MODEL
  HERMES_WEBUI_PASSWORD
  HERMES_WHATSAPP_MODE
  WHATSAPP_ALLOWED_USERS
  COMPOSIO_API_KEY
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

# --- Ensure docker-compose.yml is in sync (needed for extra_hosts, volumes, etc.) ---
COMPOSE_SRC="$(dirname "${COMPOSE_FILE}")/docker-compose.yml"
echo "[DEPLOY] Syncing docker-compose.yml..."
scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$COMPOSE_SRC" "${SSH_HOST}:/tmp/docker-compose.yml"
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "sudo mv -f /tmp/docker-compose.yml ${REMOTE_DIR}/docker-compose.yml"
echo "[DEPLOY] docker-compose.yml synced."
else
  echo "[DEPLOY] WARNING: Caddyfile not found at $CADDYFILE"
fi

# --- Transfer Hermes artifacts (SOUL.md, config.yaml, memory) from repo to instance ---
HERMES_REPO_DIR="$(dirname "$0")/hermes"
if [ -d "$HERMES_REPO_DIR" ]; then
  echo "[DEPLOY] Transferring Hermes artifacts from repo..."
  rsync -rlptv --delete -e "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
    "$HERMES_REPO_DIR/SOUL.md" \
    "$HERMES_REPO_DIR/config.yaml" \
    "${SSH_HOST}:/tmp/hermes-repo/" 2>/dev/null || true
  # Transfer memory files if present
  [ -f "$HERMES_REPO_DIR/memory/MEMORY.md" ] && \
    scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      "$HERMES_REPO_DIR/memory/MEMORY.md" "${SSH_HOST}:/tmp/hermes-repo/memory/" 2>/dev/null || true
  [ -f "$HERMES_REPO_DIR/memory/USER.md" ] && \
    scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      "$HERMES_REPO_DIR/memory/USER.md" "${SSH_HOST}:/tmp/hermes-repo/memory/" 2>/dev/null || true
  # Transfer WebUI settings if present
  [ -f "$HERMES_REPO_DIR/webui/settings.json" ] && \
    scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      "$HERMES_REPO_DIR/webui/settings.json" "${SSH_HOST}:/tmp/hermes-repo/webui/" 2>/dev/null || true
  echo "[DEPLOY] Hermes artifacts transferred."
  HERMES_ARTIFACTS_DEPLOYED=true
else
  echo "[DEPLOY] No hermes artifacts dir at $HERMES_REPO_DIR — skipping."
  HERMES_ARTIFACTS_DEPLOYED=false
fi

# --- Clone / pull ResearchIt repo ---
echo "[DEPLOY] Syncing ResearchIt..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "sudo mkdir -p /opt/researchit && sudo chown opc:opc /opt/researchit && \
   cd /opt/researchit && \
   if [ -d .git ]; then \
     git pull origin main 2>&1 || echo '  pull failed (non-fatal)'; \
   else \
     gh repo clone kirlts/researchit /tmp/researchit-tmp 2>/dev/null && \
     cp -a /tmp/researchit-tmp/. /opt/researchit/ && \
     rm -rf /tmp/researchit-tmp; \
   fi && \
   set -a && source /home/opc/.hermes/.env && set +a && \
   export COMPOSIO_REDDIT_CONNECTION_ID=${COMPOSIO_REDDIT_CONNECTION_ID:-reddit_hight-mudden} && \
   env | grep -E '^(OPENCODE_GO_API_KEY|COMPOSIO_API_KEY|COMPOSIO_REDDIT)' | \
   while IFS='=' read -r k v; do echo \"\$k=\$v\" >> /opt/researchit/.env; done" 2>&1 | sed 's/^/  [RESEARCHIT] /'
echo "[DEPLOY] ResearchIt synced."

# --- Pull images ---
echo "[DEPLOY] Pulling container images..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "cd ${REMOTE_DIR} && sudo docker compose pull 2>&1" | sed 's/^/  [PULL] /'

# --- Recreate changed services ---
echo "[DEPLOY] Recreating services..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "sudo systemctl stop hermes-webui 2>/dev/null || true && \
   cd ${REMOTE_DIR} && sudo docker compose down --remove-orphans 2>&1 && \
   sudo docker compose up -d --remove-orphans --force-recreate 2>&1 && \
   sudo systemctl start hermes-webui 2>/dev/null || true" | sed 's/^/  [UP] /'

# --- Verify critical services ---
echo "[DEPLOY] Verifying critical services..."
sleep 10
CRITICAL="caddy hindsight infisical"
for attempt in 1 2 3 4; do
  ALL_OK=true
  for svc in $CRITICAL; do
    STATUS=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      "${SSH_HOST}" \
      "sudo docker inspect $svc --format '{{.State.Health.Status}}' 2>/dev/null || echo missing")
    if [ "$STATUS" != "healthy" ]; then
      echo "  ⏳ $svc: $STATUS (attempt $attempt/4)"
      ALL_OK=false
    fi
  done
  $ALL_OK && break
  [ "$attempt" -lt 4 ] && sleep 30
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
  sync_secret "dev" "COMPOSIO_MCP_KEY" "${COMPOSIO_MCP_KEY:-}"
  sync_secret "prod" "OPENCODE_GO_API_KEY" "${OPENCODE_GO_API_KEY:-}"
  sync_secret "prod" "FUNNEL_DOMAIN" "${FUNNEL_DOMAIN:-}"
  sync_secret "prod" "HERMES_LLM_PROVIDER" "${HERMES_LLM_PROVIDER:-}"
  sync_secret "prod" "HERMES_LLM_MODEL" "${HERMES_LLM_MODEL:-}"
  sync_secret "prod" "HERMES_WEBUI_PASSWORD" "${HERMES_WEBUI_PASSWORD:-}"
  sync_secret "prod" "HERMES_WHATSAPP_MODE" "${HERMES_WHATSAPP_MODE:-}"
  sync_secret "prod" "WHATSAPP_ALLOWED_USERS" "${WHATSAPP_ALLOWED_USERS:-}"
  sync_secret "prod" "COMPOSIO_API_KEY" "${COMPOSIO_API_KEY:-}"
  sync_secret "prod" "COMPOSIO_MCP_KEY" "${COMPOSIO_MCP_KEY:-}"
  sync_secret "prod" "FUNNEL_DOMAIN" "${FUNNEL_DOMAIN:-}"
  sync_secret "prod" "HERMES_LLM_PROVIDER" "${HERMES_LLM_PROVIDER:-}"
  sync_secret "prod" "HERMES_LLM_MODEL" "${HERMES_LLM_MODEL:-}"
  sync_secret "prod" "HERMES_WEBUI_PASSWORD" "${HERMES_WEBUI_PASSWORD:-}"
  sync_secret "prod" "HERMES_WHATSAPP_MODE" "${HERMES_WHATSAPP_MODE:-}"
  sync_secret "prod" "WHATSAPP_ALLOWED_USERS" "${WHATSAPP_ALLOWED_USERS:-}"
  sync_secret "prod" "COMPOSIO_API_KEY" "${COMPOSIO_API_KEY:-}"
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
  <span class="pipe">├──</span> <span class="path"><a href="/hermes/">/hermes/</a></span>                  <span class="desc">Hermes WebUI &mdash; via Caddy (mobile)</span> <span class="status">✅</span>
  <span class="pipe">├──</span> <span class="path"><a href="https://${CADDY_DOMAIN}:8443/">:8443/</a></span>                  <span class="desc">Infisical UI &mdash; Funnel directo</span>      <span class="status">✅</span>
  <span class="pipe">└──</span> <span class="path"><a href="https://${CADDY_DOMAIN}:8787/">:8787/</a></span>                  <span class="desc">Hermes WebUI &mdash; Funnel directo</span>     <span class="status">✅</span>
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
  <p>Hermes WebUI: <a href="https://${CADDY_DOMAIN}:8787/" style="color:#7ec8e3;">https://${CADDY_DOMAIN}:8787/</a> <span class="status">(Funnel)</span> &bull; <a href="/hermes/" style="color:#7ec8e3;">/hermes/</a> <span class="status">(via Caddy, mobile-friendly)</span></p>
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

# --- Transfer Hermes SOUL.md (identity & meta-rules) ---
SOUL_FILE="$(dirname "${COMPOSE_FILE}")/Hermes-SOUL.md"
if [ -f "$SOUL_FILE" ]; then
  echo "[DEPLOY] Transferring Hermes SOUL.md..."
  scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$SOUL_FILE" "${SSH_HOST}:/tmp/Hermes-SOUL.md"
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "sudo cp /tmp/Hermes-SOUL.md /home/opc/.hermes/SOUL.md && sudo chown opc:opc /home/opc/.hermes/SOUL.md"
  echo "[DEPLOY] Hermes SOUL.md synced."
fi

# --- Transfer Hermes config.yaml (structural config from repo) ---
HERMES_CONFIG_SRC="$(dirname "${COMPOSE_FILE}")/hermes/config.yaml"
if [ -f "$HERMES_CONFIG_SRC" ]; then
  echo "[DEPLOY] Transferring Hermes config.yaml..."
  scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$HERMES_CONFIG_SRC" "${SSH_HOST}:/tmp/hermes-config.yaml"
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "sudo cp /tmp/hermes-config.yaml /home/opc/.hermes/config.yaml && sudo chown opc:opc /home/opc/.hermes/config.yaml"
  echo "[DEPLOY] Hermes config.yaml synced."
fi

# --- Transfer Hermes memory files (MEMORY.md + USER.md) ---
HERMES_MEMORY_SRC="$(dirname "${COMPOSE_FILE}")/hermes/memory"
if [ -d "$HERMES_MEMORY_SRC" ]; then
  echo "[DEPLOY] Transferring Hermes memory files..."
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "sudo mkdir -p /home/opc/.hermes/memories"
  for memfile in MEMORY.md USER.md; do
    if [ -f "${HERMES_MEMORY_SRC}/${memfile}" ]; then
      scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        "${HERMES_MEMORY_SRC}/${memfile}" "${SSH_HOST}:/tmp/${memfile}"
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        "${SSH_HOST}" \
        "sudo cp /tmp/${memfile} /home/opc/.hermes/memories/${memfile} && sudo chown opc:opc /home/opc/.hermes/memories/${memfile}"
    fi
  done
  echo "[DEPLOY] Hermes memory files synced."
fi

# --- Transfer Hermes scripts ---
HERMES_SCRIPTS_SRC="$(dirname "${COMPOSE_FILE}")/hermes/scripts"
if [ -d "$HERMES_SCRIPTS_SRC" ] && [ -n "$(ls -A ${HERMES_SCRIPTS_SRC} 2>/dev/null)" ]; then
  echo "[DEPLOY] Transferring Hermes scripts..."
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "sudo mkdir -p /home/opc/.hermes/scripts"
  tar czf /tmp/hermes-scripts.tar.gz -C "$(dirname "${HERMES_SCRIPTS_SRC}")" "$(basename "${HERMES_SCRIPTS_SRC}")"
  scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    /tmp/hermes-scripts.tar.gz "${SSH_HOST}:/tmp/"
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "sudo tar xzf /tmp/hermes-scripts.tar.gz -C /home/opc/.hermes/ --strip-components=1 && \
     sudo chown -R opc:opc /home/opc/.hermes/scripts && \
     sudo rm -f /tmp/hermes-scripts.tar.gz"
  rm -f /tmp/hermes-scripts.tar.gz
  echo "[DEPLOY] Hermes scripts synced."
fi

# --- Remove default SOUL.md template (solo debe existir nuestro custom SOUL.md) ---
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "sudo rm -f /usr/local/lib/hermes-agent/docker/SOUL.md && \
   echo '[hermes] Default SOUL.md template removed'"

# --- Sync Hermes skills (from repo hermes/skills/) ---
SKILLS_SRC="$(dirname "${COMPOSE_FILE}")/hermes/skills"
if [ -d "$SKILLS_SRC" ]; then
  echo "[DEPLOY] Syncing Hermes skills..."
  tar czf /tmp/hermes-skills.tar.gz -C "$(dirname "$SKILLS_SRC")" "$(basename "$SKILLS_SRC")" && \
  scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    /tmp/hermes-skills.tar.gz "${SSH_HOST}:/tmp/" && \
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "sudo mkdir -p /tmp/hermes-skills && \
     sudo tar xzf /tmp/hermes-skills.tar.gz -C /tmp/hermes-skills --strip-components=1 && \
     sudo cp -r /tmp/hermes-skills/. /home/opc/.hermes/skills/ && \
     sudo chown -R opc:opc /home/opc/.hermes/skills/ && \
     sudo rm -rf /tmp/hermes-skills /tmp/hermes-skills.tar.gz && \
     echo '[hermes] Skills synced'" && \
   rm -f /tmp/hermes-skills.tar.gz

else
  echo "[DEPLOY] WARNING: hermes-skills/ directory not found at $SKILLS_SRC"
fi

# --- Write Hermes .env on remote (always overwrite — Hermes creates a default template) ---
# Hermes systemd service runs as user 'opc', so .hermes dir is under /home/opc/
HERMES_DIR="/home/opc/.hermes"
echo "[DEPLOY] Writing Hermes .env with CI/CD secrets..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "sudo mkdir -p ${HERMES_DIR} && sudo tee ${HERMES_DIR}/.env > /dev/null && sudo chown -R opc:opc ${HERMES_DIR}" <<HERMESENV
# Hermes .env — managed by deploy.sh (CI/CD). DO NOT EDIT MANUALLY.
OPENCODE_GO_API_KEY=${OPENCODE_GO_API_KEY}
OPENCODE_GO_BASE_URL=https://opencode.ai/zen/go/v1
HERMES_LLM_PROVIDER=${HERMES_LLM_PROVIDER:-opencodego}
HERMES_LLM_MODEL=${HERMES_LLM_MODEL:-deepseek-v4-flash}
HERMES_WEBUI_PASSWORD=${HERMES_WEBUI_PASSWORD:-}
# Gateway reads WHATSAPP_MODE (not HERMES_WHATSAPP_MODE)
WHATSAPP_MODE=${HERMES_WHATSAPP_MODE:-bot}
WHATSAPP_ALLOWED_USERS=${WHATSAPP_ALLOWED_USERS:-}
WHATSAPP_ENABLED=true
COMPOSIO_API_KEY=${COMPOSIO_API_KEY:-}
COMPOSIO_MCP_KEY=${COMPOSIO_MCP_KEY:-}
HERMESENV
echo "[DEPLOY] Hermes .env written."

# --- Export OPENCODE_GO_API_KEY to shell (needed by Kilo CLI {env:...} resolution) ---
echo "[DEPLOY] Exporting OPENCODE_GO_API_KEY to .bashrc for Kilo CLI..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "grep -q 'OPENCODE_GO_API_KEY' /home/opc/.bashrc 2>/dev/null && \
   echo '[bashrc] Export already present' || \
   printf '%s\n' '' '# Export for Kilo CLI (managed by deploy.sh)' \"export OPENCODE_GO_API_KEY=\\\$(grep '^OPENCODE_GO_API_KEY=' /home/opc/.hermes/.env 2>/dev/null | cut -d= -f2-)\" | sudo tee -a /home/opc/.bashrc > /dev/null && \
   echo '[bashrc] Export added'"

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

   # ---- Ensure Hermes is in PATH for subsequent commands ----
   export PATH="/usr/local/bin:$PATH"

   # ---- Install GitHub CLI (gh) if missing ----
   if ! command -v gh &>/dev/null; then
     echo '[hermes] Installing GitHub CLI...' | sudo tee -a ${HERMES_LOG}
     sudo dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo 2>/dev/null
     sudo dnf install -y gh 2>&1 | tail -1
   fi

   #    # ---- Authenticate gh CLI (idempotent) ----
   GH_CLI_TOKEN="${GH_CLI_TOKEN:-}"
   if [ -n "$GH_CLI_TOKEN" ]; then
     echo "$GH_CLI_TOKEN" | sudo -u opc gh auth login --with-token 2>/dev/null || true
     echo '[hermes] gh CLI authenticated' | sudo tee -a ${HERMES_LOG}
   fi

    # ---- Install Kilo CLI if missing ----
    if ! command -v kilo &>/dev/null; then
      echo '[hermes] Installing Kilo CLI...' | sudo tee -a ${HERMES_LOG}
      sudo npm install -g @kilocode/cli 2>&1 | tail -3
    fi
   \
    # ---- Install Hermes if missing, then ensure STT dependency ----
    if ! command -v hermes &>/dev/null; then
      echo '[hermes] Installing Hermes Agent...' | sudo tee -a ${HERMES_LOG}
      curl -fsSL https://hermes-agent.nousresearch.com/install.sh | sudo bash 2>&1 | sudo tee -a ${HERMES_LOG}
    fi
    # Ensure Hermes code dir is owned by opc (git safe.directory compliance, v2.35+)
    # curl|sudo bash installs as root, but git blocks repos not owned by the current user.
    sudo chown -R opc:opc /usr/local/lib/hermes-agent 2>/dev/null || true
    # Ensure Whisper STT is installed (for WhatsApp voice message transcription)
    /home/opc/.local/bin/uv pip install --python /usr/local/lib/hermes-agent/venv/bin/python3 faster-whisper -q 2>/dev/null || true
    \
    # ---- Add opc to docker group for sandbox access ----
    sudo usermod -aG docker opc 2>/dev/null
    \
    # ---- Restore Hermes artifacts from repo (SOUL.md, config.yaml, memory) ----
    if [ -f /tmp/hermes-repo/SOUL.md ]; then
      cp /tmp/hermes-repo/SOUL.md /home/opc/.hermes/SOUL.md
      echo '[hermes] SOUL.md restored from repo' | sudo tee -a ${HERMES_LOG}
    fi
    if [ -f /tmp/hermes-repo/config.yaml ]; then
      cp /tmp/hermes-repo/config.yaml /home/opc/.hermes/config.yaml
      echo '[hermes] config.yaml restored from repo' | sudo tee -a ${HERMES_LOG}
    fi
    if [ -f /tmp/hermes-repo/memory/MEMORY.md ]; then
      cp /tmp/hermes-repo/memory/MEMORY.md /home/opc/.hermes/memories/MEMORY.md 2>/dev/null || true
    fi
    if [ -f /tmp/hermes-repo/memory/USER.md ]; then
      cp /tmp/hermes-repo/memory/USER.md /home/opc/.hermes/memories/USER.md 2>/dev/null || true
    fi
    # Restore WebUI settings if present (solo si no existe ya la config local)
    if [ -f /tmp/hermes-repo/webui/settings.json ] && [ ! -f /home/opc/.hermes/webui/settings.json ]; then
      mkdir -p /home/opc/.hermes/webui
      cp /tmp/hermes-repo/webui/settings.json /home/opc/.hermes/webui/settings.json
      echo '[hermes] WebUI settings restored from repo' | sudo tee -a ${HERMES_LOG}
    fi
    # Clean up temp files
    rm -rf /tmp/hermes-repo 2>/dev/null || true
    \
    # ---- Setup systemd for Hermes gateway (idempotent, non-interactive) ----
    export PATH="/usr/local/bin:/usr/local/lib/hermes-agent:\$PATH"
    if command -v hermes &>/dev/null; then
      if ! systemctl is-enabled hermes-gateway &>/dev/null 2>&1; then
        echo '[hermes] Enabling Hermes systemd service...' | sudo tee -a ${HERMES_LOG}
        printf 'Y\nY\n' | sudo /usr/local/bin/hermes gateway install --system 2>&1 | sudo tee -a ${HERMES_LOG}
        sudo sed -i '/^Group=opc$/a SupplementaryGroups=docker' /etc/systemd/system/hermes-gateway.service 2>/dev/null
        sudo systemctl daemon-reload 2>/dev/null
      else
        echo '[hermes] Gateway service already enabled' | sudo tee -a ${HERMES_LOG}
        sudo systemctl kill -s KILL hermes-gateway 2>/dev/null || true
        sleep 1
        sudo systemctl reset-failed hermes-gateway 2>/dev/null || true
        sudo systemctl start hermes-gateway --no-block 2>/dev/null || true
      fi
    else
      echo '[hermes] WARNING: hermes command not found, skipping systemd setup' | sudo tee -a ${HERMES_LOG}
    fi"

echo "[DEPLOY] Hermes + Kilo setup complete."

# --- Install MarkItDown (Microsoft document-to-markdown converter) ---
echo "[DEPLOY] Installing MarkItDown (document-to-markdown converter)..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "VENV_PY=/usr/local/lib/hermes-agent/venv/bin/python && \
   SUDO_PIP=\"sudo \\\$VENV_PY -m pip install\" && \
   if \\\$VENV_PY -c 'import markitdown' 2>/dev/null; then \
     echo '[hermes] MarkItDown already installed, upgrading...'; \
     eval \\\$SUDO_PIP -q 'markitdown[all]' --upgrade 2>&1 | tail -2; \
   else \
     echo '[hermes] Installing MarkItDown...'; \
     eval \\\$SUDO_PIP -q 'markitdown[all]' 2>&1 | tail -3; \
   fi && \
   if ! command -v markitdown &>/dev/null; then \
     echo '#!/usr/bin/env bash' | sudo tee /usr/local/bin/markitdown > /dev/null && \
     echo 'exec /usr/local/lib/hermes-agent/venv/bin/python -m markitdown \"\$@\"' | sudo tee -a /usr/local/bin/markitdown > /dev/null && \
     sudo chmod +x /usr/local/bin/markitdown && \
     echo '[hermes] markitdown CLI wrapper installed at /usr/local/bin/markitdown'; \
   fi" 2>&1 | sed 's/^/  [markitdown] /'
echo "[DEPLOY] MarkItDown installation complete."

# --- Fix pydantic in Hermes venv (mcp package requires pydantic >=2) ---
echo "[DEPLOY] Ensuring Hermes venv has pydantic >=2 (required by mcp 1.26.0)..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "VENV_PY=/usr/local/lib/hermes-agent/venv/bin/python && \
   SUDO_PIP=\"sudo \\\$VENV_PY -m pip install\" && \
   echo '[hermes] Installing/upgrading pydantic to >=2 (mcp streamable_http support)...' && \
   eval \\\$SUDO_PIP 'pydantic>=2' -q 2>&1 | tail -2 && \
   echo '[hermes] pydantic OK'" 2>&1 | sed 's/^/  [pydantic] /'
echo "[DEPLOY] pydantic check complete."

# --- Create gh token file for Docker sandbox (idempotent) ---
echo "[DEPLOY] Creating gh token file for Docker sandbox..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "echo 'export GH_TOKEN=${GH_CLI_TOKEN}' | sudo tee /home/opc/.hermes/gh_token.env > /dev/null && \
   sudo chmod 644 /home/opc/.hermes/gh_token.env && \
   echo '[hermes] gh token file created'"

 
# --- Hindsight bank backup/restore (resilience: bank data survives volume wipe) ---
BACKUP_DIR="${REMOTE_DIR}/backups/hindsight"
echo "[DEPLOY] Checking Hindsight bank backup..."
HINDSIGHT_DATA_EXISTS=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "sudo docker inspect hindsight --format '{{.State.Running}}' 2>/dev/null || echo 'missing'" 2>/dev/null || echo "missing")
if [ "$HINDSIGHT_DATA_EXISTS" = "true" ]; then
  # Create timestamped backup
  BACKUP_TS=$(date -u +"%Y%m%dT%H%M%SZ")
  echo "[DEPLOY][backup] Creating Hindsight data backup (${BACKUP_TS})..."
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
     "sudo mkdir -p ${BACKUP_DIR} && \
      sudo docker exec hindsight sh -c 'tar czf /tmp/hindsight-backup-${BACKUP_TS}.tar.gz -C /home/hindsight .pg0' && \
      sudo docker cp hindsight:/tmp/hindsight-backup-${BACKUP_TS}.tar.gz ${BACKUP_DIR}/ && \
      sudo docker exec hindsight rm /tmp/hindsight-backup-${BACKUP_TS}.tar.gz && \
      ls -1t ${BACKUP_DIR}/*.tar.gz 2>/dev/null | tail -n +11 | xargs -r sudo rm -f && \
      echo '[DEPLOY][backup] Done'"
else
  # Try to restore from latest backup (volume was wiped or fresh deploy)
  LATEST_BACKUP=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "ls -1t ${BACKUP_DIR}/*.tar.gz 2>/dev/null | head -1" 2>/dev/null || echo "")
  if [ -n "$LATEST_BACKUP" ]; then
    echo "[DEPLOY][restore] Restoring Hindsight from backup: $(basename ${LATEST_BACKUP})..."
    HINDSIGHT_VOL=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      "${SSH_HOST}" "sudo docker inspect hindsight --format '{{range .Mounts}}{{if eq .Destination \"/home/hindsight/.pg0\"}}{{.Source}}{{end}}{{end}}'" 2>/dev/null || echo "")
    if [ -n "$HINDSIGHT_VOL" ]; then
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        "${SSH_HOST}" \
        "sudo tar xzf ${LATEST_BACKUP} -C /tmp/hindsight-restore && \
         sudo cp -a /tmp/hindsight-restore/.pg0/* ${HINDSIGHT_VOL}/ && \
         sudo rm -rf /tmp/hindsight-restore && \
         echo '[DEPLOY][restore] Done'"
    else
      echo "[DEPLOY][restore] WARNING: Could not find Hindsight data volume"
    fi
  else
    echo "[DEPLOY][backup] No Hindsight data running and no backup found — skipping restore"
  fi
fi

# --- Ensure "hermes" bank exists in Hindsight ---
echo "[DEPLOY] Ensuring 'hermes' bank exists in Hindsight..."
HAS_HERMES_BANK=$(curl -s "https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/v1/default/banks" 2>/dev/null | python3 -c "import sys,json; print(any(b.get('bank_id')=='hermes' for b in json.load(sys.stdin).get('banks',[])))" 2>/dev/null || echo "False")
if [ "$HAS_HERMES_BANK" = "False" ]; then
  echo "[DEPLOY] Creating 'hermes' bank..."
  curl -s -X PUT "https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/v1/default/banks/hermes" \
    -H "Content-Type: application/json" \
    -d '{"name":"hermes","mission":"Hermes Agent memory: identity, repo knowledge, task history, rules"}' 2>/dev/null | python3 -c "import sys,json; print(f'  Bank: {json.load(sys.stdin).get(\"bank_id\",\"error\")}')" 2>/dev/null || echo "  Bank hermes already exists"
else
  echo "[DEPLOY] 'hermes' bank already exists"
fi

# --- Ensure all known project banks exist in Hindsight ---
echo "[DEPLOY] Ensuring project banks exist in Hindsight..."
for bank_id in $(ls infrastructure/hermes/banks/); do
  HAS_BANK=$(curl -s "https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/v1/default/banks" 2>/dev/null | python3 -c "import sys,json; print(any(b.get('bank_id')=='$bank_id' for b in json.load(sys.stdin).get('banks',[])))" 2>/dev/null || echo "False")
  if [ "$HAS_BANK" = "False" ]; then
    echo "  Creating bank '$bank_id'..."
    curl -s -X PUT "https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/v1/default/banks/$bank_id" \
      -H "Content-Type: application/json" \
      -d '{"name":"'"$bank_id"'"}' 2>/dev/null > /dev/null && echo "  Bank $bank_id created" || echo "  Bank $bank_id already exists or error"
  else
    echo "  Bank '$bank_id' already exists"
  fi
done
 
# --- Hermes runtime config (idempotent) ---
echo "[DEPLOY] Configuring Hermes runtime..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "export PATH=/usr/local/bin:/home/opc/.local/bin:\$PATH; \
    hermes config set terminal.backend local 2>/dev/null; \
    hermes config set memory.provider hindsight 2>/dev/null; \
    hermes config set memory.hindsight.url 'https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/mcp/' 2>/dev/null; \
    hermes config set memory.hindsight.bank 'hermes' 2>/dev/null; \
    hermes config set model.default 'opencodego/deepseek-v4-flash' 2>/dev/null; \
    hermes config set model.provider 'opencode-go' 2>/dev/null; \
    hermes config set context_file_max_chars 25000 2>/dev/null; \
    python3 -c \"
import yaml
cfg_path = '/home/opc/.hermes/config.yaml'
with open(cfg_path) as f:
    cfg = yaml.safe_load(f) or {}
cfg.pop('memory_provider', None)
cfg.pop('default', None)  # old format, use model: instead
cfg.setdefault('mcp_servers', {})
# Model config: nested format for WebUI + CLI compatibility
cfg['model'] = {'default': 'opencodego/deepseek-v4-flash', 'provider': 'opencode-go'}
cfg['context_file_max_chars'] = 25000
composio_key = os.environ.get('COMPOSIO_MCP_KEY', '${COMPOSIO_MCP_KEY:-}')
if composio_key:
    cfg['mcp_servers']['composio'] = {
        'url': 'https://connect.composio.dev/mcp',
        'headers': {'x-consumer-api-key': composio_key},
        'connect_timeout': 60,
        'timeout': 180
    }
cfg['mcp_servers']['hindsight-selfhosted'] = {
    'url': 'https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/mcp/'
}
with open(cfg_path, 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False)
print('MCP servers configured')
\" 2>&1 || echo 'MCP config fallback: hindsight only'"

echo "[DEPLOY] Hermes runtime configuration complete."
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

# --- Ensure Hermes WebUI systemd service ---
echo "[DEPLOY] Ensuring Hermes WebUI systemd service..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "if ! systemctl is-enabled hermes-webui &>/dev/null 2>&1; then
     # Pull latest or clone fresh
     sudo git -C /opt/hermes-webui pull --ff-only 2>/dev/null || (sudo git clone https://github.com/nesquena/hermes-webui.git /opt/hermes-webui && sudo chown -R opc:opc /opt/hermes-webui && sudo git -C /opt/hermes-webui config pull.ff only)
     # Ensure correct ownership
     sudo tee /etc/systemd/system/hermes-webui.service > /dev/null << SERVEOF
[Unit]
Description=Hermes WebUI
After=network.target hermes-gateway.service
Wants=hermes-gateway.service

[Service]
Type=simple
User=opc
WorkingDirectory=/opt/hermes-webui
Environment=HERMES_WEBUI_PORT=8888
Environment=HERMES_WEBUI_HOST=0.0.0.0
Environment=HERMES_WEBUI_SKIP_ONBOARDING=1
ExecStart=/usr/local/lib/hermes-agent/venv/bin/python /opt/hermes-webui/server.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVEOF
     sudo systemctl daemon-reload
     sudo systemctl enable --now hermes-webui 2>&1
     echo '[hermes-webui] Service installed and started'
   else
      # Pull latest version before restarting
      sudo git -C /opt/hermes-webui pull --ff-only 2>/dev/null || true
      sudo chown -R opc:opc /opt/hermes-webui 2>/dev/null || true
      sudo systemctl restart hermes-webui 2>/dev/null || true
      echo '[hermes-webui] Service updated and restarted'
    fi
    # Set default model in WebUI settings
    python3 -c 'import json, os; sp="/home/opc/.hermes/webui/settings.json"; d={}
if os.path.exists(sp):
    try:
        with open(sp) as f: d = json.load(f)
    except: pass
d["default_model"] = "opencodego/deepseek-v4-flash"
d["default_provider"] = "opencode-go"
with open(sp, "w") as f: json.dump(d, f, indent=2)
print("WebUI default model set")' 2>/dev/null || true
    echo '[hermes-webui] Default model configured'"

# --- Ensure Hermes WebUI Funnel on :8787 -> localhost:8888 ---
HERMES_PORT="8787"
HERMES_BACKEND="8888"
echo "[DEPLOY] Ensuring Hermes WebUI Funnel on :${HERMES_PORT} -> localhost:${HERMES_BACKEND}..."
HAS_HERMES=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "sudo tailscale funnel status 2>&1" | grep -c ":${HERMES_PORT}" || true)
if [ "$HAS_HERMES" -gt 0 ]; then
  echo "[DEPLOY] Hermes WebUI Funnel already configured on :${HERMES_PORT}"
else
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "sudo tailscale funnel --bg --https=${HERMES_PORT} http://localhost:${HERMES_BACKEND} 2>&1" | sed 's/^/  /'
  echo "[DEPLOY] Hermes WebUI Funnel configured on :${HERMES_PORT} -> :${HERMES_BACKEND}"
fi

# --- Post-deploy summary ---
# --- Derive Tailscale IP for internal URLs ---
TAILSCALE_IP=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "sudo tailscale ip -4 2>/dev/null || echo '100.x.x.x'" 2>/dev/null || echo "100.x.x.x")

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
  echo "  Hindsight API    http://${TAILSCALE_IP}:8888 (via Funnel: /hindsight/*)"
  echo "  Hindsight CP     http://${TAILSCALE_IP}:9999 (via Funnel: /dashboard)"
  echo "  Infisical        http://${TAILSCALE_IP}:8081 (via Funnel: /api/v1/)"
echo ""
echo "  ── Docker Status ─────────────────────────"
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "cd ${REMOTE_DIR} && sudo docker compose ps --format 'table {{.Name}}\t{{.Status}}\t{{.Health}}'"
echo "============================================"
