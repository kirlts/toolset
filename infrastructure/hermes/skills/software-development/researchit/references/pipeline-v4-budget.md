# Pipeline v4 — evolución y decisiones (2026-08-08)

Sesión de investigación MCP servers (encargo real de Martín) que evolucionó el pipeline ResearchIt de v1 a v4. Este archivo documenta QUÉ cambió, POR QUÉ, y los modos de falla observados, para que futuras iteraciones no repitan el descubrimiento.

## Evolución v1 → v4

| Versión | Mecanismo | Resultado típico | Problema |
|---|---|---|---|
| v1 | Síntesis única de todo el corpus (max_tokens 8192) + refine si <8K chars | 14K chars ≈ 15 páginas | Informe corto, cubría 1 de 18 elementos; "truncado en página 15" |
| v2 | Síntesis por capítulo (1 por sub-pregunta del plan, 10-16 preguntas), paralelo | 455K chars ≈ 400+ páginas | Explosión de tamaño; repetición de contexto; 2-3x el objetivo |
| v3 | Prompt de densidad + max_tokens 12288 → 4096 → 6144 | 35K-131K chars | El modelo ignora el rango de palabras del prompt (escribe 2-3x); tamaño inestable |
| v3.1 | Techo duro 7000 chars/capítulo (truncado post-hoc) | 51 páginas | MARTÍN LO RECHAZÓ: "pésima idea truncar a la fuerza, corta información relevante" |
| v4 | Presupuesto por páginas (`--max-pages` 45) repartido entre N capítulos que el plan decide + condensación editorial condicional | objetivo 40-50 páginas | — |

## Decisiones de diseño (voz de Martín)

1. **No hardcodear el número de capítulos.** "No sé si hardcodear el número de capítulos está bien... ResearchIt debe decidir cuántos capítulos hace, pero debe saber de antemano cuántos va a hacer y ahí recién se ajusta el presupuesto de palabras por capítulo."
2. **Reparto automático del presupuesto.** El pipeline calcula: `max_pages × CHARS_PER_PAGE ÷ N capítulos = target_words por capítulo` (clamp 450-1500).
3. **Presupuesto total por páginas, mínimo según tipo de contenido.** "Nosotros solo le decimos el requerimiento máximo de páginas y un mínimo... eso es lo que hace Gemini."
4. **La condensación editorial es la ÚNICA segunda pasada permitida.** draft → editor (comprime preservando hechos/veredictos/fuentes). Prohibidos: refine expansivo ("síntesis sobre síntesis") y truncado a cuchillo.

## Modos de falla observados (deepseek-v4-flash vía OpenCode Go)

### Respuesta vacía intermitente (plan, síntesis, condensación)
El modelo devuelve `content=""` de forma intermitente (~30-50% en llamadas largas). NO es determinista por tema largo: una reproducción con el MISMO prompt largo devolvió contenido completo. El "fix" de truncar el topic a 1500 chars ayuda pero no elimina: la solución real es **retry 3x en cada etapa** (plan, síntesis por capítulo, condensación) + RuntimeError explícito en el plan.
- Diagnóstico: `finish_reason: stop`, `content: None/""`, `reasoning_tokens` altos (1165+). El modelo "piensa" pero no emite texto.

### El modelo ignora el contrato de palabras del prompt
Con "entre 1000 y 1300 palabras" escribió 3000-5000. Con "máximo 1100" escribió ~5000 (35K chars totales). Con "600-800" escribió 2000-3000. La lección: NO confiar en el prompt para control de longitud; el control REAL es (a) presupuesto como contrato en la tarea y (b) condensación editorial condicional tras el conteo.

### Condensación fuera de rango
- Con target 950: condensados de 667-1199 palabras (rango aceptación 0.5-1.4 era 475-1330... algunos quedaron fuera → se conservó original).
- Con target 700: 3 de 5 devolvieron VACÍO (0 palabras) → conservar original.
- Fix: retry 3x contra vacíos + rango de aceptación 0.5-1.5×target + `c_words < words` (nunca empeorar).
- Compresión realista: 3000→800 funciona; 3000→700 con menos margen.

### Typst `the document does not contain a bibliography`
El modelo escribió `#cite(label("..."))` en el texto; pandoc (MD→Typst) lo pasó como código Typst y Typst falló sin bibliografía. Fix en `report._md_to_typst()` post-process:
```python
typst = re.sub(r"#(?!(?:link|raw)\()([a-zA-Z_][a-zA-Z0-9_]*\()", r"\\#\1", typst)
```
Preserva `#link()` y `#raw()` (generados por pandoc), escapa `#cite()`, `#bibliography()`, etc.

### Lock stale tras SIGTERM
`/tmp/researchit.lock` no se libera si matas el proceso (el `finally: _release_lock()` no corre bajo SIGTERM). Al relanzar tras un kill: `rm -f /tmp/researchit.lock` primero. (Ya documentado en Mantenimiento, se re-confirmó.)

### Reddit file format
El código lee `reddit_data.get("results")` — el archivo DEBE ser `{"results": [{"title", "url", "content", "score"}]}`. Un JSON con `{"posts": [...]}` se ignora silenciosamente (0 resultados inyectados; el informe dice "la URL del hilo no fue proporcionada").

## Métricas de rendimiento del PDF

- **Chars por página del PDF**: ~814-970 (depende de headers/tablas). Usar 900 para presupuesto (`_CHARS_PER_PAGE`).
- **Chars por palabra en español**: ~6.6 (`_CHARS_PER_WORD`).
- Fórmula del reparto: `per_chapter_words = clamp((max_pages * 900) / N / 6.6, 450, 1500)`.

## Post-proceso de limpieza (ya implementado)

- `_dedupe_chapter_headers(md)`: elimina headers '# Capítulo N' exactos consecutivos y stubs (header con <500 chars de contenido antes de otro header del MISMO número → se reemplaza por el segundo).
- `_strip_internal_report_headers(md)`: elimina secciones '# Resumen Ejecutivo / Introducción / Desarrollo / Conclusiones / Referencias / Metodología' (sin numeración de capítulo) y su contenido hasta el próximo '# Capítulo N' — son re-síntesis del informe completo que el modelo inserta dentro de un capítulo y duplican contenido.
