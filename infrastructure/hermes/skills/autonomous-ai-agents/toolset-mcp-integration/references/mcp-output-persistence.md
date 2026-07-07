# MCP Tool Output Persistence

When an MCP tool returns a result larger than ~200K characters, the Hermes runtime auto-saves it to a temporary file under `/tmp/hermes-results/call_<session>_<random>.txt`. Smaller results are returned inline in the tool output.

## Behaviors

| Size | Behavior | File path |
|------|----------|-----------|
| > ~200K chars | Auto-persisted to temp file | `/tmp/hermes-results/call_*.txt` |
| < ~200K chars | Returned inline in structured content | N/A — data is in conversation context |

## Impact on Cron Jobs (no `execute_code`)

In cron mode, `execute_code` is blocked (no user present to approve). You cannot use the Hermes tools Python API to process large MCP outputs. The correct pattern is:

### Large output (persisted to temp file)

```bash
cp /tmp/hermes-results/call_*.txt /target/path/<bank>/YYYY-MM-DD.json
```

### Small output (inline)

```bash
python3 << 'EOF'
import json
data = {"items": [...], "total": N, "limit": 1000, "offset": 0}
wrapper = {"result": json.dumps(data), "structuredContent": data}
with open("/target/path/<bank>/YYYY-MM-DD.json", "w") as f:
    json.dump(wrapper, f)
EOF
```

### Threshold ambiguity

The exact threshold (~200K chars) is runtime-dependent. If you're uncertain whether the output will be persisted:
1. Call the MCP tool
2. If output says `"Full output saved to: /tmp/hermes-results/..."` → it was persisted
3. If output is fully inline → use the inline saving pattern above

### File Format

All bank export files use the exact MCP wrapper format:
```json
{"result": "<JSON-stringified items object>", "structuredContent": "<parsed items object>"}
```

Do NOT save only the inner `items` array — keep the MCP wrapper for compatibility with the repo's historical format.
