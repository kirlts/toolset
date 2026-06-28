#!/usr/bin/env bash
# patch-bridge.sh — Extiende bridge.js para exponer metadata.desc desde Baileys groupMetadata
# Llamado por deploy.sh. Idempotente (detecta si ya está parcheado).
set -euo pipefail

BRIDGE_JS="${BRIDGE_JS:-/usr/local/lib/hermes-agent/scripts/whatsapp-bridge/bridge.js}"

if [ ! -f "$BRIDGE_JS" ]; then
  echo "[patch-bridge] bridge.js not found at $BRIDGE_JS — skipping"
  exit 0
fi

if grep -q "metadata.desc" "$BRIDGE_JS" 2>/dev/null; then
  echo "[patch-bridge] Already patched"
  exit 0
fi

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