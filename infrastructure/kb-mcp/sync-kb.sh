#!/usr/bin/env bash
# sync-kb.sh — actualiza los clones de las KB en /opt/kb y reindexa si alguno cambio.
# Desplegado por deploy.sh a /home/opc/.hermes/scripts/. Lo dispara el gancho
# pre-push de la KB al publicar; el cron cada minuto queda como red.
# Acotado a proposito: solo toca /opt/kb y el contenedor kb-mcp. Nunca otros.
set -euo pipefail

# ── UNA CORRIDA A LA VEZ ──────────────────────────────────────────────────────
# El cron pasó de cada 15 minutos a cada minuto el 2026-08-19, para que lo que
# se captura en la base llegue al conector —y a quien lo consulta desde afuera—
# en cerca de un minuto en vez de en un cuarto de hora. Medido: una corrida sin
# cambios cuesta 3,4 s, así que el intervalo corto es barato; pero una CON
# cambios tarda unos 60 s, o sea exactamente el intervalo, y sin este candado
# dos corridas se solaparían: la segunda haría `reset --hard` sobre el clon
# mientras la primera lo está indexando, y mandaría un segundo SIGHUP sobre una
# recarga en curso. `flock -n` hace que la que llega tarde se retire.
#
# PERO NO SE RETIRA EN SILENCIO, y esa es la corrección del 2026-08-19. Desde que
# existe el aviso al publicar (`kb-sync-ahora`, llamado por el gancho pre-push de
# la KB), retirarse en silencio SÍ pierde algo: si se publica dos veces seguidas,
# el segundo aviso choca con el rearmado del primero y el cambio nuevo queda
# esperando al reloj. Se vio: el servidor sirviendo e5ccb681 con 9d8effd ya
# publicado. Con el reloj cada quince minutos eso era invisible; con un aviso que
# promete ser instantáneo, es la diferencia entre serlo y no serlo.
#
# Así que el que llega tarde deja una MARCA, y el que está corriendo la mira antes
# de irse y vuelve a pasar. El reintento está acotado para que no pueda quedar
# dando vueltas si alguien publica sin parar.
PENDIENTE=/tmp/sync-kb.pendiente
exec 9>/tmp/sync-kb.lock
if ! flock -n 9; then
  : > "$PENDIENTE" 2>/dev/null || true
  exit 0
fi
rm -f "$PENDIENTE" 2>/dev/null || true

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

# UNA CAPACIDAD APAGADA NO SE QUEJA SOLA, asi que se le pregunta cada vez. Criterio de Martin,
# 2026-08-09: «esto no puede depender de que yo me acuerde de que existen estos componentes».
# Cada mejora del buscador se enciende con una variable de entorno —a proposito: corren en el
# camino de servir y cada una se encendio con su numero medido— pero un despliegue que no
# arrastre una de esas variables deja el buscador PEOR respondiendo exactamente igual de sano.
# Esto corre en cada sync sin que nadie lo pida, que es la unica forma de que se note.
apagadas() {
  printf '%s' "${1:-}" | python3 -c 'import json,sys
try: c = json.load(sys.stdin).get("capacidades") or {}
except Exception: sys.exit(0)
esperadas = {"recencia_por_subentrada": True, "fecha_por_subentrada": True}
print(" ".join(k for k, v in esperadas.items() if c and c.get(k) != v))' 2>/dev/null || true
}

if [ "$cambio" -eq 1 ]; then
  # ── RECAMBIO DE CONTENEDOR, no SIGHUP ───────────────────────────────────────────────
  # Hasta el 2026-08-08 un cambio de contenido hacia `docker restart` y la base NO CONTESTABA
  # A NADIE mientras levantaba. Desde esa fecha y hasta el 2026-09-26 se le mandaba SIGHUP: el
  # servidor armaba el indice nuevo EN UN HILO del MISMO proceso que atiende HTTP, mientras
  # seguia sirviendo con el viejo. Eso midio "0 peticiones fallidas de 150" con el modelo
  # estatico liviano — pero el 2026-09-26, sondeando la puerta del fundador cada 1s durante una
  # recarga real con el modelo semantico pesado que corre hoy en produccion
  # (sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2), la recarga tardo 212s y,
  # cerca del final —el paso mas caro del ranking semantico—, 7 llamadas `initialize` SEGUIDAS
  # fallaron por timeout, recuperandose al instante cuando la recarga termino. Causa: el hilo
  # que arma el indice compite por GIL/CPU con el hilo que atiende HTTP, y el VPS tiene solo 2
  # nucleos — `os.nice(10)` adentro del proceso no alcanza a proteger al que sirve cuando los
  # dos comparten el mismo interprete.
  #
  # Ahora el contenido nuevo se sirve exactamente como un cambio de CODIGO: un contenedor
  # aparte arma su indice completo — sin compartir proceso, ni GIL, con el que esta sirviendo —
  # y solo si contesta una llamada MCP real (`initialize`+`listar`) se lo swapea al alias de red
  # compartido; si nunca contesta sano, el viejo no se toca. Es el mismo
  # desplegar-sin-caida.sh que ya prueba cada despliegue de codigo (0 fallas en 869 sondeos
  # contra un par de contenedores de prueba, y confirmado sin corte en produccion real): se
  # reusa tal cual, en vez de mantener un segundo mecanismo de recarga. Su propio candado
  # (`/tmp/kb-mcp-swap.lock`) evita que este camino se pise con un despliegue de codigo
  # concurrente.
  antes_salud=$(salud_de)
  SWAP_SALIO=0
  SWAP_LOG=$(sudo REMOTE_DIR=/opt/toolset bash /opt/toolset/kb-mcp/desplegar-sin-caida.sh 2>&1) || SWAP_SALIO=$?
  printf '%s\n' "$SWAP_LOG" | sed 's/^/[kb-sync] /'
  salud=$(salud_de)

  if [ "$SWAP_SALIO" -eq 0 ] && [ -n "$salud" ]; then
    off=$(apagadas "$salud")
    [ -n "$off" ] && log "ALERTA: el buscador corre con capacidades APAGADAS ($off). Se midio que sirven; alguien las perdio en un despliegue."
    log "$CONTAINER recargado SIN CORTAR el servicio (recambio de contenedor por contenido nuevo): $salud"
  elif [ "$SWAP_SALIO" -ne 0 ]; then
    # desplegar-sin-caida.sh nunca toca al viejo si el nuevo no contesta sano (ver su propio
    # freno de salud): que esto falle significa que el contenido nuevo NO quedo indexado, y el
    # contenedor de antes sigue sirviendo el contenido de ANTES, sin corte.
    log "ALERTA: el recambio de $CONTAINER por contenido nuevo FALLO (codigo $SWAP_SALIO). El contenido nuevo NO quedo servido; el contenedor sigue con el de antes: $antes_salud"
  else
    log "ALERTA: $CONTAINER no responde /kb/salud tras el recambio (aunque el guion de recambio salio en 0)."
  fi
else
  log "sin cambios en ninguna KB"
fi

# ── ¿ALGUIEN PUBLICÓ MIENTRAS ESTO CORRÍA? ───────────────────────────────────
# Si la marca está, hubo un aviso que llegó y se topó con esta corrida. Volver a
# pasar AHORA es lo que sostiene la promesa de que publicar actualiza el conector
# en el acto; esperar al reloj la rompe justo cuando se publica seguido.
# El tope de tres evita que publicaciones encadenadas dejen esto girando.
if [ -e "$PENDIENTE" ]; then
  rm -f "$PENDIENTE" 2>/dev/null || true
  N="${SYNC_KB_REINTENTO:-0}"
  if [ "$N" -lt 3 ]; then
    log "hubo una publicacion mientras esto corria; se vuelve a pasar en el acto (reintento $((N+1)))"
    flock -u 9 2>/dev/null || true
    exec 9>&-
    exec env SYNC_KB_REINTENTO=$((N+1)) /bin/bash "$0"
  fi
  log "hubo una publicacion mientras esto corria, pero ya van $N reintentos: lo toma el reloj"
fi
