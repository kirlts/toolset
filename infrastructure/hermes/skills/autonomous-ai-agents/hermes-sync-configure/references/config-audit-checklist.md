# CI/CD Config Audit Checklist

> Supporting reference for `hermes-sync-configure` skill.
> Generated from the 2026-06-25 pipeline audit session. Updated after PR #2 fixes.

## Inventory Template

For each service in the toolset, fill:

```
Service:          [Hermes | Kilo | ResearchIt | WebUI | ...]
Config path:      [/home/opc/.config/kilo/kilo.jsonc | ~/.hermes/config.yaml | ...]
Repo path:        [infrastructure/kilo.jsonc | infrastructure/hermes/config.yaml | ...]
In deploy.sh?:    [yes | no] — line number: ___
In sync script?:  [yes | no]
Has secrets?:     [yes | no] — if yes, how resolved: [deploy.sh env var | {env:} ref | manual]
```

## Hermes Config Audit

| Item | Path | In repo | Deployed | Auto-synced |
|---|---|---|---|---|
| SOUL.md | `~/.hermes/SOUL.md` | ✅ `infrastructure/hermes/SOUL.md` | ✅ deploy.sh | ✅ daily |
| config.yaml | `~/.hermes/config.yaml` | ✅ `infrastructure/hermes/config.yaml` | ✅ deploy.sh | ✅ daily (secrets redacted before commit) |
| Memory | `~/.hermes/memories/` | ✅ `infrastructure/hermes/memory/` | ✅ deploy.sh | ✅ daily |
| Skills | `~/.hermes/skills/` | ✅ `infrastructure/hermes/skills/` | ✅ deploy.sh | ✅ daily |
| Scripts | `~/.hermes/scripts/` | ✅ `infrastructure/hermes/scripts/` | ✅ deploy.sh | ✅ daily |
| Hooks | `~/.hermes/hooks/` | ✅ `infrastructure/hermes/hooks/` | ❌ not in deploy | ✅ daily |
| WebUI settings | `~/.hermes/webui/settings.json` | ✅ `infrastructure/hermes/webui/` | ✅ deploy.sh | ✅ daily |
| Banks (Hindsight) | Hindsight MCP | ✅ `infrastructure/hermes/banks/` | N/A | ✅ daily (agent-driven) |

## Kilo Config Audit

| Item | Path | In repo | Deployed | Auto-synced |
|---|---|---|---|---|
| kilo.jsonc | `/home/opc/.config/kilo/kilo.jsonc` | ✅ `infrastructure/kilo.jsonc` | ✅ deploy.sh | ✅ daily (added in PR #2) |
| Kilo CLI | global npm | ❌ version not pinned | ✅ npm install -g | ❌ always latest |

## Pipeline Components

| Component | File | Validated? |
|---|---|---|
| OpenTofu infra | `.github/workflows/deploy.yml` job `opentofu` | ✅ OCI API key, plan, apply |
| Deploy services | `.github/workflows/deploy.yml` job `deploy-services` | ✅ bash syntax |
| deploy.sh | `infrastructure/deploy.sh` | ✅ bash syntax |
| config.yaml | `validate-configs` job (PR #2) | ✅ Python YAML parser |
| kilo.jsonc | `validate-configs` job (PR #2) | ✅ Python JSONC parser |
| Kilo env refs | `validate-kilo-config.py` script (PR #2) | ✅ Coherence check |
| Hermes sandbox Dockerfile | `infrastructure/hermes-sandbox.Dockerfile` | ✅ Build in CI/CD (PR #2) |

## Common Drift Patterns

### 1. command_allowlist drift — ✅ Fixed
Local config had entries added interactively (`execute_code`, `docker restart`, `hermes update`, etc.). Repo config had a different set. 
**Fix applied**: config.yaml sincronizado local → repo en PR #2. Ahora ambas listas son idénticas.

### 2. Secret in config.yaml — ✅ Fixed
The deploy.sh Python block reads `COMPOSIO_MCP_KEY` from env and writes it as plaintext into `mcp_servers.composio.headers.x-consumer-api-key`. The daily sync then copies config.yaml back to the repo — key was landing in git history.
**Fix applied**: sync-hermes-to-repo.sh now runs a `sed` step that replaces the Composio key value with `PLACEHOLDER_REPLACED_BY_DEPLOY` before committing. deploy.sh restores the real key from env on next deploy.

### 3. Env var reference truncated in terminal output — ℹ️ By design
Hermes secret redactor masks API-key-looking strings in tool output. When reading kilo.jsonc or config.yaml via `cat`/`grep`, `OPENCODE_GO_API_KEY` appears as `O...KEY`. The actual file content is correct.

**Verify with**:
```bash
xxd /home/opc/.config/kilo/kilo.jsonc | grep -A2 "apiKey"
python3 -c "import json; print(json.load(open('/home/opc/.config/kilo/kilo.jsonc'))['provider']['opencodego']['options']['apiKey'])"
```

### 4. Git dubious ownership after Hermes install — ✅ Fixed in PR #1
The `curl | sudo bash` installer puts `/usr/local/lib/hermes-agent/` under root. Git >=2.35 blocks any operation on repos owned by a different user.

**Fix in deploy.sh** (added unconditionally after install block):
```bash
sudo chown -R opc:opc /usr/local/lib/hermes-agent 2>/dev/null || true
```
Added in PR #1 (branch `hermes-fix-hermes-agent-ownership`).
