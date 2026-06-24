---
name: hermes-webui
description: "Manage the Hermes WebUI (nesquena/hermes-webui) deployment, configuration, and troubleshooting. Covers systemd service, settings.json, send_key behavior, Caddy reverse proxy, CI/CD integration via deploy.sh."
version: 1.0.0
author: Toolset Personal
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [webui, deployment, configuration, settings, send-key, caddy, systemd]
    related_skills: [hermes-sync-configure, agent-state-management, hermes-agent]
---

# Hermes WebUI

The Hermes WebUI is the [nesquena/hermes-webui](https://github.com/nesquena/hermes-webui) project — a lightweight, dark-themed web app interface for Hermes Agent. It runs as a standalone systemd service (`hermes-webui.service`) on port 8888, reverse-proxied by Caddy at `/hermes/`.

## Architecture

```
Browser ──> Caddy (:8080) ──> /hermes/* ──> host.docker.internal:8888 ──> hermes-webui (systemd)
                                                                               │
                                                                               └──> ~/.hermes/webui/settings.json
                                                                               └──> /opt/hermes-webui/ (Git clone)
```

- **Caddy** (`infrastructure/Caddyfile`): routes `/hermes/*` to `host.docker.internal:8888`
- **systemd service**: `/etc/systemd/system/hermes-webui.service`
- **Settings**: `/home/opc/.hermes/webui/settings.json`
- **Source**: `/opt/hermes-webui/` (git clone from nesquena/hermes-webui)
- **Deploy**: CI/CD via `deploy.sh` (clones, configures, starts service)

## Key Configuration

### `settings.json`

Located at `~/.hermes/webui/settings.json`. This is a JSON file with user preferences, NOT in the toolset repo. Key settings:

| Key | Values | Description |
|---|---|---|
| `send_key` | `"enter"` (default) or `"ctrl+enter"` | Controls Enter key behavior in chat composer |
| `default_model` | e.g. `"opencodego/deepseek-v4-flash"` | Default model for new sessions |
| `default_provider` | e.g. `"opencode-go"` | Default provider |
| `theme` | `"dark"` or `"light"` | UI theme |
| `language` | e.g. `"en"`, `"es"` | UI language |
| `busy_input_mode` | `"queue"`, `"interrupt"`, `"steer"` | Behavior when sending while agent is running |

### Send Key Behavior

The `send_key` setting controls how Enter works in the chat composer:

**`"enter"` (default):**
| Key | Behavior |
|---|---|
| Enter | Sends message |
| Shift+Enter | Newline |

**`"ctrl+enter"`:**
| Key | Behavior |
|---|---|
| Enter | Newline |
| Ctrl+Enter / Cmd+Enter | Sends message |
| Numpad Enter | Sends message |

The setting is loaded at boot time from `settings.json` and stored in `window._sendKey`. The keyboard handler is in `static/boot.js` (~line 1556):

```javascript
if(window._sendKey==='ctrl+enter'||_mobileDefault){
  if(isNumpadEnter||e.ctrlKey||e.metaKey){e.preventDefault();send();}
} else {
  if(!e.shiftKey){e.preventDefault();send();}
}
```

## Configuring Auxiliary Vision Model

The Hermes `config.yaml` has an `auxiliary.vision` section that controls the model used for image analysis. This is separate from the main text model (`model.default`) and must use a multimodal-capable model.

### Write Protection

The running config at `~/.hermes/config.yaml` is **write-protected from tool-based file writes**. Attempting `patch()` or `write_file()` on it will be rejected with a security error. To modify the running config, use the Hermes CLI:

```bash
hermes config set auxiliary.vision.model mimo-v2-omni
hermes config set auxiliary.vision.base_url 'https://opencode.ai/zen/go/v1'
hermes config set auxiliary.vision.provider opencode-go
```

### CI/CD Double-Write Pattern

Any change to Hermes config must update **both** locations:

| Location | Method | Purpose |
|---|---|---|
| `~/.hermes/config.yaml` | `hermes config set` | Running config (takes effect immediately) |
| `infrastructure/hermes/config.yaml` | patch/write_file | Repo source of truth (persists through CI/CD) |

The repo config is what `deploy.sh` restores during deployment. Changing only the running config without updating the repo means the change is lost on the next CI/CD deploy.

### Correct Vision Config for OpenCode Go

Per user permanent directive (24 Jun 2026):

```yaml
auxiliary:
  vision:
    provider: opencode-go
    model: mimo-v2-omni
    base_url: "https://opencode.ai/zen/go/v1"
```

**Do NOT** use `openai/gpt-4o` as the vision model — that was set incorrectly by a previous session that mis-interpreted "omni" as a generic descriptor. The correct model is `mimo-v2-omni` from OpenCode Go's model list. See `references/opencode-models.md` for the full model list and discovery endpoint.

The user's permanent directive (retained in Hindsight bank `hermes`):
- `mimo-v2-omni` is the exclusive vision model
- `deepseek-v4-flash` is the exclusive text model
- Every config change must go through CI/CD (repo + deploy), no exceptions

## Common Tasks

### Check if service is running

```bash
systemctl status hermes-webui
```

### View current settings

```bash
cat ~/.hermes/webui/settings.json | python3 -m json.tool
```

### Change send key

```bash
python3 -c "
import json
sp = '/home/opc/.hermes/webui/settings.json'
d = json.load(open(sp))
d['send_key'] = 'ctrl+enter'  # or 'enter'
json.dump(d, open(sp, 'w'), indent=2)
print('send_key updated')
"
```

After changing settings, hard-refresh the WebUI page (Ctrl+Shift+R) to reload boot.js.

### Restart the service

```bash
sudo systemctl restart hermes-webui
```

### Update the WebUI source

The source lives at `/opt/hermes-webui/`, cloned from GitHub. deploy.sh handles this:

```bash
cd /opt/hermes-webui && git pull
sudo systemctl restart hermes-webui
```

## CI/CD Integration (deploy.sh)

The `deploy.sh` script handles WebUI setup in lines ~774-813:

1. **Clone/update**: `git clone https://github.com/nesquena/hermes-webui.git /opt/hermes-webui`
2. **Service**: Creates `hermes-webui.service` systemd unit
3. **Start**: Enables and starts the service
4. **Default model**: Sets `default_model` and `default_provider` in settings.json
5. **Tailscale funnel**: Ensures port 8787 is funneled to 8888 (Tailscale HTTPS access)

**Important**: `deploy.sh` sets only `default_model` and `default_provider`. Other settings (send_key, theme, language) persist across deploys because they're in `settings.json` which is NOT overwritten. To reset WebUI settings, delete `settings.json` and restart.

## Troubleshooting

### WebUI not loading / blank page

1. Check service: `systemctl status hermes-webui`
2. Check port: `ss -tlnp | grep 8888`
3. Check logs: `journalctl -u hermes-webui -n 50`
4. Verify Caddy proxy: `curl -s http://localhost:8080/hermes/ | head -5`
5. Hard refresh browser (Ctrl+Shift+R)

### "Send Key" toggle not working in Settings UI

If clicking the send key toggle in Settings doesn't change behavior:

1. Verify the setting was persisted: `cat ~/.hermes/webui/settings.json | grep send_key`
2. If correct, the boot.js may be cached. Do a hard refresh (Ctrl+Shift+R).
3. If still broken, check browser console for JavaScript errors in boot.js.
4. The toggle writes to the `/api/settings` endpoint which saves to `settings.json`. Verify the endpoint returns 200.

### WebUI settings not persisting after deploy

Settings persist across deploys because deploy.sh only writes `default_model` and `default_provider`. If settings are being reset, check if something else writes to `settings.json` or if the file was deleted.

## Pitfalls

- **settings.json is NOT versioned in the toolset repo** — it lives in `~/.hermes/webui/` only. A full instance rebuild loses WebUI preferences.
- **Caddy proxy uses `host.docker.internal`** — this works because the hermes-webui runs on the host (systemd), not in Docker.
- **Port 8888 is shared between Hindsight (Docker) and hermes-webui (systemd)** — Caddy routes by path: `/hermes/*` → hermes-webui, `/hindsight/*` → Hindsight container.
- **Hard refresh needed after settings change** — boot.js loads `send_key` once at page load. Changing settings.json requires a page refresh to take effect.
- **Running config.yaml is write-protected** — direct file writes (patch/write_file) to `~/.hermes/config.yaml` are rejected with a security error. Always use `hermes config set` for the running config.
- **CI/CD double-write is mandatory** — after modifying the running config via CLI, always update `infrastructure/hermes/config.yaml` in the toolset repo too. The repo copy is what deploy.sh restores; a running-only change is lost on next deploy.
