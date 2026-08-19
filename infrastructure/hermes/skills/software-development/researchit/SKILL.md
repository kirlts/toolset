---
name: researchit
description: "ResearchIt — DIY Deep Research Engine. SearXNG + httpx/BS4 + deepseek-v4-flash + Typst. Investigación profunda asíncrona con entrega de PDF por WhatsApp."
version: 1.2.0
author: Hermes Agent / Toolset Personal
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [research, deep-research, searxng, typst, pdf]
    related_skills: [kilo-code, markitdown-converter]
---

# ResearchIt — Deep Research Engine

## Descripción

ResearchIt es un motor de investigación profunda auto-hospedado que reemplaza a Gemini Deep Research. Corre completamente en el VPS (ARM64, OL9), 100% gratuito, sin APIs de pago.

## Pipeline (v4 — presupuesto por páginas, estilo Gemini, 2026-08-08)

**Filosofía (decisión de Martín):** ResearchIt decide CUÁNTOS capítulos hace (el plan elige libremente según el tema, típicamente 4-10) y el presupuesto TOTAL (máx. de páginas) se REPARTE automáticamente entre ellos. Nada de hardcodear el número de capítulos ni un target rígido de palabras: solo se le dice el requerimiento máximo de páginas. Eso replica el enfoque de Gemini Deep Research.

1. **Plan** — deepseek-v4-flash genera las preguntas NECESARIAS (4-10 según complejidad del tema; sin forzar número). Tema truncado a 1500 chars (temas largos causan respuesta vacía intermitente), parseo robusto (JSON/fences/listas), retry 3x ante vacío + RuntimeError explícito.
2. **Reparto de presupuesto** — `--max-pages` (default 45) × `_CHARS_PER_PAGE` (900, rendimiento medido del PDF ~814-970) = presupuesto total de chars, dividido entre N capítulos → target de palabras por capítulo (clamp 450-1500).
3. **Search** — SearXNG busca cada pregunta EN PARALELO (semáforo 4), 8 resultados c/u.
4. **Dedup + Scrape** — deduplica URLs; httpx+BS4 extrae contenido (lotes de 5, 6K chars/URL), máx 40 fuentes por defecto.
5. **Synthesize POR CAPÍTULO** — cada capítulo recibe su target_words dinámico en el prompt ("Presupuesto: ~N palabras, tolerancia ±25%") y sintetiza SUS fuentes, en paralelo (semáforo 4). max_tokens=8192, contexto 20K chars. Retry 3x por capítulo ante respuesta vacía. Capítulos stub (<1500 chars tras retries) se eliminan.
6. **Pase editorial (condensación)** — si un capítulo excede target×1.25, una llamada de condensación lo comprime al presupuesto PRESERVANDO hechos, datos, veredictos y fuentes; elimina redundancia y prosa vacía. Retry 3x contra vacíos. Acepta rango 0.5-1.5×target. NO es truncado a cuchillo ni refine expansivo: es draft → editor (estándar industria).
7. **Post-proceso** — dedupe de headers '# Capítulo N' (exactos y stubs) + strip de secciones internas redundantes que el modelo a veces inserta ('# Resumen Ejecutivo', '# Introducción', '# Desarrollo', '# Conclusiones', '# Referencias').
8. **PDF** — Typst compila el MD completo. report.py escapa funciones Typst que el modelo escribe en el texto (`#cite(...)`, `#bibliography(...)`) preservando `#link()` y `#raw()`.
9. **Delivery** — Hermes lee el PDF de `vault/` y lo envía por WhatsApp como attachment nativo.
   - **CRITICAL**: `MEDIA:` tag debe estar en su PROPIA LÍNEA, SIN backticks, SIN markdown, SIN emojis decorativos en la misma línea. Ejemplo correcto:
     ```
     MEDIA:/opt/researchit/vault/researchit_tema_20260706_123456.pdf
     ```
   - Verificar que el PDF existe con `ls -la` ANTES de referenciarlo en MEDIA
   - Siempre usar ruta ABSOLUTA

**Lección MCP-vs-CLI (2026-08-08):** en investigaciones de herramientas, definir SIEMPRE con el usuario qué cobertura ya tiene (MCPs en uso, CLIs, tools nativas del agente) ANTES de evaluar candidatos. Evaluar contra la premisa "¿esto resuelve una necesidad que no puedo resolver igual o mejor con lo que ya tengo?". Evita informes de 187 páginas para una conclusión de 2 líneas.

## Prerrequisitos

- SearXNG en localhost:4000 (servicio `searxng` en el docker-compose de toolset, `kirlts/toolset/infrastructure/docker-compose.yml`). Corre como `--user root` por compatibilidad ARM64/SELinux.
- Repo en `/opt/researchit/` (clonado desde `kirlts/researchit`)
- Python 3.11+ con `pip install -r requirements.txt`
- Typst instalado (se auto-instala en primera ejecución)

## Invocación desde Hermes

Hermes invoca ResearchIt como subproceso Python. La API key requiere `set -a` para exportarse correctamente:

```bash
set -a && source /home/opc/.hermes/.env && set +a && cd /opt/researchit && python3 -m src.research "tema" --max-sources 30
```

**Parámetros clave:**
- `--max-pages 45` (default): presupuesto máximo de páginas del informe. El pipeline reparte este total entre los capítulos que el plan decida.
- `--max-sources 40` (default): máximo de fuentes scrapeadas
- `--no-pdf`: solo Markdown, sin PDF
- `--language en`: búsqueda en inglés
- `--reddit-file vault/reddit_{topic}.json`: formato **`{"results": [{"title", "url", "content", "score"}]}`** (NO "posts" — el código lee `reddit_data.get("results")`)

Output:
- Markdown: `vault/researchit_{topic}_{timestamp}.md`
- PDF: `vault/researchit_{topic}_{timestamp}.pdf`

## Generación de PDF (mobile-friendly)

El PDF se genera con Typst usando `templates/report.typ`. Configuración:

| Parámetro | Valor |
|-----------|-------|
| Fuente | DejaVu Sans 11pt |
| Alineación | Justificado |
| Márgenes | 1.6cm laterales, 1.2cm verticales |
| Títulos H1 | 17pt bold, con pagebreak |
| Títulos H2 | 14pt bold |
| Títulos H3 | 12pt bold |
| Links | Azul #1a56db |

**NO usar cmarker** — no funciona en este entorno. La conversión MD→Typst es directa vía `report._md_to_typst()`.
**NO fallback raw** — la compilación es una sola ruta limpia sin cmarker.

Si el PDF no se genera, revisar:
1. `typst compile` corre desde el directorio del output (cwd)
2. La template report.typ existe en `templates/`
3. Las fuentes disponibles son: Cantarell, DejaVu Sans/Mono, Libertinus Serif, Source Code Pro

## Uso directo CLI

```bash
# Investigación básica
python -m src.research "impacto de la IA en la medicina 2026"

# Sin PDF (solo Markdown)
python -m src.research "tema" --no-pdf

# Control de fuentes
python -m src.research "tema" --max-sources 5 --language en

# Directorio custom
python -m src.research "tema" --output-dir /tmp/reports
```

## Arquitectura

| Módulo | Función |
|---|---|
| `src/search.py` | Cliente SearXNG (localhost:4000, formato JSON) |
| `src/scrape.py` | Scraping async con httpx+BS4 |
| `src/synthesize.py` | Síntesis con deepseek-v4-flash vía OpenCode Go |
| `src/report.py` | Generación PDF con Typst |
| `src/research.py` | Orquestador principal (pipeline 7 etapas) |

## Token Optimization (v4)

- Truncado a **2K chars por entrada** de búsqueda; contexto por capítulo **20K chars**
- Priorización por score de SearXNG (las mejores fuentes primero)
- **Síntesis por capítulos**: el informe crece con el NÚMERO de capítulos, no con refine. max_tokens=8192 por capítulo
- **Presupuesto dinámico**: `--max-pages` × 900 chars/página ÷ N capítulos = target de palabras por capítulo (clamp 450-1500)
- **Condensación editorial condicional**: solo si el capítulo excede target×1.25 (una llamada extra, retry 3x contra vacíos)
- Budget v4: ~500 tokens plan, ~2000 search, ~15000 scrape, 8192 max_tokens síntesis + condensación condicional
- 40 fuentes por defecto (configurable vía `--max-sources`)

## Reglas de calidad (preferencias de Martín)

- **NO síntesis sobre síntesis.** Martín lo dijo explícitamente (2026-08-08): el informe NO se construye refinando/expandiendo una síntesis previa. Cada capítulo es síntesis DIRECTA de fuentes frescas de su propia búsqueda. El refine global solo existe como red de seguridad del modo informe único (sin capítulos) y NO debe usarse como mecanismo de extensión. La ÚNICA segunda pasada permitida es la CONDENSACIÓN editorial (comprime preservando hechos/veredictos/fuentes), no la expansión.
- **NUNCA truncar a cuchillo.** "Pésima idea truncar un informe a la fuerza" (Martín, 2026-08-08): si el modelo da más información de la pedida y es relevante, se conserva. El control de longitud se hace por presupuesto (prompt) + condensación editorial, jamás cortando en un byte arbitrario.
- **El pipeline decide capítulos y reparte presupuesto, no el usuario.** "ResearchIt debe tener la capacidad de decidir el presupuesto y repartirlo; nosotros solo le decimos el requerimiento máximo de páginas y un mínimo según el tipo de contenido" (Martín, 2026-08-08). NO hardcodear el número de capítulos ni targets fijos.
- **Un informe corto es un error, no una elección.** Si algo queda sin cubrir, el fix es más capítulos/cobertura, nunca expandir con otra llamada LLM.
- **Paralelismo por defecto.** Búsquedas y síntesis van en paralelo con semáforo (4). Secuencial se considera un bug. Martín: "Por supuesto que debes cambiarlo a paralelo".
- **Filtrar lo que el usuario ya resuelve.** Si el encargo pide evaluar herramientas y el usuario ya usa/descarta algunas (ej: Filesystem MCP porque Claude Code tiene acceso local, GitHub MCP porque usa CLI, Supabase MCP porque ya lo usa, memoria/knowledge-graph porque su KB lo cubre, Sentry porque tiene observabilidad por CLI), NO analizarlas como candidatos: declararlas excluidas y enfocar el análisis en el resto bajo el prisma "¿esto resuelve una necesidad que no puedo resolver igual o mejor con lo que ya tengo?".

## Mantenimiento

- **Git (repo researchit):** merge directo a `main` AUTORIZADO por Martín (2026-08-08) — no crear PRs para este repo. El flujo validado: cambios en `/opt/researchit` → `kilo run "/document" --auto` (workflow Kairos de .agents/workflows/document.md sincroniza docs/) → branch hermes-* → merge a main → `git push origin main`. El repo local ES la copia desplegada (git pull no aplica; ya está al día).
- SearXNG: `docker restart researchit-searxng`
- Logs: `docker logs researchit-searxng`
- Lock: `/tmp/researchit.lock` (eliminar si una investigación se queda colgada). Un SIGTERM al proceso NO libera el lock: si matas una corrida, borra el lock manualmente antes de relanzar.
- Reportes: `vault/`

## Troubleshooting

| Problema | Causa | Solución |
|---|---|---|
| 401 en OpenCode Go | API key no exportada | Usar `set -a && source .env && set +a` |
| 0 resultados SearXNG | SearXNG caído | `docker restart researchit-searxng` |
| PDF no generado | Typst compilation error | Revisar template en templates/report.typ y fuentes disponibles (typst fonts). Ver `references/typst-escaping-pitfalls.md` para errores comunes como `unclosed delimiter`, `label does not exist`, `unknown font family`. **Error `the document does not contain a bibliography` en una línea con `#cite(...)`: el modelo escribió sintaxis Typst cruda en el texto y pandoc la pasó como código.** Fix ya aplicado en `report._md_to_typst()`: escapa `#función(` preservando `#link()` y `#raw()` (regex `#(?!(?:link|raw)\()([a-zA-Z_][a-zA-Z0-9_]*\()`). |
| .env con `***` | El archivo .env tiene valores masked (`***`) que Python lee literalmente | NO usar .env con valores masked. Usar `set -a && source /home/opc/.hermes/.env && set +a` para heredar env vars de Hermes. El .env de researchit solo debe contener valores reales o no existir. |
| 401 en OpenCode Go | API key no exportada | Usar `set -a && source .env && set +a` |
| Reporte sale con 1 solo capítulo (Reddit) o cubre solo el primer elemento | El plan devolvió 0 preguntas y el pipeline siguió sin validar (bug corregido: ahora RuntimeError tras 3 intentos) | Antes de confiar en un reporte, verificar en el log: `Plan generado: N preguntas` (esperado 4-10) y `Presupuesto: ... capítulos x ~N palabras` y `Fuentes:` (esperado >0). Si el plan dio 0, la causa típica es topic >1500 chars (ver fila siguiente). |
| Plan devuelve 0 preguntas / respuesta vacía | deepseek-v4-flash devuelve string vacío cuando el topic del prompt del plan es muy largo (>1500 chars) | `_build_sub_questions_prompt` y `synthesize` recortan el topic a 1500 chars (`topic[:1500]`). El plan tiene parseo robusto (JSON/fences/listas) + 3 reintentos + RuntimeError explícito. Al relanzar una corrida matada, borrar `/tmp/researchit.lock` primero. |
| "El informe se trunca en la página N" | CASI SIEMPRE el PDF NO está truncado: contiene todo el MD. Lo corto es la SÍNTESIS (el LLM no cubrió todas las secciones del encargo) | Diagnosticar: extraer texto del PDF (pymupdf) y comparar longitud con el MD. Si coinciden, el fix es cobertura por capítulos (una pregunta por elemento), NUNCA refine/expandir. |
| Engines bloqueados por captcha | IP del VPS (OCI datacenter) es bloqueada por buscadores independientes: startpage, brave, mojeek responden CAPTCHA o 0 resultados | Confiables desde OCI: duckduckgo, bing, wikipedia (verificados 2026-08-08). Los demás deshabilitados en settings.yml. No perder tiempo reactivándolos. |
| Editar settings.yml de SearXNG | Bind mount de /opt/researchit/searxng es propiedad de uid 977 (SearXNG container). El restart del contenedor re-owna el dir a 977 y rompe futuros edits como opc | `sudo chown opc:opc /opt/researchit/searxng/` y luego patch. Para aplicar cambios SIN restart (evita re-chown): `docker kill -s HUP researchit-searxng` (recarga settings, granian). |
| Síntesis devuelve 0 caracteres | El LLM devolvió vacío (temas largos, fuentes pobres, rate limit) | Retry 3x por capítulo ya implementado. Si TODOS los capítulos salen vacíos, revisar el topic (recortar a 1500 chars), la API key y reintentar. |
| Condensación devuelve 0 palabras o fuera de rango | deepseek-v4-flash devuelve vacío intermitente en llamadas largas; target de compresión muy agresivo (3000→700) falla | `condense_chapter` reintenta 3x ante vacío. Rango de aceptación 0.5-1.5×target; si el condensado queda fuera o vacío, se conserva el original con warning (nunca empeorar). Targets realistas: compresión 3000→800 es factible, 3000→700 con menos margen. |
| Informe con capítulos duplicados o secciones '# Resumen Ejecutivo/# Desarrollo' internas | El modelo a veces repite el título del capítulo dentro del cuerpo o inserta estructura completa de informe en un capítulo | Post-proceso ya implementado: `_dedupe_chapter_headers` (exactos + stubs con gap <500 chars) y `_strip_internal_report_headers` (elimina headers internos sin numeración de capítulo hasta el próximo '# Capítulo N'). |
| MEDIA tag no entrega PDF en WhatsApp | MEDIA: fue escrita dentro de backticks o markdown (```MEDIA:/path```) en lugar de línea aparte sin formato | La línea `MEDIA:/ruta/al/archivo.pdf` debe estar SOLA, sin backticks, sin emojis, sin markdown alrededor. Solo así el bridge de WhatsApp la parsea como attachment. |

## Reddit Integration

ResearchIt puede incluir hasta 15 resultados de Reddit como fuentes adicionales. Los resultados se obtienen vía **Composio MCP** (herramienta `REDDIT_SEARCH_ACROSS_SUBREDDITS`) y se pasan al pipeline como archivo JSON.

**Flujo:**
1. Hermes ejecuta búsquedas Reddit vía `mcp_composio_COMPOSIO_MULTI_EXECUTE_TOOL` con queries en inglés y español
2. Los resultados se guardan en `vault/reddit_{topic}.json`
3. Se pasan a research.py vía `--reddit-file vault/reddit_{topic}.json`
4. research.py inyecta hasta 15 resultados Reddit con score normalizado en la etapa de síntesis

**Ejemplo:**
```bash
python -m src.research "tema" --max-sources 30 --reddit-file vault/reddit_tema.json
```

Los secrets de Composio (API key, connection_id) se manejan vía Infisical/env vars, NO hardcodeados.

## Cron Integration

ResearchIt puede ejecutarse como cron job semanal para entregar informes periódicos vía WhatsApp. El patrón típico:

1. Cron job con skill `researchit` cargada y `deliver: origin`
3. ResearchIt genera PDF en `vault/`
4. El agente del cron encuentra el PDF más reciente (`ls -t /opt/researchit/vault/*.pdf | head -1`), verifica que existe, y lo entrega con `MEDIA:` en línea aparte (sin backticks, sin markdown alrededor de la línea MEDIA)

**Pitfall — múltiples PDFs generados en una ejecución:** El agente del cron no debe asumir un solo PDF. Si el cron generó N reportes (e.g., dos temas diferentes en la misma ejecución programada), TODOS deben entregarse. NO hacer `ls -t ... | head -1`. En su lugar, encontrar todos los PDFs creados después del inicio de la ejecución actual, ordenar por tiempo de creación, y entregar cada uno con su propia línea `MEDIA:`.

```python
import glob, os, time
batch_start = time.time()
pdfs = sorted(glob.glob("/opt/researchit/vault/researchit_*.pdf"), key=os.path.getctime)
for pdf in pdfs:
    if os.path.getctime(pdf) >= batch_start - 60:  # created during this run
        print(f"MEDIA:{pdf}")  # one line per PDF
```

Si ocurre que un PDF no se entrega (síntoma: el reflect lo menciona como "pendiente" días después), verificar:
1. ¿El cron generó >1 PDF pero el agente solo tomó el primero?
2. ¿El archivo aún existe en `vault/`? (Si pasaron 4+ días, puede haber sido limpiado.)
3. Si el archivo ya no existe, la única opción es re-ejecutar la investigación.

Ver `references/weekly-cron-patterns.md` para el patrón completo de inteligencia laboral semanal y ejemplos de configuración.

Ver `references/pipeline-v2-chapters.md` para la migración a síntesis por capítulos: cambios de código, pitfall del plan vacío con temas largos, lock stale tras kill, y diagnóstico de "informe truncado".

Ver `references/pipeline-v4-budget.md` para la evolución v1→v4, decisiones de Martín (presupuesto por páginas estilo Gemini, NO truncar, condensación editorial como única segunda pasada), modos de falla de deepseek-v4-flash (respuestas vacías intermitentes), fix del `#cite` en Typst, y fórmulas del reparto de presupuesto.

## Mobile PDF — Formato para WhatsApp

El PDF está optimizado para lectura en teléfonos móviles:

| Parámetro | Valor |
|-----------|-------|
| Fuente | DejaVu Sans 11pt (disponible en ARM64/OL9) |
| Alineación | Justificado con leading 0.7em |
| Márgenes | 1.6cm laterales, 1.2cm verticales |
| Títulos H1 | 17pt bold, con pagebreak, fondo azul marino (texto blanco), radius 4pt |
| Títulos H2 | 14pt bold, fondo gris claro (#e8f0fe), texto azul (#1e3a5f) |
| Títulos H3 | 12pt bold, texto azul (#2d5a87) |
| Links | Azul #1a56db |
| Raw blocks | Fondo gris (#f1f5f9), texto 7.5pt |
| Strong/Bold | Texto #1e293b |
| Encabezado/Footer | Texto gris suave (#94a3b8 / #cbd5e1) |

**NO usar cmarker** — no funciona en este entorno. La conversión MD→Typst es directa vía `report._md_to_typst()`.
**NO hay bold/italic conversion** — el texto con `*` y `_` se escapa completamente para evitar errores de "unclosed delimiter" en Typst. Los únicos formatos inline convertidos son: `codigo` → `raw()`, y `[texto](url)` → `#link()`.

## Secrets Management

Todos los secrets se manejan vía **Infisical** + **GitHub Secrets**. NO hardcodear en código.

**Variables requeridas:**
- `COMPOSIO_API_KEY` — API key de Composio (para Reddit via MCP)
- `COMPOSIO_REDDIT_CONNECTION_ID` — connection ID de Reddit en Composio
- `OPENCODE_GO_API_KEY` — API key de OpenCode Go
- `OPENCODE_GO_BASE_URL` — URL base de OpenCode Go (default: https://opencode.ai/zen/go/v1)

**Resolución de secrets (por orden de prioridad):**
1. Infisical SDK (`INFISICAL_SERVICE_TOKEN` en env → `InfisicalClient.get_secret()`)
2. Variable de entorno directa (`os.getenv()`)
3. Warning en log si no se encuentra

**Exportación correcta:**
```bash
set -a && source /home/opc/.hermes/.env && set +a
```

Sin `set -a`, las variables no se exportan a procesos hijo (Kilo, Python) y fallan con 401 o "Missing API key".
