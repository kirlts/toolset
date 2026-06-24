# RULES

> Operational rules for artificial intelligence agents working in this repository.
> Referenced in MASTER-SPEC §8.

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
- **Rationale:** Session 2026-06-22 demonstrated that local `tofu taint` + `tofu apply` caused SSH lockout, boot volume quota exhaustion, and ~2 hours of unrecoverable downtime. Observability and reproducibility require all infrastructure mutations to be traceable through GitHub Actions logs.

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
