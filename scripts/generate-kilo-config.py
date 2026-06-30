#!/usr/bin/env python3
"""Generate kilo.jsonc from kilo-system-prompt.md source of truth.

Usage:
    python3 scripts/generate-kilo-config.py

Reads infrastructure/kilo-system-prompt.md, sets it as agent.build.prompt
in infrastructure/kilo.jsonc using proper JSON manipulation (no regex).
"""
import json, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPT_FILE = REPO_ROOT / "infrastructure" / "kilo-system-prompt.md"
CONFIG_FILE = REPO_ROOT / "infrastructure" / "kilo.jsonc"


def md_to_prompt(path: Path) -> str:
    lines = path.read_text().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    while lines and not lines[0].strip():
        lines = lines[1:]
    while lines and not lines[-1].strip():
        lines.pop()
    result = []
    blank = False
    for line in lines:
        if not line.strip():
            if not blank:
                result.append("")
            blank = True
        else:
            result.append(line)
            blank = False
    return "\n".join(result).strip()


def regenerate(config_path: Path, prompt_text: str) -> None:
    # Parse as JSON (kilo.jsonc is standard JSON at the structural level)
    with open(config_path) as f:
        config = json.load(f)

    # Set the prompt
    config["agent"]["build"]["prompt"] = prompt_text

    # Write with pretty formatting matching the original style
    raw = json.dumps(config, indent=2, ensure_ascii=False)
    config_path.write_text(raw + "\n")


if __name__ == "__main__":
    prompt = md_to_prompt(PROMPT_FILE)
    regenerate(CONFIG_FILE, prompt)
    print(f"[OK] Prompt injected ({len(prompt)} chars)")
    print("[OK] JSON valid")
