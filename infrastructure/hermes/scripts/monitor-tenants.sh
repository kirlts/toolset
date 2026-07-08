#!/usr/bin/env bash
# monitor-tenants.sh — health check for all active Hermes tenants.
# Called by the main Hermes cron system every 5 minutes.
# Silent when everything is OK; only outputs alert on failures.
set -euo pipefail

PROFILES_DIR="$HOME/.hermes/profiles"
ALERTS=""
THRESHOLD_MMIN="-15"   # log activity in last 15 min

for profile_dir in "$PROFILES_DIR"/*/; do
  [ -d "$profile_dir" ] || continue
  tenant=$(basename "$profile_dir")
  [ "$tenant" = "default" ] && continue
  [ -f "$profile_dir/.tenant" ] || continue

  # 1. Systemd gateway service
  if ! systemctl --user is-active "hermes-gateway-${tenant}" >/dev/null 2>&1 && \
     ! sudo systemctl is-active "hermes-gateway-${tenant}" >/dev/null 2>&1; then
    ALERTS="${ALERTS}⚠\u{fe0f} *${tenant}*: gateway service NOT ACTIVE\n"
    continue
  fi

  # 2. WhatsApp bridge port — read WHATSAPP_BRIDGE_PORT from .env
  env_file="$profile_dir/.env"
  if [ -f "$env_file" ]; then
    bridge_port=$(grep "^WHATSAPP_BRIDGE_PORT=" "$env_file" | cut -d= -f2)
    if [ -n "$bridge_port" ] && ! ss -tlnp | grep -q ":$bridge_port "; then
      ALERTS="${ALERTS}⚠\u{fe0f} *${tenant}*: WhatsApp bridge not listening on port ${bridge_port}\n"
    fi
  fi
done

if [ -n "$ALERTS" ]; then
  echo -e "\u{1f6e1}\u{fe0f} *Hermes Tenant Monitor*\n\nSe detectaron problemas en los siguientes tenants:\n\n${ALERTS}"
  exit 1
fi
exit 0
