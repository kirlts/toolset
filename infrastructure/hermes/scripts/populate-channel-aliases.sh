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

# --- Cleanup orphaned groups from whatsapp-groups.yaml ---
# Groups that exist in YAML but NOT in the bridge directory have been left/removed.
# Remove them from the runtime YAML so Hermes stops trying to inject those profiles.
if os.path.exists(WHATSAPP_GROUPS_YAML):
    try:
        import yaml
        with open(WHATSAPP_GROUPS_YAML) as f:
            yaml_data = yaml.safe_load(f)
        yaml_groups = yaml_data.get('groups', {})
        active_jids = set(result.keys())

        orphaned = {}
        kept = {}
        for jid, info in yaml_groups.items():
            if jid in active_jids:
                kept[jid] = info
            else:
                orphaned[jid] = info

        if orphaned:
            yaml_data['groups'] = kept
            with open(WHATSAPP_GROUPS_YAML, 'w') as f:
                yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            for jid, info in orphaned.items():
                name = info.get('name', jid) if isinstance(info, dict) else info
                print('REMOVED orphan: {} ({})'.format(jid, name))

            # Write event for Hermes to sync the change to the repo
            events_dir = '/tmp/hermes-buffer-events'
            os.makedirs(events_dir, exist_ok=True)
            event_file = os.path.join(events_dir, 'whatsapp_groups_cleanup_{}.json'.format(
                __import__('datetime').datetime.now().strftime('%Y%m%d%H%M%S')))
            with open(event_file, 'w') as f:
                json.dump({
                    'event': 'whatsapp_groups_cleanup',
                    'orphaned': {jid: (info.get('name', jid) if isinstance(info, dict) else str(info))
                                 for jid, info in orphaned.items()},
                    'timestamp': __import__('datetime').datetime.now().isoformat(),
                    'action_required': 'sync_to_repo'
                }, f)
    except ImportError:
        pass
    except Exception as e:
        print('Cleanup skipped: {}'.format(e))
PYEOF
