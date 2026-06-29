#!/usr/bin/env bash
# populate-channel-aliases.sh
# Consulta el bridge de WhatsApp para obtener nombres humanos y descripciones
# de grupos, y escribe channel_aliases.json para resolucion JID -> {name, desc}.
# Si la descripcion del bridge esta vacia, fallback a whatsapp-groups.yaml.
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
import json, subprocess as sp, os

BRIDGE = '$BRIDGE'
DIRECTORY = '$DIRECTORY'
ALIASES = '$ALIASES'
WHATSAPP_GROUPS_YAML = os.path.expanduser('~/.hermes/whatsapp-groups.yaml')

with open(DIRECTORY) as f:
    dir_data = json.load(f)

# Load YAML descriptions as fallback for empty WhatsApp descriptions
yaml_descs = {}
if os.path.exists(WHATSAPP_GROUPS_YAML):
    try:
        import yaml
        with open(WHATSAPP_GROUPS_YAML) as f:
            yaml_data = yaml.safe_load(f)
        groups = yaml_data.get('groups', {})
        for jid, info in groups.items():
            desc = info.get('description', '') if isinstance(info, dict) else ''
            if desc:
                yaml_descs[jid] = desc
    except ImportError:
        pass
    except Exception:
        pass

existing = {}
if os.path.exists(ALIASES):
    with open(ALIASES) as f:
        existing = json.load(f).get('whatsapp', {})

result = {}
for ch in dir_data.get('platforms', {}).get('whatsapp', []):
    jid = ch['id']
    if not jid.endswith('@g.us'):
        continue
    try:
        r = sp.run(['curl', '-s', '--max-time', '5', '{}/chat/{}'.format(BRIDGE, jid)],
                   capture_output=True, text=True, timeout=5)
        data = json.loads(r.stdout)
        bridge_desc = data.get('desc', '').strip()
        # Fallback: if bridge returns empty desc, use YAML description
        if not bridge_desc and jid in yaml_descs:
            bridge_desc = yaml_descs[jid]
        entry = {
            'name': data.get('name', jid.split('@')[0]),
            'desc': bridge_desc
        }
    except Exception:
        entry = {
            'name': jid.split('@')[0],
            'desc': yaml_descs.get(jid, '')
        }
    prev = existing.get(jid, {})
    prev_name = prev.get('name', '') if isinstance(prev, dict) else prev
    new_name = entry['name']
    result[jid] = entry
    if prev_name != new_name:
        label = 'Updated' if prev else 'Added'
        print('{}: {} -> {}'.format(label, jid, new_name))

with open(ALIASES, 'w') as f:
    json.dump({'whatsapp': result}, f, indent=2, ensure_ascii=False)
print('Done: {} WhatsApp group aliases'.format(len(result)))
PYEOF
