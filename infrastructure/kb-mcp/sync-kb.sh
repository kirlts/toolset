#!/usr/bin/env bash
# sync-kb.sh — actualiza los clones de las KB en /opt/kb y reindexa si alguno cambio.
# Desplegado por deploy.sh a /home/opc/.hermes/scripts/. Cron cada 15 min.
# Acotado a proposito: solo toca /opt/kb y el contenedor kb-mcp. Nunca otros.
set -euo pipefail

KB_ROOT="${KB_ROOT:-/opt/kb}"
CONTAINER="${CONTAINER:-kb-mcp}"

export PATH="/usr/local/bin:/home/opc/.local/bin:$PATH"
export GIT_TERMINAL_PROMPT=0

# Cada linea del log lleva su hora: sin eso, la anomalia del 2026-07-27 (un indice viejo
# servido despues de un reinicio anotado) fue imposible de reconstruir — habia lineas pero
# no se podian ordenar contra los eventos de despliegue y cron.
log() { echo "[kb-sync $(date -u +%H:%M:%S)] $*"; }

cambio=0
for dir in "$KB_ROOT"/*/; do
  [ -d "${dir}.git" ] || continue
  rama=$(git -C "$dir" rev-parse --abbrev-ref HEAD)
  antes=$(git -C "$dir" rev-parse HEAD)
  # SIN --depth: el clon es partial (blob:none), asi el historial completo de
  # commits se mantiene y crece. La temporalidad (fechas por nodo) depende de eso.
  git -C "$dir" fetch origin "$rama" --quiet
  git -C "$dir" reset --hard "origin/${rama}" --quiet
  despues=$(git -C "$dir" rev-parse HEAD)
  if [ "$antes" != "$despues" ]; then
    log "$(basename "$dir"): $(echo "$antes" | cut -c1-8) -> $(echo "$despues" | cut -c1-8)"
    cambio=1
  fi
done

if [ "$cambio" -eq 1 ]; then
  # El indice se reconstruye al arrancar; reiniciar solo este contenedor.
  sudo docker restart "$CONTAINER" >/dev/null
  # Lazo CERRADO: reiniciar y asumir que quedo bien es el mismo patron que la
  # vigilancia-que-anota-normal. Se comprueba contra el propio servicio: /kb/salud
  # debe responder y declarar las KB. Si a los 60s no responde, se dice ALERTA en el
  # log — que es lo unico que este script puede hacer, pero queda dicho con hora.
  # La ruta interna es /salud (el /kb lo antepone el proxy), y el contenedor no trae
  # curl: se consulta con su propio python.
  for i in $(seq 1 12); do
    salud=$(sudo docker exec "$CONTAINER" python3 -c 'import urllib.request;print(urllib.request.urlopen("http://127.0.0.1:8765/salud",timeout=4).read().decode())' 2>/dev/null || true)
    [ -n "$salud" ] && break
    sleep 5
  done
  if [ -n "${salud:-}" ]; then
    log "$CONTAINER reindexado y verificado: $salud"
  else
    log "ALERTA: $CONTAINER no respondio /kb/salud tras el reinicio"
  fi
else
  log "sin cambios en ninguna KB"
fi
