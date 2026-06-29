# ResearchIt — Cron Integration Patterns

## Pattern 1: Weekly Job Market Intelligence

Created 29-Jun-2026. Delivers every Monday at 12:00 Chile (16:00 UTC) to the user's DM.

### Agent prompt structure

The cron job runs as an LLM-driven agent (not no_agent) with the `researchit` skill loaded. The prompt should:

1. **Gather context** — Use `gh search commits --author=kirlts --limit=10` and `gh search issues --author=kirlts --state=open` for recent activity
2. **Define research topic** — Based on GitHub activity + user's static profile (stack, projects, interests), pick a specific job market / industry intelligence topic
3. **Invoke ResearchIt** — Standard invocation:
   ```bash
   set -a && source /home/opc/.hermes/.env && set +a && cd /opt/researchit && python3 -m src.research "specific topic" --max-sources 30 --language es
   ```
4. **Deliver** — Find the PDF with `ls -t vault/*.pdf | head -1` and include `MEDIA:/opt/researchit/<path>` in the response, plus a 2-3 line summary

### Cron job definition

```json
{
  "name": "researchit-job-market-weekly",
  "schedule": "0 16 * * 1",
  "skills": ["researchit"],
  "deliver": "origin",
  "repeat": "forever"
}
```

## Pattern 2: Self-Contained Research Cron (no agent)

For pure data-collection without LLM reasoning:

```json
{
  "name": "researchit-scheduled-topic",
  "schedule": "0 6 * * 3",
  "script": "/opt/researchit/run-topic.sh",
  "no_agent": true,
  "deliver": "origin"
}
```

The script handles env sourcing, researchit invocation, and outputs the PDF path.

## Pitfalls

- **API key scoping**: Without `set -a`, env vars from .env don't propagate to child processes (Python). Always use `set -a && source .env && set +a`.
- **Timeout**: ResearchIt can take 2-5 minutes for a full run with 30 sources. Cron jobs have generous timeouts but very long runs (>10 min) may need `background=true` in terminal calls within the prompt.
- **Stale context**: The static profile (stack, projects, interests) hardcoded in the prompt will drift. Refresh periodically by recalling from personal-profile bank or updating the cron prompt.
- **gh CLI auth**: `gh` must be authenticated as kirlts for the context-gathering step. If gh CLI is not available, fall back to the static profile only.
- **PDF path discovery**: The `ls -t vault/*.pdf` approach picks the most recent PDF. If multiple researchit runs happen in the same cron tick, tag outputs by topic for deterministic discovery.
