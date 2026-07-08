#!/usr/bin/env python3
"""tenant-create.py — interactive CLI to create a tenant definition JSON.

Usage:
    python3 tenant-create.py                   # interactive mode
    python3 tenant-create.py --output dinobot.json  # output to file
    python3 tenant-create.py --dry-run          # print JSON only, don't save
"""

import json
import sys
from pathlib import Path

ALLOWED_TOOLSETS = ["terminal", "file", "web", "cronjob", "skills"]
ALLOWED_MEMORY = ["holographic", "builtin"]
ALLOWED_APPROVAL_MODES = ["off", "smart", "manual"]
ALLOWED_CRON_MODES = ["deny", "approve"]


def prompt(prompt_text, default=None, validate_fn=None):
    while True:
        default_str = f" [{default}]" if default is not None else ""
        val = input(f"{prompt_text}{default_str}: ").strip()
        if not val and default is not None:
            val = default
        if validate_fn:
            err = validate_fn(val)
            if err:
                print(f"  Error: {err}")
                continue
        return val


def prompt_yn(prompt_text, default=True):
    yn = "Y/n" if default else "y/N"
    val = input(f"{prompt_text} [{yn}]: ").strip().lower()
    if not val:
        return default
    return val in ("y", "yes")


def prompt_multi(prompt_text, items, allow_all=True):
    print(f"\n{prompt_text}")
    selected = []
    for item in items:
        default_yn = "Y" if item in ["terminal", "file", "skills"] else "n"
        yn = "Y/n" if default_yn == "Y" else "y/N"
        val = input(f"  {item}? [{yn}]: ").strip().lower()
        if not val and default_yn == "Y":
            selected.append(item)
        elif val in ("y", "yes"):
            selected.append(item)
    return selected


def validate_name(name):
    import re
    if not re.match(r"^[a-z][a-z0-9_-]{1,31}$", name):
        return "must be lowercase kebab-case, 1-32 chars"
    if name in ("default", "hermes", "toolset", "personal", "chat", "wwe", "entrenador"):
        return f"'{name}' is a reserved name"
    return None


def validate_phone(number):
    import re
    if not re.match(r"^\+\d{8,15}$", number):
        return "must be E.164 format (e.g. +56936414929)"
    return None


def validate_gh_url(url):
    import re
    if not re.match(r"^https://github\.com/[\w.-]+/[\w.-]+$", url):
        return "must be a valid GitHub HTTPS URL"
    return None


def validate_digits(value):
    import re
    if not re.match(r"^[1-9][0-9]{6,14}$", str(value)):
        return "must be digits only, no + prefix"
    return None


def main():
    output_file = None
    dry_run = False

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--output" and i + 1 < len(args):
            output_file = args[i + 1]
            i += 2
        elif args[i] == "--dry-run":
            dry_run = True
            i += 1
        elif args[i] == "--help":
            print(__doc__)
            sys.exit(0)
        else:
            print(f"Unknown argument: {args[i]}")
            sys.exit(2)

    print("=== Tenant Creator ===\n")

    # ── Tennant name ──
    name = prompt("Tenant name (lowercase kebab-case)", validate_fn=validate_name)

    # ── Description ──
    description = prompt("Short description", default=f"Asistente autonomo para {name}")

    # ── WhatsApp ──
    wa_number = prompt("WhatsApp phone number (+569...)", validate_fn=validate_phone)
    allowed = []
    print("\nAllowed WhatsApp users (digits only, one per line, empty line to finish):")
    while True:
        user = input("  Phone: ").strip()
        if not user:
            break
        err = validate_digits(user)
        if err:
            print(f"    Error: {err}")
        else:
            allowed.append(user)
    if not allowed:
        print("  No users added. Adding default placeholder.")
        allowed = ["56994172921"]

    # ── Repos ──
    repos = []
    print("\nRepositories (one per line, format: URL push:true|false branch):")
    print("  Example: https://github.com/kirlts/repo true main")
    while True:
        line = input("  Repo: ").strip()
        if not line:
            break
        parts = line.split()
        if len(parts) < 3:
            print("    Error: need URL push:true|false branch")
            continue
        url, push_str, branch = parts[0], parts[1], parts[2]
        err = validate_gh_url(url)
        if err:
            print(f"    Error: {err}")
            continue
        push = push_str.lower() in ("true", "1", "yes")
        repos.append({"url": url, "push": push, "branch": branch})
    if not repos:
        print("  No repos added. Aborting.")
        sys.exit(1)

    # ── Model ──
    print("\nModel configuration:")
    model_default = prompt("  Default model", default="deepseek-v4-flash")
    model_provider = prompt("  Provider", default="opencode-go")
    model_fallback = prompt("  Fallback model", default="qwen3.7-plus")

    # ── Toolsets ──
    toolsets = prompt_multi("Toolsets:", ALLOWED_TOOLSETS)

    # ── Memory ──
    print("\nMemory provider:")
    for i, m in enumerate(ALLOWED_MEMORY):
        print(f"  [{i+1}] {m}")
    mem_idx = prompt("  Choice", default="1")
    mem_provider = ALLOWED_MEMORY[int(mem_idx)-1] if mem_idx.isdigit() and 1 <= int(mem_idx) <= len(ALLOWED_MEMORY) else "holographic"

    # ── Approvals ──
    print(f"\nApprovals mode: {', '.join(ALLOWED_APPROVAL_MODES)}")
    appr_mode = prompt("  Mode", default="smart")
    if appr_mode not in ALLOWED_APPROVAL_MODES:
        appr_mode = "smart"
    print(f"Cron approvals mode: {', '.join(ALLOWED_CRON_MODES)}")
    cron_mode = prompt("  Cron mode", default="approve")
    if cron_mode not in ALLOWED_CRON_MODES:
        cron_mode = "approve"

    # ── Workspace ──
    workspace = f"/home/opc/workspace/tenants/{name}"
    cwd_custom = prompt("Workspace path", default=workspace)

    terminal_timeout = prompt("Terminal timeout (seconds)", default="180")
    try:
        terminal_timeout = int(terminal_timeout)
    except ValueError:
        terminal_timeout = 180

    # ── TTS ──
    print("\nTTS (Text-to-Speech via Edge):")
    tts_enabled = prompt_yn("  Enable TTS?", default=False)
    tts_voice = "es-CL-LorenzoNeural"
    tts_scope = "all"
    if tts_enabled:
        print("  Voice: [1] es-CL-LorenzoNeural (masculina)  [2] es-CL-CatalinaNeural (femenina)")
        voice_idx = prompt("  Choice", default="1")
        tts_voice = "es-CL-CatalinaNeural" if voice_idx == "2" else "es-CL-LorenzoNeural"
        print("  Scope: [1] all  [2] DM only  [3] groups only")
        scope_idx = prompt("  Choice", default="1")
        tts_scope = {"2": "dm", "3": "groups"}.get(scope_idx, "all")

    # ── Build JSON ──
    tenant = {
        "name": name,
        "description": description,
        "whatsapp_number": wa_number,
        "allowed_users": allowed,
        "repos": repos,
        "model": {
            "default": model_default,
            "provider": model_provider,
            "fallback": model_fallback,
        },
        "toolsets": toolsets,
        "memory": {
            "provider": mem_provider,
        },
        "approvals": {
            "mode": appr_mode,
            "cron_mode": cron_mode,
        },
        "terminal": {
            "cwd": f"{cwd_custom}/repos",
            "timeout": terminal_timeout,
        },
        "cron": {
            "gateway_notify_interval": 3600,
        },
        "tts": {
            "enabled": tts_enabled,
            "voice": tts_voice,
            "scope": tts_scope,
        },
    }

    json_str = json.dumps(tenant, indent=2, ensure_ascii=False)

    if dry_run:
        print("\n=== Generated JSON ===\n")
        print(json_str)
        return

    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        Path(output_file).write_text(json_str + "\n")
        print(f"\n✓ Written to {output_file}")
    else:
        # Default: write to definitions dir
        defs_dir = Path(__file__).resolve().parent.parent / "hermes" / "tenants" / "definitions"
        out = defs_dir / f"{name}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json_str + "\n")
        print(f"\n✓ Written to {out}")

    # ── Validate ──
    print("\nValidating...")
    vq_path = Path(__file__).resolve().parent.parent / "hermes" / "scripts" / "validate-tenant-json.py"
    if vq_path.exists():
        import subprocess
        target = output_file or str(out)
        result = subprocess.run([sys.executable, str(vq_path), target], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Validation passed: {result.stdout.strip()}")
        else:
            print(f"✗ Validation failed:\n{result.stderr}")
            sys.exit(1)

    print(f"\nDone. To provision this tenant, run:")
    print(f"  provision-tenant.sh {output_file or str(out)}")


if __name__ == "__main__":
    main()
