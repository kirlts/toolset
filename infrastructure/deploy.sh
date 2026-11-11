#!/usr/bin/env bash
set -euo pipefail

# deploy.sh — Toolset Personal CI/CD Deploy
set -euo pipefail

# SSH multiplexing: reuse single connection for all SSH/SCP calls
SSH_OPTS="${SSH_OPTS:--o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null}"
SSH_MUX="-o ControlMaster=auto -o ControlPath=/tmp/ssh-mux-%r@%h:%p -o ControlPersist=600"
SSH_BASE="$SSH_OPTS $SSH_MUX"

# Override ssh/scp to always use ControlMaster multiplexing
ssh() { command ssh $SSH_BASE "$@"; }
scp() { command scp $SSH_BASE "$@"; }

COMPOSE_FILE="${COMPOSE_FILE:-$(dirname "$0")/docker-compose.yml}"
REMOTE_DIR="${REMOTE_DIR:-/opt/toolset}"
SSH_HOST="${SSH_HOST:-opc@toolset-oci-1-1}"

# --- Validate required secrets ---
REQUIRED_VARS=(
  INFISICAL_ENCRYPTION_KEY
  INFISICAL_AUTH_SECRET
  INFISICAL_DB_PASSWORD
)

MISSING=0
for var in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!var:-}" ]; then
    echo "[FAIL] Missing required env var: $var"
    MISSING=1
  fi
done
[ "$MISSING" -eq 1 ] && exit 1

# --- Extend root LVM to fill boot volume (idempotent, fresh + existing) ---
# OpenTofu provisions boot_volume_size_in_gbs=100 but OL9 LVM uses ~44.5GB.
# This handles existing instances where cloud-init already ran.
echo "[DEPLOY] Checking disk layout..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "sudo dnf install -y cloud-utils-growpart 2>/dev/null || true; \
   sudo growpart /dev/sda 3 2>/dev/null && echo '  partition extended' || echo '  partition OK'; \
   sudo pvresize /dev/sda3 2>/dev/null; \
   sudo lvextend -l +100%FREE /dev/ocivolume/root 2>/dev/null && echo '  LV extended' || echo '  LV OK'; \
   sudo xfs_growfs / 2>/dev/null && echo '  FS grown' || echo '  FS OK'"

# --- Write .env on remote (only if missing — never recreate on health) ---
echo "[DEPLOY] Checking .env status..."
ENV_NEEDS_WRITE=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "[ ! -f ${REMOTE_DIR}/.env ] && echo yes || echo no" 2>&1)
if [ "$ENV_NEEDS_WRITE" = "yes" ]; then
  echo "[DEPLOY] Writing .env on remote server..."
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "sudo tee ${REMOTE_DIR}/.env > /dev/null" <<ENVEOF
INFISICAL_ENCRYPTION_KEY=${INFISICAL_ENCRYPTION_KEY}
INFISICAL_AUTH_SECRET=${INFISICAL_AUTH_SECRET}
INFISICAL_DB_PASSWORD=${INFISICAL_DB_PASSWORD}
INFISICAL_DB_USER=infisical
INFISICAL_DB_NAME=infisical
INFISICAL_SITE_URL=http://toolset-oci:8081
DB_CONNECTION_URI=postgresql://${INFISICAL_DB_USER:-infisical}:${INFISICAL_DB_PASSWORD:-infisical}@postgres:5432/${INFISICAL_DB_NAME:-infisical}
FUNNEL_DOMAIN=${FUNNEL_DOMAIN:-toolset-oci-1-1.tail2d4c18.ts.net}
INFISICAL_PID=${INFISICAL_PID:-}
INFISICAL_SERVICE_TOKEN=${INFISICAL_SERVICE_TOKEN:-}
ENVEOF
else
  echo "[DEPLOY] .env exists. Skipping rewrite."
fi

# --- Contrasena de administrador de Nextcloud (se genera en el servidor, una vez) ---
# El .env solo se escribe si falta, asi que una variable nueva no llega por el bloque de arriba.
# Se genera alla y nunca sale del servidor. docker-compose.yml la exige con `:?`: sin ella la
# imagen deja el instalador web publico abierto.
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "sudo grep -q '^NEXTCLOUD_ADMIN_PASSWORD=' ${REMOTE_DIR}/.env || \
   { echo \"NEXTCLOUD_ADMIN_PASSWORD=\$(openssl rand -base64 30 | tr -dc A-Za-z0-9 | head -c 32)\" | sudo tee -a ${REMOTE_DIR}/.env > /dev/null && echo '  NEXTCLOUD_ADMIN_PASSWORD generada'; }"

# --- Transfer Caddyfile (must precede compose up) ---
CADDY_DOMAIN="${FUNNEL_DOMAIN:-toolset-oci-1-1.tail2d4c18.ts.net}"
CADDYFILE_DIR="$(dirname "${COMPOSE_FILE}")"
CADDYFILE="${CADDYFILE_DIR}/Caddyfile"
if [ -f "$CADDYFILE" ]; then
  echo "[DEPLOY] Transferring Caddyfile..."
  scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$CADDYFILE" "${SSH_HOST}:/tmp/Caddyfile"

  # Se escribe con `tee`, no con `mv`: el Caddyfile es un bind mount de ARCHIVO y mv
  # crea un inode nuevo — el contenedor seguiria viendo el archivo viejo. Y se detecta
  # si cambio, porque transferirlo no lo aplica: el sitio corre con `admin off`, asi
  # que no hay reload en caliente y recargar significa reiniciar el contenedor. Sin
  # esto un cambio de rutas se transfiere y no surte efecto, en silencio.
  CADDY_CHANGED=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "sudo cmp -s /tmp/Caddyfile ${REMOTE_DIR}/Caddyfile && echo no || echo yes" \
    2>/dev/null || echo yes)
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "sudo tee ${REMOTE_DIR}/Caddyfile < /tmp/Caddyfile > /dev/null && rm -f /tmp/Caddyfile"
  echo "[DEPLOY] Caddyfile transferred (domain: ${CADDY_DOMAIN}, changed: ${CADDY_CHANGED})"

  if [ "$CADDY_CHANGED" = "yes" ]; then
    if ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
         "${SSH_HOST}" "docker ps --format '{{.Names}}' | grep -qx caddy" > /dev/null 2>&1; then
      # Validar ANTES de reiniciar: con una config que no adapta, Caddy no arranca y se
      # lleva por delante todo lo publicado. Si es invalida no se toca nada —el
      # contenedor sigue sirviendo la anterior— y el deploy avisa y continua.
      if ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
           "${SSH_HOST}" "docker exec caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile" \
           > /dev/null 2>&1; then
        # || true por [DT-010]: si el restart falla, Caddy sigue con la config anterior
        # —degradado, no caido— y no vale abortar el deploy completo por eso.
        if ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
             "${SSH_HOST}" "docker restart caddy" > /dev/null 2>&1; then
          echo "[DEPLOY] Caddy reiniciado con la config nueva."
        else
          echo "[DEPLOY] ⚠️  No se pudo reiniciar Caddy; sigue con la config anterior."
        fi
      else
        echo "[DEPLOY] ⚠️  Caddyfile INVALIDO — Caddy NO se reinicia, sigue con la config anterior."
      fi
    else
      echo "[DEPLOY] Caddy aun no existe; lo creara 'compose up' con la config nueva."
    fi
  fi

# --- Ensure docker-compose.yml is in sync (needed for extra_hosts, volumes, etc.) ---
COMPOSE_SRC="$(dirname "${COMPOSE_FILE}")/docker-compose.yml"
echo "[DEPLOY] Syncing docker-compose.yml..."
scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$COMPOSE_SRC" "${SSH_HOST}:/tmp/docker-compose.yml"
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "sudo mv -f /tmp/docker-compose.yml ${REMOTE_DIR}/docker-compose.yml"
echo "[DEPLOY] docker-compose.yml synced."
else
  echo "[DEPLOY] WARNING: Caddyfile not found at $CADDYFILE"
fi

# --- Apply Caddy's cgroup limits (cpuset/cpu_shares/memory) live, never by recreating it ---
# Caddy es tan sensible a esto como kb-mcp (ver el comentario de "Recreate services" mas
# abajo, que ya excluye a kb-mcp por la misma razon): el `docker compose up -d` generico
# recrea CUALQUIER servicio cuya config resuelta cambio, y una recreacion de Caddy corta
# cualquier conexion en vuelo mientras arranca de cero -- es la puerta publica del
# fundador (UD-004/D5 de kb-okos), nunca puede tener ese hueco. Medido el 2026-09-27:
# agregar `cpuset` a docker-compose.yml (para que el kb-mcp activo deje de compartir
# nucleo con el candidato en armado, ver desplegar-sin-caida.sh) disparo justo esta
# recreacion generica -- Caddy todavia no estaba excluido de "OTROS" porque hasta ese
# commit su compose nunca habia cambiado un valor de cgroup -- y la puerta quedo sin
# contestar ~11s (sondeada cada 1s: 8 fallas seguidas, "TLS unexpected eof", con Caddy
# logueando "serving initial configuration" -- arranque de cero, no una recarga).
# aplicar-recursos-caddy.sh aplica esos mismos valores con `docker update` sobre el
# contenedor VIVO -- sin tocar su proceso ni soltar una conexion -- y por eso Caddy
# se saca de "OTROS" mas abajo, igual que kb-mcp.
echo "[DEPLOY] Applying Caddy resource limits live (no restart)..."
scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$(dirname "$0")/aplicar-recursos-caddy.sh" "${SSH_HOST}:/tmp/aplicar-recursos-caddy.sh"
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "sudo mv -f /tmp/aplicar-recursos-caddy.sh ${REMOTE_DIR}/aplicar-recursos-caddy.sh && \
   sudo chmod +x ${REMOTE_DIR}/aplicar-recursos-caddy.sh && \
   cd ${REMOTE_DIR} && sudo REMOTE_DIR=${REMOTE_DIR} bash aplicar-recursos-caddy.sh" \
  | sed 's/^/  [CADDY-CPU] /' \
  || echo "[DEPLOY]   ⚠️  no se pudieron aplicar los recursos de Caddy en vivo (no bloqueante; sigue con los de antes)."

# --- Pull images ---
echo "[DEPLOY] Pulling container images..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "cd ${REMOTE_DIR} && sudo docker compose pull 2>&1" | sed 's/^/  [PULL] /'

# --- Port cleanup (prevent "address already in use" from zombie processes) ---
# 8080 SE SACO DE ESTA LIMPIEZA INCONDICIONAL. Es el puerto de Caddy — el UNICO frente
# del conector del fundador (UD-004/D5 de kb-okos), que no puede tener ninguna caida en
# ningun momento. Medido el 2026-09-26: este `fuser -k 8080/tcp` corria en CUALQUIER
# despliegue de esta infraestructura, tocara o no tocara kb-mcp, y mataba el
# docker-proxy que sostiene el puerto de un Caddy sano y corriendo — el paso de mas
# abajo, "Verify Caddy port binding", lo detectaba roto un momento despues y lo
# recreaba, con la puerta del fundador devolviendo 502 durante ese hueco (~20s
# medidos). Ese mismo paso de mas abajo YA comprueba la salud primero y solo
# interviene si de verdad esta sordo — es la forma correcta, condicional, de resolver
# el "docker-proxy colgado" que este cleanup preventivo pretendia evitar. 8888 y 9999
# no son de Caddy (puertos sueltos de pruebas manuales/sandboxes) y se siguen matando
# sin condicion, porque no sirven nada que el fundador use.
echo "[DEPLOY] Cleaning up ports..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "sudo fuser -k 8888/tcp 2>/dev/null || true; \
   sudo fuser -k 9999/tcp 2>/dev/null || true; \
   sleep 1"
echo "[DEPLOY] Ports cleaned (8080/Caddy excluido — su propio paso de verificacion decide)."

# --- Recreate changed services ---
# kb-mcp QUEDA AFUERA A PROPOSITO. Este `up -d` generico no sabe nada de recambios sin
# corte: si compose ve que la imagen resuelta para el servicio "kb-mcp" ya no coincide
# con la del contenedor corriendo (p.ej. porque alguien reconstruyo el tag localmente,
# aunque sea para un ensayo — comprobado el 2026-09-26), lo RECREA EN EL LUGAR aca mismo,
# antes de que el bloque dedicado a kb-mcp (mas abajo, con desplegar-sin-caida.sh) llegue
# siquiera a correr. Eso peso exactamente esa falla: el paso generico bajo el contenedor
# viejo y el nuevo tardo 126s en indexar antes de escuchar — de 1 a 2 minutos de la puerta
# del fundador (UD-004/D5 de kb-okos) respondiendo 502, con el mecanismo sin corte todavia
# sin haber tocado nada. kb-mcp SOLO se recrea por su propio bloque, nunca por este.
echo "[DEPLOY] Recreating services (kb-mcp excluded — it has its own no-downtime path)..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
    "cd ${REMOTE_DIR} && \
    OTROS=\$(docker compose config --services | grep -vxE 'kb-mcp|caddy' | tr '\n' ' ') && \
    docker compose up -d --remove-orphans \$OTROS 2>&1" | sed 's/^/  [UP] /'

# --- Verify Caddy port binding (docker-proxy often drops it) ---
# El fuser -k + --force-recreate juntos son la via correcta solo cuando caddy esta
# Running pero sordo (docker-proxy colgado): matar el proceso justo antes de que
# compose recree el MISMO contenedor corre una carrera con el daemon ("No such
# container" al referenciar un ID que compose ya estaba retirando). Si el
# contenedor quedo en Created/Exited (p.ej. porque un `up` previo aborto por la
# espera de una dependencia), no hay proxy que matar: basta un `up -d` normal.
# Ademas, el `|| true` final es obligatorio: esto es un intento de recuperacion
# best-effort que YA se verifica despues (PORT_RETRY y el loop de servicios
# criticos); sin el, un fallo aca disparaba `pipefail` + `set -e` y abortaba TODO
# el deploy a mitad de camino, dejando caddy a medio recrear (bug real: 2026-07-25).
echo "[DEPLOY] Verifying Caddy port binding..."
PORT_OK=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://localhost:8080/health 2>/dev/null || echo '000'" 2>/dev/null || echo "000")
if [ "$PORT_OK" != "200" ] && [ "$PORT_OK" != "502" ]; then
  echo "  Port 8080 not responding (HTTP $PORT_OK). Attempting recovery..."
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "cd ${REMOTE_DIR} && \
     STATE=\$(sudo docker inspect caddy --format '{{.State.Status}}' 2>/dev/null || echo missing); \
     echo \"  caddy state: \$STATE\"; \
     if [ \"\$STATE\" = running ]; then \
       echo '  running but unresponsive: killing stale port binding and recreating'; \
       sudo fuser -k 8080/tcp 2>/dev/null || true; \
       sleep 2; \
       sudo docker compose up -d --force-recreate caddy 2>&1; \
     else \
       echo \"  not running (\$STATE): starting\"; \
       sudo docker compose up -d caddy 2>&1; \
     fi" | sed 's/^/  [FIX] /' || true
  sleep 5
  PORT_RETRY=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://localhost:8080/health 2>/dev/null || echo '000'" 2>/dev/null || echo "000")
  echo "  Port after fix: HTTP $PORT_RETRY"
else
  echo "  ✅ Caddy port binding OK (HTTP $PORT_OK)"
fi

# --- Save compose state for rollback ---
echo "[DEPLOY] Saving compose state for rollback..."
ROLLBACK_FILE="${REMOTE_DIR}/docker-compose.previous.yml"
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "if [ -f ${REMOTE_DIR}/docker-compose.yml ]; then \
     sudo cp ${REMOTE_DIR}/docker-compose.yml ${ROLLBACK_FILE} && \
     echo '  Previous compose saved'; \
   else echo '  No previous compose to save'; fi"

DEPLOY_FAILED=false

# --- Sync kb-mcp server code (server.py + Dockerfile), SIN CORTAR EL SERVICIO ---
# VA ANTES DE VERIFICAR LOS SERVICIOS CRITICOS, Y NO AL FINAL. El 2026-09-10 este bloque vivia al
# final del guion: el bootstrap de Infisical fallo (salida 7) y el despliegue murio sin llegar aca,
# asi que el servidor de la base quedo sirviendo el codigo de agosto aunque el commit habia entrado
# —cuarenta minutos, hasta un reintento a mano—. El servidor de la base es el servicio con mas
# consumidores de esta maquina y su sincronizacion no puede depender de que todo lo demas salga bien.
# Cierra la brecha DT-012: hasta 2026-07-24 el codigo del servidor kb-mcp solo se
# desplegaba a mano por SSH — el pipeline dejaba el contenedor corriendo la version
# anterior en silencio (deploy verde ≠ contenedor actualizado, el mismo patron de
# fallo silencioso de HEU-006). Bloque deliberadamente no-fatal (`|| true` en todo)
# y condicionado por checksum: si el codigo remoto ya es identico no toca NADA (ni
# build ni recambio — cero riesgo para lo que esta corriendo). Solo reconstruye
# cuando hay diferencia real.
#
# HASTA EL 2026-09-26 ESTO HACIA `docker compose up -d kb-mcp` EN EL LUGAR, que para el
# contenedor viejo, lo saca y recien arranca el nuevo — con la cache de vectores fria,
# medido entre 60 y 71s sin que el servidor conteste nada (ver el comentario de
# desplegar-sin-caida.sh). Ese servidor es la puerta del fundador (UD-004/D5 de kb-okos,
# `KB_TOKEN_PUBLICADO`), que puede entrar en cualquier momento — no hay ventana. Ahora el
# recambio lo hace desplegar-sin-caida.sh: levanta el contenedor nuevo al lado, lo prueba
# con una llamada MCP real, y solo si contesta lo hace responder al nombre `kb-mcp` (con
# el viejo todavia respondiendolo tambien, nunca un instante sin nadie) antes de bajar al
# viejo. Ensayado el 2026-09-26 contra un par de contenedores de prueba: 0 fallas en 195
# sondeos cada 0.2s durante el recambio.
KB_MCP_SRC="$(dirname "${COMPOSE_FILE}")/kb-mcp"
# vivo.py se sumo el 2026-09-25: server.py importa `esta_retirado` desde ahi (ver el
# comentario del Dockerfile). Sin sumarlo tambien aca, el checksum nunca lo detecta,
# nunca se copia al remoto, y el build de la imagen falla con ModuleNotFoundError —el
# mismo patron de "el codigo fuente cambio y el despliegue no se entero" que este
# bloque entero existe para cerrar (DT-012). desplegar-sin-caida.sh entra al mismo
# checksum por la misma razon: si cambia el mecanismo de despliegue sin que cambie
# server.py, el checksum viejo no lo detectaria y el servidor seguiria recambiandose
# con el guion desactualizado.
if [ -f "$KB_MCP_SRC/server.py" ] && [ -f "$KB_MCP_SRC/Dockerfile" ] && [ -f "$KB_MCP_SRC/vivo.py" ] \
   && [ -f "$KB_MCP_SRC/desplegar-sin-caida.sh" ]; then
  echo "[DEPLOY] Syncing kb-mcp server code..."
  KB_MCP_LOCAL_SUM=$(cat "$KB_MCP_SRC/server.py" "$KB_MCP_SRC/Dockerfile" "$KB_MCP_SRC/vivo.py" \
    "$KB_MCP_SRC/desplegar-sin-caida.sh" | md5sum | awk '{print $1}')
  KB_MCP_REMOTE_SUM=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "cat /opt/toolset/kb-mcp/server.py /opt/toolset/kb-mcp/Dockerfile /opt/toolset/kb-mcp/vivo.py \
      /opt/toolset/kb-mcp/desplegar-sin-caida.sh 2>/dev/null | md5sum | awk '{print \$1}'" \
    2>/dev/null || echo "unreachable")
  if [ "$KB_MCP_LOCAL_SUM" = "$KB_MCP_REMOTE_SUM" ]; then
    echo "[DEPLOY]   kb-mcp code unchanged; container untouched."
  elif [ "$KB_MCP_REMOTE_SUM" = "unreachable" ]; then
    echo "[DEPLOY]   ⚠️  no se pudo leer el codigo remoto; kb-mcp queda como esta (no bloqueante)."
  else
    scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      "$KB_MCP_SRC/server.py" "$KB_MCP_SRC/Dockerfile" "$KB_MCP_SRC/vivo.py" \
      "$KB_MCP_SRC/desplegar-sin-caida.sh" \
      "${SSH_HOST}:/tmp/" 2>/dev/null || true
    ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      "${SSH_HOST}" \
      "sudo cp /tmp/server.py /opt/toolset/kb-mcp/server.py && \
       sudo cp /tmp/Dockerfile /opt/toolset/kb-mcp/Dockerfile && \
       sudo cp /tmp/vivo.py /opt/toolset/kb-mcp/vivo.py && \
       sudo cp /tmp/desplegar-sin-caida.sh /opt/toolset/kb-mcp/desplegar-sin-caida.sh && \
       sudo chmod +x /opt/toolset/kb-mcp/desplegar-sin-caida.sh && \
       rm -f /tmp/server.py /tmp/Dockerfile /tmp/vivo.py /tmp/desplegar-sin-caida.sh && \
       cd ${REMOTE_DIR} && \
       sudo REMOTE_DIR=${REMOTE_DIR} bash kb-mcp/desplegar-sin-caida.sh" 2>&1 | tail -20 \
      && echo "[DEPLOY]   kb-mcp recambiado sin corte." \
      || echo "[DEPLOY]   ⚠️  el recambio sin corte fallo; el contenedor sigue con la version anterior (no bloqueante — desplegar-sin-caida.sh nunca toca al viejo si el nuevo no contesta sano)."
  fi
fi

# --- Verify critical services ---
echo "[DEPLOY] Verifying critical services..."
sleep 10
CRITICAL="caddy infisical"
for attempt in 1 2 3; do
  ALL_OK=true
  for svc in $CRITICAL; do
    STATUS=$(ssh "${SSH_HOST}" \
      "sudo docker inspect $svc --format '{{.State.Health.Status}}' 2>/dev/null || echo missing")
    if [ "$STATUS" != "healthy" ]; then
      echo "  ⏳ $svc: $STATUS (attempt $attempt/3)"
      ALL_OK=false
    fi
  done
  $ALL_OK && break
  [ "$attempt" -lt 3 ] && sleep 10
done
for svc in $CRITICAL; do
  STATUS=$(ssh "${SSH_HOST}" \
    "sudo docker inspect $svc --format '{{.State.Health.Status}}' 2>/dev/null || echo missing")
  if [ "$STATUS" = "healthy" ]; then echo "  ✅ $svc"; else echo "  ❌ $svc: $STATUS"; DEPLOY_FAILED=true; fi
done

# --- Clone toolset repo on server (idempotent) ---
echo "[DEPLOY] Syncing toolset repo on server..."
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "if [ -d /opt/toolset-repo/.git ]; then \
     cd /opt/toolset-repo && sudo git pull --ff-only 2>&1 | tail -1; \
   else \
     sudo git clone https://github.com/kirlts/toolset.git /opt/toolset-repo && \
     sudo chown -R opc:opc /opt/toolset-repo; \
   fi"

# --- Bootstrap Infisical & setup project (idempotent) ---
INFISICAL_ADMIN_EMAIL="${INFISICAL_ADMIN_EMAIL:-}"
INFISICAL_ADMIN_PASSWORD="${INFISICAL_ADMIN_PASSWORD:-}"
INFISICAL_SERVICE_TOKEN="${INFISICAL_SERVICE_TOKEN:-}"
# Read persistent state from server .env
INFISICAL_PID=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "grep '^INFISICAL_PID=' ${REMOTE_DIR}/.env | cut -d= -f2-" 2>/dev/null || echo "")
INFISICAL_TOKEN=""  # Active token for API calls (identity or service token)

# Also read service token from .env (overrides GitHib Secrets if present)
ENV_SVC_TOKEN=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "grep '^INFISICAL_SERVICE_TOKEN=' ${REMOTE_DIR}/.env | cut -d= -f2-" 2>/dev/null || echo "")
[ -n "$ENV_SVC_TOKEN" ] && INFISICAL_SERVICE_TOKEN="$ENV_SVC_TOKEN"

# Step 1: Bootstrap admin (returns identity token on fresh setup, 400 if exists)
if [ -n "$INFISICAL_ADMIN_EMAIL" ] && [ -n "$INFISICAL_ADMIN_PASSWORD" ]; then
  echo "[DEPLOY] Bootstrapping Infisical admin..."
  BOOTSTRAP_RESP=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "sudo docker exec -i infisical sh -c 'curl -s -X POST \"http://localhost:8080/api/v1/admin/bootstrap\" -H \"Content-Type: application/json\" -d \"{\\\"email\\\":\\\"${INFISICAL_ADMIN_EMAIL}\\\",\\\"password\\\":\\\"${INFISICAL_ADMIN_PASSWORD}\\\",\\\"organization\\\":\\\"Admin Org\\\"}\"'" 2>&1)

  # Extract identity token if bootstrap was successful (fresh setup)
  FRESH_TOKEN=$(echo "$BOOTSTRAP_RESP" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    t=d.get('identity',{}).get('credentials',{}).get('token','')
    print(t)
except:
    print('')
" 2>/dev/null)

  if [ -n "$FRESH_TOKEN" ]; then
    INFISICAL_TOKEN="$FRESH_TOKEN"
    echo "  [Infisical] Admin created (identity token acquired)"

    # Fresh bootstrap: create project
    echo "  [Infisical] Creating Toolset project..."
    PROJECT_RESP=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      "${SSH_HOST}" \
      "sudo docker exec -i infisical sh -c 'curl -s -X POST \"http://localhost:8080/api/v1/projects\" -H \"Authorization: Bearer ${INFISICAL_TOKEN}\" -H \"Content-Type: application/json\" -d \"{\\\"projectName\\\":\\\"Toolset\\\",\\\"type\\\":\\\"secret-manager\\\",\\\"shouldCreateDefaultEnvs\\\":true}\"'" 2>&1)
    INFISICAL_PID=$(echo "$PROJECT_RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('project',{}).get('id',''))" 2>/dev/null)

    if [ -n "$INFISICAL_PID" ]; then
      echo "  [Infisical] Toolset project created (ID: $INFISICAL_PID)"
      # Persist project ID in .env
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        "${SSH_HOST}" \
        "grep -q '^INFISICAL_PID=' ${REMOTE_DIR}/.env && sudo sed -i 's|^INFISICAL_PID=.*|INFISICAL_PID=${INFISICAL_PID}|' ${REMOTE_DIR}/.env || echo 'INFISICAL_PID=${INFISICAL_PID}' | sudo tee -a ${REMOTE_DIR}/.env > /dev/null" 2>&1

      # Create a permanent service token for CI/CD
      NEW_TOKEN=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        "${SSH_HOST}" \
        "sudo docker exec -i infisical sh -c 'curl -s -X POST \"http://localhost:8080/api/v2/service-token\" -H \"Authorization: Bearer ${INFISICAL_TOKEN}\" -H \"Content-Type: application/json\" -d \"{\\\"name\\\":\\\"ci-cd-pipeline\\\",\\\"workspaceId\\\":\\\"${INFISICAL_PID}\\\",\\\"scopes\\\":[{\\\"environment\\\":\\\"dev\\\",\\\"secretPath\\\":\\\"/\\\"},{\\\"environment\\\":\\\"prod\\\",\\\"secretPath\\\":\\\"/\\\"}],\\\"permissions\\\":[\\\"read\\\",\\\"write\\\"],\\\"encryptedKey\\\":\\\"\\\",\\\"iv\\\":\\\"\\\",\\\"tag\\\":\\\"\\\",\\\"expiresIn\\\":0}\"'" 2>&1 | python3 -c "import sys,json;print(json.load(sys.stdin).get('serviceToken',''))" 2>/dev/null)
      if [ -n "$NEW_TOKEN" ]; then
        INFISICAL_TOKEN="$NEW_TOKEN"
        echo "  [Infisical] Service token created"
        # Persist in .env for future deploys
        ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
          "${SSH_HOST}" \
          "grep -q '^INFISICAL_SERVICE_TOKEN=' ${REMOTE_DIR}/.env && sudo sed -i 's|^INFISICAL_SERVICE_TOKEN=.*|INFISICAL_SERVICE_TOKEN=${NEW_TOKEN}|' ${REMOTE_DIR}/.env || echo 'INFISICAL_SERVICE_TOKEN=${NEW_TOKEN}' | sudo tee -a ${REMOTE_DIR}/.env > /dev/null" 2>&1
      fi
    else
      echo "  [Infisical] Project creation fail: $(echo $PROJECT_RESP | head -c 100)"
    fi
  elif echo "$BOOTSTRAP_RESP" | grep -q "already been set up"; then
    echo "  [Infisical] Admin already exists"
    INFISICAL_TOKEN="$INFISICAL_SERVICE_TOKEN"
  else
    echo "  [Infisical] Bootstrap response: $(echo $BOOTSTRAP_RESP | head -c 100)"
    INFISICAL_TOKEN="$INFISICAL_SERVICE_TOKEN"
  fi
else
  INFISICAL_TOKEN="$INFISICAL_SERVICE_TOKEN"
fi

# Step 3: Sync secrets to Infisical (standalone script, verifiable)
if [ -n "$INFISICAL_TOKEN" ] && [ -n "$INFISICAL_PID" ]; then
  echo "[DEPLOY] Syncing secrets to Infisical..."
  SYNC_SCRIPT="/opt/toolset-repo/scripts/sync-infisical-secrets.py"
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "set -- \
      INFISICAL_TOKEN='${INFISICAL_TOKEN}' \
      INFISICAL_PID='${INFISICAL_PID}' \
      FUNNEL_DOMAIN='${FUNNEL_DOMAIN:-}'; \
    for var in \"\$@\"; do eval export \"\$var\"; done && \
    python3 ${SYNC_SCRIPT} push && \
    python3 ${SYNC_SCRIPT} verify"
  echo "[DEPLOY] All secrets synced to Infisical (dev + prod)."

  # Reverse sync moved to deploy.yml (GitHub Runner context) where
  # GH_TOKEN has permissions for gh secret set. See deploy.yml step.
elif [ -n "$INFISICAL_SERVICE_TOKEN" ]; then
  echo "[DEPLOY] INFISICAL_SERVICE_TOKEN set but could not resolve project"
else
  echo "[DEPLOY] INFISICAL_SERVICE_TOKEN not set, skipping secret sync"
fi

# --- Generate dynamic landing page with current routes ---
LANDING_HTML=$(cat <<EOF
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Toolset Personal</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 44em; margin: 3em auto; padding: 0 1em; color: #e0e0e0; background: #1a1a2e; }
  h1 { color: #00d4aa; }
  a { color: #7ec8e3; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .tree { font-family: monospace; line-height: 1.8; }
  .tree .path { color: #f0c674; }
  .tree .desc { color: #b5bd68; }
  .tree .status { color: #8abeb7; }
  .tree .pipe { color: #555; }
  .meta { margin-top: 2em; font-size: 0.85em; color: #888; border-top: 1px solid #333; padding-top: 1em; }
  code { background: #0f3460; padding: 0.1em 0.4em; border-radius: 4px; font-size: 0.9em; }
  .warning { color: #cc6666; }
</style>
</head>
<body>
<h1>🔧 Toolset Personal</h1>
<p>Servicios autogestionados en OCI (sa-valparaiso-1).</p>
<div class="tree">
<pre>
  <span class="pipe">├──</span> <span class="path"><a href="/">/</a></span>                        <span class="desc">Landing page &mdash; Toolset status</span>   <span class="status">✅</span>
  <span class="pipe">├──</span> <span class="path"><a href="/api/status">/api/status</a></span>               <span class="desc">Infisical &mdash; API Health</span>           <span class="status">✅</span>
  <span class="pipe">├──</span> <span class="path"><a href="https://${CADDY_DOMAIN}:8443/">:8443/</a></span>                  <span class="desc">Infisical UI &mdash; Funnel directo</span>      <span class="status">✅</span>
</pre>
</div>
<div class="meta">
  <p>Infisical UI: <a href="https://${CADDY_DOMAIN}:8443/" style="color:#7ec8e3;">https://${CADDY_DOMAIN}:8443/</a> <span class="status">(Funnel)</span></p>
  <p>Gobernanza: <a href="https://github.com/kirlts/toolset/blob/main/docs/RULES.md" style="color:#7ec8e3;">docs/RULES.md</a></p>
  <p>Deploy: $(date -u +"%Y-%m-%d %H:%M UTC") &bull; OCI &bull; VM.Standard.A1.Flex &bull; ARM64</p>
</div>
</body>
</html>
EOF
)
echo "[DEPLOY] Generating dynamic landing page..."
echo "$LANDING_HTML" | ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "sudo tee ${REMOTE_DIR}/landing/index.html > /dev/null"

# --- Deploy kb-mcp KB sync (clon de la KB + script + cron) ---
# Bloque deliberadamente no-fatal: todo termina en `|| true` para que un fallo
# aqui NUNCA aborte un deploy (deploy.sh corre con set -euo pipefail).
# SE INSTALA CON `mv`, NO CON `cp`, y la diferencia no es de estilo (2026-08-19).
# bash lee un guion por tramos mientras lo ejecuta, asi que sobrescribir el archivo
# EN EL SITIO mientras hay una corrida viva la hace seguir leyendo desde el
# desplazamiento viejo del archivo nuevo: ejecuta basura. Paso ese dia — una linea
# de comentario corrida a mitad se ejecuto como comando. `mv` es un renombre: la
# corrida en curso conserva su archivo viejo entero y termina bien.
# Importa mas que antes: el reloj pasa cada minuto y un rearmado dura unos 60 s,
# asi que lo normal es que HAYA una corrida viva justo cuando se despliega.
KB_SYNC_SRC="$(dirname "${COMPOSE_FILE}")/kb-mcp/sync-kb.sh"
if [ -f "$KB_SYNC_SRC" ]; then
  echo "[DEPLOY] Deploying kb-mcp KB sync..."
  SSH_HOST="${SSH_HOST}" bash "$(dirname "${COMPOSE_FILE}")/kb-mcp/instalar-sync-kb.sh" || true
  # Manifiesto de KB a servir: "slug rama repo". Agregar una KB nueva es una linea.
  # Clon partial (--filter=blob:limit=1m): historial completo de commits, y ademas los
  # CONTENIDOS de texto, sin descargar los binarios pesados del historial.
  #
  # ERA `blob:none` HASTA EL 2026-08-08, y el cambio tiene una razon medida. Sin contenidos,
  # `git log --name-only` alcanza para la fecha por ARCHIVO, pero NO para la fecha por
  # SUB-ENTRADA, que se deriva de la autoria linea por linea y necesita cada version historica
  # del archivo. Con `blob:none` git sale a buscarlas por red de a una y el servidor no termina
  # de arrancar: 411 archivos, contenedor «unhealthy», registro vacio.
  #
  # Lo que cuesta traerlas, medido en el VPS el 2026-08-08 sobre la KB de okos: 3 segundos y
  # 12 MB (de 16 a 28 MB), y con eso el calculo de las 105 sub-entradas baja a 4 segundos. El
  # limite de 1 MB por objeto conserva el motivo original —los binarios pesados no bajan— que
  # es de donde salia la cifra de 154 MB.
  #
  # Un clon YA EXISTENTE no cambia con esto: se lo actualiza una vez con
  #   git -C /opt/kb/<slug> fetch --refetch --filter=blob:limit=1m origin <rama> Privadas: usa las credenciales de gh del usuario opc.
  # Las KB son repos privados y git no trae credenciales por si solo: sin esto el
  # clon inicial y el cron de sync fallan con "could not read Username" —el fetch
  # aborta y la KB se queda congelada en la version del dia del clon, en silencio.
  # `gh auth setup-git` registra gh como credential helper; es idempotente.
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "gh auth setup-git" > /dev/null 2>&1 \
    && echo "[DEPLOY]   credenciales git (gh) configuradas" \
    || echo "[DEPLOY]   ⚠️  gh no autenticado: las KB privadas no podran sincronizarse"

  KB_MANIFIESTO="traza-ambiental planning https://github.com/kirlts/traza-ambiental.git
personal main https://github.com/kirlts/personal.git
okos master https://github.com/kirlts/kb-okos.git"
  echo "$KB_MANIFIESTO" | while read -r slug rama repo; do
    [ -n "$slug" ] || continue
    # -n: sin stdin. Dentro de un while-read, ssh sin -n se COME las lineas restantes
    # del manifiesto — solo la primera KB se procesaba y el resto moria en silencio
    # (descubierto 2026-07-25 al agregar la tercera KB: el log solo decia
    # "traza-ambiental ya clonada" y okos nunca se clono).
    ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      "${SSH_HOST}" \
      "export PATH=/usr/local/bin:/home/opc/.local/bin:\$PATH GIT_TERMINAL_PROMPT=0; \
       sudo mkdir -p /opt/kb && sudo chown opc:opc /opt/kb; \
       sudo mkdir -p /opt/kb-vectores && sudo chown 10001:10001 /opt/kb-vectores; \
       if [ ! -d /opt/kb/${slug}/.git ]; then \
         S=/opt/kb/.stage.\$\$; rm -rf \"\$S\"; \
         git clone --filter=blob:limit=1m --branch ${rama} --single-branch \
           ${repo} \"\$S\" -q && \
         [ \"\$(find \"\$S/knowledge-base\" -name '*.md' | wc -l)\" -ge 5 ] && \
         sudo rm -rf /opt/kb/${slug} && mv \"\$S\" /opt/kb/${slug} && \
         echo '  ${slug} clonada' || { rm -rf \"\$S\"; echo '  ${slug} clone fallo (no bloqueante)'; }; \
       else echo '  ${slug} ya clonada'; fi" 2>/dev/null || true
  done
  # El cron escribe a un log, NO a /dev/null. Con /dev/null, un sync que falla —el caso
  # real: credenciales de git ausentes, el fetch aborta— deja la KB congelada en la version
  # del dia del clon y nada lo dice: el servicio responde sano, con contenido viejo. La linea
  # se reescribe si quedo apuntando a /dev/null de un despliegue anterior.
  #
  # CADA MINUTO, no cada quince (2026-08-19). Desde ese dia el camino normal ya no
  # es el reloj: el repositorio de la KB avisa AL PUBLICAR, via el gancho pre-push
  # que llama a /usr/local/sbin/kb-sync-ahora. El reloj quedo como RED, para el caso
  # de que el aviso no llegue —sin red, servidor ocupado, publicacion desde una
  # maquina sin la llave—; y una red que tarda un cuarto de hora deja al fundador
  # leyendo contenido viejo sin saberlo. El costo de correrlo cada minuto es nulo
  # cuando no hay cambios: compara el HEAD y sale.
fi


# Raw TCP hasta Caddy en :8091, donde Caddy mismo termina la TLS con el certificado de
# Tailscale (ver Caddyfile). NO "--https=443 http://localhost:8080": ese modo hace que
# tailscaled termine la TLS con su propio stack en espacio de usuario, y ahi vive un bug
# conocido (tailscale/tailscale#18916) que agrega ~220ms de pausa por Nagle+ACK retrasado,
# DOS veces por handshake — medido el 2026-09-27 en el camino publico del Funnel.
FUNNEL_LOCAL_PORT="8091"
echo "[DEPLOY] Ensuring Tailscale Funnel -> Caddy (TLS propia, :${FUNNEL_LOCAL_PORT})..."
CURRENT_FUNNEL=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "sudo tailscale funnel status 2>&1" || echo "")
if echo "$CURRENT_FUNNEL" | grep -q "tcp://127.0.0.1:${FUNNEL_LOCAL_PORT}"; then
  echo "[DEPLOY] Tailscale Funnel already forwards raw TCP to Caddy:${FUNNEL_LOCAL_PORT}"
else
  echo "[DEPLOY] Configuring Tailscale Funnel on :443 -> raw TCP -> Caddy:${FUNNEL_LOCAL_PORT}..."
  # Si el 443 seguia en modo HTTPS (config vieja), primero se limpia: los dos modos no
  # coexisten en el mismo puerto.
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "sudo tailscale funnel --https=443 off 2>&1" | sed 's/^/  /' || true
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "sudo tailscale funnel --bg --tcp=443 ${FUNNEL_LOCAL_PORT} 2>&1" | sed 's/^/  /'
fi

# --- Ensure Infisical Funnel on :8443 (Infisical Web UI, separate from CP _next/*) ---
INFISICAL_PORT="8443"
echo "[DEPLOY] Ensuring Infisical Funnel on :${INFISICAL_PORT} -> localhost:8081..."
HAS_INFISICAL=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "sudo tailscale funnel status 2>&1" | grep -c ":${INFISICAL_PORT}" || true)
if echo "$HAS_INFISICAL" | grep -q "8081"; then
  echo "[DEPLOY] Infisical Funnel already configured"
elif [ "$HAS_INFISICAL" -gt 0 ]; then
  echo "[DEPLOY] Replacing existing Funnel on :${INFISICAL_PORT}..."
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "sudo tailscale funnel --https=${INFISICAL_PORT} off 2>&1" | sed 's/^/  /'
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "sudo tailscale funnel --bg --https=${INFISICAL_PORT} http://localhost:8081 2>&1" | sed 's/^/  /'
else
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" "sudo tailscale funnel --bg --https=${INFISICAL_PORT} http://localhost:8081 2>&1" | sed 's/^/  /'
fi

# --- Rollback on failure: restore previous compose ---
if [ "$DEPLOY_FAILED" = "true" ]; then
  echo ""
  echo "============================================"
  echo "  [DEPLOY] ❌ Service verification failed — initiating rollback"
  echo "============================================"
  ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${SSH_HOST}" \
    "if [ -f ${ROLLBACK_FILE} ]; then \
       echo '  Restoring previous docker-compose.yml...'; \
       sudo cp ${ROLLBACK_FILE} ${REMOTE_DIR}/docker-compose.yml && \
       cd ${REMOTE_DIR} && OTROS=\$(docker compose config --services | grep -vxE 'kb-mcp|caddy' | tr '\n' ' ') && \
       sudo docker compose up -d --remove-orphans \$OTROS 2>&1 && \
       echo '  Rollback complete'; \
     else \
       echo '  No rollback file available — manual recovery required'; \
     fi"
fi

# --- Infisical secret exposure verification (SEC-03) ---
echo "[DEPLOY] Verifying .env has expected secrets..."
SECRET_COUNT=$(ssh "${SSH_HOST}" "sudo grep -c '=' ${REMOTE_DIR}/.env 2>/dev/null || echo 0")
if [ "$SECRET_COUNT" -gt 3 ]; then
  echo "[DEPLOY]  ✅ .env has ${SECRET_COUNT} secrets populated"
else
  echo "[DEPLOY]  ❌ .env has only ${SECRET_COUNT} entries — secrets may not be synced"
  DEPLOY_FAILED=true
fi

# --- Preflight checks (post-deploy verification via single SSH session) ---
PREFLIGHT_SCRIPT="$(dirname "$0")/preflight.sh"
if [ -f "$PREFLIGHT_SCRIPT" ]; then
  echo "[DEPLOY] Running preflight checks..."
  # Run on VPS via single SSH connection (avoids N individual SSH calls)
  scp -q "$PREFLIGHT_SCRIPT" "${SSH_HOST}:/tmp/preflight.sh"
  if ssh "${SSH_HOST}" "bash /tmp/preflight.sh 2>&1; rm -f /tmp/preflight.sh"; then
    echo "[DEPLOY] All preflight checks passed"
  else
    echo "[DEPLOY] ❌ Preflight failed"
    DEPLOY_FAILED=true
    # Attempt rollback from preflight failure
    ssh "${SSH_HOST}" \
      "if [ -f ${ROLLBACK_FILE} ]; then \
         sudo cp ${ROLLBACK_FILE} ${REMOTE_DIR}/docker-compose.yml && \
         cd ${REMOTE_DIR} && OTROS=\$(docker compose config --services | grep -vxE 'kb-mcp|caddy' | tr '\n' ' ') && \
         sudo docker compose up -d --remove-orphans \$OTROS 2>&1; \
       fi"
  fi
fi

# --- Verify all public URLs respond correctly (mandatory) ---
echo "[DEPLOY] Verifying public URLs..."
FUNNEL="https://${CADDY_DOMAIN}"
URLS=(
  "/:Landing page"
  "/health:Health check"
  "/api/v1/:Infisical API"
)
for entry in "${URLS[@]}"; do
  path="${entry%%:*}"
  name="${entry##*:}"
  CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${FUNNEL}${path}" 2>/dev/null || echo "000")
  if [ "$CODE" = "200" ] || [ "$CODE" = "302" ] || [ "$CODE" = "404" ]; then
    echo "  ✅ ${name} (${path}) → ${CODE}"
  else
    echo "  ❌ ${name} (${path}) → ${CODE}"
    DEPLOY_FAILED=true
  fi
done

# --- Exit with error if deploy failed ---
if [ "$DEPLOY_FAILED" = "true" ]; then
  echo "[DEPLOY] ❌ Deploy completed with errors — check logs above"
  exit 1
fi

# --- Post-deploy summary ---
# --- Derive Tailscale IP for internal URLs ---
TAILSCALE_IP=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" "sudo tailscale ip -4 2>/dev/null || echo '100.x.x.x'" 2>/dev/null || echo "100.x.x.x")

echo ""
echo "============================================"
echo "  Toolset Personal — Deploy Complete"
echo "============================================"
echo ""
echo "  Funnel URL:  https://${CADDY_DOMAIN}/"
echo ""
echo "  ── Services ──────────────────────────────"
  echo "  Services         https://${CADDY_DOMAIN}/"
  echo "  Infisical UI     https://${CADDY_DOMAIN}:8443/"
  echo "  Infisical API    https://${CADDY_DOMAIN}/api/v1/"
echo ""
echo ""
echo "  ── Internal (via Tailscale) ──────────────"
  echo "  Infisical        http://${TAILSCALE_IP}:8081 (via Funnel: /api/v1/)"
echo ""
echo "  ── Docker Status ─────────────────────────"
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "${SSH_HOST}" \
  "cd ${REMOTE_DIR} && sudo docker compose ps --format 'table {{.Name}}\t{{.Status}}\t{{.Health}}'"
echo "============================================"
