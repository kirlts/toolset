# Cambio de Era — Ejemplo concreto (19 julio 2026)

Este archivo documenta el primer Cambio de Era ejecutado en la KB Narrativa Mitológica, como referencia para futuros cambios similares.

## Contexto

Martín pasó de un período de desempleo post-titulación (estrés, casa difícil, estancamiento en karate, liquidez cero) a conseguir empleo como líder tecnológico de un SaaS de IA. El cambio fue lo suficientemente fundamental como para merecer una actualización integral de la KB.

## Diagnóstico pre-cambio

### Terreno (hechos vigentes hasta 19-jul)
- Clima/Mercado Laboral Saturado — estado: draft
- Material/Liquidez Restringida — estado: draft (sin ingresos)
- Material/Jiu Jitsu Brasileno — documentaba solo primera sesión
- Motor/Práctica de Karate — sin evaluación de rendimiento

### Mito (constructos vigentes hasta 19-jul)
- Adaptaciones/Autonomía Residencial — modo contención (sobrevivir el 8x6)
- Ego/Filosofía de la Adversidad — encuadre de espera
- Campañas — 8 campañas, NINGUNA de empleo

## Cambios ejecutados

### Terreno
| Nodo | Cambio | Estado nuevo |
|---|---|---|
| Mercado Laboral Saturado | Sección "Desenlace — Julio 2026" agregada | historical |
| Liquidez Restringida | Sección "Resolución — Julio 2026" agregada | resolved |
| Jiu Jitsu Brasileno | Contenido reemplazado con rutina actual | draft |
| Espacio Dino | Ocupación actualizada con BJJ + viernes sparring | draft |
| Práctica de Karate | Evaluación de estancamiento agregada | draft |
| Bitácora 2026-07-19 | NUEVO nodo con contexto completo | draft |
| Empleo Alan SaaS | NUEVO nodo con condiciones | draft |
| Líder Tecnológico Alan SaaS | NUEVO nodo con rol | draft |

### Mito
| Nodo | Cambio | Estado |
|---|---|---|
| Campaña Escalar Producto Alan | NUEVA campaña | en ejecucion |
| Campaña Autonomía Residencial | NUEVA campaña | en planificacion |
| Autonomía Residencial | Actualización post-empleo agregada | draft |
| Filosofía de la Adversidad | Nuevo encuadre (adversidad cambió de forma) | draft |
| Campañas hub | YAML + inventario actualizados | — |

## Lecciones del proceso

1. La clasificación KR2 debe ser exhaustiva antes de proponer — no saltar a "esto es Terreno, esto Mito" sin descomponer cada unidad de información.
2. Para cambios grandes (>10 archivos), el batch KR10 es más eficiente que tarea por tarea.
3. compile.py puede requerir 2-3 iteraciones post-cambio para converger totalmente.
4. Los nodos stub que compile.py crea automáticamente (para wikilinks sin destino) son esperables y no deben eliminarse sin autorización del usuario.
