---
name: project-orientation
description: "Systematically orient in a new project repository using Kairos governance, Hindsight memory banks, and documentary axis reading order. Covers REPOMAP, MASTER-SPEC, RULES, infrastructure exploration, and state verification."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [orientation, onboarding, kairos, governance, hindsight, repomap, codebase-exploration]
    related_skills: [codebase-inspection, github-repo-management, plan]
prerequisites:
  commands: [gh, git]
---

# Project Orientation

Systematic approach to understanding a new project repository — especially those governed by Kairos with Hindsight memory banks. Use this skill whenever a user says "familiarízate con el repo", "examina este proyecto", "entiende la infraestructura", or you need to orient before making changes.

## Core Principle: Hindsight First, Files Second

Per Kairos **[MEM-01] Context Initialization Architecture**, the memory bank is the primary source of truth. **Always recall the project's Hindsight bank before reading any files.** This avoids saturating context window and establishes the baseline operational state.

## Standard Orientation Sequence

Execute these steps in order. Each builds on the previous one.

### Phase 1: Memory (Hindsight Bank)

1. **Identify the active banks.** Two banks are always needed:
   - **Project bank** — matches the project directory/repo name (e.g., `toolset` → bank `toolset`).
   - **User profile bank** — always bank `hermes` (user preferences, conventions, meta-rules).

2. **Run `recall` on both banks** with broad, high-budget queries, in parallel:

   ```python
   # Project context
   mcp_hindsight_selfhosted_recall(
       query="contexto completo del proyecto infraestructura arquitectura",
       bank_id="<project-name>",
       budget="high"
   )

   # User profile
   mcp_hindsight_selfhosted_recall(
       query="perfil del usuario preferencias contexto del entorno",
       bank_id="hermes",
       budget="high"
   )
   ```

3. **Store the full outputs.** Results are typically large (100+ KB with 50+ memories each). Save to temp files for later scanning (`/tmp/hermes-results/*.txt`).

4. **Scan for key memory categories** in each bank's results:

   **Project bank — look for:**
   - Infrastructure facts (`fact_type: world/observation` about OCI, services, networking)
   - Project progress (`fact_type: experience` with context `project_progress`)
   - Governance rules (`fact_type: observation` tagged `governance`, `lesson-learned`)
   - Document references (tags like `toolset_document`, `repomap`)
   - Architectural decisions (`tags: technical_decisions`)

   **User profile bank (`hermes`) — look for:**
   - User preferences (tone, style, format, verbosity)
   - Environment conventions (tool choices, workflows, project structure)
   - Corrections and lessons learned (tagged `lesson-learned`)
   - Active directives or standing instructions

5. If the bank doesn't exist or is empty, note it and proceed — the repo's physical docs become your primary source.

### Phase 2: Repository Structure

1. **Clone the repo** (if not already present):

   ```bash
   gh repo clone <owner>/<repo> /path/to/workspace/<repo>
   # OR: git clone https://github.com/<owner>/<repo>.git
   ```

2. **Read `REPOMAP.md`** (`docs/REPOMAP.md`). This is the routing matrix that defines:
   - Which files/directories to consult for what purpose
   - What each directory's **nature** is: Active Governance, Domain Axiom, Documentation, Infrastructure, Planning
   - The **mandatory** entries to always read

3. **Read `MASTER-SPEC.md`** (`docs/MASTER-SPEC.md`). This is the architectural specification:
   - §1 Project Identity — what the project is and isn't
   - §2 Architecture — component diagram and data flow
   - §3 Technical Stack — layer-by-layer technology choices with justification
   - §4 Constraints — inviolable boundaries (override all other decisions)
   - §5 Agreed Trade-offs — explicit sacrifices and why
   - §7 Module Specifications — detailed component documentation
   - §8 Operational Rules — where to find agent rules

4. **Read `RULES.md`** (`docs/RULES.md`). These are the operational rules for AI agents:
   - Synergy rules for Hindsight MCP (MEM-01, MEM-02)
   - Synergy rules for Composio MCP
   - Infrastructure provisioning rules (INFRA-01, INFRA-02, INFRA-03)
   - CLI interaction patterns (e.g., `hermes -z` for one-shot)

### Phase 3: Domain Files

1. **Read `README.md`** — high-level overview and startup instructions.

2. **Read any foundational specification files** listed as Domain Axioms in REPOMAP (e.g., `Toolset Junio 2026.md`, `Hermes-integration.md`).

3. **Explore key subdirectories** per REPOMAP routing:

   | Directory | Purpose |
   |-----------|---------|
   | `infrastructure/` | Deployment config (OpenTofu `.tf`, Docker Compose, Caddyfile, deploy.sh, cloud-init) |
   | `.github/workflows/` | CI/CD pipeline definitions |
   | `.agents/` | Kairos governance structure (roles, rules, skills, workflows, templates) |

### Phase 4: State and Progress

1. **Read `docs/TODO.md`** — task tracking with coverage check references. Identifies:
   - Completed tasks (what's been done)
   - In-progress tasks (what's being worked on)
   - Blocked tasks (what's stuck and why)
   - Pending tasks (what's coming next)

2. **Check `docs/VERIFICATION.md`** — verification matrix for what has been validated.

3. **Check `docs/CHANGELOG.md`** — recent changes and their chronology.

4. **Check `docs/TECHNICAL-DEBT.md`** — known technical debt with tracking IDs.

5. **Check `docs/USER-DECISIONS.md`** — explicit user decisions and their rationale.

### Phase 5: Infrastructure Verification

If the project involves deployed infrastructure (like Toolset Personal):

1. **Cross-reference Hindsight bank facts** with physical infrastructure files:
   - `infrastructure/compute.tf` → VM shape, OS, region, boot volume
   - `infrastructure/network.tf` → VCN, subnets, security rules
   - `infrastructure/docker-compose.yml` → running services
   - `infrastructure/Caddyfile` → reverse proxy routing
   - `infrastructure/deploy.sh` → deployment procedure

2. **Check `.github/workflows/deploy.yml`** for CI/CD pipeline structure.

3. **Check `infrastructure/cloud-init.yaml`** for first-boot provisioning.

## Pitfalls

1. **Skipping the user profile bank (`hermes`)** — recalling only the project bank means you miss user-level context: preferences, corrections, meta-rules that apply across all projects. Always recall BOTH banks.

2. **Skipping Hindsight recall** — per Kairos MEM-01, Hindsight MUST be the first step. Reading files first and then recalling duplicates effort and wastes context window.

3. **Reading files out of order** — REPOMAP defines the reading order. Always start with REPOMAP, then MASTER-SPEC, then RULES.

4. **Treating all docs as equal** — `MASTER-SPEC.md` is a Domain Axiom (architectural authority), `TODO.md` is documentation (task tracking). They have different authority levels. REPOMAP clarifies this.

5. **Over-relying on git log** — commit messages only show *what* changed, not *why* or *how the system works*. The documentary axis (docs/) and memory (Hindsight) provide the "why".

6. **Ignoring .agents/** — the `.agents/` directory is the active governance layer with roles, skills, workflows, and templates that define how the agent should operate in this repo. Per Kairos, it's a MUST-READ.

7. **Forgetting .agents/ on new projects** — Para CADA proyecto nuevo, .agents/ debe clonarse desde `kirlts/kairos`. No crearlo manualmente ni copiar de otro repo. Esto asegura reglas, templates y workflows consistentes en todos los proyectos del toolset.

8. **/document en el repo equivocado** — El workflow `/document` debe ejecutarse SIEMPRE en el contexto del repo `kirlts/toolset` (repo de gobierno central), NO en el repo donde se trabajó. Toolset contiene la configuración global, skills, y documentación de infraestructura.

9. **Bank naming** — Los banks de Hindsight se nombran EXACTAMENTE como el repo al que refieren (bank_id="researchit", no "ResearchIt Engine"). El name (nombre amigable) también debe ser el nombre del repo.

10. **Secrets no van en código** — Todos los secrets (API keys, connection IDs) van en Infisical, respaldados por GitHub Secrets. No hardcodear en el código fuente. Ver `kilo-code` skill para el patrón de exportación (`set -a && source .env`).

## References

- `references/kairos-governance-files.md` — condensed reference for files in a Kairos-governed repo
