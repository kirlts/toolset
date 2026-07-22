#!/usr/bin/env python3
"""
Daily sync of ALL Hindsight banks — Phase 1: Export
list_memories with pagination → save as JSON
"""
import json, urllib.request, os, time
from datetime import datetime, timezone

MCP_URL = "https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/mcp/"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
BASE_DIR = "/home/opc/workspace/toolset/infrastructure/hermes/banks"

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

def list_all_memories(bank_id, limit=1000):
    all_memories = []
    offset = 0
    while True:
        result = mcp_call("list_memories", {"bank_id": bank_id, "limit": limit, "offset": offset})
        if isinstance(result, dict):
            items = result.get("items", [])
        elif isinstance(result, list):
            items = result
        else:
            items = []
        if not items:
            break
        all_memories.extend(items)
        if len(items) < limit:
            break
        offset += limit
        print(f"    [{bank_id}] {len(all_memories)} facts...")
    return all_memories

def save_json(bank_id, memories):
    dir_path = os.path.join(BASE_DIR, bank_id)
    os.makedirs(dir_path, exist_ok=True)
    filepath = os.path.join(dir_path, f"{TODAY}.json")
    with open(filepath, "w") as f:
        json.dump(memories, f, indent=2, ensure_ascii=False, default=str)
    print(f"    Saved {len(memories)} facts → {filepath}")
    return filepath

def main():
    print(f"=== PHASE 1: Export — {TODAY} ===\n")
    r = mcp_call("list_banks")
    banks = [b for b in r.get("banks", []) if b["bank_id"] != "default"]
    print(f"Banks: {len(banks)}\n")

    results = {}
    for i, bank in enumerate(banks, 1):
        bid = bank["bank_id"]
        print(f"[{i}/{len(banks)}] {bid} ({bank.get('fact_count', '?')} facts)")
        memories = list_all_memories(bid)
        fp = save_json(bid, memories)
        results[bid] = {"exported": len(memories), "file": fp}
        print()

    manifest = {"date": TODAY, "phase": "export", "banks": results,
                "timestamp": datetime.now(timezone.utc).isoformat()}
    mp = os.path.join(BASE_DIR, f"export-manifest-{TODAY}.json")
    with open(mp, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, default=str)
    print(f"Manifest: {mp}")
    print(json.dumps(manifest, ensure_ascii=False, default=str))

if __name__ == "__main__":
    main()
