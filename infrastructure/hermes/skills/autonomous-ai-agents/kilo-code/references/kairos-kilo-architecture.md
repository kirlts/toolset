# Kairos + Kilo CLI — Arquitectura de Integración

## kilo.jsonc: Configuración Persistente

La configuración de Kilo CLI vive en `~/.config/kilo/kilo.jsonc` y se versiona en `infrastructure/kilo.jsonc` del repo toolset.

### Componentes Clave

| Campo | Propósito | Configurado |
|-------|-----------|-------------|
| `provider` | OpenCode Go con deepseek-v4-flash | ✅ |
| `mcp` | Composio + Hindsight-selfhosted | ✅ |
| `instructions` | Carga archivos markdown como system prompt | ✅ `.agents/rules/01-behavior.md`, `05-constraints.md`, `docs/RULES.md` |
| `agent.build.prompt` | System prompt base para agente build | ✅ Identity Kairos, workflow /document, TDD, SDD, secrets Infisical, Hindsight memory |

### Provider: opencodego

```jsonc
"provider": {
  "opencodego": {
    "name": "OpenCode Go",
    "options": {
      "baseURL": "https://opencode.ai/zen/go/v1",
      "apiKey": "{env:OPENCODE_GO_API_KEY}"
    },
    "models": {
      "deepseek-v4-flash": { "name": "deepseek-v4-flash" }
    }
  }
}
```

**Importante:** NO incluir el campo `npm`. Sin él, Kilo usa su handler OpenAI-compatible nativo y funciona correctamente. Con `npm: "@ai-sdk/openai-compatible"` falla con "Missing API key".

### Instrucciones

```jsonc
"instructions": [
  ".agents/rules/01-behavior.md",
  ".agents/rules/05-constraints.md",
  "docs/RULES.md"
]
```

Estos archivos se cargan como system prompt adicional al inicio de cada sesión de Kilo CLI. Equivalente a configurar "rules files" en Kilo Code VS Code.

### System Prompt Base (agent.build.prompt)

El prompt del agente `build` cubre:
1. **Identidad**: agente efímero invocado por Hermes (proxy humano)
2. **Gobernanza**: Kairos v4, Master Spec como fuente de verdad
3. **Workflow obligatorio**: /document inicio/fin y tras cambios, TDD + SDD, /test con permiso de instalar dependencias
4. **Secrets**: todo via Infisical, nunca .env ni hardcodeado
5. **Hindsight**: recall/retain/reflect por bank nombrado como el repo
6. **Calidad**: zero slop, zero fabricación, respuestas concisas

## API Key: Export al Shell

La env var `OPENCODE_GO_API_KEY` vive en `/home/opc/.hermes/.env`. Para que Kilo CLI resuelva `{env:OPENCODE_GO_API_KEY}`, la variable debe estar exportada al shell.

**Mecanismo:** El deploy.sh agrega al `.bashrc` del usuario `opc`:

```bash
if [ -f /home/opc/.hermes/.env ]; then
  export OPENCODE_GO_API_KEY=$(grep "^OPENCODE_GO_API_KEY=" /home/opc/.hermes/.env | cut -d= -f2-)
fi
```

Esto asegura que cada shell interactivo tenga la variable disponible. No es necesario `set -a && source`.

## MCPs en Kilo CLI

```jsonc
"mcp": {
  "composio": {
    "type": "remote",
    "url": "https://connect.composio.dev/mcp",
    "headers": {
      "x-consumer-api-key": "{env:COMPOSIO_MCP_KEY}"
    }
  },
  "hindsight-selfhosted": {
    "type": "remote",
    "url": "https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/mcp/"
  }
}
```

Ambos MCPs se conectan automáticamente en cada sesión de Kilo CLI. Composio expone herramientas de integración (Reddit, Gmail, etc.) y Hindsight expone recall/retain/reflect para memoria persistente.
