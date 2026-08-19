#!/usr/bin/env bash
# comprobar-deriva.sh — el motor del buscador vive en DOS sitios y se separó sin que nadie lo notara.
#
# El contenido de cada base se sincroniza al publicar (el gancho pre-push de la KB llama a
# kb-sync-ahora; el cron de cada minuto queda como red), pero el CÓDIGO del
# servidor viaja dentro de la imagen Docker, que se construye desde esta carpeta. El 2026-07-30 se
# descubrió que la copia de acá estaba dos días atrás de la del repositorio de la base: le faltaban
# 419 líneas, entre ellas los dos arreglos que más habían mejorado la precisión. Es decir: se
# trabajó una jornada sobre un motor que no era el que servía.
#
# Esto no es una recomendación: devuelve 1 si difieren, para que un despliegue pueda detenerse.
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)/server.py"
CANON="${KB_SERVER_CANONICO:-$HOME/kb-okos/tools/kb-mcp/server.py}"

if [ ! -f "$CANON" ]; then
  echo "comprobar-deriva: no encuentro el original en $CANON — no puedo comparar." >&2
  exit 2
fi
if diff -q "$AQUI" "$CANON" >/dev/null; then
  echo "comprobar-deriva: al día (idéntico a $CANON)"
  exit 0
fi
echo "comprobar-deriva: ⚠ DERIVA — la copia que se despliega NO es la del repositorio de la base." >&2
echo "  acá:  $AQUI  ($(wc -l < "$AQUI") líneas)" >&2
echo "  base: $CANON ($(wc -l < "$CANON") líneas)" >&2
echo "  diferencias: $(diff "$AQUI" "$CANON" | grep -c '^[<>]') líneas" >&2
echo "  remedio: cp \"$CANON\" \"$AQUI\" y volver a construir la imagen." >&2
exit 1
