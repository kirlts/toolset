# GitHub Webhooks para Monitoreo Autónomo de Deploys

## Contexto

El usuario solicitó específicamente hooks de GitHub (webhooks) para que Hermes detecte fallos de CI/CD sin polling. Un cron con `gh run list` es una solución válida pero ineficiente — la óptima es event-driven vía webhooks.

## Opciones (ordenadas por optimalidad)

### Opción 1: Webhook de GitHub → Caddy → Receptor → Hermes (EVENT-DRIVEN)

**Arquitectura:**
```
GitHub (workflow_run event) → POST → Caddy (/webhook/github)
                                           ↓
                                    Receptor script
                                           ↓
                                    Hermes diagnostica
                                    y resuelve automáticamente
```

**Setup:**
1. Configurar webhook en repo `kirlts/toolset` → Settings → Webhooks → Add webhook
   - Payload URL: `https://toolset-oci-1-1.tail2d4c18.ts.net/webhook/github`
   - Content type: `application/json`
   - Events: solo `Workflow runs` (desmarcar todos los demás)
2. Agregar ruta en Caddyfile:
   ```
   handle /webhook/github* {
       reverse_proxy localhost:9999
   }
   ```
3. Crear receptor (Flask mínimo o script Python) que:
   - Verifica firma HMAC-SHA256 (secret del webhook)
   - Filtra solo `action: "completed"` + `conclusion: "failure"`
   - Dispara diagnóstico y auto-resolución en Hermes

**Payload relevante (`workflow_run` event):**
```json
{
  "action": "completed",
  "workflow_run": {
    "id": 28181499037,
    "name": "Deploy OpenTofu + Services to OCI",
    "head_branch": "main",
    "head_commit": {"message": "fix: ..."},
    "status": "completed",
    "conclusion": "failure",
    "html_url": "https://github.com/kirlts/toolset/actions/runs/28181499037"
  },
  "repository": {"full_name": "kirlts/toolset"},
  "sender": {"login": "kirlts"}
}
```

**Pros:** 100% event-driven, 0 latencia, 0 polling, 0 recursos idle.
**Contra:** Requiere setup inicial de endpoint webhook + receptor.
**Prioridad:** Alta — es lo que el usuario pidió explícitamente.

### Opción 2: Workflow Failure Step en deploy.yml (SIMPLEST)

Agregar un step al final de `.github/workflows/deploy.yml` que corre SOLO si falla:

```yaml
- name: Notify Hermes on failure
  if: failure() || cancelled()
  run: |
    curl -s -X POST "https://toolset-oci-1-1.tail2d4c18.ts.net/webhook/deploy-status" \
      -H "Content-Type: application/json" \
      -d '{
        "status": "failed",
        "repo": "kirlts/toolset",
        "run_id": ${{ github.run_id }},
        "commit": "${{ github.sha }}"
      }'
```

Requiere el mismo endpoint receptor que la Opción 1.
**Pros:** 2 líneas de YAML, no requiere configurar webhook en GitHub.
**Contra:** Modifica el pipeline CI/CD (mezcla lógica de notificación con deploy).

### Opción 3: Cron Polling (IMPLEMENTADO — ver Deploy Watch)

Cron `hermes-deploy-watch` cada 3 minutos con `gh run list`. Ya implementado.
**Pros:** Cero infraestructura nueva. gh CLI ya autenticado.
**Contra:** Polling, hasta 3 min de latencia, ineficiente para un agente autónomo.
**Uso:** Solución temporal mientras se implementa Opción 1.

## Cómo Conectar el Webhook a Hermes

Hermes no expone una API HTTP pública para recibir tareas. Para que un webhook dispare una acción en Hermes:

**Opción A — Webhook escribe archivo de evento:**
1. Receptor escribe `/tmp/webhook-events/deploy-failed.json`
2. Un cron de alta frecuencia (ej. cada 30s) detecta el archivo y ejecuta el flujo de auto-resolución
3. Esto sigue siendo semi-polling pero con latencia mucho menor

**Opción B — Webhook llama a Hermes CLI vía SSH:**
```bash
ssh opc@localhost 'hermes -z "Deploy #189 falló en toolset. Diagnostica y resuelve."'
```

**Opción C — Webhook se comunica vía WhatsApp:**
1. Receptor envía un mensaje al número del bot de WhatsApp
2. Hermes lo recibe como cualquier mensaje entrante
3. El agente ejecuta el flujo de auto-resolución

## Auto-resolución (Self-Healing)

El objetivo final no es solo notificar, sino que Hermes RESUELVA automáticamente:

1. **Detectar** el fallo vía webhook (o cron)
2. **Diagnosticar** con `gh run view <run-id> --log-failed`
3. **Clasificar** el fallo (config vs container vs API key)
4. **Resolver** aplicando el fix correspondiente (según tabla de failure points)
5. **Reportar** el resultado al usuario

## Referencias

- Doc oficial GitHub webhooks: https://docs.github.com/en/webhooks
- Evento workflow_run: https://docs.github.com/en/webhooks/webhook-events-and-payloads#workflow_run
- Skill `infrastructure-deployment` → Deploy Failure Diagnosis Protocol
