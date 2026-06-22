# RULES

> Reglas operativas para agentes de inteligencia artificial que trabajen en este repositorio.
> Referenciado en MASTER-SPEC §8.

---

## Scope

Estas reglas se aplican de forma obligatoria a todas las operaciones realizadas por el asistente de inteligencia artificial dentro del repositorio actual, incluyendo la modificacion de codigo, pruebas, aprovisionamiento de infraestructura y sincronizacion de la documentacion de gobernanza.

---

## Rules

### Sinergia y Uso de Hindsight MCP (Memoria Centralizada)

- **Ruteo Dinámico por Proyecto:** El agente (independientemente del harness o IDE, ej. Kilo Code, Antigravity, Codex, Claude Code, o este asistente) debe interactuar exclusivamente con el banco de Hindsight correspondiente al repositorio activo:
  - El agente determinará el nombre del banco extrayendo el nombre del directorio raíz del proyecto actual.
  - El agente debe buscar en la configuración de servidores MCP del entorno el servidor con el identificador exacto `hindsight-<nombre-del-proyecto>`.
  - Si el servidor correspondiente existe, se utilizará para todas las operaciones de recall y retain.
  - Si no existe un servidor configurado con el nombre del proyecto activo, el agente debe abortar inmediatamente la operación de memoria y alertar al usuario para que añada la configuración en la configuración de MCP global de su arnés.
- **Carga Proactiva de Contexto:** Al inicio de cualquier tarea o sesión, el agente debe invocar la herramienta `recall` con palabras clave relacionadas con la tarea activa para recuperar preferencias, decisiones arquitectónicas e historial relevante del usuario desde el banco del proyecto activo.
- **Sincronización Obligatoria de Gobernanza:** El agente debe ejecutar la herramienta `retain` en Hindsight SIEMPRE que se cumpla al menos una de las siguientes condiciones deterministas. No hay excepciones ni margen para la interpretación:
  - **Finalización de Workflows (INCONDICIONAL):** Ejecutar `retain` es el paso OBLIGATORIO final, justo antes de dar por terminada la ejecución de los workflows `/document`, `/repomap` y `/derive`, independientemente de si los archivos físicos sufrieron modificaciones o no. La sola invocación del workflow exige retención de estado.
  - **Creación de archivos:** Creación de cualquier archivo nuevo en el directorio `docs/`.
  - **Edición de MASTER-SPEC.md:** Cualquier alteración de contenido en `docs/MASTER-SPEC.md`.
  - **Adición de identificadores únicos:** Inserción de nuevos bloques con identificadores únicos (`[TASK-NNN]`, `[UD-NNN]`, `[HEU-NNN]`, `[ACTOR.CAT.NN.VER]`) en los archivos de `docs/`.
  - **Cambios de estado:** Modificación de tareas en `docs/TODO.md` o checks en `docs/VERIFICATION.md`.
  - **Actualizaciones de ruteo:** Modificaciones en la tabla de ruteo de `docs/REPOMAP.md`.
- **Consistencia de Inferencia:** Para evitar la destrucción de la caché de contexto (cache miss), el agente debe consultar Hindsight al inicio de la sesión para verificar las directrices sobre el modelo de inferencia seleccionado y evitar alternar modelos de forma innecesaria.

### Sinergia y Uso de Composio MCP (Pasarela de Integraciones)

- **Pasarela Única:** Composio es el canal exclusivo para autenticar e interactuar con APIs externas y herramientas de terceros. Está prohibido escribir scripts de autenticación o intentar implementar flujos manuales para herramientas soportadas y activamente expuestas por Composio.
- **Validación de Esquemas:** El agente debe inspeccionar el esquema de entrada de cada herramienta de Composio antes de ejecutarla para garantizar que los argumentos cumplen estrictamente con los tipos y campos obligatorios definidos en el servidor.
