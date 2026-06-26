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
         └── NO (401) → ¿Gateway arrancó después de la inyección de key?
                         ├── SÍ → La key es inválida. Regenerar en Composio.
                         └── NO → Gateway necesita restart.
                                  Referencia: references/gateway-restart-requirement.md
```

## Errores Conocidos de Diagnóstico

| Error | Causa Real |
|-------|-----------|
| Test con curl da 200, tools no aparecen | Curl no replica el protocolo MCP (JSON-RPC sobre SSE). El gateway usa un cliente MCP diferente. |
| El usuario ejecutó /new y no funciona | /new crea sesión pero no reinicia gateway. MCP connections se cachean al iniciar el gateway. |
| config.yaml tiene la key correcta | El gateway cargó su config al arrancar. Cambios posteriores en disco no se reflejan hasta restart. |
| `systemctl restart hermes-gateway` falla desde Hermes | El gateway bloquea restart desde procesos hijos. Usar cronjob no_agent o SSH externo. |

## Post-Restart Verificación

```bash
# Verificar que el gateway se reinició
systemctl show hermes-gateway --property=ActiveEnterTimestamp

# Verificar que Composio conectó OK
journalctl -u hermes-gateway --no-pager | grep -i "composio" | tail -3

# Verificar que las tools están disponibles (desde nueva sesión)
# → Listar tools disponibles, buscar "mcp_composio_*"
```
