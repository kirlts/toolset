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

# --- Ensure Tailscale Funnel is active ---
echo "[DEPLOY] Verifying Tailscale Funnel..."
FUNNEL_STATUS=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "sudo tailscale funnel status 2>&1" || echo "FUNNEL_FAILED")
if echo "$FUNNEL_STATUS" | grep -q "Funnel on"; then
  echo "[DEPLOY] Tailscale Funnel OK"
elif echo "$FUNNEL_STATUS" | grep -q "FUNNEL_FAILED"; then
  echo "[DEPLOY] WARNING: Could not verify Funnel (non-fatal)"
  echo "  Manual: ssh ${SSH_HOST} 'sudo tailscale funnel --bg http://localhost:8888'"
else
  echo "[DEPLOY] Enabling Tailscale Funnel..."
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "sudo tailscale funnel --bg http://localhost:8888 2>&1" | sed 's/^/  /'
fi

if [ "$ALL_HEALTHY" = true ]; then
  echo "[DEPLOY] All services healthy after ${ELAPSED}s."
else
  echo "[DEPLOY] WARNING: Not all services reported healthy within ${HEALTH_TIMEOUT}s."
  echo "=== Final Container Status ==="
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "cd ${REMOTE_DIR} && sudo docker compose ps --format 'table {{.Name}}\t{{.Status}}\t{{.Health}}'"
  echo "[DEPLOY] Check logs: ssh ${SSH_HOST} 'cd ${REMOTE_DIR} && sudo docker compose logs --tail=50 <service>'"
fi
