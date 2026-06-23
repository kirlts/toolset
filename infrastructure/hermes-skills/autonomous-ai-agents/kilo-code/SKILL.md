---
name: kilo-code
description: "Delegate coding tasks to Kilo Code CLI (features, PRs, refactors, tests)."
version: 1.0.0
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

## Autonomous Mode (Recomendado)

```
terminal(command="kilo run 'Descripción detallada de la tarea' --auto", workdir="/path/to/repo", timeout=180)
```

**Flags importantes:**
| Flag | Propósito |
|------|-----------|
| `--auto` | Modo autónomo — no requiere intervención. Exitoso con código 0, time-out con 124, error con 1. |
| `--model <name>` | Especificar modelo (ej: `deepseek-v4-pro` para tareas complejas). Default: el del `kilo.jsonc`. |
| `--continue` | Continuar sesión anterior. |
| `--file <path>` | Pasar archivo(s) como contexto. |

**Exit codes:** 0 = éxito, 124 = time-out (más turns necesarios), 1 = error.

## Model Discovery

```
# Listar modelos disponibles del proveedor OpenCode Go
terminal(command="kilo models opencodego", timeout=15)
```

Usar modelos más potentes (`deepseek-v4-pro`, `kimi-k2.6`, `qwen3.7-max`) para tareas complejas. Mantener `deepseek-v4-flash` para tareas rápidas.

## Estrategia de Delegación

1. **Analizar el requerimiento** del usuario.
2. Si requiere >50 líneas de código o múltiples archivos → `kilo run "tarea" --auto`.
3. Monitorear el progreso. Si `kilo` excede el tiempo límite (exit 124), dividir la tarea en subtareas más pequeñas.
4. Verificar el resultado y reportar al usuario.

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
