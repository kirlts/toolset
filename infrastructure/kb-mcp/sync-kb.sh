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

  # UNA CAPACIDAD APAGADA NO SE QUEJA SOLA, asi que se le pregunta cada vez. Criterio de Martin,
  # 2026-08-09: «esto no puede depender de que yo me acuerde de que existen estos componentes».
  # Cada mejora del buscador se enciende con una variable de entorno —a proposito: corren en el
  # camino de servir y cada una se encendio con su numero medido— pero un despliegue que no
  # arrastre una de esas variables deja el buscador PEOR respondiendo exactamente igual de sano.
  # Esto corre cada quince minutos sin que nadie lo pida, que es la unica forma de que se note.
  apagadas() {
    printf '%s' "${1:-}" | python3 -c 'import json,sys
try: c = json.load(sys.stdin).get("capacidades") or {}
except Exception: sys.exit(0)
esperadas = {"recencia_por_subentrada": True, "fecha_por_subentrada": True}
print(" ".join(k for k, v in esperadas.items() if c and c.get(k) != v))' 2>/dev/null || true
  }

  if [ -n "$gen_ahora" ] && [ "$gen_ahora" != "$gen_antes" ]; then
    off=$(apagadas "$salud")
    [ -n "$off" ] && log "ALERTA: el buscador corre con capacidades APAGADAS ($off). Se midio que sirven; alguien las perdio en un despliegue."
    log "$CONTAINER recargado EN CALIENTE, sin cortar el servicio (generacion $gen_antes -> $gen_ahora): $salud"
  elif printf '%s' "$salud" | grep -q '"error_ultima_recarga": "'; then
    log "ALERTA: la recarga de $CONTAINER FALLO y sigue sirviendo la generacion $gen_antes. El contenido nuevo NO esta indexado: $salud"
  elif [ -z "$salud" ]; then
    # NO CONTESTAR NO ES «IMAGEN VIEJA», y confundirlos hizo daño el 2026-08-09 a las 02:17. La
    # rama de abajo existe para una imagen anterior a la recarga en caliente, que SI contesta pero
    # sin declarar su generacion. Cuando /salud no contesta NADA la causa es otra —el contenedor
    # esta arrancando, o alguien lo esta reemplazando— y reiniciarlo ahi es pelearse con quien
    # este trabajando: eso fue exactamente lo que paso, un despliegue en curso y este guion
    # reiniciando encima, dejando el servicio caido y una ALERTA que culpaba a la imagen.
    #
    # Un arranque legitimo tarda hasta ~160 s con el codificador y el cache frio. No se hace nada:
    # se dice, y el proximo ciclo —quince minutos— lo encuentra resuelto o lo vuelve a decir.
    log "ALERTA: $CONTAINER no responde /kb/salud. NO se reinicia: puede estar arrancando o en reemplazo. Se reintenta en el proximo ciclo."
  else
    # CONTESTA pero sin declarar generacion: imagen anterior a la recarga en caliente. Ahi si.
    log "$CONTAINER contesta pero no publica generacion (imagen vieja); se reinicia como antes"
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
