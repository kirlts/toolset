---
name: onboarding-context-ingestion
description: "Methods for ingesting onboarding context from various sources. Covers repo analysis via Kilo CLI, document conversion, voice transcription, and prior session recall. Companion to the group-onboarding skill — fills the Phase 0 patterns that the main skill references."
version: 1.1.0
platforms: [linux]
metadata:
  hermes:
    tags: [onboarding, context, ingestion, kilo, repo-analysis]
    triggers: ["/onboarding with context"]
---

# Onboarding Context Ingestion

## Purpose

When `/onboarding` is invoked with context (a repo, document, voice message, URL, or prior conversation), this skill captures the specific resolution methods for each source type. It complements the Phase 0 algorithm in `group-onboarding` with executable patterns.

## Source-Specific Methods

### 1. GitHub Repo (Kilo CLI) — with stale-doc detection

**Trigger:** User says "el contexto es este repo", "lee mi repo X", or names a GitHub repository as onboarding context.

**Rule:** Do NOT use read_file, search_files, or terminal ls/cat to explore the repo yourself. Delegate to Kilo CLI — UNLESS the user explicitly says "lee mi repo" or "read the content" (direct instruction overrides the rule).

**Steps:**

1. Clone the repo if not already present:
   ```
   gh repo clone <org>/<repo-name>
   ```
   (Use gh CLI — SSH keys may not be configured. Detect org from URL: if user says "kirlts/x" use kirlts, if "jpgil/x" use jpgil, etc.)

2. Run Kilo CLI with an analysis prompt that includes stale-doc cross-checking:
   ```
   kilo run "Dame un analisis completo del proposito y contenido del repositorio /home/opc/<repo-name>. CRITICO: verifica si la documentacion declarativa (.cursorrules, CLAUDE.md, AGENTS.md, README.md) coincide con la realidad del codigo. Para eso, compara sus afirmaciones sobre versiones de Python, framework, y dependencias contra requirements.txt, Dockerfile, pyproject.toml, y git log. Si hay discrepancia (docs desactualizadas), reportala explicitamente. Que tipo de informacion contiene, cual es su estructura, cuales son sus objetivos, y que conclusiones puedo sacar sobre como deberia operar el grupo de WhatsApp '<group-name>' de Martin (kirlts). Incluye detalles como: estructura de directorios, proposito principal, principios operativos, estado actual. Responde en español." --auto --dir /home/opc/<repo-name>
   ```

3. Kilo returns a structured analysis. Extract from it:
   - Profile name suggestion (often matches group or repo name)
   - Description (one sentence)
   - Repository path
   - Skills the profile needs
   - Constraints derived from repo's rules/RULES.md
   - Tone inferred from the repo's voice
   - Worker profile type (default vs worker)

4. Feed these into the `group-onboarding` Phase 1-3 flow, skipping questions already answered.

**Why Kilo CLI:** The user requires Kilo for ANY repo interaction, even read-only analysis. This is particularly strict for repos with `.agents/` (Kairós governance) where even reading a file directly is forbidden. The pattern `kilo run "task" --auto --dir <path>` is the universal entry point.

### 2. Attached Document

**Trigger:** PDF, DOCX, PPTX, XLSX, EPUB, TXT, CSV, JSON, XML, image, audio, ZIP file.

**Resolution:** `markitdown <file>` CLI converts to Markdown. Then read the output.

### 3. Voice Message

**Trigger:** Audio voice note from user.

**Pipeline:** STT (Groq Whisper) → transcribed text → analyze as plain text context.

### 4. URL

**Trigger:** User shares a URL as onboarding reference.

**Resolution:** Fetch and extract content via web tools, then analyze.

### 5. Prior Conversation

**Trigger:** User says "en base a lo que conversamos" or similar.

**Resolution:** `recall(bank=<group-name>-profile)` or session_search for the relevant session.

## Pitfalls

| Mistake | Correction |
|---|---|
| Using read_file on a repo with `.agents/` | Always use Kilo CLI for repo exploration |
| Trying to explore a repo before cloning it | Clone first with `gh repo clone` |
| Asking "should I read this repo" when user already said "lee mi repo" | Just do it — the user explicitly asked |
| Reading partial files from a repo to save time | Let Kilo handle the full analysis — it reads comprehensively |
| Kilo output is long but user is on WhatsApp | Summarize Kilo's output to 2-3 lines, offer the full analysis as context for Phase 1-3 |
