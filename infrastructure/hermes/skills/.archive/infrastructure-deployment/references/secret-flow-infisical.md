# Secret Flow: GitHub Secrets → Infisical → VPS

## Arquitectura

```
GitHub Actions (secrets)
    │
    ├── sync_secret() escribe en Infisical API (desde GH Actions)
    │
    └── deploy.sh ejecuta SSH → VPS
            │
            └── script Python lee INFISICAL_SERVICE_TOKEN de /opt/toolset/.env
                    │
                    └── curl a localhost:8081/api/v3/secrets/raw/<NAME>
                            │
                            └── extrae secret.secretValue

NUNCA: env vars de GH Actions → SSH directo
NUNCA: editar config.yaml manualmente en VPS
NUNCA: leer .env con cat/grep para diagnosticar (usar API de Infisical)
```

## Patrón Python correcto para leer secrets de Infisical

⚠️ **IMPORTANTE:** La API v3 de Infisical **REQUIERE** los parámetros `workspaceId` y `environment`. Sin ellos responde `400 Missing environment`.

```python
import json, subprocess, os

# 1. Leer token de Infisical
token = ''
try:
    with open('/opt/toolset/.env') as f:
        for line in f:
            line = line.strip()
            if line.startswith('INFISICAL_SERVICE_TOKEN=***                token = line.split('=', 1)[1]
                break
except:
    pass

# 2. Obtener secreto de Infisical API
#    NECESITA workspaceId + environment — sin esto falla con 400
project_id = "08535df4-97d1-42cb-b127-bc2dbfa3cb79"  # Toolset project
secret_value = ''
if token:
    try:
        r = subprocess.run(
            ['curl', '-s',
             f'http://localhost:8081/api/v3/secrets/raw/SECRET_NAME?workspaceId={project_id}&environment=prod',
             '-H', f'Authorization: Bearer ***            capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            data = json.loads(r.stdout)
            secret_value = data.get('secret', {}).get('secretValue', '')
    except:
        pass

# 3. Usar el valor
if secret_value:
    cfg['mcp_servers']['composio'] = {
        'url': 'https://connect.composio.dev/mcp',
        'headers': {'x-consumer-api-key': secret_value},
    }
```

## BUG CONOCIDO en deploy.sh (línea 806)

El script Python de inyección usa esta URL **incorrecta**:

```
http://localhost:8081/api/v3/secrets/raw/COMPOSIO_MCP_KEY
```

Sin `?workspaceId=` ni `?environment=`. La API responde `400 Missing environment`,
la excepción se captura, `composio_key = ''`, el bloque `if composio_key:` no se
ejecuta, y el config.yaml queda con el placeholder `PLACEH...PLOY`.

**Síntoma:** Tools MCP de Composio no aparecen en la sesión, aunque
`mcp_servers.composio` existe en config.yaml.

**Diagnóstico:**
```bash
grep 'x-consumer-api-key' /home/opc/.hermes/config.yaml
# Si muestra "PLACEH...PLOY" → la inyección falló
```

**Fix:** Agregar `?workspaceId=<ID>&environment=prod` a la URL del curl en el script
Python dentro de deploy.sh, y leer `workspaceId` desde la respuesta de
`/api/v2/service-token` o desde `/opt/toolset/.env`.

## Referencia de API Infisical

| Endpoint | Método | Uso |
|---|---|---|
| `http://localhost:8081/api/v1/auth/login` | POST | Login con email/password (obtener token temporal) |
| `http://localhost:8081/api/v2/service-token` | GET | Info del service token (incluye projectId y scopes) |
| `http://localhost:8081/api/v3/secrets/raw/<NAME>?workspaceId=<ID>&environment=<env>` | GET | Leer secreto (requiere Bearer token + params) |
| `http://localhost:8081/api/v3/secrets/raw/<NAME>` | POST | Escribir secreto (con body JSON incluyendo workspaceId + environment) |

## Dónde está cada secreto

| Secreto | Ubicación en GH Secrets | En Infisical | Accesible en VPS vía |
|---|---|---|---|
| COMPOSIO_MCP_KEY | secrets.COMPOSIO_MCP_KEY | prod/COMPOSIO_MCP_KEY | API Infisical local |
| COMPOSIO_API_KEY | secrets.COMPOSIO_API_KEY | prod/COMPOSIO_API_KEY | API Infisical local |
| INFISICAL_SERVICE_TOKEN | secrets.INFISICAL_SERVICE_TOKEN | N/A (es el token mismo) | /opt/toolset/.env |

## Lecciones de debugging (26 Jun 2026)

1. **No leer `.env` directamente.** Si necesitas verificar un secreto, usa la API
   de Infisical local (`localhost:8081`) con el service token.
2. **Cuando las tools MCP no aparecen en una sesión:** primero revisa si
   `config.yaml` tiene la key real o el placeholder. Si es placeholder, el
   problema está en el deploy script, no en el gateway.
3. **Service token `ci-cd-pipeline`**: creado 23 Jun 2026, scope dev+prod,
   permissions read+write, no expira. projectId: `08535df4-97d1-42cb-b127-bc2dbfa3cb79`.
