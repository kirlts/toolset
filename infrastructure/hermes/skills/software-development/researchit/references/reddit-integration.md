# Reddit Integration — ResearchIt

## Via Composio MCP

Las búsquedas Reddit se hacen vía Composio MCP (herramienta `REDDIT_SEARCH_ACROSS_SUBREDDITS`).

**Connection ID (de Infisical/env):** `COMPOSIO_REDDIT_CONNECTION_ID`
**API Key (de Infisical/env):** `COMPOSIO_API_KEY`

## Queries usadas para ballenas (ejemplo)

| Query | Idioma | Resultados |
|-------|--------|------------|
| `whales` | inglés | 25 posts (score 100K+) |
| `ballenas` | español | 25 posts (score 500-) |
| `cetaceans` | inglés | 25 posts (score 1K+) |

## Parámetros óptimos

- `sort: "relevance"` (mejores resultados)
- `limit: 25` (máximo por query, 100 max)
- `restrict_sr: true` (solo posts, no subreddits)

## Formato de resultado

Cada post tiene: author, created_utc, id, num_comments, over_18, permalink, score, selftext (hasta 2000 chars), subreddit, title, url.

## Inyección en pipeline

Los posts se guardan como JSON en `vault/reddit_{topic}.json` y se pasan a research.py:

```bash
python -m src.research "tema" --max-sources 30 --reddit-file vault/reddit_tema.json
```

Se inyectan hasta 15 posts Reddit con score normalizado (score/50000, capped at 1.0) como fuentes adicionales en la etapa de síntesis.

## Rate limit

Máximo ~1-2 requests/segundo. 3 queries paralelas funcionan sin problemas.

## Arquitectura futura

Idealmente, reddit_search.py debería llamar a Composio MCP directamente desde el pipeline Python, no requerir prefetch manual de Hermes. Pendiente para V2.0 cuando el SDK de Composio esté disponible.
