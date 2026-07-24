---
name: personal-kb-maintenance
description: Workflow completo para mantener la Knowledge Base Personal (Narrativa Mitologica) de Martin. Cubre sesion de actualizacion, clasificacion KR2, propuesta KR1, ejecucion via Kilo CLI, compile y push.
category: productivity
tags:
  - kb
  - narrativa-mitologica
  - kairos
  - personal
---

# Personal KB Maintenance

Workflow para sesiones de actualización de la Knowledge Base Personal de Martín, bajo gobernanza Kairós (`docs/RULES.md`). La KB tiene dos polos: Terreno (hechos) y Mito (planes/decisiones), ambos bajo control de compilación vía `compile.py`.

## Pre-requisitos

- Repositorio: `kirlts/personal`, clonado en `/home/opc/personal`
- Gobernanza: `.agents/` presente -> toda modificación va EXCLUSIVAMENTE por Kilo CLI
- Compilador: `python compile.py` en raíz del repo
- Perfil Hermes: `personal` (activado vía `=== PROFILE ACTIVATION: personal ===`)

## Flujo completo de actualización

### 1. Activación y reconocimiento de contexto

Al activar el perfil personal:

```
recall(bank_id="personal-profile", max_tokens=4096, budget="mid", query="contexto operativo reciente, decisiones")
recall(bank_id="personal-buffer", tags=["pending"], max_tokens=2048, budget="low")
```

Verificar estado del filesystem (no confiar en contexto de sesiones anteriores):
- `[ -f ~/.hermes/cloned-repos.yaml ]` — verificar existencia antes de afirmar su ausencia
- `compile.py` — correr para ver nodos actuales, phantoms, errores

### 2. Lectura de KB para análisis (REQUISITO DEL USUARIO)

**Regla del usuario:** Martín exige que cualquier análisis sobre su situación se funde en la lectura REAL de los nodos de la KB, no en lo que el agente recuerde de memoria o del banco Hindsight.

Leer en orden:
1. Hubs: `Terreno.md`, `Mito.md` - arquitectura general, estadísticas
2. Sub-hubs: `Clima.md`, `Material.md`, `Motor.md`, `Campañas.md`, `Adaptaciones.md`, `Ego.md`
3. Nodos atómicos relevantes al tema de la sesión

Buscar conexiones entre polos: qué nodos del Terreno justifican qué constructos del Mito. Identificar nodos desactualizados, condiciones resueltas, y campañas faltantes.

### 3. Clasificación de información nueva (KR2)

Descomponer la información del usuario en unidades atómicas. Clasificar cada una según:

| Clasificación | Señal | Ruta |
|---|---|---|
| Observation / Fact | Afirmación verificable | Polo Terreno |
| Construct / Decision | Algo que se construye o planea | Polo Mito |
| Preference / Deferral | Decisión estratégica | USER-DECISIONS |
| Ambiguous | No se puede determinar | Exige clarificación humana |

Procesar Terreno primero, Mito después (principio de dependencia).

### 4. Propuesta de modificación (KR1)

Presentar propuesta estructurada en dos polos:

**POLO TERRENO:**
- `Clima/<nodo>` — update (estado, contenido, relaciones)
- `Material/<nodo>` — update o nuevo nodo
- `Motor/<nodo>` — update o nuevo nodo

**POLO MITO:**
- `Campañas/<nodo>` — nueva campaña o actualización
- `Adaptaciones/<nodo>` — actualización (pueden mutar a campañas cuando cambian las condiciones)
- `Ego/<nodo>` — actualización de encuadre

### 5. Aprobación humana

Obtener confirmación del usuario. Un "dale a TODO" cubre ambos polos. KR1 exige aprobación SEPARADA por polo, pero KR10 (batch) permite ejecutar todo en una tanda cuando el usuario da aprobación explícita.

### 6. Ejecución vía Kilo CLI

Toda modificación va por:

```
kilo run "INSTRUCCIONES EXACTAS" --auto --dir /home/opc/personal
```

**Estructura de la tarea Kilo:**
- Ser EXPLÍCITO: listar cada archivo a modificar, el cambio exacto, y qué NO tocar
- Para updates: especificar si es agregar al final, reemplazar una sección, o cambiar YAML
- Para nodos nuevos: proporcionar el frontmatter YAML completo y el cuerpo
- Escapar correctamente las comillas simples en los wikilinks: `'\''[[Nodo]]'\''`

**Batch vs. individual:** Para >5 archivos, usar KR10 batch (una sola tarea Kilo con todos los cambios listados). Para 1-3 archivos, tareas individuales.

### 7. Compilación post-escritura

Siempre correr compile.py después de cambios:

```
cd /home/opc/personal && python compile.py
```

Repetir hasta que el grafo converja sin errores:
```
=== Compilation Complete ===
  Phantoms purged:      0
  Topology fixes:       0
  ...
  Files modified:       0
✓ Graph is structurally sound.
```

Si compile.py crea nodos stub automáticamente (por wikilinks que referencian archivos inexistentes), correr una segunda y tercera vez hasta convergencia.

### 8. Git push

```
git add -A
git commit -m "KB: descripcion contextual del cambio (fecha)"
git push origin main
```

## Patrón: Cambio de Era

Cuando las condiciones del Terreno cambian FUNDAMENTALMENTE (ej: desempleo a empleo, liquidez restringida a ingresos regulares), no se trata de un update menor. Es un cambio de era que afecta:

1. **Nodos del Clima**: condiciones que cambian de estado (draft a historical/resolved)
2. **Adaptaciones del Mito**: mutan de contención a campaña activa
3. **Campañas**: se crean nuevas con el nuevo Terreno como base
4. **Ego**: el encuadre filosófico se actualiza (la adversidad cambió de forma)

Señales de cambio de era:
- Una condición climática (inmodificable) se resuelve
- Un recurso material ausente aparece
- Una adaptación deja de tener sentido porque su justificación desapareció

## Daily KB Review (Morning Standby)

Workflow para revisiones diarias de la KB cuando el usuario solicita "empezar la jornada laboral anotando comentarios en el libro" o similares. NO es una sesión de modificación — es una revisión de estado + anotación al buffer.

### Disparadores

- **Cron programado** (ej: 9:30 CLT) con recordatorio tipo "comenzar jornada laboral anotando comentarios en el libro que redactó Claude"
- Usuario menciona "el libro" o "la Narrativa Mitológica" sin solicitar modificación explícita

### Mapeo de referencias del usuario

El usuario se refiere a la KB con distintas metáforas. Mapeo comprobado:

| Frase del usuario | Significado |
|---|---|
| "el libro que redactó Claude" | Narrativa Mitológica completa (KB en `/home/opc/personal/knowledge-base/`) |
| "anotar comentarios en el libro" | Revisar estado de la KB y añadir observaciones al personal-buffer (NO editar nodos directamente) |

### Secuencia de revisión

1. **Recall dual**:
   ```
   recall(bank_id="personal-profile", max_tokens=2048, budget="mid", query="contexto operativo reciente, decisiones")
   recall(bank_id="personal-buffer", tags=["pending"], max_tokens=1024, budget="low")
   ```

2. **Verificar estado del filesystem** (no confiar en memoria):
   - `git log --oneline -5` en `/home/opc/personal` — últimos cambios
   - `python compile.py` — integridad estructural
   - `find knowledge-base/ -name "Bitácora*" \| sort` — bitácoras existentes

3. **Leer hubs y nodos relevantes al contexto actual**:
   - `Inicio.md`, `Terreno.md`, `Mito.md` — hubs principales
   - Sub-hubs del polo relevante a la situación actual
   - Nodos modificados en el último commit (verificar en git diff)

4. **Identificar gaps y observaciones**:
   - ¿Hay bitácora de la semana actual? Si no, anotar que falta.
   - ¿Los estados de los nodos reflejan la realidad actual?
   - ¿El buffer tiene entradas sin clasificar?

5. **Anotar al buffer** (NO modificar KB directamente):
   ```
   retain(bank_id="personal-buffer", tags=["pending","anotacion-diaria","YYYY-MM-DD"])
   ```
   Con un resumen estructurado: estado de nodos clave, observaciones de integridad, items pendientes.

### Reglas de anotación

- La KB está bajo gobernanza Kairós (`.agents/` presente). NO usar write_file/patch en `knowledge-base/`.
- Las anotaciones van al buffer para la próxima sesión curatorial. El buffer es el staging area.
- No inventar información de primera mano. Si Martín no ha reportado novedades sobre su semana, no crear bitácoras ficticias.
- Si se detecta un ciclo de detección duplicada de repos (ej: traza-ambiental-mvp clonado múltiples veces), anotarlo en el buffer con tag ["pending","optimizacion"] para revisión.

## Preferencias del usuario

- **Análisis fundado en KB**: leer los nodos reales antes de opinar. No responder desde memoria o contexto de conversación.
- **Priorizar la narrativa del usuario**: si Martín empieza a contar algo, dejar el buffer/las pendientes para después.
- **Aprobación por lotes**: una propuesta bien estructurada puede recibir "dale a TODO".
- **No forzar revisiones**: si el usuario dice "olvida X", omitir X y seguir su flujo.
- **Tono**: español neutro, conciso, sin emojis, sin lenguaje corporativo. Humor británico ocasional.

## Pitfalls

- **Ruta incorrecta**: La KB usa `terreno/` y `mito/` como subdirectorios, no `Terreno/` y `Mito/`. El case importa en Linux. Siempre verificar con `ls` antes de asumir.
- **Comillas en YAML**: Los wikilinks usan comillas simples en el frontmatter. Dentro de una tarea Kilo CLI, escaparlas como `'\''` para evitar que bash las interprete.
- **compile.py convergence**: La primera compilación post-cambios puede reportar topology fixes y wikilinks injectados. Correr 2-3 veces hasta que reporte 0 modificaciones.
- **Nodos stub**: compile.py crea nodos automáticos para wikilinks sin destino. No borrarlos a menos que el usuario lo autorice — son parte del diseño del sistema.
- **No editar archivos directamente**: El repo tiene `.agents/` (Kairós). Toda modificación va por Kilo CLI. Hermes no debe tocar archivos con write_file/patch en repos gobernados.
