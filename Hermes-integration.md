# Hermes Integration Plan

> Planning session: 2026-06-23
> Status: **Draft — awaiting explicit approval per section**

---

## 1. Use Cases & Boundaries

### 1.1 Primary Use Cases

I will use Hermes as:

1. **Remote async entry point** — Interact with the Toolset from anywhere (PC, smartphone, abroad) via WhatsApp, Discord, or the Hermes WebUI. Send voice/text describing a task; Hermes executes it and reports back.
2. **Sandboxed code execution & validation** — Delegate work to subagents that clone repos (by URL or by name if Hermes has worked with it before), run tests, and execute code in Docker-isolated sandboxes without polluting the host. If I push to master from Kilo locally but need someone to run tests and deploy from the VPS, I reference the repo to Hermes via WhatsApp and it handles the rest. Hermes can also accept arbitrary .zip URLs, unzip and manage them in a sandbox.
3. **Visual feedback on demand** — Request screenshots of anything: a running UI, terminal output, dashboard state, web pages, any visual state Hermes can access. Deliver them via WhatsApp/Discord/email, post to Reddit, or send as email attachment — whatever channel I choose for that specific task. Hermes uses its native browser/web tools for this, not necessarily Playwright.
4. **Repository manipulation at a distance** — Modify repos using an LLM that follows `.agents/` and `docs/` rules. Hermes clones the repo (by name or URL), works on it, and maintains master context for all repos it has accessed: what they are, what was done, and why.
5. **Proactive status reporting & multi-channel delivery** — Hermes monitors running processes and proactively alerts me via WhatsApp/Discord on completion, errors, or on-demand request. I can choose per-task whether I want a WhatsApp ping, a Discord message, or an email report.

### 1.2 Boundaries (What Hermes is NOT)

- **Not a replacement for Kilo (VS Code extension)** — The VS Code extension stays on my laptop for interactive in-editor work. Kilo Code CLI (`@kilocode/cli`) is installed on the VPS and used by Hermes as a coding subagent via `kilo run --auto`, sharing the same `~/.config/kilo/kilo.jsonc` config (OpenCode Go provider, MCPs, permissions).
- **Not an infrastructure provisioner** — OpenTofu + CI/CD (`deploy.yml`) remains the sole authority for infrastructure mutations (per `[INFRA-01]`). Hermes doesn't modify its own running environment on the fly — changes go through infrastructure-as-code.
- **Not a direct shell to production** — Hermes operates through sandboxed backends (Docker/Daytona/SSH), not by mutating the OCI instance directly.

### 1.3 User Decisions (Answered)

| # | Question | Decision |
|---|---|---|
| Q1 | WhatsApp mode | **Dedicated bot number** (Google Voice or prepaid SIM) |
| Q2 | Discord deployment | **Postponed** — logged as future work when needed |
| Q3 | LLM provider for Hermes | **Same OpenCode Go** subscription as local Kilo (cost consolidation) |

---

## 2. Why Integrate Hermes

### 2.1 Current Gap

The Toolset (Fase 1) is 100% local-workstation-bound:
- No async execution capability when away from the terminal
- No mobile/remote access to orchestration
- All agent deliberation happens synchronously on the local machine
- No proactive alerting — you must be present to see results

### 2.2 Value Proposition

Hermes bridges Fase 1 → Fase 2 with four distinct capabilities:

| Capability | How It Works |
|---|---|
| **Mobility** | Same agent identity reachable from WhatsApp, Discord, WebUI, or CLI — switch mid-workflow without losing context. Context sync requires manual `/document` workflow to update repo/branch/Hindsight bank state, which Hermes immediately picks up. Hermes should also respond to GitHub webhooks (push events) to auto-pull and stay in sync. |
| **Asynchrony** | Delegate long-running tasks (test suites, Playwright screenshots, repo modifications) via any channel; receive results on completion |
| **Sandboxing** | 6 terminal backends (local, Docker, SSH, Daytona, Modal, Singularity) — each task runs isolated from the host and from other tasks |
| **Accumulation** | Persistent memory (markdown files + SQLite session search) + self-improving skills — the agent gets better at your stack over time without manual configuration |

### 2.3 Why Hermes Specifically (vs Alternatives)

- **Kilo Code CLI** (`@kilocode/cli`) is the **only** coding subagent — open source, `kilo run --auto` on the VPS, sharing the same config as local Kilo. Autonomous mode, ACP server, session continuation.
- **Daytona/e2b rejected** for complexity — Hermes wraps them as backend options, not primary orchestration targets. You interact with Hermes; Hermes decides which backend to use.
- **OpenClaw** is the closest competitor but has documented stability regressions (Telegram broken across 2026 releases), skill marketplace security incidents (~20% of ClawHub flagged malicious), and is Node.js-based. Hermes is Python-native, writes skills automatically from experience, and has higher update stability.

---

## 3. CI/CD Integration & Edge Cases

### 3.1 Current CI/CD State

The pipeline (`deploy.yml`) has two jobs on `push: main`:
1. **OpenTofu**: Provisions OCI infrastructure (VCN, instance, security groups), uploads state to `toolset-opentofu-state` bucket
2. **Deploy Services**: Tailscale SSH → deploys Docker Compose services via `deploy.sh`. Current services: PostgreSQL, Infisical, Hindsight, Caddy, Redis
3. **Tailscale Funnel**: Ya activo en OCI. Dos funnels — `:443` para Caddy (proxy multiplex) y `:8443` directo a Infisical UI (`deploy.sh` líneas 281-334). El Caddyfile escucha plano en `:8080`; Tailscale termina HTTPS por encima. No hay configuración de Funnel en Caddyfile — se gestiona en runtime via `tailscale funnel --bg` desde `deploy.sh`.

⚠️ **Disk space alert**: OpenTofu configura `boot_volume_size_in_gbs = 100` pero Oracle Linux 9 solo asigna ~44.5GB a LVM (29.5GB root + 15GB oled). Root estaba al 96%. Fix via `cloud-init.yaml` + `deploy.sh`: growpart → lvextend → xfs_growfs (OL9 usa XFS, no ext4). Después del fix: 83GB root, 35% uso. Verificado.

### 3.2 Hermes Deployment Model

**Revised: Hybrid — Hermes as systemd service (bare metal) + infrastructure in Docker Compose**

Per r/hermesagent VPS Deployment Megathread (June 2026, community-sourced from 200+ comments):
- **Bare metal / root install** is Tier 1 (community favorite)
- **Docker** is Tier 3 (stable production only, after toolset is locked)
- The official Hermes Docker image is "very limited" — no browser, no search, missing tools/skills
- Community consensus: "Hermes needs more than a container to run optimally. It needs an entire tech stack."

**Why hybrid**:
- Infrastructure services (PostgreSQL, Infisical, Hindsight, Caddy) stay in Docker Compose — unchanged pipeline
- Hermes installed directly on the OS via the official one-liner (`curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`) → full filesystem access for browser tools, system deps, CLI tools
- Hermes runs as systemd service (`hermes gateway install --system`) → auto-start on boot, clean restarts, proper logging
- Infrastructure ports (`localhost:8081` Infisical, `localhost:8888/9999` Hindsight, `localhost:8080` Caddy) are accessible to Hermes via `127.0.0.1` — no Docker networking needed
- Hermes WebUI runs on the host (or in a Docker container) at `:8787` → Tailscale Funnel route

**What changes in CI/CD**:
- `deploy.sh` adds: install Hermes via one-liner if missing, `hermes gateway install --system`, configure `~/.hermes/.env` with secrets from Infisical
- Hermes state (`~/.hermes/`) should be snapshotted but not managed by Docker volumes
- Pipeline still idempotent: deploy.sh checks if Hermes is installed, updates config, restarts gateway

### 3.3 Updated Service Architecture

```
┌─────────────────────────────────────────────────┐
│  Tailscale Funnel (3+ puertos, gestionados en   │
│  deploy.sh via `tailscale funnel --bg`)         │
│  :443 → Caddy (:8080)                           │
│  :8443 → Infisical UI (:8081)                   │
│  :8787 → Hermes WebUI (:8787)                   │
├─────────────────────────────────────────────────┤
│  Docker Compose (toolset-net)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ Postgres │←→│ Infisical│  │ Hindsight    │   │
│  │ (Infis)  │  │ (secrets)│  │ (memory MCP) │   │
│  └──────────┘  └──────────┘  └──────────────┘   │
│        ↑              ↑              ↑           │
│        └──────────────┼──────────────┘           │
│                   localhost:8081,8888,9999        │
├─────────────────────────────────────────────────┤
│  Host (bare metal — systemd service)             │
│  ┌─────────────────────────────────────────┐    │
│  │ Hermes Agent (gateway + terminal)       │    │
│  │  ├─ WhatsApp (Baileys bridge)           │    │
│  │  ├─ Docker sandbox backend              │    │
│  │  ├─ MCP client (Composio, Hindsight)    │    │
│  │  └─ OpenCode Go LLM provider            │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │ Hermes WebUI (same host, :8787)          │    │
│  └─────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

### 3.4 Edge Cases & Mitigations

| Edge Case | Impact | Mitigation |
|---|---|---|
| **WhatsApp session persistence** | Baileys QR session stored in `~/.hermes/platforms/whatsapp/session` must survive container restarts | Mount as persistent Docker volume; verified by compose healthcheck |
| **Sandbox port collisions** | Multiple Docker sandboxes competing for the same host port | Hermes' Docker backend uses ONE persistent container per Hermes process (`container_persistent: true`, default). All terminal commands and subagents share it via `docker exec`. No `docker run -p` per command → no port conflicts. If isolated ports are needed (e.g., running a dev server + test server simultaneously), use `daytona` backend which provisions independent cloud workspaces with their own networking |
| **Docker-in-Docker confusion** | User asked: "can I sandbox non-Dockerized code?" and "dockerized Dockerization?" | **Yes — Hermes' built-in `docker` terminal backend wraps ANY code in a container** automatically, regardless of whether it has a Dockerfile. It `pip/apt install`s dependencies on the fly. Port isolation via single persistent container with `docker exec`. Daytona is a Hermes backend option if independent cloud workspaces are needed, but adds latency (~3-6s spawn time vs instant `docker exec`) and requires an external service. Community uses bare Docker for dev, Daytona/Modal only when full network isolation is required. |
| **Secret exposure to LLM** | Hermes' LLM could see Infisical secrets during .env construction | Hermes reads secrets from Infisical via service token (server-side); the LLM only sees the secret names, not values, when constructing .env files. Secret values are injected directly into the sandbox environment via `env_passthrough`, not through the prompt |
| **State corruption on concurrent writes** | Multiple platforms (WhatsApp + Discord + WebUI) hitting same session store | Hermes uses SQLite with FTS5 and atomic writes with contention handling — designed for multi-surface concurrency from day one |
| **Container resource exhaustion** | Multiple subagents + Hermes gateway + WebUI + existing services | Instance has **12 GB RAM** (VM.Standard.A1.Flex, 2 OCPU). Container limits: `container_cpu: 1`, `container_memory: 5120` (default). Subagent sandboxes have PID limits (256). **✅ Disk fixed**: 30GB → 83GB root via growpart + lvextend + xfs_growfs. Log rotation via `logrotate` for `~/.hermes/sessions/`, `~/.hermes/logs/`, and Docker logs needed before deployment |
| **Pipeline rollback without affecting other services** | Hermes crashes or enters bad state post-deploy | Systemd `restart=always` handles crashes. To revert: deploy.sh uninstalls/reinstalls Hermes from fresh. `~/.hermes/` backed up before destructive operations. Docker services (Infisical, Hindsight) are unaffected since Hermes runs on the host, not in a container |

### 3.5 Required Secrets (New)

**Can be added NOW** (before Hermes setup):
| Secret | Purpose | Value |
|---|---|---|
| `HERMES_LLM_PROVIDER` | LLM provider name | `opencodego` (same as local Kilo) |
| `HERMES_LLM_MODEL` | Default model | `deepseek-v4-flash` (único modelo en el stack) |
| `HERMES_LLM_API_KEY` | OpenCode Go API key | `OPENCODE_GO_API_KEY` — already exists in GitHub Secrets! |
| `HERMES_WEBUI_PASSWORD` | WebUI authentication | Generate random password |
| `HERMES_WHATSAPP_MODE` | WhatsApp mode | `bot` |

**Require Hermes initial setup first** (setup wizard + QR pairing):
| Secret | Purpose | Source |
|---|---|---|
| `WHATSAPP_ALLOWED_USERS` | Phone number allowlist | Your phone number (with country code) |
| `WHATSAPP_SESSION_DATA` | Baileys QR session (auto-generated after pairing) | Generated by Hermes on first WhatsApp setup |
| `HERMES_DISCORD_BOT_TOKEN` | Discord bot token | Discord Developer Portal (postponed) |

**API key reuse**: `OPENCODE_GO_API_KEY` is already a GitHub Secret → Infisical. Hermes will read it from there. No duplicate secret needed.

---

## 4. Use Case Deep Dives

### 4.1 Remote Code Execution & Sandbox

**Scenario**: You push code to master from Kilo locally, then leave. Someone needs to run tests and deploy via WhatsApp.

**Flow**:
```
User (WhatsApp): "Corre los tests en /home/kirlts/toolset y despliega si pasan"
        ↓
Hermes gateway (WhatsApp adapter → AIAgent)
        ↓
Hermes terminal backend (docker):
  1. git clone <repo_url> /workspace/toolset
  2. cd /workspace/toolset
  3. pip install -r requirements.txt (or detect package manager)
  4. pytest / npm test (auto-detect test runner)
        ↓
If tests pass → deploy (via CI/CD trigger or docker compose up -d)
If tests fail → send failure report + diff
        ↓
Response delivered to same WhatsApp chat
```

**Sandbox for non-Dockerized code**: Hermes' `docker` backend creates a base container (e.g., `python:3.11-slim`) and installs dependencies at runtime. No Dockerfile required. It detects the project type (Python, Node, Go, etc.) and bootstraps accordingly.

**Port isolation**: The Docker backend uses `docker exec` into a single persistent container — no port mapping per command. If a task requires a running server (e.g., Playwright with a UI), Hermes starts it as a background process (`background=true`) and can take screenshots via the `vision_analyze` or `browser_snapshot` tools. Port conflicts are avoided because all services run inside the same sandboxed container with internal-only networking.

### 4.2 Screenshots on Demand

**Capability**: Hermes has built-in multimodal tools:
- `vision_analyze` — takes screenshots and analyzes them
- `browser_snapshot` — captures browser state
- `browser_vision` — vision-based browser interaction

**Flow for "take a screenshot"**:
```
User (WhatsApp): "Mándame screenshot de la UI que está corriendo en el sandbox"
        ↓
Hermes:
  1. browser_snapshot → captures current browser state
  2. vision_analyze → processes the image
  3. Sends image back via WhatsApp (native image support)
        ↓
Can route through Composio for email, Reddit post, etc.
```

**Multi-channel delivery**:
- **WhatsApp**: Native image delivery (OGG/MP3 for audio, PNG/JPEG for images)
- **Discord**: Native image embedding
- **Email**: Via Composio MCP (`GMAIL_SEND_EMAIL` with attachment)
- **Reddit**: Via Composio MCP (`REDDIT_CREATE_SUBMISSION`)

### 4.3 Repository Master Context

**Approach**: Use Hindsight as Hermes' high-level knowledge base:
- Create a dedicated `hermes` bank for system-level context (identity, capabilities, rules, repo inventory)
- Use `docs/` `.agents/` structure within each repo for project-level rules
- Hermes recalls from the `hermes` bank what repos exist, their purpose, and what operations have been performed

**Bank separation strategy**:
```
┌─────────────────┐
│  Bank: "hermes" │  System-level: who Hermes is, repos it knows,
│                 │  global rules, capability inventory, history
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼──┐  ┌───▼───┐
│"toolset"│ │"repo-X"│  Project-level: repo-specific rules,
│ bank   │  │ bank   │  conventions, task history
└────────┘  └───────┘
```

**Version-controlled memory**: Store ALL Hindsight banks in the `toolset` repo via CI/CD export/import cycle. This achieves complete Hindsight resilience — even if the volume is wiped, the next deploy should restore it. Design goal: auto-update the bank representations in the toolset repo every time a `retain` command is executed by any agent (Hermes or Kilo), via a deterministic GitOps workflow.

### 4.4 Code Execution Subagent Strategy (Verified via r/hermesagent June 2026)

**Reddit consensus** (post by u/jebk, 119 upvotes, 53 comments — "You're probably accidentally tokenmaxxing. Learn to delegate more"):
- Orchestrator should NEVER see implementation details — only specs and summaries
- Rule hard: if task >50 lines code/output → delegate to subagent via `delegate_task()`
- Subagent gets fresh context + isolated terminal (viewable in hermes-webui)
- Orchestrator context: ~1KB spec + 500 bytes summary vs 15-20KB without delegation
- Kanban dispatch for coding tasks — executor profile pinned to cheap model (deepseek flash)
- Delegate-first tool access pattern: disable heavy toolsets on default profile, SOUL.md delegates when needed

**Kilo Code CLI exists — this is the preferred integration path**.

Kilo Code has a standalone CLI (`@kilocode/cli`, installable via `npm install -g`) that supports:
- **Autonomous non-interactive mode**: `kilo run "Implement feature X" --auto` — exits with 0/124/1
- **ACP server**: `kilo acp` — Agent Client Protocol for programmatic control
- **MCP server**: `kilo mcp` — can be used as MCP tool from Hermes
- **Same config**: Uses `~/.config/kilo/kilo.jsonc` — same providers, MCPs, permissions as local Kilo
- **Session continuation**: `kilo --continue` for multi-step workflows
- **Model switching**: `kilo models [provider]` to list available models

**Integration strategy**:

1. **Install Kilo CLI on VPS** during Hermes setup:
   ```bash
   npm install -g @kilocode/cli
   ```
2. **Copy local `kilo.jsonc`** to the VPS config — same OpenCode Go provider, same API key, same MCP config
3. **Hermes invokes Kilo** for heavy coding tasks:
   - Via terminal subagent: `kilo run "Implement feature X in /workspace/repo" --auto`
   - Via ACP protocol: `kilo acp` for deeper integration
4. **Model discovery**: User asks Hermes "qué modelos hay disponibles?" → `kilo models opencodego` → user picks → `kilo run --model <selected>` 

**For moderate tasks** (runs tests, git operations, small edits), use `delegate_task()` with terminal tool — avoids spawning a full Kilo subprocess.

**Hermes as intermediary**:
```
User → WhatsApp/Discord → Hermes (OpenCode Go LLM)
                              ↓
            delegate_task() for small/medium tasks
            kilo run "..." --auto for heavy coding
            terminal for git/scripts/test runners
```

**Subscription reuse**: Kilo CLI reads the same `~/.config/kilo/kilo.jsonc` which references OpenCode Go API key via environment variable → same subscription, same config, same models as local.

### 4.5 Branch Management & PR Automation

**Standard workflow for devs**:
- User: "Crea una feature branch `fix/auth-bug` y arregla el login"
- Hermes:
  1. `git checkout -b hermes-fix/auth-bug`
  2. `kilo run "Fix the auth bug in /workspace/repo" --auto` (Kilo CLI subagent)
  3. Runs tests via terminal
  4. `git add -A && git commit -m "fix: auth bug"` && `git push origin hermes-fix/auth-bug`
  5. `gh pr create --base main --title "Fix auth bug" --body "..."`

**Credential persistence**: `gh` CLI authentication token stored as GitHub Secret `GITHUB_CLI_TOKEN` → injected into sandbox → `gh auth login --with-token` at sandbox init.

**Merge criteria**: Configurable per-repo in `docs/RULES.md`. Hermes checks tests pass, lint clean, and merge rules before creating PR or requesting human review.

### 4.6 Infisical + GitHub Secrets Pipeline

**Architecture**:
```
GitHub Secrets (source of truth)
       ↓ (deploy.yml)
Infisical (operational secrets manager)
       ↓ (service token)
Hermes (reads via MCP or CLI)
       ↓ (env_passthrough)
Sandbox containers (get only what they need)
```

**Principle of least privilege**:
- Hermes constructs `.env` files by calling Infisical with specific secret paths
- Sandbox containers receive only the secrets required for their specific task
- When Hermes adds a new secret to Infisical, a post-action hook adds it to GitHub Secrets for disaster recovery

**CI/CD memory replication**: The deploy pipeline exports ALL Hindsight banks + Hermes `~/.hermes/` directory → pushes to repo as tracked artifacts → on fresh instance, deploy.sh restores all before starting services. Design goal: any `retain` call (from Hermes or Kilo) triggers auto-update of bank representations in the toolset repo, achieving "Ultron-style" full resilience.

### 4.7 Composio MCP Parity

**Requirement**: Hermes must use the same Composio MCP that the local Kilo environment uses.

**Implementation**:
1. Hermes exposes itself as an MCP server (built-in capability), connects to Composio as an MCP client, AND connects to Hindsight as an MCP client
2. Composio MCP server configuration stored in `~/.hermes/config.yaml` under the `mcp` section
3. Hindsight MCP configuration at `https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/mcp/` (same URL used by local Kilo)
4. Tool discovery: Hermes queries Composio's available tools → registers them in its tool registry → available to all Hermes sessions (CLI, WhatsApp, Discord, WebUI)
5. Schema validation: Hermes inspects Composio tool schemas before execution (same discipline as Kilo)

**Tool parity table**:
| Tool | Local Kilo | Hermes (VPS) |
|---|---|---|
| Gmail (send/read) | ✅ Composio MCP | ✅ Composio MCP |
| Slack (send/search) | ✅ Composio MCP | ✅ Composio MCP |
| Reddit (post/search) | ✅ Composio MCP | ✅ Composio MCP |
| GitHub (issues/PRs) | ✅ Composio MCP | ✅ Composio MCP |
| Figma (create/update) | ✅ Composio MCP | ✅ Composio MCP |

---

## 5. Implementation Plan (High-Level)

### Phase 1: Infrastructure Preparation
- [x] Add LVM disk extension to `cloud-init.yaml` + `deploy.sh` (growpart + lvextend + `xfs_growfs`). ✅ Verified: root 30GB→83GB, 96%→35%
- [ ] Add Hermes install + systemd setup to `deploy.sh` (hermes gateway install --system)
- [ ] Add Hermes secrets schema to `deploy.sh` (.env template for ~/.hermes/.env)
- [ ] Add Hermes secrets to GitHub Secrets workflow (`deploy.yml` env block)
- [ ] Configure Tailscale Funnel route for Hermes WebUI (:8787)
- [ ] Install Kilo CLI (`npm install -g @kilocode/cli`) in deploy.sh
- [ ] Sync `~/.config/kilo/kilo.jsonc` (same config as local — OpenCode Go, Composio MCP, Hindsight MCP)

### Phase 2: Messaging & Gateway
- [ ] Set up WhatsApp integration (Baileys bridge, QR pairing, allowlist)
- [ ] Set up Discord bot (Developer Portal token, invite link, DM routing)
- [ ] Configure user allowlists per platform in `~/.hermes/config.yaml`
- [ ] Test multi-surface session continuity (same conversation from WhatsApp → WebUI → Discord)

### Phase 3: Integration Wiring
- [ ] Connect Hermes to Infisical via `HERMES_INFISICAL_SERVICE_TOKEN`
- [ ] Configure Hindsight as external memory provider in Hermes (`hermes memory setup`)
- [ ] Create `hermes` Hindsight bank with system-level context
- [ ] Set up Composio MCP connection in Hermes config
- [ ] Configure Docker terminal backend with resource limits

### Phase 4: Kilo CLI + Subagent Integration
- [ ] Verify Kilo CLI installed on VPS (`kilo --version`)
- [ ] Test autonomous mode: `kilo run "Run tests" --auto`
- [ ] Create Hermes skill/script that delegates coding tasks to `kilo run --auto`
- [ ] Implement model discovery flow: Hermes calls `kilo models opencodego` → user selects via WhatsApp
- [ ] Implement session continuation pattern for multi-turn workflows

### Phase 5: End-to-End Validation
- [ ] Test flow: WhatsApp message → clone repo → run tests → deploy → report back
- [ ] Test screenshot flow: request → capture → deliver via WhatsApp/email/Reddit
- [ ] Test repo modification: WhatsApp → create branch → Kilo subagent → PR creation
- [ ] Test secret injection: sandbox gets correct .env without LLM seeing values
- [ ] Test error scenarios: sandbox failure, API timeout, WhatsApp session expiry
- [ ] Verify WebUI accessible via Tailscale Funnel from smartphone

### Phase 6: Documentation & Governance
- [ ] Update `docs/MASTER-SPEC.md` with Hermes integration details
- [ ] Update `docs/REPOMAP.md` routing matrix
- [ ] Update `CHANGELOG.md`
- [ ] Run documentary sync workflow

---

## 6. Stack Synergy

### 6.1 Existing Synergies

| Component | Synergy with Hermes |
|---|---|
| **Tailscale** | Private network + Funnel for WebUI public access — no port exposure needed. SSH tunnel alternative: `ssh -N -L 8787:127.0.0.1:8787` |
| **Infisical** | Centralized secrets injection. Hermes reads via service token, constructs .env for sandboxes, syncs new secrets back to GitHub |
| **Hindsight** | External memory provider plugin. Hermes connects to `hindsight:8888` for recall/retain. Separate `hermes` bank for system-level context |
| **Caddy** | Reverse proxy for Hermes WebUI at `/hermes` path. Health endpoint for pipeline verification |
| **PostgreSQL** | Infisical's database — no direct dependency from Hermes |
| **Redis** | Infisical's cache — no direct dependency from Hermes |
| **GitHub Actions** | CI/CD pipeline deploys Hermes. GitHub Secrets → Infisical sync on every deploy |

### 6.2 New Dependencies

| Component | Purpose | Source |
|---|---|---|
| **Hermes Agent** | Core agent engine — installed via one-liner, runs as systemd service | Nous Research |
| **Hermes WebUI** | Browser interface (`ghcr.io/nesquena/hermes-webui` or host-installed) | Community project |
| **Baileys** | WhatsApp Web bridge (bundled with Hermes) | Community |
| **Composio MCP** | External service integrations | Existing in stack |
| **Kilo Code CLI** (`@kilocode/cli`) | Coding subagent — autonomous mode (`kilo run --auto`), shared config with local | Kilo Org |
| **Daytona (optional)** | Cloud sandbox for true container-in-container isolation | Optional, not required |

### 6.3 Gaps Resolved During Review

| Gap | Resolution |
|---|---|
| **LLM provider** | **OpenCode Go** (same as local Kilo) — `https://opencode.ai/zen/go/v1` with existing API key |
| **OCI instance sizing** | **12 GB RAM** (VM.Standard.A1.Flex, 2 OCPU) — verified from OpenTofu. Disk: 100GB boot volume but Oracle Linux LVM allocates only ~44.5GB. Fix in cloud-init.yaml (growpart + lvextend + xfs_growfs) and deploy.sh (idempotent check for existing instances). Result: 83GB root, 35% usage |
| **Tailscale Funnel status** | **✅ Already active** — `:443` → Caddy (`localhost:8080`), `:8443` → Infisical (`localhost:8081`). Verified via `tailscale funnel status` |
| **WhatsApp phone number** | **Dedicated bot number** (Google Voice or prepaid SIM) |
| **Discord server/bot** | **Postponed** — logged as future work |

---

## Approval Checklist

| Section | Status | Notes |
|---|---|---|
| 1. Use Cases & Boundaries | ✅ APPROVED | Corrections applied per review (items 1-5, 7, 8, 9) |
| 1.1 Primary Use Cases | ✅ CORRECTED | No hardcoded paths, Kilo CLI found, general chatbot removed |
| 1.2 Boundaries | ✅ CORRECTED | Kilo as VS Code extension clarified, general chatbot allowed |
| 1.3 Open Questions | ✅ RESOLVED | Q1: bot number, Q2: postponed, Q3: OpenCode Go |
| 2. Why Integrate Hermes | ✅ CORRECTED | Context sync via /document + GitHub webhooks |
| 2.3 Why Hermes Specifically | ✅ DRAFTED | Including competitors |
| 3. CI/CD Integration | ✅ CORRECTED | Hybrid model: systemd service + Docker Compose infra |
| 3.3 Architecture diagram | ✅ CORRECTED | Host-level Hermes + Docker Compose services |
| 3.4 Edge cases | ✅ CORRECTED | Daytona vs Docker latency, RAM (12GB), disk fix (cloud-init + deploy.sh) |
| 3.5 Required secrets | ✅ CORRECTED | Classified: can-add-now vs after-setup |
| 4. Use Case Deep Dives | ✅ DRAFTED | All scenarios addressed |
| 4.1 Remote code + sandbox | ✅ CORRECTED | URL, name, .zip support; non-Playwright screenshots |
| 4.2 Screenshots | ✅ CORRECTED | Native Hermes tools, examples not prescriptive |
| 4.3 Repo master context | ✅ CORRECTED | All banks in repo, auto-update on retain |
| 4.4 Kilo integration | ✅ CORRECTED | `kilo run --auto` (CLI exists!), ACP server, same config |
| 4.5 Branch/PR management | ✅ DRAFTED | gh CLI + credential persistence |
| 4.6 Infisical pipeline | ✅ CORRECTED | Hermes + Hindsight MCP both connected |
| 4.7 Composio parity | ✅ CORRECTED | Hindsight MCP added alongside Composio |
| 5. Implementation Plan | ✅ CORRECTED | Kilo CLI install, LVM fix, no Docker Compose for Hermes |
| 6. Stack Synergy | ✅ DRAFTED | Existing + new dependencies |
| 6.3 Gaps resolved | ✅ RESOLVED | 5 items all addressed |
