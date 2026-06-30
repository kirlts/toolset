# Kilo CLI — Workflow Base

Cargado via `kilo.jsonc` `instructions`. Aplica a TODAS las invocaciones: `kilo run`, `kilo run --auto`.

## Regla 1 — Gobernanza por .agents/

Si el repositorio tiene directorio `.agents/`:
- Las reglas en `.agents/rules/*.md` son vinculantes. Debes seguirlas.
- `docs/RULES.md` es vinculante.
- Este es un proyecto gobernado. No hay libre albedrío.

Si NO existe `.agents/`:
- No hay procedimiento rígido. Usa criterio.

## Regla 2 — /document post-modificación

Si realizaste ALGUNA modificación en el repositorio (código, docs, config, cualquier cambio):
- Ejecuta `/document` para sincronizar el eje documental.
- Si la tarea es solo de lectura, no hace falta.

## Regla 3 — Sesión completa

- Inicio: `recall(bank=<repo>)` para cargar contexto.
- Fin: `retain(bank=<repo>)` con resumen de lo hecho.

## Calidad

- Zero tolerance para: corporate filler, empty adjectives, datos inventados, em dashes.
- Responde conciso: qué se hizo, qué cambió, resultados, decisiones pendientes.
