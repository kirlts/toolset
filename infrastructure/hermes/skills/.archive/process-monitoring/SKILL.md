---
name: process-monitoring
description: Protocolo de monitoreo activo para procesos largos — updates cada 3 min, reporte inmediato de blockers, sin silencio prolongado
---

# Monitoreo de Procesos Largos

Protocolo obligatorio cuando ejecutas tareas que toman más de 30 segundos (deploys, Kilo CLI, builds, tests, research).

## Regla de Oro

**Cada llamada a tool relevante = oportunidad de update.** No esperes a tener resultados completos para hablar. El usuario prefiere saber que estás trabajando aunque no haya novedades.

## ⚠️ REGLA ABSOLUTA: Kilo CLI nunca timeout

Kilo CLI ejecuta workflows multi-step (Kairós: /document, /derive, integraciones) que pueden tomar 5+ minutos.

- NUNCA usar `terminal(timeout=N)` para Kilo CLI. Siempre `terminal(background=true, notify_on_complete=true, timeout=600)`.
- Foreground timeout menor a 600 mata el proceso. El workflow queda incompleto y puede corromper estado.
- Esto aplica a TODOS los perfiles, sin excepción.
- Reportar update en cada señal de progreso (fase completada, archivo creado, error).

## Frecuencia de Updates

| Contexto | Frecuencia |
|---|---|
| Tarea en foreground con iteraciones visibles | Cada 3 tool calls o cuando haya un cambio de fase |
| Proceso en background (notify_on_complete) | Cada 3 minutos |
| Deploy/monitoreo activo | Cada tool call relevante — informar qué paso se completó y qué sigue |
| Blocker o error | INMEDIATO — no esperar al próximo update programado |

## Formato de Update

```
**Update N** (~X min desde inicio) — [estado actual]
[breve detalle de qué se completó y qué sigue]
```

Sin verborrea. Sin emojis. Sin "estoy trabajando en ello". Decir QUÉ se está haciendo concretamente.

## Protocolo de Blocker

1. Reportar INMEDIATAMENTE — no esperar al próximo update programado
2. Especificar: qué falló, por qué, qué alternativa se intentó
3. Si no hay alternativa desde el agente, escalar al usuario con la info para que él decida
4. NUNCA quedarse en silencio más de 5 minutos si hay un blocker

## Casos de Uso

- `kilo run --auto` en background
- Deploy CI/CD tracking
- ResearchIt investigaciones largas
- Cualquier proceso que el usuario pidió monitorear

## Model Latency Consideration

Cuando monitoreas Kilo CLI con deepseek-v4-flash, ten en cuenta:
- La PRIMERA inferencia puede tardar 30-90 segundos en cargar el modelo (especialmente si no se usó recientemente)
- Durante ese tiempo Kilo no produce output visible
- NO asumas que está colgado — verifica con `pstree -p <pid>` para confirmar que tiene threads activos
- Si el proceso tiene threads `.kilo` activos, está procesando — solo espera

Este comportamiento es normal para deepseek-v4-flash via opencode-go y no indica un problema.

## Referencias

- Este skill nace del incidente 25-jun-2026 donde el agente estuvo 10+ minutos sin updates durante deploy #196
- La instrucción quedó grabada en memory y SOUL.md como regla permanente
- REGLA ABSOLUTA Kilo CLI no-timeout agregada 28-jun-2026 tras timeout de 120s en /document workflow
