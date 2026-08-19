---
description: /mcp - Onboards and manages the MCP (Model Context Protocol) configurations for the current repository. Standardizes memory routing and tool access.
---

# Kairós MCP Management

## Step 1: Governance Detection

The AI agent verifies the existence of the `docs/RULES.md` file.

- **If `docs/RULES.md` does not exist:** The agent aborts the workflow, notifies the user, and suggests executing `/document` first to initialize the repository's governance structure.
- **If `docs/RULES.md` exists:** The agent proceeds to Phase A.

## Phase A: Rule Injection

The AI agent checks if `docs/RULES.md` contains the specific text defined in `.agents/templates/mcp.md`.

- **If the rules are absent:** The agent injects the contents of `.agents/templates/mcp.md` into `docs/RULES.md`. It is placed at the beginning of the rules section, or immediately after any high-priority rules.
- **If the rules are already present:** The agent acknowledges the correct governance state and proceeds seamlessly to Phase B.

## Phase B: Configuration Management

The agent actively manages the MCP configurations for the project's memory.

1. **Discovery:** The agent identifies the active harness and locates its corresponding global MCP configuration file (e.g., `~/.gemini/config/mcp_config.json`, `~/.config/kilo/kilo.jsonc`, `~/.gemini/antigravity/mcp_config.json`).

## Phase C: Organic Interaction

- If the condition is met, the agent initiates an interactive session, asking the user if they wish to add, remove, or modify any other required MCP servers (like Composio). If the user provides instructions, the agent edits the global configuration files accordingly.
- If the condition is not met (changes were made in A or B), this phase is skipped entirely.

## Conclusion

