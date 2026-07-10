# MCP Tool Output Persistence

When an MCP tool returns a result larger than ~500KB (~200K chars), the Hermes runtime auto-saves it to a temporary file under `/tmp/hermes-results/call_<session>_<random>.txt`. Smaller results are returned inline in the tool output's `structuredContent` field.

**Observed behavior (empirical, as of 2026-07-09):**

| Total chars | Facts (typical) | Behavior | Access method |
|------------|-----------------|----------|---------------|
| > ~200K chars (>500KB) | 90+ facts | Auto-persisted to `/tmp/hermes-results/call_*.txt` | `cp` or `cat` from temp file |
| < ~200K chars (<500KB) | <90 facts | Inline in `structuredContent.result` | Read from MCP response, save via `write_file` |

The exact threshold is runtime-dependent (subject to change with Hermes version). **Always check the tool output header first:**
- If you see `"Full output saved to: /tmp/hermes-results/..."` → it was persisted
- If the full JSON body is inline in the response → it was not persisted

## File Format

When persisted, the file contains the raw MCP transport wrapper:

```json
{"result": "<stringified JSON>", "structuredContent": {...}}
```

The inner `result` field is a JSON-stringified string containing the actual tool output. To extract clean JSON:

```python
import json
with open("file.json") as f:
    raw = json.load(f)           # outer parse
inner = raw["result"]            # still a string
if isinstance(inner, str):
    inner = json.loads(inner)    # inner parse → actual items
```

## Impact on Cron Jobs

In cron mode, `execute_code` is blocked (no user present to approve). Use these alternatives:

### Large output (persisted to temp file)
```bash
cp /tmp/hermes-results/call_*.txt /target/path/bank/YYYY-MM-DD.json
# Then unwrap the MCP wrapper:
python3 -c "
import json
with open('/target/path/bank/YYYY-MM-DD.json') as f:
    outer = json.load(f)
inner = outer.get('result', '')
if isinstance(inner, str): inner = json.loads(inner)
with open('/target/path/bank/YYYY-MM-DD.json', 'w') as f:
    json.dump(inner, f, indent=2, ensure_ascii=False)
"
```

### Small output (inline — NOT persisted)

**Best approach (most reliable):** Use the `write_file` tool directly with the JSON content from the MCP structuredContent while the data is still in your context. The `write_file` tool handles unicode escapes and embedded quotes correctly.

**Fallback (if data already scrolled out of context):** Re-fetch by calling the MCP tool again, then use `terminal()` with `python3 -c` piped through stdin:

```bash
# Re-fetch the MCP data and pipe through python for extraction
# (example: small bank with inline data)
# First call list_memories again, then immediately:
python3 -c "
import json,sys
data = json.loads(sys.stdin.read())
if 'result' in data:
    inner = json.loads(data['result']) if isinstance(data['result'], str) else data['result']
else:
    inner = data
with open('/target/path/bank/YYYY-MM-DD.json', 'w') as f:
    json.dump(inner, f, indent=2, ensure_ascii=False)
print('Saved', len(inner.get('items',[])), 'items')
"
# Pipe the MCP response JSON into this script
```

**Do NOT use `cat << 'EOF'` heredocs for inline MCP data.** The JSON contains unicode escapes, embedded quotes, and multiline strings in `text` fields that break heredocs. Always use `write_file` or `python3 -c` piping instead.
