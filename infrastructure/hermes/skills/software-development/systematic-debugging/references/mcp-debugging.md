# MCP Call Failure Debugging

Debugging MCP tool timeouts and transport failures in Hermes' gateway-to-server communication.

## Symptoms

- MCP tool call returns: `TimeoutError: MCP call timed out after Ns (configured timeout: Ns)`
- The operation completed on the server side despite the timeout (check server logs)
- Retry with the `sync` variant of the same tool works

## Architecture Context

In this Toolset deployment:

```
Hermes Gateway ──HTTP/SSE──→ Caddy (:8080) ──→ MCP Server (:8888 or :9999)
```

- MCP calls are routed via the reverse proxy (Caddy), not directly to the container
- The MCP transport uses SSE (Server-Sent Events) — a persistent HTTP connection
- If the SSE connection drops, the MCP client won't receive responses even if the server processes the request

## Investigation Steps

### 1. Check Server Logs First (docker logs)

```bash
docker logs <container_name> --tail 200 | grep -E "mcp|error|timeout|<relevant_op>"
```

Key signals:
- `Processing request of type CallToolRequest` → MCP server received the request
- `Processing request of type PingRequest` → MCP transport health check (should be periodic)
- `Marked async operation as completed` → async op finished but client may have timed out

**If there's NO `CallToolRequest` log** — the MCP request never reached the handler. The transport was dead.

**If there IS a `CallToolRequest` log** but no response → the handler crashed or response wasn't sent.

### 2. Check the MCP Transport Health

Look for `PingRequest` in the MCP server logs. The MCP protocol uses periodic pings to keep the SSE connection alive. If pings are present:
- Before the failed call → transport was healthy at that point
- After the failed call → transport recovered (transient issue)
- Not present during the failure window → transport was down

### 3. Trace the Routing

Check each hop in the chain:

1. Hermes config.yaml → MCP URL
2. Reverse proxy config (Caddyfile / Nginx) — which port and upstream
3. Docker compose → container port mapping

### 4. Cross-reference Timestamps

From the client side, note when the call was made. From the server logs, find what happened at that time:

- If the server shows NO activity during the call window → transport issue (connection dropped)
- If the server shows the operation created but no MCP request logged → request arrived via REST API, not MCP endpoint
- If the server shows the operation completed but the client timed out → MCP response never made it back

### 5. Check Worker Pool Saturation

Server logs showing `WORKER_STATS` entries indicate the worker pool status:

```
worker=... slots=X/10 | reserved: [...] | shared=0/8 | global: pending=N
```

- `slots=X/10` — how many workers are busy
- `global: pending=N` — queued operations waiting for a worker
- `proc: rss_mb=N` — memory pressure

If all slots are full or `pending > 0`, the server may not be able to accept new MCP connections.

## Common Root Causes

| Symptom | Likely Cause | Approach |
|---------|-------------|----------|
| No CallToolRequest logged, operation still completed | MCP transport died; request arrived via REST API | Restart container or check SSE health |
| CallToolRequest logged, no response sent | Server handler crashed (uncaught exception) | Check server error logs |
| All MCP calls fail, not just one | Server down or port misconfigured | Check `docker ps` and port mapping |
| Intermittent timeouts | Worker pool full or memory pressure | Check WORKER_STATS for saturation |
| sync variant works but regular times out | async handler path has different transport handling | Use sync variant as fallback; investigate server version |

## Real Case: Hindsight async retain timeout (June 2026)

**Symptom:** `mcp_hindsight_selfhosted_retain` timed out after 300s. `sync_retain` worked immediately after.

**Trace:**

1. Checked hindsight container logs — `retain` WAS received and completed successfully:
   ```
   [PENDING_BREAKDOWN] batch_retain: total=1 claimable=0 payload_null=1
   ```
   Note `payload_null=1` — the MCP request arrived without a proper payload attachment via the MCP transport.

2. Meanwhile, NO `Processing request of type CallToolRequest` was logged for `retain`. Only `sync_retain` later logged `CallToolRequest`. This confirms the MCP SSE transport was disconnected when the first call arrived.

3. The operation DID complete on the server side (37s later), but the MCP client never received the `operation_id` response because the transport channel was dead.

4. `sync_retain` worked 5 minutes later because the SSE connection had re-established by then.

**Key insight:** `retain` (async) goes through a different code path than `sync_retain`. The async version creates an operation via the REST API endpoint and returns immediately. If the MCP transport is down, the request falls through to REST but the MCP client on the gateway side gets no response. The `sync` version blocks on the MCP `CallToolRequest` handler, which works only when the transport is alive.

**Lesson:** When an MCP async tool times out but `sync_retain` works, the issue is the MCP transport layer, not the server. The operation probably completed fine.

**Hindsight-specific architecture for this Toolset:**

```
Hermes Gateway → Caddy (/hindsight/* → hindsight:8888) → Hindsight API
                                      (/api/banks/* → hindsight:9999) → Hindsight CP
```

The docker-compose for hindsight:
```yaml
hindsight:
  ports:
    - "127.0.0.1:8888:8888"  # API/MCP
    - "127.0.0.1:9999:9999"  # Control Plane
  healthcheck:
    test: ["CMD", "curl", "-sf", "http://localhost:8888/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 60s
  environment:
    HINDSIGHT_API_LLM_PROVIDER: openai
    HINDSIGHT_API_LLM_MODEL: deepseek-v4-flash
    HINDSIGHT_API_LLM_BASE_URL: https://opencode.ai/zen/go/v1
```

The healthcheck only tests port 8888 (API), NOT 9999 (MCP port). And the MCP endpoint is routed via Caddy `/hindsight/* → hindsight:8888`, so the actual MCP path is `http://hindsight:8888/mcp/`.

**Fallback pattern:** When `retain` (async) times out, immediately retry with `sync_retain` as fallback. Sync doesn't block long for small payloads because it processes synchronously without queueing overhead.
