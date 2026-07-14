---
name: project-bitacora
description: Mantener bitácoras operacionales (BITACORA.md) en knowledge bases de proyectos. Cuando el usuario comparte actualizaciones de estado, decisiones, o hitos de un proyecto, el registro va a un archivo BITACORA.md físico en el KB del proyecto (no solo a Hindsight memory banks).
category: productivity
---

# Bitácora de Proyecto (BITACORA.md)

Cuando el usuario comparte información operacional sobre un proyecto (estado, decisiones, migraciones, hitos), debes registrarla en un archivo `BITACORA.md` dentro del knowledge base del proyecto, no solo en Hindsight memory.

## Señales de activación

- El usuario dice "dejalo en bitacora", "anotalo en bitacora", "registralo"
- El usuario comparte una actualización de estado operacional de un proyecto ("X ahora está en Y%", "migramos Z a nuevo dominio", "cambiamos la infraestructura a W")
- El proyecto tiene un knowledge base o repo con estructura de documentación

## Formato de entrada

Cada entrada en BITACORA.md sigue esta estructura:

```markdown
## YYYY-MM-DD — Título descriptivo del evento

- Descripción concisa de qué ocurrió, con detalles relevantes.
- Estado actual (porcentajes, ETA, responsables si aplica).
- Enlaces o referencias a recursos relevantes si existen.
```

## Reglas

1. **Siempre bitácora física + Hindsight**: La entrada va en BITACORA.md en el KB del proyecto Y se retiene en los banks de Hindsight (hermes + perfil del grupo). No es uno u otro, son ambos.

2. **Ubicación**: BITACORA.md va en la raíz del knowledge base del proyecto (e.g., `/opt/traza-ambiental/knowledge-base/BITACORA.md`). Si no existe KB, va en `docs/` del repo.

3. **Entradas nuevas al inicio del archivo** (más reciente primero) o al final (orden cronológico). Usa orden cronológico inverso (más reciente arriba) para proyectos activos.

4. **Sin ruido**: No registres cada mensaje trivial. Solo estado operacional, decisiones, cambios de infraestructura, migraciones, y hitos.

5. **Tono**: Neutro, factual, sin emojis ni adornos. Fechas en formato ISO (YYYY-MM-DD).

## Archivos de referencia

- `references/formato-bitacora.md`: Ejemplo concreto de entrada de bitácora (proyecto Trazambiental). Úsalo como referencia de formato.

## Pitfalls

- No asumas que un retain() en Hindsight es suficiente cuando el usuario pide bitácora. La bitácora es un archivo visible, no solo memoria interna.
- No crees la bitácora en una ubicación que el usuario no pueda ver fácilmente (e.g., dentro de `.agents/` o `.git/`).
- Si el usuario pidió explícitamente bitácora, confirma con "Hecho, registrado en BITACORA.md" y menciona la ruta.

## Verificación

```bash
# Verificar que la entrada existe
grep -c "YYYY-MM-DD" /opt/<proyecto>/knowledge-base/BITACORA.md
```
