# Pipeline v2 — Síntesis por Capítulos (migración 2026-08-08)

## Por qué existe

El pipeline v1 hacía UNA síntesis LLM para todo el reporte (max_tokens 8192). Síntomas observados:
- Reportes de ~14K chars que solo cubrían la sección 2.1 de 18 (el LLM "se acabó")
- El PDF parecía "truncado en la página 15", pero contenía TODO el MD: lo corto era la síntesis
- El refine (segunda llamada LLM que expande) producía "síntesis sobre síntesis", explícitamente rechazado por Martín

## Diseño v2

1. Plan genera 10-16 preguntas (una por elemento a evaluar + contexto/comparación)
2. Search en paralelo (semáforo 4), 8 resultados por pregunta
3. Dedup global
4. Scrape hasta 60 URLs
5. Síntesis POR CAPÍTULO en paralelo (semáforo 4), max_tokens 16384, cada capítulo con SOLO sus fuentes
6. Post-proceso: dedupe de encabezados '# Capítulo N' repetidos
7. PDF único con todo concatenado

Resultado observado: 16 capítulos, ~455K chars (~100+ páginas), 0 frases duplicadas.

## Cambios de código (src/research.py, src/synthesize.py)

- `_parse_questions()`: parseo robusto del plan (JSON array, fences de código, listas con numeración/bullets)
- `_plan_questions()`: 3 reintentos + RuntimeError explícito si plan vacío
- `_build_sub_questions_prompt()`: recorta topic a 1500 chars
- `synthesize(..., section_title=None)`: modo capítulo con `_SECTION_PROMPT` (sin resumen ejecutivo repetido)
- `synthesize()` user_prompt: recorta topic a 1500 chars
- `_dedupe_chapter_headers()`: elimina encabezados consecutivos duplicados
- `_SEARCH_CONCURRENCY = 4`, `_SYNTH_CONCURRENCY = 4`: asyncio.Semaphore + asyncio.gather
- `_MIN_CHAPTER_CHARS = 1500`: capítulo corto se conserva (warning), no se refina
- max_results búsqueda 5 → 8; `--max-sources` default 30 → 60; `_MAX_TOTAL_CHARS` 25K → 50K

## Pitfall crítico: plan vacío con tema largo

deepseek-v4-flash devuelve `""` cuando el prompt del plan supera ~1500 chars de topic.
Síntoma en logs: `Plan generado: 0 preguntas` seguido de `Búsqueda: 0.00s — 0 grupos/0 resultados`
y un reporte con solo el capítulo Reddit. El pipeline v1 continuaba silenciosamente;
v2 lanza RuntimeError tras 3 intentos.

## Pitfall: lock stale tras kill

SIGTERM al proceso de researchit NO ejecuta el `finally: _release_lock()`.
`/tmp/researchit.lock` queda con PID muerto y bloquea la siguiente corrida (TTL 1800s).
Fix: `rm -f /tmp/researchit.lock` antes de relanzar.

## Diagnóstico de "informe truncado en página N"

```python
import pymupdf
doc = pymupdf.open('vault/report.pdf')
print('paginas:', doc.page_count)
print('chars pdf:', sum(len(p.get_text()) for p in doc))
# comparar con len(open('vault/report.md').read())
```
Si PDF ≈ MD → el PDF está completo; el problema es cobertura de síntesis → más capítulos.
