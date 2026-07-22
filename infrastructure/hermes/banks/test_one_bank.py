#!/usr/bin/env python3
"""Test: export memories from hermes bank and reflect+retain."""
import json, urllib.request, sys, time

MCP_URL = "https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/mcp/"

def mcp_call(method, params=None):
    if params is None: params = {}
    payload = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000000) % 999999,
        "method": "tools/call",
        "params": {"name": method, "arguments": params}
    }
    req = urllib.request.Request(
        MCP_URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req, timeout=120).read().decode()
    for line in resp.split("\n"):
        if line.startswith("data: "):
            data = json.loads(line[6:])
            if "result" in data:
                content = data["result"].get("content", [])
                for item in content:
                    if item.get("type") == "text":
                        return json.loads(item["text"])
                struct = data["result"].get("structuredContent", {})
                r = struct.get("result", data["result"])
                if isinstance(r, str): return json.loads(r)
                return r
    return {"error": "No result"}

# Test 1: list_memories
print("=== Test: list_memories(hermes, limit=5) ===")
r = mcp_call("list_memories", {"bank_id": "hermes", "limit": 5})
print(f"Type: {type(r).__name__}")
if isinstance(r, dict):
    print(f"Keys: {list(r.keys())}")
    items = r.get("items", [])
    print(f"Items count: {len(items)}")
    if items:
        print(f"First item keys: {list(items[0].keys())}")
        print(f"First text: {items[0].get('text', 'N/A')[:100]}")
else:
    print(f"Raw: {str(r)[:300]}")

# Test 2: list_memories with pagination
print("\n=== Test: list_memories(hermes, limit=1000, offset=0) ===")
r2 = mcp_call("list_memories", {"bank_id": "hermes", "limit": 1000, "offset": 0})
if isinstance(r2, dict):
    items2 = r2.get("items", [])
    print(f"Items: {len(items2)}")
    total = r2.get("total", "?")
    print(f"Total (from API): {total}")
else:
    print(f"Unexpected type: {type(r2).__name__}")

# Test 3: reflect
print("\n=== Test: reflect(hermes) ===")
r3 = mcp_call("reflect", {
    "bank_id": "hermes",
    "query": "Sintetiza las interacciones, decisiones, aprendizajes y cambios de las últimas 24 horas relacionados con este proyecto. ¿Qué se hizo? ¿Qué se aprendió? ¿Qué decisiones se tomaron?",
    "budget": "mid",
    "max_tokens": 4096
})
print(f"Reflect type: {type(r3).__name__}")
if isinstance(r3, dict):
    reflect_text = r3.get("result", "")
    print(f"Result length: {len(reflect_text)}")
    print(f"Preview: {reflect_text[:200]}")
else:
    print(f"Raw: {str(r3)[:300]}")

# Test 4: retain
print("\n=== Test: retain(hermes) ===")
r4 = mcp_call("retain", {
    "bank_id": "hermes",
    "content": f"Test daily summary for {time.strftime('%Y-%m-%d')}",
    "tags": ["daily-summary", time.strftime("%Y-%m-%d"), "hermes"]
})
print(f"Retain result: {str(r4)[:200]}")

print("\n=== All tests done ===")
