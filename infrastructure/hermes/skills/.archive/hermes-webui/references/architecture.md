# Hermes WebUI — Session-Specific Detail

> Architecture and configuration notes from the toolset personal deployment.
> Last updated: 2026-06-24

## Port Map

| Port | Process | Routes |
|---|---|---|
| 8080 | Caddy (Docker) | Main reverse proxy |
| 8888 | hermes-webui (systemd) | WebUI backend (Python/API) |
| 8787 | Tailscale Funnel | HTTPS direct access to hermes-webui |
| 9999 | Hindsight CP (Docker) | Hindsight Control Plane |

## Caddy Routing for /hermes/

From `infrastructure/Caddyfile`:

```
handle_path /hermes/* {
    reverse_proxy host.docker.internal:8888
}
```

`host.docker.internal:8888` reaches the Docker host's port 8888, which is the hermes-webui systemd service. The Hindsight Docker container also maps port 8888, but Caddy path-based routing disambiguates: `/hermes/*` → hermes-webui, `/hindsight/*` → Hindsight.

## deploy.sh WebUI Section (lines ~774-813)

The deploy script:

1. Clones nesquena/hermes-webui to `/opt/hermes-webui` if not present
2. Creates systemd unit at `/etc/systemd/system/hermes-webui.service`
3. Sets env vars: `HERMES_WEBUI_PORT=8888`, `HERMES_WEBUI_HOST=0.0.0.0`, `HERMES_WEBUI_SKIP_ONBOARDING=1`, `HERMES_WEBUI_PASSWORD=***`
4. Sets default model in settings.json:
   ```python
   d["default_model"] = "opencodego/deepseek-v4-flash"
   d["default_provider"] = "opencode-go"
   ```
5. Configures Tailscale funnel on port 8787 → localhost:8888

## systemd Service

```
[Service]
Type=simple
User=opc
WorkingDirectory=/opt/hermes-webui
ExecStart=/usr/local/lib/hermes-agent/venv/bin/python /opt/hermes-webui/server.py
Restart=on-failure
```

## Settings JSON Schema

Full `~/.hermes/webui/settings.json` structure (as of v0.51.582):

- `send_key`: `"enter"` | `"ctrl+enter"`
- `default_workspace`: string path
- `default_model`: e.g. `"opencodego/deepseek-v4-flash"`
- `default_provider`: e.g. `"opencode-go"`
- `theme`: `"dark"` | `"light"`
- `skin`: theme variant string
- `language`: locale code
- `busy_input_mode`: `"queue"` | `"interrupt"` | `"steer"`
- `font_size`: `"small"` | `"medium"` | `"large"`
- `show_thinking`: boolean
- `simplified_tool_calling`: boolean
- `notifications_enabled`: boolean
- `sound_enabled`: boolean
- Various `hide_composer_*` visibility toggles
- `password_hash`: string or null
- Various `inflight_state_*` memory caps

## Loading the Settings

In `static/boot.js`, the settings are fetched from `/api/settings` at boot:

```javascript
const s = await api('/api/settings');
window._sendKey = s.send_key || 'enter';
```
