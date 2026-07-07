# ResearchIt — Cron Integration Patterns

## Pattern 1: Weekly Job Market Intelligence

Created 29-Jun-2026. Delivers every Monday at 12:00 Chile (16:00 UTC) to the user's DM.

### Agent prompt structure

The cron job runs as an LLM-driven agent (not no_agent) with the `researchit` skill loaded. The prompt should:

1. **Gather context** — Use `gh search commits --author=kirlts --limit=10 --order=desc --json=repository,commit,url` and `gh search issues --author=kirlts --state=open --limit=5 --json=title,repository,createdAt` for recent activity. **Known quirk**: `gh search commits` does not expose `message` or `createdAt` as top-level JSON fields — they nest inside the `commit` object. Always request `--json=commit` and parse `commit.message` / `commit.author.date`.
2. **Define research topic** — Based on GitHub activity + user's static profile (stack, projects, interests), pick a specific job market / industry intelligence topic. **Avoid duplicates**: check `ls /opt/researchit/vault/*.pdf` to see which topics were already covered and pick a different angle.
3. **Invoke ResearchIt** — Standard invocation:
   ```bash
   set -a && source /home/opc/.hermes/.env && set +a && cd /opt/researchit && python3 -m src.research 'specific topic' --max-sources 30 --language es
   ```
4. **Deliver** — Find the PDF with `ls -t /opt/researchit/vault/*.pdf | head -1`, verify it exists with `ls -la`, then include `MEDIA:/opt/researchit/<path>` on its OWN line (no backticks, no markdown formatting around the MEDIA line). Add a 2-3 line summary as separate text.

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
- **Timeout**: ResearchIt can take 2-5 minutes for a full run with 30 sources. The refine step (second LLM pass, triggered when first pass returns <8000 chars) is the most expensive, often ~3 min alone. Cron jobs should set generous timeouts (600s+) on the terminal call. If the first-pass synthesis returns 0 chars (known edge case with low-quality sources), the refine still recovers — don't abort early.
- **Stale context**: The static profile (stack, projects, interests) hardcoded in the prompt will drift. Refresh periodically by recalling from personal-profile bank or updating the cron prompt.
- **gh CLI auth**: `gh` must be authenticated as kirlts for the context-gathering step. If gh CLI is not available, fall back to the static profile only.
- **gh JSON field discovery**: `gh <command> --json` lists available fields but they vary by subcommand. Run `gh search commits --json=""` (empty string) to see valid fields for that specific subcommand — do not assume fields from `gh api` or other gh subcommands carry over. Commits nest `message` and `date` inside a `commit` object.
- **Vault topic dedup**: Always check `/opt/researchit/vault/*.pdf` before committing to a topic. Two reports on the same theme the same week waste compute and produce stale insight for the user.
- **PDF path discovery**: The `ls -t vault/*.pdf` approach picks the most recent PDF. If multiple researchit runs happen in the same cron tick, tag outputs by topic for deterministic discovery.
- **MEDIA formatting**: The `MEDIA:/path` line must be on its own line with NO surrounding backticks, NO markdown, NO emojis on the same line. The WhatsApp bridge only parses `MEDIA:` when it's bare text at line start. Writing ``MEDIA:/path`` inside backticks or `📎 MEDIA:/path` with emoji prefix will silently fail — the file won't be attached.
