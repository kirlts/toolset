# Bank Sync Execution Procedure

Used by the `hermes-sync-banks` cron job (02:00 UTC daily). This doc captures the step-by-step procedure and known pitfalls.

## Pre-flight

### Memory cycle at cron start

Even for cron jobs, the Memory Cycle rules apply — though no user is present:

```json
mcp_hindsight_selfhosted_recall(bank="hermes", max_tokens=16384, budget="high")
```

This loads the last session's retain context so the sync knows what "last known state" was. It's useful for detecting unexpected state changes between runs. Do NOT retain at cron start (nothing new to record); retain replaces the state at the end.

### Directory creation

Dirs are created on-demand by the export script or manually:

```bash
mkdir -p /home/opc/workspace/toolset/infrastructure/hermes/banks/{<all-known-bank-ids>}
```

Banks discovered at runtime via `list_banks()`. Create dirs as they appear.

## Step 1: Discover banks

Call `mcp_hindsight_selfhosted_list_banks()`. Filter out `"default"` (legacy internal bank — never include it).

**Live check**: Bank counts change over time. Re-run `list_banks()` each sync for the actual `fact_count` field, not any static table.

**Edge case — empty bank**: Some banks have ~2 facts (created by onboarding, no content yet). Run reflect+retain on them anyway; the reflect will report "no activity". Do not skip — the retain creates the daily-summary tag chain.

## Step 2: Export each bank as JSON

For each bank (process SEQUENTIALLY per bank — reflect+retain are stateful; but `list_memories` calls across different banks ARE independent reads and CAN be batched into parallel MCP calls to save wall-clock time):

### Method A (RECOMMENDED): Direct MCP JSON-RPC via curl

Call the hindsight MCP endpoint directly using JSON-RPC over HTTP SSE. This is more reliable than extracting from MCP tool output because it avoids temp-file hunting and double-encoded JSON issues.

The endpoint is at the URL configured in `~/.hermes/config.yaml` under `memory.hindsight.url`:
```
https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/mcp/
```

The response is SSE-streamed (`event: message\r\ndata: {...}`). Parse the `data:` line for the result.

#### Python export script

Create `/tmp/export_bank.py` on each run (it's ephemeral — recreate if missing):

```python
#!/usr/bin/env python3
"""Export all memories from a hindsight bank to a JSON file via MCP JSON-RPC."""
import json, sys, os, urllib.request, urllib.error

MCP_URL = "https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/mcp/"

def call_mcp(method, params):
    payload = json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call",
                          "params":{"name":method,"arguments":params}})
    req = urllib.request.Request(MCP_URL, data=payload.encode(),
                                  headers={"Content-Type":"application/json"},
                                  method="POST")
    resp = urllib.request.urlopen(req, timeout=120).read().decode()
    for line in resp.split("\n"):
        if line.startswith("data: "):
            data = json.loads(line[6:])
            if "result" in data:
                content = data["result"].get("content", [])
                for c in content:
                    if c.get("type") == "text":
                        return json.loads(c["text"])
            elif "error" in data:
                raise Exception(f"MCP error: {data['error']}")
    raise Exception(f"No result in response: {resp[:200]}")

def export_bank(bank_id, output_path):
    all_items = []
    offset = 0
    limit = 1000
    total = None
    while total is None or offset < total:
        result = call_mcp("list_memories", {"bank_id": bank_id, "limit": limit, "offset": offset})
        items = result.get("items", [])
        total = result.get("total", len(items))
        all_items.extend(items)
        offset += limit
        if not items:
            break
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    output = {"bank_id": bank_id, "exported_at": "YYYY-MM-DDT00:00:00Z",
              "total": total, "exported_count": len(all_items), "items": all_items}
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"Exported {len(all_items)}/{total} memories to {output_path}")
    return len(all_items)

if __name__ == "__main__":
    export_bank(sys.argv[1], sys.argv[2])
```

Run it for each bank:
```bash
python3 /tmp/export_bank.py <bank_id> /home/opc/workspace/toolset/infrastructure/hermes/banks/<bank_id>/YYYY-MM-DD.json
```

**Batch execution**: Since requests are I/O-bound, run multiple banks concurrently with `&` + `wait`:
```bash
python3 /tmp/export_bank.py bank1 /path/bank1/date.json 2>&1 &
python3 /tmp/export_bank.py bank2 /path/bank2/date.json 2>&1 &
...
wait
```

**Pagination**: The script handles pagination automatically (limit=1000, offset-based). No bank has exceeded 1000 facts as of 2026-07-10, but the loop is defensive.

### Method B (legacy): MCP tool output → persisted temp file

When MCP tool output exceeds ~100K chars, Hermes auto-saves it to `/tmp/hermes-results/call_*.txt`:

```bash
cp /tmp/hermes-results/call_<FILE>.txt /home/opc/workspace/toolset/infrastructure/hermes/banks/<BANK_ID>/YYYY-MM-DD.json
# Clean the MCP wrapper (the file is {"result": "...{escaped JSON}..."}):
python3 -c "
import json
d = json.load(open('f.json'))
raw = json.loads(d['result']) if isinstance(d.get('result'), str) else d['result']
json.dump(raw, open('f.json','w'), indent=2, ensure_ascii=False)
"
```

This approach works but has downsides:
- Temp file path must be located in tool output headers
- Double-encoded JSON needs unwrapping
- Some response sizes fall between thresholds (not persisted, too large for heredoc)
- The raw `cp` retains the MCP outer wrapper; the cleanup step is mandatory

### Method C (legacy): `write_file` for small banks

For banks under ~50 facts (~60-200KB total), the MCP response is inline. Use `write_file` with the `structuredContent` JSON:

```python
# Extract via the tool's structuredContent.result field
# Not via cat heredoc — unicode escapes and embedded quotes break heredocs
```

## Step 3: Reflect + Retain daily summary

For each bank:

### 3a. Reflect

```
mcp_hindsight_selfhosted_reflect(
    bank_id=BANK_ID,
    budget="mid" for large banks (200+ facts), "low" for others,
    query="Sintetiza las interacciones, decisiones, aprendizajes y cambios de las últimas 24 horas..."
)
```

**Edge case — reflect returns empty**: If `finish_reason=length` or `Provider returned empty message content`, retry with a shorter, more targeted query:
```
query="¿Qué cambios, entradas nuevas o decisiones de procesamiento hubo en el buffer en las últimas 24 horas?"
```
and `budget="low"`. This happened with `personal-buffer` (344 facts, large bank) — the full synthesis query exceeded the model's output window.

### 3b. Retain the result

Use `retain()` (async) — it returns instantly:

```json
{"status":"accepted","operation_id":"<uuid>"}
```

Keep the retain content concise (3-8 sentences, not the full reflect text). Focus on: what was done, what was learned, what decisions were made. Tags always: `["daily-summary", "YYYY-MM-DD", "BANK_ID"]`

## Step 4: Git commit + push

### Pre-push: resolve repo state

**Stale rebase-merge directory**: The previous cron run may have left `.git/rebase-merge/` on the filesystem if it crashed mid-rebase:
```bash
rm -fr ".git/rebase-merge" && git pull --rebase origin main
```

**Detached HEAD**: If previous cron ran on detached HEAD (common when rebasing), any commits made there are orphaned. Cherry-pick them onto main before proceeding:
```bash
git checkout main
git cherry-pick <orphaned-commit-hash>   # if relevant
```

**Diverged main**: If local main and origin/main have diverged (local has commits from orphaned detached HEAD, remote has 15+ different commits), use soft reset instead of rebase:
```bash
git reset --soft origin/main
```
This keeps your staged/new files and aligns the branch pointer. Then add + commit + push normally.

### Standard push

```bash
cd /home/opc/workspace/toolset
git add infrastructure/hermes/banks/
git commit -m "hermes-sync: banks YYYY-MM-DD"
git pull --rebase origin main
git push origin main
```

### Pattern B — Pre-existing unstaged/staged changes

When other files were modified outside this sync:

```bash
cd /home/opc/workspace/toolset
git add infrastructure/hermes/banks/
git commit -m "hermes-sync: banks YYYY-MM-DD"
git stash push -- docs/TODO.md infrastructure/hermes-context.md  # only pre-existing files
git pull --rebase origin main
git push origin main
```

### Verification

```bash
git log --oneline -3
# Should show: <hash> hermes-sync: banks YYYY-MM-DD
```

## Known pitfalls

| Pitfall | Mitigation |
|---------|-----------|
| `execute_code` blocked in cron mode | Use `terminal()` with inline Python or the export script via `python3 /tmp/export_bank.py`. The `terminal()` tool is available in cron mode. |
| `git pull --rebase` fails with stale `.git/rebase-merge/` | `rm -fr ".git/rebase-merge"` before the pull. Previous cron crashes leave this behind. |
| Detached HEAD from previous rebase | `git checkout main` then `git cherry-pick` any orphaned commits from the sync. Use `git log` on the orphan to check if it's relevant sync content. |
| Local main diverged from origin/main | `git reset --soft origin/main` — aligns pointer while preserving staged/unstaged work. |
| `list_memories(limit=1000)` sandbox overflow | Banks with 200-280 facts produce 420K-520K char responses at `limit=1000`. The sandbox can fail to persist the output file when it exceeds ~460K chars. **Workaround:** use `limit=500` for any bank with 200-1000 facts. Check the bank's `fact_count` from `list_banks()` output first. If the tool result says "could not be saved to sandbox", re-call with `limit=500`. |
| reflect returns empty content for large banks | Retry with shorter query + lower budget (`budget="low", max_tokens=512`). The full synthesis prompt can hit output length limits on 300+ fact banks. **If retry also fails** (observed with `toolset` at 125 facts and `personal-profile` at 224 facts on 2026-07-15): compose a manual summary from the `list_memories` output. Scan the items for patterns (dates, entities, tags) and write a 3-8 sentence summary focusing on what was done/learned/decided. The reflect failure appears to be a `deepseek-v4-flash` output length issue, not a data problem — the manual fallback produces a valid retain. |
| Export script missing at `/tmp/export_bank.py` | The script is ephemeral by nature. Re-create from the script block in this reference doc. Consider making it persistent if it's used 3+ times. |
| `default` bank exists and has facts | Skip it — it's an internal Hindsight bank, not a project bank. |
| Banks file grows with each daily dump | This is intentional — dumps are versioned by date for audit trail. |

## Appendix: Bank Inventory (as of 2026-07-15)

| Bank | Facts | Notes |
|---|---|---|
| personal-buffer | 1419 | Staging for KB candidates (largest bank) |
| hermes | 1183 | Orchestrator identity & state |
| wwe-profile | 369 | WWE preferences |
| chat-profile | 256 | General chat ideas & patterns |
| personal-profile | 224 | Curated KB (Terreno/Mito) |
| researchit | 216 | Research engine |
| toolset-profile | 222 | Toolset infra decisions |
| entrenador-profile | 154 | Personal trainer profile |
| cl-concerts-db | 126 | Concert DB project |
| toolset | 125 | Infra multi-tenant |
| kairos | 124 | Governance framework |
| evidencia-zero | 79 | Data sanitization tool |
| yacv | 69 | Resume builder |
| desarrollo-trazambiental-profile | 67 | Dev sub-group Trazambiental |
| trazambiental-profile | 67 | Equipo Trazambiental |
| witral | 54 | Plugin-based data router |

**Threshold guide**: Banks with >200 facts (hermes, personal-buffer, wwe-profile, personal-profile, researchit, toolset-profile) are the most expensive to export. Banks in the 200-280 range (personal-profile, researchit, toolset-profile, wwe-profile) need `limit=500` to avoid sandbox overflow. Banks below 200 facts work fine with `limit=1000`.

This table is for orientation only — always use live `list_banks()` for the actual counts.
