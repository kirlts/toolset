#!/usr/bin/env bash
# Recicla tailscaled SOLO si su memoria pasó del umbral.
#
# POR QUE EXISTE (2026-08-18): tailscaled llego a 2.2 GB tras 54 dias sin reiniciarse,
# en una maquina de 10.9 GB que ya swapeaba. No pesa por el tamano de la tailnet
# --con los mismos 768 nodos, recien reiniciado usa 67 MB-- sino por el CHURN: el CI
# registra un nodo por corrida y nunca lo borra, y procesar esas altas/bajas durante
# semanas es lo que no se libera.
#
# El drop-in de systemd pone un techo duro de 1G, pero ese techo MATA el proceso en
# cualquier momento. Esto lo recicla antes, ordenadamente y a una hora sin nadie.
# No reinicia si no hace falta: en estado sano no hace nada y no corta la red.
set -uo pipefail
UMBRAL_MB=600
USO=$(( $(systemctl show tailscaled -p MemoryCurrent --value) / 1024 / 1024 ))
[ "$USO" -lt 1 ] && exit 0   # sin dato, no tocar
if [ "$USO" -lt "$UMBRAL_MB" ]; then
  logger -t reciclar-tailscaled "sano: ${USO}MB < ${UMBRAL_MB}MB, no se toca"
  exit 0
fi
logger -t reciclar-tailscaled "AL LIMITE: ${USO}MB >= ${UMBRAL_MB}MB, reciclando"
systemctl restart tailscaled
for i in $(seq 1 30); do
  if tailscale status --self=true --peers=false >/dev/null 2>&1; then
    NUEVO=$(( $(systemctl show tailscaled -p MemoryCurrent --value) / 1024 / 1024 ))
    logger -t reciclar-tailscaled "OK: volvio en $((i*2))s, ${USO}MB -> ${NUEVO}MB"
    exit 0
  fi
  sleep 2
done
logger -t reciclar-tailscaled "ALERTA: NO volvio en 60s"
exit 1
