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

# --- PATCH 2: Inject [ROUTING] block for groups with profile ---
if ! grep -q "ROUTING INJECTION" "$BRIDGE_JS" 2>/dev/null; then
  sudo python3 << 'PYEOF'
path = "/usr/local/lib/hermes-agent/scripts/whatsapp-bridge/bridge.js"
with open(path) as f:
    content = f.read()

old = """      messageQueue.push(event);"""

new = """      // === ROUTING INJECTION ===
      if (isGroup) {
        try {
          const groupsRaw = fs.readFileSync(
            process.env.HOME + '/.hermes/whatsapp-groups.yaml', 'utf8');
          const jidIdx = groupsRaw.indexOf('"' + chatId + '"');
          if (jidIdx !== -1) {
            const block = groupsRaw.substring(jidIdx, jidIdx + 500);
            const pm = block.match(/profile:\s*"(\\w+)"/);
            if (pm) {
              const sm = block.match(/scope:\s*"(\\w+)"/);
              const sp = sm ? '\\nscope=' + sm[1] : '';
              event.body = '[ROUTING]\\nprofile=' + pm[1] + sp + '\\n[/ROUTING]\\n\\n' + event.body;
            }
          }
        } catch(e) {
          console.error('[routing]', e.message);
        }
      }
      messageQueue.push(event);"""

if old in content:
    content = content.replace(old, new)
    with open(path, "w") as f:
        f.write(content)
    print("[patch-bridge] Applied — [ROUTING] injection added")
else:
    print("[patch-bridge] WARNING: could not find push pattern for [ROUTING] patch")
    print("[patch-bridge] Bridge may have been updated — manual review required")
PYEOF
else
  echo "[patch-bridge] Patch 2 ([ROUTING]) already applied"
fi