# OpenCode Go — Diagnóstico de Auth en Kilo CLI

> Árbol de decisión para cuando Kilo CLI falla con errores de autenticación
> contra OpenCode Go (proveedor `opencodego/deepseek-v4-flash`).

## Síntomas y causas

| Síntoma en Kilo | Lo que realmente pasó | Causa raíz |
|---|---|---|
| `Missing API key` | Kilo no encontró la env var o el provider no cargó | (1) `npm` field en provider, o (2) env var no exportada |
| `Invalid API key` (401) | Kilo envió la key pero el servidor la rechazó | Key expirada/revocada |
| `Invalid API key` (403, code 1010) | Key funciona para `/models` pero no para `/chat/completions` | Key restringida o permisos insuficientes |
| SDK funciona, Kilo no | OpenAI Python SDK funciona, Kilo con `@ai-sdk/*` no | Diferencia en headers HTTP entre SDKs |

## Árbol de diagnóstico

### Paso 1: ¿El provider está bien definido en kilo.jsonc?

```bash
timeout 20 kilo models opencodego
# Debe listar: opencodego/deepseek-v4-flash
# Si no lista nada → el provider no cargó
```

**Si no carga:** revisar que `kilo.jsonc` NO tenga campo `npm`:

```jsonc
// MAL — causa Missing API key
{
  "provider": {
    "opencodego": {
      "npm": "@ai-sdk/openai-compatible",  // ← QUITAR ESTO
      "options": { ... }
    }
  }
}

// BIEN
{
  "provider": {
    "opencodego": {
      "options": {
        "baseURL": "https://opencode.ai/zen/go/v1",
        "apiKey": "{env:OPENCODE_GO_API_KEY}"
      },
      "models": {
        "deepseek-v4-flash": { "name": "deepseek-v4-flash" }
      }
    }
  }
}
```

El campo `npm` le dice a Kilo que use un módulo npm específico (`@ai-sdk/openai-compatible`). Si el módulo no está instalado correctamente en el contexto de Kilo, el provider se ignora completamente y Kilo tira "Missing API key" aunque la env var esté bien definida.

### Paso 2: ¿La env var está exportada al proceso?

```bash
# Verificar en el shell actual
env | grep OPENCODE_GO_API_KEY

# Verificar en un shell limpio (sin env heredada)
bash -c 'unset OPENCODE_GO_API_KEY; source /home/opc/.bashrc; env | grep OPENCODE_GO_API_KEY'
```

**Si no aparece:**
- Revisar `/home/opc/.bashrc` — debe tener:
  ```bash
  export OPENCODE_GO_API_KEY=$(grep '^OPENCODE_GO_API_KEY=' /home/opc/.hermes/.env 2>/dev/null | cut -d= -f2-)
  ```
- Si no está, agregarlo (o corre deploy.sh que lo agrega automáticamente)

**Nota:** El systemd service de Hermes tiene la env var por el `.env` que deploy.sh escribe. Pero Kilo CLI corre como proceso independiente y necesita la env var en el shell.

### Paso 3: ¿La key es válida?

Probar con el mismo SDK que Hermes usa:

```bash
source /usr/local/lib/hermes-agent/venv/bin/activate
python3 -c "
from openai import OpenAI
k = open('/home/opc/.hermes/.env').read().split('OPENCODE_GO_API_KEY=')[1].split()[0]
c = OpenAI(api_key=k, base_url='https://opencode.ai/zen/go/v1')
r = c.chat.completions.create(model='deepseek-v4-flash', messages=[{'role':'user','content':'hi'}], max_tokens=5)
print('SDK OK:', r.choices[0].message.content)
"
```

**Si funciona:**
- La key es válida → el problema está en Cómo Kilo la envía (Paso 4)

**Si NO funciona con SDK pero funciona con curl `/models`:**
- La key tiene permisos restringidos en OpenCode (puede listar modelos pero no hacer chat)
- Solución: rotar la key en GitHub Secrets

### Paso 4: ¿Kilo está usando el provider correcto?

```bash
# Debug logs de Kilo
timeout 20 kilo run "test" --print-logs 2>&1 | grep -i "provider\|api\|key\|auth\|error\|opencodego"
```

Buscar en los logs:
- `providerID=opencodego found` — el provider se cargó ✅
- `providerID=opencodego pkg=@ai-sdk/openai-compatible using bundled provider` — Kilo usó su SDK nativo ✅  
- `responseBody...Missing API key` — el servidor rechazó la request (volver a Paso 2)
- Si no aparece `providerID=opencodego found` → el provider no cargó (volver a Paso 1)

### Paso 5: ¿Hay un project-level kilo.jsonc haciendo shadow?

```bash
find /home/opc -name "kilo.jsonc" -not -path "*/node_modules/*" 2>/dev/null
```

Si hay un `kilo.jsonc` dentro de un proyecto (ej. `infrastructure/kilo.jsonc`), Kilo lo carga como project-level config cuando se usa `--dir`. Esto puede:

1. Hacer shadow al provider config global (si el project-level no lo define)
2. Tener el `npm` field (versión desactualizada)
3. Tener `instructions` desactualizadas

**Fix:** El repo versiona `kilo.jsonc` en `infrastructure/kilo.jsonc`. deploy.sh lo copia al global. No debe haber copias project-level. Si las hay, eliminarlas.

## Verificación completa

```bash
# Test end-to-end en shell limpio
bash -c '
  unset OPENCODE_GO_API_KEY
  source /home/opc/.bashrc
  timeout 30 kilo run "Only respond with OK" --model opencodego/deepseek-v4-flash --auto
'
# Debe responder: OK
```

## Lo que NO funciona

- `source /home/opc/.hermes/.env` directo — las env vars se heredan pero Kilo puede no verlas si corre en subproceso sin `inherit_env`
- Pasar la key inline: `OPENCODE_GO_API_KEY=... kilo run ...` — funciona pero no es persistente
- Hardcodear la key en kilo.jsonc en vez de usar `{env:...}` — viola la política de secrets
- Instalar `@ai-sdk/openai-compatible` manualmente — Kilo necesita que el módulo esté en su propio contexto de node_modules, no en un path arbitrario
