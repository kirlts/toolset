# REPOMAP: Toolset Personal

> Generated: 2026-06-29 (Kairós v4.0.0)  
> Purpose: Routing matrix. Defines when the AI is authorized to read each directory or file.

## Authoring Constraints (Read Before Populating)

- **Scope:** The agent maps the host project only. Kairós release metadata files (`README-KAIROS.md`, `kairos-version.txt`) are distribution artifacts and do not appear as Domain Axioms or individual rows. If listed at all, they are compressed into a single noise cluster row. The `.agents/` directory is the **active governance layer** and is handled by a hardcoded mandatory row below — it is not classified as a noise cluster or invisible infrastructure. The documentary axis files in `docs/` are project documentation, not governance. `docs/MASTER-SPEC.md` receives an individual row as a Domain Axiom; the remaining axis files defined in `04-documentation.md` are grouped into a single row.
- **Abstraction level:** Source code files are always mapped at the directory level, rather than as individual rows. Only documentation and specification files qualify for individual rows as Domain Axioms, per the three-signal detection algorithm in the `/repomap` workflow.
- **Anti-recency bias:** The physical timestamp of a file is not a factor. Recently modified files are not elevated. Prominence is determined by the architectural role defined in `MASTER-SPEC`, not by modification date.
- **MECE:** Every row is Mutually Exclusive (no overlapping access conditions) and Collectively Exhaustive (every directory or logical cluster is represented).
- **Language:** This document is written in English regardless of the host project's language.

## Routing Matrix

| Directory / File | Nature | When to Consult |
|---|---|---|
| `.agents/` | **[Active Governance]** Rules, skills, workflows, and templates that define agent behavior. | **MANDATORY.** The agent consults `01-behavior.md` at session start; the agent dynamically loads other files per `[RULE: DYNAMIC CONTEXT LOAD]` and `[RULE: DYNAMIC SKILL ACTIVATION]` triggers. |
| `docs/MASTER-SPEC.md` | **[Domain Axiom]** Foundational architectural and operational specification of the project (identity, stack, constraints, trade-offs, modules, rules). | Consult before any architectural decision, infrastructure mutation, or cross-module change. Authoritative source for project boundaries and inviolable constraints (§4). |
| `docs/` (excluding MASTER-SPEC.md) | **[Documentation]** Project documentary axis: RULES.md, VERIFICATION.md, TODO.md, MEMORY.md, USER-DECISIONS.md, CHANGELOG.md, TECHNICAL-DEBT.md, REPOMAP.md, and doc-gen/. | Consult per `[RULE: TASK INITIATION & AUTHORIZATION]` conditions — task completion verification, strategic decision review, version history updates, or rule lookup. |
| `infrastructure/` | **[Infrastructure Module]** OpenTofu provisioning (`.tf`), Docker Compose services, deploy.sh CI/CD script, Hermes agent config (SOUL.md, config.yaml, banks/, memory/, skills/, scripts/, webui/), Caddyfile, cloud-init, and external Hermes skills. | Consult when modifying infrastructure provisioning, CI/CD pipeline, service deployment, Hermes agent configuration, or when verifying deployed system state. Maps to MASTER-SPEC §7.1. |
| `.github/` | **[CI/CD Module]** GitHub Actions workflow definitions (deploy.yml). | Consult when modifying the CI/CD pipeline, troubleshooting deployment failures, or reviewing workflow structure. |
| `.kilo/` | **[Editor Configuration]** Kilo CLI config (agent-manager.json, package.json, worktrees/). | Consult when troubleshooting Kilo CLI setup, agent-manager state, worktree management, or editor integration issues. |
| `.ssh/` | **[Infrastructure Access]** SSH key pair for OCI server (toolset-oci, toolset-oci.pub). | Consult during SSH connectivity troubleshooting or when verifying key-based access to the OCI instance. |
| `scripts/` | **[Utility Module]** Standalone utility scripts (validate-kilo-config.py). | Consult when validating Kilo configuration or running standalone repo utility tasks. |
| `Root Config Files` | **[Configuration]** `.gitignore` and `.env.example`. | Consult `.gitignore` to verify file tracking policy; consult `.env.example` as schema reference for environment variables required by the system. |
| `Project Documentation` | **[Documentation]** `README.md` (high-level project overview) and `AGENTS.md` (Hermes agent operational context). | Consult README.md at session start for project orientation; consult AGENTS.md when understanding Hermes agent capabilities, architecture, memory banks, and autonomy protocol. |
| `Kairós Metadata` | **[Distribution Artifact]** `README-KAIROS.md` (framework quick reference) and `kairos-version.txt` (version manifest). | Consult only when verifying Kairós framework version or reviewing governance command reference. |
| `Planning Documents` | **[Planning]** `Hermes-integration.md`, `Toolset Junio 2026.md`, `remediation-plan.md`, `2026-06-25-fallo-sistemico.md`. | Consult when reviewing Hermes deployment plans, foundational project specifications, remediation strategies, or incident diagnostic reports. These are advisory, not normative. |
| `Security Keys` | **[Infrastructure Artifacts]** SSH and GitHub Actions key material (`*.pem` files). | Consult only during key rotation, infrastructure bootstrap, or CI/CD authentication troubleshooting. Gitignored. |
