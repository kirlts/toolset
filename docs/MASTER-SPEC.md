# MASTER-SPEC: Toolset Personal v0.1.0

> Infraestructura tecnica para un solo developer autonomo optimizando costos fijos y ejecucion asincrona en la nube.

---

## §1. Project Identity

**Purpose:** Definir y orquestar la infraestructura tecnica del desarrollador autonomo, separando la deliberacion en local (workstation) de la ejecucion asincrona en la nube (OCI), mitigando el bloqueo por proveedor (vendor lock-in) y los costos variables.

**Name:** Toolset Personal

**Domain:** Devops / Entornos de Desarrollo Cooperativos

**Problem it solves:** Evita la fragmentacion de contexto, la dependencia exclusiva de proveedores de nube de alto costo y la variabilidad de facturacion cuando agentes autonomos ejecutan tareas persistentes en la nube.

**Direct beneficiary:** El desarrollador (kirlts) al operar de forma movil y local con un entorno de costo predecible.

**Indirect beneficiary:** Los proyectos y clientes cuyos sistemas son desarrollados y mantenidos mediante este toolset.

**What it IS NOT:** No es una plataforma multi-inquilino (multi-tenant), ni un servicio de nube publica comercial.

---

## §2. Architecture

**Type:** Servidor-Cliente Descentralizado / Workspace Local-Nube

**Component Diagram:**

### Fase 1: Estado Actual (Transición)
```
[Local Workstation: Antigravity/Kilo] ----> (Internet) ----> [Composio MCP Cloud]
                                         |
                                         +-----------------> [Hindsight MCP Cloud (vectorize.io)]
```

### Fase 2: Estado Objetivo (Toolset Junio 2026)
```
[Local Workstation: Antigravity/Kilo] <== (Tailscale) ==> [OCI Server 24/7]
                                                                    |
                                                                    +---> [Hermes Agent]
                                                                    +---> [Daytona Sandboxes]
                                                                    +---> [Infisical Secrets]
                                                                    +---> [Hindsight Memory]
```

**Main Data Flow (Fase 2):**

1. El usuario envia comandos mediante mensajes de texto o audio a Hermes Agent (WhatsApp/Discord).
2. Hermes Agent delega la tarea a un subagente asincrono para evitar bloquear el canal de comunicacion.
3. El subagente solicita los secretos necesarios a Infisical y provisiona un entorno de pruebas aislado en Daytona.
4. El subagente clona el repositorio, ejecuta validaciones o cambios de codigo, y toma capturas de pantalla con Playwright.
5. El subagente publica los cambios mediante Composio/GitHub CLI y envia el reporte final al usuario a traves de Hermes Agent.

---

## §3. Technical Stack

| Layer | Technology | Justification |
| --- | --- | --- |
| Local Engine | Antigravity 2.0 | Motor principal de deliberacion y planificacion local. |
| Local Editor | Kilo Code (VS Code Extension) + OpenCode Go | Entorno por defecto conectado a OpenCode Go bajo suscripcion fija, integrado con Composio y Hindsight en modo Cloud (Fase 1). |
| Provisioning | OpenTofu (Planned) | Aprovisionamiento declarativo e inmutable de la infraestructura. |
| Network | Tailscale and Funnel (Planned) | Red privada entre local y nube sin exposicion de puertos publicos. |
| Secrets | Infisical (Planned) | Gestion de variables de entorno inyectadas directamente en memoria. |
| Sandbox | Daytona (Planned) | Creacion de micro-contenedores aislados para pruebas de codigo. |
| Memory | Hindsight | Fase 1: Cloud MCP (vectorize.io). Fase 2: Self-hosted en OCI. Base de conocimiento centralizada. |
| Integration | Composio | Pasarela de autenticacion OAuth para integraciones externas (Activo). |

---

## §4. Constraints (Inviolable Boundaries)

> These constraints override any other decision. They are the lines that must not be crossed.

1. Todos los secretos del sistema deben inyectarse mediante Infisical en tiempo de ejecucion; no se permiten archivos .env persistentes en disco.
2. Los puertos del servidor OCI no deben exponerse publicamente; todo el trafico debe cursar a traves de la red privada de Tailscale.
3. La base de datos de conocimiento de Hindsight debe ser unica y compartida entre todos los entornos para evitar la fragmentacion del contexto.

---

## §5. Agreed Trade-offs

> Decisions where one quality was sacrificed in favor of another, with the explicit reason.

| Trade-off | In favor of | Against | Justification |
| --- | --- | --- | --- |
| Autonomia vs Latencia | Control de costos fijos y portabilidad | Latencia de inicio de Daytona y llamadas remota a modelos | Se prefiere la predictibilidad de costos (nivel gratuito OCI y suscripciones locales fijas) sobre la velocidad de respuesta inmediata de la infraestructura. |

---

## §6. UI and User Experience

**Reference atmosphere:** Minimalista, utilitario y robusto. La interaccion principal se realiza mediante interfaces conversacionales de mensajeria y terminal local, priorizando la entrega rapida de datos estructurados, reportes y capturas visuales.

**Main user flow:**

1. El usuario interactua localmente mediante terminal/IDE o remotamente por WhatsApp/Discord.
2. El agente procesa la instruccion y responde con el estado de ejecucion en texto estructurado.
3. Si la tarea requiere revision visual, el agente adjunta la captura generada en el sandbox.

**Interface components:**

| Component | Function | File |
| --- | --- | --- |
| Hermes Chat Client | Interfaz movil de comunicacion | Integracion nativa de Hermes con WhatsApp/Discord |

---

## §7. Module Specifications

> Technical detail of each module or critical system component.

### 7.1. Orquestador Hermes

**Purpose:** Actuar como punto de entrada conversacional persistente para procesar ordenes y coordinar subagentes asincronos.

**Interface:**
```
 HermesInputReceiver -> parseCommand() -> delegateToSubagent() -> sendResponse()
```

**Dependencies:** Tailscale, Infisical, Daytona.

---

## §8. Operational Rules

> How the AI agent should operate within this repository.

**Rules location:** [docs/RULES.md](file:///home/kirlts/toolset/docs/RULES.md)

**Scope:** Todas las operaciones del agente en el repositorio.
