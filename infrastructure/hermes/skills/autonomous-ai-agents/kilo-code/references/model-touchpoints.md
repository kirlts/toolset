# Model Touchpoints — Toolset Stack

> Lugares donde se configura o referencia el modelo LLM en el stack Toolset.
> Útil para auditorías y enforcement de deepseek-v4-flash como único modelo.

## Hermes (host OCI)

| Ubicación | Qué contiene | Propósito |
|---|---|---|
| `~/.hermes/SOUL.md` | `§Plataforma`, `§Reglas KILO-01` | Identidad del agente, restricción de modelo + preamble |
| `~/.config/kilo/kilo.jsonc` | `provider.opencodego.models` | Modelos disponibles para Kilo CLI |
| `~/.hermes/skills/autonomous-ai-agents/kilo-code/SKILL.md` | `§PREAMBLE OBLIGATORIO` | Skill de orquestación de Kilo desde Hermes |
| `~/.hermes/skills/hermes-skills/autonomous-ai-agents/kilo-code/SKILL.md` | duplicado | Ídem |

## Repositorio toolset (kirlts/toolset)

| Ubicación | Qué contiene | Propósito |
|---|---|---|
| `infrastructure/kilo.jsonc` | `models` | Template de config de Kilo para deploy |
| `infrastructure/Hermes-SOUL.md` | `§Plataforma` | Template de SOUL.md que se deploya |
| `infrastructure/hermes-skills/.../kilo-code/SKILL.md` | model references | Template de skill para deploy |
| `infrastructure/deploy.sh` | `HINDSIGHT_API_LLM_MODEL` | Modelo para Hindsight API |
| `infrastructure/docker-compose.yml` | `HINDSIGHT_API_LLM_MODEL` env var | Modelo para contenedor Hindsight |
| `Hermes-integration.md` | `HERMES_LLM_MODEL` | Documentación de integración |
| `docs/MASTER-SPEC.md` | `§3`, `§7.1` | Especificación arquitectónica |
| `Toolset Junio 2026.md` | `§2.2`, `§4` | Especificación fundacional |

## CI/CD

| Ubicación | Qué contiene | Propósito |
|---|---|---|
| `.github/workflows/deploy.yml` | env vars | Pipeline references |

## Hindsight runtime (OCI)

| Ubicación | Qué contiene | Propósito |
|---|---|---|
| `/opt/toolset/.env` | `HINDSIGHT_API_LLM_MODEL=deepseek-v4-flash` | Config runtime de Hindsight |
| Docker env | `HINDSIGHT_API_LLM_MODEL` | Variable del contenedor |

## Regla general

deepseek-v4-flash es el **único modelo permitido** en todo el stack.
Cualquier referencia a deepseek-v4-pro, qwen\*, kimi\*, mimo\*, gpt\*, claude\*, o similar debe ser eliminada.
