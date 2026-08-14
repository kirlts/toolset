# Bank Sync Execution Procedure

Used by the `hermes-sync-banks` cron job (02:00 UTC daily). This doc captures the step-by-step procedure and known pitfalls.

## Decision flow (DO NOT go MCP-first)

**The MCP-tools path cannot complete the full 16-bank sync inside one cron run.** Observed 2026-08-05: exporting via MCP `list_memories` pagination cost ~40+ tool calls (personal-buffer 6 pages at 5995 facts, hermes 3 pages at 2622, etc.), and the run was killed by the tool-calling iteration cap at 1/16 through the reflect+retain phase. Even when exports succeed, reflect+retain for 16 banks is 32+ more calls. MCP tools are conversational, not batch.

**UPDATE 2026-08-06 — the MCP path CAN complete when the iteration budget allows.** A full 16-bank sync via MCP tools finished in one cron turn (~15 min wall clock, 13,412 facts: personal-buffer 7 pages, hermes 3 pages, rest 1 page each, using `execute_code` to merge/persist page dumps instead of reading every page inline). The 08-05 failure was the iteration cap, not the MCP path itself. REST script (Method D) remains the lower-risk default, but if the run has budget for ~50-70 tool calls, MCP is viable and produces the final report content directly. When doing so: use `execute_code`/`terminal` to merge page outputs into the dated JSON (dedupe by `id`, verify count == `total`), and delete `_pageN.json` intermediates before `git add`.

**CONFIRMED 2026-08-10 — full sequential MCP sync succeeded again** (16 banks, 172,417 JSON lines committed as e36fe46). Pattern: per bank, `list_memories(limit=1000)` → parse persisted output (double-`json.loads` unwrap: `data['result']` is an escaped JSON string → `result['items']`) → write dated JSON via `terminal()` python → `reflect` + `retain`. The MCP path is now a proven reliable cron mode, not a last resort.

**CONFIRMED 2026-08-13 — 16-bank MCP sync with PURELY PARALLEL reflect/retain batches succeeded** (409,293 JSON lines committed as ef63476). This run departed from the old sequential-per-bank advice and proved the batching ceiling is higher than previously assumed: all 15 reflects fired in ONE parallel turn, then all 15 retains in ONE parallel turn (plus per-bank `list_memories` export pages fetched in parallel 8-9 calls at a time). No truncation, no timeouts. Only `list_memories` large responses need serialization; reflect/retain payloads are small enough to batch freely. Export verification used the `offset+last_page_items == total` check (personal-buffer: offset 8000 page returned 342 items → 8342 confirmed).

**CONFIRMED 2026-08-14 — clean 16-bank MCP sync, zero failures** (419,081 insertions, commit 31ca9d2). Third consecutive full MCP run without a single timeout, truncation, or reflect-empty event. Pattern used: exports with `list_memories` (personal-buffer 8,629 facts / 9 pages, hermes 2,796 / 3 pages — the giant bank no longer needs REST), then reflect+retain in 2-3-call parallel batches per turn (not all-at-once like 08-13, but parallel within turn, sequential across turns). All 16 retains returned `{"status":"accepted","operation_id":...}`. Notable: retains stored the FULL reflect synthesis text verbatim (1,300-3,100 output tokens each, not the 3-8 sentence condensed form) and were all accepted — full-text retain of reflect output is fine in practice despite the older "keep concise" advice. JSON dump sizes worth knowing: hermes 2.9MB, personal-buffer 9.3MB.

**Correct order of attack when the sync must run:**
1. **REST API script first** — `scripts/hindsight-sync.py` (background `terminal(background=true, notify_on_complete=true)`). It does export + reflect + retain + git in one process.
2. **If `127.0.0.1:8888` is refused**, use the container IP: `HIP=$(docker inspect hindsight --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')` then `HINDSIGHT_API=http://$HIP:8888 python3 hindsight-sync.py`. This has been the fix on 2026-08-02, 08-03 AND 08-05 — treat the mapped port as likely-broken and jump to the container IP early, before burning iterations on MCP.
3. **MCP tools as LAST resort only** for a few small banks (<100 facts) when the REST API is genuinely unreachable. Never attempt the full 16-bank export+reflect+retain via MCP tools in one turn — budget the iteration cap (you have roughly 40-50 tool calls per cron run total, including this pre-flight recall).

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

**IMPORTANT — parallel list_memories constraint:** Do NOT batch more than 2 list_memories calls in the same turn for banks likely to produce >500KB responses. When 3+ concurrent list_memories calls are made for larger banks, some responses can be truncated with "Full output could not be saved to sandbox". However, batching 3-5 *small* banks (<300KB response expected, i.e. under ~100 facts) in one turn has been observed to work reliably (2026-07-19: 5 banks up to 427 facts/~852KB each all succeeded). Err on the side of serializing any bank you're unsure about. reflect() and retain() calls are safe to batch since their payloads are small.

### ⚠️ Method A (deprecated — REST API preferred over MCP JSON-RPC)

Direct MCP JSON-RPC via curl is **no longer recommended** for bulk exports. As of 2026-07-30, POSTing to the MCP SSE endpoint at the tailscale URL returns `"Invalid Content-Type header"` — the MCP SSE transport requires a persistent connection, not individual curl requests.

**Use Method D (Local REST API) instead.** Keep Method A's export script as a fallback only if the REST API is unavailable.

**Legacy details preserved below for reference:**

The endpoint was at:
```
https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/mcp/
```

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

### Method D (PREFERRED): Local Hindsight REST API

The Hindsight Docker container exposes a REST API on `http://127.0.0.1:8888` (not to be confused with the MCP SSE endpoint at the tailscale URL — that one does NOT accept standard HTTP POST). This approach is simpler, faster, and more reliable than MCP JSON-RPC: standard HTTP POST/GET, no SSE parsing, no double-encoded JSON, no Content-Type issues.

**⚠️ Port mapping can break while the container is healthy (observed 2026-08-02 AND 2026-08-03 — recurring, treat as likely-broken).** `127.0.0.1:8888` returned connection refused from the host even though `docker ps` showed `hindsight Up (healthy)` and the API responded fine inside the container (`docker exec hindsight curl http://localhost:8888/v1/default/banks`). Fix: query the container IP directly from the host:
```bash
HIP=$(docker inspect hindsight --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
curl "http://$HIP:8888/v1/default/banks"   # works when the mapped port refuses
```
Then point the sync script at it: `HINDSIGHT_API=http://$HIP:8888 python3 /tmp/hindsight-sync.py` (the script reads `HINDSIGHT_API`, default `http://127.0.0.1:8888`). The canonical script lives at `scripts/hindsight-sync.py` in this skill — copy to /tmp each run rather than hand-writing it.

**Key endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/default/banks` | GET | List all banks |
| `/v1/default/banks/{bank_id}/memories/list` | GET | Paginated memory list (params: limit, offset, type, tags) |
| `/v1/default/banks/{bank_id}/reflect` | POST | Run reflect |
| `/v1/default/banks/{bank_id}/memories` | POST | Retain memories |

**Response formats:**

- list_memories: `{"items": [...], "total": N, "limit": N, "offset": N}`
- reflect: `{"text": "# Synthesis...", "usage": {...}}`
- retain: `{"success": true, "items_count": 1, "bank_id": "..."}`
- list_banks: `{"banks": [{"bank_id": "...", "name": "...", "fact_count": N, ...}]}`

**Reflect request body:**
```json
{
  "query": "Sintetiza las interacciones, decisiones, aprendizajes y cambios...",
  "budget": "high",
  "max_tokens": 4096
}
```

**Retain request body (async=false preferred for cron — blocks until stored):**
```json
{
  "items": [{
    "content": "reflect output text here",
    "context": "daily-summary",
    "timestamp": "2026-07-30T00:00:00Z",
    "tags": ["daily-summary", "YYYY-MM-DD", "BANK_ID"]
  }],
  "async": false
}
```

**Full sync script structure:**

The script is written to `/tmp/hindsight-sync.py` (ephemeral — recreate from this doc each run). It uses `urllib.request` (stdlib, no pip deps):

```python
#!/usr/bin/env python3
"""Hindsight Daily Sync — export all banks, reflect+retain, git push."""
import json, os, subprocess
from datetime import datetime, timezone
import urllib.request

API = "http://127.0.0.1:8888"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
EXPORT = "/home/opc/workspace/toolset/infrastructure/hermes/banks"

def api_get(path):
    with urllib.request.urlopen(f"{API}{path}", timeout=120) as r:
        return json.loads(r.read().decode())

def api_post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{API}{path}", data=data, method="POST",
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode())

def memories(bid):
    all_items, off = [], 0
    while True:
        r = api_get(f"/v1/default/banks/{bid}/memories/list?limit=500&offset={off}")
        items = r.get("items", [])
        all_items.extend(items)
        if off + 500 >= r.get("total", 0):
            break
        off += 500
    return all_items

# Discover banks
banks = api_get("/v1/default/banks").get("banks", [])
skip = {"default", "test_one_bank.py", "sync_phase2_reflect.py", "sync_phase1_export.py",
        "sync_banks.py", "reflect-progress.json", "export-manifest-2026-07-22.json"}
banks = [b for b in banks if b["bank_id"] not in skip]

for b in banks:
    bid = b["bank_id"]
    os.makedirs(f"{EXPORT}/{bid}", exist_ok=True)

    mems = memories(bid)
    json.dump({"export_date": TODAY, "bank_id": bid,
               "total_memories": len(mems), "memories": mems},
              open(f"{EXPORT}/{bid}/{TODAY}.json", "w"),
              indent=2, ensure_ascii=False, default=str)

    ref = api_post(f"/v1/default/banks/{bid}/reflect", {
        "query": "Sintetiza las interacciones, decisiones, aprendizajes y cambios...",
        "budget": "high", "max_tokens": 4096})
    text = ref.get("text", "")
    if text:
        api_post(f"/v1/default/banks/{bid}/memories", {
            "items": [{"content": text, "context": "daily-summary",
                       "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "tags": ["daily-summary", TODAY, bid]}],
            "async": False})

# Git
os.chdir("/home/opc/workspace/toolset")
for cmd in [["git", "pull", "--rebase", "origin", "main"],
            ["git", "add", "infrastructure/hermes/banks/"],
            ["git", "commit", "-m", f"hermes-sync: banks {TODAY}"],
            ["git", "push", "origin", "main"]]:
    subprocess.run(cmd, timeout=120)
```

**Timeout scaling — split into batches:** Processing all ~16 banks in one script takes 8-10 minutes and will hit the 600s terminal timeout. Split across 3 sequential scripts in the same conversation:

| Batch | Banks | Est. time |
|-------|-------|-----------|
| 1 | hermes, personal-buffer, desarrollo-trazambiental-profile, witral, evidencia-zero, yacv | ~200s |
| 2 | cl-concerts-db, toolset-profile, trazambiental-profile, kairos, researchit, toolset | ~200s |
| 3 | chat-profile, wwe-profile, personal-profile, entrenador-profile | ~150s |

Run as three sequential `terminal()` calls in the same assistant turn.

**⚠️ Observed 2026-08-01 — the 3-batch plan is TOO OPTIMISTIC.** Real per-bank time with reflect budget=high is ~1.5-2.5 min (export is fast; reflect+retain dominate). A 6-bank foreground call timed out at 420s mid-retain; a 4-bank call timed out at 300s. **Preferred approach: run the whole remaining list as ONE background process** (`terminal(background=true, notify_on_complete=true)`) — the script prints per-bank progress with flush=True and survives foreground timeouts. Total wall-clock for 16 banks: ~25-30 min — but the 2026-08-03 full run took ~43 min; per-bank reflect can spike to 5+ min even on mid-size banks (toolset-profile 314s, wwe-profile 290s, both ~480-615 facts), so treat 1.5-2.5 min as the floor, not the ceiling. When a foreground call is killed mid-retain: the retain often still lands server-side (async=False completes server-side even if the client dies) — verify with `curl "http://127.0.0.1:8888/v1/default/banks/<bid>/memories/list?limit=3&tags=daily-summary"` and check `mentioned_at` timestamps before reprocessing that bank.

**Python helpers (for ad-hoc per-bank operations via execute_code or terminal):**
```python
BASE = "http://127.0.0.1:8888"
# Actually define these inline before each use — session vars don't persist across terminal() calls
```

**Monitoring a background sync run (2026-08-03):** `process(action='poll')` often returns an EMPTY `output_preview` while the run is in progress — even minutes in, despite the script using `flush=True`. Per-bank log lines only surface in `wait`/`log` output and may arrive in bursts. Ground truth for progress: count exported files on disk:
```bash
ls /home/opc/workspace/toolset/infrastructure/hermes/banks/*/<TODAY>.json | wc -l   # 16 = exports done; reflect+retain may still be running
```
The final `SYNC SUMMARY` block plus the `GIT ...` lines (pull/add/commit/push) in the process output confirm the full pipeline incl. git push. Expected cadence on 2026-08-03: ~1 bank per 2-3 min early, slower on the two giant banks (hermes 2.6K facts, personal-buffer 5.4K facts), faster on small ones.

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

Use `retain()` (sends the operation to the server) — normally returns immediately with an `operation_id`:

```json
{"status":"accepted","operation_id":"<uuid>"}
```

**Known timeout:** The MCP call itself can timeout at 300s under server load for larger banks (200+ facts). This is a transport-level timeout — the async operation is often still accepted on the server side despite the client-side timeout. If a retain call times out, **retry once** — the second attempt reliably succeeds.

Keep the retain content concise (3-8 sentences, not the full reflect text). Focus on: what was done, what was learned, what decisions were made. Tags always: `["daily-summary", "YYYY-MM-DD", "BANK_ID"]`

## Step 4: Git commit + push

### Pre-push: resolve repo state

**Active rebase with real conflict (observed 2026-08-06)**: The 01:00 file-artifacts cron and 02:00 banks cron both commit into `infrastructure/hermes/`, so `git pull --rebase` can hit a genuine conflict (this run: `both modified: infrastructure/hermes/config.yaml`). First check `git status` for `interactive rebase in progress`. If conflicted:
1. `grep -n "<<<<<<\|======\|>>>>>>" infrastructure/hermes/config.yaml` to locate markers.
2. Trivial conflicts (same YAML content, different key ordering) → keep HEAD's side via `patch` (replace-mode on the marker block).
3. `git add` the resolved file, then continue with **`GIT_EDITOR=true git rebase --continue`** — plain `git rebase --continue` fails in cron/terminal mode with `error: Terminal is dumb, but EDITOR unset`.
4. Do `git pull --rebase origin main` AGAIN after the rebase completes to catch any commits pushed since; then add banks, commit, push.
If the conflict is non-trivial, prefer the repo copy as source of truth (deploy.sh restores from repo).

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

# Per-bank file presence — do NOT trust `git show --stat | grep` (rename detection
# undercounts: showed 15/16 files on 2026-08-03 while all 16 were committed).
# Check each bank explicitly:
git ls-tree --name-only HEAD infrastructure/hermes/banks/<bank>/YYYY-MM-DD.json
```

## Known pitfalls

| Pitfall | Mitigation |
|---------|-----------|
| **`list_memories(limit=1000)` returns `has_more=False` but bank has far more facts** | Observed 2026-08-10: personal-buffer had `fact_count` 7471 but a single `list_memories(limit=1000)` call returned 1000 items with `has_more=False` — the run accepted it and moved on (potential silent under-export). `has_more` is NOT a reliable completeness signal in cron mode. Mitigation: compare exported `items` count against the bank's `fact_count` from `list_banks()`; if it differs materially, paginate by `offset` in `limit=1000` steps until `offset >= total` regardless of `has_more`. |
| **`execute_code` blocked in cron mode** | Use `terminal()` with inline Python or the export script via `python3 /tmp/export_bank.py`. The `terminal()` tool is available in cron mode. |
| `git pull --rebase` fails with stale `.git/rebase-merge/` | `rm -fr ".git/rebase-merge"` before the pull. Previous cron crashes leave this behind. |
| Detached HEAD from previous rebase | `git checkout main` then `git cherry-pick` any orphaned commits from the sync. Use `git log` on the orphan to check if it's relevant sync content. |
| Local main diverged from origin/main | `git reset --soft origin/main` — aligns pointer while preserving staged/unstaged work. |
| `list_memories(limit=1000)` sandbox overflow | Banks with 200-280 facts produce 420K-520K char responses at `limit=1000`. The sandbox can fail to persist the output file when it exceeds ~460K chars. **Workaround:** use `limit=500` for any bank with 200-1000 facts. Check the bank's `fact_count` from `list_banks()` output first. If the tool result says "could not be saved to sandbox", re-call with `limit=500`. |
| **Parallel list_memories causes truncation** | 3+ concurrent `list_memories` calls produce "could not be saved to sandbox" even for small banks (58 facts, 116KB). **Do not batch more than 2 list_memories calls.** Serialize them, or at most parallelize 2 at a time. reflect() and retain() calls ARE safe to batch. |
| reflect returns empty content for large banks | Retry with shorter query + lower budget (`budget="low", max_tokens=512`). The full synthesis prompt can hit output length limits on 300+ fact banks. **If retry also fails** (observed with `toolset` at 125 facts and `personal-profile` at 224 facts on 2026-07-15): compose a manual summary from the `list_memories` output. Scan the items for patterns (dates, entities, tags) and write a 3-8 sentence summary focusing on what was done/learned/decided. The reflect failure appears to be a `deepseek-v4-flash` output length issue, not a data problem — the manual fallback produces a valid retain. |
| **retain() MCP call timeout** | retain() initiates an async operation on the server side, but the MCP call itself can timeout (300s). Observed with researchit (~226 facts) and wwe-profile (~403 facts). **Mitigation:** Retry once — the async operation is often accepted server-side despite the transport timeout. A second attempt reliably succeeds. |
| **Script execution hits 600s terminal timeout** | Processing all 16 banks in one script takes ~480-600s. The terminal timeout is 600s. **Mitigation:** Split across 3 scripts (6 banks → 6 banks → 4 banks). Each completes in ~200-300s. See Method D for the batch breakdown. |
| Export script missing at `/tmp/hindsight-sync.py` or `/tmp/export_bank.py` | The script is ephemeral by nature. Re-create from the script block in this reference doc. Consider making it persistent if it's used 3+ times. |
| `default` bank exists and has facts | Skip it — it's an internal Hindsight bank, not a project bank. |
| Banks file grows with each daily dump | This is intentional — dumps are versioned by date for audit trail. |
| **Paginated MCP pages can collide / duplicate** | When paginating `list_memories` via MCP with persisted temp files, the LAST page often comes back INLINE (not persisted to `/tmp/hermes-results/`) because it is small (e.g. 12 items at offset=500 of 512 total). If you then read the previous page's file path again, you get page 1 twice (1000 items, 500 duplicated). Observed 2026-08-05 with toolset-profile. **Mitigation:** after combining pages, dedupe by `id` (`seen=set(); [it for it in items if not (it['id'] in seen or seen.add(it['id']))]`) and verify the count matches the `total` field from the last response (`500 + 12 == 512`). Never assume a file exists for every page — check the tool output header for a persisted-path marker on each call. |
| **`_pageN.json` intermediates committed by mistake** | When paginating via MCP (multi-page banks like personal-buffer 7 pages, hermes 3 pages), the merge step produces `YYYY-MM-DD_pageN.json` scratch files. Delete them before `git add`: `rm -f infrastructure/hermes/banks/<bank>/<date>_page*.json` (observed 2026-08-06: `2026-08-06_page1.json` was cleaned up; commit contains only the merged `2026-08-06.json` per bank). |
| **`jq add` fails to merge paginated pages with nested arrays** | Observed 2026-08-13 merging `list_memories` pages: `jq add` corrupts/mishandles nested structures (items are arrays of objects with nested links/tags). Don't fight jq — merge with inline Python: load each page file, `items.extend(page_items)`, dedupe by `id`, dump the combined `{"bank_id", "exported_at", "total", "items"}`. |
| **`chunk_id` can be `null` — don't key page files on it** | When pages are persisted separately, the tool response's `chunk_id` is sometimes null and cannot identify the bank. Map page files to banks by their file path (`/tmp/hermes-results/call_*.txt` per bank), not by any content field (observed 2026-08-13). |
| **`git rebase --continue` fails: "Terminal is dumb, but EDITOR unset"** | Cron/terminal has no editor configured. Run `GIT_EDITOR=true git rebase --continue` (observed 2026-08-06 after resolving config.yaml conflict). Without it the rebase stalls with "could not commit staged changes". |
| **Rebase conflict on `infrastructure/hermes/config.yaml`** | The 01:00 files cron and 02:00 banks cron both touch this file; conflicts are expected. Usually trivial YAML key-order (e.g. `provider` vs `model` line order). Resolve keeping HEAD's side, `git add`, continue with `GIT_EDITOR=true`. See Pre-push section. |
| **Export script reused instead of canonical** | The canonical script is `scripts/hindsight-sync.py` in this skill — copy it to /tmp each run. Do not hand-write a fresh `sync_banks.py` per run (observed 2026-08-05: a hand-written script hung on HTTP calls to the MCP endpoint); use Method D + `HINDSIGHT_API` env var. |

| **REST API reflect returns empty `text` for busy banks** | Observed on some banks when reflect times out internally. Retry with `budget="low"` and a shorter query, or fall back to manual summary from list_memories output. |
| **MCP JSON-RPC via curl returns `Invalid Content-Type header`** | The MCP SSE endpoint does not accept standard HTTP POST with JSON body. Use the REST API at `http://127.0.0.1:8888` instead. |
| **REST API `127.0.0.1:8888` connection refused but container healthy** | docker-proxy port mapping can fail while the container is fine (observed 2026-08-02 AND 2026-08-03 — recurring). Use container IP: `HIP=$(docker inspect hindsight --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')` then `HINDSIGHT_API=http://$HIP:8888`. See Method D section. |

## Appendix: Bank Inventory (as of 2026-08-10)

| Bank | Facts | Notes |
|---|---|---|
| personal-buffer | ~7,471 | Staging for KB candidates (largest bank, needs pagination: 8 pages at limit=1000) |
| hermes | ~2,756 | Orchestrator identity & state (needs pagination: 3 pages at limit=1000) |
| wwe-profile | ~644 | WWE preferences |
| toolset-profile | ~529 | Toolset infra decisions |
| personal-profile | ~525 | Curated KB (Terreno/Mito) |
| chat-profile | ~462 | General chat ideas & patterns |
| entrenador-profile | ~385 | Personal trainer profile |
| researchit | ~362 | Research engine |
| desarrollo-trazambiental-profile | ~328 | Dev sub-group Trazambiental |
| toolset | ~324 | Infra multi-tenant |
| cl-concerts-db | ~288 | Concert DB project |
| kairos | ~210 | Governance framework |
| trazambiental-profile | ~207 | Equipo Trazambiental |
| evidencia-zero | ~147 | Data sanitization tool |
| yacv | ~139 | Resume builder |
| witral | ~122 | Plugin-based data router |

**Threshold guide**: Banks with >1,000 facts need pagination. For personal-buffer (7,471 facts), `limit=1000` needs 8 pages. For hermes (2,756 facts), `limit=1000` needs 3 pages. All other banks fit in a single `limit=1000` call (but see the `has_more=False` pitfall — verify counts against `list_banks()` even for single-page banks).

**REST API pagination**: `GET /v1/default/banks/{bid}/memories/list?limit=500&offset=0` → response has `items`, `total`, `limit`, `offset`. Use `while offset < total: offset += limit` to paginate.

This table is for orientation only — always use live `list_banks()` for the actual counts.
