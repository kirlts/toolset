---
name: kilo-code
description: "Delegate ALL code generation, testing, and documentation to Kilo Code CLI. Hermes is a LIGHTWEIGHT ORCHESTRATOR only."
version: 1.2.0
author: Toolset Personal
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Coding-Agent, Kilo, Kairos, Orchestration, Automation]
    related_skills: [hermes-agent, markitdown-converter]
---

# Kilo Code — Mandato de Delegación Total

## Regla Cardinal

Hermes NO escribe código. Punto. Toda generación de código, testeo, debugging, refactorización, creación de documentación kairos (MASTER-SPEC, TODO, MEMORY, USER-DECISIONS, CHANGELOG) y cualquier archivo `.py`, `.ts`, `.js`, `.md` de proyecto DEBE ser generado por Kilo CLI.

Hermes solo:
- Recibe la solicitud del usuario
- Carga contexto de Hindsight (recall)
- Construye el prompt para Kilo con instrucciones claras
- Invoca `kilo run --auto`
- Persiste aprendizajes en Hindsight (retain)
- Reporta resultados al usuario

Si Hermes escribe código directamente, el usuario lo corrige. **Señal de alerta:** cuando el usuario pregunta "¿Estás usando Kilo CLI para esto?" ya operaste mal.

## ⚠️ PREAMBLE OBLIGATORIO — Toda invocación a Kilo

Toda invocación a `kilo run ... --auto` DEBE incluir este preámbulo al INICIO del prompt:

```
INSTRUCCIÓN PERMANENTE: 
Sigue las reglas de la carpeta .agents/ en todos los repositorios que la contengan, así como Docs/RULES.md.
Usa recall/retain en Hindsight con el bank_id del repo activo (el nombre del repositorio) para contexto y persistencia.

[TAREA ESPECÍFICA]
```

No es opcional. Aplica a TODA ejecución futura de Kilo.

## API Key — Export Correcto

La API key de OpenCode Go NO se exporta correctamente con `source` simple. Usar SIEMPRE:

```bash
set -a && source /home/opc/.hermes/.env && set +a
```

Luego invocar Kilo en el mismo comando compuesto, o usar el wrapper `/opt/researchit/kilo.sh`.

## Kairos .agents/ — Obligatorio en Cada Proyecto

Para CADA proyecto nuevo o clonado, Hermes DEBE:

1. Clonar `.agents/` desde `kirlts/kairos` en la raíz del proyecto
2. Crear `docs/` con MASTER-SPEC.md, TODO.md, MEMORY.md, USER-DECISIONS.md, CHANGELOG.md siguiendo `.agents/templates/`
3. Ejecutar `/document` workflow (vía Kilo: `kilo run "Ejecuta /document según .agents/workflows/document.md" --auto`)
4. Crear bank en Hindsight con `bank_id = nombre-del-repo` (exactamente el nombre del repo, sin descripciones)
5. Crear skill Hermes para la capacidad permanente
6. Push a GitHub

## Estrategia de Delegación

1. **Cargar contexto**: `recall(bank="<repo-name>", query="contexto del proyecto")`
2. **Si .agents/ no existe** en el repo → clonar desde kirlts/kairos primero
3. **Delegar TODO** a Kilo (código, tests, docs, debugging)
4. **Monitorear**: si Kilo excede timeout (exit 124), dividir en subtareas más pequeñas
5. **Persistir**: `retain(bank="<repo-name>", content="qué se hizo, qué se aprendió")`
6. **/document periódico**: ejecutar `/document` tras bloques de trabajo significativos. **IMPORTANTE:** el `/document` se ejecuta SIEMPRE en el contexto del repo `kirlts/toolset` (el repo de gobierno central), NO en el repo donde se trabajó. Toolset es el repo que contiene la configuración global de Hermes, skills, y documentación de infraestructura.
7. **Reportar** al usuario concreto y sin verborrea

## Pitfalls

- **Bash quoting en prompts largos**: Si el prompt contiene backticks (`), comillas simples ('), o caracteres especiales, `kilo run 'prompt'` puede fallar con errores de sintaxis bash. Preferir escribir el prompt en un archivo temporal y pasarlo con `--file prompt.txt`. Alternativa: usar `export OPENC...E_API_KEY` en un `set -a && source && set +a` compuesto.
- **PREAMBLE OBLIGATORIO OLVIDADO**: Cada invocación a Kilo DEBE empezar con la instrucción permanente sobre .agents/ y recall/retain. Si Kilo no sabe que debe seguir .agents/, las reglas de kairos no se aplican y el output puede ser inconsistente.
- **Timeout vs error**: Exit code 124 = time-out (dividir tarea en subtareas más pequeñas). Exit code 1 = error real (revisar API key, sintaxis del prompt, .agents/).
- **`set -a` obligatorio**: Sin `set -a` antes de `source .env`, las variables de entorno no llegan a procesos hijo (Kilo, Python) y fallan con 401 o "Missing API key".
- **Non-interactive**: NO usar `kilo run` con `pty=true`. `--auto` es suficiente. No hay TUI que necesite pty.

## Prompts Complejos con Kilo

Cuando el prompt contiene caracteres especiales (backticks, comillas, $, saltos de línea), `kilo run 'prompt'` falla con errores de sintaxis bash. Dos estrategias:

**Estrategia A (Recomendada):** Escribir el prompt en un archivo y pasarlo con `--file`:
```bash
cat > /tmp/kilo-prompt.txt << 'EOF'
INSTRUCCIÓN PERMANENTE: Sigue .agents/ y reglas kairos.
Usa recall/retain en Hindsight con bank_id del repo activo.

[TAREA con carácteres especiales: `backticks`, $variables, "comillas"]
EOF
kilo run --file /tmp/kilo-prompt.txt --auto
```

**Estrategia B:** Prompt inline pero con variables de entorno exportadas antes:
```bash
set -a && source /home/opc/.hermes/.env && set +a && \
  kilo run 'tarea simple sin caracteres especiales' --auto
```

## Flags Importantes

| Flag | Propósito |
|------|-----------|
| `--auto` | Modo autónomo — no requiere intervención |
| `--continue` | Continuar sesión anterior |
| `--file <path>` | Pasar archivo(s) como contexto |

**Exit codes:** 0 = éxito, 124 = time-out (dividir tarea), 1 = error.

## Integración con Toolset

- Los cambios de infraestructura (docker-compose, deploy.sh) se versionan en `kirlts/toolset/infrastructure/`
- Las skills de Hermes se versionan en `toolset/infrastructure/hermes/skills/`
- El CI/CD es el único mecanismo para cambios de infraestructura (INFRA-01)
- Los nuevos servicios se agregan al `docker-compose.yml` canónico de toolset
