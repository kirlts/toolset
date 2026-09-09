#!/usr/bin/env bash
# Deja el servidor de la base de conocimiento sirviendo despues de un arranque, y publica el 443.
#
# POR QUE EXISTE, con su fecha. El 2026-09-06 a las 03:42 esta maquina se apago de forma abrupta
# —dockerd registro decenas de «layer not mounted», que es la firma de una caida sucia—. Al volver,
# el contenedor `kb-mcp` quedo en `Exited (255)` y NO lo trajo de vuelta su propia politica
# `restart: unless-stopped`: un contenedor que muere en una caida sucia queda en un estado que
# docker no reintenta. Ademas la publicacion del 443 —que es `tailscale funnel`, configuracion de
# runtime que no vive declarada en ningun archivo— tampoco estaba.
#
# El costo fue TRES DIAS de base inconsultable para todo consumidor remoto, y nadie se entero
# porque nada lo vigilaba. La vigilancia vive ahora en el barrido de kb-okos
# (`tools/base_responde.py`, revision permanente); esto es la otra mitad: que vuelva sola.
#
# Es idempotente a proposito: si ya esta arriba y ya esta publicado, no toca nada y sale 0. Asi
# puede correr en cada arranque sin pensar, y tambien a mano cuando alguien quiera asegurarse.
set -uo pipefail

COMPOSE_DIR=/opt/toolset
SERVICIO=kb-mcp
PUERTO_CADDY=http://localhost:8080

log() { logger -t levantar-kb "$*"; echo "[levantar-kb] $*"; }

# --- 1. el servidor de la base ---------------------------------------------------------------
estado="$(docker inspect "$SERVICIO" --format '{{.State.Status}}' 2>/dev/null || echo ausente)"
if [ "$estado" = "running" ]; then
  log "el servidor ya corre, no se toca"
elif [ "$estado" = "ausente" ]; then
  # No existe el contenedor: lo crea el compose. NO se construye la imagen acá —un build en el
  # arranque puede tardar mucho y competir por los dos nucleos de esta maquina—.
  log "el contenedor no existe: lo levanta compose"
  ( cd "$COMPOSE_DIR" && docker compose up -d --no-build "$SERVICIO" ) \
    || log "ALERTA: compose no pudo levantarlo"
else
  log "el servidor esta en «$estado»: arrancandolo con su imagen actual"
  docker start "$SERVICIO" >/dev/null || log "ALERTA: docker start fallo"
fi

# --- 2. la publicacion del 443 ---------------------------------------------------------------
# Sin esto, el servidor puede estar sano y ser inalcanzable igual, que es la mitad del incidente.
# SE BUSCA EL DESTINO, NO «que haya algun funnel». La primera version preguntaba si existia
# cualquier publicacion, y esta maquina tiene otra —el 10000 de otro proyecto—: con esa sola,
# habria dicho «ya esta publicado» y no habria restaurado el 443. Un chequeo que no puede decir
# que no es peor que ninguno. Y con la ruta absoluta, porque el PATH de systemd es minimo.
TS=/usr/bin/tailscale
[ -x "$TS" ] || TS="$(command -v tailscale || echo /usr/bin/tailscale)"
if "$TS" funnel status 2>/dev/null | grep -qF "proxy $PUERTO_CADDY"; then
  log "el 443 ya esta publicado"
else
  log "el 443 no esta publicado: restaurandolo hacia $PUERTO_CADDY"
  "$TS" funnel --bg --https=443 "$PUERTO_CADDY" >/dev/null 2>&1 \
    || log "ALERTA: no se pudo restaurar la publicacion del 443"
fi

# El servidor tarda unos cuatro minutos en indexar antes de contestar: en ese rato se ve
# «unhealthy» y NO esta roto. No se espera acá para no demorar el arranque; quien quiera
# comprobarlo de verdad corre `python3 tools/base_responde.py` desde kb-okos.
exit 0
