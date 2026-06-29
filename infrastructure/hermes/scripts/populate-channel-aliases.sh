#!/usr/bin/env bash
# populate-channel-aliases.sh
# Consulta el bridge de WhatsApp para obtener nombres humanos y descripciones
# de grupos, y escribe channel_aliases.json para resolucion JID → {name, desc}.
#
# Corre en cada deploy y via cron cada 10 minutos.
set -euo pipefail

BRIDGE="http://127.0.0.1:3000"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
DIRECTORY="$HERMES_HOME/channel_directory.json"
ALIASES="$HERMES_HOME/channel_aliases.json"

if [ ! -f "$DIRECTORY" ]; then
  echo "channel_directory.json not found at $DIRECTORY"
  exit 0
fi

python3 << PYEOF
import json, subprocess as sp

BRIDGE = '$BRIDGE'
DIRECTORY = '$DIRECTORY'
ALIASES = '$ALIASES'

with open(DIRECTORY) as f:
    dir_data = json.load(f)

existing = {}
if __import__('os').path.exists(ALIASES):
    with open(ALIASES) as f:
        existing = json.load(f).get('whatsapp', {})

result = {}
for ch in dir_data.get('platforms', {}).get('whatsapp', []):
    jid = ch['id']
    if not jid.endswith('@g.us'):
        continue
    try:
        r = sp.run(['curl', '-s', '--max-time', '5', f'{BRIDGE}/chat/{jid}'],
                   capture_output=True, text=True, timeout=5)
        data = json.loads(r.stdout)
        entry = {
            'name': data.get('name', jid.split('@')[0]),
            'desc': data.get('desc', '')
        }
    except Exception:
        entry = {
            'name': jid.split('@')[0],
            'desc': ''
        }
    prev = existing.get(jid, {})
    prev_name = prev.get('name', '') if isinstance(prev, dict) else prev
    new_name = entry['name']
    result[jid] = entry
    if prev_name != new_name:
        label = 'Updated' if prev else 'Added'
        print(f'{label}: {jid} -> {new_name}')

with open(ALIASES, 'w') as f:
    json.dump({'whatsapp': result}, f, indent=2, ensure_ascii=False)
print(f'Done: {len(result)} WhatsApp group aliases')
PYEOF
