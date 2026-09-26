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
# vivo.py se sumó el 2026-09-25 (server.py hace `from vivo import esta_retirado`): un archivo del
# que el servidor depende para arrancar, y que hasta entonces esta comprobación no miraba. Se
# compara junto con server.py, con el mismo criterio.
#
# Esto no es una recomendación: devuelve 1 si CUALQUIERA de los dos difiere, para que un
# despliegue pueda detenerse.
set -euo pipefail
AQUI_DIR="$(cd "$(dirname "$0")" && pwd)"
CANON_DIR="${KB_SERVER_CANONICO_DIR:-$HOME/kb-okos/tools}"

deriva=0
for nombre_par in "server.py:kb-mcp/server.py" "vivo.py:vivo.py"; do
  aqui_nombre="${nombre_par%%:*}"
  canon_rel="${nombre_par#*:}"
  aqui="$AQUI_DIR/$aqui_nombre"
  canon="$CANON_DIR/$canon_rel"

  if [ ! -f "$canon" ]; then
    echo "comprobar-deriva: no encuentro el original en $canon — no puedo comparar $aqui_nombre." >&2
    deriva=2
    continue
  fi
  if diff -q "$aqui" "$canon" >/dev/null; then
    echo "comprobar-deriva: $aqui_nombre al día (idéntico a $canon)"
    continue
  fi
  echo "comprobar-deriva: ⚠ DERIVA en $aqui_nombre — la copia que se despliega NO es la del repositorio de la base." >&2
  echo "  acá:  $aqui  ($(wc -l < "$aqui") líneas)" >&2
  echo "  base: $canon ($(wc -l < "$canon") líneas)" >&2
  echo "  diferencias: $(diff "$aqui" "$canon" | grep -c '^[<>]') líneas" >&2
  echo "  remedio: cp \"$canon\" \"$aqui\" y volver a construir la imagen." >&2
  deriva=1
done

exit "$deriva"
