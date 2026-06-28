---
name: group-onboarding
description: "Domain-abstract setup for WhatsApp groups. Hermes can be whatever you want — not just code repos."
version: 2.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [onboarding, setup, whatsapp, groups]
    triggers: ["/onboarding"]
---

# WhatsApp Group Onboarding — Domain-Abstract

## When Activated

When a user sends `/onboarding` in a WhatsApp group where Hermes is a member.

## Prerequisites

- `~/.hermes/whatsapp-groups.yaml` exists (created by deploy.sh)
- Hindsight MCP tools available (`create_bank`, `list_banks`)
- Hermes profiles exist (created by deploy.sh or manually)

## Onboarding Flow

### Step 1: Detect and check existing config

1. Get group JID from session origin (`remoteJid`)
2. Get human-readable name from `~/.hermes/channel_aliases.json`
3. Check if JID already exists in `~/.hermes/whatsapp-groups.yaml`
   - **If found**: show current config. Ask "¿Reconfigurar? (si/no)"
   - **If not found**: proceed as new group

### Step 2: Choose group type

Preguntar: "¿Qué querés que sea este grupo?"

| Opción | type | Significado |
|---|---|---|
| 💻 Coding | `coding` | Repositorio GitHub + perfil worker + Kilo CLI |
| 🔬 Research | `research` | Investigación profunda + búsqueda + análisis |
| 👤 Personal | `personal` | Orquestador maestro (sin delegación) |
| ⚙️ Custom | `custom` | Lo que vos quieras — describilo libremente |

### Step 3: Follow-up questions by type

#### If `coding`:
a. "¿Qué repositorio GitHub? (nombre corto, ej: toolset)"
   → Validar: `git ls-remote https://github.com/kirlts/<repo>.git`
b. "¿Perfil worker? (enter para 'default')"
   → Validar: `hermes profile list | grep <profile>` si no es default
c. "¿Skills extra? (separadas por coma, ej: kilo-code,github-pr-workflow, o 'n')"
   → Validar cada skill si se especifican
d. "¿Descripción? (una línea sobre qué hace este grupo)"

#### If `research`:
a. "¿Área de investigación? (ej: IA, ciberseguridad, música docta)"
   → Campo libre, sin validación
b. "¿Repositorio asociado? (opcional, enter para ninguno)"
   → Si se provee, validar con `git ls-remote`
c. "¿Perfil worker? (enter para 'default')"
d. "¿Skills extra? (separadas por coma o 'n')"
e. "¿Descripción?"

#### If `personal`:
a. "¿Descripción? (una línea sobre para qué usás este grupo)"

#### If `custom`:
a. "¿Descripción? (describí libremente qué querés que Hermes sea en este grupo)"
b. "¿Perfil worker? (enter para 'default')"
c. "¿Skills extra? (separadas por coma o 'n')"

### Step 4: Create Hindsight bank

Para TODOS los tipos, crear bank programáticamente vía MCP:

```
list_banks() → verificar si "<group-name>-profile" ya existe
Si no existe:
  create_bank(
    bank_id="<group-name>-profile",
    name="<group-name> Worker Profile",
    mission="<description proporcionada por el usuario>"
  )
```

Si el bank ya existe (reconfiguración), no recrear — preserva contexto histórico.

### Step 5: Initialize per-profile identity (coding + custom types)

Si el grupo usa un perfil worker específico (no 'default'):

```
# Crear SOUL.md personalizado para el perfil si no existe
cat > ~/.hermes/profiles/<profile>/SOUL.md << 'SOULEOF'
# <profile> — Worker Profile

Sos el perfil worker para el grupo WhatsApp "<group-name>".
Tu propósito: <description>

## Contexto
<description proporcionada por el usuario>

## Repositorio
<repo> (si aplica)

## Reglas
- Usá recall(bank="<group-name>-profile") al iniciar cada sesión
- Usá retain(bank="<group-name>-profile") al finalizar
- Reportá resultados al orquestador vía kanban_complete()

SOULEOF
```

Si SOUL.md ya existe, no sobrescribir — preservar personalización previa.

### Step 6: Write mapping

Escribir entrada en `~/.hermes/whatsapp-groups.yaml`:

```yaml
groups:
  "<jid>":
    name: "<group-name>"
    type: "<type>"
    description: "<user description>"
    repo: "<repo>"          # solo si aplica
    profile: "<profile>"
    skills: ["<skill1>", "<skill2>"]  # solo si se especificaron
```

### Step 7: Commit and push

```
cd /opt/toolset-repo
git add infrastructure/hermes/whatsapp-groups.yaml
git add infrastructure/hermes/banks/ 2>/dev/null || true
git commit -m "feat: onboarding group <group-name> → <type> (bank: <group-name>-profile)"
git push origin main
```

### Step 8: Confirm

Responder con resumen:

"✅ Grupo '<group-name>'
   Tipo: <type>
   <si es coding/research con repo>: Repo: <repo>
   Perfil: <profile>
   Bank: '<group-name>-profile' creado
   <si skills>: Skills: <skills>
   Disponible ahora mismo."

## Reconfiguration

If the group was previously configured, show the OLD values before asking each
question. On confirmation:
- Overwrite YAML entry
- Bank is NOT recreated (preserves existing context)
- SOUL.md is NOT overwritten (preserves customizations)

## Error Handling

| Error | Response |
|---|---|
| Repo doesn't exist | "❌ <repo> no existe en GitHub. ¿Escribiste bien el nombre?" |
| Profile doesn't exist | "❌ <profile> no existe. Creá el perfil primero o usá 'default'." |
| Skill not installed | "❌ <skill> no está en <profile>. Instalala primero o salteala." |
| Git push fails | "❌ No pude pushear. ¿Tengo acceso de escritura al repo toolset?" |
| YAML file missing | "❌ No encuentro whatsapp-groups.yaml. El deploy debería crearlo." |
| Hindsight unreachable | "❌ No pude crear el bank. ¿Hindsight está corriendo? Intentá de nuevo." |
