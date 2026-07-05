# Repo Context Extraction — Worked Examples

## Detection de Stale Docs

### Case: cl-concerts-db (jpgil/cl-concerts-db)

**Repo type:** Flask app legacy-familiar, modernizado via intervencion mayor ("Phoenix Rising").

**Declarative docs claimed:**
- `.cursorrules`: Flask <2.0, Python 3.7, SQLAlchemy <2.0, Werkzeug 0.16.0
- No `.agents/` directory

**Source truth revealed:**
- `requirements.txt`: Flask 3.1.2, SQLAlchemy 2.0.46, mysqlclient, pytest, Playwright
- `Dockerfile` (at `docker/Dockerfile` or `Dockerfile.prod`): Python 3.12+
- `git log`: commits from 2025-2026, modern tooling

**Verdict:** `.cursorrules` obsoleto. Fue escrito antes de la modernizacion y nunca actualizado. Ignorar sus restricciones de version. El codigo real es Flask 3.x / SQLAlchemy 2.x / Python moderno.

### Why it happens

1. `.cursorrules` is typically written once during initial setup and never revisited
2. Major refactors (dependency upgrades, stack migrations) don't update cursorrules
3. The file lives in the repo root and is NOT validated by CI

### Checklist for any repo

| Source | What to check | Staleness signal |
|---|---|---|
| `.cursorrules` | Python version, framework versions, prohibited patterns | If actual deps are newer |
| `README.md` | Setup instructions, stack description | If Dockerfile/deps differ |
| `requirements.txt` / `pyproject.toml` | Real dependency versions | This IS source truth |
| `Dockerfile` (or `docker/`) | Base image, Python version | Source truth |
| `git log --oneline -5` | Recent activity | Shows if repo is alive |
| `.github/workflows/` or CI config | Test framework, linting | Shows actual tooling |
| `.agents/` | Kairós governance presence | If absent, no delegation rules |
| Branch name | master vs devel vs main | Master = prod, devel = dev |

### When to flag

If ANY declarative doc claims a version or constraint that differs from source truth (requirements.txt / Dockerfile), flag it in the Phase 0 summary as stale. Do NOT silently adopt the doc's claims.
