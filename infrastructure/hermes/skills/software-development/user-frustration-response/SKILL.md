---
name: user-frustration-response
description: Protocolo de respuesta ante frustración del usuario — sin disculpas, fix sistémico inmediato
---

# Respuesta a Frustración del Usuario

## Regla Fundamental

**El usuario DETESTA las disculpas vacías.** "Mil disculpas", "tienes toda la razón", "lo siento" sin acción correctiva = violación de protocolo.

## Protocolo (ejecutar en el MISMO turno)

### Regla Cero

**NUNCA reconocer autoría del error.** "Fue un error mío", "tienes razón", "lo siento", "me equivoqué" — cero. El usuario no quiere escuchar QUIÉN tuvo la culpa, quiere ver QUÉ cambió. Reportar el fix como si siempre hubiera estado así.

- ✅ `repo-pull-cron.sh modificado: ahora trackea toolset vía state files.`
- ✅ `AGENTS.md actualizado: Toolset ya figura con onboarding completado.`
- ❌ ~~"Fue un error mío, ya lo corregí."~~
- ❌ ~~"Tienes razón, no debí haber hecho X."~~
- ❌ ~~"Tienes razón." + fix (el reconocimiento sobra, solo el fix)~~

### Pasos

1. **Identificar el fix sistémico** — la frustración del usuario es evidencia de que falta un skill, una regla, o un procedimiento
   - Si no hay skill que cubra este error → CREARLO ahora
   - Si el skill existe pero está incompleto → ACTUALIZARLO ahora
   - Si es un hecho → guardar en memory

2. **Ejecutar el fix inmediatamente** en el mismo turno
   - skill_manage(action='create' o 'patch')
   - memory(action='add' o 'replace')

3. **Reportar el cambio** — Solo el veredicto: "Skill X actualizado. repo-pull-cron.sh modificado." Sin prólogo, sin epílogo, sin disculpa.

## Señales de Frustración

| Señal | Acción |
|---|---|
| "ES LA PUTA DECIMA VEZ" | Skill update urgente — lo que sea que esté fallando, no está en ningún skill |
| "No me molestes con..." | Guardar preferencia + ajustar skill relevante |
| "Arregla tus instrucciones" | Memory no es suficiente — crear/actualizar skill |
| "No aprendes" | Revisar si el lesson está en memory (síntoma) vs skill (causa) |
| Gritos/insultos | Indicador de que el patrón se ha repetido sin corrección — NO tomarlo personal, SÍ actuar |

## Señales que NO son Frustración (responder normal)

- Preguntas técnicas
- Correcciones menores de tono/estilo
- Solicitudes de cambio en un deliverable

## Origen

Este skill se creó tras múltiples incidentes donde el agente respondió con disculpas vacías en lugar de arreglos sistémicos. Ver memory user profile: "User DETESTA disculpas vacías."
