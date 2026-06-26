---
name: infrastructure-deployment
description: "CI/CD pipeline management, deploy failure diagnosis, self-healing, and proactive communication for infrastructure changes."
version: 1.3.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [deploy, cicd, infrastructure, docker, self-healing, communication]
    related_skills: [systematic-debugging, github-pr-workflow]
---

# Infrastructure Deployment

## Overview

Managing infrastructure deployments involves more than running commands. It requires diagnosing failures, self-healing when possible, and proactively communicating status to the user.

**Core principle:** Deploy failures must be diagnosed, fixed, and reported within 30 minutes. Silence is not an option.

## ⚠️ CRITICAL: Pre-flight Context — DO THIS FIRST

**Antes de CUALQUIER acción** relacionada con deploy, pipeline CI/CD, notificaciones de deploy, o infraestructura del Toolset:

1. Ejecuta `recall(bank="toolset", query="infraestructura, despliegues recientes, estado del pipeline, notificaciones")`
2. Si el usuario mencionó un repo específico (kairos, cl-concerts-db, etc.), haz recall también de su bank
3. Solo después de tener contexto completo, empieza a trabajar

**Por qué es obligatorio:** El bank toolset contiene estado del pipeline, últimas ejecuciones, issues conocidos, y decisiones técnicas. Trabajar sin este contexto = repetir errores y dar respuestas incompletas. Fue instrucción directa del usuario.

**Esto NO es opcional.** Si empiezas a diagnosticar, investigar, o proponer soluciones sin recall previo, estás violando la regla.

## Deploy Pipeline Architecture

### Typical CI/CD Flow

```
Push to main → GitHub Actions:
  1. validate-configs (syntax + schema validation)
  2. OpenTofu Infrastructure (IaC)
  3. Deploy Services (Docker Compose via SSH)
```

### Common Failure Points

| Failure | Symptom | Diagnosis |
|---------|---------|-----------|
| **Config validation** | JSON/YAML parse error | Check for // in URLs, trailing commas, control chars |
| **Port conflict** | "address already in use" | Check if WebUI or other service binds the same port |
| **Container name conflict** | container name already in use | Container from prior deploy wasnt cleaned up |
| **API key expired** | Missing API key / Invalid API key | Key in .env doesnt match credential pool |
| **Docker compose down** | Stops running containers | Must stop conflicting services first (e.g. WebUI) |
| **Hindsight startup timeout** | dependency failed to start: container hindsight is unhealthy | HuggingFace model download (BAAI/bge-small-en-v1.5) times out on first attempt |
| **Cascading dependency failure** | Downstream service (caddy) stays Created while upstream (hindsight) eventually becomes healthy | Compose dependency check fired before hindsight recovered via restart policy |

## Deploy Failure Diagnosis Protocol

### Step 1: Identify the Failing Job

```
gh run list --repo <repo> --limit 1 --json status,conclusion
gh run view <run-id> --repo <repo> --log-failed | tail -30
```

### Step 2: Classify the Failure

- **Config/syntax error** → fix file, push commit
- **Infrastructure error** → check OpenTofu state, OCI API
- **Service deploy error** → check Docker, port conflicts, container names

### Step 3: Apply Fix

#### Port Conflicts
When `docker compose up` fails with "address already in use":
1. Stop the service occupying the port: `sudo systemctl stop <service>`
2. Run `docker compose up -d --remove-orphans --force-recreate`
3. Restart the stopped service: `sudo systemctl start <service>`
4. The deploy.sh should encode this pattern automatically

#### Container Name Conflicts
When `docker compose up` fails with "container name already in use":
1. Remove the conflicting container: `sudo docker rm -f <container-name>`
2. Use `--force-recreate` flag: `docker compose up -d --remove-orphans --force-recreate`

#### Cascading Dependency Failures

When `docker compose up -d` succeeds partially — some services are healthy but downstream services (e.g. caddy) stay in `Created` state:

**Symptom:** `docker compose ps` shows the downstream service as `Created` while its dependency shows `Up` and healthy. This happens when the dependency failed health checks during the initial compose run, then recovered via its restart policy, but compose's dependency resolution already gave up.

**Root cause:** Docker Compose evaluates `depends_on` conditions once during startup. If hindsight (for example) fails its health check on first attempt and the container enters a restart loop, compose marks the dependency as failed and never starts caddy — even if hindsight later recovers.

**Diagnosis:**
- `docker compose ps --all` — look for services in `Created` (not `Up`)
- `docker inspect <service> --format '{{.State.Status}} {{.State.Health.Status}}'` — check if the dependency is now healthy
- Check the dependency's logs for the original failure: `docker logs --tail 30 <dependency>`

**Fix:**
Once the dependency service is running and healthy, start the stuck downstream service:
```bash
cd /opt/toolset
docker compose up -d <downstream-service>   # e.g. caddy
```
This runs docker compose's dependency resolution again against the already-running healthy services, skipping the one that previously failed.
### API Key Issues

When Kilo CLI or Hermes gets "Missing API key":
1. Check if the env var is exported to the shell (not just in .env)
2. Verify the key works: `source .env && curl -H "Authorization: Bearer $KEY" https://api.example.com/v1/models`
3. If key is expired, rotate via GitHub Secrets → Infisical

### Infisical API Call Missing Parameters (known bug)

When a script in deploy.sh reads from Infisical API and the secrets come back empty:

**Symptom:** `config.yaml` has `PLACEH...PLOY` as `x-consumer-api-key` for MCP composio server.

**Root cause:** The API call `http://localhost:8081/api/v3/secrets/raw/COMPOSIO_MCP_KEY` is missing `?workspaceId=<ID>&environment=prod` query params. Infisical v3 requires these parameters — without them it returns `400 Missing environment`, the exception is caught, and the secret value defaults to empty string.

**Fix:** Add the query parameters to the URL. The `workspaceId` can be obtained from the service token info endpoint (`/api/v2/service-token`) or hardcoded from the known project ID.

**Diagnosis:**
```bash
grep 'x-consumer-api-key' /home/opc/.hermes/config.yaml
# → PLACEH...PLOY means injection failed
```

**Full reference in:** `references/secret-flow-infisical.md`.

## ⚠️ CRITICAL: Secret Flow Architecture — DO NOT BREAK OR BYPASS

**Regla inviolable del flujo de secretos en Toolset:**

```
GitHub Secrets → Infisical (vía sync_secret) → VPS lee de Infisical
```

**NUNCA hagas esto:**
- ❌ Pasar secrets de GitHub Actions a través de SSH como env vars
- ❌ Leer secrets directamente de GitHub Secrets en el VPS
- ❌ Editar config.yaml, .env o cualquier archivo con secrets manualmente en el VPS
- ❌ Hardcodear API keys o tokens en código o config
- ❌ Leer .env con cat/grep/read_file para diagnosticar (la fuente de verdad es Infisical, no el archivo)

**SIEMPRE haz esto:**
- ✅ Los secrets se escriben en Infisical durante el deploy vía `sync_secret` en deploy.sh
- ✅ Scripts en el VPS leen de la API local de Infisical (`localhost:8081`) usando `INFISICAL_SERVICE_TOKEN`
- ✅ El token de servicio de Infisical está en `/opt/toolset/.env` (único .env permitido)
- ✅ Para leer un secreto desde el VPS:
  ```python
  import os, json, subprocess
  token = ''
  with open('/opt/toolset/.env') as f:
      for line in f:
          if line.startswith('INFISICAL_SERVICE_TOKEN='):
              token = line.split('=', 1)[1].strip()
              break
  if token:
      r = subprocess.run(['curl', '-s', 'http://localhost:8081/api/v3/secrets/raw/SECRET_NAME?workspaceId=<ID>&environment=prod',
          '-H', f'Authorization: Bearer {token}'], capture_output=True, text=True, timeout=10)
      if r.returncode == 0:
          data = json.loads(r.stdout)
          secret_value = data.get('secret', {}).get('secretValue', '')
  ```

**⚠️ Consecuencia de violar esta regla:** El usuario fue explícito: "si empiezas a mezclar la forma en la que se provisionan los servicios o en la que se inyectan los secretos vas a cometer errores fatales."

### 🔧 Inline Python en SSH: Bug de escaping (KNOWN)

NUNCA pongas scripts Python inline dentro de `ssh host "python3 -c '...'"`. Las
f-strings de Python se rompen con el anidamiento de quotes de bash, causando
fallos silenciosos.

**Síntoma:** El script corre pero falla calladamente, la excepción se captura,
y la variable queda vacía. Nadie se entera.

**Fix:** Script standalone, transferido y ejecutado:
```bash
scp script.py host:/tmp/script.py
ssh host "python3 /tmp/script.py; rm -f /tmp/script.py"
```

El repo tiene `infrastructure/hermes/inject-composio-key.py` como ejemplo. Para
cualquier script que lea de Infisical o modifique config.yaml desde deploy.sh,
usa este patrón.

### 🔧 Post-Inyección de Keys MCP: Gateway Restart Obligatorio

**Problema detectado (25 Jun 2026):** El pipeline de deploy inyecta `COMPOSIO_MCP_KEY`
en `config.yaml` vía `inject-composio-key.py`, pero el gateway `hermes-gateway`
NUNCA se reinicia después. Como las conexiones MCP se cargan al iniciar el gateway
(y se cachean en memoria), el gateway sigue usando la key vieja. `/new` no ayuda
— las sesiones heredan las tools del gateway existente.

**Fix idempotente en deploy.sh:** Después de cualquier script que modifique
`mcp_servers` en config.yaml, agregar:
```bash
sudo systemctl restart hermes-gateway
```

**⚠️ No se puede hacer desde dentro del gateway.** El gateway bloquea
`systemctl restart hermes-gateway` porque SIGTERM mata al comando antes de
completar. Soluciones:
- **Cronjob no_agent:** `cronjob action=create no_agent=true script="sudo systemctl restart hermes-gateway"`
- **systemd-run:** `sudo systemd-run --unit=hermes-restart sudo systemctl restart hermes-gateway`
- **SSH externo:** Ejecutar desde fuera del VPS

**Verificación post-restart:**
```bash
journalctl -u hermes-gateway --no-pager | grep -E "(composio|MCP)"
# Debe mostrar: MCP server 'composio' connected successfully (sin 401)
```

**Referencia completa:** `toolset-mcp-integration/references/gateway-restart-requirement.md`

## ⚠️ CRITICAL: Config Changes Go Through Repo + CI/CD

**Reglas:**
1. **INFRA-04 (derivado de CI-CD-01):** Todo cambio en config.yaml, deploy.sh, docker-compose.yml, o cualquier archivo de infraestructura del Toolset debe hacerse EXCLUSIVAMENTE a través del repositorio + CI/CD.
2. **NUNCA edites archivos de configuración directamente en el VPS** (ni config.yaml, ni .env, ni deploy.sh).
3. El flujo correcto es: `repo → commit → push → GitHub Actions → deploy.sh → VPS`
4. Excepción: puedes correr `docker compose up -d` manualmente para restaurar servicios después de un deploy fallido, pero el fix debe ir al repo.

**Pasos cuando necesitas cambiar configuración:**
1. Clona/actualiza el repo: `cd /tmp/toolset && git pull`
2. Crea rama: `git checkout -b hermes-fix-<description>`
3. Haz el cambio
4. Commit + push: `git add && git commit && git push`
5. PR + merge: `gh pr create && gh pr merge`
6. Espera el deploy CI/CD

## Investigate Before Implementing

Cuando el usuario pide resolver un problema técnico (especialmente de infraestructura, CI/CD, o secretos):

1. **Primero investiga** con ResearchIt (SearXNG verificado, --max-sources 30)
2. **Lee la documentación** del repo (docs/, MASTER-SPEC.md, CHANGELOG.md, USER-DECISIONS.md)
3. **Diagnostica la causa raíz** (no adivines la solución)
4. **Propón la solución** basada en la evidencia
5. **Solo entonces implementa**

**Anti-patrón:** Implementar polling cuando el usuario pidió hooks. Implementar un fix sin entender el flujo de secrets. Editar config.yaml sin pasar por el repo.

## Self-Healing Rules

1. **Diagnose before reporting** — understand the failure before telling the user
2. **Fix what you can** — config errors, container conflicts, script fixes are in scope
3. **Escalate what you cannot** — expired API keys, OCI API down, GitHub Actions outage
4. **Update after each step** — not just a final conclusive message. Send what you found, what you tried, what worked.

## Communication Protocol

### ⚠️ REGLA DE ORO: Updates REGULARES durante monitoreo

El usuario EXIGE actualizaciones CADA VEZ que completes un paso relevante durante tareas de monitoreo, deploy, o diagnóstico. No esperes al resultado final.

**Esto NO es opcional.** El usuario lo ha corregido múltiples veces. Cada tool call que produzca un resultado relevante = update inmediato al usuario.

### Mandatory Rules

- **Every user message gets a direct text response.** Command output alone is not a response.
- **Updates REGULARES durante monitoreo.** Cada paso completado = notificación. NO esperar al resultado final.
- **Be conclusive.** Complete the task. "I will do X" is not a valid response — do X, then report.
- **Pipeline failures: report immediately.** No 30-minute silence.
- **Health checks: run daily at 04:00 UTC.** Check CI/CD status, pending messages, service health, pending tasks.
- **NUNCA digas "mil disculpas" o "perdón".** El usuario detesta las disculpas vacías. En vez de disculparte, arregla la causa raíz (instrucciones internas, skills, memory) para que el error no se repita.

### Response Format for Failures

```
Problema: [one line]
Causa raíz: [one line]
Fix: [one line]
Estado: ✅ Todo verde | ❌ [what remains]
```

### Anti-patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| [silence >30 min on failed deploy] | Send update after each relevant step |
| "I will check the logs" | Check logs, then report |
| [only posts command output] | Write a text summary |
| "Let me try X" | Try X, then report result |
| "Mil disculpas" / "Perdón" | Fix the root cause (update skill/memory) |
| Wait for deploy to finish to report | Send updates: PR created → CI started → deploy running → verify result |

## Infrastructure Patterns

### Docker Compose Deploy with Port Conflicts

When deploying services that share ports with system services (e.g., WebUI on port 8888 and Hindsight on port 8888):

```bash
# Stop conflicting services
sudo systemctl stop hermes-webui 2>/dev/null || true

# Deploy
cd /opt/toolset
sudo docker compose down --remove-orphans
sudo docker compose up -d --remove-orphans --force-recreate

# Restart conflicting services
sudo systemctl start hermes-webui 2>/dev/null || true
```

This pattern is now encoded in deploy.sh. If adding new services, check for port conflicts during code review.

### Bank Provisioning / Hindsight

Every repository gets a Hindsight bank named after the repo. Banks are:
- Created in Hindsight on first deploy
- Exported as JSON daily via `hermes-sync-banks` cron
- Provisioned from repo directory `infrastructure/hermes/banks/` on each deploy
- The deploy.sh loop reads `$(ls infrastructure/hermes/banks/)` dynamically

#### SearXNG — Config Pitfalls

**Problema 1: "settings.yml not valid"** — Container fails to start.

**Root cause:** The container generates a default settings.yml from a template, but the template produces invalid config on certain platforms (ARM64/OL9 with SELinux).

**Fix:** Mount a pre-configured settings.yml from the researchit repo:
```yaml
volumes:
  - /opt/researchit/searxng:/etc/searxng:rw
```
Then:
```bash
cd /opt/toolset && sudo docker compose up -d searxng --force-recreate
```

**Problema 2: "KeyError: 'default_doi_resolver'"** — Container starts but `/search` returns 500.

**Root cause:** SearXNG >=2026.6.24 requiere `default_doi_resolver` y `doi_resolvers` a root level del settings.yml (no bajo `search:`). Ver `references/searxng-settings-doi-resolver.md` en la skill researchit.

#### Hindsight Startup Pitfall: Model Download Timeout

On first startup (or after `--force-recreate`), Hindsight downloads two SentenceTransformer models from HuggingFace Hub:
- `BAAI/bge-small-en-v1.5` (embeddings)
- `cross-encoder/ms-marco-MiniLM-L-6-v2` (reranker)

The download happens during the health check `start_period` (60s in the compose file). If the download takes longer than the health check retries + interval allow, or if HuggingFace Hub is slow/unreachable, the health check fails and the container is marked unhealthy. Compose then reports `dependency failed to start: container hindsight is unhealthy`.

**Behavior:**
- `restart: unless-stopped` will automatically restart the container, and the model cache from the failed attempt may speed up the next try.
- If the download succeeds on retry, the container becomes healthy — but any downstream service that depended on `hindsight: condition: service_healthy` (e.g. caddy) will NOT start automatically (see "Cascading Dependency Failures" above for the fix).

**Verification:** Check `docker logs hindsight` for lines containing `Loading SentenceTransformer model` and `Embeddings: initializing` — these indicate the model download is in progress.

### Health Check Cron (04:00 UTC)

A daily cron job (`hermes-health-check`) performs:
1. Check last 3 CI/CD runs for failures
2. Check for unanswered user messages
3. Check service health (Docker containers)
4. Report to user via WhatsApp if anything is wrong
5. Self-diagnose if there are pending tasks

### Deploy Watch — Notificación Automática de Fallos

En lugar de monitorear activamente los deploys, Hermes corre un watcher que detecta fallos automáticamente y notifica por WhatsApp.

**Implementación:** cron job `hermes-deploy-watch` (job_id=9d95e690ba92, cada 3 min) con `no_agent=True`:

- Script en `~/.hermes/scripts/deploy-watch.sh`
- Corre `gh run list --repo kirlts/toolset --limit 1 --json number,conclusion,displayTitle`
- Compara con `/tmp/hermes-deploy-last-run` para evitar notificaciones duplicadas
- **Silencio si todo OK** (no emite stdout = sin mensaje)
- **Notifica solo si hay un nuevo fallo** (emite stdout = se entrega por WhatsApp)
- **Tracking de runs exitosos** también para no re-notificar deploys viejos

**Script (`deploy-watch.sh`):**
```bash
#!/bin/bash
LAST_RUN_FILE="/tmp/hermes-deploy-last-run"
RUN_INFO=$(gh run list --repo kirlts/toolset --limit 1 --json number,conclusion,displayTitle)
RUN_NUM=$(echo "$RUN_INFO" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['number'])")
RUN_CONCLUSION=$(echo "$RUN_INFO" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['conclusion'])")
RUN_TITLE=$(echo "$RUN_INFO" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['displayTitle'])")
LAST_NOTIFIED=$(cat "$LAST_RUN_FILE" 2>/dev/null || echo "")
[ "$RUN_NUM" = "$LAST_NOTIFIED" ] && exit 0
echo "$RUN_NUM" > "$LAST_RUN_FILE"
[ "$RUN_CONCLUSION" = "failure" ] && echo "❌ Deploy #$RUN_NUM falló en toolset: $RUN_TITLE"
```

**Para crear el cron:**
```bash
cronjob action=create name="hermes-deploy-watch" schedule="every 3m" \
  script="deploy-watch.sh" no_agent=true deliver=origin
```

**Zero infra nueva:** usa `gh` CLI ya autenticado, no requiere endpoints HTTP, webhooks en GitHub, ni modificar el pipeline.

**Límite:** hasta 3 minutos de latencia (el intervalo del cron). Para notificación en tiempo real sin polling, usar GitHub webhooks (`references/github-webhooks-autonomous-monitoring.md`).

**⚠️ Preferencia del usuario:** El usuario pidió explícitamente hooks (webhooks), no polling. El cron es solución temporal. Migrar a webhooks (Opción 1 en la referencia) cuando sea posible.

## Related Skills

- `systematic-debugging` — for root cause analysis of failures
- `github-pr-workflow` — for PR and branch management
- `test-driven-development` — for test-first approach to fixes

## Reglas de Memoria

Esta skill trabaja con infraestructura y despliegues. Por lo tanto:

1. ⚠️ **Pre-flight (OBLIGATORIO — ver sección arriba):** Antes de empezar, ejecuta `recall(bank="toolset", query="infraestructura, despliegues recientes, estado del pipeline")`. Fue instrucción directa del usuario no omitir este paso.

2. **Post-action persist:** Al completar un deploy o diagnóstico, ejecuta `retain(bank="toolset", content="deploy: <commit>, resultado: ✅/❌, issues: <lista>", tags=["deploy", "YYYY-MM-DD"])`.
