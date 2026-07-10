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

```bash
mkdir -p /home/opc/workspace/toolset/infrastructure/hermes/banks/{<all-known-bank-ids>}
```

Banks discovered at runtime via `list_banks()`. Create them as they appear.

## Step 1: Discover banks

Call `mcp_hindsight_selfhosted_list_banks()`. Filter out `"default"` (legacy internal bank — never include it).

Current active banks and approximate fact counts (as of 2026-07-05):

| Bank | Facts | Activity |
|---|---|---|
| toolset | ~727 | Core infra decisions |
| hermes | ~354 | Orchestrator identity & state |
| researchit | ~158 | Research engine |
| chat-profile | ~92 | General chat ideas & patterns |
| personal-profile | ~85 | Curated KB (Terreno/Mito) |
| kairos | ~80 | Governance framework |
| wwe-profile | ~72 | WWE preferences |
| cl-concerts-db | ~68 | Concert DB project |
| personal-buffer | ~52 | Staging for KB candidates |
| evidencia-zero | ~45 | Data sanitization tool |
| yacv | ~40 | Resume builder |
| witral | ~27 | Plugin-based data router |
| toolset-profile | ~2 | Toolset worker (empty) |

**Live check**: Bank counts change over time. Re-run `list_banks()` each sync for the actual `fact_count` field, not the table above.

**Edge case — empty bank**: toolset-profile has ~2 facts (created by onboarding, no content yet). It's fine to run reflect+retain on it; the reflect will simply report "no activity". Do not skip it — the retain creates the daily-summary tag chain.

## Step 2: Export each bank as JSON

For each bank (process SEQUENTIALLY, one at a time):

### 2a. Fetch memories

```
mcp_hindsight_selfhosted_list_memories(bank=BANK_ID, limit=1000)
```

**Pagination check**: if the response shows `"total" > limit`, paginate with `offset` to get all pages.

### 2b. Extract and save to file

**Cron-mode constraint**: `execute_code` is blocked by `approvals.cron_mode`. All data extraction MUST use `terminal()` — either `cp` for persisted temp files or `cat` heredocs for inline data.

**Large outputs** (>100K chars) are auto-saved to `/tmp/hermes-results/call_*.txt` as `persisted-output`. The simplest extraction is a plain `cp`:

```bash
cp /tmp/hermes-results/call_<FILE>.txt /home/opc/workspace/toolset/infrastructure/hermes/banks/<BANK_ID>/YYYY-MM-DD.json
```

The file is already valid JSON — no parsing needed. Banks like `toolset` (420 facts, ~870KB), `hermes` (227 facts, ~450KB), and `researchit` (112 facts, ~218KB) consistently hit this threshold.

**Small outputs** (<100K chars, typically banks with <50 facts) return inline. Save with a `cat` heredoc (single-quoted EOF delimiter to prevent shell expansion):

```bash
cat > /home/opc/workspace/toolset/infrastructure/hermes/banks/<BANK_ID>/YYYY-MM-DD.json << 'EOF'
{"result": "<full JSON output from MCP tool result>"}
EOF
```

For inline data, verify the JSON is well-formed by testing a quick `python3 -m json.tool` on the file after writing. Some MCP responses include multi-line strings with Unicode escapes that are valid JSON but fragile in heredocs.

**Combo pattern**: fetch the next bank's `list_memories()` while processing the current bank's reflect+retain, to reduce wall-clock time. But always process reflect+retain sequentially per bank.

## Step 3: Reflect + Retain daily summary

For each bank:

### 3a. Reflect

```
mcp_hindsight_selfhosted_reflect(
    bank_id=BANK_ID,
    budget="mid" for large banks (200+ facts), "low" for small banks,
    query="Sintetiza las interacciones, decisiones, aprendizajes y cambios de las últimas 24 horas..."
)
```

### 3b. Retain the result

Use `retain()` (async) — it returns instantly and doesn't block the sync pipeline. The write is queued and completes asynchronously:

```json
{"status":"accepted","operation_id":"<uuid>"}
```

`sync_retain` is available but NOT recommended here — it blocks until Hindsight finishes processing, which can take seconds on large banks. The sync pipeline prioritizes throughput; async retention is sufficient for daily summaries.

Keep the retain content concise (3-8 sentences, not the full reflect text). Focus on: what was done, what was learned, what decisions were made.

## Step 4: Git commit + push

Two patterns depending on what state the working tree is in:

### Pattern A — Clean working tree (no pre-existing changes)

```bash
cd /home/opc/workspace/toolset
git add infrastructure/hermes/banks/
git pull --rebase origin main
git commit -m "hermes-sync: banks YYYY-MM-DD"
git push origin main
```

Pull before commit when the tree is clean — avoids diverging from remote.

### Pattern B — Pre-existing unstaged/staged changes (most common)

When other files (e.g. `docs/TODO.md`, `infrastructure/hermes-context.md`) were modified outside this sync:

```bash
cd /home/opc/workspace/toolset
git add infrastructure/hermes/banks/
git commit -m "hermes-sync: banks YYYY-MM-DD"
# Now git pull --rebase will fail because of the other modified files.
# Stash only those, not our committed changes:
git stash push -- docs/TODO.md infrastructure/hermes-context.md
git pull --rebase origin main
git push origin main
# git stash pop later when convenient
```

**Why commit first**: The new bank files are versioned and safe. Stashing only the pre-existing unrelated changes isolates them from the sync commit. The stash doesn't need to be popped for push.
**Why not `git stash` (unqualified)**: That stashes everything including the new files we just committed. `git stash pop` can then fail on merge conflicts if the rebase touched the same areas.

### Verification

After push, confirm:

```bash
git log --oneline -3
# Should show: <hash> hermes-sync: banks YYYY-MM-DD
```

## Combo pattern (parallelism within sequential processing)

While banks are processed sequentially (one reflect+retain at a time), you can overlap I/O with computation:

```
Fetch bank N list_memories  →  while waiting:  process bank N-1 reflect+retain
                              ↓
Save bank N JSON             →  reflect bank N  →  retain bank N
                              ↓
Fetch bank N+1 list_memories →  (overlap starts again)
```

This reduces wall-clock time significantly on the 14-bank pipeline without violating the "sequential per-bank" requirement. The pattern works because MCP tools are async at the transport level — you issue the next `list_memories` immediately after saving the previous bank's output.

## Known pitfalls

| Pitfall | Mitigation |
|---------|-----------|
| `execute_code` blocked in cron mode | Use `terminal()` with `python3 << 'PYEOF'` or `python3 -c "..."` instead. The `terminal()` tool is available in cron mode. |
| `git pull --rebase` fails with pre-existing unstaged/staged changes | Use **Pattern B** (commit first, stash only pre-existing files, pull, push). Do NOT use unqualified `git stash` — it buries the committed files and risks merge conflicts on pop. |
| Banks file grows with each daily dump | This is intentional — dumps are versioned by date for audit trail |
| **Inline MCP data too large for heredoc, too small for temp file** — banks with 30-90 facts (~60-200KB total chars) return inline in the MCP response but contain unicode escapes, embedded quotes, and multiline strings that break `cat << 'EOF'` heredocs | **Primary method (reliable):** use `write_file` tool with the JSON content from the MCP `structuredContent` field. The write_file tool handles special characters correctly. **Secondary method:** use `terminal()` with `python3 -c "import json,sys; json.dump(json.loads(sys.stdin.read())['result'], open('/path/file.json','w'), indent=2)"` piping raw JSON through stdin. **NOT recommended:** `cat << 'EOF'` heredocs — they break on unicode escapes and embedded quotes. |
| `default` bank exists and has facts | Skip it — it's an internal Hindsight bank, not a project bank |
| Large banks (200+ facts) generate 500KB+ tool output with persisted file at `/tmp/hermes-results/call_*.txt` | Use `cp /tmp/hermes-results/call_*.txt .../BANK_ID/YYYY-MM-DD.json` then clean the MCP wrapper with `python3 -c "import json; d=json.load(open('f.json')); json.dump(json.loads(d['result']) if isinstance(d.get('result'),str) else d['result'], open('f.json','w'), indent=2, ensure_ascii=False)"`. The raw `cp` retains the MCP outer wrapper; this command strips it to clean JSON. |
| Medium banks (50-200 facts) may cross the persistence threshold (~200-500KB total output) | Check for `persisted-output` header in tool response + `/tmp/hermes-results/call_*.txt` path. If present, use `cp` + clean. If inline, use `write_file`. |
| MCP `list_memories` for banks under ~50 facts often returns inline data that's NOT auto-persisted | These are the trickiest. The data is in the MCP response's `structuredContent.result.items` but not in a temp file. Extract with `write_file` before the data scrolls out of context, or use `terminal()` with python piping via a second MCP call. |
| Hindsight MCP might be slow on large reflects | Set budget="mid" for 200+ fact banks; budget="low" for <50 fact banks. Budget="low" produces adequate summaries even for larger banks. |
| `sync_retain` vs `retain` — sync_retain blocks, retain returns instantly | Use async `retain()` for throughput. The backed-up retain queue on Hindsight is non-blocking and doesn't degrade on burst writes. |
| File cleanup — `cp` from `/tmp/hermes-results/` preserves the MCP wrapper `{"result": "{...}"}` | This is expected. The inner JSON (`result.items`) is what matters. Use the `python3` cleanup command above after the `cp` to unwrap. Without unwrapping, downstream consumers get a double-encoded string instead of a proper JSON array. |
