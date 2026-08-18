#!/usr/bin/env bash
# Censo de nodos de CI en la tailnet. Deja el resultado en el registro del sistema.
#
# POR QUE (2026-08-18): el CI dejaba un nodo por corrida y nunca lo borraba; en 54 dias
# acumulo 763 y eso inflo a tailscaled hasta 2.2 GB. Se limpiaron y se reemitio la auth
# key marcada Ephemeral + Reusable, que es lo que hace que cada nodo se borre solo.
#
# LO QUE ESTE CENSO NO PUEDE DECIR, y por eso no lo dice:
#   "0 nodos de CI" NO prueba que la llave sea efimera. Significa lo mismo si la llave
#   funciona que si el CI no corrio desde ayer. Un instrumento que da por buena una
#   cosa cuando en realidad no midio nada es peor que no tenerlo, asi que aca se
#   informa el numero y se nombra la ambiguedad. La unica prueba es mirar DESPUES de
#   una corrida: si el deploy corrio y no quedo ningun nodo, la llave es efimera.
#   El numero que si es concluyente es el que SUBE: eso prueba que no lo es.
#
# Se cuentan solo las lineas que son un nodo (empiezan con IP 100.x). Contar todas
# metia el bloque "# Funnel on:" y las vacias, y reportaba 11 maquinas donde hay 5.
# Los 'funnel-ingress-node' no cuentan: son relays de la propia Tailscale.
set -uo pipefail
PAT='actions-runner|gh-deploy|gh-actions-traza|ghdeploy'
REALES=$(tailscale status 2>/dev/null | grep -E '^100\.' | grep -vcE 'funnel-ingress-node')
CI=$(tailscale status 2>/dev/null | grep -E '^100\.' | grep -cE "$PAT")
if [ "${CI:-0}" -gt 5 ]; then
  logger -t censar-tailnet "ATENCION: ${CI} nodos de CI acumulados (${REALES} maquinas reales). CONCLUYENTE: la auth key no es efimera. Reemitirla marcando Ephemeral ADEMAS de Reusable."
else
  logger -t censar-tailnet "${CI} nodos de CI, ${REALES} maquinas reales. NO concluyente por si solo: cero significa lo mismo si la llave es efimera que si el CI no corrio. Se confirma mirando despues de un deploy."
fi
