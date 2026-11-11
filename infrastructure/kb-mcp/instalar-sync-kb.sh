#!/usr/bin/env bash
# instalar-sync-kb.sh — instala en el servidor la sincronización de las KB.
#
#   SSH_HOST=usuario@servidor bash infrastructure/kb-mcp/instalar-sync-kb.sh
#
# Instala, desde este repositorio:
#   /usr/local/sbin/sync-kb.sh      sincroniza /opt/kb y reindexa si cambió algún HEAD
#   /usr/local/sbin/kb-sync-ahora   lo dispara el gancho pre-push de la KB (regla de sudo acotada)
#   cron de opc, cada minuto        red para cuando el aviso al publicar no llega
#   /var/log/kb-sync.log            registro del cron y del aviso, con rotación semanal
#
# Hasta el 2026-11-11 el guion vivía en /home/opc/.hermes/scripts/. Retirar ese directorio
# (2026-11-11 00:48 UTC) borró el guion y el cron, y /opt/kb dejó de actualizarse. Por eso
# ahora vive en /usr/local/sbin, junto a los demás guardias del servidor (vps-guardias/).
#
# El cron escribe a un registro y no a /dev/null: un sync que falla deja la KB congelada en
# silencio, con el servicio respondiendo sano. El reloj es cada minuto porque el camino normal
# es el aviso al publicar; sin cambios el guion compara el HEAD y sale.
#
# `mv` y no `cp`: bash lee el guion por tramos, y sobrescribir en el sitio una corrida viva
# hace que ejecute basura. Con un renombre la corrida en curso conserva su archivo entero.
set -euo pipefail
SSH_HOST="${SSH_HOST:?SSH_HOST=usuario@servidor}"
AQUI="$(cd "$(dirname "$0")" && pwd)"
SSH_O=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

scp -q "${SSH_O[@]}" "$AQUI/sync-kb.sh" "$AQUI/kb-sync-ahora" "${SSH_HOST}:/tmp/"
ssh "${SSH_O[@]}" "${SSH_HOST}" 'set -e
  sudo install -m 755 -o root -g root /tmp/sync-kb.sh /usr/local/sbin/sync-kb.sh.nuevo
  sudo mv -f /usr/local/sbin/sync-kb.sh.nuevo /usr/local/sbin/sync-kb.sh
  sudo install -m 755 -o root -g root /tmp/kb-sync-ahora /usr/local/sbin/kb-sync-ahora.nuevo
  sudo mv -f /usr/local/sbin/kb-sync-ahora.nuevo /usr/local/sbin/kb-sync-ahora
  rm -f /tmp/sync-kb.sh /tmp/kb-sync-ahora
  sudo touch /var/log/kb-sync.log && sudo chown opc:opc /var/log/kb-sync.log
  printf "/var/log/kb-sync.log {\n  weekly\n  rotate 4\n  compress\n  missingok\n  notifempty\n}\n" \
    | sudo tee /etc/logrotate.d/kb-sync > /dev/null
  LINEA="* * * * * bash /usr/local/sbin/sync-kb.sh >> /var/log/kb-sync.log 2>&1"
  ACTUAL=$(sudo -u opc crontab -l 2>/dev/null || true)
  if printf "%s\n" "$ACTUAL" | grep -qxF "$LINEA"; then
    echo "cron ya instalado"
  else
    { printf "%s\n" "$ACTUAL" | grep -v "sync-kb.sh" || true; echo "$LINEA"; } | sudo -u opc crontab -
    echo "cron instalado"
  fi
  echo "sync-kb.sh instalado"'
