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

