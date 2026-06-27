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

### [TASK-005] Despliegue de Infisical

**Covered checks:** `[DEV.CR.05.LLM]`

- [x] Investigar métodos de instalación self-hosted de Infisical en OCI ARM64. Desplegado con PostgreSQL 16 + Redis 7 como dependencias. 2026-06-22 [🤖 Verified by tool]
- [x] Desplegar Infisical self-hosted en Docker Compose. Admin `martin.gil.o@gmail.com` creado via web UI. 2026-06-22 [🤖 Verified by tool]
- [x] Configurar Infisical con proyectos, entornos y secrets para uso de Hermes. 2026-06-22 [🤖 Verified by tool]
- [ ] Integrar Infisical Agent con Hermes para inyección de secrets en runtime.

---

## [EPIC-004] Orquestación y Mensajería

> Ref: MASTER-SPEC §7.1

### [TASK-006] Despliegue de Hermes Agent

**Covered checks:** `[DEV.CR.06.LLM]`, `[DEV.CR.07.LLM]`, `[DEV.CR.13.LLM]`, `[USER.FN.04.HUM]`

- [x] Investigar Hermes Agent (Nous Research) — framework OSS real con sandbox Docker nativo, subagentes asíncronos, v0.15.0 (May 2026). 2026-06-22 [🤖 Verified by tool]
- [x] Investigar sandbox backend: comunidad usa Docker nativo (`terminal.backend: docker`) con hardening automático. Daytona/Modal/Vercel como backends alternativos configurables. 2026-06-22 [🤖 Verified by tool]
- [x] Daytona eliminado del stack — Hermes usa sandbox Docker nativo. 2026-06-22 [🧑 UD-011]
- [x] Investigar métodos de integración con plataformas de mensajería (WhatsApp/Discord). Confirmado: Baileys bridge para WhatsApp, adapter nativo para Discord. 2026-06-23 [🤖 Verified by tool]
- [x] Definir la arquitectura técnica interna de Hermes (subagentes, delegación, estado). Documentado en Hermes-integration.md. 2026-06-23 [🤖 Verified by tool]
- [x] Investigar conexión Kilo Code → Hermes. Resultado: **Kilo Code CLI existe** (`@kilocode/cli` npm package) — `kilo run --auto`, autonomous mode, ACP server, MCP server, mismo config que Kilo local. 2026-06-23 [🤖 Verified by official docs + Reddit via Composio]
- [x] Investigar Hindsight como memory provider externo de Hermes. Confirmado: plugin nativo `hermes memory setup → hindsight`. 2026-06-23 [🤖 Verified by official docs]
- [x] LVM disk extend: cloud-init.yaml (growpart + lvextend + xfs_growfs) + deploy.sh (idempotent check). ✅ Verificado: root 30GB→83GB, 96%→35%. 2026-06-23 [🤖 Verified by deploy]
- [x] Implementar Hermes Agent como servicio persistente (systemd, no Docker). ✅ v0.17.0, gateway active, Docker backend. 2026-06-23 [🤖 Verified by deploy]
- [x] Integrar Hermes con Infisical para inyección de secrets en tiempo de ejecución. ✅ vía .env + sync_secret. 2026-06-23 [🤖 Verified by deploy]
- [x] Configurar Hindsight como memory provider en Hermes (`hermes memory setup`). ✅ MCP 36 tools + bank hermes. 2026-06-23 [🤖 Verified by deploy]
- [x] Configurar WhatsApp (Baileys bridge) bot number. ✅ Bot number 56936414929, allowlist ambos números. 2026-06-23 [🤖 Verified by user]
- [x] Configurar Tailscale Funnel para Hermes WebUI (:8787). ✅ Funnel activo. 2026-06-23 [🤖 Verified by deploy]
- [x] Integrar Composio MCP como servidor MCP en Hermes config. ✅ ck_ key, 7 tools registrados. 2026-06-23 [🤖 Verified by deploy]
- [x] Verificar integración Hermes → Hindsight (MCP), Hermes → Composio (MCP). ✅ 43 tools, 0 failures. 2026-06-23 [🤖 Verified by deploy]
- [x] Instalar Kilo CLI (`npm install -g @kilocode/cli`) en VPS. ✅ v7.3.54. 2026-06-23 [🤖 Verified by deploy]
- [x] Sync `~/.config/kilo/kilo.jsonc` al VPS (mismos providers, MCPs, permissions). ✅ 2026-06-23 [🤖 Verified by deploy]
- [x] Instalar gh CLI para operaciones Git/GitHub. ✅ v2.95.0, autenticado como kirlts. 2026-06-23 [🤖 Verified by deploy]
- [x] Crear y seedear bank "hermes" en Hindsight. ✅ 30 facts de identidad. 2026-06-23 [🤖 Verified by deploy]
- [x] Configurar SOUL.md con contexto completo (identidad, reglas, memoria, herramientas). ✅ 116 líneas. 2026-06-23 [🤖 Verified by deploy]
- [x] Auditoría exhaustiva CI/CD: 10+ correcciones aplicadas (comillas, if/fi, secrets, sudo, etc.). ✅ Pipeline verde. 2026-06-23 [🤖 Verified by deploy]
- [x] Crear skill de Hermes para delegar tareas pesadas a `kilo run --auto`. ✅ Creada en infrastructure/hermes-skills/kilo-code/. 2026-06-26 [🤖 Verified by tool]
- [x] Test flujo completo: WhatsApp → clonar repo → responder pregunta. ✅ Hermes clonó researchit y contó 8 archivos .py. 2026-06-26 [🤖 Verified via hermes -z]
- [x] Test `kilo run "Run tests" --auto` desde terminal VPS. ✅ Ejecutó python3 hello.py → "hello world". 2026-06-26 [🤖 Verified via SSH]
- [x] Implementar model discovery: No necesario. El stack usa exclusivamente deepseek-v4-flash via OpenCode Go. No hay selección de modelos. 2026-06-26 [🔄 Cerrado por decisión arquitectónica]

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
- [x] [TASK-007]; 2026-06-26 12:15 [🤖🧑 Pre-verified + confirmed by user]

---

## [EPIC-006] Próximos Pasos — Investigación

> Ref: MASTER-SPEC §2 (Fase 2), §4

### [TASK-008] Tailscale Funnel y Webhooks

**Covered checks:** `[DEV.CR.09.LLM]`

- [x] Investigar cómo configurar Tailscale Funnel para recepción de webhooks desde GitHub y otras plataformas. 2026-06-22 [🤖 Verified by tool]
- [x] Habilitar Funnel en Tailscale admin console. 2026-06-22 [🧑 Habilitado por usuario]
- [x] Configurar Funnel en OCI: apunta a Caddy (`http://localhost:8080`) que enruta por path a cada servicio. 2026-06-22 [🤖 Verified by tool]
- [x] Implementar Caddy reverse proxy multi-servicio (Hindsight API/MCP/CP, Infisical, landing page). 2026-06-22 [🤖 Verified by tool]
- [x] Reestructurar Caddyfile: catch-all a landing page, Infisical en /api/*, rutas CP específicas. 2026-06-22 [🤖 Verified by tool]
- [x] Segundo Funnel en :8443 para Infisical UI (evita conflicto _next/* con CP). 2026-06-22 [🤖 Verified by tool]
- [x] `deploy.sh` imprime tabla de URLs completa post-deploy. 2026-06-22 [🤖 Verified by tool]
- [x] Arreglar CI/CD pipeline: Caddy healthy independiente de Infisical, deploy-services pasa. 2026-06-22 [🤖 Verified by tool]
- [ ] Configurar webhooks de GitHub hacia Hindsight/Infisical usando el Funnel como endpoint.

### [TASK-009] Integración Infisical con Servicios

**Covered checks:** `[DEV.CR.10.LLM]`

- [ ] Investigar API de Infisical para inyección de secrets en contenedores Docker (sin archivos .env).
- [ ] Configurar proyecto y entorno en Infisical para Toolset.

### [TASK-010] Hardening de Seguridad

**Covered checks:** `[DEV.CR.11.LLM]`, `[DEV.CR.12.LLM]`

- [ ] Investigar cómo habilitar Tailscale SSH en Oracle Linux 9 con SELinux activo.
- [ ] Resolver DT-001: Token Exchange OIDC Identity Propagation Trust para GitHub Actions.
- [ ] Eliminar API key estática del pipeline CI/CD (reemplazar por OIDC).

---

### [TASK-011] Estrategia de autenticación para URLs de gestión vía Funnel

**Covered checks:** `Transversal governance`

> Ref: DT-002. Una vez Hermes esté operativo (TASK-006), definir e implementar autenticación.

- [ ] Definir qué URLs requieren auth (gestión: Infisical, Hindsight CP, Hermes) y cuáles quedan públicas (observabilidad: health, API, MCP).
- [ ] Implementar auth: Caddy `basicauth` por path o forward auth con Infisical.
- [ ] Verificar que harnesses (Kilo Code, Claude Code) puedan conectar a MCP sin auth.

---

## Overall Coverage Summary

| Epic | Tasks | Status | 🤖 .LLM | 🧑 .HUM | 🤖🧑 .MIX | Total Checks |
| --- | --- | --- | --- | --- | --- | --- |
| EPIC-001 | TASK-001 a TASK-003 | Completed | 4 | 1 | 0 | 5 |
| EPIC-002 | TASK-004 | Completed | 1 | 1 | 0 | 2 |
| EPIC-003 | TASK-005 | In Progress | 1 | 0 | 0 | 1 |
| EPIC-004 | TASK-006 | In Progress | 3 | 1 | 0 | 4 |
| EPIC-005 | TASK-007 | Completed | 0 | 0 | 1 | 1 |
| EPIC-006 | TASK-008 a TASK-011 | In Progress | 4 | 0 | 0 | 4 |
| **TOTAL** | | | **13** | **3** | **1** | **17** |
