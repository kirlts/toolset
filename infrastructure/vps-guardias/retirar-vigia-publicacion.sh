#!/usr/bin/env bash
# Retira del servidor el temporizador del vigia de publicacion de OKOS. Idempotente.
# Se corre en el servidor, como kirlts:  bash retirar-vigia-publicacion.sh
#
# POR QUE SOBRA AQUI (conversio-connect docs/PUBLICACION.md; kb-okos «Pasar a producción depende
# del notebook», 2026-11-03):
#   - Por diseno el vigia corre a pedido en la maquina del operador (`npm run publicar`); el
#     temporizador es opcional (`install-publication-watchdog.sh --timer`) y Martin objeto a los
#     residentes el 2026-10-06. En el notebook esta desactivado.
#   - La orden del boton «Pasar a producción» la ejecuta el notebook, que tiene las llaves que el
#     vigia necesita (API de gestion de Supabase, despliegue de Fly, proyecto de Vercel, acceso git
#     de escritura). El servidor no las tiene y no debe tenerlas: ~/.claude se retiro de el.
#   - Desde el 2026-11-04 la unidad fallaba cada 10 minutos con «missing ~/.claude/vercel-ro-token»
#     (288 fallos por dia) y nadie lo veia.
# El resto de las unidades okos-* del servidor (sondas de latido, cola de fusion) no se tocan.
set -euo pipefail
systemctl --user disable --now okos-publication-watchdog.timer 2>/dev/null || true
systemctl --user stop okos-publication-watchdog.service 2>/dev/null || true
systemctl --user reset-failed okos-publication-watchdog.service 2>/dev/null || true
if systemctl --user is-enabled okos-publication-watchdog.timer >/dev/null 2>&1; then
  echo "el temporizador sigue habilitado"; exit 1
fi
echo "vigia de publicacion: temporizador retirado, unidad sin fallos"
