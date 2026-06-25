# Synthesize Token Optimization — ResearchIt

## El problema

Cuando se pasan >20 fuentes a deepseek-v4-flash, el modelo puede devolver **0 caracteres** (respuesta vacía). Esto ocurre porque el contenido total del prompt excede la capacidad efectiva o satura al modelo.

## Solución implementada (v1.1)

| Parámetro | Antes | Después |
|-----------|-------|---------|
| `_MAX_ENTRY_CHARS` | 4000 | **2000** |
| `_MAX_TOTAL_CHARS` | 30000 | **25000** |
| `_MAX_TOKENS` | 8192 | 8192 (sin cambio) |
| System prompt | Estándar | **+ "Mínimo 3000 palabras. No respondas con vacío."** |

## Refine guard

El refine (segunda pasada LLM para expandir) a veces **achicaba** el reporte en vez de expandirlo. Solución: comparar longitud antes/después y conservar el original si refine lo acorta.

```python
refined = await _refine_report(topic, report_md)
if len(refined) >= len(report_md):
    report_md = refined
else:
    # keep original
```

## Budget aproximado por etapa

| Etapa | Tokens input | Notas |
|-------|-------------|-------|
| Plan (8 preguntas) | ~500 | Genera sub-preguntas |
| Search results | ~2000 | 8 queries × 5 results × 50 chars |
| Scrape content | ~15000 | 20-30 URLs × 2000 chars c/u |
| Synthesis | ~3000 output | deepseek-v4-flash, max_tokens=8192 |
| Refine | ~16000 output | Segunda pasada si <8000 chars |

Total input estimado: ~25000 chars (~6000 tokens con deepseek-v4-flash).

## Notas

- deepseek-v4-flash tiene 1M de contexto, pero en la práctica devuelve respuestas vacías si el prompt es muy largo o tiene demasiadas fuentes
- El truncado agresivo (2000 chars/entry) es necesario para 30 fuentes
- Si el reporte sigue siendo corto (<8000 chars), el refine lo expande
- Si el refine empeora el reporte, el guard lo descarta
