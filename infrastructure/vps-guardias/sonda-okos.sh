#!/usr/bin/env bash
# Corre en el servidor las sondas de latido de OKOS (puerta del fundador y motor), con los secretos
# que el propio servidor ya tiene, sin ningun archivo en ~/.claude.
# Uso: sonda-okos.sh founder|engine
#
# POR QUE EXISTE. Las sondas viven en conversio-connect (scripts/probe-*.sh) y leen sus secretos de
# ~/.claude. En el servidor ~/.claude se retiro con Claude, asi que desde entonces la sonda de la
# puerta decia «founder gateway probe skipped» cada 2 minutos y no empujaba latido. Solo lo empujaba
# el notebook, y la regla de Grafana avisa por SILENCIO: el 2026-11-12 el notebook estuvo
# suspendido de 01:56 a 12:11, la puerta respondia 200 por sus dos direcciones publicas y la
# alerta (issue #1824 de conversio-connect) salto igual.
#
# DE DONDE SALE CADA SECRETO, sin copiarlo a ningun archivo ni repositorio:
#   - la URL de la puerta: la arma el propio servicio que la sirve. Caddy publica
#     /kb/<KB_TOKEN_PUBLICADO>/..., y KB_TOKEN_PUBLICADO y FUNNEL_DOMAIN estan en /opt/toolset/.env.
#     Es la direccion del fundador (ver Caddyfile): sondear la misma que el usa.
#   - el token de empuje a Loki: Infisical del propio servidor, entorno prod, clave
#     GRAFANA_LOKI_PUSH_TOKEN, leido con el token de servicio que ya esta en el .env.
# Ambos viajan solo en variables de entorno del proceso de la sonda (FOUNDER_GATEWAY_URL y
# LOKI_PUSH_TOKEN, que la sonda lee antes que sus archivos). Nada se imprime.
set -uo pipefail

SONDA="${1:-}"
case "$SONDA" in
  founder) SCRIPT=probe-founder-gateway.sh ;;
  engine)  SCRIPT=probe-engine-health.sh ;;
  *) echo "uso: $0 founder|engine"; exit 2 ;;
esac

ENV_FILE="${OKOS_ENV_FILE:-/opt/toolset/.env}"
INFISICAL_URL="${OKOS_INFISICAL_URL:-http://127.0.0.1:8081}"
CLONE="${OKOS_CLONE:-${HOME}/.cache/okos/watchdog-clone}"
STAMP="${HOME}/.cache/okos/sonda-clone-refrescado"
REFRESCAR_CADA=1800

env_get() { grep -m1 "^$1=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true; }

[ -r "$ENV_FILE" ] || { echo "no puedo leer ${ENV_FILE}: la sonda no corre"; exit 1; }
[ -d "$CLONE/.git" ] || { echo "no hay clon de conversio-connect en ${CLONE}: la sonda no corre"; exit 1; }

# El clon se lleva a main, como hacia el vigia de publicacion en cada tick. Ese vigia ya no corre
# aqui (necesitaba credenciales de ~/.claude), asi que sin esto la sonda se quedaria en la version
# que tenia el clon el dia que dejo de actualizarse. Como mucho cada 30 minutos; si falla se sigue
# con lo que hay.
ahora="$(date +%s)"
ultimo="$(stat -c %Y "$STAMP" 2>/dev/null || echo 0)"
if [ $((ahora - ultimo)) -ge "$REFRESCAR_CADA" ]; then
  if git -C "$CLONE" fetch --quiet origin main 2>/dev/null \
     && git -C "$CLONE" checkout --quiet --force -B main origin/main 2>/dev/null; then
    mkdir -p "$(dirname "$STAMP")" && touch "$STAMP"
  else
    echo "no se pudo llevar el clon a main; se usa la version que tiene"
  fi
fi
[ -f "$CLONE/scripts/$SCRIPT" ] || { echo "falta ${CLONE}/scripts/${SCRIPT}"; exit 1; }

# Token de Loki desde Infisical. Si no responde, la sonda lo dice en su propio mensaje
# («no LOKI_PUSH_TOKEN ...») y no empuja.
SERVICE_TOKEN="$(env_get INFISICAL_SERVICE_TOKEN)"
if [ -n "$SERVICE_TOKEN" ]; then
  LOKI_PUSH_TOKEN="$(INFISICAL_SERVICE_TOKEN="$SERVICE_TOKEN" INFISICAL_URL="$INFISICAL_URL" python3 -c '
import json, os, urllib.request
base, tok = os.environ["INFISICAL_URL"], os.environ["INFISICAL_SERVICE_TOKEN"]
def get(path):
    req = urllib.request.Request(base + path, headers={"Authorization": "Bearer " + tok})
    return json.load(urllib.request.urlopen(req, timeout=8))
try:
    w = get("/api/v2/service-token")["workspace"]
    q = "?workspaceId=%s&environment=prod&secretPath=/" % w
    print(get("/api/v3/secrets/raw/GRAFANA_LOKI_PUSH_TOKEN" + q)["secret"]["secretValue"], end="")
except Exception:
    pass
' 2>/dev/null || true)"
  export LOKI_PUSH_TOKEN
fi

if [ "$SONDA" = founder ]; then
  dominio="$(env_get FUNNEL_DOMAIN)"
  token="$(env_get KB_TOKEN_PUBLICADO)"
  if [ -z "$dominio" ] || [ -z "$token" ]; then
    echo "faltan FUNNEL_DOMAIN o KB_TOKEN_PUBLICADO en ${ENV_FILE}: no se puede armar la URL de la puerta"
    exit 1
  fi
  export FOUNDER_GATEWAY_URL="https://${dominio}/kb/${token}/okos/mcp"
fi

exec bash "$CLONE/scripts/$SCRIPT"
