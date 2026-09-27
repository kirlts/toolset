#!/usr/bin/env bash
# aplicar-recursos-caddy.sh — aplica los límites de cgroup (cpuset, cpu_shares, memoria)
# que docker-compose.yml declara para el servicio "caddy" a un contenedor YA CORRIENDO,
# sin recrearlo. Corre EN EL VPS (deploy.sh lo invoca por ssh).
#
# POR QUÉ EXISTE. `deploy.sh` excluye a "caddy" del paso genérico `docker compose up -d`
# (igual que ya excluía a "kb-mcp", ver el comentario de "Recreate changed services" en
# deploy.sh) porque ESE paso, al ver que la config resuelta de un servicio cambió,
# recrea el contenedor EN EL LUGAR: lo para, lo saca y levanta uno nuevo. Para kb-mcp
# eso ya estaba resuelto con un recambio sin corte propio (desplegar-sin-caida.sh); para
# Caddy no había ningún camino — porque hasta el 2026-09-27 su compose nunca había
# cambiado un valor de cgroup — así que agregarle `cpuset` disparó la recreación
# genérica y la puerta pública del fundador (UD-004/D5 de kb-okos) quedó sin contestar
# mientras el contenedor arrancaba de cero (medido: "serving initial configuration" en
# su log, con la sonda pública devolviendo 000 justo antes).
#
# CÓMO EVITA EL CORTE. `docker update` cambia cpuset/cpu-shares/memoria de un contenedor
# VIVO sin tocar su proceso ni soltar una sola conexión en vuelo (confirmado con
# `docker inspect` antes/después en contenedores de ensayo y en este mismo VPS, nunca
# contra caddy real hasta este script). Si Caddy no existe todavía (primer arranque de
# la máquina), no hay nada que actualizar en caliente: se lo crea con `compose up`, que
# ahí sí es seguro porque no hay conexión previa que cortar.
set -euo pipefail
cd "${REMOTE_DIR:-/opt/toolset}"

if ! sudo docker ps --format '{{.Names}}' | grep -qx caddy; then
  echo "[aplicar-recursos-caddy] caddy no existe todavia: lo crea 'compose up' (sin conexiones que cortar)."
  sudo docker compose up -d caddy
  exit 0
fi

# Se lee de `docker compose config` (la fuente que un humano corrige a mano), nunca del
# contenedor vivo -- mismo principio que ya usa desplegar-sin-caida.sh para kb-mcp: así
# un valor que se retire del compose se retira también del contenedor en la próxima
# pasada, en vez de quedar pegado para siempre.
LECTURA=$(sudo docker compose config --format json | python3 -c '
import json, sys
d = json.load(sys.stdin)
s = (d.get("services") or {}).get("caddy") or {}
print(s.get("cpuset") or "")
print(s.get("cpu_shares") or "")
print(s.get("mem_limit") or "")
')
CPUSET=$(echo "$LECTURA" | sed -n 1p)
SHARES=$(echo "$LECTURA" | sed -n 2p)
MEM=$(echo "$LECTURA" | sed -n 3p)

ARGS=()
[ -n "$CPUSET" ] && ARGS+=(--cpuset-cpus="$CPUSET")
[ -n "$SHARES" ] && ARGS+=(--cpu-shares="$SHARES")
[ -n "$MEM" ] && ARGS+=(--memory="$MEM")

if [ "${#ARGS[@]}" -eq 0 ]; then
  echo "[aplicar-recursos-caddy] docker-compose.yml no declara cpuset/cpu_shares/mem_limit para caddy; nada que aplicar en vivo."
  exit 0
fi

echo "[aplicar-recursos-caddy] aplicando en vivo: ${ARGS[*]}"
sudo docker update "${ARGS[@]}" caddy
echo "[aplicar-recursos-caddy] listo, sin recrear el contenedor."
