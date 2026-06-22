# Kairós: Referencia Rápida

> **Version:** v3.5.0


Este archivo es la referencia operativa del framework de gobernanza, no documentación del proyecto. Todo el contenido del directorio `.agents/` (reglas, skills, workflows, plantillas) está escrito para ser leído y ejecutado autónomamente por la IA. El agente es el operador del framework; el usuario define la intención.

**Entorno optimizado:** Antigravity IDE. Compatibilidad teórica con Cursor, Windsurf, Claude Code y Gemini CLI (no probada en producción).

## Estructura

| Carpeta | Función |
|---|---|
| `.agents/rules/` | Reglas de comportamiento (always-on y model-decision) |
| `.agents/roles/` | Identidades extraídas para gobernanza de sesión |
| `.agents/workflows/` | Flujos invocables con comandos |
| `.agents/skills/` | Protocolos automáticos por contexto |
| `.agents/knowledge/` | Material de referencia bajo demanda |
| `.agents/templates/` | Plantillas para documentos del proyecto |
| `docs/` | MASTER-SPEC, TODO, MEMORY, CHANGELOG, USER-DECISIONS, REPOMAP, LIVING-DOCUMENT, TEST, RULES |

## Comandos

| Comando | Función |
|---|---|
| `/derive` | Checklist exhaustivo desde código o documentación, integrado con MASTER-SPEC y TODO |
| `/checklist` | Checklist desde cualquier input, standalone, agnóstico al dominio |
| `/test` | Definir o ejecutar estrategia de testing |
| `/fix` | Diagnosticar y resolver deuda técnica |
| `/document` | Sincronizar documentación con el estado real del proyecto |
| `/repomap` | Genera el mapa de enrutamiento y acceso a directorios en REPOMAP.md |
| `/narrate` | Único punto de entrada para generar o actualizar LIVING-DOCUMENT.md con exportación EPUB |
| `/mcp` | Administrar servidores MCP (Hindsight y Composio) del proyecto |
| `/update` | Actualizar gobernanza a la última versión |
| `/release` | Generar nueva versión del framework (solo repo canónico) |
| `/role` | Activar una identidad de gobernanza (persona) para la sesión |
| `/create-role` | Extraer una nueva identidad a partir de fuentes primarias |

## Patrones de adherencia aplicados

| Patrón | Efecto medido | Decisión de diseño | Fuente |
|---|---|---|---|
| Declarative System Framing | -81% varianza entre idiomas | Reglas como hechos del entorno. El tono declarativo es neutro entre idiomas; el imperativo genera varianza de adherencia | arXiv 2603.25015 (Imperative Interference) |
| Tabular Superiority | +40.29% precisión lógica | Subconjuntos 🤖/🧑/🤖🧑, LNC y Leyes de Armonía expresados en tablas. Las tablas fuerzan razonamiento columna a columna, cerrando atajos probabilísticos | arXiv 2412.17189 (Better Think with Tables) |
| Primacy/Recency Anchoring | Mitiga Factorial Dead Zone | Restricciones clave al inicio y al final de las plantillas. El modelo rinde en U: máximo en posición inicial y final, mínimo en el centro | Stanford CS (Lost in the Middle); arXiv 2603.10123 |
| State Isolation | Mitiga -39% degradación multi-turno | Ciclo BEFORE/DURING/AFTER: reconstruye el estado desde artefactos aislados en cada turno, sin acumulación entre conversaciones | OpenReview (LLMs Get Lost In Multi-Turn Conversation) |
| Positive Directive Mapping | -50% desviación comportamental | Espacio de conducta explícito. Las prohibiciones cubren solo fallos catastróficos; mapear lo permitido supera en eficacia a mapear lo prohibido | arXiv 2604.01438 (ClawSafety) |
| Traceable Identifiers | 80.4% F1 multi-paso | `[ACTOR.CAT.NN.VER]`, `[R-NNN]`, `[LNC-NN]`. Anclan cada verificación a un artefacto concreto en cadenas de razonamiento largas | ResearchGate (LLMs for Doc-to-Code Traceability) |
| Translation Tax Suppression | Elimina "Linguistic Heterogeneity Penalty" | Los protocolos internos operan en inglés determinista para alinearse con el espacio latente de la IA, maximizando la comprensión lógica, mientras la interacción y escritura final reflejan el idioma del usuario. | Adherencia Lingüística en IA Frontera (Abril 2026) |
| Axiomatic Pre-Contextualization | Previene -6.81% degradación | Meta-instrucciones preceden a los datos que gobiernan. El modelo lee el marco antes que el contenido que debe interpretar | arXiv 2412.17189 (input design studies) |
| Modular Context Partitioning | Previene degradación >32K tokens | rules (siempre activas), skills (por demanda), knowledge (@referencia). Mantiene el contexto activo bajo el umbral de degradación documentado | arXiv 2601.10343 (OctoBench); arXiv 2603.16021 (Folder Structure as Agent Architecture) |

## Gobernanza Topológica (REPOMAP)

El framework impone un "Cortafuegos de Contexto" (Context Firewall) frente a la exploración probabilística de los IDEs agenticos, neutralizando el *Context Rot* y la *Deuda de Verificación*.

| Principio Arquitectónico | Mecanismo y Efecto | Fuente / Justificación |
|---|---|---|
| Axiomatic Pre-Contextualization | Aísla reglas críticas (`MASTER-SPEC`) como "Axiomas de Dominio". Previene que el LLM deduzca reglas normativas a partir de código estadístico (descriptivo). | arXiv 2603.07896 (SMGI: Fact-Value Distinction) |
| Context Firewall | Sustituye la búsqueda vectorial (BM25/Embeddings) del IDE por fronteras declarativas. Elimina las "Alucinaciones Complacientes" causadas por contextos ruidosos. | arXiv 2604.17025 (Convergent AI Agent Framework - CAAF) |
| MECE Clustering | Compresión estricta de la topología en clústeres planos (Mutuamente Excluyentes, Colectivamente Exhaustivos). Maximiza la densidad de señal y previene la dilución de atención. | arXiv 2307.03172 (Lost in the Middle); Andrej Karpathy (LLM OS: RAM vs Hard Drive) |
| Stateless Overwriting | Regeneración *Zero-Shot* del mapa desde la topología física. Erradica el Sesgo de Recencia y la Oscilación Estocástica propios de las actualizaciones diferenciales continuas. | arXiv 2603.16021 (Folder Structure as Agent Architecture); OpenReview NeurIPS (LLMs Get Lost in Multi-Turn Conversation) |

## Asignación de dominio por diseño

El framework previene fallas de delegación estructurando el trabajo en tres subconjuntos basados en las limitaciones empíricas medidas de los LLMs:

- **🤖 Subconjunto LLM:** Ejecución autónoma (andamiaje sintáctico, tests de funciones puras).
- **🧑 Subconjunto HUM:** Tareas bloqueadas para la IA (*trade-offs* estructurales, diseño lógico, validación).
- **🤖🧑 Subconjunto MIX:** Evaluación compartida. El modelo procesa la información inicial y establece un punto de control del operador para avanzar.

**Fuentes:** Límites de autonomía (*SWE-bench Verified*), deficiencias de predicción (*Anthropic JOSSE dataset*), seguridad de agentes (*ClawSafety*, arXiv 2604.01438).

## AI Smell

Convergencia paramétrica de LLMs en interfaces visuales.

| Mecanismo | Ubicación |
|---|---|
| Lista Negra de Convergencia (10 vectores con valores, contexto y desvío) | `.agents/knowledge/ai-smell-registry.md` |
| Regla de desvío justificado | `.agents/rules/06-aesthetics.md` |
| Gate visual de 3 pasos (Anti-Slop, Armonía, Integridad) | `.agents/skills/visual-excellence-protocol/SKILL.md` |

**Fuente:** Síntesis de patrones de convergencia en interfaces generadas por IA (2025-2026). Wikipedia, "Signs of AI Writing".

## Erradicación del sesgo de compresión (Falsa modestia)

Las reglas del framework establecen que **la IA no tiene fatiga biológica ni costo temporal de tipeo**. Las directivas exigen entregas completas dentro del Subconjunto 🤖 LLM, sin interpoladores pasivos ni omisiones.

**Fuentes:** Estudio Anthropic de estimación JIRA (JOSSE dataset, 2025). Reporte Greptile *State of AI Coding* (medida del volumen neto efectivo en repositorios).

## Detección de escritura IA

| Categoría | Patrones | Mecanismo |
|---|---|---|
| Muletillas RLHF | «Cabe destacar que», «Es importante señalar» | Filtro anti-slop en workflows + 00-behavior.md |
| Paralelismos negativos | «not just X, but Y», «no solo X, sino Y» | Filtro 7 en plantillas de trabajo |
| Copy corporativo | «cutting-edge», «seamless», «innovative» | Detección en `/document` + Filtro 7 |
| Positividad servil | «¡Excelente pregunta!», «Gran observación» | 00-behavior.md |
| Em dashes | Cualquier instancia de (—) | Filtro 7, tolerancia cero |

**Fuentes:** Wikipedia, "Signs of AI Writing". Detección heurística derivada de ai-smell-registry.md.

## Actualización

`/update` compara versión local con la publicada, propone diffs, no toca docs del proyecto.
