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

## Pipeline

1. **Plan** — deepseek-v4-flash genera 8 sub-preguntas de investigación
2. **Search** — SearXNG (Docker, localhost:4000, puerto 4000) busca cada sub-pregunta (5 resultados c/u)
3. **Dedup** — Deduplica URLs por normalización
4. **Scrape** — httpx+BS4 extrae contenido textual (lotes de 5, 6K chars/URL)
5. **Synthesize** — deepseek-v4-flash sintetiza reporte estructurado (Markdown, temperature=0.3, max_tokens=8192)
6. **Refine** — Si reporte <8000 chars, expande a 5000+ palabras con segunda llamada LLM
7. **PDF** — Typst compila Markdown a PDF. Sin cmarker. Conversión directa MD→Typst vía `_md_to_typst()`
8. **Delivery** — Hermes lee el PDF de `vault/` y lo envía por WhatsApp (MEDIA:/path/to/file)

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
- `--max-sources 30` (default, antes era 10): mínimo 30 fuentes para reportes robustos
- `--no-pdf`: solo Markdown, sin PDF
- `--language en`: búsqueda en inglés

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

## Token Optimization

- Truncado a **2K chars por entrada** de búsqueda (bajado de 4K para evitar saturación con 30+ fuentes)
- Total máximo de contenido: **25K chars** (bajado de 30K para evitar respuesta vacía del LLM)
- Priorización por score de SearXNG (las mejores fuentes primero)
- Progressive refinement: si reporte <8000 chars, expande a 5000+ palabras con segunda llamada LLM
- **Refine inteligente**: si el refine produce un resultado más corto que el original, se conserva el original (evita que refine empeore el reporte)
- System prompt exige explícitamente "Mínimo 3000 palabras. No respondas con vacío."
- Budget-aware: ~500 tokens plan, ~2000 search, ~15000 scrape, ~8192 synthesis (~25000 total input)
- 30 fuentes por defecto (configurable vía `--max-sources`, default 30)

## Mantenimiento

- SearXNG: `docker restart researchit-searxng`
- Logs: `docker logs researchit-searxng`
- Lock: `/tmp/researchit.lock` (eliminar si una investigación se queda colgada)
- Reportes: `vault/`

## Troubleshooting

| Problema | Causa | Solución |
|---|---|---|
| 401 en OpenCode Go | API key no exportada | Usar `set -a && source .env && set +a` |
| 0 resultados SearXNG | SearXNG caído | `docker restart researchit-searxng` |
| PDF no generado | Typst compilation error | Revisar template en templates/report.typ y fuentes disponibles (typst fonts). Ver `references/typst-escaping-pitfalls.md` para errores comunes como `unclosed delimiter`, `label does not exist`, `unknown font family`. |
| .env con `***` | El archivo .env tiene valores masked (`***`) que Python lee literalmente | NO usar .env con valores masked. Usar `set -a && source /home/opc/.hermes/.env && set +a` para heredar env vars de Hermes. El .env de researchit solo debe contener valores reales o no existir. |
| 401 en OpenCode Go | API key no exportada | Usar `set -a && source .env && set +a` |
| Reporte corto | Pocas fuentes con contenido útil | Aumentar --max-sources (default 30) o mejorar queries de SearXNG |

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
