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

## Cron Job Failure Diagnosis

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

## Health Checks

| Service | Command |
|---|---|
| Docker containers | `sudo docker compose -f /opt/toolset/docker-compose.yml ps` |
| Hindsight | `curl -sf https://${FUNNEL_DOMAIN:-toolset-oci-1-1.tail2d4c18.ts.net}/hindsight/health` |
| Infisical | `curl -sf http://localhost:8081/api/status` |
| Caddy | `curl -sf http://localhost:8080/health` |
| hermes-gateway | `systemctl is-active hermes-gateway` |
