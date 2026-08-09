#!/usr/bin/env bash
# monitor-tenants.sh — health check for all active Hermes tenants.
# Called by the main Hermes cron system every 5 minutes.
# Silent when everything is OK; only outputs alert on failures.
# Rate limit: max 2 alerts per tenant per day (state in /tmp/tenant-alert-state/).
set -euo pipefail

PROFILES_DIR="$HOME/.hermes/profiles"
STATE_DIR="/tmp/tenant-alert-state"
MAX_ALERTS_PER_DAY=2
ALERTS=""

mkdir -p "$STATE_DIR"

# emit_alert <tenant> <message> — respeta el límite diario por tenant.
emit_alert() {
  local tenant="$1" msg="$2"
  local today
  today=$(date +%F)
  local day_file="$STATE_DIR/${tenant}.day"
  local count_file="$STATE_DIR/${tenant}.count"

  if [ -f "$day_file" ] && [ "$(cat "$day_file")" = "$today" ]; then
    local count=0
    [ -f "$count_file" ] && count=$(cat "$count_file")
    if [ "$count" -ge "$MAX_ALERTS_PER_DAY" ]; then
      return 0  # ya se alertó el máximo de hoy: silencioso
    fi
  else
    echo "$today" > "$day_file"
    echo 0 > "$count_file"
  fi

  ALERTS="${ALERTS}${msg}\n"
  local c=0
  [ -f "$count_file" ] && c=$(cat "$count_file")
  echo $((c + 1)) > "$count_file"
}

for profile_dir in "$PROFILES_DIR"/*/; do
  [ -d "$profile_dir" ] || continue
  tenant=$(basename "$profile_dir")
  [ "$tenant" = "default" ] && continue
  [ -f "$profile_dir/.tenant" ] || continue
  [ -f "$profile_dir/config.yaml" ] || continue  # solo perfiles realmente provisionados

  # 1. Gateway service — systemd OR process-based
  SERVICE_OK=false
  if systemctl --user is-active "hermes-gateway-${tenant}" >/dev/null 2>&1 || \
     sudo systemctl is-active "hermes-gateway-${tenant}" >/dev/null 2>&1; then
    SERVICE_OK=true
  elif pgrep -f "hermes.*(-p|--profile) ${tenant}.*gateway run" >/dev/null 2>&1; then
    SERVICE_OK=true
  fi
  if [ "$SERVICE_OK" = false ]; then
    emit_alert "$tenant" "⚠\\u{fe0f} *${tenant}*: gateway service NOT ACTIVE"
    continue
  fi

  # 2. WhatsApp bridge port — read WHATSAPP_BRIDGE_PORT from .env
  env_file="$profile_dir/.env"
  if [ -f "$env_file" ]; then
    bridge_port=$(grep "^WHATSAPP_BRIDGE_PORT=" "$env_file" | cut -d= -f2)
    if [ -n "$bridge_port" ] && ! ss -tlnp | grep -q ":$bridge_port "; then
      if [ "$tenant" = "tito" ]; then
        emit_alert "$tenant" "⚠\\u{fe0f} *tito*: sesión de WhatsApp caída — Oye, tienes que actualizar o reloguearte con el chip de Tito"
      else
        emit_alert "$tenant" "⚠\\u{fe0f} *${tenant}*: WhatsApp bridge not listening on port ${bridge_port}"
      fi
    fi
  fi
done

if [ -n "$ALERTS" ]; then
  echo -e "\\u{1f6e1}\\u{fe0f} *Hermes Tenant Monitor*\\n\\nSe detectaron problemas en los siguientes tenants:\\n\\n${ALERTS}"
  exit 1
fi
exit 0
