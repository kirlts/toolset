---
name: group-onboarding
description: "3-phase MECE onboarding for WhatsApp groups and DM. Creates SOUL.md, skills config, and Hindsight bank. No predefined categories — each group defines its own identity."
version: 4.0.0
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
| `~/.hermes/whatsapp-groups.yaml` | Group → profile mapping |
| `~/.hermes/profiles/<name>/SOUL.md` | Per-profile identity and rules |
| `~/.hermes/channel_aliases.json` | JID → {name, desc} resolution |
| Hindsight `create_bank()` / `list_banks()` | Memory bank per group |
| `.agents/templates/profile-soul.md` | SOUL.md template |

## Pre-Flight: DM Handler

If `/onboarding` is invoked in a DM:

1. Read current `~/.hermes/SOUL.md`. Show compact summary.
2. Ask: "¿Modificar mi personalidad base? Esto me afecta en todos los canales. (si/no)"
3. If "no" → explain what /onboarding does in groups. End.
4. If "si" → proceed to Phase 1. Profile=default, bank=hermes, no repo.

## Group Onboarding: 3-Phase Flow

No categories. No predefined types. Each phase is MECE.

### Phase 1: Identity

**Goal:** Define WHAT this profile is.

1. **Name:** Auto-detected from `channel_aliases.json`. Editable by user.
2. **Description:** "¿Que hace este perfil? Describilo en una frase."
   - Leer `channel_aliases.json` -> `whatsapp.<jid>.desc`.
   - Si hay descripcion disponible, mostrarla como sugerencia:
     "Descripcion del grupo en WhatsApp: '<desc>'. ¿La usamos o preferis escribir una nueva?"
3. **Repository:** "¿Repositorio GitHub asociado? (nombre corto, URL completa, o 'n' para ninguno)"
   - Si se provee: validar con `git ls-remote https://github.com/kirlts/<repo>.git`.
   - El repo define el `terminal.cwd` para el worker y el bank adicional.

**Edge cases:**
- **No prior context:** Preguntas frescas, sin asunciones.
- **Prior conversation context:** Usar mensajes previos como pistas para pre-llenar descripcion.
- **Single large instruction:** Extraer keywords de la instruccion y proponer descripcion.
- **Attached artifacts:** Si hay documentos adjuntos, usar markitdown para extraer dominio y proposito.

**Exit condition:** Usuario confirma nombre, descripcion, repo (opcional).

### Phase 2: Capabilities

**Goal:** Define WHAT this profile can do.

1. **Skills:** "¿Skills para este perfil? (nombres separados por coma, 'n' para ninguna, '?' para ver disponibles)"
   - If "?": list skills from `hermes skills list` and external_skills_dirs.
   - No hay defaults por tipo (no hay tipos). El usuario define desde cero.
2. **MCP servers:** "¿Servers MCP adicionales? ('n' para los defaults: hindsight + composio)"
3. **Constraints:** "¿Algo que este perfil NUNCA deba hacer?"
   - Store as negative rules in SOUL.md.

**Exit condition:** Usuario confirma skills, MCP servers, constraints.

### Phase 3: Operations

**Goal:** Define HOW this profile operates.

1. **Tone:** "¿Como debe comunicarse este perfil?" (tecnico / conversacional / minimal / custom)
2. **Worker profile:** "¿Perfil Hermes worker? (nombre, 'default' para orquestador directo, o 'nuevo' para crear uno)"
   - "default": sin delegacion, perfil orquestador.
   - "nuevo": crear con `hermes profile create <name> --clone`, configurar `terminal.cwd`.
3. **Workflows:** "¿Flujos de trabajo especificos? (ej: 'siempre correr tests antes de commit')"
4. **Evolution:** "¿Como queres que este perfil aprenda y evolucione?"
   - Hermes crea skills automaticamente por defecto. Opciones: auto / preguntar / solo explicitas / custom.

**Exit condition:** Usuario confirma todo.

## Post-Phase: Artifact Creation

### Step 1: Hindsight Bank

```
list_banks() → verificar si "<name>-profile" existe.
Si no existe:
  create_bank(bank_id="<name>-profile", name="<name>", mission="<description>")
```

### Step 2: Profile SOUL.md

Generate from `.agents/templates/profile-soul.md`. Placeholders:

| Placeholder | Source |
|---|---|
| `{PROFILE_NAME}` | Worker profile name |
| `{DOMAIN}` | Description |
| `{TYPE}` | "custom" (sin categorias) |
| `{GROUP_NAME}` | Group name |
| `{REPO}` | Repo or "none" |
| `{DESCRIPTION}` | Description |
| `{CWD}` | Worker cwd |
| `{BANKS}` | `<name>-profile` + repo bank if applicable |
| `{SKILLS_TABLE}` | Table from Phase 2 skills |
| `{BANK_ID}` | `<name>-profile` |
| `{REPO_BANK}` | Repo bank row if specified |
| `{EVOLUTION_RULE}` | Evolution preference |
| `{DESC_PRIORITY_RULE}` | Dynamic context rule |

### Step 3: whatsapp-groups.yaml

```yaml
groups:
  "<jid>":
    name: "<group-name>"
    description: "<description>"
    repo: "<repo>"
    profile: "<profile>"
    skills: ["<skill1>", ...]
```

### Step 4: Master SOUL.md (DM only)

Overwrite `~/.hermes/SOUL.md`. Backup en `~/.hermes/SOUL.md.bak.<timestamp>`.

### Step 5: Commit

```
cd /opt/toolset-repo
git add infrastructure/hermes/whatsapp-groups.yaml
git commit -m "feat: onboarding <group-name> (profile: <profile>, bank: <name>-profile)"
git push origin main
```

### Step 6: Confirm

"Perfil `<profile>` configurado.
Descripcion: `<description>` | Repo: `<repo>` | Skills: `<skills>` | Bank: `<name>-profile`
Disponible inmediatamente."

## Reconfiguration

1. Show current config.
2. "¿Reconfigurar desde cero? (si/no)"
3. Si: restart Phase 1. Sobrescribir todo.
4. No: "¿Ajustar algo especifico? (skills / tone / description / cancelar)"

## Error Table

| Error | Response |
|---|---|
| Repo unreachable | "`<repo>` no responde en GitHub. ¿Nombre corto? (ej: toolset)" |
| Profile creation fails | "No pude crear `<profile>`. Usando 'default'. ¿OK?" |
| Skill not found | "`<skill>` no instalada. Skills disponibles: `<list>`" |
| Git push fails | "No pude pushear. Worker funciona, cambios locales." |
| Hindsight unreachable | "No pude crear el bank. Perfil funciona sin memoria persistente." |

## Anti-Patterns

| Don't | Do instead |
|---|---|
| Preguntar "¿estas seguro?" mas de una vez | Una confirmacion al final de Phase 3 |
| Asumir que el usuario quiere un tipo de perfil | No hay tipos — el usuario define todo |
| Skills pre-seleccionadas por categoria | Skills vacias por defecto. El usuario elige |
| Extender el proceso mas alla de 3 fases | Editar SOUL.md directamente si se necesita mas |
| Preguntas condicionales por tipo | Mismas preguntas para todos los grupos |
