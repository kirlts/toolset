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
- [x] Desplegar instancia de cómputo VM.Standard.A1.Flex (2 OCPU, 12 GB RAM, 100 GB boot, OL9 ARM64) usando OpenTofu + cloud-init. 2026-06-22 [🤖 Verified by tool]
- [x] Configurar Tailscale para red privada. Nodo `toolset-oci-1` conectado via auth key reusable. 2026-06-22 [🤖 Verified by tool]
- [x] Cerrar puerto SSH público — solo accesible desde VCN (10.0.0.0/16). Acceso real via Tailscale. 2026-06-22 [🤖 Verified by tool]
- [x] Configurar keepalive cron para evitar reclamation de OCI Always Free. 2026-06-22 [🤖 Verified by tool]
- [x] Configurar remote state en OCI Object Storage (bucket `toolset-opentofu-state`, sync via OCI CLI en pipeline). 2026-06-22 [🤖 Verified by tool]

---

## [EPIC-003] Gestión de Secretos y Sandboxing

> Ref: MASTER-SPEC §3, §4

### [TASK-005] Despliegue de Infisical y Daytona

**Covered checks:** `[DEV.CR.05.LLM]`, `[DEV.CR.06.LLM]`

- [x] Investigar métodos de instalación self-hosted de Infisical en OCI ARM64. Desplegado con PostgreSQL 16 + Redis 7 como dependencias. 2026-06-22 [🤖 Verified by tool]
- [x] Desplegar Infisical self-hosted en Docker Compose. Admin `martin.gil.o@gmail.com` creado via web UI. 2026-06-22 [🤖 Verified by tool]
- [ ] Configurar Infisical con proyectos, entornos y secrets para uso de Hermes y Daytona.
- [ ] Investigar cómo desplegar Daytona en ARM64 con Docker-in-Docker en Oracle Linux 9.
- [ ] Configurar el entorno de micro-contenedores aislados de Daytona.

---

## [EPIC-004] Orquestación y Mensajería

> Ref: MASTER-SPEC §7.1

### [TASK-006] Despliegue de Hermes Agent

**Covered checks:** `[DEV.CR.07.LLM]`, `[USER.FN.04.HUM]`

- [ ] Investigar frameworks viables para Hermes Agent (LangChain, CrewAI, AutoGPT, etc.) en entorno ARM64.
- [ ] Investigar métodos de integración con plataformas de mensajería (WhatsApp/Discord) para recepción y envío de comandos.
- [ ] Definir la arquitectura técnica interna de Hermes (subagentes, delegación, estado).
- [ ] Implementar el agente y configurarlo como servicio persistente en Docker Compose.
- [ ] Integrar Hermes con Infisical para inyección de secrets en tiempo de ejecución.

---

## [EPIC-005] Soberanía de Memoria

> Ref: MASTER-SPEC §4

### [TASK-007] Migración de Hindsight a Self-hosted en OCI

**Covered checks:** `[DEV.CR.08.MIX]`

- [x] Investigar despliegue self-hosted de Hindsight. **Resultado:** Viable vía `ghcr.io/vectorize-io/hindsight:latest` (ARM64 soportado). Modo standalone con pg0 embebido (no requiere pgvector externo). 2026-06-22 [🤖 Verified by tool]
- [x] Desplegar Hindsight (`ghcr.io/vectorize-io/hindsight:latest`) en Docker Compose junto a PostgreSQL, Redis, Infisical. 2026-06-22 [🤖 Verified by tool]
- [x] Configurar LLM API key (OpenCode Go + DeepSeek V4 Flash) en Hindsight vía `OPENCODE_GO_API_KEY`. 2026-06-22 [🤖 Verified by tool]
- [x] Crear `infrastructure/docker-compose.yml` canónico en repo con healthchecks en todos los servicios. 2026-06-22 [🤖 Verified by tool]
- [x] Crear `infrastructure/deploy.sh` — script de despliegue CI/CD que transfiere compose + .env + verifica health. 2026-06-22 [🤖 Verified by tool]
- [x] Extender `.github/workflows/deploy.yml` con job `deploy-services` vía Tailscale + SSH. 2026-06-22 [🤖 Verified by tool]
- [x] Añadir `SSH_PRIVATE_KEY` a GitHub Secrets para acceso CI/CD. 2026-06-22 [🤖 Verified by tool]
- [x] Configurar MCP self-hosted en Kilo Code (deshabilitado hasta migración). 2026-06-22 [🤖 Verified by tool]
- [x] Migrar el bank "toolset" desde hindsight cloud al self-hosted en OCI sin perder contexto. 2026-06-22 [🤖 Verified by tool]
  - Exportado: 14 documentos, 72 facts, 56 observaciones via `document-transfer`.
  - Importado: mismo conteo verificado en self-hosted.
  - Recall funcional: 119 resultados retornados.
- [x] Activar MCP self-hosted en Kilo Code y desactivar cloud (post-migración). 2026-06-22 [🤖 Changed in kilo.jsonc]
  - `hindsight-selfhosted`: activo, URL via Funnel.
  - `hindsight-toolset` + `hindsight-cl-concerts`: desactivados (`disabled: true`).

---

## [EPIC-006] Próximos Pasos — Investigación

> Ref: MASTER-SPEC §2 (Fase 2), §4

### [TASK-008] Tailscale Funnel y Webhooks

- [x] Investigar cómo configurar Tailscale Funnel para recepción de webhooks desde GitHub y otras plataformas. 2026-06-22 [🤖 Verified by tool]
- [x] Habilitar Funnel en Tailscale admin console. 2026-06-22 [🧑 Habilitado por usuario]
- [x] Configurar Funnel en OCI: `tailscale funnel --bg http://localhost:8888` — expone Hindsight API/MCP vía HTTPS público en `https://toolset-oci-1.tail2d4c18.ts.net/mcp/`. 2026-06-22 [🤖 Verified by tool]
- [ ] Configurar webhooks de GitHub hacia Hindsight/Infisical usando el Funnel como endpoint.

### [TASK-009] Integración Infisical con Servicios

- [ ] Investigar API de Infisical para inyección de secrets en contenedores Docker (sin archivos .env).
- [ ] Configurar proyecto y entorno en Infisical para Toolset.

### [TASK-010] Hardening de Seguridad

- [ ] Investigar cómo habilitar Tailscale SSH en Oracle Linux 9 con SELinux activo.
- [ ] Resolver DT-001: Token Exchange OIDC Identity Propagation Trust para GitHub Actions.
- [ ] Eliminar API key estática del pipeline CI/CD (reemplazar por OIDC).

---

## Overall Coverage Summary

| Epic | Tasks | Status | 🤖 .LLM | 🧑 .HUM | 🤖🧑 .MIX | Total Checks |
| --- | --- | --- | --- | --- | --- | --- |
| EPIC-001 | TASK-001 a TASK-003 | Completed | 4 | 1 | 0 | 5 |
| EPIC-002 | TASK-004 | Completed | 2 | 1 | 0 | 3 |
| EPIC-003 | TASK-005 | In Progress | 2 | 0 | 0 | 2 |
| EPIC-004 | TASK-006 | Pending | 1 | 1 | 0 | 2 |
| EPIC-005 | TASK-007 | Completed | 8 | 0 | 1 | 9 |
| EPIC-006 | TASK-008 a TASK-010 | In Progress | 1 | 1 | 0 | 2 |
| **TOTAL** | | | **17** | **4** | **1** | **22** |
