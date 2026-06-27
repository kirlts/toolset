#!/usr/bin/env bash
# caddy-selfheal.sh — Verifica que Caddy responda en :8080. Si no, lo recrea.
# Corre como cron cada 5 min. No requiere sudo para curl.
# Edge case: docker-proxy pierde port binding tras restart del daemon Docker.

CADDY_URL="http://localhost:8080/health"
COMPOSE_DIR="/opt/toolset"
LOG="/tmp/caddy-selfheal.log"

# Test 1: Caddy responde via localhost?
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$CADDY_URL" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "502" ]; then
  # Caddy responde. 502 significa que el proxy funciona pero el backend falla (distinto problema).
  exit 0
fi

# Caddy no responde. Forzar recreación.
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Caddy no responde (HTTP $HTTP_CODE). Recreando..." >> "$LOG"
sudo fuser -k 8080/tcp 2>/dev/null || true
sleep 2
cd "$COMPOSE_DIR" && sudo docker compose up -d --force-recreate caddy 2>&1 | tail -3 >> "$LOG"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Caddy recreado." >> "$LOG"
