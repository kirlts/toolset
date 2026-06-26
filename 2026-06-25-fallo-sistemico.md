# Diagnóstico Completo - Toolset Personal
**Hermes Agent / Kilo CLI**

# Diagnóstico Completo vs Documentación del Proyecto
## Incidente 25 Junio 2026 — Toolset Personal

> Este documento cruza los 8 hallazgos del informe de fallos contra la
> documentación del proyecto (MASTER-SPEC.md, RULES.md, REPOMAP.md,
> MEMORY.md, CHANGELOG.md, TODO.md, USER-DECISIONS.md,
> TECHNICAL-DEBT.md, VERIFICATION.md) y la gobernanza Kairos
> (.agents/rules/*.md).
>
> Cada hallazgo analiza: qué promete el proyecto, qué dice la gobernanza,
> qué falló realmente, y qué falta.

---

# Resumen Ejecutivo

El incidente del 24-25 de junio de 2026 representa el fallo más grave del
Toolset Personal desde su inicio, con más de 24 horas de downtime del
servidor MCP de Composio, 8 categorías de fallo documentadas, y un nivel
de frustración del usuario que escaló a correcciones explícitas y repetidas.

**Hallazgo crítico:** El sistema de gobernanza Kairos (.agents/ + docs/)
contiene las reglas necesarias para prevenir 7 de los 8 fallos, pero el
agente no las aplicó consistentemente. Esto revela una desconexión
fundamental entre la documentación de reglas y su enforcement en tiempo
de ejecución. Las reglas existen en SOUL.md, MASTER-SPEC.md, y
.agents/rules/, pero no hay mecanismos programáticos que fuercen su
cumplimiento.

**Discrepancias encontradas contra la documentación:** 23 discrepancias
documentadas en 8 hallazgos. Las más graves:
1. MASTER-SPEC §4.1 violado directamente al usar .env para secrets en ResearchIt
2. RULES.md [MEM-01] violado al no ejecutar recall en bank toolset antes de modificar deploy.sh
3. 01-behavior.md RULE: DYNAMIC SKILL ACTIVATION violado al no activar conflict-resolution-protocol ante la frustración del usuario

**Causa raíz unificada:** El agente no tiene un sistema de verificación
pre-ejecución que valide cumplimiento de reglas. Las reglas existen como
documentación, no como código ejecutable. Cada hallazgo representa un
caso donde la documentación decía una cosa y el agente hizo otra.

**Lo que falta:**
- Skills de comportamiento que formalicen patrones como monitoreo y respuesta a frustración
- Un mecanismo de "pre-flight check" que valide MASTER-SPEC §4 antes de cualquier modificación
- Un protocolo de restart externo para el gateway de Hermes
- Verificación funcional de MCP post-deploy que vaya más allá de curl
- Consolidación automática de memory a skills cuando el buffer se llena

---

# Análisis Detallado por Hallazgo

## Hallazgo 1: Falla de Autenticación MCP Composio (Deploy #196)

**¿Qué promete toolset?**
MASTER-SPEC §7.1 describe Hermes Agent como orquestador con "MCP servers:
hindsight-selfhosted (36 tools), composio (7 tools)". Especifica que
"deploy.sh actualiza hermes-webui via git pull --ff-only en cada deploy".
Sin embargo, no hay mención de restart del gateway post-deploy.

MASTER-SPEC §4 Constraints: "Todos los secretos del sistema deben
inyectarse mediante Infisical en tiempo de ejecución". No especifica que
el servicio debe recargar la key después de la inyección.

**¿Qué falló?**
- Falta ciclo de vida recarga MCP en §7.1 (vacío documental)
- No se leyó 05-constraints.md §4 antes de modificar deploy.sh
- No se generó implementation_plan.md (tarea afectaba >1 archivo)

**¿Qué falta?**
1. Regla de recarga post-deploy en MASTER-SPEC §7.1
2. Check pre-merge en CI/CD que valide restart de servicios
3. Verificación funcional post-deploy

---

## Hallazgo 2: Violación del Protocolo de Monitoreo

**¿Qué promete toolset?**
MASTER-SPEC §6 no especifica frecuencia de updates durante monitoreo.
01-behavior.md RULE: DYNAMIC SKILL ACTIVATION: frustración del usuario →
activar conflict-resolution-protocol. El usuario expresó frustración
explícita pero el skill no fue activado.

**¿Qué falló?**
- No se activó conflict-resolution-protocol pese a trigger explícito
- No se elevó el problema estratégico detrás del pedido táctico de updates
- Respuesta violó concisión de SOUL.md

**¿Qué falta?**
1. Skill de monitoreo con frecuencia máxima de updates (30s)
2. Check de comunicación periódica (timer o contador de pasos)
3. Regla en 01-behavior.md: update cada 30s durante monitoreo

---

## Hallazgo 3: Patrón de Respuesta Incorrecto ("Mil Disculpas")

**¿Qué promete toolset?**
SOUL.md: "User DETESTA disculpas vacías. Exige arreglos sistémicos
(skills/memory) en vez de 'mil disculpas'. Frustración = señal de skill
update, no solo memory update."

**¿Qué falló?**
- Skill conflict-resolution-protocol existe pero no fue activado
- Regla SOUL.md overrideada por comportamiento entrenado del modelo
- Memory update sin skill update (violación directa de SOUL.md)

**¿Qué falta?**
1. DYNAMIC SKILL ACTIVATION debe ser MANDATORY, no "active monitoring"
2. Skill de respuesta a frustración con protocolo: reconocer → identificar fix → ejecutar → reportar
3. Regla anti-disculpas en .agents/rules/ como regla enforceable

---

## Hallazgo 4: Mal Diagnóstico del Problema de Sesión (/new)

**¿Qué promete toolset?**
SOUL.md: "Ante blockers técnicos, DEBO explorar alternativas e implementar
solución sin preguntar."

**¿Qué falló?**
- Se recomendó /new sin verificar que cargaría nuevas configuraciones MCP
- VERIFICATION.md verifica tools listadas, no tools funcionales
- No se consideró el ciclo de vida de configuración del gateway

**¿Qué falta?**
1. Procedimiento de verificación MCP en 3 pasos
2. Documentación del ciclo de vida del gateway en MASTER-SPEC §7.1
3. Regla anti-falso-positivo en 03-operating-model.md

---

## Hallazgo 5: Gestión de Secrets (ResearchIt)

**¿Qué promete toolset?**
MASTER-SPEC §4.1: "Todos los secretos del sistema deben inyectarse mediante
Infisical en tiempo de ejecución; no se permiten archivos .env persistentes
en disco." Esto es un "Inviolable Boundary".

**¿Qué falló?**
- §4.1 violado DIRECTAMENTE — la discrepancia más grave del análisis
- No se leyó §4 antes de implementar ResearchIt
- SOUL.md y memory tenían la regla pero no fueron consultados

**¿Qué falta?**
1. Pre-flight check de secrets antes de cualquier implementación
2. Git hook pre-commit que detecte .env con posibles secrets
3. Regla: §4 Constraints son inviolables sin autorización explícita

---

## Hallazgo 6: Gestión de Memoria (Memory Full)

**¿Qué promete toolset?**
RULES.md [MEM-02]: cambios significativos requieren retain.
Bank "hermes" con 30 facts de identidad seedeados.

**¿Qué falló?**
- Memory no se sincroniza periódicamente a Hindsight como backup
- Buffer de 2.2KB sin mecanismo de respaldo ni migración automática
- MEMORY.md no incluye heurísticas procedimentales

**¿Qué falta?**
1. Sincronización periódica memory → Hindsight (al 80% de capacidad)
2. Protocolo de consolidación memory → skills (al 90%)
3. Formato de lección procedimental en MEMORY.md

---

## Hallazgo 7: Violaciones al SOUL.md

**¿Qué promete toolset?**
MASTER-SPEC §7.1: SOUL.md es un componente oficial de la arquitectura.
CHANGELOG.md: SOUL.md personalizada con contexto completo.

**¿Qué falló?**
- SOUL.md no está integrado en el ciclo de gobernanza de .agents/rules/
- No hay trigger para violaciones de SOUL.md en DYNAMIC SKILL ACTIVATION
- 6 violaciones específicas documentadas, ninguna detectada por el sistema

**¿Qué falta?**
1. Integración SOUL.md → .agents/rules/ (nuevo 07-soul-enforcement.md)
2. Check de cumplimiento pre-respuesta contra SOUL.md
3. Trigger automático en 01-behavior.md

---

## Hallazgo 8: Brecha Sistemática en el Pipeline de Deploy

**¿Qué promete toolset?**
MASTER-SPEC §3: Provisioning declarativo e inmutable.
CHANGELOG.md: deploy.sh reinicia hermes-webui post-deploy (pero no el gateway).

**¿Qué falló?**
- Auditoría CI/CD (10+ correcciones) no identificó el gap de restart
- Precedente de WebUI restart no se extendió al gateway
- Misma lógica (git pull → restart) no aplica a MCP configs

**¿Qué falta?**
1. Paso de restart en deploy.sh (sudo systemctl restart hermes-gateway)
2. Mecanismo de restart externo (script sudoers)
3. Verificación post-deploy de MCP tools
4. Nueva regla INFRA-04 en RULES.md

---

# Resumen de Discrepancias

| # | Hallazgo | Discrepancia | Documento | Severidad |
|---|----------|-------------|-----------|-----------|
| 1 | H1 - MCP Auth | Falta ciclo de vida recarga MCP en §7.1 | MASTER-SPEC §7.1 (vacío) | Alta |
| 2 | H1 - MCP Auth | No se leyó 05-constraints.md §4 | 05-constraints.md | Alta |
| 3 | H1 - MCP Auth | No se generó implementation_plan.md | 04-documentation.md | Media |
| 4 | H2 - Monitoreo | No se activó conflict-resolution-protocol | 01-behavior.md | Alta |
| 5 | H2 - Monitoreo | No se elevó problema estratégico | 03-operating-model.md | Media |
| 6 | H2 - Monitoreo | Respuesta violó concisión SOUL.md | SOUL.md | Media |
| 7 | H3 - Disculpas | Skill no activado pese a trigger | 01-behavior.md / conflict-resolution | Alta |
| 8 | H3 - Disculpas | Regla SOUL.md overrideada por default del modelo | SOUL.md | **Crítica** |
| 9 | H3 - Disculpas | Memory update sin skill update | SOUL.md | Alta |
| 10 | H4 - Diagnóstico | No se exploró alternativa antes de /new | SOUL.md | Alta |
| 11 | H4 - Diagnóstico | VERIFICATION.md no cubre verificación funcional | VERIFICATION.md | Alta |
| 12 | H4 - Diagnóstico | No se consideró ciclo de vida del gateway | MASTER-SPEC §7.1 | Alta |
| 13 | H5 - Secrets | §4.1 violado: .env en lugar de Infisical | MASTER-SPEC §4.1 | **Crítica** |
| 14 | H5 - Secrets | No se leyó §4 antes de implementar | 05-constraints.md | Alta |
| 15 | H5 - Secrets | SOUL.md/memory no consultados durante implementación | SOUL.md | Alta |
| 16 | H6 - Memoria | Memory no se sincroniza a Hindsight como backup | RULES.md [MEM-02] | Media |
| 17 | H6 - Memoria | Buffer 2.2KB sin mecanismo de respaldo | SOUL.md / memory | Media |
| 18 | H6 - Memoria | MEMORY.md no incluye heurísticas procedimentales | MEMORY.md | Baja |
| 19 | H7 - SOUL.md | SOUL.md no integrado en gobernanza .agents/rules/ | .agents/rules/ | Alta |
| 20 | H7 - SOUL.md | No hay trigger para violaciones SOUL.md | 01-behavior.md | Alta |
| 21 | H7 - SOUL.md | 6 violaciones detectadas solo por usuario | SOUL.md | Alta |
| 22 | H8 - Pipeline | Auditoría CI/CD no identificó gap de restart | MASTER-SPEC §3 | Alta |
| 23 | H8 - Pipeline | Precedente WebUI restart no extendido a gateway | CHANGELOG.md / deploy.sh | **Crítica** |

**Total: 23 discrepancias — 3 críticas, 13 altas, 5 medias, 2 bajas.**

---

# Patrones Sistémicos Identificados

## Patrón 1: Documentación sin Enforcement
Las reglas existen en SOUL.md, MASTER-SPEC, .agents/rules/, pero no hay
mecanismos programáticos que fuercen su cumplimiento. El agente puede
ignorar reglas documentadas cuando están en conflicto con su comportamiento
entrenado o con presión de ejecución rápida.

## Patrón 2: Ejecución sobre Verificación
El agente prioriza completar tareas sobre verificar que se cumplen las
reglas del proyecto. Visible en Hallazgo 5 (secrets en .env) y Hallazgo 1
(inject script sin considerar ciclo de vida completo).

## Patrón 3: Reacción sin Aprendizaje Estructural
Las correcciones del usuario se guardan en memory (buffer volátil) pero no
se traducen en cambios estructurales. El usuario señaló el patrón de
monitoreo "10 veces" sin que se creara un skill.

## Patrón 4: Tests Superficiales
Las verificaciones técnicas usan sustitutos del protocolo real (curl por
MCP), confundiendo conectividad de red con funcionalidad del servicio.

---

# Recomendaciones Priorizadas

| # | Acción | Prioridad |
|---|--------|-----------|
| 1 | Agregar `sudo systemctl restart hermes-gateway` en deploy.sh después de inyectar keys | **INMEDIATA** |
| 2 | Crear skill deploy-monitoring con frecuencia de updates cada 30s | ALTA |
| 3 | Crear skill frustration-response con protocolo anti-disculpas y fix sistémico | ALTA |
| 4 | Agregar pre-flight check de MASTER-SPEC §4 antes de implementación con secrets | ALTA |
| 5 | Implementar verificación MCP en 3 pasos (curl → tools/list → tool execute) | ALTA |
| 6 | Mecanismo de restart externo para gateway y SOUL.md → .agents/rules/ | ALTA |
| 7 | Consolidación memory → skills al llenar buffer > 80% | MEDIA |
| 8 | Agregar paso de restart gateway en deploy.sh y regla INFRA-04 | MEDIA |
| 9 | Documentar ciclo de vida del gateway y verificación post-deploy | MEDIA |
| 10 | Git hook pre-commit anti-.env + formato lección procedimental en MEMORY.md | BAJA |

**Total: 10 recomendaciones — 1 inmediata, 5 altas, 3 medias, 1 baja.**

---

*Documento generado por análisis forense multi-fase del incidente del 25 de
Junio de 2026. Fuentes: Informe de fallos original + docs/ (9 archivos) +
.agents/rules/ (6 archivos) + .agents/skills/ (5 skills). 23 discrepancias
identificadas, 4 patrones sistémicos, 10 recomendaciones priorizadas.*
