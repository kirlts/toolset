#!/usr/bin/env python3
"""sync-infisical-secrets.py — Bidirectional secret sync between GitHub and Infisical.

Actions:
  push   GitHub → Infisical  (seeds/updates secrets in Infisical from env vars)
  pull   Infisical → GitHub  (reads secrets from Infisical, writes to GitHub Secrets)

The push runs via SSH on OCI (remote server). The pull runs in the GitHub
Actions runner where GITHUB_TOKEN has repo secrets write permission.

Usage (push via SSH):
  INFISICAL_TOKEN=... INFISICAL_PID=... \
    OPENCODE_GO_API_KEY=... \
    python3 sync-infisical-secrets.py push

Usage (pull from GitHub runner):
  INFISICAL_TOKEN=... INFISICAL_PID=... \
    INFISICAL_URL=https://toolset-oci-1-1.tail2d4c18.ts.net \
    GITHUB_TOKEN=... \
    python3 sync-infisical-secrets.py pull
"""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.parse

INFISICAL_URL = os.environ.get(
    "INFISICAL_URL", "http://localhost:8081"
).rstrip("/")

SCOPED_SECRETS = {
    "dev": [
        "OPENCODE_GO_API_KEY",
        "FUNNEL_DOMAIN",
        "HERMES_LLM_PROVIDER",
        "HERMES_LLM_MODEL",
        "HERMES_WEBUI_PASSWORD",
        "HERMES_WHATSAPP_MODE",
        "WHATSAPP_ALLOWED_USERS",
        "COMPOSIO_API_KEY",
        "COMPOSIO_MCP_KEY",
    ],
    "prod": [
        "OPENCODE_GO_API_KEY",
        "FUNNEL_DOMAIN",
        "HERMES_LLM_PROVIDER",
        "HERMES_LLM_MODEL",
        "HERMES_WEBUI_PASSWORD",
        "HERMES_WHATSAPP_MODE",
        "WHATSAPP_ALLOWED_USERS",
        "COMPOSIO_API_KEY",
        "COMPOSIO_MCP_KEY",
    ],
}

# PREFIXES for reverse-sync (only these keys flow Infisical → GitHub)
REVERSE_PREFIXES = ("HERMES_", "WHATSAPP_", "INFISICAL_")


def _get_token_pid():
    token = (
        os.environ.get("INFISICAL_TOKEN")
        or os.environ.get("INFISICAL_SERVICE_TOKEN", "")
    )
    pid = os.environ.get("INFISICAL_PID", "")
    if not token:
        print("  [sync] ERROR: INFISICAL_TOKEN or INFISICAL_SERVICE_TOKEN required")
        sys.exit(1)
    if not pid:
        print("  [sync] ERROR: INFISICAL_PID required")
        sys.exit(1)
    return token, pid


def _api(method: str, path: str, data: dict = None) -> dict:
    token, pid = _get_token_pid()
    url = f"{INFISICAL_URL}/api/v3{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:500]
        print(f"  [sync] HTTP {e.code} {method} {path}: {err}")
        return {}
    except Exception as e:
        print(f"  [sync] ERROR {method} {path}: {e}")
        return {}


def _fetch_secret_strict(name: str, env: str) -> "str | None":
    """Fetch a single secret by name. Returns value or None."""
    token, pid = _get_token_pid()
    params = urllib.parse.urlencode({
        "workspaceId": pid,
        "environment": env,
    })
    url = f"{INFISICAL_URL}/api/v3/secrets/raw/{name}?{params}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("secret", {}).get("secretValue") or data.get("secretValue")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        return None


def action_push():
    pid = os.environ.get("INFISICAL_PID", "")
    errors = 0
    for env_name, names in SCOPED_SECRETS.items():
        for name in names:
            value = os.environ.get(name, "")
            if not value:
                print(f"  [sync] SKIP {env_name}/{name} (empty)")
                continue
            payload = {
                "workspaceId": pid,
                "environment": env_name,
                "secretPath": "/",
                "secretValue": value,
                "type": "shared",
            }
            result = _api("POST", f"/secrets/raw/{name}", payload)
            if result.get("secret"):
                print(f"  [sync] OK {env_name}/{name}")
            else:
                # Secret already exists → update via PATCH
                result = _api("PATCH", f"/secrets/raw/{name}", payload)
                if result.get("secret"):
                    print(f"  [sync] UPD {env_name}/{name}")
                else:
                    print(f"  [sync] FAIL {env_name}/{name}")
                    errors += 1
    if errors:
        print(f"  [sync] {errors} failures")
        return 1
    print("  [sync] All secrets pushed")
    return 0


def action_verify():
    """Verify that all scoped secrets exist in Infisical by fetching each one."""
    errors = 0
    for env_name, names in SCOPED_SECRETS.items():
        for name in names:
            val = _fetch_secret_strict(name, env_name)
            if val is not None:
                print(f"  [sync] VERIFY OK {env_name}/{name}")
            else:
                print(f"  [sync] VERIFY MISSING {env_name}/{name}")
                errors += 1
    if errors:
        print(f"  [sync] {errors} secret(s) missing after push")
        return 1
    print("  [sync] All secrets verified")
    return 0


def action_pull():
    """Pull new secrets from Infisical to GitHub Secrets."""
    gh_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
    if not gh_token:
        print("  [sync] WARNING: No GITHUB_TOKEN/GH_TOKEN — skipping reverse sync")
        print("  [sync] Set GITHUB_TOKEN to enable Infisical → GitHub sync")
        return 0

    gh_repo = os.environ.get("GH_REPO", "kirlts/toolset")
    errors = 0

    # Get existing GitHub secret names for comparison
    try:
        r = subprocess.run(
            ["gh", "secret", "list", "--repo", gh_repo],
            capture_output=True, text=True, timeout=15,
            env={**os.environ, "GH_TOKEN": gh_token},
        )
        if r.returncode != 0:
            print(f"  [sync] Cannot list GitHub secrets: {r.stderr.strip()}")
            return 0
        gh_secrets = set()
        for line in r.stdout.strip().split("\n"):
            parts = line.split("\t")
            if parts:
                gh_secrets.add(parts[0])
    except Exception as e:
        print(f"  [sync] Error listing GitHub secrets: {e}")
        return 0

    found = 0
    pushed = 0
    for env_name in ("dev", "prod"):
        for name in SCOPED_SECRETS.get(env_name, []):
            if name in gh_secrets:
                continue
            val = _fetch_secret_strict(name, env_name)
            if val is None:
                continue
            found += 1
            if not name.startswith(REVERSE_PREFIXES):
                continue
            try:
                r = subprocess.run(
                    ["gh", "secret", "set", name, "--body", val, "--repo", gh_repo],
                    capture_output=True, text=True, timeout=15,
                    env={**os.environ, "GH_TOKEN": gh_token},
                )
                if r.returncode == 0:
                    print(f"  [sync] PULL OK {name}")
                    pushed += 1
                else:
                    print(f"  [sync] PULL FAIL {name}: {r.stderr.strip()}")
                    errors += 1
            except Exception as e:
                print(f"  [sync] PULL ERROR {name}: {e}")
                errors += 1

    print(f"  [sync] Found {found} new secret(s), pushed {pushed}")
    if errors:
        print(f"  [sync] {errors} reverse-sync failure(s)")
        return 1
    return 0


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "push":
        return action_push()
    elif action == "verify":
        return action_verify()
    elif action == "pull":
        return action_pull()
    else:
        print(f"Usage: {sys.argv[0]} <push|verify|pull>")
        return 1


if __name__ == "__main__":
    sys.exit(main())
