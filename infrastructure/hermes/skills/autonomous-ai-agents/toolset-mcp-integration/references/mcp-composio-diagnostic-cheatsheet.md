# MCP Composio Diagnostic Cheatsheet

> Incidente 25 Jun 2026: Gateway cargó key inválida al iniciar (401), key correcta inyectada post-arranque pero gateway nunca reiniciado. Composio caído ~24h+.

## Síntoma
El usuario reporta que Composio MCP no está disponible. Sus herramientas (SEARCH_TOOLS, MULTI_EXECUTE_TOOL, etc.) no aparecen en tu lista de tools.

## Diagnóstico Rápido (3 pasos)

### Paso 1: ¿El server está configurado?
```bash
grep -A5 'composio:' /home/opc/.hermes/config.yaml
```
Esperado: `url: https://connect.composio.dev/mcp` + `x-consumer-api-key: ck_***`

### Paso 2: ¿El gateway logró conectarse?
```bash
journalctl -u hermes-gateway --no-pager | grep -i "composio" | tail -5
```
- **"connected successfully"** → el gateway pudo conectar
- **"401 Unauthorized"** → key rechazada por Composio
- **"Failed to connect"** → no hubo conexión

### Paso 3: ¿Cuándo arrancó el gateway?
```bash
systemctl show hermes-gateway --property=ActiveEnterTimestamp
```
Si arrancó ANTES de que se inyectara la key correcta, está usando la key vieja.

## Árbol de Decisión

```
¿Config en disco tiene key válida?
├── NO → El inject falló. Revisar deploy.sh / Infisical.
│         Referencia: infrastructure-deployment/references/secret-flow-infisical.md
│
└── SÍ → ¿Gateway logró conectar?
         ├── SÍ (connected successfully) → ¿Tools presentes en sesión?
         │   ├── SÍ → Todo bien. Si el usuario dice que no, es un /new.
         │   └── NO → Bug extraño. Revisar si el MCP discovery del gateway
         │            está funcionando (mcp_discovery_timeout en config.yaml).
         │
         └── NO (401) → ¿Cuándo arrancó el gateway?
                         ├── Antes de la inyección → Gateway necesita restart.
                         │   Referencia: references/gateway-restart-requirement.md
                         └── Después de la inyección → Dos sub-casos:
                              ├── Un restart falla → Key inválida. Regenerar.
                              └── TODOS los restarts fallan (múltiples PIDs,
                              │   misma key, mismo 401 por horas) → **Problema
                              │   del lado de Composio, no local.**
                              │   - Verificar con Python directo (ver abajo)
                              │   - Esperar a que Composio se recupere
                              │   - No cambiar config
                              └── Gateway crash con "Failed with result 'signal'"
                                  → Stale systemd unit (TimeoutStopSec mismatch).
                                  Fix: `hermes gateway service install --replace`
```

## Verificación Directa de Validez de Key

Este test prueba la key contra el endpoint MCP sin depender del gateway:

```bash
python3 -c "
import urllib.request
# Extraer key del config yaml
with open('/home/opc/.hermes/config.yaml') as f:
    for line in f:
        if 'x-consumer-api-key:' in line:
            key = line.split(': ')[-1].strip()
            break

req = urllib.request.Request(
    'https://connect.composio.dev/mcp',
    headers={'x-consumer-api-key': key}
)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        print('OK - Status', r.status)
except urllib.error.HTTPError as e:
    body = e.read()[:300]
    print(f'ERR {e.code} - {body}')
except Exception as e:
    print(f'NETWORK ERROR - {e}')
"
```

| Resultado | Significado |
|-----------|-------------|
| `OK - Status 200` o `ERR 400` | Key VÁLIDA. Endpoint responde. El 400 es esperado (MCP requiere session ID) |
| `ERR 401` | Key INVÁLIDA / expirada. Regenerar en Composio |
| Timeout / conexión rechazada | Red/endpoint caído |

## Errores Conocidos de Diagnóstico

| Error | Causa Real |
|-------|-----------|
| Test con curl da 200, tools no aparecen | Curl no replica el protocolo MCP (JSON-RPC sobre SSE). El gateway usa un cliente MCP diferente. |
| El usuario ejecutó /new y no funciona | /new crea sesión pero no reinicia gateway. MCP connections se cachean al iniciar el gateway. |
| config.yaml tiene la key correcta | El gateway cargó su config al arrancar. Cambios posteriores en disco no se reflejan hasta restart. |
| `systemctl restart hermes-gateway` falla desde Hermes | El gateway bloquea restart desde procesos hijos. Usar cronjob no_agent o SSH externo. |
| `Failed with result 'signal'` en journalctl | **Stale systemd unit**: TimeoutStopSec=90s vs drain_timeout=180s mismatch. Fix: `hermes gateway service install --replace` |
| Key válida (prueba directa = 400) pero gateway 401 persistente (>3 restarts) | **Interrupción del lado de Composio**. Esperar recuperación (~3-4 hrs observado). No cambiar config. |
| Infisical falla en inject-composio-key.py | El script tiene fallback: lee COMPOSIO_MCP_KEY de `/home/opc/.hermes/.env`. Verificar que el .env tenga la key actualizada. |

## Post-Restart Verificación

```bash
# Verificar que el gateway se reinició
systemctl show hermes-gateway --property=ActiveEnterTimestamp

# Verificar que Composio conectó OK
journalctl -u hermes-gateway --no-pager | grep -i "composio" | tail -3

# Verificar que las tools están disponibles (desde nueva sesión)
# → Listar tools disponibles, buscar "mcp_composio_*"
```
