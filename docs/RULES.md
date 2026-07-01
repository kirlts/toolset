# RULES

> Operational rules for artificial intelligence agents working in this repository.
> Referenced in MASTER-SPEC §8.
> Infrastructure files tracked in `infrastructure/hermes/INFRASTRUCTURE-MANIFEST.md`.

---

## Scope

These rules apply to all operations performed by the artificial intelligence assistant within the current repository, including code modification, testing, infrastructure provisioning, and governance documentation synchronization.

---

## Rules

### Synergy and Use of Hindsight MCP (Centralized Memory)

- **Dynamic Routing by Project (Hermes):** The agent (this assistant) uses a single Hindsight MCP server (`hindsight-selfhosted`) that hosts ALL banks. Bank selection is done via the `bank_id` parameter in recall/retain/reflect calls:
  - The agent determines the active repository from the working directory, user mention, or context.
  - The agent uses the repo name as the `bank_id` for all memory operations.
  - The bank naming convention is `kebab-case` of the repo name (e.g., `cl-concerts-db`, `evidencia-zero`).
  - If a bank for the active repo does not exist, the agent creates it via `create_bank(bank_id="<repo-name>")`.
  - All skills that work with code MUST start with `recall(bank=<repo>)` and end with `retain(bank=<repo>)`.
- **[MEM-01] Context Initialization Architecture:** The Kairos infrastructure delegates all historical context, architectural decisions, and repository knowledge to the Hindsight vector memory. The standard initialization flow dictates that the recall tool, provided by the Hindsight MCP server, functions as the primary abstraction layer to access this state. The agent invokes the recall tool using specific keywords related to the active task immediately upon receiving user input (e.g., questions about the repo, exploring files, new tasks). This MUST happen at the very beginning of the session, before reading physical files or saturating the context window. The physical documentary axis in docs/ supplements this knowledge, but Hindsight MUST be prioritized to optimize context window usage. This process establishes the baseline operational state.
- **[MEM-02] Structural Synchronization Conditions:** The Kairos system maintains inter-agent state coherence and tracks progress exclusively through the retain tool, provided by the Hindsight MCP server. The operating model standardizes the execution of the retain tool as the definitive consolidation step for the following system events:
  - **Governance Workflow Closure:** The execution sequence of the /document, /repomap, and /derive workflows structurally concludes with a call to the retain tool.
  - **Knowledge and State Evolution:** Any meaningful change in the repository state, task progress, AI learnings, architectural changes, or human decisions strictly requires the consolidation of the new state via the retain tool.
- **Inference Consistency:** To avoid context cache destruction (cache miss), the agent queries Hindsight at the beginning of the session to verify the guidelines on the selected inference model and avoids alternating models unnecessarily.

### Synergy and Use of Composio MCP (Integrations Gateway)

- **Single Gateway:** Composio acts as the exclusive channel to authenticate and interact with external APIs and third-party tools. Writing authentication scripts or attempting to implement manual flows for tools supported and actively exposed by Composio is restricted.
- **Schema Validation:** The agent inspects the input schema of each Composio tool prior to execution to guarantee that the arguments strictly comply with the types and mandatory fields defined in the server.

---

### Infrastructure Provisioning: CI/CD Only

- **[INFRA-01] No local `tofu apply` or `tofu destroy`:** The agent MUST NOT execute OpenTofu plan/apply/destroy/taint locally under any circumstance. All infrastructure mutations flow exclusively through the GitHub Actions CI/CD pipeline defined in `.github/workflows/deploy.yml`.
- **[INFRA-02] Remote state is authoritative:** The OpenTofu state file stored in OCI Object Storage (`toolset-opentofu-state` bucket) is the single source of truth. The local state file is ephemeral and may be stale. The agent may use `tofu plan` locally for diagnostics only, provided it reads from remote state (the pipeline already syncs it).
- **[INFRA-03] Service deployment via CI/CD:** The `deploy-services` job handles all Docker Compose changes. The agent may run `./infrastructure/deploy.sh` locally for verification purposes, but production deploys go through CI/CD.
- **[INFRA-04] Mandatory MCP service restart after pipeline modifications:** After any change to SOUL.md, config.yaml, external skills, or .env, the hermes-gateway systemd service is restarted via `systemctl kill -s KILL` + `systemctl start`. This ensures the new configuration is picked up without requiring a full node restart.
- **Rationale:** Session 2026-06-22 demonstrated that local `tofu taint` + `tofu apply` caused SSH lockout, boot volume quota exhaustion, and ~2 hours of unrecoverable downtime. Observability and reproducibility require all infrastructure mutations to be traceable through GitHub Actions logs.

### Infrastructure Manifest & Versioning

- **[MANIFEST-01] The `infrastructure/hermes/INFRASTRUCTURE-MANIFEST.md` file is the single source of truth for all Hermes configuration files.** Every operational .md, .yaml, .sh, and .json file that affects Hermes behavior MUST be listed there. Before modifying any configuration file, read the manifest to understand its sync mechanism and dependencies.
- **[MANIFEST-02]** After ANY change to a Hermes configuration file, the manifest's `Current Session Changes` section MUST be updated with the file path, nature of the change, and date. This creates an auditable trail of what changed and when.
- **[MANIFEST-03] No configuration change lives only on the VPS.** Every file that affects Hermes behavior must be versioned in the repo and deployed via CI/CD (`deploy.sh` or `external_skills_dirs`). The manifest documents the sync mechanism for each file.
- **[MANIFEST-04]** The manifest is checked during `/document` workflow. If the manifest's listed files don't match the actual repo state, the mismatch is flagged as a documentary debt item.

### WhatsApp Multi-Group Routing

- **[ROUTE-01] Deterministic routing via bridge injection:** `patch-bridge.sh` modifies bridge.js to inject a `=== PROFILE ACTIVATION: <name> ===` block (containing the full profile SOUL.md) into every WhatsApp group message that has a configured profile. The bridge reads `~/.hermes/profiles/<name>/SOUL.md` on each message — no caching. The LLM adopts this as its identity via SOUL.md RULE 0. No LLM judgment in routing — the bridge resolves the profile in code.
- **[ROUTE-02] Cross-profile delegation:** When a task falls outside the active profile's scope, it MUST delegate via `kanban_create(assignee="<target-profile>", metadata={originating_group: "<jid>"})`. The executing profile responds in its own group and sends a short notification to the originating group.
- **[ROUTE-03] Scope isolation via identity injection:** `scope:` field in `whatsapp-groups.yaml` (injected into `[ROUTING]`) defines the profile's operational boundary. The LLM operates directly as the named profile — no dual orchestrator/worker identity.
- **[ROUTE-04] Description as context:** The WhatsApp group description (from `channel_aliases.json`) is loaded as operational context at the start of every session. The user can edit the WhatsApp group description at any time; the change is reflected within 10 minutes via the populate-channel-aliases cron job.
- **[ROUTE-05] Only the default profile (master orchestrator) creates global skills.** Worker profiles create skills scoped to their own profile only. This maintains pseudo-sandbox isolation between groups.

### /onboarding Command

- **[ONBOARD-01]** The `/onboarding` command in a WhatsApp group configures that group via a 3-phase MECE process (Identity, Capabilities, Operations). It creates a Hindsight bank, generates a profile SOUL.md from `.agents/templates/profile-soul.md`, and writes the mapping to `whatsapp-groups.yaml`.
- **[ONBOARD-02]** If `/onboarding` is invoked in a DM, it modifies the master orchestrator's `SOUL.md` directly. The user must explicitly confirm before any change is written. A backup is created at `~/.hermes/SOUL.md.bak.<timestamp>`.
- **[ONBOARD-03]** Banks are created programmatically via Hindsight MCP `create_bank()`. On reconfiguration, existing banks are preserved (context is never discarded).

### CLI Interaction with Hermes Agent

When an AI agent (this assistant) needs to interact with Hermes Agent programmatically from the VPS shell (e.g., to test capabilities, send queries, verify tool access), the correct invocation is:

```
ssh opc@toolset-oci-1-1 'export PATH=/usr/local/bin:/home/opc/.local/bin:$PATH && hermes -z "PROMPT"'
```

**Rules:**
- `-z` (one-shot mode): outputs ONLY the plain-text response. No TUI output, no escape sequences. Works when stdout is a pipe or non-TTY.
- Do NOT use `hermes chat` (interactive TUI), `hermes chat --cli`, or pipe input to stdin — these produce ANSI-escaped TUI output that corrupts when piped through SSH commands.
- Do NOT pipe queries via `echo "..." | hermes chat` — the TUI output will be unparseable.
- The `-z` flag is documented in Hermes agent v0.17.0 as `hermes -z <prompt>` one-shot mode.
- If `-z` outputs nothing, the model provider may be unconfigured or the sandbox container may need to be created (first terminal command triggers creation; subsequent commands use the persistent container).
- For verifying gh/git access from within the Hermes sandbox: `hermes -z "Usa gh para listar mis repos"` or `hermes -z "Clona github.com/kirlts/toolset y dime que contiene"`.

### Secrets Management (Infisical)

- **[SEC-01] Infisical is the SOLE source of truth for all secrets at runtime.** API keys, tokens, credentials, and any env var are stored in Infisical and injected via deploy.sh. No `.env` file persists on the VPS.
- **[SEC-02] No agent (Hermes or Kilo CLI) shall hardcode secrets** in code, scripts, configuration files, or documentation. Every credential must be fetched at runtime via `infisical secrets get <NAME>` or the Infisical API (`http://localhost:8080`).
- **[SEC-03] The deploy pipeline must verify** that Infisical exposes secrets correctly after each deploy. If the Infisical API does not return expected secrets, the deploy MUST fail.
- **[SEC-04] Agents that need to create or rotate secrets** must use `infisical secrets set <NAME> <VALUE>`. Manual `.env` editing is forbidden.
