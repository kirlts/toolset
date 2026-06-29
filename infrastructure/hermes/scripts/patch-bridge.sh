#!/usr/bin/env bash
# patch-bridge.sh — Extiende bridge.js para:
#   1. Exponer metadata.desc desde Baileys groupMetadata (parche existente)
#   2. Inyectar bloque [ROUTING] en mensajes de grupos con perfil configurado
# Llamado por deploy.sh. Idempotente (detecta si ya está parcheado).
set -euo pipefail

BRIDGE_JS="${BRIDGE_JS:-/usr/local/lib/hermes-agent/scripts/whatsapp-bridge/bridge.js}"

if [ ! -f "$BRIDGE_JS" ]; then
  echo "[patch-bridge] bridge.js not found at $BRIDGE_JS — skipping"
  exit 0
fi

# --- PATCH 1: Expose metadata.desc (existing) ---
if ! grep -q "metadata.desc" "$BRIDGE_JS" 2>/dev/null; then
  sudo python3 << 'PYEOF'
path = "/usr/local/lib/hermes-agent/scripts/whatsapp-bridge/bridge.js"
with open(path) as f:
    content = f.read()

old = """      return res.json({
        name: metadata.subject,
        isGroup: true,
        participants: metadata.participants.map(p => p.id),
      });"""

new = """      return res.json({
        name: metadata.subject,
        desc: metadata.desc || "",
        isGroup: true,
        participants: metadata.participants.map(p => p.id),
      });"""

if old in content:
    content = content.replace(old, new)
    with open(path, "w") as f:
        f.write(content)
    print("[patch-bridge] Applied — desc field added")
else:
    print("[patch-bridge] Pattern changed — may need manual review")
PYEOF
else
  echo "[patch-bridge] Patch 1 (desc) already applied"
fi

# --- PATCH 2: Inject full profile SOUL.md into body BEFORE event construction ---
# Modifies the `body` variable (before const event = {}) instead of event.body (after).
# Tested locally: syntax check + 4 scenarios verified.
if ! grep -q "PROFILE ACTIVATION" "$BRIDGE_JS" 2>/dev/null; then
  sudo python3 << 'PYEOF'
path = "/usr/local/lib/hermes-agent/scripts/whatsapp-bridge/bridge.js"
with open(path) as f:
    content = f.read()

# Step 1: Remove any old injection block (from earlier patch versions)
# Pattern matches the old code that modified event.body after construction
old_blocks = [
    # Old [ROUTING] metadata pattern (first version)
    (
        '      // === ROUTING INJECTION ===\n'
        '      if (isGroup) {\n'
        '        try {\n'
        '          const groupsRaw = fs.readFileSync(\n'
        "            process.env.HOME + '/.hermes/whatsapp-groups.yaml', 'utf8');\n"
        "          const jidIdx = groupsRaw.indexOf('\"' + chatId + '\"');\n"
        '          if (jidIdx !== -1) {\n'
        "            const block = groupsRaw.substring(jidIdx, jidIdx + 500);\n"
        '            const pm = block.match(/profile:\\s*"(\\w+)"/);\n'
        '            if (pm) {\n'
        '              const sm = block.match(/scope:\\s*"(\\w+)"/);\n'
        "              const sp = sm ? '\\nscope=' + sm[1] : '';\n"
        "              event.body = '[ROUTING]\\nprofile=' + pm[1] + sp + '\\n[/ROUTING]\\n\\n' + event.body;\n"
        '            }\n'
        '          }\n'
        "        } catch(e) {\n"
        "          console.error('[routing]', e.message);\n"
        '        }\n'
        '      }'
    ),
    # Old PROFILE ACTIVATION pattern (second version, event.body after construction)
    (
        '      // === ROUTING INJECTION ===\n'
        '      if (isGroup) {\n'
        '        try {\n'
        '          const groupsRaw = fs.readFileSync(\n'
        "            process.env.HOME + '/.hermes/whatsapp-groups.yaml', 'utf8');\n"
        "          const jidIdx = groupsRaw.indexOf('\"' + chatId + '\"');\n"
        '          if (jidIdx !== -1) {\n'
        "            const block = groupsRaw.substring(jidIdx, jidIdx + 500);\n"
        '            const pm = block.match(/profile:\\s*"(\\w+)"/);\n'
        '            if (pm) {\n'
        '              const profileName = pm[1];\n'
        '              const profilePath = process.env.HOME +\n'
        "                '/.hermes/profiles/' + profileName + '/SOUL.md';\n"
        '              let profileContent = \'\';\n'
        '              try {\n'
        "                profileContent = fs.readFileSync(profilePath, 'utf8').trim();\n"
        '              } catch(e) {\n'
        '                console.error(\'[routing] no profile SOUL.md for \' + profileName, e.message);\n'
        '              }\n'
        '              if (profileContent) {\n'
        "                event.body = '=== PROFILE ACTIVATION: ' + profileName + ' ===\\n' +\n"
        '                  profileContent +\n'
        "                  '\\n=== END PROFILE ===\\n\\n' + event.body;\n"
        '              }\n'
        '            }\n'
        '          }\n'
        "        } catch(e) {\n"
        "          console.error('[routing]', e.message);\n"
        '        }\n'
        '      }'
    ),
]

for old_block in old_blocks:
    if old_block in content:
        content = content.replace(old_block, "")
        print("[patch-bridge] Removed old injection block")
        break

# Step 2: Inject new routing code BEFORE const event = {
# Modifies the `body` VARIABLE (before const event = {}) not event.body (after).
# This eliminates the scoping issue with event object property modification.
new_block = (
    "      // === ROUTING INJECTION ===\n"
    "      if (isGroup) {\n"
    "        try {\n"
    "          const groupsRaw = fs.readFileSync(\n"
    "            process.env.HOME + '/.hermes/whatsapp-groups.yaml', 'utf8');\n"
    "          const jidIdx = groupsRaw.indexOf('\"' + chatId + '\"');\n"
    "          if (jidIdx !== -1) {\n"
    "            const block = groupsRaw.substring(jidIdx, jidIdx + 500);\n"
    "            const pm = block.match(/profile:\\s*\"(\\w+)\"/);\n"
    "            if (pm) {\n"
    "              const profileName = pm[1];\n"
    "              const profilePath = process.env.HOME +\n"
    "                '/.hermes/profiles/' + profileName + '/SOUL.md';\n"
    "              let profileContent = '';\n"
    "              try {\n"
    "                profileContent = fs.readFileSync(profilePath, 'utf8').trim();\n"
    "              } catch(e) {}\n"
    "              if (profileContent) {\n"
    "                body = '=== PROFILE ACTIVATION: ' + profileName + ' ===\\n' +\n"
    "                  profileContent +\n"
    "                  '\\n=== END PROFILE ===\\n\\n' + body;\n"
    "              }\n"
    "            }\n"
    "          }\n"
    "        } catch(e) {\n"
    "          console.error('[routing]', e.message);\n"
    "        }\n"
    "      }\n"
)

event_idx = content.find("\n      const event = {")
if event_idx < 0:
    print("[patch-bridge] ERROR: could not find const event = {")
    print("[patch-bridge] Bridge.js may have been updated")
else:
    # Insert new_block before const event
    # event_idx points to the \n right before "      const event = {"
    content = content[:event_idx + 1] + new_block + content[event_idx + 1:]

    with open(path, "w") as f:
        f.write(content)
    print("[patch-bridge] Applied — profile SOUL.md injection added before event construction")
PYEOF
else
  echo "[patch-bridge] Patch 2 (profile SOUL.md injection) already applied"
fi