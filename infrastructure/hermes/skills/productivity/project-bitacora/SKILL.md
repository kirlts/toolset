---
name: project-bitacora
description: Mantener bitácoras operacionales de proyectos. Cuando el usuario comparte actualizaciones de estado, decisiones, o hitos, el registro va al destino designado (Google Doc vía Drive, o BITACORA.md local), no a memory() de Hermes.
category: productivity
---

# Bitácora de Proyecto

## Señales de activación

- El usuario dice "dejalo en bitacora", "anotalo en bitacora", "registralo"
- El usuario comparte una actualización de estado operacional de un proyecto ("X ahora está en Y%", "migramos Z a nuevo dominio", "cambiamos la infraestructura a W")
- El proyecto tiene un knowledge base o repo con estructura de documentación

## Formato de entrada

Cada entrada sigue esta estructura (aplica tanto para Google Doc como para BITACORA.md local):

```markdown
## YYYY-MM-DD — Título descriptivo del evento

- Descripción concisa de qué ocurrió, con detalles relevantes.
- Estado actual (porcentajes, ETA, responsables si aplica).
- Enlaces o referencias a recursos relevantes si existen.
```

## ⚠️ REGLA DE ORO: VERIFICAR DESTINO PRIMERO

**ANTES de escribir cualquier bitácora, revisa el SOUL.md del perfil activo.**

Algunos proyectos tienen su bitácora en Google Drive (no en filesystem). El perfil activo SIEMPRE define dónde va la bitácora en su SOUL.md.

| Perfil | Bitácora va en | 
|---|---|
| Desarrollo Trazambiental / trazambiental | Google Doc `drive-bitacora` (vía Composio) |
| Otros (por defecto) | BITACORA.md local |

**Flujo de decisión:**

1. ¿Hay un perfil activo? → leer su SOUL.md → buscar "bitácora" o "Google Drive Resources" o "REGLA ABSOLUTA — Bitácora"
2. Si SOUL.md dice "Google Drive" (o `drive-bitacora`) → usar Composio Google Docs / Drive tools
3. Si SOUL.md NO menciona Drive → BITACORA.md local
4. Si NO hay perfil activo (DM, orquestador default):
   - **Antes de preguntar al usuario**, verificar si `channel_aliases.json` tiene un `name` para el grupo actual. Si el name existe, buscar si hay un perfil en `.hermes/profiles/<name-kebab-case>/SOUL.md` (el name del grupo en kebab-case suele coincidir con el profile dir).
   - Si existe el profile en disco → leer su SOUL.md directamente y seguir pasos 1-3 sobre ese perfil (aunque no esté enrutado formalmente).
   - Si no existe ningún perfil en disco → preguntar al usuario o no asumir.

## Reglas

1. **Siempre verificar el perfil activo primero.** El SOUL.md del perfil es la autoridad sobre dónde va la bitácora. No asumas filesystem local.

2. **Bitácora es el destino primario, NO memory()**. Cuando el usuario dice "anota en bitácora" o "registra esto", el destino es la bitácora designada (Google Doc o BITACORA.md), no el `memory()` de Hermes. Memory es solo para preferencias de usuario y perfil. La bitácora es el archivo visible y accesible por el equipo.

4. **Ubicación (solo para proyectos que usan filesystem)**: BITACORA.md va en la raíz del knowledge base del proyecto (e.g., `/opt/traza-ambiental/knowledge-base/BITACORA.md`). Si no existe KB, va en `docs/` del repo.

5. **Entradas nuevas al inicio del archivo** (más reciente primero) o al final (orden cronológico). Usa orden cronológico inverso (más reciente arriba) para proyectos activos.

6. **Sin ruido**: No registres cada mensaje trivial. Solo estado operacional, decisiones, cambios de infraestructura, migraciones, y hitos.

7. **Tono**: Neutro, factual, sin emojis ni adornos. Fechas en formato ISO (YYYY-MM-DD).

## Archivos de referencia

- `references/formato-bitacora.md`: Ejemplo concreto de entrada de bitácora (proyecto Trazambiental). Úsalo como referencia de formato.
- `references/composio-drive-bitacora.md`: Cómo escribir en la bitácora de Google Drive usando Composio MCP (para proyectos que usan Drive).

## Pitfalls

- **Usar memory() para registros operacionales** en vez de la bitácora designada. Violación documentada en 2026-07-21: Martín corrigió explícitamente "anota en la bitácora, no en tu memoria, SIEMPRE". Memory es para preferencias de usuario, no para registros de proyecto.
- No crees la bitácora en una ubicación que el usuario no pueda ver fácilmente (e.g., dentro de `.agents/` o `.git/`).
- Si el usuario pidió explícitamente bitácora, confirma con "Hecho, registrado en [destino]" y menciona el destino exacto (Google Doc link o ruta local).
- **No asumir filesystem local sin verificar el perfil activo.** Siempre revisar SOUL.md primero. Los perfiles Trazambiental usan Google Drive, no BITACORA.md local.

## Verificación

```bash
# Para bitácora local (BITACORA.md):
grep -c "YYYY-MM-DD" /opt/<proyecto>/knowledge-base/BITACORA.md

# Para bitácora en Google Drive:
# Verificar en el Google Doc directamente (no hay comando local)
# El Google Doc ID está en el SOUL.md del perfil
```
