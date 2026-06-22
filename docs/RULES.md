# RULES

> Operational rules for artificial intelligence agents working in this repository.
> Referenced in MASTER-SPEC §8.

---

## Scope

These rules apply to all operations performed by the artificial intelligence assistant within the current repository, including code modification, testing, infrastructure provisioning, and governance documentation synchronization.

---

## Rules

### Synergy and Use of Hindsight MCP (Centralized Memory)

- **Dynamic Routing by Project:** The agent (regardless of harness or IDE, e.g., Kilo Code, Antigravity, Codex, Claude Code, or this assistant) interacts exclusively with the Hindsight bank corresponding to the active repository:
  - The agent determines the bank name by extracting the name of the current project's root directory.
  - The agent searches the environment's MCP server configuration for the server with the exact identifier `hindsight-<project-name>`.
  - If the corresponding server exists, it is used for all recall and retain operations.
  - If a server configured with the active project's name does not exist, the agent aborts the memory operation immediately and alerts the user to add the configuration to their harness's global MCP configuration.
- **[MEM-01] Context Initialization Architecture:** The Kairos infrastructure delegates all historical context, architectural decisions, and repository knowledge to the Hindsight vector memory. The standard initialization flow dictates that the recall tool, provided by the Hindsight MCP server, functions as the primary abstraction layer to access this state. The agent invokes the recall tool using specific keywords related to the active task immediately upon receiving user input (e.g., questions about the repo, exploring files, new tasks). This MUST happen at the very beginning of the session, before reading physical files or saturating the context window. The physical documentary axis in docs/ supplements this knowledge, but Hindsight MUST be prioritized to optimize context window usage. This process establishes the baseline operational state.
- **[MEM-02] Structural Synchronization Conditions:** The Kairos system maintains inter-agent state coherence and tracks progress exclusively through the retain tool, provided by the Hindsight MCP server. The operating model standardizes the execution of the retain tool as the definitive consolidation step for the following system events:
  - **Governance Workflow Closure:** The execution sequence of the /document, /repomap, and /derive workflows structurally concludes with a call to the retain tool.
  - **Knowledge and State Evolution:** Any meaningful change in the repository state, task progress, AI learnings, architectural changes, or human decisions strictly requires the consolidation of the new state via the retain tool.
- **Inference Consistency:** To avoid context cache destruction (cache miss), the agent queries Hindsight at the beginning of the session to verify the guidelines on the selected inference model and avoids alternating models unnecessarily.

### Synergy and Use of Composio MCP (Integrations Gateway)

- **Single Gateway:** Composio acts as the exclusive channel to authenticate and interact with external APIs and third-party tools. Writing authentication scripts or attempting to implement manual flows for tools supported and actively exposed by Composio is restricted.
- **Schema Validation:** The agent inspects the input schema of each Composio tool prior to execution to guarantee that the arguments strictly comply with the types and mandatory fields defined in the server.
