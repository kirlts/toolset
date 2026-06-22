# TODO: Toolset Personal v0.1.0

> Trazabilidad directa: cada tarea referencia checks de `VERIFICATION.md`.

## Kairós Symbol Legend

| Symbol | Meaning |
|---|---|
| 🤖 | Check verificable por IA / herramienta automatica |
| 🧑 | Check que requiere verificacion humana |
| 🤖🧑 | Check pre-verificable por IA, con validacion humana final |
| ⏳ | En progreso |
| 🔲 | Pendiente |
| 🚨 | Bloqueo critico |

---

## [EPIC-001] Repositorio e Integracion de Workspace

> Ref: MASTER-SPEC §1, §3

### [TASK-001] Inicializacion de Git

> Ref: MASTER-SPEC §1

**Covered checks:** `[USER.FN.02.HUM]`

- [x] Inicializar repositorio local git en /home/kirlts/toolset 2026-06-21 20:30:00 [🧑 Verified by user]

---

### [TASK-002] Integracion de Composio y Hindsight MCP

> Ref: MASTER-SPEC §3

**Covered checks:** `[DEV.CR.01.LLM]`, `[USER.FN.01.LLM]`, `[DEV.CR.03.LLM]`

- [x] Configurar Composio en mcp_config.json 2026-06-21 20:45:00 [🤖 Verified by tool]
- [x] Configurar Hindsight en mcp_config.json 2026-06-21 21:53:00 [🤖 Verified by tool]
- [x] Verificar conexion de Hindsight via RPC tools/list y recall 2026-06-21 21:55:00 [🤖 Verified by tool]

---

### [TASK-003] Inicializacion de Documentacion Kairos

> Ref: MASTER-SPEC §1, §8

**Covered checks:** `[DEV.CR.02.LLM]`

- [x] Crear estructura de archivos obligatorios en docs/ 2026-06-21 21:55:00 [🤖 Verified by tool]

---

## [EPIC-002] Infraestructura Base Cloud y Red Privada

> Ref: MASTER-SPEC §3

### [TASK-004] Investigación y Aprovisionamiento OCI

**Covered checks:** `[DEV.CR.04.LLM]`, `[USER.FN.03.HUM]`

- [x] Investigar requisitos técnicos exactos y generar configuración (ej. OpenTofu) para OCI. 2026-06-22 05:40:00 [🤖 Verified by tool]
- [⚠️] Configurar Workload Identity Federation (Identity Propagation Trust) para GitHub Actions. Trust creado pero token exchange no funcional — ver TECHNICAL-DEBT.md. 2026-06-22 06:30:00 [🤖 Verified by tool]
- [x] Desplegar red base (VCN y Subnet) usando OpenTofu. 2026-06-22 05:40:00 [🤖 Verified by tool]
- [x] Pipeline CI/CD funcional con autenticación API key (puente temporal). 2026-06-22 06:36:00 [🤖 Verified by tool]
- [ ] Desplegar instancia de cómputo base y validar que los puertos públicos estén cerrados.
- [ ] Investigar y configurar Tailscale para crear la red privada.

---

## [EPIC-003] Gestión de Secretos y Sandboxing

> Ref: MASTER-SPEC §3, §4

### [TASK-005] Despliegue de Infisical y Daytona

**Covered checks:** `[DEV.CR.05.LLM]`, `[DEV.CR.06.LLM]`

- [ ] Investigar métodos de instalación self-hosted viables en el servidor OCI para ambos servicios.
- [ ] Implementar gestor de secretos sin depender de archivos .env persistentes.
- [ ] Configurar el entorno de micro-contenedores aislados de Daytona.

---

## [EPIC-004] Orquestación y Mensajería

> Ref: MASTER-SPEC §7.1

### [TASK-006] Despliegue de Hermes Agent

**Covered checks:** `[DEV.CR.07.LLM]`, `[USER.FN.04.HUM]`

- [ ] Definir la arquitectura técnica interna de Hermes.
- [ ] Investigar métodos de integración con plataformas de mensajería (WhatsApp/Discord).
- [ ] Implementar el agente y configurarlo como servicio persistente.

---

## [EPIC-005] Soberanía de Memoria

> Ref: MASTER-SPEC §4

### [TASK-007] Migración a Hindsight Self-hosted

**Covered checks:** `[DEV.CR.08.MIX]`

- [ ] Investigar el despliegue del binario/docker de Hindsight (vectorize.io) en modo self-hosted.
- [ ] Realizar la migración de la base de conocimiento actual al entorno en OCI sin perder el contexto.

---

## Overall Coverage Summary

| Epic | Tasks | Status | 🤖 .LLM | 🧑 .HUM | 🤖🧑 .MIX | Total Checks |
| --- | --- | --- | --- | --- | --- | --- |
| EPIC-001 | TASK-001 a TASK-003 | Completed | 4 | 1 | 0 | 5 |
| EPIC-002 | TASK-004 | In Progress | 1 | 1 | 0 | 2 |
| EPIC-003 | TASK-005 | In Progress | 2 | 0 | 0 | 2 |
| EPIC-004 | TASK-006 | In Progress | 1 | 1 | 0 | 2 |
| EPIC-005 | TASK-007 | In Progress | 0 | 0 | 1 | 1 |
| **TOTAL** | | | **8** | **3** | **1** | **12** |
