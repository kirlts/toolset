---
name: group-onboarding
description: "Interactive setup for new WhatsApp groups. Maps a group JID to a repo + worker profile via whatsapp-groups.yaml."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [onboarding, setup, whatsapp, groups]
    triggers: ["/onboarding"]
---

# WhatsApp Group Onboarding

## When Activated

When a user sends `/onboarding` in a WhatsApp group where Hermes is a member.

## Prerequisites

- `~/.hermes/whatsapp-groups.yaml` exists (created by deploy.sh)
- Hindsight bank for the repo exists (or will be created)
- Worker profile for the repo exists (or will be created)

## Onboarding Flow

1. Detect group name from `~/.hermes/channel_aliases.json` (JID → human name)
2. Check if JID already exists in `~/.hermes/whatsapp-groups.yaml`
   - If found: show current mapping. Ask: "Reconfigurar? (s/n)"
   - If not found: proceed as new group
3. If user confirms reconfig OR this is a new group:
   a. Ask user: "¿Qué repositorio GitHub? (nombre corto, ej: toolset)"
   b. Validate: `git ls-remote https://github.com/kirlts/<repo>.git` responde
   c. Ask user: "¿Qué perfil worker usar? (ej: toolset-worker)"
   d. Validate: `hermes profile list | grep <profile>` existe
   e. Ask user: "¿Skills extra? (separadas por coma, ej: kilo-code,github-pr-workflow)"
   f. Validate each skill: `hermes -p <profile> skills list | grep <skill>` existe
4. **Create Hindsight bank programmatically** via MCP:
   ```
   create_bank(
     bank_id="<group-name>-profile",
     name="<group-name> Worker Profile",
     mission="Perfil worker para el grupo WhatsApp <group-name> — repo <repo>"
   )
   ```
   Solo si el bank no existe ya. Si existe, no recrear (preserva contexto).
5. Write updated mapping to whatsapp-groups.yaml:

   ```yaml
   groups:
     "<jid>":
       name: "<group-name>"
       repo: "<repo>"
       profile: "<profile>"
       skills: ["<skill1>", "<skill2>"]
   ```

6. Commit and push changes to toolset repo:
   ```
   cd /opt/toolset-repo
   git add infrastructure/hermes/whatsapp-groups.yaml
   git commit -m "feat: onboarding group <group-name> → repo <repo> (bank: <group-name>-profile)"
   git push origin main
   ```
7. Confirm to user: "✅ Grupo '<group-name>' configurado → repo '<repo>' → perfil '<profile>'. Bank '<group-name>-profile' creado. Disponible en segundos tras deploy."

## Reconfiguration

If the group was previously configured, show the OLD values and step through
each field (repo, profile, skills) with the same validations as a new setup.
Overwrite the entire entry on confirmation. The bank is NOT recreated — it preserves existing context.

## Reconfiguration

If the group was previously configured, show the OLD values and step through
each field (repo, profile, skills) with the same validations as a new setup.
Overwrite the entire entry on confirmation.

## Error Handling

| Error | Response |
|---|---|
| Repo doesn't exist | "❌ El repositorio <repo> no existe en GitHub. Verifica el nombre." |
| Profile doesn't exist | "❌ El perfil <profile> no está instalado. Crea el perfil primero." |
| Skill doesn't exist | "❌ La skill <skill> no está instalada en el perfil <profile>." |
| Git push fails | "❌ No pude pushear el cambio. ¿Tengo acceso de escritura al repo?" |
| YAML file missing | "❌ No encuentro whatsapp-groups.yaml. El deploy debería crearlo." |
