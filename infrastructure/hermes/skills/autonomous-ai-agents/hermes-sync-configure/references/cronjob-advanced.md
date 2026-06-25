# Cronjob Advanced Patterns — Reference

## Reddit Chile Daily PDF Report (working example)

Created 2026-06-24. Serves as a reference for any "daily digest via PDF + WhatsApp" cronjob.

### Architecture

```
cronjob (12:00 UTC = 8am Chile)
  → Composio MCP (REDDIT_GET_R_TOP) — fetch posts from 3 subreddits
  → Python fpdf2 — generate single-page PDF summary
  → Cron deliver — MEDIA:/path/to/report.pdf via WhatsApp
```

### Cron job config

```json
{
  "name": "reddit-chile-daily-report",
  "schedule": "0 12 * * *",
  "deliver": "origin",
  "last_status": "ok"
}
```

### Full prompt used

```
Genera un reporte PDF diario de Reddit Chile y envíalo por WhatsApp.

INSTRUCCIONES:

1. FETCH posts de los últimos 24h:
   - Usa COMPOSIO_MULTI_EXECUTE_TOOL con 3 tools en paralelo:
     - REDDIT_GET_R_TOP: subreddit="chile", t="day", limit=10
     - REDDIT_GET_R_TOP: subreddit="chileit", t="day", limit=10
     - REDDIT_GET_R_TOP: subreddit="republicadechile", t="day", limit=10
   - Pasa session_id="moon" a todos los calls de Composio.

2. Para los 3 posts con mayor engagement (score × num_comments) de cada subreddit,
   fetch comments usando REDDIT_RETRIEVE_POST_COMMENTS (article_id = campo "id")

3. Genera resumen en texto plano con:
   - Título: "Resumen Reddit Chile - [fecha]"
   - Por subreddit: top posts con título, autor, score, num_comments, url
   - 1-2 comentarios destacados de posts más activos

4. Convierte a PDF con Python fpdf2:
   - Usa DejaVuSans (DejaVuSans.ttf + DejaVuSans-Bold.ttf)
   - NO uses emojis ni Unicode raro (DejaVuSans no los soporta todos)
   - Guarda en /tmp/reddit-chile-report-[YYYY-MM-DD].pdf
   - Single page: título grande, secciones por subreddit, métricas, citas

5. ENTREGA:
   - Respuesta FINAL = SOLO: MEDIA:/tmp/reddit-chile-report-[YYYY-MM-DD].pdf
   - Sin texto adicional, markdown, ni explicaciones
```

### Key details that made it work

| Detail | Value | Notes |
|---|---|---|
| Composio session_id | `moon` | Generated once, reused across ALL calls |
| Reddit time filter | `t="day"` | NOT `time_filter` — different tools use different param names |
| PDF font | DejaVuSans (`/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf`) | Helvetica doesn't support Unicode |
| fpdf2 install target | `/usr/local/lib/hermes-agent/venv/` | pip via the Hermes venv |
| WhatsApp delivery | `MEDIA:` in cron response | Must be the ONLY line; extra text breaks attachment delivery |
| Cron deliver mode | `origin` | Sends to the chat that created the job |

### Verification

After creating the cronjob, run it immediately with `cronjob(action='run', job_id='...')` and check the output log:
```
cat ~/.hermes/cron/output/<job_id>/<timestamp>.md
```
The log should show `MEDIA:/path/to/file.pdf` — that's the delivery instruction.
Check PDF was generated: `ls -la /tmp/reddit-chile-report-*.pdf`.

### Common cron job mistakes (these all happened)

- **Race condition**: Two jobs scheduled at same time writing to same repo = push divergence.
- **Broad git add**: `git add infrastructure/hermes/` commits banks/ files from the other job.
- **No pull before push**: Second job's push fails after first job already pushed.
- **Wrong Composio session_id**: New calls need the original session_id, not a new one.
- **Emoji in PDF**: DejaVuSans lacks most emoji. Use plain Unicode or ASCII.
- **Extra text after MEDIA:**: The delivery system parses the ENTIRE response. Any text beyond the MEDIA: line breaks attachment delivery — WhatsApp receives text instead of a file.
- **Missing full path in MEDIA:**: Must be absolute path starting with /.

### When to use this pattern

This pattern (cronjob → MCP data fetch → PDF generation → MEDIA: delivery) works for any daily digest:
- Reddit subreddit summaries
- RSS/feed digests
- GitHub trending repos
- News headlines
- Weather/climate reports
- Market summaries

Replace the MCP tool, adjust the prompt's data extraction steps, keep the fpdf2 + MEDIA: pattern identical.
