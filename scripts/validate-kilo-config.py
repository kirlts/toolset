#!/usr/bin/env python3
"""Validate kilo.jsonc and check env var references."""
import json, re, sys

text = open(sys.argv[1]).read()
# Strip JSONC comments (respecting strings)
# Remove single-line comments only outside quoted strings
text = re.sub(r'(?s)("(?:[^"\\]|\\.)*")|//.*', lambda m: m.group(1) or '', text)
cfg = json.loads(text)

refs = set()
for p in cfg.get('provider', {}).values():
    ak = p.get('options', {}).get('apiKey', '')
    if isinstance(ak, str) and ak.startswith('{env:'):
        refs.add(ak[5:-1])
for m in cfg.get('mcp', {}).values():
    hdrs = m.get('headers', {})
    for v in hdrs.values():
        if isinstance(v, str) and v.startswith('{env:'):
            refs.add(v[5:-1])

print(f'kilo.jsonc OK — env refs: {refs}')
