#!/usr/bin/env python3
"""provision-tenant.py — provision a Hermes tenant from JSON definition."""
import json, os, sys, subprocess

json_path = sys.argv[1] if len(sys.argv) > 1 else "tenants/definitions/tito.json"

with open(json_path) as f:
    t = json.load(f)

name = t["name"]
wa = t["whatsapp_number"]
allowed = t["allowed_users"]
repos = t.get("repos", [])
model_d = t["model"]
provider = model_d["provider"]
toolsets = t["toolsets"]
mem_prov = t["memory"]["provider"]
approvals = t["approvals"]
terminal = t["terminal"]
tts = t["tts"]
stt = t.get("stt", {"enabled": True, "provider": "groq", "model": "whisper-large-v3-turbo"})

cwd = terminal["cwd"]
workspace = os.path.dirname(cwd)
profile_dir = f"/home/opc/.hermes/profiles/{name}"
template_dir = os.environ.get("TEMPLATE_DIR", "/tmp/tito-provision/tenants/template")

print(f"Provisioning: {name}")
print(f"  Profile: {profile_dir}")
print(f"  WhatsApp bot: {wa}")
print(f"  Allowed users: {allowed}")
print(f"  Model: {model_d['default']} ({provider})")
print(f"  TTS: {tts['enabled']} / {tts['voice']}")
print(f"  STT: {stt['enabled']} / {stt['provider']}")

os.makedirs(profile_dir, exist_ok=True)
os.makedirs(cwd, exist_ok=True)

# Auto-assign bridge port: 3001 for first tenant, 3002 for second, etc.
profile_base = Path(profile_dir).parent
existing_tenants = sum(1 for p in profile_base.iterdir() if (p / ".tenant").exists() and p.name != name)
bridge_port = 3001 + existing_tenants
print(f"  Bridge port auto-assigned: {bridge_port}")

# ── config.yaml ──
cfg = open(f"{template_dir}/config.yaml").read()
cfg = cfg.replace("<TENANT_NAME>", name)
cfg = cfg.replace("<TENANT_MODEL>", model_d["default"])
cfg = cfg.replace("<TENANT_PROVIDER>", provider)
cfg = cfg.replace("<TENANT_FALLBACK_MODEL>", f"{provider}/{model_d['fallback']}")
cfg = cfg.replace("<TENANT_WORKSPACE>", workspace)
cfg = cfg.replace("<TENANT_TTS_VOICE>", tts["voice"])
cfg = cfg.replace("<TENANT_TTS_ENABLED>", str(tts["enabled"]).lower())
cfg = cfg.replace("<TENANT_STT_ENABLED>", str(stt["enabled"]).lower())

allowed_yaml = "\n".join(f"  - {u}" for u in allowed)
cfg = cfg.replace("<TENANT_ALLOWED_USERS>", allowed_yaml)

toolsets_yaml = "\n".join(f"- {ts}" for ts in toolsets)
cfg = cfg.replace("<TENANT_TOOLSETS>", toolsets_yaml)

cfg = cfg.replace("mode: smart", f"mode: {approvals['mode']}")
cfg = cfg.replace("cron_mode: approve", f"cron_mode: {approvals['cron_mode']}")

open(f"{profile_dir}/config.yaml", "w").write(cfg)
print("  \u2713 config.yaml")

# ── SOUL.md ──
soul = open(f"{template_dir}/SOUL.md").read()
soul = soul.replace("<TENANT_NAME>", name)
soul = soul.replace("<TENANT_DESCRIPTION>", t["description"])
soul = soul.replace("<TENANT_WORKSPACE>", workspace)
soul = soul.replace("<TENANT_TOOLSETS_DESCRIPTION>", ", ".join(toolsets))
soul = soul.replace("<TENANT_TTS_DESCRIPTION>", "")

if repos:
    repos_desc = []
    for r in repos:
        push_str = " (push)" if r["push"] else " (read-only)"
        repos_desc.append("- " + r["url"] + " [" + r["branch"] + "]" + push_str)
    soul += "\n## Repositorios autorizados\n" + "\n".join(repos_desc) + "\n"
else:
    soul += "\n## Repositorios\nSin repositorios asignados. Eres un asistente conversacional.\n"

if tts["enabled"]:
    soul += "\n## TTS\nTu TTS esta activado con voz " + tts["voice"] + ". Alcance: " + tts.get("scope", "all") + ".\nCuando respondas mensajes que califiquen para audio (respuestas densas, >200 palabras), genera un audio usando la herramienta TTS de Hermes con provider edge.\n"
else:
    soul += "\n## TTS\nTTS desactivado.\n"

if stt["enabled"]:
    soul += "\n## STT\nPuedes recibir y transcribir mensajes de voz via WhatsApp.\nProveedor: " + stt["provider"] + " (" + stt["model"] + ").\n"
else:
    soul += "\n## STT\nSTT desactivado.\n"

open(f"{profile_dir}/SOUL.md", "w").write(soul)
print("  \u2713 SOUL.md")

# ── .env ──
env_tpl = open(f"{template_dir}/env.template").read()
env = env_tpl.replace("<TENANT_NAME>", name)
env = env.replace("<TENANT_BRIDGE_PORT>", str(bridge_port))
env = env.replace("<TENANT_API_KEY>", os.environ.get("OPENCODE_GO_API_KEY", "PLACEHOLDER"))
env = env.replace("<TENANT_WHATSAPP_NUMBER>", wa)
env = env.replace("<TENANT_ALLOWED_USERS_CSV>", ",".join(allowed))
env = env.replace("<TENANT_GITHUB_TOKEN>", "")
env = env.replace("<TENANT_GITHUB_USER>", "git")
env = env.replace("<TENANT_GROQ_API_KEY>", os.environ.get("GROQ_API_KEY", ""))
open(f"{profile_dir}/.env", "w").write(env)
os.chmod(f"{profile_dir}/.env", 0o600)
print("  \u2713 .env")

# ── Marker ──
open(f"{profile_dir}/.tenant", "w").close()
print("  \u2713 .tenant marker")

# ── Hermes profile ──
subprocess.run(["hermes", "profile", "create", name], capture_output=True)
print("  \u2713 hermes profile")

# ── Gateway install ──
subprocess.run(["hermes", "-p", name, "gateway", "install"], capture_output=True)
print("  \u2713 gateway installed")

print(f"\n\u2713 Tenant '{name}' ready.")
print(f"  Profile: {profile_dir}")
print(f"  Next: hermes -p {name} whatsapp  (scan QR on VPS)")
print(f"  Then start: systemctl --user start hermes-gateway-{name}")
