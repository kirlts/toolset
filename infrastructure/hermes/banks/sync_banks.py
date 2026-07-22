#!/usr/bin/env python3
"""
Daily sync of ALL Hindsight banks.

1. list_banks() → discover banks
2. For each bank (except default): list_memories with pagination → save as JSON
3. For each bank: reflect + retain daily summary
4. Git commit + push
"""

import json
import urllib.request
import os
import sys
import time
from datetime import datetime, timezone

MCP_URL = "https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/mcp/"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
BASE_DIR = "/home/opc/workspace/toolset/infrastructure/hermes/banks"

def mcp_call(method, params=None):
    """Call an MCP tool and return the result."""
    if params is None:
        params = {}
    payload = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000) % 1000000,
        "method": "tools/call",
        "params": {"name": method, "arguments": params}
    }
    req = urllib.request.Request(
        MCP_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        raw = resp.read().decode()
        # Parse SSE response — extract data after "data: "
        for line in raw.split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if "result" in data:
                    # Extract the text content from the MCP result
                    content = data["result"].get("content", [])
                    for item in content:
                        if item.get("type") == "text":
                            return json.loads(item["text"])
                    # Fallback: structuredContent
                    struct = data["result"].get("structuredContent", {})
                    return struct.get("result", data["result"])
        return {"error": "No result in response", "raw": raw[:500]}
    except Exception as e:
        return {"error": str(e)}


def list_all_banks():
    """Get all banks, excluding 'default'."""
    result = mcp_call("list_banks")
    banks = result.get("banks", [])
    return [b for b in banks if b["bank_id"] != "default"]


def list_all_memories(bank_id, limit=1000):
    """Get ALL memories for a bank, with pagination."""
    all_memories = []
    offset = 0
    while True:
        result = mcp_call("list_memories", {
            "bank_id": bank_id,
            "limit": limit,
            "offset": offset
        })
        # Response format: {"items": [...]} or {"total": N, "items": [...]}
        if isinstance(result, dict):
            memories = result.get("items", [])
        elif isinstance(result, list):
            memories = result
        else:
            memories = []

        if not memories:
            break

        all_memories.extend(memories)
        if len(memories) < limit:
            break

        offset += limit
        print(f"    [{bank_id}] Fetched {len(all_memories)} facts so far...")

    return all_memories


def reflect_bank(bank_id):
    """Run reflect on a bank for the daily summary."""
    result = mcp_call("reflect", {
        "bank_id": bank_id,
        "query": "Sintetiza las interacciones, decisiones, aprendizajes y cambios de las últimas 24 horas relacionados con este proyecto. ¿Qué se hizo? ¿Qué se aprendió? ¿Qué decisiones se tomaron?",
        "budget": "mid",
        "max_tokens": 4096
    })
    return result


def retain_bank(bank_id, content):
    """Store the daily summary back into the bank."""
    tags = ["daily-summary", TODAY, bank_id]
    result = mcp_call("retain", {
        "bank_id": bank_id,
        "content": content,
        "tags": tags
    })
    return result


def save_json(bank_id, memories):
    """Save memories as JSON to the bank's directory."""
    dir_path = os.path.join(BASE_DIR, bank_id)
    os.makedirs(dir_path, exist_ok=True)
    filepath = os.path.join(dir_path, f"{TODAY}.json")
    with open(filepath, "w") as f:
        json.dump(memories, f, indent=2, ensure_ascii=False, default=str)
    print(f"    Saved {len(memories)} facts to {filepath}")
    return filepath


def main():
    print(f"=== Hindsight Bank Sync — {TODAY} ===\n")

    # Step 1: Discover all banks
    print("Step 1: Discovering banks...")
    banks = list_all_banks()
    print(f"Found {len(banks)} banks (excluding default):")
    for b in banks:
        print(f"  - {b['bank_id']} ({b.get('fact_count', '?')} facts)")
    print()

    # Step 2 & 3: Process each bank sequentially
    results = {}
    for i, bank in enumerate(banks, 1):
        bank_id = bank["bank_id"]
        fact_count = bank.get("fact_count", 0)
        print(f"[{i}/{len(banks)}] Processing: {bank_id} ({fact_count} facts)")

        # Step 2: Export all memories
        print(f"  Exporting memories...")
        memories = list_all_memories(bank_id)
        filepath = save_json(bank_id, memories)
        results[bank_id] = {
            "exported_facts": len(memories),
            "file": filepath
        }

        # Step 3: Reflect + Retain
        print(f"  Reflecting...")
        reflect_result = reflect_bank(bank_id)
        if isinstance(reflect_result, dict) and "error" in reflect_result:
            print(f"  Reflect error: {reflect_result['error']}")
            results[bank_id]["reflect"] = f"ERROR: {reflect_result['error']}"
            results[bank_id]["retain"] = "skipped"
        else:
            # Extract the reflection text
            reflect_text = ""
            if isinstance(reflect_result, dict):
                reflect_text = reflect_result.get("result", str(reflect_result))
            else:
                reflect_text = str(reflect_result)

            # Truncate if too long for retain
            if len(reflect_text) > 5000:
                reflect_text = reflect_text[:5000] + "\n\n[truncated]"

            print(f"  Retaining daily summary...")
            retain_result = retain_bank(bank_id, reflect_text)
            results[bank_id]["reflect"] = "ok"
            results[bank_id]["retain"] = "ok" if not (isinstance(retain_result, dict) and "error" in retain_result) else f"ERROR: {retain_result['error']}"

        print()

    # Summary
    print(f"=== Sync Complete ===")
    for bank_id, r in results.items():
        status = "✓" if r.get("retain") == "ok" else "⚠"
        print(f"  {status} {bank_id}: {r.get('exported_facts', 0)} facts → {r.get('file', '?')}")
    print()

    # Write a manifest file with the results
    manifest = {
        "date": TODAY,
        "banks_processed": len(results),
        "results": results,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    manifest_path = os.path.join(BASE_DIR, f"sync-manifest-{TODAY}.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, default=str)
    print(f"Manifest written to {manifest_path}")

    # Output results as JSON for the calling script
    print(f"\n---RESULTS_JSON---")
    print(json.dumps(manifest, ensure_ascii=False, default=str))
    print(f"---END_RESULTS_JSON---")


if __name__ == "__main__":
    main()
