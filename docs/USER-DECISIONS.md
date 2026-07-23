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

---

## [UD-014] Remoción OIDC — DT-001 cerrado, API key estática permanente

**Date:** 2026-06-26
**Context:** El Identity Propagation Trust "GitHub Actions Toolset Trust" en OCI rechazó el JWT OIDC de GitHub para las 6 combinaciones de grant_type x token_type probadas.
**Decision:** Cerrar DT-001 como no resoluble sin OCI Console. Mantener API key estática como mecanismo permanente. Eliminar secrets OIDC (OCI_DOMAIN_URL, OCI_OAUTH_CLIENT_ID/SECRET) de GitHub Secrets.
**Consequences:** API key estática requiere rotación manual. No hay SSO para CI/CD.
**Discarded alternatives:** Debug en OCI Console (requiere intervención del usuario).

---

## [UD-015] GitHub Secrets como única fuente de verdad — sin variables, sin hardcodeo

**Date:** 2026-06-27
**Context:** Tras auditoría CI/CD, se determinó que usar GitHub Variables para FUNNEL_DOMAIN y hardcodear valores inconsistentemente causaba fractura en la fuente de verdad.
**Decision:** GitHub Secrets son la única fuente de verdad. FUNNEL_DOMAIN migrado de variable a secret. No hay ${{ vars.* }} en deploy.yml.
**Consequences:** Todos los valores sensibles y de configuración están en un solo lugar. Rotación consistente.

---

## [UD-016] Sin auth en rutas de Caddy/Hindsight CP

**Date:** 2026-06-27
**Context:** Caddy basicauth implementado inicialmente para Hindsight CP pero el usuario prefirió sin auth.
**Decision:** Eliminar todos los bloques basicauth del Caddyfile. Hindsight CP, dashboard y APIs son públicos.
**Consequences:** Menos overhead de deploy. Riesgo aceptado: solo accesible vía Tailscale Funnel (no indexado).

---

## [UD-018] Workers creados solo por /onboarding — sin pre-creación en deploy

**Date:** 2026-06-28
**Context:** Deploy.sh pre-creaba code-worker y research-worker en cada deploy. El usuario determinó que ningún worker profile debe existir hasta que se ejecute `/onboarding` en el grupo WhatsApp correspondiente. Los grupos deben mostrar "no configurado" hasta completar las 3 fases.
**Decision:** Eliminar toda pre-creación de workers de deploy.sh. Workers se crean exclusivamente via `/onboarding` (Phase 3, pregunta "nuevo"). El usuario es la única autoridad para crear workers.
**Discarded alternatives:** Mantener workers base pre-creados y que /onboarding los complemente (descartado por contaminación de estado inicial).
**Consequences:** No hay workers sin onboarding. 0 perfiles extra en `hermes profile list`. El usuario debe ejecutar /onboarding para cada grupo.
**Reversion conditions:** Si se necesita un worker base pre-configurado para deploy inmediato.

---

## [UD-019] Sin categorías predefinidas en onboarding

**Date:** 2026-06-28
**Context:** El onboarding original tenía 4 categorías (coding/research/personal/custom) con skills defaults y preguntas condicionales por tipo. El usuario señaló que es imposible cubrir todos los usos posibles con categorías fijas.
**Decision:** Eliminar todas las categorías del onboarding. Las 3 fases son idénticas para todos los grupos. Sin skills defaults, sin preguntas condicionales. El usuario define todo desde cero.
**Discarded alternatives:** Mantener categorías con opción "otro" (descartado: el sesgo de las categorías existentes condiciona la elección del usuario).
**Consequences:** Onboarding más largo (sin defaults) pero más flexible. Cada grupo define su identidad completa.
**Reversion conditions:** Si el usuario encuentra que el onboarding sin defaults es tedioso para casos repetitivos.

---

## [UD-020] Descripción de grupo WhatsApp como contexto dinámico

**Date:** 2026-06-28
**Context:** WhatsApp group descriptions se leen cada 10 min via cron y se almacenan en channel_aliases.json. El usuario puede editar la descripción del grupo en WhatsApp y Hermes lo refleja en minutos.
**Decision:** La descripción del grupo se carga como contexto operativo al inicio de cada sesión. Sirve como pizarra dinámica: recordatorios, enlaces, estado de tareas. No poner credenciales reales (visible a todos los miembros del grupo).
**Discarded alternatives:** Solo usar description estática del YAML (descartado: perdería la capacidad de actualizar contexto sin intervención del agente).
**Consequences:** Contexto actualizable desde WhatsApp sin escribir código. Cambio reflejado en <10 min.
**Reversion conditions:** Si el usuario prefiere controls estáticos y no dinámicos.

---

## [UD-021] Bridge parcheado para exponer descripciones de grupos WhatsApp

**Date:** 2026-06-28
**Context:** Baileys groupMetadata() retorna descripciones de grupos (metadata.desc) pero el bridge de WhatsApp no las exponía. Solo exponía name, isGroup, y participants.
**Decision:** Parchear bridge.js para incluir desc en la respuesta de GET /chat/:id. Versión del parche en infrastructure/hermes/scripts/patch-bridge.sh, aplicado idempotentemente por deploy.sh.
**Discarded alternatives:** Usar API de WhatsApp Business para obtener descripciones (descartado: no hay API pública para grupos de comunidad).
**Consequences:** Cualquier herramienta que consulte el bridge obtiene descripciones. Sin LLM involvement.
**Reversion conditions:** Si Hermes actualiza el bridge.js y el parche ya no aplica (patch-bridge.sh detecta y falla grácilmente).

---

## [UD-022] Toda consulta a una KB debe nombrarla en la ruta, sin base por defecto

**Date:** 2026-07-23
**Context:** El servidor kb-mcp pasó de servir una sola KB a servir varias en un mismo proceso. Cabía exponer una KB por defecto en la raíz del endpoint para abreviar la URL de la que se usa más.
**Decision:** No hay KB por defecto. Cada base se sirve únicamente bajo `/kb/<slug>/mcp` y quien consulta siempre nombra cuál quiere. El usuario lo pidió explícitamente pensando en el futuro: "siempre haya que especificar cuál es la Knowledge Base a consultar Y esto es muy bueno porque así a futuro nosotros podemos agregarle una lógica de autenticación".
**Discarded alternatives:**
- KB por defecto en la raíz (descartado: convierte una ruta en un recurso ambiguo y deja sin anclaje la futura autorización).
- Selección de KB por parámetro de la herramienta (descartado: la autorización quedaría dentro del protocolo en vez de en la capa HTTP, donde un proxy puede aplicarla).
**Consequences:** Cada KB es un recurso HTTP distinto, así que un token podrá habilitarla o negarla sin tocar el servidor. La URL es más larga y agregar una KB obliga a comunicar su slug.
**Reversion conditions:** Si alguna vez el servidor sirviera una sola KB de forma permanente y la autorización se resolviera en otra capa.

---

## [UD-023] Las KB se referencian por el nombre de su repositorio, no por rutas secretas

**Date:** 2026-07-23
**Context:** Para evitar que la KB personal quedara expuesta junto a la compartida con un tercero, se propuso anteponer un prefijo secreto a cada ruta mientras no existiera autenticación real.
**Decision:** Rechazado por el usuario: "Me parece una forma súper estúpida de abordar esto. Que es una mala práctica de ingeniería, tomaste un atajo. Lo importante es que cada knowledge base se referencie por el nombre del repositorio". Las rutas son predecibles a propósito, y si la KB pertenece a un repositorio público o privado no cambia nada, porque eso corresponde a la lógica de autorización por token que se agregará después.
**Discarded alternatives:**
- Prefijo secreto por KB, tipo seguridad por oscuridad (descartado: no es autenticación, ensucia la URL y estorba a la capa real cuando llegue).
**Consequences:** El enrutamiento queda limpio y estable, y no se mezcla con la autorización. A cambio, hasta que exista la capa de tokens cualquiera con la URL puede leer cualquier KB publicada, límite registrado en [DT-011].
**Reversion conditions:** Ninguna prevista. Si hiciera falta ocultar la existencia de una KB, se resuelve con autorización, no con la ruta.

---

## [UD-024] No afectar a Hermes es la restricción máxima de toda intervención en el VPS

**Date:** 2026-07-23
**Context:** El servidor kb-mcp se desplegó en el mismo VPS que ya opera Hermes, Hindsight e Infisical, compartiendo Caddy, Docker y el pipeline de deploy.
**Decision:** El usuario fijó la prioridad por encima de cualquier otra: "SIN AFECTAR A HERMES O LO QUE YA ESTE AHI, ESA ES TU DIRECTIVA MAXIMA". En la práctica: medir el baseline antes de tocar, verificarlo después de cada cambio, aislar el servicio nuevo y preferir no hacer un cambio antes que arriesgar el existente.
**Discarded alternatives:**
- Desplegar en una instancia separada (descartado: el nivel gratuito de OCI ya está ocupado y duplicaría la operación).
- Confiar en que el aislamiento de Docker basta (descartado: comparten Caddy y el pipeline, que es justo donde aparecieron los riesgos reales).
**Consequences:** Cada intervención cuesta más y exige verificación explícita. Gracias a eso se detectaron a tiempo dos fallas que habrían roto el deploy de Hermes: la imagen sin `pull_policy: build` y el restart de Caddy sin tolerancia a fallo.
**Reversion conditions:** Si Hermes migrara a otra instancia y dejaran de compartir infraestructura.

---

## [UD-025] La forma de las descripciones MCP sale de investigación publicada, no de criterio propio

**Date:** 2026-07-23
**Context:** Las herramientas del servidor describían su mecanismo pero no su dominio, así que un agente con la URL no podía saber de qué trataba cada base. Al corregirlo, la redacción se estaba definiendo por criterio propio.
**Decision:** El usuario lo detuvo: "Antropic publicó informaciones muy valiosas sobre cómo hacer MSPs para los agentes y cómo hacer este tipo de herramientas. De ahí debes sacar la forma que debe tener la descripción de cada Knowledge Base. No debe ser algo que tú adivines, sino que se base en investigación ya existente". La descripción se reescribió siguiendo la guía de Anthropic: qué hace, cuándo usarla, cuándo no, y qué información no devuelve.
**Discarded alternatives:**
- Redacción por criterio propio (descartado: es el factor que más pesa en que el agente elija bien, demasiado importante para improvisarlo).
- Instrucciones de proyecto en el cliente (descartado: obliga al usuario a explicar el servidor cada vez; debe bastar la URL).
**Consequences:** Las descripciones son largas y explícitas por norma, y cuestan contexto en cada llamada. Toda herramienta nueva del servidor debe seguir la misma forma.
**Reversion conditions:** Si Anthropic publicara una guía que contradiga la actual, se adopta la nueva.
