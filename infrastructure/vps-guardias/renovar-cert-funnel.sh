#!/usr/bin/env bash
# Renueva el certificado de Tailscale que usa Caddy para terminar la TLS del Funnel en :8091.
#
# POR QUE EXISTE (2026-09-27). El 443 publico dejo de pasar por el terminador TLS de tailscaled
# (bug conocido, tailscale/tailscale#18916: ~220ms de pausa por Nagle+ACK retrasado, dos veces
# por handshake) y ahora Caddy termina la TLS el mismo en :8091, con un certificado propio. Ese
# certificado lo sigue emitiendo Tailscale (`tailscale cert`, el mismo mecanismo ACME-like que
# ya usaba tailscaled) pero como archivo en el host, y como todo archivo con vencimiento, alguien
# tiene que pedir el siguiente antes de que caduque el actual.
#
# Es idempotente a proposito: `tailscale cert` no hace nada nuevo si el certificado vigente
# todavia tiene vida de sobra, asi que correr esto seguido no daña nada. Solo reinicia Caddy
# cuando el archivo cambio de verdad (comparando su hash), para no pagar el pequeño corte de un
# reinicio en cada corrida sin necesidad.
set -uo pipefail

HOSTNAME_FUNNEL="${FUNNEL_DOMAIN:-toolset-oci-1-1.tail2d4c18.ts.net}"
DIR_CERTS=/opt/toolset/certs
CRT="$DIR_CERTS/funnel.crt"
KEY="$DIR_CERTS/funnel.key"

log() { logger -t renovar-cert-funnel "$*"; echo "[renovar-cert-funnel] $*"; }

mkdir -p "$DIR_CERTS"

TS=/usr/bin/tailscale
[ -x "$TS" ] || TS="$(command -v tailscale || echo /usr/bin/tailscale)"

HASH_ANTES=""
[ -f "$CRT" ] && HASH_ANTES="$(sha256sum "$CRT" | cut -d' ' -f1)"

if ! "$TS" cert --cert-file "$CRT" --key-file "$KEY" "$HOSTNAME_FUNNEL" 2>&1 | logger -t renovar-cert-funnel; then
  log "ALERTA: tailscale cert fallo, se conserva el certificado anterior"
  exit 1
fi

chmod 644 "$KEY" 2>/dev/null || true  # Caddy en el contenedor lee como usuario propio, no root

HASH_DESPUES="$(sha256sum "$CRT" | cut -d' ' -f1)"

if [ "$HASH_ANTES" = "$HASH_DESPUES" ]; then
  log "sin cambios: el certificado vigente sigue sirviendo"
  exit 0
fi

log "certificado renovado: reiniciando Caddy para que lo tome"
if ( cd /opt/toolset && docker compose restart caddy ) >/dev/null 2>&1; then
  log "OK: Caddy reiniciado con el certificado nuevo"
else
  log "ALERTA: no se pudo reiniciar Caddy, el certificado en disco ya esta actualizado igual"
  exit 1
fi
