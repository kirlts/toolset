---
name: toolset-mcp-integration
description: "How Hermes Agent integrates with MCP services in the Toolset Personal — Hindsight (recall/retain/reflect) and Composio. Architecture, tool semantics, known issues, and operational principles."
version: 1.2.0
author: Toolset Personal
license: MIT
metadata:
  hermes:
    tags: [toolset, mcp, hindsight, composio, infrastructure, architecture]
    related_skills: [agent-state-management, project-orientation, hermes-webui]
---

# Toolset MCP Integration

How Hermes Agent uses MCP services within the Toolset Personal infrastructure — specifically the **hindsight-selfhosted** (memory) and **composio** (third-party API gateway) MCP servers.

## MCP Server Topology

| Server | URL | Tools | Status |
|--------|-----|-------|--------|
| `hindsight-selfhosted` | `https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/mcp/` | 37 tools (recall, retain, reflect, list_banks, get_bank, etc.) | ✅ Enabled (resolved: see CI-CD-01 Compliance) |
| `composio` | `https://connect.composio.dev/mcp` | 7 tools (SEARCH_TOOLS, etc.) | ✅ Enabled |

Both are configured in `~/.hermes/config.yaml` under `mcp_servers:` and are started at session init.

## Tool Semantics: Memory vs MCP Hindsight Tools

**This is the most common confusion point.** There are TWO separate interfaces for memory in this toolset:

### 1. Hermes `memory` tool (built-in)

| Aspect | Detail |
|--------|--------|
| **What it is** | A built-in Hermes tool for simple key-value persistence |
| **Backend config** | `memory.provider: hindsight` → stores into bank `hermes` |
| **Capacity** | 2,200 chars (`memory_char_limit`) |
| **Scope** | User profile + personal agent notes only |
| **Bank** | Always bank `hermes` — cannot target other banks |
| **Use for** | User preferences, environment notes, simple facts about who the user is |

### 2. MCP Hindsight tools (recall / retain / reflect / list_banks / etc.)

| Aspect | Detail |
|--------|--------|
| **What they are** | MCP-server-hosted tools from the hindsight-selfhosted server (37 tools) |
| **How they arrive** | Injected at session start via MCP discovery from the hindsight-selfhosted MCP server |
| **Capacity** | Unlimited (PostgreSQL + pgvector) |
| **Scope** | Any bank in the system — `toolset`, `kairos`, `cl-concerts-db`, `evidencia-zero`, etc. |
| **Bank targeting** | Pass `bank_id="<repo-name>"` to operate on a specific bank |
| **Use for** | All project memory: architectural decisions, code context, task progress, lessons learned |

### Which one to use

| Situation | Use |
|-----------|-----|
| Save "user prefers concise responses" | `memory()` → goes to bank `hermes` |
| Save "this repo uses pytest with xdist" | `retain(bank_id="<repo>", fact="...")` |
| Load project context before working | `recall(bank_id="<repo>", query="...")` |
| Synthesize learnings from a bank | `reflect(bank_id="<repo>", query="...")` |
| Discover available banks | `list_banks()` |
| Store user preference about behavior | `memory()` (goes to `hermes`) |
| Store a technical decision about infra | `retain(bank_id="toolset", fact="...")` |

**Never use `memory()` for project-level or bank-specific operations.** The `memory` tool only addresses the `hermes` bank with a 2KB limit.

**Never use `retain`/`recall` for user profile facts** — those go via `memory()` to the profile system.

## MCP Response Wire Formats

When working with Hindsight MCP tools programmatically (e.g. from a Python script via direct HTTP), the response parsing is non-obvious:

### list_memories
```json
{"items": [...], "total": 1939, "limit": 1000, "offset": 0}
```
- The key is **`items`**, not `memories` or `result`.
- `total` tells you the full count — if `total > limit`, paginate with `offset`.
- The raw MCP SSE response wraps this as `content[0].text` which is a JSON string; parse it once to get the dict above.

### reflect
```json
{"text": "# Synthesis of last 24 hours..."}
```
- The `content[0].text` is a JSON object whose key is **`text`**, not `result`.
- The `structuredContent.result` mirrors this: it's `{"text": "..."}`.
- **Incorrect:** `result.get("result", "")` returns empty string.
- **Correct:** `json.loads(content[0].text).get("text", "")`.

### retain
```json
{"status": "accepted", "message": "Memory storage initiated", "operation_id": "uuid"}
```
- Async operation. Returns immediately with an `operation_id`.
- Track via `get_operation(operation_id)` if confirmation is needed.

### list_banks
```json
{"banks": [{"bank_id": "...", "name": "...", "fact_count": N, ...}]}
```
- Simple flat list. No nesting surprises.
- Filter out `bank_id: "default"` — legacy system bank, no useful content.

### Pagination pattern
When iterating banks with `list_memories`:
```python
offset = 0
limit = 1000
all_items = []
while True:
    data = mcp_call("list_memories", {"bank_id": bid, "limit": limit, "offset": offset})
    items = data.get("items", [])
    if not items:
        break
    all_items.extend(items)
    if len(items) < limit:
        break
    offset += limit
```

## Session Initialization Protocol

Every new session (WebUI, WhatsApp, CLI, any channel) MUST:

```
1. memory(query="contexto completo...")   # user profile from bank hermes
2. recall(bank_id="<active-repo>")        # project context from specific bank
3. If no active repo, recall(bank_id="toolset")  # infra context
```

This is documented in SOUL.md and is mandatory per the toolset's operational rules. The recall must happen BEFORE reading files.

## CI-CD-01 Compliance

**Current state:** ✅ **VERSIONED** — 25 Jun 2026 (commit `094ec15`)

The fix was added to `infrastructure/deploy.sh` as an idempotent step using the same `eval` pattern as the existing MarkItDown install. Each deploy ensures pydantic >= 2 in the Hermes venv:

```bash
VENV_PY=/usr/local/lib/hermes-agent/venv/bin/python
SUDO_PIP="sudo $VENV_PY -m pip install"
eval $SUDO_PIP 'pydantic>=2' -q
```

This runs after the Hermes venv is installed/updated, so it survives CI/CD deploys. The step is safe to re-run — `pip install 'pydantic>=2'` is idempotent.

**Full details** in `references/streamable-http-bug.md` — includes root cause table, verification steps, dependency warnings, and detection script.

**Gateway restart mechanics** in `references/gateway-restart-requirement.md` — documents why MCP tools don't survive config changes without gateway restart, the `/new` fallacy, and workarounds for restarting from outside the gateway process tree.

## Operational Principles

### Source of Truth

**The toolset repo (`/home/opc/workspace/toolset/`) is the single source of truth for infrastructure knowledge.** When uncertain about architecture, config, or how something works:

1. Check `docs/MASTER-SPEC.md` → architectural specification
2. Check `infrastructure/hermes/config.yaml` → actual running config template
3. Check `docs/CHANGELOG.md` → recent changes and verification status
4. Check `docs/TODO.md` → known issues and pending work
5. Check `docs/RULES.md` → operational rules for AI agents

**Do NOT make assertions from memory or system prompt alone.** The system prompt describes what SHOULD be; the repo describes what IS.

### CI/CD Double-Write (CI-CD-01)

Every infrastructure fix applied locally MUST be replicated in:
- `infrastructure/deploy.sh` (the deployment procedure)
- `infrastructure/hermes/config.yaml` (the versioned config)
- `infrastructure/docker-compose.yml` (the service definitions)

A change made only to the live instance is lost on the next CI/CD deploy. The repo is the durable record.

### Secret Management

All secrets (API keys, tokens, connection IDs) are managed via Infisical, not hardcoded. The flow is:
```
GitHub Secrets → CI/CD (deploy.yml) → deploy.sh → Infisical → .env at runtime
```

The Composio MCP key injection uses a two-attempt fallback chain:
1. **Attempt 1 — Infisical API**: `inject-composio-key.py` reads `INFISICAL_SERVICE_TOKEN` + `INFISICAL_PID` from `/opt/toolset/.env` and calls the local Infisical API (`localhost:8081`) for `COMPOSIO_MCP_KEY`
2. **Attempt 2 — Hermes .env fallback**: If Infisical is down or unreachable, reads `COMPOSIO_MCP_KEY` directly from `/home/opc/.hermes/.env`

If Infisical fails (e.g. container down, DB connection issue), the **fallback `.env` file is the active source**. The `.env` is populated by `deploy.sh` via `export COMPOSIO_MCP_KEY=***` and sourced at deploy time.

**To check which source is active:**
```bash
# Check if Infisical is alive
curl -sf http://localhost:8081/api/status || echo "Infisical DOWN"

# Check the fallback env key
grep COMPOSIO_MCP_KEY /home/opc/.hermes/.env
```

Never hardcode secrets in configs, skills, or scripts.

### MCP Connectivity Verification Procedure

**Problema detectado (25 Jun 2026):** Testear Composio MCP con `curl -H "x-consumer-api-key: ..."` al endpoint HTTP da un **falso positivo**. El curl prueba conectividad HTTP, no disponibilidad de tools MCP desde el gateway.

### Protocolo de Verificación Correcto (4 niveles)

```
Nivel 1: Gateway tiene el MCP server configurado?
  → grep -A5 'composio:' /home/opc/.hermes/config.yaml
  → Debe mostrar url + headers con key

Nivel 2: Gateway pudo conectarse al MCP server?
  → journalctl -u hermes-gateway --no-pager | grep -i "composio"
  → Debe mostrar "connected successfully" o similar. NO debe mostrar 401.

Nivel 2.5: Verificación directa de validez de la key (independiente del gateway)
  → python3 -c "
import urllib.request, json
key = open('/home/opc/.hermes/config.yaml').read().split(\"x-consumer-api-key: \")[1].split('\\n')[0].strip()
req = urllib.request.Request('https://connect.composio.dev/mcp', headers={'x-consumer-api-key': key})
try:
    with urllib.request.urlopen(req, timeout=10) as r: print('Status:', r.status)
except urllib.error.HTTPError as e:
    print('HTTP Error:', e.code, '- Body:', e.read()[:200])
except Exception as e:
    print('Connection error:', e)
"
  → **400 (Bad Request: MCP session required)** = key válida, endpoint responde
  → **401 (Unauthorized)** = key rechazada por Composio (expirada/inválida)
  → **4xx/5xx genérico o timeout** = problema de red o servicio Composio caído

Nivel 3: MCP tools están disponibles en la sesión?
  → Listar las tools disponibles (revisar my tool list en el system prompt)
  → Si hay tools prefijadas "mcp_composio_*" → disponibles
  → Si solo hay "mcp_hindsight_selfhosted_*" y NO "mcp_composio_*" → no disponibles
```

**Cinco escenarios:**

| Nivel 1 | Nivel 2.5 | Nivel 2 | Nivel 3 | Diagnóstico |
|---------|-----------|---------|---------|-------------|
| ✅ Config OK | 400 | ✅ Connected | ✅ Tools presentes | **Todo funcional** |
| ✅ Config OK | 400 | ✅ Connected | ❌ Tools ausentes | Bug discovery interno del gateway (mcp_discovery_timeout?) |
| ✅ Config OK | 400 | ❌ 401 | ❌ Tools ausentes | **Key válida pero gateway cargó key stale.** Gateway necesita restart. |
| ✅ Config OK | 401 | ❌ 401 | ❌ Tools ausentes | **Key inválida/expirada.** Regenerar en Composio. |
| ❌ Sin config | — | — | ❌ Tools ausentes | MCP server no configurado en config.yaml |

**⚠️ NO confundir:** Un test de curl que devuelve 200 NO significa que el MCP funcione. El gateway usa un cliente MCP (JSON-RPC sobre SSE) que es independiente del REST. La verificación real es Nivel 2 + Nivel 3. La prueba Python (Nivel 2.5) es más precisa que curl porque diferencia 401 (key inválida) de 400 (MCP protocolo — key válida).

**Escenario adicional: 401 PERSISTENTE en TODOS los restarts con key válida (Nivel 2.5 = 400, Nivel 2 = 401 tras múltiples restarts del gateway):** Esto indica una **interrupción del lado de Composio**, no un problema local de configuración. El endpoint `connect.composio.dev/mcp` puede rechazar autenticación durante períodos de degradación. Síntomas:
  - Múltiples instancias del gateway (diferentes PIDs) todas con el mismo 401
  - La key es válida (prueba Nivel 2.5 devuelve 400)
  - El patrón de restart (por crash o manual) no cambia el resultado
  - Duración típica observada: ~3-4 horas
  - **Resolución:** esperar (el servicio Composio se recupera solo). No cambiar config.

### Diagnóstico Rápido de Tools MCP Ausentes

```bash
# 1. Verificar config en disco
grep -A5 'composio:' /home/opc/.hermes/config.yaml | grep 'x-consumer-api-key'

# 2. Verificar logs del gateway
journalctl -u hermes-gateway --no-pager | grep -i "composio" | tail -5

# 3. Si hay 401 pero la key en disco es válida → gateway necesita restart
#    (no se puede hacer desde dentro: ver references/gateway-restart-requirement.md)

# 4. Para diagnóstico avanzado: probar key directo contra endpoint MCP
python3 -c "
import urllib.request
key = open('/home/opc/.hermes/config.yaml').read().split(\"x-consumer-api-key: \")[1].split(chr(10))[0].strip()
req = urllib.request.Request('https://connect.composio.dev/mcp', headers={'x-consumer-api-key': key})
try:
    with urllib.request.urlopen(req, timeout=10) as r: print('OK', r.status)
except urllib.error.HTTPError as e:
    print('ERR', e.code, e.read()[:150])
"
```

## Composio Gmail File Attachment via Google Drive (Workaround)

**Problema:** La tool `GMAIL_SEND_EMAIL` de Composio requiere un `s3key` para adjuntar archivos. El `s3key` se obtiene subiendo el archivo al S3 de Composio, típicamente vía `COMPOSIO_REMOTE_WORKBENCH`. Pero el sandbox del workbench NO tiene acceso a archivos locales del VPS, y pasar 128KB+ de base64 inline en el código Python es inviable.

**Solución (validada 25 Jun 2026):** Subir el archivo a Google Drive primero (Composio tiene acceso a Drive) y adjuntarlo desde Drive en el email de Gmail.

### Flujo

```
1. Kilo CLI → COMPOSIO_SEARCH_TOOLS → encuentra tool de Google Drive para upload
2. Kilo CLI → sube archivo local a Google Drive → obtiene fileId
3. Kilo CLI → tool GMAIL_SEND_EMAIL con attachment desde Drive (fileId o URL)
```

### Requisitos

- Composio debe tener la integración de Google Drive autenticada (misma cuenta Google que Gmail)
- La conexión de Drive se autoriza igual que Gmail (link de OAuth de Composio)

### Fallback: GitHub Releases como File Host

Si Google Drive no está disponible o el enfoque Drive falla, se puede usar GitHub Releases
como host temporal para el archivo. **Esto funciona** porque:
- `gh release create` es inmediato y no requiere auth adicional
- La URL de descarga es pública y accesible desde el sandbox de Composio
- Se puede eliminar después de usado

**Flujo:** Ver `references/github-releases-file-host.md` para el comando exacto.

### Ventajas sobre s3key/Workbench

| Aspecto | s3key via Workbench | Drive approach |
|---------|-------------------|----------------|
| Acceso a archivos locales | ❌ Sandbox no tiene acceso | ✅ Kilo lee el archivo local |
| Tamaño de archivo | ❌ Base64 inline > 100KB es inviable | ✅ Sin límite práctico |
| Pasos | 3 (base64 → workbench → s3key → email) | 2 (Drive upload → email) |
| Confiabilidad | ❌ REMOTE_WORKBENCH propenso a timeout | ✅ API directa de Google Drive |

**⚠️ Nota:** El link de autorización de OAuth expira (~10 min). Si el usuario no autoriza a tiempo, Kilo falla con timeout. En ese caso, relanzar Kilo con la conexión ya autorizada (el usuario ya aceptó el permiso).

## MCP Output Persistence

When an MCP tool returns a result larger than ~200K characters, the runtime auto-saves it to `/tmp/hermes-results/call_*.txt`. Smaller results stay inline in the tool output. This affects how you save MCP-fetched data to files, especially in cron mode where `execute_code` is blocked.

See `references/mcp-output-persistence.md` for the full pattern and file format.

## Bulk Operations: REST API vs MCP Tools

When to use the Hindsight REST API directly instead of MCP tools:

| Scenario | MCP Tools | REST API (`http://127.0.0.1:8888`) |
|----------|-----------|-------------------------------------|
| Single recall/retain/reflect | ✅ Perfect — small payloads, conversational | ❌ Overkill |
| Export ALL memories from a bank | ❌ Responses >100K chars get truncated or temp-file-encoded | ✅ Returns clean JSON with pagination |
| Paginated memory listing | ❌ 3+ concurrent list_memories calls truncate | ✅ Standard HTTP pagination (limit+offset) |
| Daily sync (all banks) | ❌ Timeouts, truncation, encode issues | ✅ Single script, all 16 banks |
| Ad-hoc reflect on one bank | ✅ Fast, conversational | ✅ Also fine |

### REST API Endpoints

```
Base: http://127.0.0.1:8888
Docker container: hindsight (port 8888 mapped to host)
```

| Endpoint | Method | Notes |
|----------|--------|-------|
| `/v1/default/banks` | GET | List all banks → `{"banks": [...]}` |
| `/v1/default/banks/{bank_id}/memories/list` | GET | Params: `limit`, `offset`, `type`, `tags`, `q` |
| `/v1/default/banks/{bank_id}/reflect` | POST | Body: `{"query": "...", "budget": "high", "max_tokens": 4096}` |
| `/v1/default/banks/{bank_id}/memories` | POST | Body: `{"items": [...], "async": false}` |

Key difference from MCP: retain with `async: false` blocks until stored and returns `{"success": true, "items_count": 1}` — no operation ID tracking needed.

### When NOT to use REST API

- Inside a conversation turn where you need to chain multiple operations with reasoning — MCP tools are conversational
- When you're in a context where localhost:8888 isn't accessible (e.g., from a subagent without network access to Docker)
- For single memory operations — MCP tools are faster for one-off recall/retain/reflect

**See `hermes-sync-configure/references/bank-sync-execution.md` for the full daily sync procedure including the complete Python script.**

## Pitfalls

1. **Confusing `memory()` with `retain()`/`recall()`** — The most common error. `memory()` is a 2KB profile tool for the `hermes` bank only. `retain`/`recall` are the MCP tools for full bank access across all repos.

2. **Making architectural claims from system prompt alone** — The SOUL.md and system prompt describe the intended architecture. The actual state is in the toolset repo. When in doubt, read the repo — not the system prompt.

3. **Fixing infra locally without CI-CD-01 versioning** — Any local fix that isn't in `deploy.sh` or the versioned config is lost on next deploy. Example from 25 Jun 2026: pydantic was upgraded in the Hermes venv to unblock hindsight MCP; the fix was immediately versioned in `deploy.sh` via commit `094ec15`. Always follow this pattern: fix on host → version in repo → push.

4. **Not loading this skill before investigating MCP issues** — This skill already documents the architecture, the `memory` vs `retain` semantics, known issues, and the source-of-truth hierarchy. Before investigating any MCP or Hindsight issue, load this skill with `skill_view(name="toolset-mcp-integration")` to avoid rediscovering documented facts.

6. **Using `memory()` for task progress** — Task progress, project decisions, and code context belong in the project's Hindsight bank via `retain()`. The `memory` tool is for user preferences only.

7. **MCP Composio tools missing in session despite config present** — If `mcp_servers.composio` exists in `config.yaml` but Composio tools don't appear, check if the key is stale:
   - **Scenario A — Key is a placeholder:** Run `grep x-consumer-api-key /home/opc/.hermes/config.yaml`. If it shows `PLACEH...PLOY`, the inject script failed. See `infrastructure-deployment` skill's `references/secret-flow-infisical.md` for the fix (was a missing `?workspaceId=` query param in the Infisical API call).
   - **Scenario B — Key is correct in config.yaml but gateway loaded a stale version:** Check `journalctl -u hermes-gateway --no-pager | grep -i "composio.*401"`. If the gateway showed 401 at startup time but the current key on disk is valid, the gateway never reloaded after the key was injected. **Fix:** restart the gateway (see `references/gateway-restart-requirement.md` for workarounds — the gateway cannot be restarted from within itself).

8. **MCP tools not available after /new — gateway needs restart** — `/new` creates a new session within the existing gateway process. It does NOT reload MCP server connections. If Composio MCP failed to connect at gateway startup (e.g. wrong key, network issue), `/new` will NOT fix it. The gateway itself must be restarted.
   - MCP server connections are established once at gateway startup and cached in memory
   - Change the key in `config.yaml` and call `/new` = the gateway still has the old key
   - Resolution: restart the gateway via external mechanism (cronjob, systemd timer, SSH from outside)
   - Full documentation: `references/gateway-restart-requirement.md`

9. **Gateway blocks its own restart** — The `hermes-gateway` systemd service blocks `sudo systemctl restart hermes-gateway` when called from within the gateway process (SIGTERM propagates to children, killing the command). Workarounds:
   - Schedule a cronjob with `no_agent=true` that runs the restart
   - Use `sudo systemd-run --unit=hermes-restart sudo systemctl restart hermes-gateway`
   - SSH from an external machine

10. **Stale systemd unit: TimeoutStopSec mismatch** — The gateway logs this warning at startup:
    ```
    WARNING gateway.run: Stale systemd unit detected: hermes-gateway.service has
    TimeoutStopSec=90s but drain_timeout=180s (expected >=210s). systemd may
    SIGKILL the gateway mid-drain.
    ```
    This causes `systemd[1]: hermes-gateway.service: Failed with result 'signal'`
    crashes when systemd kills the process before the gateway finishes draining
    MCP connections. The fix is to regenerate the systemd unit:
    ```bash
    hermes gateway service install --replace
    ```
    The unit lives in `/etc/systemd/system/hermes-gateway.service`. After
    regeneration, systemd picks up the corrected `TimeoutStopSec` value.
    This warning is **informational** — it does not block session startup.
    But the `Failed with result 'signal'` can cascade: gateway restarts →
    repeated 401 on Composio if the key was stale when the original unit was
    generated (each restart creates a new gateway process that re-fetches
    config, but the 90s timeout can kill it mid-connect). Fix the unit and
    the restart pattern stabilizes.

11. **Using MCP `list_memories` for bank exports** — MCP tool output is limited to ~500KB/200K chars before truncation or temp-file redirection. For banks with 200+ facts, `list_memories` returns 400K-800K chars which either gets truncated or double-encoded. The REST API at `http://127.0.0.1:8888` returns clean paginated JSON with no size limit. See "Bulk Operations" section above.

12. **MCP tools unavailable for large batch workflows** — The daily sync of 16 banks cannot be done via MCP tools alone. The MCP tools are conversational/interactive. For batch automation, use the REST API and split the work across 3 script invocations to stay under the 600s terminal timeout. **Observed 2026-08-05: attempting the 16-bank sync via MCP `list_memories` pagination + reflect + retain blows the cron's tool-calling iteration budget (~40 calls just for exports; killed at 1/16 through the reflect+retain phase).** MCP-first is a dead end for multi-bank batch work — always route through `hermes-sync-configure/scripts/hindsight-sync.py` (REST API) with the container-IP fallback (`docker inspect hindsight --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'`) when `127.0.0.1:8888` refuses.
