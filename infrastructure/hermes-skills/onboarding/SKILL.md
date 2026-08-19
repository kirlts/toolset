---
name: onboarding
version: 5.1.0
platforms: [linux]
metadata:
  hermes:
    tags: [onboarding, setup, whatsapp, groups, soul, tts]
    triggers: ["/onboarding"]
---

# Group Onboarding — Context-Aware 3-Phase MECE

## Activation Context

| Context | Behavior |
|---|---|
| WhatsApp group | Onboarding for that group. Creates/updates group config + bank + profile SOUL.md. JID auto-detected from message source. |
| WhatsApp group (remote) | Remote onboarding — configure a target group from a DIFFERENT WhatsApp group. JID must be discovered via bridge or provided by user. Useful for pre-configuration before Hermes joins, or to avoid polluting the target group. See "Remote Onboarding" section. |
| WhatsApp DM | Master orchestrator SOUL.md modification. Requires explicit user confirmation. |
| WebUI / CLI | Not supported. Redirect to WhatsApp group or DM. |

## Files Involved

| File | Purpose |
|---|---|
| `~/.hermes/whatsapp-groups.yaml` | Group → profile mapping |
| `~/.hermes/profiles/<name>/SOUL.md` | Per-profile identity and rules |
| `~/.hermes/channel_aliases.json` | JID → {name, desc} resolution |
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

## Remote Onboarding (from a different group)

**Trigger:** The user requests onboarding for a WhatsApp group from a DIFFERENT group (e.g., configuring "Equipo X" from the Toolset group). Motivation: avoid polluting the target group with configuration messages, or pre-configure before Hermes joins.

**Key differences from standard group onboarding:**

| Aspect | Standard | Remote |
|---|---|---|
| JID detection | Auto-extracted from message source | User MUST provide the JID, OR bridge must have it |
| Channel alias resolution | Automatic via bridge | May need bridge restart + manual sync |
| Onboarding messages | Go to the target group | Go to the CURRENT group (where the user is talking) |
| Post-onboarding | Immediate availability | Group appears in config; active when Hermes joins |

**Pre-flight:**

1. Determine the target group JID (`\d+@g.us`). Sources (in priority order):
   - **Already in bridge directory**: run `populate-channel-aliases.sh` → check `channel_aliases.json` → if the JID appears, name/desc are resolved
   - **Bridge knows the group but directory hasn't synced**: query bridge API directly: `curl -s http://127.0.0.1:3000/chat/<jid>` — returns name, desc, participants. Then re-run `populate-channel-aliases.sh` which reads the bridge API and writes channel_aliases.json
   - **User provides the JID**: from WhatsApp group info → "Invitar via link" → the link contains the group JID. Or a group admin shares it
   - **Fallback**: ask the user to add Hermes to the group first, wait for bridge sync, then proceed

2. **Bridge discovery pitfalls:**
   - New groups may not appear in `channel_directory.json` immediately after adding Hermes — the bridge needs time to process the invite notification
   - If the bridge had connection issues (503 errors, reconnections), the invite notification may be lost entirely — the user may need to re-add Hermes or someone must send a message in the group
   - After adding Hermes, `channel_directory.json` may show the group's JID even before `channel_aliases.json` has its name — re-run `populate-channel-aliases.sh` after the bridge has processed the invite
   - If the bridge was restarted (e.g., killed by HUP), the gateway respawns it automatically with the correct env vars — the new bridge reconnects and eventually receives pending group data

3. **Allowlist check (CRITICAL for team groups):**
   - All group members must be in `WHATSAPP_ALLOWED_USERS` (bridge env var, in `~/.hermes/.env` and synced via deploy.sh)
   - The gateway also has a separate filter at `config.yaml` → `whatsapp.allowed_users`
   - Both are TWO INDEPENDENT LAYERS — a user must pass BOTH for Hermes to process their messages
   - If a team member's messages are ignored, check both allowlists
   - Current bridge allowlist value: `cat /proc/<bridge_pid>/environ | tr '\0' '\n' | grep WHATSAPP_ALLOWED_USERS`
   - Current gateway allowlist: `grep -A5 'whatsapp:' ~/.hermes/config.yaml | grep allowed_users`

4. **Without JID?** Cannot proceed — the JID is required for `whatsapp-groups.yaml` routing. Without it, messages from the target group can't be matched to the correct profile.

**Phase flow (Phases 0-4):** Same as standard. Differences:
- Phase 1 name/description come from user input (or channel_aliases if bridge synced)
- The JID is passed explicitly — no auto-detection from message source
- Onboarding response is sent to the CURRENT group (the configurator), not the target

**Post-onboarding artifact creation:** Same as standard (Steps 1-6). The `whatsapp-groups.yaml` entry uses the provided JID. After commit + deploy:
- The group config is live in the repo and deployed
- When Hermes eventually joins or receives messages from the group, routing works immediately
- `channel_aliases.json` fills in name/desc on the next cron sync (every 10 min)

**Pitfall:** If the provided JID is wrong, routing silently fails — the profile never activates for the target group. Always verify before writing `whatsapp-groups.yaml`. If unsure, ask the user to confirm via the group invite link.

### Pre-Flight: Channel Alias Resolution

Before Phase 1, verify that the group JID exists in `channel_aliases.json`.

1. Read `~/.hermes/channel_aliases.json` → check if the source JID (`<jid>@g.us`) is present.
2. If **found**: skip to Phase 1 — name and description are resolved.
3. If **NOT found**: locate and run the bridge-sync script before asking the user:
   - Script location (try in order): `workspace/toolset/infrastructure/hermes/scripts/populate-channel-aliases.sh`, or search filesystem for `populate-channel-aliases.sh`.
   - The script queries the WhatsApp bridge for group names/descriptions and writes `channel_aliases.json`.
   - Prerequisites: the bridge service must be running (check via `curl -s --max-time 3 http://127.0.0.1:3000/health`).
   - After successful run, re-read `channel_aliases.json` — the JID should now be present.
4. If the script doesn't exist or fails: fall back to asking the user for name and description directly in Phase 1.

**Verification:** Before running the script, confirm the bridge is responding:
   `curl -s --max-time 3 http://127.0.0.1:3000/health`
   And verify `channel_directory.json` exists at `~/.hermes/channel_directory.json`.
   Without the directory file, the script exits silently with no output — and the agent would be left hanging for data.

**Pitfall:** The script exits 0 even when `channel_directory.json` is missing, producing no aliases and no error message. Always check it exists before running. If it's absent, explain to the user that the bridge hasn't synced group data yet (bridge may be recently started or the group was just created).

This avoids asking the user for information the bridge already has.

---

### Remote Onboarding (from a different group)

**Trigger:** The onboarding `/onboarding` request comes from a DIFFERENT WhatsApp group than the target group (e.g., configuring "Equipo X" from the Toolset group).

**Key differences from standard group onboarding:**

| Aspect | Standard | Remote |
|---|---|---|
| JID detection | Auto-extracted from message source | User MUST provide the JID manually |
| channel_aliases.json | Resolved from bridge data automatically | Bridge may not yet know the group — name/desc come from user |
| Phase 0-4 flow | Same questions | Same questions, but user provides group name + JID instead of auto-detection |
| Post-onboarding | Available immediately | Group appears in config but has no active messages until Hermes joins |

**Pre-flight:**

1. User must provide the target group's JID (format `\d+@g.us`). Sources:
   - WhatsApp group info → "Invitar via link" → the link contains the JID
   - A group admin can share it
   - WhatsApp Web debug mode shows it
2. If the user doesn't have the JID: suggest they add Hermes to the group first, then `populate-channel-aliases.sh` can sync it.
3. The bridge may not yet have the group in `channel_directory.json`. If it does (e.g., group existed but Hermes wasn't in it, or the invite was just sent), run `populate-channel-aliases.sh` to sync. If not, proceed with user-provided name/desc.
4. **Proceed without JID?** No — the JID is required for `whatsapp-groups.yaml` routing. Without it, the group's messages cannot be routed to the correct profile.

**Phase flow:** Same as standard Phases 1-4 + Post-Phase artifact creation. The only differences:
- Phase 1's name/description are populated from user input (or from channel_aliases if the bridge synced)
- The JID is used explicitly in the whatsapp-groups.yaml entry
- The onboarding response goes to the CURRENT group, not the target group (target group has no Hermes yet)

**Bridge sync after onboarding:** Once Hermes is added to the target group, the bridge eventually receives the group notification → `channel_directory.json` updates → `populate-channel-aliases.sh` picks up the group info on next cron run (every 10 min). No manual action needed.

**Pitfall:** If the JID is wrong, routing silently fails — messages from the target group won't match the configured profile. Verify the JID by checking the group invite link or having the user confirm before writing `whatsapp-groups.yaml`.

### Phase 0: Context Ingestion (optional)

**Goal:** Extract onboarding-relevant information from any available context. Only runs when the user provides context alongside `/onboarding` (document, voice message, URL, prior conversation, or explicit instructions like "en base a lo que conversamos, haz /onboarding").

#### Context types (any, the harness resolves them):

| Source | Resolution | Extracted by |
|---|---|---|
| Attached document (PDF, DOCX, TXT, image, audio) | `markitdown` | Hermes infra, not this skill |
| URL | Agent fetches and extracts content | Agent's tool-use capability |
| Voice message | STT transcription (Groq Whisper) then MarkItDown if needed | Hermes STT pipeline |
| User instructions in the `/onboarding` command itself | Parsed directly | This skill reads the message text |

#### Extraction algorithm:

1. **Collect context.** Gather all available sources. If none exist, skip Phase 0 entirely and proceed to Phase 1.
2. **Infer identity.** From the context, the agent extracts:
   - Profile name (suggested from group name or context)
   - Description (what this profile does, in one sentence)
   - Repository (GitHub repo name or URL, or "none")
3. **Infer capabilities.** From the context, the agent extracts:
   - Skills needed (names from `hermes skills list`)
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

### Phase 4: Text-to-Speech

**Goal:** Configure whether Hermes sends voice messages in this group.

1. **Enable TTS:** "¿Quieres que Hermes te envíe mensajes de voz (text-to-speech) en este grupo? (si/no)"
   - TTS global está habilitado en `config.yaml` (provider: edge, voz: es-CL-LorenzoNeural).
   - Esta fase configura si este grupo específico recibe audio.
2. **Mode:** Si el usuario dijo "si": "¿En qué momentos quieres recibir audio? (siempre / solo respuestas largas / cuando pidas explícitamente)"
   - `always`: cada mensaje de Hermes se envía como audio + texto.
   - `responses`: solo mensajes de más de ~200 palabras.
   - `on-demand`: solo cuando el usuario lo pide ("dímelo en audio").

**Exit condition:** Usuario confirma preferencia TTS.

## Post-Phase: Artifact Creation

### Step 2: Profile SOUL.md

Generate from `.agents/templates/profile-soul.md` (if the template exists) or generate programmatically. The template/source already includes:
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
    tts:                    # Phase 4: optional, omit if TTS disabled
      enabled: true
      mode: "always"        # always | responses | on-demand
```

The bridge reads `profile` and `scope` to inject the `=== PROFILE ACTIVATION ===` block.
The LLM derives banks by convention: `<profile>-profile` + repo bank if applicable.
The `tts` block controls per-group voice message delivery. If absent or `enabled: false`, no audio.
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

### Step 7: Post-Onboarding — Bitácora Management

Profile workloads often involve maintaining a Google Docs bitácora (see WF-01 in SOUL.md workflows). For detailed formatting rules, tool-selection guidance, pending-item criteria, and known pitfalls, load the companion reference:

`references/bitacora-management.md`

## Reconfiguration

When `/onboarding` is invoked in a group that ALREADY has a profile in `whatsapp-groups.yaml`:

1. Show current config summary (name, profile, repo, skills, TTS status).
2. Offer two options:
   - **(1) "Actualizar configuración"** — detecta qué features nuevas están disponibles vs lo que ya tiene el grupo (ej: TTS no configurado, nuevos campos en el schema). Solo ejecuta las fases correspondientes a features faltantes. Si el grupo ya tiene TTS configurado, se ofrece cambiar la configuración.
3. If the user chooses (1) and the only new feature is TTS: "Este grupo no tiene TTS configurado. ¿Quieres activarlo ahora? (si/no)" → ejecutar Phase 4 únicamente.
4. If the user chooses (2): full flow, el bank existente se reutiliza (`create_bank` es idempotente).

## Error Table

| Error | Response |
|---|---|
| Repo unreachable | "`<repo>` no responde en GitHub. ¿Nombre corto? (ej: toolset)" |
| Profile creation fails | "No pude crear `<profile>`. Usando 'default'. ¿OK?" |
| Skill not found | "`<skill>` no instalada. Skills disponibles: `<list>`" |
| Git push fails | "No pude pushear. Worker funciona, cambios locales." |

## Anti-Patterns

| Don't | Do instead |
|---|---|
| Preguntar "¿estas seguro?" mas de una vez | Una confirmacion al final de Phase 3 |
| Asumir que el usuario quiere un tipo de perfil | No hay tipos — el usuario define todo |
| Skills pre-seleccionadas por categoria | Skills vacias por defecto. El usuario elige |
| Extender el proceso mas alla de 3 fases | Editar SOUL.md directamente si se necesita mas |
| Preguntas condicionales por tipo | Mismas preguntas para todos los grupos |

## Reference Files

| File | Content |
|---|---|
| `references/repo-context-extraction.md` | Repo analysis via Kilo CLI for Phase 0 context ingestion |
| `references/remote-onboarding-bridge-discovery.md` | Bridge discovery sequence, API endpoints, pitfalls, and restore commands for remote onboarding |