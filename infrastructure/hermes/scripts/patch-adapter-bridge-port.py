#!/usr/bin/env python3
"""Apply bridge port fix to Hermes adapter.py so tenant profiles get unique ports."""
import os, sys

ADAPTER_PATH = "/usr/local/lib/hermes-agent/plugins/platforms/whatsapp/adapter.py"

with open(ADAPTER_PATH) as f:
    code = f.read()

# Replace hardcoded port with env var + config fallback
OLD = 'self._bridge_port: int = config.extra.get("bridge_port", 3000)'
NEW = '''_bp = int(os.environ.get("WHATSAPP_BRIDGE_PORT", "0"))
        if not _bp:
            _bp = int(config.extra.get("bridge_port") or 3000)
        self._bridge_port: int = _bp'''

if OLD in code:
    code = code.replace(OLD, NEW)
    with open(ADAPTER_PATH, "w") as f:
        f.write(code)
    print("✓ adapter.py patched: bridge_port now reads WHATSAPP_BRIDGE_PORT env var")
elif NEW in code:
    print("✓ adapter.py already patched")
else:
    print("✗ Could not find expected line in adapter.py — patch skipped")
    sys.exit(1)
