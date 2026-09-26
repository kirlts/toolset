#!/usr/bin/env bash
# desplegar-sin-caida.sh — recambia el contenedor kb-mcp por uno con codigo nuevo SIN
# cortar el servicio, para que la puerta del fundador (UD-004/D5 de kb-okos) no tenga
# ninguna caida: puede entrar en cualquier momento, no hay ventana de mantenimiento.
#
# QUE REEMPLAZA. Hasta el 2026-09-26, deploy.sh hacia esto en el lugar:
#   docker compose build kb-mcp && docker compose up -d kb-mcp
# que PARA el contenedor viejo, lo saca y recien arranca el nuevo. Medido con un
# contenedor de prueba (nunca el real): con cache de vectores fria, el nuevo tarda
# entre 60 y 71s en contestar su primera llamada MCP real — ese es el corte, ademas
# de lo que tarde `docker compose build`. Con la cache tibia baja a unos 9-13s (ver
# los comentarios de rendimiento en Dockerfile/docker-compose.yml), pero sigue siendo
# un corte real y no cero.
#
# COMO SE EVITA. Ni Caddyfile ni docker-compose.yml cambian: Caddy sigue apuntando a
# `kb-mcp:8765`, siempre. Lo que cambia es QUE CONTENEDOR responde a ese nombre en la
# red de Docker (`toolset_toolset-net`), aprovechando que esa red YA soporta que dos
# contenedores compartan el mismo alias (es el mismo mecanismo con que Compose reparte
# trafico entre replicas de un servicio escalado): se levanta el contenedor nuevo
# APARTE, con su propio nombre, se prueba con una llamada MCP real de verdad
# (`initialize` + `listar`) y SOLO SI CONTESTA se le agrega el alias `kb-mcp` — ahi
# los dos contestan ese nombre a la vez, asi que no hay ni un instante sin nadie
# respondiendo — y recien entonces se saca al viejo de la red y se lo baja.
#
# ENSAYADO el 2026-09-26 contra un par de contenedores de prueba con el mismo mecanismo
# (nunca el kb-mcp real), sondeando cada 0.2s durante el recambio: 0 fallas de 195
# sondeos. Un primer ensayo sin el freno de salud (linea de abajo, "si nunca contesta,
# se aborta SIN tocar al viejo") si mostro 21 fallas reales — quedo cazado y corregido
# antes de tocar produccion, exactamente lo que este freno existe para evitar.
#
# Nunca toca la config de red de docker-compose.yml: usa `docker network connect`/
# `disconnect` sobre contenedores concretos, que es independiente de que compose
# gestione el servicio "kb-mcp" declarado ahi. Al terminar, el contenedor activo
# vuelve a llamarse exactamente `kb-mcp` (el nombre que el resto de esta maquina --
# sync-kb.sh, comprobar-deriva.sh, el healthcheck de compose -- ya asume).
set -euo pipefail

REMOTE_DIR="${REMOTE_DIR:-/opt/toolset}"
RED="${KB_MCP_RED:-toolset_toolset-net}"
CONTENEDOR="${KB_MCP_CONTAINER:-kb-mcp}"
IMG_TAG="kb-mcp:1"
NUEVO="${CONTENEDOR}-next-$$"

log(){ echo "[kb-mcp-deploy] $*"; }

cd "$REMOTE_DIR"

log "construyendo la imagen nueva ($IMG_TAG)..."
docker compose build kb-mcp

if ! docker inspect "$CONTENEDOR" >/dev/null 2>&1; then
  log "no hay un $CONTENEDOR corriendo todavia: primer arranque, sin recambio posible."
  log "cae al camino normal de compose (esto es lo esperado solo la primera vez)."
  docker compose up -d kb-mcp
  exit $?
fi

# CLONAR LA CONFIG DEL CONTENEDOR VIEJO, no la del docker-compose.yml de este repo: el
# servidor real puede tener overrides puestos a mano en el .env (KB_MODELO_KB,
# KB_FECHA_SUBENTRADA) que docker-compose.yml solo declara como default. Clonar el
# contenedor VIVO es la unica forma de no perder un ajuste que ya esta en produccion
# y no en este archivo (mismo principio que "los nombres salen de la base viva").
# El healthcheck se lee de `docker compose config`, NO del contenedor vivo: si el
# contenedor vivo ya lo perdiera por lo que sea (paso exactamente el 2026-09-26, en el
# primer swap de este mecanismo, que todavia no clonaba el healthcheck), clonarlo DE ESE
# contenedor perpetuaria el hueco para siempre. `docker-compose.yml` es la fuente que se
# corrige a mano y de la que todo lo demas se supone que sale — asi que este paso se
# autorepara solo con que alguien arregle el compose, sin que nadie tenga que tocar un
# contenedor corriendo.
HEALTHCHECK_JSON=$(docker compose config --format json | python3 -c '
import json, sys
d = json.load(sys.stdin)
print(json.dumps((d.get("services") or {}).get("kb-mcp", {}).get("healthcheck") or {}))
')

RUN_ARGS_FILE=$(mktemp)
docker inspect "$CONTENEDOR" --format '{{json .}}' | HEALTHCHECK_JSON="$HEALTHCHECK_JSON" python3 -c '
import json, sys, shlex, os
c = json.load(sys.stdin)
args = []
for e in c["Config"]["Env"]:
    args += ["-e", e]
for m in c["Mounts"]:
    ro = "ro" if not m.get("RW", True) else "rw"
    origen, destino = m["Source"], m["Destination"]
    args += ["-v", "{}:{}:{}".format(origen, destino, ro)]
hc = c["HostConfig"]
if hc.get("Memory"):
    args += ["--memory", str(hc["Memory"])]
if hc.get("ReadonlyRootfs"):
    args += ["--read-only"]
for k, v in (hc.get("Tmpfs") or {}).items():
    args += ["--tmpfs", f"{k}:{v}"]
for s in (hc.get("SecurityOpt") or []):
    args += ["--security-opt", s]
# EL HEALTHCHECK SE TOMA DE `docker compose config` (HEALTHCHECK_JSON), NO del
# contenedor vivo — ver el comentario mas arriba de por que. Formato de compose:
# test=["CMD",...], y timeout/interval/start_period ya vienen como "5s"/"30s" (listos
# para pasarlos directo a `docker run`, sin convertir nanosegundos).
hcheck = json.loads(os.environ.get("HEALTHCHECK_JSON") or "{}")
test = hcheck.get("test") or []
if test and test[0] not in ("NONE",):
    if test[0] == "CMD-SHELL":
        cmd = test[1] if len(test) > 1 else ""
    else:
        # --health-cmd de `docker run` siempre corre por shell (no hay forma exec-array),
        # asi que el resto del Test se re-arma como una linea de shell bien citada.
        cmd = " ".join(shlex.quote(p) for p in test[1:])
    if cmd:
        args += ["--health-cmd", cmd]
        if hcheck.get("interval"):
            args += ["--health-interval", hcheck["interval"]]
        if hcheck.get("timeout"):
            args += ["--health-timeout", hcheck["timeout"]]
        if hcheck.get("start_period"):
            args += ["--health-start-period", hcheck["start_period"]]
        if hcheck.get("retries"):
            args += ["--health-retries", str(hcheck["retries"])]
print(" ".join(shlex.quote(a) for a in args))
' > "$RUN_ARGS_FILE"
RUN_ARGS=$(cat "$RUN_ARGS_FILE")
rm -f "$RUN_ARGS_FILE"

log "levantando $NUEVO al lado de $CONTENEDOR, con la config clonada y la imagen nueva..."
docker rm -f "$NUEVO" >/dev/null 2>&1 || true
# shellcheck disable=SC2086
eval docker run -d --name "$NUEVO" --network "$RED" $RUN_ARGS "$IMG_TAG" >/dev/null

log "esperando que $NUEVO conteste una llamada MCP real (initialize + listar), hasta 300s..."
listo=0
for i in $(seq 1 100); do
  R=$(docker exec "$NUEVO" python3 -c '
import urllib.request, json, sys

def rpc(metodo, params, sid=None):
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream"}
    if sid:
        headers["Mcp-Session-Id"] = sid
    req = urllib.request.Request("http://127.0.0.1:8765/okos/mcp", method="POST",
                                  headers=headers,
                                  data=json.dumps({"jsonrpc": "2.0", "id": 1,
                                                    "method": metodo, "params": params}).encode())
    r = urllib.request.urlopen(req, timeout=5)
    sid_out = r.headers.get("Mcp-Session-Id")
    body = r.read().decode()
    for line in body.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:]), sid_out
    return None, sid_out

try:
    ini, sid = rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                   "clientInfo": {"name": "desplegar-sin-caida", "version": "1"}})
    if not ini or "result" not in ini:
        print("NO_INIT"); sys.exit(0)
    lis, _ = rpc("tools/call", {"name": "listar", "arguments": {"tipo": "plan"}}, sid)
    if lis and "result" in lis:
        print("OK")
    else:
        print("NO_LISTAR:" + json.dumps(lis)[:150])
except Exception as e:
    print("ERR:" + str(e)[:150])
' 2>/dev/null || echo "EXC")
  log "  intento $i/100: $R"
  if [ "$R" = "OK" ]; then listo=1; break; fi
  sleep 3
done

if [ "$listo" != "1" ]; then
  log "❌ $NUEVO nunca contesto una llamada MCP real. Se aborta SIN tocar $CONTENEDOR — el"
  log "   viejo sigue sirviendo, cero corte. Ultimas lineas de su log:"
  docker logs --tail 40 "$NUEVO" 2>&1 | sed 's/^/    /' || true
  docker rm -f "$NUEVO" >/dev/null 2>&1 || true
  exit 1
fi

log "$NUEVO esta sano. Agregandole el alias '$CONTENEDOR' (ahora los dos lo responden)..."
docker network disconnect "$RED" "$NUEVO"
docker network connect --alias "$NUEVO" --alias "$CONTENEDOR" "$RED" "$NUEVO"

sleep 3  # deja que cualquier resolucion en curso vea a los dos antes de sacar al viejo

log "sacando a $CONTENEDOR (el viejo) de la red — $NUEVO ya responde solo con ese nombre..."
VIEJO_ID=$(docker ps -q --filter "name=^/${CONTENEDOR}$" | grep -vx "$(docker inspect -f '{{.Id}}' "$NUEVO" | cut -c1-12)" || true)
if [ -z "$VIEJO_ID" ]; then
  # el filtro por nombre exacto puede devolver el ID largo del nuevo si docker aliaso
  # el nombre visible; se recalcula comparando IDs completos para no bajar el nuevo.
  NUEVO_ID_LARGO=$(docker inspect -f '{{.Id}}' "$NUEVO")
  VIEJO_ID=$(docker ps -q --filter "name=^/${CONTENEDOR}$" | while read -r id; do
    [ "$(docker inspect -f '{{.Id}}' "$id")" != "$NUEVO_ID_LARGO" ] && echo "$id"
  done)
fi
if [ -n "$VIEJO_ID" ]; then
  docker network disconnect "$RED" "$VIEJO_ID" 2>/dev/null || true
  docker stop "$VIEJO_ID" >/dev/null 2>&1 || true
  docker rm -f "$VIEJO_ID" >/dev/null 2>&1 || true
  log "  contenedor viejo ($VIEJO_ID) bajado."
else
  log "  no encontre un contenedor viejo distinto de $NUEVO (no deberia pasar; reviso a mano)."
fi

log "renombrando $NUEVO -> $CONTENEDOR..."
docker rename "$NUEVO" "$CONTENEDOR"

log "listo: $CONTENEDOR es ahora el codigo nuevo, servido sin corte."
docker exec "$CONTENEDOR" python3 -c 'import urllib.request;print(urllib.request.urlopen("http://127.0.0.1:8765/salud",timeout=4).read().decode())' 2>/dev/null || true
