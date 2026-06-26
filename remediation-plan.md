# Plan de Implementación: Corrección Sistémica de Hermes

## Contexto del Diagnóstico

Este plan aborda los 4 bugs reportados, cruzados contra la documentación oficial de Hermes (v0.17.0), el reporte forense del 25-Jun-2026, y la MASTER-SPEC del proyecto.

> [!IMPORTANT]
> **Adherencia a Patrones de IA (Abril 2026)**
> Toda instrucción en Markdown que gobierne a Hermes (`SOUL.md`, `CONTEXT.md`, Skills) será redactada aplicando rigurosamente los patrones de adherencia validados:
> 1. **English Latent Pivot**: Las reglas operacionales se redactarán 100% en inglés para evitar la penalización por traducción latente (CM-CoT) y evitar la dispersión semántica, aunque la identidad final hable en español.
> 2. **Declarative System Framing**: Se erradicarán los comandos imperativos ("Never do X"). En su lugar, se usarán afirmaciones declarativas de estado ("The system state prohibits X").
> 3. **Tabular Data Injection**: La lógica condicional se inyectará mediante tablas Markdown.
> 4. **Anti-AI Smell**: Se prohíbe el uso de paralelismos negativos ("Not just X, but also Y"), positividad servil y relleno transicional en el output de Hermes, alineado a `WikipediaSigns_of_AI_writing.txt`.

---

## Revisión Requerida

> [!IMPORTANT]
> **Separación SOUL.md vs AGENTS.md**: La documentación oficial de Hermes establece que SOUL.md es **solo para identidad/tono** (slot #1 del system prompt). Proyecto, reglas, y convenciones van en archivos de contexto como `AGENTS.md`. Actualmente el SOUL.md de Hermes tiene 93 líneas con reglas operacionales, tablas de capacidades, y arquitectura — contenido que debería ir en archivos de contexto. El plan propone separar ambos.

> [!WARNING]
> **Memoria nativa de Hermes es diminuta**: MEMORY.md = 2,200 chars (~800 tokens), USER.md = 1,375 chars (~500 tokens). Frozen snapshot al inicio de sesión. Confiar en Hermes para recordar reglas complejas via `memory tool` es inviable. La memoria vectorial de Hindsight es el canal correcto para conocimiento persistente (totalmente coherente con la filosofía Kairos), pero no reemplaza instrucciones determinísticas en archivos de contexto.
> 
> **Trigger de Consolidación Automática**: El agente implementador DEBE crear un mecanismo programático (ej. cron o script en background) que monitoree el tamaño de `MEMORY.md`. Cuando el archivo se acerque a su límite (ej. 80%), debe gatillar automáticamente una operación `reflect` + `retain` en el banco `toolset` para vaciar el buffer, sin darle otra carga de trabajo al LLM.

> [!CAUTION]
> **El deploy.sh actual no reinicia `hermes-gateway` tras cambios en SOUL.md/config.yaml**: El restart solo ocurre si el servicio *ya existe* (línea 525). Si SOUL.md o config.yaml cambian pero el servicio no se toca, Hermes sigue con la versión cached del inicio de sesión anterior.

---

## Preguntas Abiertas

> [!IMPORTANT]
> **¿Mover toolset al servidor?**: El bug #3 sugiere que Hermes no entiende su relación con el repo toolset porque no tiene acceso directo a él. Dos opciones:
> - **A)** Clonar `toolset` en `/opt/toolset-repo` en el server y apuntar `AGENTS.md` ahí (Hermes puede leer archivos del host)
> - **B)** Mantener la relación indirecta (deploy.sh sincroniza archivos individuales) y reforzar el contexto via SOUL.md + Hindsight
>
> El agente implementador DEBE configurar en `deploy.sh` un `git clone` idempotente del repo en `/opt/toolset-repo` + apuntar el context file ahí.
> 
> Además, el agente implementador DEBE clonar los repositorios de `researchit` y `markitdown` en `/opt/` (si no están ya), pues serán herramientas permanentes de nuestro stack.
> 
> **Justificación con Datos**: La documentación de Hermes advierte sobre el truncamiento por `context_file_max_chars` (típicamente 20k) si cargamos un solo system prompt masivo. Forzar el lenguaje mixto (Spanglish) aumenta los "thinking tokens" requeridos un 40%. Al tener el repositorio clonado localmente, evitamos embutir todo el repo en el prompt inicial; Hermes puede consultar la infraestructura nativamente, garantizando que el repo `toolset` sea explícitamente su IaC sin agotar su buffer.

> [!IMPORTANT]
> **¿Skills directory externo o skills dentro de `~/.hermes/skills/`?**: Hermes soporta `external_skills_dirs` en config.yaml. El agente implementador DEBE apuntar `external_skills_dirs` en `config.yaml` directamente a `/opt/toolset-repo/infrastructure/hermes-skills/` y a `/opt/toolset-repo/.agents/skills/`. Esto simplifica el mantenimiento y anula los comportamientos de sync de la implementación anterior.

---

## Cambios Propuestos

### Componente 1: SOUL.md — Refactorización

El SOUL.md actual viola la guía oficial de Hermes que dice "use it for durable voice and personality guidance" y "Use it less for: one-off project instructions, file paths, repo conventions, temporary workflow details."

#### [MODIFY] [Hermes-SOUL.md](file:///home/kirlts/toolset/infrastructure/Hermes-SOUL.md)

Reducir a ~40 líneas. Mantener solo:
- Identidad core estructurada usando el **Sistema Kairos (lingüística)**.
- Erradicación estricta de patrones anti-IA (`WikipediaSigns_of_AI_writing.txt`): cero "delve", cero "excellent question", cero relleno.
- **WhatsApp Tone**: Mensajes **ÚTILES** en lenguaje natural. Cero volcados crudos de tool calls; "No hay interés en ver sus tool calls como mensaje".

Mover al archivo de contexto del proyecto:
- Tabla de capacidades
- Arquitectura (backend, sandbox)
- Reglas (INFRA-01 a 03)
- Configuración de memoria (tools MCP)
- Plataforma (modelo, context_file_max_chars)

#### [NEW] [hermes-context.md](file:///home/kirlts/toolset/infrastructure/hermes-context.md)

Archivo de contexto del proyecto (~120 líneas). Se colocará como `.hermes/context.md` en el directorio home del proyecto en el servidor. Contiene:
- Tabla de capacidades operacionales
- Arquitectura del sistema (host OL9, Docker, gateway)
- Memoria: banco `hermes` en Hindsight, tools MCP
- Reglas INFRA-01, INFRA-03 e INFRA-04
- **Protocolo de Autonomía y Escalada (3 Tiers)**: 
  - *Tier 1 (Kilo CLI)*: Prevención programática y validación sintáctica/estructural. Bloquea sin intervención IA.
  - *Tier 2 (Hermes)*: Interviene con 99% de autonomía (`approvals: smart`) vía MCP para resolver heurísticas complejas que Kilo delegue.
  - *Tier 3 (Usuario)*: Escalada humana obligatoria EXCLUSIVAMENTE para decisiones pivotales, ambigüedad extrema o mutaciones destructivas en infraestructura.
- Convenciones de branches, merge criteria
- `context_file_max_chars: 25000`
- Referencia a MASTER-SPEC y RULES.md

---

### Componente 2: deploy.sh — Hardening del Pipeline

#### [MODIFY] [deploy.sh](file:///home/kirlts/toolset/infrastructure/deploy.sh)

**2a. Optimización del tiempo de ejecución (Deploy Optimization)**

El agente implementador DEBE investigar de forma autónoma oportunidades no riesgosas de optimización del tiempo de ejecución, observabilidad, arquitectura y buenas prácticas del deploy CI/CD.

**2b. Restart obligatorio de hermes-gateway tras cambios** de hermes-gateway tras cambios**

Actualmente el restart ocurre dentro del bloque condicional de systemd setup. Mover a un paso dedicado **después** de sincronizar SOUL.md, config.yaml, skills, y .env:

```bash
# --- Restart hermes-gateway (post-config changes) ---
echo "[DEPLOY] Restarting hermes-gateway..."
ssh "${SSH_HOST}" \
  "sudo systemctl kill -s KILL hermes-gateway 2>/dev/null || true; \
   sleep 1; \
   sudo systemctl reset-failed hermes-gateway 2>/dev/null || true; \
   sudo systemctl start hermes-gateway --no-block 2>/dev/null || true"
```

**2c. Verificación post-restart de gateway**

Agregar health check del gateway (verificar que responde en el puerto WebUI):

```bash
echo "[DEPLOY] Verifying hermes-gateway..."
for i in 1 2 3 4 5; do
  GW_STATUS=$(ssh "${SSH_HOST}" "systemctl is-active hermes-gateway 2>/dev/null")
  [ "$GW_STATUS" = "active" ] && break
  sleep 5
done
echo "  Gateway: $GW_STATUS"
```

**2d. Clonar toolset repo en el servidor (idempotente)**

```bash
echo "[DEPLOY] Syncing toolset repo on server..."
ssh "${SSH_HOST}" \
  "if [ -d /opt/toolset-repo/.git ]; then \
     cd /opt/toolset-repo && git pull --ff-only 2>&1 | tail -1; \
   else \
     sudo git clone https://github.com/kirlts/toolset.git /opt/toolset-repo && \
     sudo chown -R opc:opc /opt/toolset-repo; \
   fi"

*(Nota Técnica: La resolución de `SSH_HOST="${SSH_HOST:-opc@toolset-oci-1-1}"` es nativa al flujo CI/CD vía config SSH/Tailscale. **No requiere** añadir secretos extras de Github).*
```

**2e. Sincronizar context file al directorio de Hermes**

```bash
echo "[DEPLOY] Syncing Hermes context file..."
scp -q "Docs/CONTEXT.md" "${SSH_HOST}:/tmp/hermes-context.md"
ssh "${SSH_HOST}" \
  "sudo mkdir -p /home/opc/.hermes && \
   sudo cp /tmp/hermes-context.md /home/opc/.hermes/context.md && \
   sudo chown opc:opc /home/opc/.hermes/context.md"
```

**2f. Configurar external_skills_dirs apuntando al repo clonado**

En el bloque de configuración de Hermes runtime (línea 598+), agregar:

```python
cfg['external_skills_dirs'] = ['/opt/toolset-repo/infrastructure/hermes-skills', '/opt/toolset-repo/.agents/skills']
```

Esto elimina la necesidad del bloque tar/scp de skills (líneas 417-436).

**2g. Configurar home programáticamente (Filesystem)**

Hermes necesita su `home` del filesystem configurado para resolver archivos de contexto por defecto. Agregar:
*(Respondiendo a tu duda: Sí, Hermes mantendrá intacta su capacidad actual de clonar otros repositorios en `/tmp` u otras rutas y ejecutarlos en sandboxes dockerizados inyectando secretos por Infisical. El `home` solo define la ruta de búsqueda de contexto por defecto al iniciar la sesión).*

```bash
ssh "${SSH_HOST}" \
  "hermes config set home /opt/toolset-repo 2>/dev/null || true"
```

---

### Componente 3: Pre-flight Verification Script

#### [NEW] [preflight.sh](file:///home/kirlts/toolset/infrastructure/preflight.sh)

Script que se ejecuta como último paso de deploy.sh. Verifica programáticamente las invariantes del MASTER-SPEC en lugar de confiar en que el LLM las recuerde:

```bash
#!/usr/bin/env bash
# preflight.sh — Post-deploy verification of MASTER-SPEC invariants
set -euo pipefail

SSH_HOST="${SSH_HOST:-opc@toolset-oci-1-1}"
ERRORS=0

check() {
  local desc="$1" cmd="$2"
  result=$(ssh -o StrictHostKeyChecking=no "${SSH_HOST}" "$cmd" 2>/dev/null)
  if [ $? -eq 0 ] && [ -n "$result" ]; then
    echo "  ✅ $desc"
  else
    echo "  ❌ $desc"
    ERRORS=$((ERRORS + 1))
  fi
}

echo "[PREFLIGHT] Verifying MASTER-SPEC invariants..."

# §4.1 — .env must not be in git
check "No .env in repo" "[ ! -f /opt/toolset-repo/.env ] && echo ok"

# §4.2 — Infisical is running and healthy
check "Infisical healthy" \
  "sudo docker inspect infisical --format '{{.State.Health.Status}}' | grep -q healthy && echo ok"

# §4.3 — Hindsight is running and healthy
check "Hindsight healthy" \
  "sudo docker inspect hindsight --format '{{.State.Health.Status}}' | grep -q healthy && echo ok"

# §4.4 — Caddy is running and healthy
check "Caddy healthy" \
  "sudo docker inspect caddy --format '{{.State.Health.Status}}' | grep -q healthy && echo ok"

# §5.1 — Hermes gateway is active
check "hermes-gateway active" \
  "systemctl is-active hermes-gateway | grep -q active && echo ok"

# §5.2 — SOUL.md exists and is not empty
check "SOUL.md exists" \
  "[ -s /home/opc/.hermes/SOUL.md ] && echo ok"

# §5.3 — config.yaml has MCP servers
check "MCP servers configured" \
  "grep -q 'mcp_servers' /home/opc/.hermes/config.yaml && echo ok"

# §5.4 — Hindsight bank 'hermes' exists
check "Hindsight bank 'hermes'" \
  "curl -sf https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/v1/default/banks | python3 -c \"import sys,json;print('ok' if any(b.get('bank_id')=='hermes' for b in json.load(sys.stdin).get('banks',[])) else '')\" "

# §5.5 — Skills directory has content
check "Skills directory populated" \
  "ls /home/opc/.hermes/skills/*/SKILL.md 2>/dev/null | head -1 | grep -q SKILL && echo ok"

# §5.6 — context.md exists (project context)
check "context.md exists" \
  "[ -s /home/opc/.hermes/context.md ] && echo ok"

# §5.7 — Kilo CLI Constraints & MCP Verification
check "Kilo CLI enforces rules via prompt" \
  "grep -q '\.agents/rules' /root/.kilo/kilo.jsonc && echo ok"

check "Kilo CLI MCP Enabled" \
  "grep -q 'mcp' /root/.kilo/kilo.jsonc && echo ok"


echo ""
if [ $ERRORS -eq 0 ]; then
  echo "[PREFLIGHT] ✅ All invariants verified"
else
  echo "[PREFLIGHT] ❌ $ERRORS invariant(s) failed"
  exit 1
fi
```

---

### Componente 3.5: Integración de Hallazgos del Fallo Sistémico (25-Jun-2026)

Para abordar explícitamente los patrones de fallo diagnosticados:

1. **Pre-flight Checks Estrictos (Hallazgo 5 - Secrets)**: El agente implementador DEBE asegurar que `preflight.sh` valide estrictamente la regla `MASTER-SPEC §4.1` (Inyección de secretos por Infisical, prohibición de `.env`), lo cual ya está esbozado en el script.
2. **Verificación MCP en 3 Pasos (Hallazgo 4)**: El pipeline DEBE implementar una verificación funcional que vaya más allá del curl básico: (1) Curl al health, (2) Listar tools MCP, (3) Ejecutar un tool dummy.
2.5 **Resolución de Frustración Sistémica (Hallazgo 3)**: Dado que estamos vinculando la ruta `.agents/skills/`, el agente implementador NO necesita crear una skill redundante de frustración. Hermes utilizará de forma nativa el `conflict-resolution-protocol` del Sistema Kairos para erradicar las "mil disculpas" y forzar arreglos estructurales.
3. **Regla de Enforcement (Hallazgo 7)**: El agente implementador DEBE añadir una regla en `Docs/RULES.md` para integrar las validaciones de cumplimiento de `SOUL.md`. (No se debe contaminar `.agents/` dado que es versionado externamente por Kairos).
4. **Ciclo de Vida MCP (Hallazgos 1 y 4)**: El agente implementador DEBE actualizar `Docs/MASTER-SPEC.md §7.1` para documentar el ciclo de vida del gateway, y agregar la regla `INFRA-04` en `Docs/RULES.md` obligando a reiniciar servicios post-deploy.
5. **Git Hook Anti-Secrets (Hallazgo 5)**: El agente implementador DEBE crear un hook `pre-commit` local que bloquee la inclusión de archivos `.env` o secretos evidentes.
6. **Formato de Memoria (Hallazgo 6)**: El agente implementador DEBE reestructurar `MEMORY.md` para que incluya heurísticas procedimentales claras, preparándolo para su eventual consolidación a skills y optimizándolo para las operaciones automáticas de `reflect` + `retain` hacia el banco `hermes` en Hindsight.

---

### Componente 4: Hermes Skills — Reorganización

#### [MODIFY] Skills directory structure

Reorganizar `infrastructure/hermes-skills/` para seguir la convención estándar de Hermes (`name/SKILL.md`):

```
hermes-skills/
├── kilo-code/
│   └── SKILL.md           # (existente, ya correcto)
├── toolset-ops/
│   └── SKILL.md            # [NEW] Operaciones de infraestructura
└── monitoring/
    └── SKILL.md             # [NEW] Qué monitorear y cómo reportar
```

#### [NEW] [toolset-ops/SKILL.md](file:///home/kirlts/toolset/infrastructure/hermes-skills/toolset-ops/SKILL.md)

Skill para operaciones de infraestructura. Codifica las reglas INFRA-01 a 03, los pasos de deploy, y los checks de salud en un formato que Hermes puede cargar bajo demanda:

```markdown
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

- **INFRA-01**: Toda mutación de infraestructura va estrictamente por CI/CD.
- **INFRA-04**: Obligatorio reiniciar los servicios MCP (`hermes-gateway`) tras modificaciones en el pipeline.
- **INFRA-02**: El state remoto en OCI Object Storage es autoritativo. *(Nota: El state remoto es estrictamente necesario si usamos OpenTofu/Terraform para bloquear concurrencia y prevenir corrupción del estado por ejecuciones múltiples. Si solo se usa bash/docker, sirve como preparación arquitectónica para el futuro).*
- **INFRA-03**: Deploy de servicios via CI/CD (`deploy.sh`). Ejecución local solo para verificación.

## Health Checks

| Servicio | Comando |
|---|---|
| Docker containers | `sudo docker compose -f /opt/toolset/docker-compose.yml ps` |
| Hindsight | `curl -sf https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/health` |
| Infisical | `curl -sf http://localhost:8081/api/status` |
| Caddy | `curl -sf http://localhost:8080/health` |
| hermes-gateway | `systemctl is-active hermes-gateway` |

## Monitoring Protocol

Cuando el usuario pida "monitorear", ejecutar los health checks de la tabla anterior, reportar el resultado, y NO hacer follow-up a menos que detecte un fallo.
```

#### [NEW] [monitoring/SKILL.md](file:///home/kirlts/toolset/infrastructure/hermes-skills/monitoring/SKILL.md)

Skill que define qué significa "monitorear" para Hermes — resolviendo el bug #4:

```markdown
---
name: monitoring
description: "Service monitoring and alert protocols for Toolset Personal."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [Monitoring, Alerts, Health, Status]
---

# Monitoring Protocol

## Definición

"Monitorear" NO significa enviar mensajes periódicos al usuario. Significa:

1. Ejecutar los health checks (ver skill `toolset-ops`)
2. Evaluar el resultado
3. **Solo reportar al usuario si hay un fallo o cambio de estado**
4. Si todo está OK, NO enviar mensaje

## Mensajes

| Situación | Acción |
|---|---|
| Todo OK | Silencio. No reportar. |
| Un servicio caído | Reportar inmediatamente por WhatsApp: "[Servicio] está caído. Estado: [detalle]" |
| Recovery automático | Reportar: "[Servicio] recuperado." |
| Fallo persistente (>3 checks) | Reportar + sugerir acción. |

## Anti-patrón

❌ "Todo está bien, seguiré monitoreando" — esto es ruido. No enviar.
❌ "¿Quieres que siga monitoreando?" — si el usuario dijo monitorear, ya tienes la orden.
❌ Mensajes periódicos de status cuando todo funciona — spam.
```



---

### Componente 5: Hermes config.yaml — Corrección MCP

#### [MODIFY] deploy.sh Python block (líneas 610-635)

Corregir la configuración de MCP en el bloque Python que genera config.yaml:

1. Agregar `import os` (falta actualmente, causaría `NameError` en línea 621)
2. Agregar `external_skills_dirs`
3. Agregar `context_file_max_chars`
4. Configurar `home` para que Hermes busque context files en el directorio correcto
5. **Protocolo de Autonomía (Tier 2)**: Configurar `approvals: { mode: smart }` garantizando que Hermes opere con 99% de autonomía resolviendo tareas delegadas por Kilo CLI (Tier 1), escalando al usuario (Tier 3) solo ante decisiones pivotales.

```python
import yaml, os
cfg_path = '/home/opc/.hermes/config.yaml'
with open(cfg_path) as f:
    cfg = yaml.safe_load(f) or {}

cfg.pop('memory_provider', None)
cfg.pop('default', None)
cfg.setdefault('mcp_servers', {})

# Model
cfg['model'] = {'default': 'opencodego/deepseek-v4-flash', 'provider': 'opencode-go'}

# Autonomy & Approvals (99% Autonomy, delegates to Kilo, escalates ONLY for pivotal decisions)
cfg['approvals'] = {'mode': 'smart'}  # Omitirá aprobación para comandos preaprobados/no destructivos.

# Context
cfg['context_file_max_chars'] = 25000

# External skills (from toolset repo)
cfg['external_skills_dirs'] = ['/opt/toolset-repo/infrastructure/hermes-skills', '/opt/toolset-repo/.agents/skills']

# MCP Servers
composio_key = os.environ.get('COMPOSIO_MCP_KEY', '')
if composio_key:
    cfg['mcp_servers']['composio'] = {
        'url': 'https://connect.composio.dev/mcp',
        'headers': {'x-consumer-api-key': composio_key},
        'connect_timeout': 60,
        'timeout': 180
    }
cfg['mcp_servers']['hindsight-selfhosted'] = {
    'url': 'https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/mcp/'
}

with open(cfg_path, 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False)
print('Config updated')
```

---

### Componente 6: Hermes context file → `.hermes/context.md`

Hermes carga archivos de contexto desde `HERMES_HOME`. Según la documentación oficial, los context files reconocidos incluyen `AGENTS.md` y `.cursorrules` en el directorio de trabajo actual, pero también cualquier archivo referenciado vía la configuración `context_files`.

#### [NEW] [hermes-context.md](file:///home/kirlts/toolset/infrastructure/hermes-context.md)

Este archivo será copiado por deploy.sh a `/home/opc/.hermes/context.md`. Contendrá todo el contenido operacional que actualmente vive en SOUL.md y que no debería estar ahí según la documentación oficial.

---

## Plan de Verificación

### Tests Automatizados

```bash
# 1. Validar sintaxis del deploy.sh
bash -n infrastructure/deploy.sh

# 2. Ejecutar preflight.sh post-deploy
./infrastructure/preflight.sh

# 3. Verificar que Hermes responde con identidad correcta
ssh opc@toolset-oci-1-1 'export PATH=/usr/local/bin:$PATH && hermes -z "¿Quién eres?"'

# 4. Verificar que Hermes puede acceder a Hindsight
ssh opc@toolset-oci-1-1 'export PATH=/usr/local/bin:$PATH && hermes -z "Ejecuta recall con keyword toolset y dime qué encuentras"'

# 5. Verificar que skills se cargan desde external dir
ssh opc@toolset-oci-1-1 'export PATH=/usr/local/bin:$PATH && hermes -z "¿Qué skills tienes disponibles?"'
```

### Verificación Manual
*(Se ha removido explícitamente esta sección, dada la confianza total en la automatización del plan).*
---

## Resumen de Cambios por Archivo

| Archivo | Acción | Razón |
|---|---|---|
| `infrastructure/Hermes-SOUL.md` | MODIFY | Reducir a identidad/tono |
| `infrastructure/hermes-context.md` | NEW | Contenido operacional extraído del SOUL |
| `infrastructure/deploy.sh` | MODIFY | Restart gateway, clonar repo, context file, preflight |
| `infrastructure/preflight.sh` | NEW | Verificación post-deploy de invariantes |
| `infrastructure/hermes-skills/toolset-ops/SKILL.md` | NEW | Reglas de infra codificadas como skill |
| `infrastructure/hermes-skills/monitoring/SKILL.md` | NEW | Protocolo de monitoreo (resuelve bug #4) |
| `.github/workflows/deploy.yml` | MODIFY | Agregar paso de preflight post-deploy |
