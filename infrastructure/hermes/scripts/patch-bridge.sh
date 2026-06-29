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

# --- PATCH 2: Inject full profile SOUL.md for groups with profile ---
if ! grep -q "PROFILE ACTIVATION" "$BRIDGE_JS" 2>/dev/null; then
  sudo python3 << 'PYEOF'
path = "/usr/local/lib/hermes-agent/scripts/whatsapp-bridge/bridge.js"
with open(path) as f:
    content = f.read()

old = """      // === ROUTING INJECTION ===
      if (isGroup) {
        try {
          const groupsRaw = fs.readFileSync(
            process.env.HOME + '/.hermes/whatsapp-groups.yaml', 'utf8');
          const jidIdx = groupsRaw.indexOf('"' + chatId + '"');
          if (jidIdx !== -1) {
            const block = groupsRaw.substring(jidIdx, jidIdx + 500);
            const pm = block.match(/profile:\\s*"(\\w+)"/);
            if (pm) {
              const sm = block.match(/scope:\\s*"(\\w+)"/);
              const sp = sm ? '\\nscope=' + sm[1] : '';
              event.body = '[ROUTING]\\nprofile=' + pm[1] + sp + '\\n[/ROUTING]\\n\\n' + event.body;
            }
          }
        } catch(e) {
          console.error('[routing]', e.message);
        }
      }"""

new = """      // === ROUTING INJECTION ===
      if (isGroup) {
        try {
          const groupsRaw = fs.readFileSync(
            process.env.HOME + '/.hermes/whatsapp-groups.yaml', 'utf8');
          const jidIdx = groupsRaw.indexOf('"' + chatId + '"');
          if (jidIdx !== -1) {
            const block = groupsRaw.substring(jidIdx, jidIdx + 500);
            const pm = block.match(/profile:\\s*"(\\w+)"/);
            if (pm) {
              const profileName = pm[1];
              const profilePath = process.env.HOME +
                '/.hermes/profiles/' + profileName + '/SOUL.md';
              let profileContent = '';
              try {
                profileContent = fs.readFileSync(profilePath, 'utf8').trim();
              } catch(e) {
                console.error('[routing] no profile SOUL.md for ' + profileName, e.message);
              }
              if (profileContent) {
                event.body = '=== PROFILE ACTIVATION: ' + profileName + ' ===\\n' +
                  profileContent +
                  '\\n=== END PROFILE ===\\n\\n' + event.body;
              }
            }
          }
        } catch(e) {
          console.error('[routing]', e.message);
        }
      }"""

if old in content:
    content = content.replace(old, new)
    with open(path, "w") as f:
        f.write(content)
    print("[patch-bridge] Applied — profile SOUL.md injection added")
else:
    print("[patch-bridge] WARNING: could not find old routing pattern")
    print("[patch-bridge] Checking if already applied...")
    if "PROFILE ACTIVATION" in content:
        print("[patch-bridge] Already applied (PROFILE ACTIVATION found)")
    else:
        print("[patch-bridge] Pattern changed — manual review required")
PYEOF
else
  echo "[patch-bridge] Patch 2 (profile SOUL.md injection) already applied"
fi