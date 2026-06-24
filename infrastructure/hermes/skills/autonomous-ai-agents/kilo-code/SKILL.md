---
name: kilo-code
description: "Delegate coding tasks to Kilo Code CLI (features, PRs, refactors, tests)."
version: 1.1.0
author: Toolset Personal
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Coding-Agent, Kilo, OpenCode, Code-Review, Refactoring, Automation]
    related_skills: [claude-code, codex, hermes-agent, opencode]
---

# Kilo Code — Hermes Orchestration Guide

Delegate coding tasks to [Kilo Code CLI](https://kilo.ai/docs/code-with-ai/platforms/cli) (`@kilocode/cli`) via the Hermes terminal. Kilo Code CLI is a fork of OpenCode with autonomous mode, ACP server, and MCP support. Uses the same `~/.config/kilo/kilo.jsonc` config as the local Kilo Code (VS Code extension).

## Prerequisites

- **Install:** `npm install -g @kilocode/cli` (ya instalado en este entorno — v7.3.54)
- **Auth:** usa `OPENCODE_GO_API_KEY` del .env. No requiere login adicional.
- **Config:** `~/.config/kilo/kilo.jsonc` con proveedor OpenCode Go, modelos, MCPs.
- **Verificar:** `kilo --version`

## When to Delegate to Kilo Code

| Situación | ¿Delegar a Kilo? |
|---|---|
| Tarea que produce >50 líneas de código | ✅ **SÍ** — delegar a `kilo run --auto` |
| Refactorización de un módulo completo | ✅ **SÍ** |
| Crear tests para una feature | ✅ **SÍ** |
| Bug fix simple (<50 líneas) | ❌ NO — resolver directamente o con `delegate_task()` |
| Leer archivos, analizar código | ❌ NO — terminal/read_file directamente |
| Operaciones git (commit, push, PR) | ❌ NO — terminal/gh CLI directamente |
| Cambios que requieren PR + merge | ✅ **SÍ** — `kilo run --auto` + gh CLI para PR |

**Regla general:** si el output estimado supera 50 líneas de código o involucra múltiples archivos, delega a `kilo run --auto`. Si es un cambio pequeño o una consulta, terminal directo es suficiente.

### Pitfall: Ignorar el mandato SOUL.md

Si tu SOUL.md o identidad declarada dice explícitamente que uses Kilo CLI para tareas de código, ÚSALO. No caigas en la tentación de hacer todo con `terminal`/`read_file`/`search_files` solo porque parece más rápido. Esto aplica especialmente al diagnosticar código en repos clonados: si la tarea requiere entender, modificar o validar código, y tu identidad dice que tienes Kilo CLI disponible para eso, Kilo debe ser la primera opción, no el último recurso.

**Señal de alerta:** cuando el usuario pregunta "estás usando Kilo CLI para esto?" significa que estás operando por debajo de tus capacidades declaradas. El costo de delegar a Kilo es casi cero (mismo provider, mismo modelo); el costo de hacerlo manual es contexto que pagas dos veces.

> 📎 **Reference:** `references/model-touchpoints.md` — inventario completo de todos los archivos del stack donde se configura el modelo. Consultar para auditorías de enforcement.

## ⚠️ PREAMBLE OBLIGATORIO — Toda invocación a Kilo

Antes de cada `kilo run ... --auto`, DEBES construir el prompt completo así:

```
kilo run "INSTRUCCIÓN PERMANENTE: 
Sigue las reglas de la carpeta .agents/ en todos los repositorios que la contengan, así como Docs/RULES.md.
Usa recall/retain en Hindsight con el bank_id del repo activo (el nombre del repositorio) para contexto y persistencia.

[TAREA ESPECÍFICA]" --auto
```

Esta instrucción permanente SIEMPRE debe ir al inicio del prompt que se le pasa a Kilo. No es opcional. Aplica a TODA ejecución futura.

> Nota: El modelo `deepseek-v4-flash` está forzado en `~/.config/kilo/kilo.jsonc`. No es necesario explicitarlo en el prompt — la configuración ya lo garantiza.

## Autonomous Mode (Recomendado)

```
terminal(command="kilo run 'INSTRUCCIÓN PERMANENTE: ... [tarea]' --auto", workdir="/path/to/repo", timeout=300)
```

**Flags importantes:**
| Flag | Propósito |
|------|-----------|
| `--auto` | Modo autónomo — no requiere intervención. Exitoso con código 0, time-out con 124, error con 1. |
| `--continue` | Continuar sesión anterior. |
| `--file <path>` | Pasar archivo(s) como contexto. |

**Exit codes:** 0 = éxito, 124 = time-out (más turns necesarios), 1 = error.

**Modelo:** `deepseek-v4-flash` — ÚNICO modelo disponible y permitido. No usar otro.

## Estrategia de Delegación

1. **Cargar contexto del repo**: Antes de delegar a Kilo, ejecuta `recall(bank="<repo-name>", query="contexto del proyecto, reglas, decisiones previas")` para obtener el estado actual del proyecto.
2. **Analizar el requerimiento** del usuario con el contexto cargado.
3. Si requiere >50 líneas de código o múltiples archivos → `kilo run "tarea" --auto`.
4. Monitorear el progreso. Si `kilo` excede el tiempo límite (exit 124), dividir la tarea en subtareas más pequeñas.
5. **Persistir aprendizajes**: Al finalizar, ejecuta `retain(bank="<repo-name>", content="qué se hizo, qué se aprendió, qué decisiones se tomaron", tags=["kilo", "YYYY-MM-DD"])`.
6. Verificar el resultado y reportar al usuario.

## Referencia Rápida

```
# Tarea típica de feature
kilo run "Implementar endpoint GET /api/users en el módulo de autenticación, siguiendo el patrón existente en src/auth/" --auto

# Refactorización
kilo run "Refactorizar src/processor.py: extraer la lógica de validación a un módulo separado, agregar type hints" --auto

# Tests
kilo run "Agregar tests unitarios para la clase PaymentService en tests/test_payment.py" --auto

# Bug fix
kilo run "Arreglar el bug en src/inventory.py donde el stock no se actualiza después de una devolución" --auto
```
