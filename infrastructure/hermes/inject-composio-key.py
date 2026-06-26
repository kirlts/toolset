#!/usr/bin/env python3
"""Inject COMPOSIO_MCP_KEY into Hermes config.yaml.

Called by deploy.sh (CI/CD). Fetches the key from Infisical first,
falls back to the Hermes .env file. Writes mcp_servers block into config.yaml.

Why a standalone file instead of inline Python in bash/SSH:
Inline Python inside `ssh host "python3 -c \"...\""` has escaping bugs
with nested quotes, f-strings, and special chars. A file avoids all that.
"""

import json
import os
import subprocess
import sys

try:
    import yaml
except ImportError:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "pyyaml", "-q"],
        check=True,
    )
    import yaml

# --- Config ---
INFISICAL_ENV = "/opt/toolset/.env"
HERMES_ENV = "/home/opc/.hermes/.env"
CONFIG_YAML = "/home/opc/.hermes/config.yaml"
SECRET_NAME = "COMPOSIO_MCP_KEY"


def read_env_var(filepath, varname):
    """Read a single variable from an env-style file."""
    try:
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line.startswith(varname + "="):
                    return line.split("=", 1)[1]
    except FileNotFoundError:
        return None
    return None


def fetch_from_infisical(token, pid):
    """Fetch a secret from the local Infisical API."""
    try:
        url = (
            "http://localhost:8081/api/v3/secrets/raw/"
            + SECRET_NAME
            + "?workspaceId="
            + pid
            + "&environment=prod"
        )
        r = subprocess.run(
            [
                "curl",
                "-s",
                "-H",
                "Authorization: Bearer " + token,
                url,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            print("  [composio] curl exit=" + str(r.returncode), file=sys.stderr)
            return None
        data = json.loads(r.stdout)
        val = data.get("secret", {}).get("secretValue")
        return val
    except Exception as e:
        print("  [composio] Infisical fetch failed: " + str(e), file=sys.stderr)
        return None


def write_config(composio_key):
    """Write mcp_servers into Hermes config.yaml."""
    try:
        with open(CONFIG_YAML) as f:
            cfg = yaml.safe_load(f) or {}
    except FileNotFoundError:
        print("  [composio] " + CONFIG_YAML + " not found, creating new", file=sys.stderr)
        cfg = {}

    # Clean old format keys
    cfg.pop("memory_provider", None)
    cfg.pop("default", None)

    cfg.setdefault("mcp_servers", {})

    cfg["model"] = {
        "default": "opencodego/deepseek-v4-flash",
        "provider": "opencode-go",
    }

    cfg["context_file_max_chars"] = 25000

    cfg["approvals"] = {
        "mode": "smart",
        "timeout": 60,
        "destructive_slash_confirm": False,
        "mcp_reload_confirm": True,
        "cron_mode": "deny",
    }

    cfg.setdefault("skills", {})
    cfg["skills"]["external_dirs"] = [
        "/opt/toolset-repo/infrastructure/hermes-skills",
        "/opt/toolset-repo/.agents/skills",
    ]

    if composio_key:
        cfg["mcp_servers"]["composio"] = {
            "url": "https://connect.composio.dev/mcp",
            "headers": {"x-consumer-api-key": composio_key},
            "connect_timeout": 60,
            "timeout": 180,
        }
        print("  [composio] MCP server configured with real key")
    else:
        print("  [composio] WARNING: no key obtained — keeping existing config if any")

    cfg["mcp_servers"]["hindsight-selfhosted"] = {
        "url": "https://toolset-oci-1-1.tail2d4c18.ts.net/hindsight/mcp/"
    }

    with open(CONFIG_YAML, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False)

    print("  [composio] config.yaml written")
    return bool(composio_key)


def main():
    # --- Attempt 1: Infisical ---
    token = read_env_var(INFISICAL_ENV, "INFISICAL_SERVICE_TOKEN")
    pid = read_env_var(INFISICAL_ENV, "INFISICAL_PID")

    composio_key = None
    if token and pid:
        print("  [composio] fetching key from Infisical...")
        composio_key = fetch_from_infisical(token, pid)
        if composio_key:
            print("  [composio] key fetched from Infisical")
    else:
        t_status = "set" if token else "missing"
        p_status = "set" if pid else "missing"
        print(
            "  [composio] skipping Infisical (token="
            + t_status
            + ", pid="
            + p_status
            + ")"
        )

    # --- Attempt 2: Fallback to Hermes .env ---
    if not composio_key:
        print("  [composio] falling back to Hermes .env...")
        composio_key = read_env_var(HERMES_ENV, "COMPOSIO_MCP_KEY")
        if composio_key:
            print("  [composio] key read from Hermes .env (fallback)")

    # --- Write config ---
    ok = write_config(composio_key)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
