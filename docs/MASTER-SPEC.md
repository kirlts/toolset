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
[Local Workstation: Kilo Code] <== (Tailscale) ==> [OCI Server 24/7]
                                                           |
                                                           +---> [Hermes Agent (gateway + Docker sandbox)]
                                                           +---> [Infisical Secrets]
                                                           +---> [Hindsight Memory (self-hosted)]
                                                           +---> [Caddy + Tailscale Funnel (:443/:8443)]
```

**Main Data Flow (Fase 2):**

1. El usuario envia comandos mediante mensajes de texto o audio a Hermes Agent (WhatsApp/Discord/WebUI).
2. Hermes Agent delega la tarea a un subagente asincrono via `delegate_task()` para evitar bloquear el canal de comunicacion.
3. El subagente ejecuta en el sandbox Docker nativo de Hermes (`terminal.backend: docker`), con acceso a secrets via Infisical.
4. El subagente clona el repositorio, ejecuta validaciones o cambios de codigo, y toma capturas de pantalla con las herramientas nativas de Hermes (`browser_snapshot`, `vision_analyze`).
5. El subagente publica los cambios mediante Composio/GitHub CLI y envia el reporte final al usuario a traves de Hermes Agent.

---

## §3. Technical Stack

| Layer | Technology | Justification |
| --- | --- | --- |
| Local Engine | Antigravity 2.0 | Motor principal de deliberacion y planificacion local. |
| Local Editor | Kilo Code (VS Code Extension) + OpenCode Go | Entorno por defecto conectado a OpenCode Go bajo suscripcion fija, integrado con Composio y Hindsight en modo Cloud (Fase 1). |
| Provisioning | OpenTofu | Aprovisionamiento declarativo e inmutable de la infraestructura. Activo. |
| Network | Tailscale (Funnel Active) | Red privada entre local y nube sin exposicion de puertos publicos. Funnel multi-puerto (:443 Caddy, :8443 Infisical, :8787 Hermes WebUI). Activo. |
| Container Runtime | Docker 29 + Compose Plugin | Orquestacion de servicios en el servidor OCI. Activo. |
| Secrets | Infisical (Self-hosted en OCI) | Gestion de variables de entorno inyectadas directamente en memoria. GitHub Secrets → Infisical → Hermes (.env). Activo. |
| Infisical Dependencies | PostgreSQL 16, Redis 7 | Base de datos y cache/cola requeridos por Infisical self-hosted. Activos. |
| Orquestador | Hermes Agent v0.17.0 | Agente autonomo 24/7. Gateway systemd, WhatsApp bot, WebUI, Docker sandbox. Activo. |
| Subagente | Kilo Code CLI v7.3.54 (`@kilocode/cli`) | CLI autonomo para tareas de codificacion pesadas (`kilo run --auto`). Mismo provider/config que Kilo local. |
| Sandbox | Docker nativo de Hermes (`terminal.backend: docker`) | Sandbox aislado con hardening (no-new-privs, cap-drop ALL, pids-limit 256). Daytona/Modal como backends alternativos configurables. |
| Memory | Hindsight (self-hosted en OCI) | Base de conocimiento centralizada. `ghcr.io/vectorize-io/hindsight:latest` con pg0 embebido + DeepSeek V4 Flash via OpenCode Go. Banks versionados en `infrastructure/hermes/banks/`. |
| Integration | Composio | Pasarela de autenticacion OAuth para integraciones externas. Activo. |
| Knowledge Publishing | kb-mcp (servidor propio, Python + FastMCP) | Publica bases de conocimiento de `kb-template` como servidores MCP de solo lectura. Busqueda hibrida (SQLite FTS5/BM25 + embeddings estaticos model2vec + grafo de wikilinks) sin GPU ni LLM interno. Activo. |

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

**Status:** ✅ Implementado y operativo

**Purpose:** Actuar como punto de entrada conversacional persistente para procesar ordenes, rutear mensajes de grupo WhatsApp a perfiles determinísticamente, y coordinar subagentes asincronos.

**Interface:**
```
 WhatsApp -> bridge.js (inyecta [ROUTING] block) -> Hermes LLM (adopta perfil via RULE 0 en SOUL.md) -> responde o delega via Kanban
```

**Platforms activas:** WhatsApp (bot number 56936414929), WebUI (https://toolset-oci-1-1.tail2d4c18.ts.net:8787/).
**WhatsApp multi-group:** 6 grupos en comunidad "Hermes HUB": Chat, Code, Research, Personal, Hermes HUB (anuncios), + DM legacy.
**Deterministic routing:** `patch-bridge.sh` modifica bridge.js para inyectar `[ROUTING] profile=X scope=Y` en cada mensaje de grupo con perfil. El lookup es en código JS (bridge), no en LLM. El SOUL.md (RULE 0) fuerza al LLM a adoptar el perfil como identidad. Banks se derivan por convención: `{profile}-profile`. 0% LLM en decisión de ruteo.
**Worker profiles:** perfiles Hermes creados bajo demanda via `/onboarding` (3 fases MECE). Cada perfil tiene su SOUL.md con reglas operativas. El LLM adopta el perfil directamente (no via Kanban).
**Onboarding:** comando `/onboarding` en cualquier grupo WhatsApp. Crea Hindsight bank, genera profile SOUL.md desde `.agents/templates/profile-soul.md`, escribe `whatsapp-groups.yaml` con `profile:` y `scope:`. El bridge inyecta `[ROUTING]` automáticamente desde el próximo mensaje.
**WebUI deploy:** deploy.sh actualiza hermes-webui via `git pull --ff-only` en cada deploy.
**MCP servers:** hindsight-selfhosted (36 tools), composio (7 tools).
**Memory bank:** hermes (Hindsight, ~0 facts canonical v1). Por perfil: `{profile}-profile`.
**Bank discovery:** deploy.sh descubre banks desde `infrastructure/hermes/banks/` y los crea en Hindsight si no existen.
**Modelo default:** deepseek-v4-flash via OpenCode Go.
**Resiliencia de proveedor:** `fallback_providers` declara la cadena `qwen3.7-plus → minimax-m3` en formato `{provider, model}` (una cadena suelta se descarta en silencio; el estado efectivo se lee con `hermes fallback list`, no del YAML). `providers.opencode-go.stale_timeout_seconds: 90` acota la espera del vigilante de stream cuando el proveedor no entrega el primer token. Las tareas auxiliares (títulos, compresión, curador, aprobaciones, vision) apuntan explícitamente a `opencode-go` para no cascadear a proveedores sin credencial. Cada tenant repite esta configuración en su propio `config.yaml`.
**SOUL.md:** RULE 0 en inglés para procesamiento de `[ROUTING]`. Default identity solo para DM/grupos sin perfil.
**context.md (AGENTS.md):** Contexto operacional del proyecto. Cargado como context file de Hermes via auto-descubrimiento.
**External skills:** Dos directorios vía `external_skills_dirs`: `/opt/toolset-repo/infrastructure/hermes-skills/` y `/opt/toolset-repo/.agents/skills/`.
**Configuration manifest:** Todos los archivos de configuracion de Hermes se trackean en `infrastructure/hermes/INFRASTRUCTURE-MANIFEST.md`.

**MCP Lifecycle:**
1. deploy.sh sincroniza SOUL.md y context.md al servidor.
1b. deploy.sh copia `whatsapp-groups.yaml` a `~/.hermes/` y ejecuta `populate-channel-aliases.sh`.
1c. deploy.sh ejecuta `patch-bridge.sh` para aplicar parches de descripción y `[ROUTING]`.
1d. deploy.sh verifica que bridge.js generado sea sintácticamente válido (`node --check`).
2. inject-composio-key.py actualiza config.yaml.
3. Gateway se reinicia (`systemctl kill -s KILL` + `systemctl start`).
4. Health check verifica que el gateway responda activamente.
5. preflight.sh verifica invariantes POST-deploy (git state limpio, bridge injection, MCP E2E via Kilo CLI, Kanban config, perfiles, WebUI).
6. Si preflight falla → notificar inmediatamente al canal de deploy.

**Dependencies:** Tailscale, Infisical, Docker (sandbox), Hindsight, Composio, OpenCode Go.

---

### 7.2. kb-mcp: Publicacion de Bases de Conocimiento por MCP

**Status:** ✅ Implementado y operativo (2026-07-23)

**Purpose:** Exponer bases de conocimiento construidas con `kb-template` como servidores
MCP de solo lectura, para que un agente (claude.ai, Claude Code, Hermes) las consulte sin
que nadie pegue texto a mano. Aisla al que consulta de la topologia interna de la KB.

**Interface:**
```
 Agente MCP -> Tailscale Funnel :443 -> Caddy (handle_path /kb/*) -> kb-mcp:8765
              -> /kb/<slug>/mcp   (slug = nombre del repositorio de la KB)
```

**Superficie:** tres herramientas: `consultar` (busqueda), `leer` (texto integro de una
entrada), `panorama` (inventario o mapa de un tema). **Ninguna escribe.**

**Multi-KB:** un solo proceso sirve todas las KB bajo `/opt/kb`, con el modelo de
embeddings cargado una vez. No hay KB por defecto en la raiz: la ruta siempre nombra la
base. Sirviendo hoy: `traza-ambiental` (175 nodos) y `personal` (129).

**Recuperacion:** fusion reciproca ponderada de cuatro señales (nombre, semantica
(model2vec 256d int8), lexica (FTS5/BM25 con stemmer español), difusion por el grafo de
wikilinks) mas recencia por historial git como multiplicador con decaimiento exponencial.
Sin RAG vectorial pesado, sin torch, sin GPU, sin LLM interno. ~850 MB RAM.

**Auto-descripcion:** el servidor declara su dominio en las `instructions` y en la
cabecera de cada herramienta, combinando lo que la KB declara (`kb/mcp.yaml`) con los
conceptos centrales deducidos del grafo. Basta la URL: el agente no necesita que se le
explique de que trata la base.

**Ciclo de vida del indice — el acoplamiento que decidia que modelo se podia usar, y ya no.**
Hasta el 2026-08-19 el indice semantico solo se reconstruia **al arrancar el proceso**, y
`infrastructure/kb-mcp/sync-kb.sh` **reiniciaba el contenedor cada vez que el contenido de alguna KB
cambiaba**. Las dos decisiones vivian en archivos distintos y se multiplicaban: el costo de arranque
se pagaba tantas veces por dia como commits hubiera. Medido el 2026-08-07 sobre `kb-okos`:
**28 reinicios en una jornada**, o sea ~14 min diarios de servicio caido con un codificador real.

Eso ya no ocurre: el servidor **recarga el indice EN CALIENTE** por senal, sin reiniciar el
contenedor y sin dejar de contestar mientras rearma — medido el 2026-08-19 con 60 sondeos durante
una recarga completa: 59 respuestas limpias de 0,14 s y una sola lenta, ninguna caida. El
acoplamiento entre «que codificador se puede pagar» y «cuantas veces se reinicia» quedo cortado, y
la sincronizacion la dispara ahora la publicacion misma (el gancho `pre-push` de la KB llama a
`kb-sync-ahora`), con el cron de cada minuto como red. El parrafo de abajo describe el mundo
anterior y se conserva porque explica POR QUE existe el cache de vectores. Con la tabla
estatica el arranque es instantaneo y el acoplamiento es invisible; con un codificador real cuesta
~30 s por arranque, o sea ~14 min diarios de servicio caido. Por eso el servidor cachea los vectores
por hash del texto (`KB_VECTORES`): un reinicio recalcula solo lo que cambio. Sin esa variable —o sin
volumen de escritura, que es el estado de hoy: el contenedor va `read_only`— el comportamiento es el
de siempre, recalcular todo. Ver [HEU-013](MEMORY.md).

**Autorizacion:** ⚠️ Hoy **sin autenticacion**. La ruta es publica via Funnel y las KB no
estan aisladas entre si. El enrutamiento por nombre de repo esta diseñado para admitir
una capa de tokens por KB, que es trabajo pendiente ([DT-011](TECHNICAL-DEBT.md)).

**Documento canonico:** [`infrastructure/kb-mcp/README.md`](../infrastructure/kb-mcp/README.md).
Portado a la plantilla en `kb-template/tools/kb-mcp/` para que las KB nuevas lo hereden.

**Dependencies:** Docker, Caddy, Tailscale Funnel, credenciales `gh` en el VPS (las KB
son repos privados), modelo pre-cuantizado en `/opt/kb-modelo-256`.

---

## §8. Operational Rules

> How the AI agent should operate within this repository.

**Rules location:** [docs/RULES.md](file:///home/kirlts/toolset/docs/RULES.md)

**Scope:** Todas las operaciones del agente en el repositorio.
