#!/usr/bin/env bash
# Instala en el servidor la ejecucion de las sondas de latido de OKOS (ver sonda-okos.sh).
# Idempotente. Se corre en el servidor, desde esta carpeta, como kirlts (usa sudo solo para
# /usr/local/sbin):  bash instalar-sonda-okos.sh
# Requisitos: los temporizadores okos-probe-founder-gateway y okos-probe-engine-health ya existen
# (los crean scripts/install-probe-*.sh de conversio-connect); aqui solo se les cambia el ExecStart
# con un drop-in, de modo que reinstalarlos no deshace esto.
set -euo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNITS="${HOME}/.config/systemd/user"

sudo install -m 755 "${AQUI}/sonda-okos.sh" /usr/local/sbin/sonda-okos.sh
for par in founder:okos-probe-founder-gateway engine:okos-probe-engine-health; do
  sonda="${par%%:*}"; unidad="${par#*:}"
  [ -f "${UNITS}/${unidad}.service" ] || { echo "falta ${UNITS}/${unidad}.service"; exit 1; }
  mkdir -p "${UNITS}/${unidad}.service.d"
  install -m 644 "${AQUI}/sonda-okos-${sonda}.conf" "${UNITS}/${unidad}.service.d/servidor.conf"
done
systemctl --user daemon-reload
echo "instalado: sonda-okos.sh y los drop-ins de las dos sondas"
