#!/bin/bash
# Hermes Deploy Watch — monitorea gh run list cada 3 min
# no_agent=True: solo emite stdout si hay un nuevo fallo (silencio = todo ok)

set -euo pipefail

REPO="kirlts/toolset"
LAST_RUN_FILE="/tmp/hermes-deploy-last-run"

# Obtener último run
RUN_INFO=$(gh run list --repo "$REPO" --limit 1 --json number,conclusion,displayTitle,createdAt 2>/dev/null || echo "[]")
if [ "$RUN_INFO" = "[]" ] || [ -z "$RUN_INFO" ]; then
  exit 0
fi

RUN_NUM=$(echo "$RUN_INFO" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['number'])")
RUN_CONCLUSION=$(echo "$RUN_INFO" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['conclusion'])")
RUN_TITLE=$(echo "$RUN_INFO" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['displayTitle'])")

# Leer último notificado
LAST_NOTIFIED=""
if [ -f "$LAST_RUN_FILE" ]; then
  LAST_NOTIFIED=$(cat "$LAST_RUN_FILE")
fi

# Si es el mismo run que ya notificamos, salir
if [ "$RUN_NUM" = "$LAST_NOTIFIED" ]; then
  exit 0
fi

# Actualizar archivo de tracking
echo "$RUN_NUM" > "$LAST_RUN_FILE"

# Solo notificar si falló
if [ "$RUN_CONCLUSION" = "failure" ]; then
  echo "❌ Deploy #$RUN_NUM falló en toolset"
  echo "Pipeline: $RUN_TITLE"
  echo "Correlo con: gh run view $RUN_NUM --repo $REPO"
fi
