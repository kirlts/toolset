---
name: tenant-grupo
description: "Onboarding para grupos WhatsApp de tenants Hermes. Crea configuracion de grupo, SOUL.md dentro del perfil del tenant, y actualiza whatsapp-groups.yaml del tenant. Usa memoria Holographic (no Hindsight). Sin bancos, sin Kanban, sin creacion de perfiles Hermes."
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [whatsapp, tenant, group-configuration, onboarding]
---

# Tenant Group Configuration (`/grupo`)

Onboarding simplificado para grupos WhatsApp dentro de un tenant Hermes.
A diferencia del `/onboarding` del orquestador principal, NO crea bancos Hindsight,
NO crea perfiles Hermes, y NO usa Kanban. Opera exclusivamente dentro del perfil del tenant.

## Activacion

Se activa cuando un tenant recibe el comando `/grupo` en un chat de WhatsApp.
Solo responde si el remitente esta en `WHATSAPP_ALLOWED_USERS`.

## Flujo — 3 fases MECE

### Fase 0: Contexto del grupo

1. Leer `~/.hermes/profiles/<tenant>/whatsapp-groups.yaml` si existe.
2. Obtener el JID del grupo desde el contexto del mensaje.
3. Obtener la descripcion del grupo desde `channel_aliases.json` (cron de populate cada 10 min).
4. Si el grupo ya esta configurado, preguntar si desea reconfigurar.

### Fase 1: Identidad del grupo

Preguntar:

1. **Nombre del grupo:** Nombre descriptivo para este grupo.
2. **Descripcion operativa:** Que hace el tenant en este grupo.
3. **Repositorios asociados:** Subconjunto de los repos del tenant que aplican a este grupo.
   Si no se especifica, hereda todos los repos del tenant.
4. **Alcance (scope):** Que tipo de operaciones realiza en este grupo:
   - `code`: desarrollo, git, PRs
   - `chat`: conversacion libre
   - `research`: investigacion y documentacion
   - `custom`: el tenant define su propio scope

### Fase 2: Capacidades

Preguntar:

1. **Herramientas adicionales:** El tenant hereda los toolsets de su config.yaml.
   ¿Necesita habilitar toolsets extra para este grupo? (web, cronjob, etc.)
2. **Notificaciones:** ¿Debe notificar eventos de CI/CD o git en este grupo?
3. **Auto-respuesta:** ¿Responde automaticamente a todos los mensajes o solo cuando se le menciona?

### Fase 3: Operaciones

Preguntar:

1. **Horario activo:** ¿Responde 24/7 o solo en ciertos horarios?
2. **Prioridad:** Alta (responde inmediato), normal, baja (responde cuando puede).
3. **TTS (Text-to-Speech):** ¿Activar audio para respuestas largas (>200 palabras)?
   - Si esta activado a nivel tenant, preguntar si este grupo quiere TTS.
   - Si no, ofrecer activarlo solo para este grupo.
   - Voz: `es-CL-LorenzoNeural` (masculina) o `es-CL-CatalinaNeural` (femenina).
   - Modo: `responses` (respuestas densas), `on-demand` (cuando se pide con "audio").
   - Formato YAML en `whatsapp-groups.yaml`:
     ```yaml
     tts:
       enabled: true
       mode: "responses"
       voice: "es-CL-LorenzoNeural"
     ```

## Implementacion

Al completar las 3 fases, el tenant:

1. **Crea/actualiza SOUL.md del grupo:** en `~/.hermes/profiles/<tenant>/groups/<group-name>/SOUL.md`
   con el formato:
   ```markdown
   # <group-name> — <tenant>
   <descripcion>
   ## Scope
   <scope>
   ## Repositorios
   <repos>
   ## Memoria
   Holographic (SQLite). Privada del grupo.
   ```

2. **Registra el grupo en whatsapp-groups.yaml:** en `~/.hermes/profiles/<tenant>/whatsapp-groups.yaml`
   con el formato:
   ```yaml
   groups:
     "<jid>":
       name: "<group-name>"
       description: "<descripcion>"
       scope: "<scope>"
       repos: [<repo-list>]
   ```

3. **El bridge patch** (que corre en el gateway del tenant) inyecta la SOUL.md del grupo
   como `=== PROFILE ACTIVATION: <group-name> ===` en cada mensaje de ese grupo.

4. **Confirma al usuario:** "Grupo `<group-name>` configurado. Puedes editar la configuracion con `/grupo edit`."

## Archivos que modifica

- `~/.hermes/profiles/<tenant>/whatsapp-groups.yaml` — mapeo JID → config de grupo
- `~/.hermes/profiles/<tenant>/groups/<group-name>/SOUL.md` — identidad del grupo
- `channel_aliases.json` — lee, no modifica

## Archivos que NO modifica

- `~/.hermes/whatsapp-groups.yaml` (del orquestador principal)
- `~/.hermes/SOUL.md` (del orquestador principal)
- Bancos Hindsight (no existen para tenants)
- `config.yaml` del tenant (la config base no cambia por grupo)

## Comandos adicionales

- `/grupo list` — lista los grupos configurados para este tenant
- `/grupo edit <nombre>` — reabre el flujo de edicion para un grupo existente
- `/grupo remove <nombre>` — elimina la configuracion de un grupo
- `/grupo repos add <url>` — agrega un repo a la configuracion del tenant (requiere deploy key si es privado)
