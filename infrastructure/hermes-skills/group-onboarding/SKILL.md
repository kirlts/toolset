---
name: group-onboarding
description: "3-phase MECE onboarding for WhatsApp groups and DM. Creates SOUL.md, skills config, and Hindsight bank."
version: 3.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [onboarding, setup, whatsapp, groups, soul]
    triggers: ["/onboarding"]
---

# Group Onboarding — 3-Phase MECE

## Activation Context

| Context | Behavior |
|---|---|
| WhatsApp group | Onboarding for that group. Creates/updates group config + bank + profile SOUL.md. |
| WhatsApp DM | Master orchestrator SOUL.md modification. Requires explicit user confirmation. |
| WebUI / CLI | Not supported. Redirect to WhatsApp group or DM. |

## Files Involved

| File | Purpose |
|---|---|
| `~/.hermes/whatsapp-groups.yaml` | Group → type + profile mapping |
| `~/.hermes/profiles/<name>/SOUL.md` | Per-profile identity and rules |
| `~/.hermes/channel_aliases.json` | JID → {name, desc} resolution |
| Hindsight `create_bank()` / `list_banks()` | Memory bank per group |
| `.agents/templates/profile-soul.md` | SOUL.md template (repo toolset) |

## Pre-Flight: DM Handler

If `/onboarding` is invoked in a DM:

1. Read current `~/.hermes/SOUL.md`. Extract key sections (identity, rules, tone).
2. Respond with a compact summary of current SOUL.md state.
3. Ask: "¿Modificar mi personalidad base? Esto me afecta en todos los canales. (si/no)"
4. If "no" → explain what /onboarding does in groups. End.
5. If "si" → proceed directly to Phase 1 below. **Skip group type selection.** Target is ALWAYS `type: personal` with `profile: default` and `repo: hermes`. The user defines everything else.

## Group Onboarding: 3-Phase Flow

Each phase is MECE (Mutually Exclusive, Collectively Exhaustive). The process advances linearly through all 3 phases. No phase is skipped. No phase is repeated unless the user explicitly requests reconfiguration.

### Phase 1: Identity

**Goal:** Define WHAT this profile is. Zero execution in this phase.

Questions asked in sequence:

1. **Group type:** "¿Que tipo de perfil?" → coding / research / personal / custom
2. **Name:** Auto-detected from `channel_aliases.json`. Editable by user.
3. **Domain/description:** "¿Que hace este perfil? Describilo en una frase."
4. **Repository:** Solo si type=coding o type=research. "¿Repositorio GitHub? (nombre corto o URL completa, o 'n' para ninguno)"
   - Validate: `git ls-remote https://github.com/kirlts/<repo>.git` responde 200.

**Edge cases handled:**
- **No prior context:** Fresh questions, no assumptions.
- **Prior conversation context:** Use context from previous messages as hints. Ask: "Basado en lo que hablamos, ¿esto es coding, research, personal o custom?"
- **Single large instruction:** Parse the instruction for intent keywords. Propose type + description. Ask: "¿Es correcto?"
- **Attached artifacts:** If documents are attached, run `markitdown` per [MARKITDOWN-01]. Extract domain and purpose. Propose type + description.

**Exit condition:** User confirms type, name, description, and (optional) repo. No changes written yet. Proceed to Phase 2.

### Phase 2: Capabilities

**Goal:** Define WHAT this profile can do. Skills, tools, constraints.

Questions asked in sequence:

1. **Skills:** "¿Skills para este perfil? (nombres separados por coma, 'n' para ninguna, '?' para ver disponibles)"
   - If "?": list skills from `hermes skills list` and from external_skills_dirs.
   - Validate each: `hermes skills list | grep <skill>` existe.
   - Pre-fill defaults per type:
     - coding: kilo-code
     - research: standard-research, markitdown-converter
     - personal: (ninguna)
     - custom: (ninguna)
2. **MCP servers:** "¿Servers MCP adicionales? ('n' para los defaults: hindsight + composio)"
3. **Constraints:** "¿Algo que este perfil NUNCA deba hacer?"
   - Store as negative constraints in SOUL.md (e.g., "The file_delete tool is permanently disabled.")

**Edge cases handled:**
- **No skills hub access:** If `hermes skills install` fails, warn but continue. Skills from external_skills_dirs are always available.
- **Invalid skill name:** Suggest similar names via substring match. Offer to skip.
- **MCP server unreachable:** Warn. Defer to runtime.

**Exit condition:** User confirms skills, MCP servers, and constraints. No changes written yet. Proceed to Phase 3.

### Phase 3: Operations

**Goal:** Define HOW this profile operates. Tone, rules, workflows.

Questions asked in sequence:

1. **Tone:** "¿Como debe comunicarse este perfil?"
   - Options: tecnico / conversacional / minimal / custom. Free text accepted.
2. **Worker profile:** "¿Perfil Hermes worker? (nombre, 'default', o 'nuevo' para crear uno)"
   - If "default": uses orchestrator profile. No delegation needed.
   - If "nuevo": create with `hermes profile create <name> --clone`.
   - Validate existing: `hermes profile list | grep <name>`.
 3. **Workflows:** "¿Flujos de trabajo especificos? (ej: 'siempre correr tests antes de commit', 'reportar en formato JSON')"
    - Free text. Stored as operational rules in SOUL.md.
 4. **Evolution preferences:** "¿Como queres que este perfil aprenda y evolucione?"

    Hermes crea skills automaticamente desde la conversacion cuando detecta patrones repetitivos. Esta es una capacidad nativa — no requiere configuracion manual.

    | Opcion | Efecto |
    |---|---|
    | Aprender automaticamente | Hermes crea skills cuando detecte patrones. Sin preguntar. |
    | Preguntar antes de crear | El perfil pide confirmacion antes de crear skills nuevas. |
    | Solo skills explicitas | El perfil no crea skills por si solo. Solo usa las definidas en el onboarding. |
    | Personalizado | Definir reglas: (ej: "crear skill si el patron se repite 3 veces") |

    **Regla global:** Solo el perfil default (orquestador maestro) puede crear skills que afecten multiples grupos. Los perfiles worker crean skills SOLO dentro de su propio alcance. Esto mantiene el aislamiento de cada grupo como pseudo-sandbox.

    **Descripcion de grupo como contexto dinamico:**
    La descripcion del grupo WhatsApp se lee cada 10 min via cron (populate-channel-aliases.sh). El usuario puede editar la descripcion del grupo en WhatsApp y Hermes refleja el cambio en minutos. Esto sirve como contexto operativo permanente: recordatorios, enlaces a recursos, estado actual de tareas.

    Preguntar: "¿Queres usar la descripcion del grupo como contexto dinamico? (ej: editar la descripcion de WhatsApp para actualizar el estado de las tareas, pegar links, dejar notas)"
    - Si: agregar regla [ROUTE-DESC-01] al SOUL.md del perfil.
    - No: solo usa `description` estatica del YAML (la que definiste en Phase 1).

**Edge cases handled:**
- **Profile creation fails:** Fall back to "default". Warn user. Continue.
- **No cwd for new profile:** Derive from repo name (`/opt/<repo>`). Warn if path doesn't exist.
- **WhatsApp description with credentials:** The description field is visible to all group members. Do NOT put actual passwords or API keys there. Only references (e.g., "API key in Infisical path /prod/toolset").

**Exit condition:** User confirms tone, profile, workflows, and evolution preferences. Now WRITE all artifacts.

## Post-Phase: Artifact Creation

After Phase 3 confirmation, write all artifacts in a single atomic block. If any write fails, report error and stop. Do not leave partial state.

### Step 1: Hindsight Bank

```
list_banks() -> verificar si "<group-name>-profile" ya existe.
Si no existe:
  create_bank(
    bank_id="<group-name>-profile",
    name="<group-name> Worker Profile",
    mission="<description>"
  )
```
Bank stores operational memory for this profile. Not recreated on reconfiguration.

### Step 2: Profile SOUL.md

Generate from `.agents/templates/profile-soul.md` template. Fill all `{PLACEHOLDERS}` with Phase 1-3 answers.

Placeholder mapping:

| Placeholder | Source |
|---|---|
| `{PROFILE_NAME}` | Worker profile name from Phase 3 |
| `{DOMAIN}` | Description from Phase 1 |
| `{TYPE}` | Type from Phase 1 |
| `{GROUP_NAME}` | Auto-detected group name |
| `{REPO}` | Repo from Phase 1, or "none" |
| `{DESCRIPTION}` | Description from Phase 1 |
| `{CWD}` | Worker profile cwd |
| `{BANKS}` | `<group-name>-profile` + repo bank if applicable |
| `{SKILLS_TABLE}` | Markdown table from Phase 2 skills |
| `{BANK_ID}` | `<group-name>-profile` |
| `{REPO_BANK}` | Repo bank row if repo specified |
| `{EVOLUTION_RULE}` | Evolution preference from Phase 3 step 4 |
| `{DESC_PRIORITY_RULE}` | "La descripcion de WhatsApp tiene prioridad sobre la del YAML." si el usuario activo contexto dinamico, o "" si no |

Write to `~/.hermes/profiles/<worker-name>/SOUL.md`. Overwrite only on reconfiguration with user consent.

### Step 3: whatsapp-groups.yaml

Write or update entry:

```yaml
groups:
  "<jid>":
    name: "<group-name>"
    type: "<type>"
    description: "<description>"
    repo: "<repo>"           # optional
    profile: "<worker-name>"
    skills: ["<skill1>", ...]
```

### Step 4: Master SOUL.md (DM only)

If onboarding was invoked in DM: overwrite `~/.hermes/SOUL.md` with the generated content. Keep a backup at `~/.hermes/SOUL.md.bak.<timestamp>`.

### Step 5: Commit

```
cd /opt/toolset-repo
git add infrastructure/hermes/whatsapp-groups.yaml
git add .agents/templates/profile-soul.md 2>/dev/null || true
git commit -m "feat: onboarding <group-name> -> <type> (profile: <worker-name>, bank: <group-name>-profile)"
git push origin main
```

### Step 6: Confirm

Single confirmation message:

"Perfil `<worker-name>` configurado.
Tipo: `<type>` | Repo: `<repo>` | Skills: `<skills>` | Bank: `<group-name>-profile`
SOUL.md: `~/.hermes/profiles/<worker-name>/SOUL.md`
Disponible inmediatamente."

## Reconfiguration

If group already has a mapping in whatsapp-groups.yaml:

1. Show current config in compact format.
2. "¿Reconfigurar desde cero? (si/no)"
3. If "si": restart from Phase 1. Overwrite all artifacts.
4. If "no": "¿Ajustar algo especifico? (skills / tone / description / cancelar)"
5. Targeted update: modify only the specified field. Write YAML. Do NOT recreate bank or SOUL.md.

## Error Table

| Error | Response |
|---|---|
| Repo unreachable | "`<repo>` no responde en GitHub. ¿Escribiste bien el nombre? (nombre corto, ej: toolset)" |
| Profile creation fails | "No pude crear `<profile>`. Usando 'default'. ¿OK?" |
| Skill not found | "`<skill>` no esta instalada. Skills disponibles: `<list>`. ¿Cual usar?" |
| Git push fails | "No pude pushear a GitHub. Verificare acceso de escritura. El perfil funciona localmente." |
| Hindsight unreachable | "No pude crear el bank. ¿Hindsight esta corriendo? El perfil funciona, pero sin memoria persistente." |
| YAML not found | "No encuentro whatsapp-groups.yaml. El deploy deberia crearlo en ~/.hermes/." |

## Anti-Patterns

| Don't | Do instead |
|---|---|
| Preguntar "¿estas seguro?" mas de una vez | Una confirmacion al final de Phase 3 |
| Sugerir valores por defecto sin mostrarlos | Mostrar el default entre parentesis: "(default: kilo-code)" |
| Extender el proceso mas alla de 3 fases | Si el usuario quiere mas detalle, sugerir editar SOUL.md directamente |
| Pedir confirmacion para cada skill individual | Validar en lote. Reportar errores juntos |
| Generar SOUL.md verboso con parrafos de advertencia | Template conciso. Max 40 lineas. Reglas como tabla |
