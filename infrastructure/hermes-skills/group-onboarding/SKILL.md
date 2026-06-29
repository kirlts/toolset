---
name: group-onboarding
description: "Context-aware onboarding for WhatsApp groups and DM. Creates SOUL.md, skills config, and Hindsight bank. No predefined categories — each group defines its own identity. Optional Phase 0 extracts context from artifacts, URLs, voice messages, or conversation history."
version: 4.2.0
platforms: [linux]
metadata:
  hermes:
    tags: [onboarding, setup, whatsapp, groups, soul]
    triggers: ["/onboarding"]
---

# Group Onboarding — Context-Aware 3-Phase MECE

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
4. If "si" → proceed to Phase 0. Profile=default, bank=hermes, no repo.

## Group Onboarding: Flow

No categories. No predefined types. Phases 1-3 are MECE.
**Phase 0 is optional**: executes only when context exists (artifacts, conversation history, attached documents, voice messages, URLs).

---

### Phase 0: Context Ingestion (optional)

**Goal:** Extract onboarding-relevant information from any available context. Only runs when the user provides context alongside `/onboarding` (document, voice message, URL, prior conversation, or explicit instructions like "en base a lo que conversamos, haz /onboarding").

#### Context types (any, the harness resolves them):

| Source | Resolution | Extracted by |
|---|---|---|
| Attached document (PDF, DOCX, TXT, image, audio) | `markitdown` | Hermes infra, not this skill |
| URL | Agent fetches and extracts content | Agent's tool-use capability |
| Voice message | STT transcription (Groq Whisper) then MarkItDown if needed | Hermes STT pipeline |
| Prior conversation in same group | Session history from Hindsight bank | `recall(bank=<group-name>-profile)` |
| User instructions in the `/onboarding` command itself | Parsed directly | This skill reads the message text |

#### Extraction algorithm:

1. **Collect context.** Gather all available sources. If none exist, skip Phase 0 entirely and proceed to Phase 1.
2. **Infer identity.** From the context, the agent extracts:
   - Profile name (suggested from group name or context)
   - Description (what this profile does, in one sentence)
   - Repository (GitHub repo name or URL, or "none")
3. **Infer capabilities.** From the context, the agent extracts:
   - Skills needed (names from `hermes skills list`)
   - MCP servers beyond defaults (hindsight + composio)
   - Constraints (what this profile MUST NOT do)
4. **Infer operations.** From the context, the agent extracts:
   - Communication tone (technical / conversational / minimal / custom)
   - Worker profile requirements (new or default)
   - Workflow preferences
   - Evolution mode (auto / preguntar / solo explicito / custom)
   - Whether the user expects an override of default governance rules (e.g., "este perfil puede editar archivos directamente aunque el repo tenga .agents/")
   - **Delegation criteria.** If the repo has `.agents/`, infer: "tareas multi-step sobre el repo (Kilo CLI, Kairós governance, deploy, verification) se delegan a un sub-agente via Kanban. Consultas rápidas y decisiones se responden directo." If no repo or no `.agents/`, leave as gap.
5. **Detect gaps.** Compare what was inferred against what is required for a complete onboarding. Classify each gap:

   | Gap type | Example | Action |
   |---|---|---|
   | Missing identity | No repo could be inferred | Ask user |
   | Ambiguous capability | Two possible skills, context supports both | Ask user to choose |
   | Missing constraint | No restrictions found | Offer default: "sin restricciones adicionales" |
   | Unclear operation | Tone not inferrable | Ask user |

6. **Present human review.** Show the user a complete summary of everything inferred:

   ```
   Resumen de lo que entendi del contexto:
   
   IDENTIDAD
     Nombre sugerido: <name>
     Descripcion: <description>
     Repositorio: <repo>
   
   CAPACIDADES
     Skills: <skills>
     MCP adicionales: <mcp>
     Restricciones: <constraints>
   
   OPERACION
     Tono: <tone>
     Worker profile: <profile>
     Workflows: <workflows>
     Evolucion: <evolution>
     Delegacion: <delegation>
     Override de reglas default: <yes/no/details>
   
   Informacion faltante:
     - <gap 1>
     - <gap 2>
   
   ¿Es correcto? Si/No (corregir)
   ```

7. **If user confirms:** Store inferred values. Proceed to Phase 1, but skip every question whose answer was already inferred and confirmed.
8. **If user corrects:** Apply corrections. Repeat the summary with corrections applied. Proceed.
9. **If gaps exist:** Enter Phase 1 normally. The questions that correspond to gaps are asked first; questions already answered are skipped.

---

### Phase 1: Identity

**Goal:** Define WHAT this profile is.
**Scope:** Only ask questions whose answers were NOT inferred in Phase 0.

1. **Name:** Auto-detected from `channel_aliases.json`. Editable by user.
2. **Description:** "¿Que hace este perfil? Describilo en una frase."
   - Leer `channel_aliases.json` -> `whatsapp.<jid>.desc`.
   - Si hay descripcion disponible, mostrarla como sugerencia:
     "Descripcion del grupo en WhatsApp: '<desc>'. ¿La usamos o preferis escribir una nueva?"
3. **Repository:** "¿Repositorio GitHub asociado? (nombre corto, URL completa, o 'n' para ninguno)"
   - Si se provee: validar con `git ls-remote https://github.com/kirlts/<repo>.git`.
   - El repo define el `terminal.cwd` para el worker y el bank adicional.
   - **Registrar en cloned-repos.yaml:**
     ```
     cd /opt/toolset-repo
     # Add entry with yq if available, otherwise append raw YAML
     if command -v yq &>/dev/null; then
       yq -i '.repos.<name>.url = "https://github.com/kirlts/<name>.git"' \
         infrastructure/hermes/cloned-repos.yaml
       yq -i '.repos.<name>.path = "/opt/<name>"' \
         infrastructure/hermes/cloned-repos.yaml
       yq -i '.repos.<name>.type = "cloned"' \
         infrastructure/hermes/cloned-repos.yaml
       yq -i '.repos.<name>.sync = "cron"' \
         infrastructure/hermes/cloned-repos.yaml
       yq -i '.repos.<name>.sandbox = "optional"' \
         infrastructure/hermes/cloned-repos.yaml
     else
       # Fallback: append raw YAML block
       cat >> infrastructure/hermes/cloned-repos.yaml << YAML
       <name>:
         url: https://github.com/kirlts/<name>.git
         path: /opt/<name>
         type: cloned
         sync: cron
         sandbox: optional
     YAML
     fi
     git add infrastructure/hermes/cloned-repos.yaml
     git commit -m "feat: register <name> repo for <group-name> via onboarding"
     git push origin main
     ```

**Exit condition:** Usuario confirma nombre, descripcion, repo (opcional).

### Phase 2: Capabilities

**Goal:** Define WHAT this profile can do.
**Scope:** Only ask questions whose answers were NOT inferred in Phase 0.

1. **Skills:** "¿Skills para este perfil? (nombres separados por coma, 'n' para ninguna, '?' para ver disponibles)"
   - If "?": list skills from `hermes skills list` and external_skills_dirs.
   - No hay defaults por tipo (no hay tipos). El usuario define desde cero.
2. **MCP servers:** "¿Servers MCP adicionales? ('n' para los defaults: hindsight + composio)"
3. **Constraints:** "¿Algo que este perfil NUNCA deba hacer?"
   - Store as negative rules in SOUL.md.
   - If Phase 0 detected an override expectation (e.g., "este perfil puede editar archivos directamente"), present it explicitly:
     "Segun el contexto, este perfil deberia poder editar archivos directamente aunque el repositorio tenga reglas de gobernanza. ¿Confirmas esta excepcion?"

**Exit condition:** Usuario confirma skills, MCP servers, constraints.

### Phase 3: Operations

**Goal:** Define HOW this profile operates.
**Scope:** Only ask questions whose answers were NOT inferred in Phase 0.

1. **Tone:** "¿Como debe comunicarse este perfil?" (tecnico / conversacional / minimal / custom)
2. **Worker profile:** "¿Perfil Hermes worker? (nombre, 'default' para orquestador directo, o 'nuevo' para crear uno)"
   - "default": sin delegacion, perfil orquestador.
   - "nuevo": crear con `hermes profile create <name> --clone`, configurar `terminal.cwd`.
3. **Workflows:** "¿Flujos de trabajo especificos? (ej: 'siempre correr tests antes de commit')"
4. **Evolution:** "¿Como queres que este perfil aprenda y evolucione?"
   - Hermes crea skills automaticamente por defecto. Opciones: auto / preguntar / solo explicitas / custom.
5. **Delegation:** "¿En qué casos tendria sentido delegar a un sub-agente que ejecute independientemente y reporte despues? (o 'n' para nunca delegar)"
   - Si Phase 0 infirio criterio con repos `.agents/`, presentarlo como sugerencia y preguntar si confirma.
   - El criterio queda documentado en el SOUL.md del perfil como una regla operativa, no como un bloqueo.
   - Ejemplo inferido: "tareas multi-step sobre el repo (Kilo CLI, Kairós, deploy, verification) se delegan. Consultas rapidas y decisiones se responden directo."
   - Si el usuario no tiene opinion clara, default: "El orquestador decide segun la complejidad de cada solicitud."

**Exit condition:** Usuario confirma todo.

## Post-Phase: Artifact Creation

### Step 1: Hindsight Bank

```
list_banks() → verificar si "<name>-profile" existe.
Si no existe:
  create_bank(bank_id="<name>-profile", name="<name>", mission="<description>")
```

### Step 2: Profile SOUL.md

Generate from `.agents/templates/profile-soul.md` (if the template exists) or generate programmatically. The template/source already includes:
- **CONSULT-01: Si el perfil tiene repositorio asociado, la fuente de consulta PRIMARIA debe ser la filesystem del repo (con read_file/search_files). Hindsight queda como fuente SECUNDARIA (indice de busqueda semantica). El buffer es siempre write-only. Esto evita respuestas genericas por banco Hindsight vacio.**
- ROUTE-03: the profile operates directly (no orchestrator reporting)
- ROUTE-03a: mandatory cross-profile delegation for out-of-scope tasks
- ROUTE-04: Kilo CLI for repo operations (if a repo exists)
- Memory cycle (recall/retain tied to profile banks)

Placeholders:

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
    repo: "<repo>"          # optional: omit if no repo
    profile: "<profile>"
    scope: "<scope>"        # optional: conversation_kb, infrastructure, research, etc.
```

The bridge reads `profile` and `scope` to inject the `[ROUTING]` block.
The LLM derives banks by convention: `<profile>-profile` + repo bank if applicable.
No `banks:` field needed — it's derived deterministically.

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
