#!/usr/bin/env bash
# sync-kb.sh — actualiza el clon de la KB en el VPS y reindexa solo si cambio.
# Desplegado por deploy.sh a /home/opc/.hermes/scripts/. Cron cada 15 min.
# Acotado a proposito: solo toca /opt/kb y el contenedor kb-mcp. Nunca otros.
set -euo pipefail

KB_DIR="${KB_DIR:-/opt/kb/traza-ambiental}"
KB_BRANCH="${KB_BRANCH:-planning}"
CONTAINER="${CONTAINER:-kb-mcp}"

export PATH="/usr/local/bin:/home/opc/.local/bin:$PATH"
export GIT_TERMINAL_PROMPT=0

[ -d "$KB_DIR/.git" ] || { echo "[kb-sync] $KB_DIR no es un clon git"; exit 1; }

ANTES=$(git -C "$KB_DIR" rev-parse HEAD)
git -C "$KB_DIR" fetch --depth 1 origin "$KB_BRANCH" --quiet
git -C "$KB_DIR" reset --hard "origin/${KB_BRANCH}" --quiet
DESPUES=$(git -C "$KB_DIR" rev-parse HEAD)

if [ "$ANTES" = "$DESPUES" ]; then
  echo "[kb-sync] sin cambios ($(echo "$ANTES" | cut -c1-8))"
  exit 0
fi

echo "[kb-sync] $(echo "$ANTES" | cut -c1-8) -> $(echo "$DESPUES" | cut -c1-8), reindexando"
# El indice se reconstruye al arrancar; reiniciar solo este contenedor.
sudo docker restart "$CONTAINER" >/dev/null
echo "[kb-sync] $CONTAINER reiniciado"
