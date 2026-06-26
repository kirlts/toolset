# Gateway Restart Requirement for MCP Key Changes

## Root Cause (observed 25 Jun 2026)

MCP server connections (`mcp_servers` in `config.yaml`) are established **at gateway startup** and cached in memory for the lifetime of the gateway process. Sessions created via `/new` inherit the tools from the already-running gateway — they do NOT re-connect to MCP servers.

If the `x-consumer-api-key` (or any config value) in `mcp_servers` changes in `config.yaml` after the gateway has started, the change is invisible until the gateway process restarts.

## Symptom

```
config.yaml has key: x-consumer-api-key: ck_Ic0vCrJsMEx7TRLwjs_u
But gateway log shows: 401 Unauthorized for 'composio'
```

The key on disk is correct; the gateway loaded a different (stale) key at startup.

## The /new Fallacy

`/new` destroys the current session and creates a new one, but the new session reuses the same gateway process. MCP tools that failed to load at gateway startup will still be absent after `/new`. The error is at the gateway level, not the session level.

## Fix

The gateway must be restarted. This is **not possible from within the gateway** — it blocks `sudo systemctl restart hermes-gateway` because SIGTERM propagates to all child processes and kills the command before it completes.

### Workaround: Cronjob (no_agent)

Schedule a one-shot cronjob with `no_agent=true` that runs the restart command. The cron scheduler is a separate process not killed by gateway shutdown:

```bash
# Schedule via systemd-run to ensure independence
sudo systemd-run --unit=hermes-restart --same-dir sudo systemctl restart hermes-gateway
```

Or via Hermes cronjob API:

```python
# From within Hermes:
cronjob action=create name="gateway-restart" schedule="once at YYYY-MM-DDTHH:MM:SS" \
  script="sudo systemctl restart hermes-gateway" no_agent=true
```

### Workaround: Systemd Timer

Create a oneshot systemd timer (preferred — survives gateway restarts):

```ini
# /etc/systemd/system/hermes-gateway-restart.service
[Unit]
Description=Restart Hermes Gateway
[Service]
Type=oneshot
ExecStart=sudo systemctl restart hermes-gateway
User=root
```

Then trigger via `systemd-run --unit=hermes-gateway-restart-trigger --remain-after-exit`.

### Best: Include in deploy pipeline

The `deploy.sh` script should restart the gateway after any change to MCP config. This is the most reliable approach — for example after `inject-composio-key.py` runs.

## Prevention

1. **Deploy pipeline:** Always restart `hermes-gateway` after injecting MCP keys or modifying `mcp_servers` in config.yaml
2. **Deploy.sh pattern:** Add `sudo systemctl restart hermes-gateway` as the last step after any MCP config change
3. **Verification:** After restart, check `journalctl -u hermes-gateway --no-pager | grep -E '(composio|MCP.*connected)'` to confirm Composio connected successfully
