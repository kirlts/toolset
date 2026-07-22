#!/usr/bin/env python3
"""
Daily sync — Phase 2: Reflect + Retain for each bank.
Processes banks in chunks to avoid timeout.
"""
import json, urllib.request, os, sys, time
from datetime import datetime, timezone

MCP_URL = "https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/mcp/"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
STATE_FILE = "/home/opc/workspace/toolset/infrastructure/hermes/banks/reflect-progress.json"

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
    resp = urllib.request.urlopen(req, timeout=180).read().decode()
    for line in resp.split("\n"):
        if line.startswith("data: "):
            data = json.loads(line[6:])
            if "result" in data:
                content = data["result"].get("content", [])
                for item in content:
                    if item.get("type") == "text":
                        parsed = json.loads(item["text"])
                        return parsed
                struct = data["result"].get("structuredContent", {})
                r = struct.get("result", data["result"])
                if isinstance(r, str): return json.loads(r)
                return r
    return {"error": "No result"}

def process_bank(bank_id):
    """Run reflect + retain for a single bank."""
    print(f"\n[{bank_id}] Reflecting...")
    
    # reflect
    reflect_result = mcp_call("reflect", {
        "bank_id": bank_id,
        "query": "Sintetiza las interacciones, decisiones, aprendizajes y cambios de las últimas 24 horas relacionados con este proyecto. ¿Qué se hizo? ¿Qué se aprendió? ¿Qué decisiones se tomaron?",
        "budget": "mid",
        "max_tokens": 4096
    })
    
    if isinstance(reflect_result, dict) and "error" in reflect_result:
        print(f"  ✗ Reflect error: {reflect_result['error']}")
        return {"reflect": "error", "retain": "skipped"}
    
    # Extract the reflection text
    if isinstance(reflect_result, dict):
        text = reflect_result.get("text", "") or reflect_result.get("result", "") or str(reflect_result)
    else:
        text = str(reflect_result)
    
    if not text or len(text) < 10:
        print(f"  ⚠ Empty reflect result. Raw: {str(reflect_result)[:200]}")
        return {"reflect": "empty", "retain": "skipped"}
    
    # Truncate if too long
    summary = text[:5000] if len(text) > 5000 else text
    print(f"  Reflect OK ({len(text)} chars). Retaining...")
    
    # retain
    retain_result = mcp_call("retain", {
        "bank_id": bank_id,
        "content": summary,
        "tags": ["daily-summary", TODAY, bank_id]
    })
    
    if isinstance(retain_result, dict) and retain_result.get("status") == "accepted":
        print(f"  ✓ Retain OK (op: {retain_result.get('operation_id', '?')})")
        return {"reflect": "ok", "retain": "ok"}
    else:
        print(f"  ? Retain: {str(retain_result)[:200]}")
        return {"reflect": "ok", "retain": str(retain_result)[:100]}

def load_progress():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"banks": {}, "completed": []}

def save_progress(progress):
    progress["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)

def main():
    # Get bank list
    r = mcp_call("list_banks")
    banks = [b["bank_id"] for b in r.get("banks", []) if b["bank_id"] != "default"]
    
    # Load progress
    progress = load_progress()
    if progress.get("date") != TODAY:
        progress = {"date": TODAY, "banks": {}, "completed": []}
    
    completed = set(progress.get("completed", []))
    remaining = [b for b in banks if b not in completed]
    
    print(f"=== PHASE 2: Reflect + Retain — {TODAY} ===")
    print(f"Total banks: {len(banks)}")
    print(f"Completed: {len(completed)}")
    print(f"Remaining: {len(remaining)}")
    print(f"Banks remaining: {remaining}")
    
    if not remaining:
        print("\nAll done!")
        return
    
    # Process one bank at a time
    for bid in remaining:
        result = process_bank(bid)
        progress["banks"][bid] = result
        if result.get("retain") in ("ok", "skipped"):
            progress["completed"].append(bid)
        save_progress(progress)
    
    print(f"\n=== Phase 2 Progress ===")
    for bid, r in progress["banks"].items():
        icon = "✓" if r.get("retain") == "ok" else "⚠" if r.get("retain") == "skipped" else "✗"
        print(f"  {icon} {bid}: reflect={r.get('reflect','?')} retain={r.get('retain','?')}")
    
    print(f"\nCompleted: {len(progress['completed'])}/{len(banks)}")

if __name__ == "__main__":
    main()
