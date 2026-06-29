# Repo Analysis via Kilo CLI — Concrete Pattern

## Session Reference

Used during group-onboarding for the "Personal" group (2026-06-28).
Repo: `kirlts/personal` — Narrativa Mitológica (Personal Knowledge Base).

## Exact Command Used

```bash
kilo run "Dame un analisis completo del proposito y contenido del repositorio /home/opc/personal. Que tipo de informacion contiene, cual es su estructura, cuales son sus objetivos, y que conclusiones puedo sacar sobre como deberia operar el grupo de WhatsApp 'Personal' de Martin (kirlts). El repo incluye una Narrativa Mitologica (Personal Knowledge Base) con dos polos: Terreno (hechos) y Mito (accion estrategica), un compilador compile.py, documentacion en docs/ y workflows en kb/. Responde en español." --auto --dir /home/opc/personal
```

## What Kilo Did

Kilo read every file in the repo: docs/ (MASTER-SPEC, RULES, USER-DECISIONS, TODO, MEMORY, CHANGELOG, VERIFICATION, REPOMAP), knowledge-base/ (109 nodes across terreno+mito), kb/ (templates, workflows), compile.py, audit.py, .agents/. It returned a structured 6-section analysis with tables, architecture diagrams, and concrete recommendations.

## Key Findings for the Onboarding Agent

From Kilo's output, extract these structured fields:

```
PROFILE_NAME  → usually matches group or repo name
DESCRIPTION   → one sentence from the repo's README or Inicio.md
REPO          → kirlts/<name> or full URL
CWD           → /home/opc/<repo-name>
BANKS         → <group-name>-profile + <repo> if repo specified
SKILLS        → inferred from repo's workflows and .agents/ config
CONSTRAINTS   → from RULES.md in the repo (e.g. Anti-Slop, density rules)
TONE          → inferred from repo's voice (e.g. technical, dense, analytical)
WORKER_TYPE   → "default" for personal repo, "worker" for code/research repos
```

## Why This Works

Kilo uses the same model (deepseek-v4-flash) and accesses files via its own sandbox. It reads comprehensively — not just first 200 lines or 50 results — so you get the full picture without missing critical `.agents/` rules, nested knowledge-base nodes, or deeply buried config files.
