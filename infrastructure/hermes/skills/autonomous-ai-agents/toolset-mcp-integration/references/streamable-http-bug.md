# Streamable HTTP Transport — Root Cause & Resolution

## Status

✅ **RESOLVED** — 25 Jun 2026

The `mcp` package in the Hermes venv already included `client.streamable_http` (mcp v1.26.0), but it couldn't be imported because **pydantic was version 1.10.26** while mcp 1.26.0 requires **pydantic >= 2**. `TypeAdapter` (used by mcp) was introduced in pydantic v2.

**Lesson**: The error `mcp.client.streamable_http is not available` did NOT mean the mcp package was too old. The mcp package (1.26.0) was new enough — the real blocker was an incompatible pydantic pin in the Hermes venv.

## Original Error

```
hermes mcp test hindsight-selfhosted
Transport: HTTP → https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/mcp/
Auth: none
✗ Connection failed (7176ms): MCP server 'hindsight-selfhosted' requires HTTP
  transport but mcp.client.streamable_http is not available. Upgrade the mcp
  package to get HTTP support.
```

## Root Cause

| Component | Required | Had | Issue |
|-----------|----------|-----|-------|
| mcp | 1.26.0 | 1.26.0 | ✅ Version OK |
| pydantic | >= 2 | 1.10.26 | ❌ TypeAdapter missing |
| streamable_http | in mcp.client | present | ❌ Blocked by pydantic ImportError |

The `mcp/__init__.py` imports `from .client.session import ClientSession`, which in turn imports `from pydantic import AnyUrl, TypeAdapter`. With pydantic 1.x, `TypeAdapter` doesn't exist → `ImportError` → the entire mcp package is unusable → `streamable_http` never loads.

## The Fix

```bash
VENV=/usr/local/lib/hermes-agent/venv
$VENV/bin/python3 -m pip install 'pydantic>=2'
```

This upgraded pydantic from 1.10.26 → 2.13.4. After the upgrade, `streamable_http` imports successfully and the MCP server connects.

Note: `pip` binary is stripped from the Hermes install, but `python3 -m pip` works.

## Verification

```bash
# 1. Confirm mcp imports work
$VENV/bin/python3 -c "from mcp.client import streamable_http; print('OK')"

# 2. Test MCP connection
hermes mcp test hindsight-selfhosted
# Expected: ✓ Connected (177ms)  ✓ Tools discovered: 32

# 3. Confirm 32 hindsight tools now available
# Tools include: retain, recall, reflect, list_banks, create_bank, get_bank,
# list_memories, get_memory, update_memory, invalidate_memory, list_documents,
# list_tags, get_bank_stats, update_bank, delete_bank, clear_memories,
# list_mental_models, create_mental_model, list_directives, etc.
```

## Dependency Warning

The pydantic upgrade causes a version conflict with `infisical` Python package (requires pydantic < 2). This is **low risk** because:
- Infisical CLI (`infisical` binary) runs as a standalone binary, not from the Hermes venv
- The `infisical` Python package is only used if Hermes imports it directly, which doesn't happen in normal operation
- No immediate breakage observed

Minor conflicts with `hermes-agent`'s pinned deps (certifi, requests, rich) are cosmetic — pip's dependency resolver warns but does not block operation.

## CI-CD-01 Compliance

**Current state:** ✅ **VERSIONED** — 25 Jun 2026 (commit `094ec15`)

The fix was added to `infrastructure/deploy.sh` as an idempotent step using the same `eval` pattern as the existing MarkItDown install. Each deploy ensures pydantic >= 2 in the Hermes venv:

```bash
VENV_PY=/usr/local/lib/hermes-agent/venv/bin/python
SUDO_PIP="sudo $VENV_PY -m pip install"
eval $SUDO_PIP 'pydantic>=2' -q
```

This runs after the Hermes venv is installed/updated, so it survives CI/CD deploys. The step is safe to re-run — `pip install 'pydantic>=2'` is idempotent.

## Detection Script

```bash
echo "=== MCP server status ==="
hermes mcp list 2>/dev/null | grep hindsight
echo ""
echo "=== Transport test ==="
hermes mcp test hindsight-selfhosted 2>&1 | tail -5
echo ""
echo "=== Tools actually loaded ==="
hermes tools list 2>/dev/null | grep -i "recall\|retain\|reflect\|list_banks\|get_bank" || echo "No hindsight MCP tools detected in session"
```

## Original Discovery

Found 25 Jun 2026 while investigating why `recall`/`retain` MCP tools were not available in a WebUI session. The mcp package (1.26.0) was already recent enough — the real blocker was pydantic 1.x pinned in the Hermes venv.