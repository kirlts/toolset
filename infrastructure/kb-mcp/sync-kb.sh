#!/usr/bin/env bash
# sync-kb.sh — actualiza los clones de las KB en /opt/kb y reindexa si alguno cambio.
# Desplegado por deploy.sh a /home/opc/.hermes/scripts/. Cron cada 15 min.
# Acotado a proposito: solo toca /opt/kb y el contenedor kb-mcp. Nunca otros.
set -euo pipefail

KB_ROOT="${KB_ROOT:-/opt/kb}"
CONTAINER="${CONTAINER:-kb-mcp}"

export PATH="/usr/local/bin:/home/opc/.local/bin:$PATH"
export GIT_TERMINAL_PROMPT=0

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
    echo "[kb-sync] $(basename "$dir"): $(echo "$antes" | cut -c1-8) -> $(echo "$despues" | cut -c1-8)"
    cambio=1
  fi
done

if [ "$cambio" -eq 1 ]; then
  # El indice se reconstruye al arrancar; reiniciar solo este contenedor.
  sudo docker restart "$CONTAINER" >/dev/null
  echo "[kb-sync] $CONTAINER reindexado"
else
  echo "[kb-sync] sin cambios en ninguna KB"
fi
