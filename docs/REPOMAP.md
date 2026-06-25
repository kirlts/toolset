# REPOMAP: Toolset Personal

> Generated: 2026-06-25 (Kairós v4)  
> Purpose: Routing matrix. Defines when the AI is authorized to read each directory or file.

## Authoring Constraints (Read Before Populating)

- **Scope:** Map the host project only. Kairós release metadata files (`README-KAIROS.md`, `kairos-version.txt`) are distribution artifacts and MUST NOT appear as Domain Axioms or individual rows. If listed at all, compress them into a single noise cluster row. The `.agents/` directory is the **active governance layer** and is handled by a hardcoded mandatory row below; it MUST NOT be classified as a noise cluster or invisible infrastructure. The documentary axis files in `docs/` are project documentation, not governance. `docs/MASTER-SPEC.md` receives an individual row as a Domain Axiom; the remaining axis files defined in `04-documentation.md` are grouped into a single row.
- **Abstraction level:** Source code files are always mapped at the directory level, never as individual rows. Only documentation and specification files qualify for individual rows as Domain Axioms, per the three-signal detection algorithm in the `/repomap` workflow.
- **Anti-recency bias:** The physical timestamp of a file is not a factor. Do not elevate recently modified files. Prominence is determined by architectural role defined in `MASTER-SPEC`, not by modification date.
- **MECE:** Every row must be Mutually Exclusive (no overlapping access conditions) and Collectively Exhaustive (every directory or logical cluster must be represented).
- **Language:** This document is written in English regardless of the host project's language.

## Routing Matrix

| Directory / File | Nature | When to Consult |
|---|---|---|
| `.agents/` | **[Active Governance]** Rules, skills, workflows, and templates that define agent behavior. | **MANDATORY.** Consult `01-behavior.md` at session start; dynamically load other files per `[RULE: DYNAMIC CONTEXT LOAD]` and `[RULE: DYNAMIC SKILL ACTIVATION]` triggers. |
| `docs/MASTER-SPEC.md` | **[Domain Axiom]** Master architectural specification of the workspace, domains, stack, and rules. | Consult when verifying technical stack, boundaries, or when modifying architectural components. |
| `docs/` (excluding MASTER-SPEC.md) | **[Documentation]** Project progress tracking and local operational rules (TODO, VERIFICATION, CHANGELOG, USER-DECISIONS, MEMORY, RULES). | Consult to verify task completion, review strategic decisions, or update version histories. |
| `infrastructure/` | **[Infrastructure]** Deployment configuration: OpenTofu (`.tf`), Docker Compose, Caddyfile, deploy script, cloud-init. | Consult when modifying infrastructure provisioning, CI/CD pipeline, or service deployment configuration. |
| `Toolset Junio 2026.md` | **[Domain Axiom]** Base project specification and infrastructure definition from June 2026. | Consult to understand the foundational requirements, architecture, and cloud vs local domain split of the toolset. |
| `Hermes-integration.md` | **[Planning]** Hermes Agent integration plan with verified use cases, architecture diagrams, edge case mitigations, and implementation phases. | Consult when implementing Hermes deployment, WhatsApp/Discord integration, sandbox configuration, or any Hermes-related feature. |
| `README.md` | **[Documentation]** High-level overview and startup instructions for the repository. | Consult at session startup or when providing a quick overview of the repository to new clients. |
| `.kilo/` | **[Invisible Infrastructure]** Local editor configurations and dependency folders. | Consult only when investigating editor integration issues or editor-specific package dependencies. |
