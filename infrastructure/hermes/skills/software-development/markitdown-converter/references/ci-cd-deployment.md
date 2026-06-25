# CI/CD Deployment — MarkItDown

## How it's installed

MarkItDown is installed by `deploy.sh` (toolset repo: `infrastructure/deploy.sh`) into the **Hermes Agent venv** at:

```
/usr/local/lib/hermes-agent/venv/
```

The deploy script:

1. Checks if `markitdown` is already importable in the venv
2. If yes: runs `pip install 'markitdown[all]' --upgrade` (idempotent upgrade)
3. If no: runs `pip install 'markitdown[all]'` (fresh install)
4. Creates the CLI wrapper `/usr/local/bin/markitdown` that delegates to `python -m markitdown "$@"`

## Key paths

| Path | Purpose |
|------|---------|
| `/usr/local/lib/hermes-agent/venv/bin/python` | Python 3.11 that runs markitdown |
| `/usr/local/bin/markitdown` | CLI wrapper (shell script) |
| `~/.hermes/skills/software-development/markitdown-converter/SKILL.md` | Skill definition |
| `infrastructure/hermes/skills/software-development/markitdown-converter/SKILL.md` | Versioned in toolset repo |

## Python version

Hermes venv = Python 3.11.15. MarkItDown requires ≥3.10. The system Python is 3.9 — do NOT use it for MarkItDown.

## sudo requirement

The Hermes venv is owned by root. All `pip install` commands MUST use `sudo`:

```bash
sudo /usr/local/lib/hermes-agent/venv/bin/python -m pip install 'markitdown[all]'
```

## Source

GitHub: https://github.com/microsoft/markitdown
PyPI: https://pypi.org/project/markitdown/
