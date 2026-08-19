---
name: toolset-ops
description: "Infrastructure operations for Toolset Personal (OCI/Docker/CI)."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [Infrastructure, OCI, Docker, CI-CD, Deployment]
    triggers: ["deploy", "fix bug", "infrastructure", "run cd"]
---

# Toolset Infrastructure Operations

## Rules (MASTER-SPEC §8)

| Rule | Description |
|---|---|
| INFRA-01 | All infra mutations strictly via CI/CD. No local tofu apply/destroy. |
| INFRA-02 | Remote state in OCI Object Storage is authoritative. |
| INFRA-03 | Service deployment via CI/CD. Local execution for verification only. |
| INFRA-04 | Mandatory gateway restart after pipeline/SOUL/config changes. |

## Kilo CLI Execution Rules

Kilo CLI ejecuta workflows multi-step (Kairós: /document, /derive, integraciones) que pueden tomar 5+ minutos.

**Reglas:**
- NUNCA usar `terminal(timeout=N)` para Kilo CLI. Siempre `terminal(background=true, notify_on_complete=true, timeout=600)`.
- Foreground timeout menor a 600 mata el proceso. El workflow queda incompleto y puede corromper estado.
- Verificar que el proceso complete antes de continuar con otra tarea.
- REPORT-01 aplica: reportar resultado cuando el worker notifique.

### WhatsApp Bridge Process Lifecycle

The WhatsApp bridge (`bridge.js`) runs as a Node.js process on port 3000, spawned by the Hermes gateway (not systemd, not Docker).

**Verifying bridge health:**
- `curl -sf http://127.0.0.1:3000/health` — returns `{"status":"connected",...}`
- `ps aux | grep bridge.js` — should show the process
- `tail -f /home/opc/.hermes/whatsapp/bridge.log` — live log

**Pitfalls:**
- **Do NOT send HUP to the bridge process.** Unlike most daemons, `kill -HUP <pid>` kills `bridge.js` rather than restarting it. The gateway respawns it automatically (RestartSec in systemd), but there's a ~5s gap where the bridge is unavailable.
- **After restart, the bridge reconnects to WhatsApp via WebSocket.** The log will show "Timeout in AwaitingInitialSync" then "✅ WhatsApp connected!" — this is normal.
- **Gateway spawns the bridge with correct env vars** (`WHATSAPP_ALLOWED_USERS`, etc.). If you manually start the bridge without the gateway, it may lack these env vars and reject all incoming messages.
- **The bridge log appends indefinitely** at `/home/opc/.hermes/whatsapp/bridge.log`. Check disk usage if the log grows large.

**Forcing a clean restart:**
```bash
sudo systemctl restart hermes-gateway   # gateway respawns the bridge cleanly
```

### Cron Job Failure Diagnosis

When the user reports a cron job ("CRUN", "trabajo programado") failing:

1. **Identify failing jobs**: `cronjob(action='list')` → check `last_status` field
2. **Extract error**: Read `~/.hermes/cron/jobs.json` → find `last_error` field for each failing job (e.g. `[Errno 32] Broken pipe`)
3. **Check job output**: Read files under `~/.hermes/cron/output/<job_id>/` — contains prompt + response or error context
4. **Cross-reference gateway logs**:
   ```
   journalctl -u hermes-gateway --since "<run_time>" --until "<run_time + 15m>" --no-pager
   ```
   Filter for the job's API provider: `grep -i "cron\|<job_id>\|broken\|error\|provider=<provider>"`
5. **Determine root cause**:
   - `[Errno 32] Broken pipe` → API provider (OpenCode Go / deepseek-v4-flash) closed the HTTP connection mid-response. **Not a job logic bug.** This is intermittent — the provider drops the connection during streaming. The cron framework retries 3 times, then marks the job as error.
   - `TimeoutError: MCP call timed out` → MCP server unresponsive (see `systematic-debugging` skill, MCP section)
   - Rate limit / 429 → provider throttling
6. **Test current provider health**: `curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://opencode.ai/zen/go/v1/models`
7. **Resolution**: If provider-side intermittent, no code change needed. If persistent, suggest model fallback or increased retries in the cron job definition.
8. **Report**: State the job name, error class, and root cause clearly. Do not report "it failed" without telling the user why.

### Common Patterns

| Error | Likely Cause | Action |
|---|---|---|
| `[Errno 32] Broken pipe` | API provider connection drop | Verify provider health, retry later, or add retries |
| `MCP call timed out` | MCP server container issue | Check container logs |
| HTTP 4xx/5xx | Provider outage | Check provider status page |
| Job runs but output is empty | Job logic error | Read cron/output/<id>/ for the full trace |

## Documentation Governance (Kairós Compliance)

**IMPORTANT — Martín stated this explicitly: "cualquier cambio que se hace en la documentación siempre tiene que ser coherente con las reglas de Kairós, eso no puede saltarse jamás."**

All documentation changes in Kairós-governed repos MUST follow these rules:

### Format Conventions (TODO.md)

Toolset TODO.md uses a specific format. When adding new EPICs:

```
## [EPIC-00X] Epic Name

> Ref: _section reference or "Por definir"_

### [TASK-0XX] Task Name

> Ref: _section reference or "Por definir"_

**Covered checks:** `Transversal governance`

- [ ] 🔲 Por definir — brief description of what needs doing
```

- Symbol legend: 🔲 = Pendiente, ⏳ = En progreso, 🤖 = IA verificable, 🧑 = Humano, 🤖🧑 = Mixto
- Completed items: `- [x] Description timestamp [🤖 Verified by tool]`
- Update the Overall Coverage Summary table at the bottom after adding EPICs
- Leave EPIC-00X numbers sequential (next unused)
- For strategic ideas not yet defined, mark as "Por definir" with 🔲

### Repo Boundaries

| Repo | You CAN edit | You CANNOT edit | Profile |
|---|---|---|---|
| toolset | docs/ (TODO.md, RULES, etc.), infrastructure/, skills/ | — | orchestrator (default) |
| personal | NEVER | ANY file | personal-profile only |
| jarvis, dino, etc. | Only when the task explicitly requires it | Without context | code-worker |

- **Never touch the `personal` repo** unless the user is actively talking in the Personal WhatsApp group. The personal-profile is strictly isolated.
- Strategic ideas for the Hermes ecosystem go into toolset's `docs/TODO.md` as EPICs.
- Personal-domain ideas go into the personal-buffer (for Martín to classify in his review sessions).

### Strategic Ideation Workflow

When the user asks for "non-obvious use cases" or "creative applications":

1. **Explore full user context first** — read the personal KB (`/home/opc/personal/knowledge-base/`), not just memory banks. The KB contains Terreno (facts about Martín's life, skills, constraints) and Mito (campaigns, ego frameworks, adaptations).
2. **Think across ALL domains** — not just software engineering. Martín's life spans: karate (Itosu-Ryu 4x/week), música docta (CL-Concerts), fauna marina (DinoWiki), OSINT B2B (Prometeo), SaaS (Jarvis), digital forensics (BlinData), residential constraints (8x6 cycle), financial constraints (liquidez restringida), philosophy (Kairós framework).
3. **Present ideas organized by domain** (life/tech/business/physical), not as a flat list.
4. **Never assume which ideas the user wants** — ask, don't commit.
5. **Capture selected ideas only** — as EPICs in toolset's `docs/TODO.md` following the format above.

### Workflow

For each bank (excluding `default`):

1. **Export facts to JSON:**
   ```python
   list_memories(bank=BANK_ID, limit=1000)
   ```
   - Results >~200KB are saved to `/tmp/hermes-results/call_*.txt` automatically
   - Results under that threshold come inline in the tool response
   - Copy the temp file to `infrastructure/hermes/banks/BANK_ID/YYYY-MM-DD.json`
   - For inline results, use `write_file` to save the JSON response directly
   - If `total > limit`, paginate with `offset` to get all pages

2. **Reflect on last 24h:**
   ```python
   reflect(bank=BANK_ID, budget="high", max_tokens=2048|4096,
           query="Sintetiza las interacciones, decisiones, aprendizajes y cambios de las últimas 24 horas...")
   ```
   - Use `max_tokens=4096` for active banks (hermes, toolset, personal), `2048` for dormant ones
   - **Timeout workaround:** If `budget="high"` times out after 300s (MCP timeout), retry with `budget="low"` and `max_tokens=1024`. The reduced budget returns a concise but still useful summary. This happens mainly on larger banks (500+ facts) when the MCP server is under load. Do NOT skip the bank — the low-budget reflect is sufficient for the daily summary retain.

3. **Retain daily summary:**
   ```python
   retain(bank=BANK_ID,
          content="=== Daily Summary YYYY-MM-DD ===\n<concise summary>",
          tags=["daily-summary", "YYYY-MM-DD", "BANK_ID"])
   ```

4. **Git commit (after ALL banks):**
   ```bash
   cd /home/opc/workspace/toolset
   git pull --rebase origin main     # always first, avoid divergence
   git add infrastructure/hermes/banks/
   git commit -m "hermes-sync: banks YYYY-MM-DD"
   git push origin main
   ```

### Cron-Mode Constraints

- `execute_code` is BLOCKED in cron mode — use `terminal()` for file operations (cp, mv) and `write_file`/`patch` for content creation
- The sync runs as a systemd-triggered cron job with no user present — final response text is automatically delivered to the user, do NOT use send_message
- If there is genuinely nothing to report, respond with exactly `[SILENT]` (nothing else) to suppress delivery

### Pitfalls

| Issue | Symptom | Fix |
|---|---|---|
| **Large list_memories output** | >200KB, saved to `/tmp/hermes-results/` | `cp /tmp/hermes-results/call_*.txt <target>.json` |
| **Inline result too large for context** | Response has a persisted-output block | Read the temp file path shown in the output |
| **write_file truncation** | Only first N chars written for large JSON | Use terminal `cp` from temp file instead of write_file for large payloads |
| **Missing bank directory** | cp fails silently | `mkdir -p infrastructure/hermes/banks/BANK_ID/` before processing |
| **Git divergence** | `git push` rejected | Always `git pull --rebase origin main` before add/commit/push |
| **Timeout on large banks** | Bank with 200+ facts takes long reflect | Set `max_tokens=2048` and `budget="mid"` for large banks, reserve `budget="high"` for active ones |
| **Sequential processing cost** | 16 banks x 3 API calls = 48 calls | Accept sequential — required per spec. |
| **Repetitive dormant bank summaries** | Inactive banks (witral, yacv, evidencia-zero) produce near-identical reflect output daily | Normal behavior. The retain still serves as a timestamped heartbeat. If the pattern becomes problematic, consider a once-weekly reflect for banks with >7 consecutive no-activity days. |
| **reflect budget=high timeout** | 300s MCP timeout on banks >500 facts under load | Retry with `budget=low` and `max_tokens=1024` — produces a shorter but adequate daily summary. **Update 2026-07-16:** `budget=mid` with `max_tokens=2048` now confirmed reliable across all 16 banks (including personal-buffer at 1,654 facts) with no timeouts. Reserve `budget=low` only if `mid` times out. |
| **reflect returns empty content** | `finish_reason=length`, empty `text` field — provider cut off mid-reflection | Retry with `budget=low`, `max_tokens=1024`. The shorter prompt reliably produces a summary. Happens occasionally on active banks with dense recent history (toolset-profile ~268 facts triggered it). This is a provider-side truncation, not a data issue. |
| **retain() call timeout** | retain() MCP call itself times out at 300s (observed with researchit ~226 facts, wwe-profile ~403 facts) | Retry once — the async operation is often still accepted server-side despite the MCP call timeout. A second attempt reliably succeeds. This is a MCP transport-level timeout, not a data loss event. |
| **Parallel list_memories causes "could not be saved"** | 3+ concurrent list_memories calls produce "Full output could not be saved to sandbox" for some responses | Do NOT batch more than 2 list_memories calls in parallel. Even small banks (witral, 58 facts, 116KB) fail in parallel batches of 3+. Serialize list_memories calls, or at most parallelize 2 at a time. reflect() and retain() calls are fine in larger batches since they have smaller payloads. |
| **execute_code BLOCKED in cron mode** | Error: "BLOCKED: execute_code runs arbitrary local Python... Cron jobs run without a user present to approve it." | Use terminal() with python3 -c '...' or python3 << 'PYEOF' heredocs for all data processing. The terminal tool is NOT blocked in cron mode. |

### Banks to skip

### Current bank inventory (as of 2026-07-18)

16 active banks. Fact counts change daily — banks requiring pagination: `personal-buffer` (~2,707 facts, 3 pages), `hermes` (~1,487 facts, 2 pages). All others fit in one page.

| Bank | Facts | Pages | Activity |
|---|---|---|---|
| personal-buffer | ~2,707 | 3 | Active staging area — fastest growing |
| hermes | ~1,487 | 2 | Orchestrator — active |
| wwe-profile | ~412 | 1 | Active (Raw/SD discussions) |
| personal-profile | ~259 | 1 | Curated KB |
| toolset-profile | ~268 | 1 | Active (infra sessions) |
| chat-profile | ~280 | 1 | Paused since 10 jul |
| researchit | ~233 | 1 | Stable V1.4, no dev |
| kairos | ~141 | 1 | Stable v4.0.0 |
| cl-concerts-db | ~151 | 1 | Paused since 24 jun |
| toolset | ~160 | 1 | Infrastructure facts |
| entrenador-profile | ~176 | 1 | Paused (1 session done) |
| evidencia-zero | ~91 | 1 | Seed, no activity |
| desarrollo-trazambiental-profile | ~90 | 1 | Paused since 9 jul |
| trazambiental-profile | ~91 | 1 | Paused since 9 jul |
| yacv | ~77 | 1 | Seed, no activity |
| witral | ~62 | 1 | Seed, no activity |

All 16 banks fit in a single sync run (~15-20 min wall clock at normal API speeds). Use `budget="mid"`, `max_tokens=2048` for all banks — no timeouts observed even on the largest ones.

**Reference:** `references/bank-sync-execution-notes.md` for session-specific export strategies and pagination notes.

## Personal-Buffer Feed Configuration

See `references/ci-cd-repo-commit-detection.md` for the state-file approach used to detect commits in CI/CD-managed repos (like toolset) and feed them into `personal-buffer`. Applied via modification to `repo-pull-cron.sh`.

## WhatsApp Group Context Injection

See `references/whatsapp-groups-context-injection.md` for the bridge-level injection that gives every profile awareness of all WhatsApp groups, their profiles, and repos. This prevents cross-profile routing errors (suggesting the wrong group for delegation).

## WhatsApp Bridge Lifecycle Management

The bridge (`bridge.js`) is the WhatsApp Web client that connects Hermes to WhatsApp. It runs as a **bare Node.js process** — no Docker, no systemd, no PM2.

### Identify the bridge

```bash
# Main bridge (port 3000)
ps aux | grep "bridge.js" | grep -v grep | grep -v tito

# If there's a secondary bridge for another profile (e.g., tito on port 3001):
ps aux | grep "bridge.js" | grep "port 3001"
```

The main bridge command:
```
/usr/bin/node /usr/local/lib/hermes-agent/scripts/whatsapp-bridge/bridge.js \
  --port 3000 \
  --session /home/opc/.hermes/whatsapp/session \
  --mode bot
```

### Check if it's running

```bash
curl -sf http://localhost:3000/health
# Response: {"status":"connected","queueLength":N,"uptime":SECONDS}
```

If the endpoint doesn't respond, the bridge is down.

### Start the bridge

```bash
terminal(
  command="/usr/bin/node /usr/local/lib/hermes-agent/scripts/whatsapp-bridge/bridge.js --port 3000 --session /home/opc/.hermes/whatsapp/session --mode bot",
  background=true,
  notify_on_complete=false   # server process, never exits
)
```

Important: do NOT restart via nohup/disown — the tool rejects shell-level background wrappers. Always use terminal(background=true).

### Pitfalls

| Action | What happens | Correct approach |
|---|---|---|
| `kill -HUP <pid>` | **Kills the process.** SIGHUP terminates Node.js, it does not reload or restart. | Use terminal(background=true) to start a fresh process |
| `kill -9 <pid>` | Force kills. Same outcome — process dies without cleanup. | Start a fresh process |
| `systemctl restart hermes-gateway` | Restarts the Hermes gateway AND the bridge (the bridge is spawned by the gateway as a child process). | Just restart — both come back. |
| Having BOTH user and system gateway services installed | `hermes gateway status` defaults to user service (stopped) while system service is active. Confusing status reports. | `hermes gateway uninstall` removes the user-level duplicate. |
| Expecting WhatsApp to replay missed group invitations after bridge restart | **They are NOT replayed.** Pending group invites received while the bridge was down are lost. | Someone must send a message in the group to trigger bridge discovery, or re-invite Hermes to the group |

### Tenant session logout and re-pairing

Applies when `monitor-tenants.sh` reports `<tenant>: WhatsApp bridge not listening on port N` every 5 minutes. The bridge is usually NOT simply down: it is in a crashloop. WhatsApp invalidated the session, the bridge starts, receives `Logged out`, dies, and the tenant gateway respawns it. The monitor samples a random point in that cycle, so the alert looks intermittent.

**Confirm the crashloop before touching anything** (a plain restart fixes nothing here):

```bash
grep -c "Logged out" ~/.hermes/profiles/<tenant>/whatsapp/bridge.log
# Repeated "Logged out" + "listening on port N" pairs = crashloop, not a dead bridge.

for i in $(seq 1 8); do ss -tlnp | grep -oP ':<port> .*pid=\K[0-9]+' || echo NINGUNO; sleep 9; done
# A PID that appears, vanishes, and comes back with a different number confirms it.

grep -o '"whatsapp":{[^}]*}' ~/.hermes/profiles/<tenant>/gateway_state.json
# "state":"disconnected" corroborates it.
```

Recovery requires re-scanning a QR from the tenant's phone. It cannot be automated, and for `tito` it costs the user a full manual cycle (reinstalling WhatsApp, swapping the SIM). Confirm the diagnosis first, and coordinate the moment: the QR expires in under a minute.

**Phase 1 (agent).** Stop the gateway and back up the session. `reset-failed` clears the `failed` state that a SIGTERM leaves behind:

```bash
systemctl --user stop hermes-gateway-<tenant>
systemctl --user reset-failed hermes-gateway-<tenant>
pkill -f "bridge[.]js --port <port>" || true
tar czf ~/<tenant>-session-backup-$(date +%Y%m%d-%H%M).tar.gz \
  -C ~/.hermes/profiles/<tenant>/whatsapp session
```

**Phase 2 (the user, in their own terminal).** The QR only renders reliably on a real TTY, so the agent hands over this command instead of running it. `--pair-only` connects, prints the QR, saves credentials and exits without opening the HTTP server, so it never fights the gateway for port `<port>`:

```bash
ssh -t opc@toolset-oci-1-1 '
  P=/home/opc/.hermes/profiles/<tenant>
  rm -rf "$P/whatsapp/session"
  /usr/bin/node /usr/local/lib/hermes-agent/scripts/whatsapp-bridge/bridge.js \
    --pair-only --session "$P/whatsapp/session"
'
```

Scan from *Linked devices*. A `stream:error` with `code: 515` right after scanning is expected: Baileys reconnects on its own. Done when `Pairing complete. Credentials saved.` prints and the process exits.

**Phase 3 (agent).** Restore service and verify:

```bash
systemctl --user start hermes-gateway-<tenant>
sleep 25
ss -tlnp | grep ":<port> "
curl -sf http://127.0.0.1:<port>/health
bash ~/.hermes/scripts/monitor-tenants.sh; echo "EXIT=$?"
```

Verify stability, not just that the port answers: sample the PID for 90 seconds and confirm it does not change. A crashloop also produces a listening port, just not for long. Check that the gateway relaunched the bridge with `--mode bot` (the pairing run defaults to `self-chat`, which rejects everything with `self_chat_mode_rejects_non_self`). `EXIT=0` with no output from the monitor closes the incident.

| Pitfall | What happens | Correct approach |
|---|---|---|
| `pkill -f "bridge.js --port 3001"` inside an `ssh '...'` command | **It kills the SSH shell itself.** `-f` matches the full command line, and the remote shell carries that same text in its own argv. The connection closes with no output and `\|\| true` does not help: the shell was signalled, not failed. | Break the self-match with a character class: `pkill -f "bridge[.]js --port 3001"` |
| Restarting the gateway to fix `Logged out` | The bridge comes back and dies again. Restarting never re-authenticates. | Re-pair (Phase 2). Only a QR scan restores the session. |
| Deleting `session/` before the user has the phone ready | The QR expires in under a minute and the tenant is left with no session and no one to scan. | Back up first, and delete only at the moment of pairing |
| Running `--pair-only` while the gateway is up | Two Baileys clients on the same session directory. | Stop the gateway first (Phase 1) |

### New group discovery

When Hermes is added to a new WhatsApp group:

1. WhatsApp sends a group-add notification through the WebSocket
2. The bridge's Baileys client processes it and updates internal state
3. The `channel_directory.json` is updated (the bridge writes it)
4. `populate-channel-aliases.sh` reads `channel_directory.json` and writes `channel_aliases.json`
5. The cron job runs this every 10 minutes — or run it manually: `bash ~/.hermes/scripts/populate-channel-aliases.sh`

If the group doesn't appear after running the script:
- The bridge may not have received the notification yet (recent reconnection)
- **Workaround:** Someone sends any message in the group — the bridge receives it and discovers the group
- **Alternative:** Ask the user for the JID directly and proceed with manual onboarding

The bridge's channel_directory.json is at `~/.hermes/channel_directory.json`. The channel_aliases.json is at `~/.hermes/channel_aliases.json`.

## Health Checks

### Services Quick-Reference

| Service | Command |
|---|---|
| All Docker containers | `docker ps --format "table {{.Names}}\t{{.Status}}"` |
| Infisical | `curl -sf http://localhost:8081/api/status` |
| Caddy | `curl -sf http://localhost:8080/` (serves landing page) |
| hermes-gateway | `systemctl is-active hermes-gateway` | Cruza con `ps aux | grep hermes.*gateway` — puede estar vivo fuera de systemd. Si Hermes no responde, ver `references/gateway-crash-diagnosis.md`. |
| hermes-webui | `systemctl is-active hermes-webui` |
| WhatsApp Bridge | `curl -sf http://localhost:3000/messages` (returns `[]` when up) |
| SearXNG | `curl -sf http://localhost:4000` |

### Gateway Crash Diagnosis (SIGKILL Pattern)

When the user reports service disruption without a clear CI/CD failure, the most common cause is the gateway restarting via `restart-gateway.sh`. The symptom is health check failures that self-resolve on the next run.

**Causa raíz (descubierta 2026-07-19):**
Los SIGKILL "on client request" NO son crashes espontáneos ni OOM. Son causados por `restart-gateway.sh`
(`sudo systemctl restart hermes-gateway`) que se ejecuta al final de cada ciclo de `hermes-sync` (sync-hermes-to-repo.sh
o hermes-sync-banks). El flujo es:

1. El cron hermes-sync corre (triggered por push a main, ~02:30 UTC / ~22:30 CLT)
2. Ejecuta tareas: list_memories, reflect, retain, skill_manage, etc. (algunas fallan por escape-drift o timeout MCP)
3. Al terminar el ciclo, ejecuta `restart-gateway.sh` para que los cambios (skills, config) surtan efecto
4. `sudo systemctl restart hermes-gateway` envía SIGTERM al proceso principal
5. Si los procesos child (node bridge) no terminan limpiamente dentro del TimeoutStopSec (210s), systemd
   los mata con SIGKILL
6. A veces ocurre un **double-kill**: el primer restart (step 4-5) deja procesos node colgados, y el nuevo
   proceso también recibe SIGKILL ~40s después

**Cómo confirmar que un SIGKILL fue restart planeado vs crash inesperado:**

- Look for the **cron job context** before the kill. En journalctl, busca actividad de hermes-sync minutos antes:
  `WARNING agent.tool_executor: Tool skill_manage returned error`
  `hermes-sync: banks/file artifacts` en los commits de git
- Los kills planeados ocurren en **pares** (double-kill) separados por ~40s
- Los kills ocurren consistentemente después de pushes de hermes-sync (verificar con `git log`)

**Detection:**
```bash
journalctl -u hermes-gateway --since "YYYY-MM-DD 00:00:00" --until "YYYY-MM-DD 23:59:59" --no-pager

# Count SIGKILL events:
journalctl -u hermes-gateway --since "..." --until "..." | grep -c "killed, status=9/KILL"

# Show context around each kill:
journalctl -u hermes-gateway --since "..." --until "..." | grep -B5 "killed, status=9/KILL"
```

**Key indicators:**
- `Sent signal SIGKILL to main process ... on client request` — the kill was requested by a client (Hermes itself, a script, or a cron job), NOT the OOM killer. OOM kills say `out of memory` in the journal, not `on client request`.
- The gateway is systemd-managed with `Restart=always`, so it comes back within ~5s (restart counter shows as `restart counter is at 1` after a crash).
- Typical memory peak is ~360MB — well within the 12GB VM. Do not assume OOM unless the journal explicitly mentions it.

**Correlating with CI/CD health check failures:**

When a Health Check workflow fails:
1. Note the exact UTC timestamp from the failed run: `gh run view <ID> --repo kirlts/toolset --log-failed | grep "Check.*UNKNOWN STEP" | head -1`
2. Query gateway logs for that window: `journalctl -u hermes-gateway --since "<timestamp - 5min>" --until "<timestamp + 5min>"`
3. If you find SIGKILL events within that window, the health check failure is a **secondary symptom** of the gateway restart — the gateway crash took Caddy down momentarily, and Caddy hadn't recovered by the time the GitHub runner probed the public endpoint.
4. If you find NO gateway crash, investigate Caddy or provider issues separately.

**Pitfalls:**
- Gateway crashes often cluster: 2-3 kills close together as systemd's restart loop fires. A count of 8+ in 3 days warrants attention but most are **planned restarts** from hermes-sync.
- The `caddy-selfheal` script (see below) only checks `localhost:8080`. If the gateway restart also resets Caddy's internal state, the public domain endpoint may still return 000 even though the selfheal script considers Caddy healthy. The selfheal log at `/tmp/caddy-selfheal.log` is empty when no intervention was needed — an empty log does NOT mean Caddy was healthy from the public perspective.
- The provider (`deepseek-v4-flash` via OpenCode Go) can independently fail with `Broken pipe` during the same window, compounding the problem. Check for `[Errno 32] Broken pipe` in gateway logs around the same time.

**Reference:** `references/gateway-restart-loop-analysis-2026-07-19.md` — análisis completo con cronología de eventos, comandos de investigación, y líneas de acción.

### Comprehensive Health Check (5-axis)

Run this when asked for a "health check" or "revision de salud":

1. **CI/CD**: `gh run list --repo kirlts/toolset --limit 3` — check last 3 workflow conclusions. If any failed, inspect logs: `gh run view <ID> --repo kirlts/toolset --log-failed`. Check whether subsequent runs already fixed the issue before proposing a fix — the hermes-sync cron often pushes commits that fail CI validation and the next commit already resolves it.
2. **WhatsApp**: Two complementary methods:
   - **Bridge liveness**: `curl -sf http://localhost:3000/messages` — HTTP 200 = alive.
   - **Pending message detection via state.db**: Query `state.db` sessions where `source LIKE '%whatsapp%'` and `started_at > (now - 12h)`. For each session, check if the last message's role is `'user'` — this means the user sent something that may need a response. Cross-reference sequential sessions with similar titles. See `references/health-check-state-db-queries.md` for exact SQL.
   - **Check for undecryptable messages**: grep bridge.log for `No session found` in the last 12h — indicates lost messages. See `references/whatsapp-bridge-decryption-failures.md`.
   - `recall(bank_id="toolset-profile", query="pending, todo, pendiente, tarea", max_tokens=4096, budget="mid")` — operational tasks from toolset profile sessions
   - `recall(bank_id="toolset", query="pending, todo, pendiente, tarea", max_tokens=4096, budget="mid")` — infrastructure-level decisions and tech debt (secret migration, bridge patches, etc.)
   - `recall(bank_id="hermes", query="pending, todo, pendiente, tarea", max_tokens=4096, budget="mid")` — orchestrator-level tasks, stalled user-dependent items
   - `reflect(bank_id="hermes", budget="low", max_tokens=2048, query="¿Hay tareas, solicitudes o cambios pendientes que Hermes deba ejecutar autónomamente y no haya ejecutado?")` — `reflect` often surfaces synthesis-level findings that raw `recall` misses (e.g., "personal-buffer primera revisión nunca ejecutada").
   Cross-reference pending memory entries against actual filesystem/state — old entries (4+ days) that no longer reflect reality should be flagged as **stale** and optionally invalidated.
   **Note on stale entries:** Entries carried through 4+ consecutive health checks without change are expected — they indicate blocker items waiting on user input (e.g. "gateway pre-processor espera decision del usuario"). Do not flag these as degraded unless the underlying decision or dependency has been resolved.
4. **Docker services**: `docker ps --format "table {{.Names}}\t{{.Status}}"` — all should be `Up` and `(healthy)`. **Pitfall:** `systemctl is-active <container>` returns `NOT RUNNING` for Docker services even when they're healthy — they're managed by Docker, not systemd. Always use `docker ps` to check container health. Check hermes-gateway and hermes-webui via `systemctl` since those ARE systemd services.
5. **Host resources**: `free -h`, `df -h /`, `uptime`, `cat /proc/loadavg`

### Reporting Protocol

Health checks are **requested inspections** — unlike continuous monitoring (which follows state-transition reporting: silent-on-OK), health checks always produce a report because the user explicitly asked for one.

| Result | Report |
|---|---|
| All OK | Brief single-paragraph summary confirming each axis |
| Issues found | Detail per axis with diagnostics and suggested remediations |
| Partial data | Report what you found and what you couldn't verify, with the reason |

When running as a cron job: the final response is automatically delivered. Do NOT use `send_message`. If genuinely nothing exists to report (no axes were checked because the skill itself couldn't run), respond with `[SILENT]` to suppress delivery.

### Cron Mode Constraints

- `execute_code` is BLOCKED in cron mode (no user present to approve arbitrary Python). Use `terminal()` for data processing instead — pipe through `python3 -c '...'` inline.
- The WhatsApp bridge (`/usr/local/lib/hermes-agent/scripts/whatsapp-bridge/bridge.js`) uses Baileys (WhatsApp Web protocol). **No REST API for message querying exists** — it's a push-only system. For health checks, only liveness can be confirmed via HTTP.
- Bridge has a known non-critical: `link-preview-js` package missing from Baileys dependencies (URL preview generation fails, messaging works). Do not flag as service-down.

### Stale Memory Detection During Health Checks

1. For each entry dated 4+ days ago, verify against current files/state
2. Common stale patterns:
   - `deploy.sh changes pending` when CI/CD runs pass clean
   - References to deleted files that were restored in later commits
   - TODO items marked complete in the repo but not cleaned from memory
   - ResearchIt PDFs or generated artifacts referenced in `vault/` that were subsequently cleaned up from disk (files deleted after 4+ days by OS cleanup or manual removal)
3. If stale → note in report but do not delete. Flag for user review.
4. After the health check, `retain(bank_id="toolset-profile")` with the check result for traceability

## Profile Configuration

Cada perfil de Hermes puede tener su propia configuración de modelo, providers, y otros ajustes. La configuración por perfil es útil cuando diferentes grupos de WhatsApp necesitan diferentes modelos o comportamientos.

### Cambiar el modelo de un perfil

```bash
hermes config set --profile <name> model.default <provider>/<model>
```

Ejemplo (toolset cambiado a deepseek-v4-pro el 2026-07-19):
```bash
hermes config set --profile toolset model.default opencodego/deepseek-v4-pro
```

Esto crea (o actualiza) `~/.hermes/profiles/<name>/config.yaml` con solo las secciones modificadas.
El cambio es inmediato — no requiere restart del gateway.

### Modelos disponibles en OpenCode Go

Listar modelos disponibles:
```bash
curl -s https://opencode.ai/zen/go/v1/models | python3 -c "import sys,json; data=json.load(sys.stdin); [print(f['id']) for f in data.get('data',data if isinstance(data,list) else [])]"
```

A 2026-07-19, los modelos relevantes son:
- `deepseek-v4-pro` — modelo premium (usado por toolset desde 2026-07-19)
- `deepseek-v4-flash` — modelo rápido (default global)
- `glm-5.2` — usado por perfil personal
- `mimo-v2-omni` — usado para visión

### Sincronización con el repositorio

**⚠️ sync-hermes-to-repo.sh NO cubre profiles.** Los config.yaml de perfiles
(`~/.hermes/profiles/<name>/config.yaml`) no se copian al repositorio toolset
por el sync automático. Si haces un cambio de configuración en un perfil y quieres
versionarlo, debes:

1. Copiar manualmente el archivo al repo: `cp ~/.hermes/profiles/<name>/config.yaml /opt/toolset-repo/infrastructure/hermes/profiles/<name>/config.yaml`
2. Committear via Kilo CLI o directamente si es una operación de sync
3. O modificar sync-hermes-to-repo.sh para que incluya profiles

**Decisión pendiente (2026-07-19):** Martín evaluó si agregar profiles al sync script.
Hasta que se decida, los cambios de perfil existen solo en local.

Todos los bancos de perfil siguen el patrón `<profile>-profile`. El banco `hermes` es la unica excepcion (no tiene sufijo).

| Perfil | Bank correcto | Estado |
|---|---|---|
| Personal | `personal-profile` | Correcto |
| Chat | `chat-profile` | Correcto |
| Toolset | `toolset-profile` | Canonico (0 facts, banco fresco iniciado 2026-07-05 post-refactor) |
| WWE | `wwe-profile` | Correcto |

**Reglas:**
- `docs/RULES.md` define la convencion `<profile>-profile`. Sin excepciones.
- El template de perfil (`.agents/templates/profile-soul.md`) usa `{BANK_ID}` que debe poblarse con `<profile>-profile`.
- `docs/RULES.md` dice "use repo name as bank_id, kebab-case" — esto ESTA DESACTUALIZADO. La convencion correcta es `<profile>-profile`.
- La unica excepcion es `bank="hermes"` (orquestador).

## Recall Budget Policy (CANONICAL)

Toda llamada a `recall()` DEBE especificar `max_tokens` y `budget` explicitamente para evitar flooding de contexto:

| Contexto | max_tokens | budget | Razon |
|---|---|---|---|
| Hermes (perfiles) | 4096 | `mid` | Suficiente para contexto operativo sin saturar |
| Hermes (orquestador, bank hermes) | 4096 | `mid` | Idem |
| Kilo CLI (recall de inicio) | 1024 | `low` | Solo necesita contexto minimo del proyecto |
| Health checks | 8192 | `mid` | Mas permisivo porque es lectura dedicada |

**Prohibido:** usar `budget="high"` o `max_tokens=16384` como default. Esto devolvio >600KB del banco `toolset` en una sola llamada, saturando el LLM context.

**Referencia:** Ver `references/recall-budget-policy.md` para el analisis completo del incidente que motivo esta politica.
