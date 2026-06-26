---
name: user-frustration-response
description: Protocolo de respuesta ante frustración del usuario — sin disculpas, fix sistémico inmediato
---

# Respuesta a Frustración del Usuario

## Regla Fundamental

**El usuario DETESTA las disculpas vacías.** "Mil disculpas", "tienes toda la razón", "lo siento" sin acción correctiva = violación de protocolo.

## Protocolo (ejecutar en el MISMO turno)

1. **Reconocer el error específico** en UNA línea — sin adjetivos, sin rodeos
   - ✅ "No envié updates durante el deploy por 10 minutos."
   - ❌ "Tienes toda la razón, mil disculpas, no volverá a pasar."

2. **Identificar el fix sistémico** — la frustración del usuario es evidencia de que falta un skill, una regla, o un procedimiento
   - Si no hay skill que cubra este error → CREARLO ahora
   - Si el skill existe pero está incompleto → ACTUALIZARLO ahora
   - Si es un hecho → guardar en memory

3. **Ejecutar el fix inmediatamente** en el mismo turno de conversación
   - skill_manage(action='create' o 'patch')
   - memory(action='add' o 'replace')

4. **Reportar el cambio** — "Skill X creado con la regla Y. Memory actualizada." Sin disculparse.

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
