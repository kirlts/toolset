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

# Consulta /salud desde adentro del contenedor (no trae curl; se usa su propio python).
# La ruta interna es /salud: el /kb se lo antepone el proxy.
salud_de() {
  sudo docker exec "$CONTAINER" python3 -c 'import urllib.request;print(urllib.request.urlopen("http://127.0.0.1:8765/salud",timeout=4).read().decode())' 2>/dev/null || true
}
# La generacion del indice. Sube de a uno cada vez que el servidor lo reconstruye.
# Un servidor viejo no la publica y esto devuelve vacio, que es como se detecta.
generacion_de() {
  printf '%s' "${1:-}" | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("generacion",""))
except Exception: print("")' 2>/dev/null || true
}

if [ "$cambio" -eq 1 ]; then
  # ── RECARGA EN CALIENTE, no reinicio ────────────────────────────────────────────────
  # Hasta el 2026-08-08 esto hacia `docker restart` y la base NO CONTESTABA A NADIE mientras
  # levantaba: ~9 s con el modelo estatico y ~49 s con un codificador. Por 28 cambios de
  # contenido en un dia son entre 4 y 23 minutos diarios de servicio caido, en tandas, mientras
  # alguien pregunta. Era ademas lo que volvia indesplegable al codificador.
  #
  # Ahora se le manda SIGHUP: el servidor construye el indice nuevo EN UN HILO mientras sigue
  # atendiendo con el viejo, y solo cuando el nuevo esta entero cambia el puntero. Medido con el
  # servidor bajo carga, tres recargas seguidas: 0 peticiones fallidas de 150.
  #
  # QUE TENDRIA QUE PASAR PARA QUE ESTO DIJERA QUE NO. Tres cosas, y las tres se distinguen:
  #   · el contenido nuevo no se puede indexar  -> la generacion NO sube y /salud trae
  #     `error_ultima_recarga`. Se dice ALERTA con el error, y la base sigue sirviendo lo viejo.
  #   · la imagen es vieja y no sabe de SIGHUP  -> la generacion no sube Y no hay error. Ahi se
  #     cae al reinicio de antes, que es correcto para esa imagen, y se dice en el log.
  #   · el contenedor no responde                -> ALERTA, igual que antes.
  antes_salud=$(salud_de)
  gen_antes=$(generacion_de "$antes_salud")

  sudo docker kill -s HUP "$CONTAINER" >/dev/null 2>&1 || true

  salud=""; gen_ahora=""
  for _ in $(seq 1 24); do   # hasta 120 s: en el VPS reconstruir cuesta ~12 s con cache
    sleep 5
    salud=$(salud_de)
    gen_ahora=$(generacion_de "$salud")
    case "$salud" in *'"recargando": true'*) continue ;; esac
    [ -n "$gen_ahora" ] && [ "$gen_ahora" != "$gen_antes" ] && break
    case "$salud" in *'"error_ultima_recarga": "'*) break ;; esac
  done

  if [ -n "$gen_ahora" ] && [ "$gen_ahora" != "$gen_antes" ]; then
    log "$CONTAINER recargado EN CALIENTE, sin cortar el servicio (generacion $gen_antes -> $gen_ahora): $salud"
  elif printf '%s' "$salud" | grep -q '"error_ultima_recarga": "'; then
    log "ALERTA: la recarga de $CONTAINER FALLO y sigue sirviendo la generacion $gen_antes. El contenido nuevo NO esta indexado: $salud"
  else
    # Sin generacion en /salud: imagen anterior a la recarga en caliente. Se reinicia como antes.
    log "$CONTAINER no publica generacion (imagen vieja); se reinicia como antes"
    sudo docker restart "$CONTAINER" >/dev/null
    for _ in $(seq 1 12); do
      salud=$(salud_de)
      [ -n "$salud" ] && break
      sleep 5
    done
    if [ -n "$salud" ]; then
      log "$CONTAINER reindexado y verificado: $salud"
    else
      log "ALERTA: $CONTAINER no respondio /kb/salud tras el reinicio"
    fi
  fi
else
  log "sin cambios en ninguna KB"
fi
