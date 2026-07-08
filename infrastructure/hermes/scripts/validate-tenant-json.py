#!/usr/bin/env python3
"""validate-tenant-json.py — validates a tenant definition JSON against schema.

Usage:
    python3 validate-tenant-json.py tenant.json   # returns 0 if valid, 1 if invalid
    python3 validate-tenant-json.py --schema       # prints JSON schema to stdout
"""

import json
import sys
import re
from pathlib import Path

SCHEMA = {
    "type": "object",
    "required": ["name", "description", "whatsapp_number", "allowed_users", "repos", "model", "toolsets", "memory", "approvals", "terminal", "cron", "tts", "stt"],
    "properties": {
        "name": {
            "type": "string",
            "pattern": "^[a-z][a-z0-9_-]{1,31}$",
            "description": "Tenant name. Lowercase kebab-case, 1-32 chars. Used as Hermes profile name."
        },
        "description": {
            "type": "string",
            "minLength": 3,
            "description": "Short description of the tenant. Injected into its SOUL.md."
        },
        "whatsapp_number": {
            "type": "string",
            "pattern": "^\\+[1-9][0-9]{7,14}$",
            "description": "WhatsApp phone number in E.164 format (e.g. +56936414929)."
        },
        "allowed_users": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "string",
                "pattern": "^[1-9][0-9]{6,14}$"
            },
            "description": "List of WhatsApp phone numbers (without + prefix) authorized to talk to this tenant."
        },
        "repos": {
            "type": "array",
            "minItems": 0,
            "items": {
                "type": "object",
                "required": ["url", "push", "branch"],
                "properties": {
                    "url": {
                        "type": "string",
                        "pattern": "^https://github\\.com/[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$",
                        "description": "GitHub HTTPS clone URL."
                    },
                    "push": {
                        "type": "boolean",
                        "description": "Whether the tenant needs git push access to this repo."
                    },
                    "branch": {
                        "type": "string",
                        "description": "Default branch to work on."
                    }
                }
            }
        },
        "model": {
            "type": "object",
            "required": ["default", "provider", "fallback"],
            "properties": {
                "default": {"type": "string", "minLength": 1},
                "provider": {"type": "string", "minLength": 1},
                "fallback": {"type": "string", "minLength": 1}
            }
        },
        "toolsets": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "enum": ["terminal", "file", "web", "cronjob", "skills"]},
            "description": "Hermes toolsets enabled for this tenant."
        },
        "memory": {
            "type": "object",
            "required": ["provider"],
            "properties": {
                "provider": {"type": "string", "enum": ["holographic", "builtin"]}
            }
        },
        "approvals": {
            "type": "object",
            "required": ["mode", "cron_mode"],
            "properties": {
                "mode": {"type": "string", "enum": ["off", "smart", "manual"]},
                "cron_mode": {"type": "string", "enum": ["deny", "approve"]}
            }
        },
        "terminal": {
            "type": "object",
            "required": ["cwd"],
            "properties": {
                "cwd": {"type": "string", "minLength": 1},
                "timeout": {"type": "integer", "minimum": 30, "maximum": 600}
            }
        },
        "cron": {
            "type": "object",
            "properties": {
                "gateway_notify_interval": {"type": "integer", "minimum": 60, "maximum": 86400}
            }
        },
        "tts": {
            "type": "object",
            "required": ["enabled", "voice"],
            "properties": {
                "enabled": {"type": "boolean"},
                "voice": {"type": "string", "enum": ["es-CL-LorenzoNeural", "es-CL-CatalinaNeural"]},
                "scope": {"type": "string", "enum": ["dm", "groups", "all"]}
            }
        },
        "stt": {
            "type": "object",
            "required": ["enabled", "provider", "model"],
            "properties": {
                "enabled": {"type": "boolean"},
                "provider": {"type": "string", "minLength": 1},
                "model": {"type": "string", "minLength": 1}
            }
        }
    }
}

ALLOWED_MEMORY_PROVIDERS = {"holographic", "builtin"}
ALLOWED_TOOLSETS = {"terminal", "file", "web", "cronjob", "skills"}


def validate(data, filepath=None):
    errors = []

    # ── Top-level required fields ──
    for field in SCHEMA["required"]:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if errors:
        return errors

    # ── Name ──
    name = data.get("name", "")
    if not re.match(r"^[a-z][a-z0-9_-]{1,31}$", name):
        errors.append(f"name '{name}': must be lowercase kebab-case, 1-32 chars (got '{name}')")
    if name in ("default", "hermes", "toolset", "personal", "chat", "wwe", "entrenador"):
        errors.append(f"name '{name}': reserved name, cannot be used for a tenant")

    # ── WhatsApp number ──
    wa = data.get("whatsapp_number", "")
    if not re.match(r"^\+\d{8,15}$", wa):
        errors.append(f"whatsapp_number '{wa}': must be E.164 format (e.g. +56936414929)")

    # ── Allowed users ──
    allowed = data.get("allowed_users", [])
    if not isinstance(allowed, list) or len(allowed) == 0:
        errors.append("allowed_users: must be a non-empty array")
    else:
        for i, u in enumerate(allowed):
            if not re.match(r"^[1-9][0-9]{6,14}$", str(u)):
                errors.append(f"allowed_users[{i}] '{u}': invalid phone number format (no + prefix, digits only)")

    # ── Repos ──
    repos = data.get("repos", [])
    if not isinstance(repos, list):
        errors.append("repos: must be an array")
    else:
        for i, r in enumerate(repos):
            if not isinstance(r, dict):
                errors.append(f"repos[{i}]: must be an object")
                continue
            url = r.get("url", "")
            if not re.match(r"^https://github\.com/[\w.-]+/[\w.-]+$", url):
                errors.append(f"repos[{i}].url '{url}': invalid GitHub HTTPS URL")
            if not isinstance(r.get("push"), bool):
                errors.append(f"repos[{i}].push: must be true or false")
            if not r.get("branch"):
                errors.append(f"repos[{i}].branch: must be a non-empty string")

    # ── Model ──
    model = data.get("model", {})
    if not model.get("default"):
        errors.append("model.default: must be a non-empty string")
    if not model.get("provider"):
        errors.append("model.provider: must be a non-empty string")

    # ── Toolsets ──
    toolsets = data.get("toolsets", [])
    if not isinstance(toolsets, list):
        errors.append("toolsets: must be an array")
    else:
        for i, t in enumerate(toolsets):
            if t not in ALLOWED_TOOLSETS:
                errors.append(f"toolsets[{i}] '{t}': not in allowed set {ALLOWED_TOOLSETS}")

    # ── Memory ──
    mem = data.get("memory", {})
    provider = mem.get("provider", "")
    if provider not in ALLOWED_MEMORY_PROVIDERS:
        errors.append(f"memory.provider '{provider}': must be one of {ALLOWED_MEMORY_PROVIDERS}")

    # ── Approvals ──
    approvals = data.get("approvals", {})
    if approvals.get("mode") not in ("off", "smart", "manual"):
        errors.append(f"approvals.mode '{approvals.get('mode')}': must be off, smart, or manual")
    if approvals.get("cron_mode") not in ("deny", "approve"):
        errors.append(f"approvals.cron_mode '{approvals.get('cron_mode')}': must be deny or approve")

    # ── Terminal ──
    terminal = data.get("terminal", {})
    if not terminal.get("cwd"):
        errors.append("terminal.cwd: must be a non-empty string")

    # ── Description ──
    desc = data.get("description", "")
    if len(desc.strip()) < 3:
        errors.append("description: must be at least 3 characters")

    # ── TTS ──
    tts = data.get("tts", {})
    if tts.get("voice") not in ("es-CL-LorenzoNeural", "es-CL-CatalinaNeural"):
        errors.append("tts.voice: must be es-CL-LorenzoNeural or es-CL-CatalinaNeural")
    if tts.get("scope") not in ("dm", "groups", "all"):
        errors.append("tts.scope: must be dm, groups, or all")

    # ── STT ──
    stt = data.get("stt", {})
    if not stt.get("provider"):
        errors.append("stt.provider: must be a non-empty string")
    if not stt.get("model"):
        errors.append("stt.model: must be a non-empty string")

    return errors


def print_schema():
    print(json.dumps(SCHEMA, indent=2))


def main():
    if len(sys.argv) < 2:
        print("Usage: validate-tenant-json.py <file.json> | --schema", file=sys.stderr)
        sys.exit(2)

    if sys.argv[1] == "--schema":
        print_schema()
        sys.exit(0)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"ERROR: file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(filepath.read_text())
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    errors = validate(data, str(filepath))
    if errors:
        print(f"FAILED validation ({len(errors)} errors):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    print(f"✓ {filepath.name}: valid")
    sys.exit(0)


if __name__ == "__main__":
    main()
