# /learn — Creating Skills from Sources

Reference: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills#learning-a-skill-from-sources-learn

## What it is

`/learn` is the fast way to turn reference material into a reusable user-local skill (`~/.hermes/skills/`) without hand-writing SKILL.md. The agent gathers material with its existing tools (web_extract, read_file, search_files), then authors a skill following Hermes skill standards and saves it with `skill_manage`.

Works in: CLI, messaging gateway, TUI, dashboard.

## Usage patterns

| Source | Example |
|---|---|
| Online doc | `/learn https://docs.example.com/api/quickstart` |
| Local dir | `/learn the REST client in ~/projects/sdk, focus on auth + pagination` |
| Conversation workflow | `/learn how I just deployed the staging server` |
| Pasted procedure | `/learn filing an expense: open portal, New > Expense, attach receipt, submit` |

## What /learn produces

- A SKILL.md at `~/.hermes/skills/<category>/<name>/SKILL.md`
- Follows standard frontmatter (name, description ≤1024 chars, tags, version, author)
- Follows standard structure (Overview → When to Use → body → Pitfalls → Verification)
- Hermes-tool framing — no invented commands
- The write-approval gate (`skills.write_approval`) applies if enabled

## Dashboard UI

The Skills page has a "Learn a skill" button with fields for directory path, URL, and open-ended text box. It composes a `/learn` request and runs it in chat.

## Limitations

- Produces user-local skills only (in `~/.hermes/skills/`), not in-repo skills
- Quality depends on the source material quality — garbage in, garbage out
- Agent uses only its available tools to gather material — can't access private APIs or authenticated resources

## Related

- Manual skill creation via `skill_manage(action='create')`
- Hub skill installation via `hermes skills install`
