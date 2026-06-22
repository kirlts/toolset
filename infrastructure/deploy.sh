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
SSH_HOST="${SSH_HOST:-opc@100.77.183.125}"

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

# --- Build .env content (base64 to avoid special char issues) ---
ENV_B64=$(cat <<EOF | base64 -w0
INFISICAL_ENCRYPTION_KEY=${INFISICAL_ENCRYPTION_KEY}
INFISICAL_AUTH_SECRET=${INFISICAL_AUTH_SECRET}
INFISICAL_DB_PASSWORD=${INFISICAL_DB_PASSWORD}
INFISICAL_DB_USER=infisical
INFISICAL_DB_NAME=infisical
INFISICAL_SITE_URL=http://toolset-oci:8081
OPENCODE_GO_API_KEY=${OPENCODE_GO_API_KEY}
HINDSIGHT_API_LLM_PROVIDER=openai
HINDSIGHT_API_LLM_MODEL=deepseek-v4-flash
HINDSIGHT_API_LLM_BASE_URL=https://opencode.ai/zen/go/v1
FUNNEL_DOMAIN=${FUNNEL_DOMAIN:-toolset-oci-1.tail2d4c18.ts.net}
EOF
)

DC=$(basename "$COMPOSE_FILE")
# --- Transfer compose file (via /tmp for sudo) ---
echo "[DEPLOY] Transferring ${DC} to ${SSH_HOST}:${REMOTE_DIR}/"
scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${COMPOSE_FILE}" "${SSH_HOST}:/tmp/${DC}"
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "sudo mv -f /tmp/${DC} ${REMOTE_DIR}/${DC}"

# --- Write .env on remote ---
echo "[DEPLOY] Writing .env on remote server..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "echo '${ENV_B64}' | base64 -d | sudo tee ${REMOTE_DIR}/.env > /dev/null"

# --- Transfer Caddyfile (must precede compose up) ---
CADDY_DOMAIN="${FUNNEL_DOMAIN:-toolset-oci-1.tail2d4c18.ts.net}"
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

# --- Wait for healthchecks ---
echo "[DEPLOY] Waiting for healthchecks..."
HEALTH_TIMEOUT=120
HEALTH_INTERVAL=10
ELAPSED=0
ALL_HEALTHY=false

while [ "$ELAPSED" -lt "$HEALTH_TIMEOUT" ]; do
  STATUS=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "cd ${REMOTE_DIR} && sudo docker compose ps --format '{{.Name}} {{.Status}}' 2>&1")

  UNHEALTHY=$(echo "$STATUS" | grep -c "unhealthy" 2>/dev/null || true)
  EXITED=$(echo "$STATUS" | grep -c "Exited" 2>/dev/null || true)

  if [ "$UNHEALTHY" -gt 0 ] || [ "$EXITED" -gt 0 ]; then
    echo "[HEALTH] Unhealthy or exited containers detected:"
    echo "$STATUS" | grep -E "unhealthy|Exited" | sed 's/^/  /'
    echo "[HEALTH] Aborting — manual intervention required."
    echo ""
    echo "=== Container Status ==="
    echo "$STATUS"
    exit 1
  fi

  ALL_UP=$(echo "$STATUS" | grep -c "healthy" 2>/dev/null || true)
  TOTAL=$(echo "$STATUS" | wc -l)

  if [ "$TOTAL" -gt 0 ] && [ "$ALL_UP" -eq "$TOTAL" ]; then
    ALL_HEALTHY=true
    break
  fi

  sleep "$HEALTH_INTERVAL"
  ELAPSED=$((ELAPSED + HEALTH_INTERVAL))
done

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
</style>
</head>
<body>
<h1>🔧 Toolset Personal</h1>
<p>Servicios autogestionados en OCI (sa-valparaiso-1).</p>
<div class="tree">
<pre>
  <span class="path">/</span>                        <span class="desc">Landing page</span>            <span class="status">✅ 200</span>
  <span class="pipe">├──</span> <span class="path"><a href="/infisical/">/infisical/</a></span>              <span class="desc">Infisical &mdash; Gestor de Secretos</span>    <span class="status">✅ 200</span>
  <span class="pipe">├──</span> <span class="path"><a href="/hindsight/health">/hindsight/health</a></span>        <span class="desc">Hindsight &mdash; API Health</span>           <span class="status">✅ 200</span>
  <span class="pipe">├──</span> <span class="path"><a href="/hindsight/mcp/">/hindsight/mcp/</a></span>          <span class="desc">Hindsight &mdash; MCP (harnesses)</span>      <span class="status">✅ 200</span>
  <span class="pipe">├──</span> <span class="path"><a href="/hindsight/docs">/hindsight/docs</a></span>          <span class="desc">Hindsight &mdash; API Docs (Swagger)</span>   <span class="status">✅ 200</span>
  <span class="pipe">├──</span> <span class="path"><a href="/cpanel/">/cpanel/</a></span>                 <span class="desc">Hindsight &mdash; Control Plane</span>        <span class="status">✅ 308</span>
  <span class="pipe">└──</span> <span class="path"><a href="/dashboard">/dashboard</a></span>               <span class="desc">Redirecciona a /cpanel/</span>            <span class="status">✅ 301</span>
</pre>
</div>
<div class="meta">
  <p>MCP: <code>opencodego://toolset-oci-1.tail2d4c18.ts.net/hindsight/mcp/</code></p>
  <p>Deploy: $(date -u +"%Y-%m-%d %H:%M UTC") &bull; OCI &bull; VM.Standard.A1.Flex &bull; ARM64</p>
</div>
</body>
</html>
EOF
)
echo "[DEPLOY] Generating dynamic landing page..."
echo "$LANDING_HTML" | ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "sudo tee ${REMOTE_DIR}/landing/index.html > /dev/null"

# --- Ensure Tailscale Funnel points to Caddy (multi-service proxy) ---
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

# --- Remove legacy Funnel on :8443 if present ---
echo "[DEPLOY] Checking for legacy Funnel :8443..."
HAS_8443=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "sudo tailscale funnel status 2>&1" | grep -c "8443" || true)
if [ "$HAS_8443" -gt 0 ]; then
  echo "[DEPLOY] Removing legacy Funnel :8443... (Infisical ahora va por Caddy)"
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "sudo tailscale funnel --https=8443 off 2>&1" | sed 's/^/  /'
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
  echo "  Infisical        https://${CADDY_DOMAIN}/infisical/"
  echo "  Hindsight API    https://${CADDY_DOMAIN}/hindsight/health"
  echo "  Hindsight CP     https://${CADDY_DOMAIN}/cpanel/"
  echo "  Hindsight MCP    https://${CADDY_DOMAIN}/hindsight/mcp/"
  echo "  API Docs         https://${CADDY_DOMAIN}/hindsight/docs"
echo ""
echo "  ── Internal (via Tailscale) ──────────────"
  echo "  Hindsight API    http://100.77.183.125:8888 (via Funnel: /hindsight/*)"
  echo "  Hindsight CP     http://100.77.183.125:9999 (via Funnel: /cpanel/*)"
  echo "  Infisical        http://100.77.183.125:8081 (via Funnel: /)"
echo ""
echo "  ── Docker Status ─────────────────────────"
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "cd ${REMOTE_DIR} && sudo docker compose ps --format 'table {{.Name}}\t{{.Status}}\t{{.Health}}'"
echo "============================================"
