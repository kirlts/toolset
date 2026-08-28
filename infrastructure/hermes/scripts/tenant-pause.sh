#!/usr/bin/env bash
# tenant-pause.sh — silencia por completo el WhatsApp de un tenant Hermes, y lo revierte.
#
#   tenant-pause.sh pause  <tenant>
#   tenant-pause.sh resume <tenant>
#   tenant-pause.sh status <tenant>
#
# Silenciar son dos cortes, uno por cada vía de salida hacia WhatsApp:
#
#   1. Entrante. WHATSAPP_ALLOWED_USERS pasa a un número imposible. El bridge
#      descarta cada mensaje con allowlist_mismatch antes de que el gateway lo
#      vea (allowlist.js: lista vacía o sin coincidencia => nadie pasa), así que
#      el agente no llega ni a redactar una respuesta. Se usa un valor imposible
#      y no la lista vacía porque el adapter, cuando la variable está vacía,
#      vuelve a llenarla desde config.yaml.
#
#   2. Saliente. Los cron jobs del tenant que estén activos se pausan uno por
#      uno, guardando sus ids: al reanudar se reactivan exactamente esos y no
#      los que ya estaban pausados de antes.
#
# El bridge sigue corriendo y conectado. La sesión de WhatsApp no se toca, de
# modo que despausar no implica re-parear el teléfono del tenant.
set -euo pipefail

ACTION="${1:-}"
TENANT="${2:-}"

if [ -z "$ACTION" ] || [ -z "$TENANT" ]; then
  echo "uso: $0 {pause|resume|status} <tenant>" >&2
  exit 2
fi

PROFILE_DIR="$HOME/.hermes/profiles/$TENANT"
ENV_FILE="$PROFILE_DIR/.env"
JOBS_FILE="$PROFILE_DIR/cron/jobs.json"
STATE_FILE="$PROFILE_DIR/.pause-state.json"
SERVICE="hermes-gateway-${TENANT}"
SENTINEL="00000000000000"

[ -d "$PROFILE_DIR" ] || { echo "no existe el perfil $TENANT en $PROFILE_DIR" >&2; exit 1; }

bridge_port() {
  grep -E "^WHATSAPP_BRIDGE_PORT=" "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]'
}

current_allowlist() {
  grep -E "^WHATSAPP_ALLOWED_USERS=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true
}

active_job_ids() {
  [ -f "$JOBS_FILE" ] || return 0
  python3 - "$JOBS_FILE" <<'PY'
import json, sys
raw = json.load(open(sys.argv[1]))
jobs = raw if isinstance(raw, list) else raw.get("jobs", [])
for job in jobs:
    if job.get("enabled"):
        print(job["id"], job.get("name", ""), sep="\t")
PY
}

verify() {
  local port; port="$(bridge_port)"
  echo "--- verificación ---"
  systemctl --user is-active "$SERVICE" >/dev/null 2>&1 \
    && echo "gateway:  activo" \
    || { echo "gateway:  CAÍDO"; return 1; }
  if [ -n "$port" ] && ss -tln | grep -q ":${port} "; then
    echo "bridge:   escuchando en ${port}"
  else
    echo "bridge:   NO escucha en ${port:-?}"; return 1
  fi
  local health; health="$(curl -sf --max-time 5 "http://127.0.0.1:${port}/health" || echo '{"status":"sin respuesta"}')"
  echo "whatsapp: $(python3 -c 'import json,sys; print(json.load(sys.stdin).get("status","?"))' <<<"$health")"
  echo "allowlist: $(current_allowlist)"
  echo "crons activos: $(active_job_ids | wc -l)"
}

case "$ACTION" in
  pause)
    if [ -f "$STATE_FILE" ]; then
      echo "$TENANT ya está pausado (existe $STATE_FILE). Usa resume primero." >&2
      exit 1
    fi

    ORIGINAL="$(current_allowlist)"
    [ -n "$ORIGINAL" ] || { echo "no encontré WHATSAPP_ALLOWED_USERS en $ENV_FILE" >&2; exit 1; }

    PAUSED_IDS=()
    while IFS=$'\t' read -r id name; do
      [ -n "$id" ] || continue
      hermes -p "$TENANT" cron pause "$id" >/dev/null
      PAUSED_IDS+=("$id")
      echo "cron pausado: $id  $name"
    done < <(active_job_ids)

    cp -p "$ENV_FILE" "${ENV_FILE}.bak-pause-$(date +%Y%m%d-%H%M%S)"
    sed -i "s|^WHATSAPP_ALLOWED_USERS=.*|WHATSAPP_ALLOWED_USERS=${SENTINEL}|" "$ENV_FILE"

    python3 - "$STATE_FILE" "$ORIGINAL" "${PAUSED_IDS[@]:-}" <<'PY'
import json, sys, datetime
state_file, original, *ids = sys.argv[1:]
json.dump({
    "paused_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "allowed_users": original,
    "paused_cron_ids": [i for i in ids if i],
}, open(state_file, "w"), indent=2)
PY

    systemctl --user restart "$SERVICE"
    sleep 12
    verify
    echo "estado guardado en $STATE_FILE"
    ;;

  resume)
    [ -f "$STATE_FILE" ] || { echo "$TENANT no está pausado (falta $STATE_FILE)" >&2; exit 1; }

    ORIGINAL="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["allowed_users"])' "$STATE_FILE")"
    sed -i "s|^WHATSAPP_ALLOWED_USERS=.*|WHATSAPP_ALLOWED_USERS=${ORIGINAL}|" "$ENV_FILE"

    while read -r id; do
      [ -n "$id" ] || continue
      hermes -p "$TENANT" cron resume "$id" >/dev/null
      echo "cron reanudado: $id"
    done < <(python3 -c 'import json,sys; [print(i) for i in json.load(open(sys.argv[1]))["paused_cron_ids"]]' "$STATE_FILE")

    systemctl --user restart "$SERVICE"
    sleep 12
    mv "$STATE_FILE" "${STATE_FILE}.done-$(date +%Y%m%d-%H%M%S)"
    verify
    ;;

  status)
    if [ -f "$STATE_FILE" ]; then
      echo "$TENANT: PAUSADO"
      cat "$STATE_FILE"
    else
      echo "$TENANT: activo"
    fi
    verify
    ;;

  *)
    echo "acción desconocida: $ACTION" >&2
    exit 2
    ;;
esac
