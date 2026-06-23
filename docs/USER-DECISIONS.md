# USER-DECISIONS: Human Agency Record

> Este documento no es un changelog. Registra las decisiones estrategicas y la soberania del usuario.

| Symbol | Meaning |
|---|---|
| 💡 | Decision estrategica del usuario |
| 🔗 | Referencia cruzada a checks de tipo `.HUM` |

---

## [UD-001] Uso de Composio para la conectividad de Workspace

**Date:** 2026-06-21

**Context:** El intento inicial de configurar el servidor MCP de Google Drive local fallo debido a un error redirect_uri_mismatch en la consola de Google Cloud, causado por la incompatibilidad de credenciales de tipo Escritorio con la redireccion remota del agente.

**Decision:** El usuario decidio utilizar Composio.io como pasarela de integracion y autenticacion global de MCP para obviar la complejidad de configuracion local de redireccion de OAuth de Google Cloud.

**Discarded alternatives:**
- Configurar un servidor web local con callback publico para manejar el flujo OAuth (descartado por alta complejidad y requerimientos de mantenimiento).

**Consequences:**
- Se logro acceso inmediato a las herramientas de Google Drive mediante el token global de Composio.
- Se introduce una dependencia de red con Composio.io.

**Reversion conditions:** Cambios en el modelo de precios de Composio, fallos de disponibilidad continuos o politicas de seguridad corporativas que prohiban el uso de gateways externos.

---

## [UD-002] Integracion de Hindsight como MCP Server de Memoria Centralizada

**Date:** 2026-06-21

**Context:** Para garantizar la consistencia y persistencia del contexto e historial de desarrollo del Toolset entre las workstations locales y las instancias en la nube (OCI), se requiere una memoria centralizada compartida.

**Decision:** El usuario decidio agregar y configurar Hindsight (vectorize.io) como un servidor MCP HTTP persistente con token de autorizacion Bearer estatico.

**Discarded alternatives:**
- Almacenamiento local de transcripciones y sincronizacion manual mediante scripts de rsync (descartado por riesgo de fragmentacion y conflictos de sincronizacion).

**Consequences:**
- Las workstations (Claude Code/Kilo Code) y el agente en la nube (Hermes) consultan y actualizan la misma base de conocimiento en tiempo real.
- Dependencia del servicio Hindsight (vectorize.io).

**Reversion conditions:** Migracion a un modelo vectorial auto-hospedado (self-hosted vector database) en OCI en caso de requerir offline completo o mayor privacidad de datos.

---

## [UD-003] Workload Identity Federation (OIDC) para GitHub Actions

**Date:** 2026-06-22

**Context:** El paso de credenciales de seguridad entre GitHub y OCI tradicionalmente requería almacenar claves privadas (.pem) de larga duración como secretos de repositorio, lo que aumenta la superficie de ataque y rompe el patrón de cero confianza (Zero Trust). Además, el aprovisionamiento de OCI requería limpiar VCNs heredadas que la Web UI bloqueaba.

**Decision:** El usuario delegó al sistema la eliminación forzada de los recursos limitantes mediante `oci` CLI local, y aprobó la implementación de *Identity Propagation Trust* para federar GitHub Actions. OpenTofu asume credenciales inyectadas sin estado persistente.

**Discarded alternatives:**
- Almacenar la llave privada en los Secretos de GitHub (descartado por mala práctica de seguridad).
- Utilizar el proveedor de Terraform para dominios de identidad OCI (descartado debido a un error crítico `400-BadErrorResponse` del proveedor para estos recursos).

**Consequences:**
- Las rotaciones de credenciales de CI/CD ya no son necesarias.
- Se ha eliminado la dependencia de interfaces de usuario propensas a errores para la limpieza de infraestructura pesada.

**Reversion conditions:** Cambio a otra plataforma CI/CD distinta de GitHub Actions que no soporte OIDC nativo, o si Oracle depreca la API de Identity Propagation Trust.

---

## [UD-004] API Key como puente temporal para CI/CD ante falla de OIDC

**Date:** 2026-06-22

**Context:** Tras configurar exitosamente la Confidential App y el Identity Propagation Trust en OCI, el token exchange desde GitHub Actions contra `/oauth2/v1/token` del dominio retornó repetidamente `invalid_request`. Se probaron grant types `urn:ietf:params:oauth:grant-type:token-exchange` y `urn:ietf:params:oauth:grant-type:jwt-bearer`, con Basic auth y form params, con audiencia `oci` y con la URL del token endpoint. Ninguna combinación funcionó.

**Decision:** Para destrabar el pipeline, se optó por almacenar una API key del usuario `svc_github_actions` como secret de GitHub (`OCI_API_KEY`). La autenticación del pipeline CI/CD funciona con API key mientras se resuelve el flujo OIDC.

**Discarded alternatives:**
- Seguir debugueando el exchange OIDC sin fecha de resolución clara (descartado por bloqueo del avance del proyecto).

**Consequences:**
- El pipeline de OpenTofu despliega contra OCI exitosamente.
- Se introduce una llave estática que debe rotarse manualmente (en contra del principio Zero Trust de UD-003).
- La infraestructura OIDC (Trust, Confidential App) queda configurada y lista para reactivarse cuando se resuelva el exchange.

**Reversion conditions:** Resolver el token exchange OIDC, eliminar el secret `OCI_API_KEY` del repositorio, y restaurar el flujo de Identity Propagation Trust.

---

## [UD-005] Instancia ARM (A1.Flex) en lugar de AMD (E2.1.Micro)

**Date:** 2026-06-22

**Context:** La instancia VM.Standard.E2.1.Micro (AMD, 1 GB RAM) era insuficiente para el stack Toolset (Hindsight, Infisical, Daytona, Hermes). Se requería al menos 12 GB de RAM para operar todos los servicios.

**Decision:** Desplegar VM.Standard.A1.Flex (Ampere ARM) con 2 OCPU y 12 GB RAM, el máximo permitido en el Always Free Tier de OCI.

**Discarded alternatives:**
- Usar dos instancias E2.1.Micro (1 GB cada una) y distribuir servicios (descartado: 1 GB es insuficiente para cualquier servicio individual del stack).

**Consequences:**
- Stack completo cabe en una sola instancia con margen de recursos.
- ARM64 requiere imágenes Docker compatibles con arquitectura aarch64 (verificado: Docker, PostgreSQL, Redis, Infisical, Tailscale todos soportan ARM64).
- Oracle Linux Cloud Developer no disponible para ARM — se usó OL9 estándar.
- Disponibilidad de A1.Flex en sa-valparaiso-1 depende de capacidad del datacenter (riesgo en redeploy).

---

## [UD-006] Infisical con PostgreSQL en lugar de SQLite

**Date:** 2026-06-22

**Context:** La versión actual de Infisical (v0.161.3) no soporta SQLite como backend de base de datos. Requiere PostgreSQL obligatoriamente, además de Redis para caché/cola.

**Decision:** Agregar contenedores de PostgreSQL 16 y Redis 7 al Docker Compose como dependencias de Infisical.

**Discarded alternatives:**
- Usar una versión anterior de Infisical con soporte SQLite (descartado: riesgo de seguridad y falta de soporte).
- No desplegar Infisical hasta que sea necesario (descartado: el usuario quiere el stack completo listo).

**Consequences:**
- Stack de contenedores crece de 1 a 4 servicios (infisical, postgres, redis, + futuros).
- Consumo adicional de RAM/CPU aceptable dentro de los 12 GB disponibles.
- PostgreSQL y Redis usan imágenes Alpine optimizadas para ARM64.

---

## [UD-007] Hindsight auto-hosted en OCI como siguiente paso

**Date:** 2026-06-22

**Context:** El plan original (MASTER-SPEC §3) contemplaba migrar Hindsight a self-hosted en OCI. Se investigó y el Docker image `ghcr.io/vectorize-io/hindsight:latest` sí está disponible para ARM64. Requiere PostgreSQL 14+ con pgvector y una LLM API key.

**Decision:** Agregar Hindsight self-hosted al roadmap del Toolset. Migrar el bank "toolset" desde hindsight cloud al auto-hosted en OCI.

**Requirements:**
- Instalar extensión pgvector en PostgreSQL 16 existente.
- Configurar Hindsight con LLM provider (OpenAI / Groq / Ollama).
- Migrar datos del bank "toolset" desde cloud.
- Actualizar configuración MCP en Kilo Code.

**Consequences:**
- La migración de Hindsight a self-hosted elimina la dependencia del servicio cloud de vectorize.io.
- Permite completar la Fase 2 de soberanía de infraestructura.

---

## [UD-008] SSH público cerrado, acceso exclusivo por Tailscale

**Date:** 2026-06-22

**Context:** MASTER-SPEC §4.2 exige que ningún puerto del servidor OCI esté expuesto públicamente. El puerto SSH (22) estaba abierto como conveniencia temporal durante el bootstrap.

**Decision:** Restringir SSH entrante a solo la VCN (10.0.0.0/16). El acceso real se realiza vía Tailscale (IP 100.77.183.125).

**Discarded alternatives:**
- Cerrar SSH completamente y depender de Tailscale SSH (descartado: SELinux en OL9 bloquea Tailscale SSH; se requiere acceso de emergencia vía VCN).
- Usar OCI Bastion como alternativa (descartado: añade complejidad innecesaria cuando Tailscale ya funciona).

**Consequences:**
- El bootstrap de una instancia nueva requiere abrir SSH temporalmente (~5-8 min hasta que Tailscale conecte).
- Documentado como limitación conocida en la especificación del proyecto.

---

## [UD-009] Hindsight self-hosted con pg0 embebido + OpenCode Go

**Date:** 2026-06-22

**Context:** Se investigó el despliegue self-hosted de Hindsight. La imagen `ghcr.io/vectorize-io/hindsight:latest` soporta modo standalone con base de datos embebida (pg0, SQLite-based), sin requerir PostgreSQL externo con pgvector. Para LLM provider se evaluaron OpenAI, Groq, DeepSeek directo, y OpenCode Go (suscripción existente).

**Decision:** Desplegar Hindsight en modo standalone (pg0 embebido) sin PostgreSQL externo. Usar OpenCode Go como LLM provider con modelo DeepSeek V4 Flash via endpoint OpenAI-compatible (`https://opencode.ai/zen/go/v1`). Migrar bank "toolset" desde hindsight cloud al self-hosted.

**Discarded alternatives:**
- PostgreSQL externo con pgvector (descartado: pg0 embebido es suficiente para single-dev, evita complejidad operativa).
- LLM directo DeepSeek (descartado: requería API key separada; OpenCode Go ya tiene suscripción activa).

**Consequences:**
- Hindsight self-hosted operativo sin base de datos adicional.
- DeepSeek V4 Flash cuesta $0.14/M tokens (más barato que OpenAI).
- Bank "toolset" migrado exitosamente (14 docs, 72 facts, 56 observaciones).
- MCP configurado en Kilo Code vía Tailscale Funnel.

**Reversion conditions:** Si pg0 no escala para el uso proyectado, migrar a PostgreSQL externo con pgvector.

---

## [UD-010] CI/CD pipeline extendido con deploy de servicios via SSH/Tailscale

**Date:** 2026-06-22

**Context:** El pipeline CI/CD solo gestionaba infraestructura OpenTofu. No había mecanismo para desplegar cambios en docker-compose.yml o secrets sin intervención manual SSH.

**Decision:** Extender el pipeline con job `deploy-services` que se conecta al servidor OCI via Tailscale + SSH, transfiere el docker-compose.yml canónico (desde el repo), genera .env desde GitHub Secrets, y ejecuta `docker compose pull && docker compose up -d` con verificación de healthchecks.

**Discarded alternatives:**
- Infisical Agent como sidecar para inyección de secrets (descartado: aumenta complejidad, los bootstrap secrets de Infisical ya están en GitHub Secrets).
- OCI Instance Agent runcommand (descartado: async, complejo de monitorear desde CI/CD).

**Consequences:**
- Sin gestión manual de archivos en el servidor — todo fluye por CI/CD.
- SSH_PRIVATE_KEY almacenada como GitHub Secret.
- Healthchecks nativos (no polling) en todos los servicios.

**Reversion conditions:** Migrar a autenticación OIDC cuando DT-001 esté resuelto.

---

## [UD-011] Daytona reemplazado por sandbox Docker nativo de Hermes Agent

**Date:** 2026-06-22

**Context:** Daytona se consideró inicialmente como plataforma de sandboxing para Hermes. Investigación reveló que: (a) Daytona OSS deploy requiere 9 servicios (PostgreSQL propio, MinIO, Registry, etc.) y dominio público, (b) la comunidad de Hermes Agent (r/hermesagent) usa Docker nativo como estándar, (c) Hermes tiene integración nativa con Docker hardening (no-new-privs, capabilities drop, tmpfs, network none).

**Decision:** Eliminar Daytona del stack. Hermes Agent usará su sandbox Docker nativo (`terminal.backend: docker`) con imagen efímera y hardening por defecto. Si en el futuro se necesita GPU o sandboxes persistentes cross-sesión, Hermes soporta Daytona Cloud, Modal, o Vercel Sandbox como backends intercambiables.

**Discarded alternatives:**
- Daytona OSS deploy en OCI (descartado: 9 servicios adicionales, no cabe en 12GB con el resto del stack).
- E2B (descartado: requiere Nomad+Consul, heavy ops).
- Beam beta9 (descartado: requiere Kubernetes).

**Consequences:**
- Menos servicios que operar en OCI.
- Hermes puede cambiar de backend sin cambiar código (solo config).
- Alineado con las mejores prácticas de la comunidad Hermes (r/hermesagent VPS megathread).

**Reversion conditions:** Si se requiere GPU en sandboxes o persistencia long-tail, evaluar Daytona Cloud como backend de Hermes.

---

## [UD-012] Tailscale Funnel como mecanismo de exposición pública para MCP

**Date:** 2026-06-22

**Context:** El MCP de Hindsight self-hosted en OCI era accesible solo via Tailscale IP (100.77.183.125:8888). Para que cualquier harness (Kilo Code, Claude Code, Hermes) se conecte sin Tailscale, se necesitaba exponer el endpoint vía HTTPS público.

**Decision:** Usar Tailscale Funnel para exponer Hindsight API/MCP en `https://toolset-oci-1.tail2d4c18.ts.net/`. Sin puertos abiertos en OCI (solo UDP 41641 de Tailscale). Habilitado desde admin console de Tailscale por el usuario.

**Discarded alternatives:**
- Caddy reverse proxy con certificados Let's Encrypt (descartado: requiere puerto 80/443 abierto, viola MASTER-SPEC §4.2).
- Tailscale Serve (solo dentro del tailnet, no resuelve el problema).

**Consequences:**
- Hindsight MCP accesible desde cualquier máquina sin Tailscale.
- Sin superficie de ataque adicional en OCI.
- Funnel se mantiene activo entre deploys (verificado en deploy.sh).
- La URL es pública (cualquiera puede intentar acceder), mitigado por oscuridad de la URL y formato MCP.

**Reversion conditions:** Si se requiere autenticación en el MCP, habilitar `HINDSIGHT_CP_ACCESS_KEY` en Hindsight y agregar header de Authorization en el MCP config.

---

## [UD-013] Bootstrap recovery + service token para Infisical CI/CD

**Date:** 2026-06-22

**Context:** Tras resolver DT-004 (ENCRYPTION_KEY corregida), la cuenta admin de Infisical requería registro manual desde la Web UI. Esto no es recuperable si la instancia OCI se redeploya en un volumen PostgreSQL fresco. Además, el pipeline CI/CD necesitaba una forma permanente de sincronizar secrets sin depender del JWT de sesión del admin (expira en 10 días).

**Decision:** Implementar dos mecanismos de resiliencia:
1. **Bootstrap automático**: deploy.sh llama `POST /api/v1/admin/bootstrap` en cada deploy con las credenciales de admin almacenadas en GitHub Secrets. Si ya existe admin → 400 "already set up" (seguro). Si no existe → crea admin + org automáticamente.
2. **Service token permanente**: Creado via `POST /api/v2/service-token` con JWT de admin, scoped al proyecto Toolset (dev + prod, read+write). Token de formato `st.*` almacenado como GitHub Secret `INFISICAL_SERVICE_TOKEN`.
3. **CI/CD sync automático**: deploy.sh usa el service token en cada deploy para sincronizar secrets de GitHub Secrets a Infisical (idempotente via POST upsert).

**Discarded alternatives:**
- SRP login via CLI (descartado: Infisical usa SRP para passwords, la CLI no puede loguearse sin resolver SRP, y el endpoint login1 falla con 500).
- Crear service token via DB directamente (descartado: el hash del token requiere formato específico no documentado).
- Identidad machine-to-machine con universal auth (descartado: requiere crear una identity primero, creando dependencia cíclica).

**Consequences:**
- Admin account recuperable en cualquier redeploy (bootstrap).
- Service token permanente permite CI/CD autónomo sin JWT de admin.
- Secrets en GitHub Secrets como fuente de verdad, Infisical como runtime.
- Para un volumen completamente fresco, el primer deploy crea admin + org; el service token falla hasta que se cree el proyecto manualmente.

**Reversion conditions:** Cambiar a OIDC para auth de CI/CD o a machine identities cuando Infisical madure el soporte.
