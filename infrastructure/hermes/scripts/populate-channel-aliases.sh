#!/usr/bin/env bash
# populate-channel-aliases.sh
# Consulta el bridge de WhatsApp para obtener nombres humanos de grupos
# y escribe channel_aliases.json para que Hermes resuelva JIDs a nombres.
#
# Corre en cada deploy y via cron cada 10 minutos.
set -euo pipefail

BRIDGE="http://127.0.0.1:3000"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
DIRECTORY="$HERMES_HOME/channel_directory.json"
ALIASES="$HERMES_HOME/channel_aliases.json"

if [ ! -f "$DIRECTORY" ]; then
  echo "No channel_directory.json found at $DIRECTORY"
  exit 0
fi

# Leer aliases existentes (para preservar overlays manuales si existen)
if [ -f "$ALIASES" ]; then
  python3 -c "
import json
with open('$DIRECTORY') as f:
    dir_data = json.load(f)
with open('$ALIASES') as f:
    aliases = json.load(f)
result = aliases.get('whatsapp', {})

for ch in dir_data.get('platforms', {}).get('whatsapp', []):
    jid = ch['id']
    if not jid.endswith('@g.us'):
        continue
    import subprocess as sp
    import json as jmod
    try:
        r = sp.run(['curl', '-s', '--max-time', '5', '$BRIDGE/chat/' + jid],
                   capture_output=True, text=True, timeout=5)
        data = jmod.loads(r.stdout)
        name = data.get('name', jid.split('@')[0])
    except Exception as e:
        name = jid.split('@')[0]
    # Solo actualizar si el nombre cambió o no existía
    if jid not in result or result[jid] != name:
        result[jid] = name
        print('Updated: %s → %s' % (jid, name))

with open('$ALIASES', 'w') as f:
    jmod.dump({'whatsapp': result}, f, indent=2)
print('Done: %d WhatsApp group aliases' % len(result))
" 2>&1
else
  # Primera ejecución: crear desde cero
  python3 -c "
import json
with open('$DIRECTORY') as f:
    dir_data = json.load(f)
result = {}
for ch in dir_data.get('platforms', {}).get('whatsapp', []):
    jid = ch['id']
    if not jid.endswith('@g.us'):
        continue
    import subprocess as sp
    import json as jmod
    try:
        r = sp.run(['curl', '-s', '--max-time', '5', '$BRIDGE/chat/' + jid],
                   capture_output=True, text=True, timeout=5)
        data = jmod.loads(r.stdout)
        name = data.get('name', jid.split('@')[0])
    except:
        name = jid.split('@')[0]
    result[jid] = name
    print('Added: %s → %s' % (jid, name))
with open('$ALIASES', 'w') as f:
    jmod.dump({'whatsapp': result}, f, indent=2)
print('Done: %d new WhatsApp group aliases' % len(result))
" 2>&1
fi
