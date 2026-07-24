# VERIFICATION: Toolset Personal v0.1.0

> Verificaciones formales y limites de prueba para el Toolset Personal.

## Kairós Symbol Legend

| Symbol | Meaning |
|---|---|
| 🤖 `.LLM` | Verificable por IA / herramienta automatica |
| 🧑 `.HUM` | Requiere verificacion humana |
| 🤖🧑 `.MIX` | Pre-verificable por IA, con validacion humana final |
| ✅ | Implementado y verificado |
| 🔲 | Pendiente |

---

### Verificaciones de Integracion de Workspace (EPIC-001)

- ✅ `[DEV.CR.01.LLM]` Verificar que mcp_config.json contiene la configuracion valida de Composio y Hindsight.
  - *Resultado esperado:* Los endpoints de los servidores responden 200 OK y estan sintacticamente bien formados.
  - *Verificacion:* ✅ Implemented (🤖 Verified by curl HTTP responses; 2026-06-21 21:54)

- ✅ `[USER.FN.01.LLM]` Listar archivos de Google Drive a traves de la integracion de Composio.
  - *Resultado esperado:* El listado devuelve los metadatos correctos del documento "Toolset Junio 2026".
  - *Verificacion:* ✅ Implemented (🤖 Verified by Composio tool execution; 2026-06-21 21:48)

- ✅ `[USER.FN.02.HUM]` Inicializar repositorio local git en /home/kirlts/toolset.
  - *Resultado esperado:* git status confirma la existencia de un repositorio valido con rama principal main.
  - *Verificacion:* ✅ Implemented (🧑 Confirmed by user; 2026-06-21 20:30)

- ✅ `[DEV.CR.02.LLM]` Verificar que docs/ contiene los 8 archivos requeridos por el workflow de gobernanza de Kairos sin divergencias de plantilla.
  - *Resultado esperado:* Los archivos MASTER-SPEC.md, TODO.md, MEMORY.md, USER-DECISIONS.md, CHANGELOG.md, VERIFICATION.md, REPOMAP.md y RULES.md existen en docs/ y cumplen con el lint estructural.
  - *Verificacion:* ✅ Implemented (🤖 Verified by local structural checks; 2026-06-21 22:07)

- ✅ `[DEV.CR.03.LLM]` Verificar conexion directa e indexacion en el servidor Hindsight.
  - *Resultado esperado:* La llamada RPC retain registra con exito una memoria y recall recupera los conceptos indexados.
  - *Verificacion:* ✅ Implemented (🤖 Verified by Hindsight JSON-RPC tools/call responses; 2026-06-21 21:55)

### Verificaciones de Infraestructura Base Cloud (EPIC-002)

- ✅ `[DEV.CR.04.LLM]` Verificar aprovisionamiento base del servidor OCI.
  - *Resultado esperado:* El servidor responde a ping a través de la red privada (Tailscale) y los puertos públicos están cerrados.
  - *Verificacion:* ✅ Implemented (🤖 SSH via Tailscale IP funcional; puerto 22 público restringido a VCN; 2026-06-22)

- ✅ `[USER.FN.03.HUM]` Confirmar la conectividad SSH local hacia el servidor OCI.
  - *Resultado esperado:* El usuario puede acceder al servidor mediante la IP de Tailscale (100.77.183.125) o hostname (`toolset-oci-1`).
  - *Verificacion:* ✅ Implemented (🧑 Usuario confirmó acceso SSH via Tailscale; 2026-06-22)

### Verificaciones de Gestión de Secretos y Sandboxing (EPIC-003)

- ✅ `[DEV.CR.05.LLM]` Validar el funcionamiento del gestor de secretos (Infisical).
  - *Resultado esperado:* La API de Infisical responde con health OK desde el Funnel. Inyección de secrets en runtime pendiente.
  - *Verificacion:* ✅ Implemented (🤖 Verified by curl /api/status → {"message":"Ok"}; 2026-06-22 01:07)

- ✅ `[DEV.CR.06.LLM]` Validar el funcionamiento del sandbox Docker nativo de Hermes Agent.
  - *Resultado esperado:* Hermes ejecuta comandos en contenedores Docker efímeros con hardening (no-new-privs, capabilities drop, network none).
  - *Verificacion:* ✅ Implementado. Hermes v0.17.0 con `terminal.backend: docker` configurado. Verificado por deploy. (2026-06-23)

- ✅ `[DEV.CR.07.LLM]` Validar la integración de Hermes con Hindsight (MCP) y Composio (MCP).
  - *Resultado esperado:* Hermes tiene acceso a herramientas MCP de ambos servidores y puede ejecutarlas.
  - *Verificacion:* ✅ Implementado. 43 tools: 36 hindsight + 7 composio. 0 failures. (2026-06-23)

### Verificaciones de Orquestación y Mensajería (EPIC-004)

- ✅ `[DEV.CR.13.LLM]` Verificar que Hermes Agent está corriendo como servicio persistente.
  - *Resultado esperado:* El agente responde a health checks internos y su proceso está activo.
  - *Verificacion:* ✅ Implemented (🤖 Verified by deploy; 2026-06-23)

- 🔲 `[USER.FN.04.HUM]` Probar la comunicación bidireccional mediante interfaz móvil.
  - *Resultado esperado:* El usuario puede enviar un mensaje y recibir respuesta desde el agente.
  - *Verificacion:* 🔲 Pendiente

### Verificaciones de Soberanía de Memoria (EPIC-005)

- ✅ `[DEV.CR.08.MIX]` Validar migración de Hindsight a instancia self-hosted en OCI.
  - *Resultado esperado:* Las operaciones MCP utilizan la instancia en OCI en lugar del servicio cloud, con el bank "toolset" migrado sin pérdida de contexto.
  - *Verificacion:* ✅ Implementado. Hindsight desplegado en OCI (modo standalone con pg0 embebido). LLM configurado con OpenCode Go + DeepSeek V4 Flash. Bank "toolset" migrado desde cloud (14 docs, 72 facts, 56 observaciones). Recall funcional. MCP self-hosted activo en Kilo Code. Cloud desactivado. (🤖🧑 Pre-verified + confirmed by user; 2026-06-26 12:15)

### Verificaciones de Próximos Pasos (EPIC-006)

- ✅ `[DEV.CR.09.LLM]` Verificar configuración de Tailscale Funnel para recepción de webhooks.
  - *Resultado esperado:* Hindsight API/MCP accesible vía HTTPS público.
  - *Verificación:* ✅ Implementado. Funnel activo. MCP reachable. (🤖 Verified by curl; 2026-06-22)
- 🔲 `[DEV.CR.10.LLM]` Verificar integración de Infisical con servicios en runtime.
- 🔲 `[DEV.CR.11.LLM]` Verificar Tailscale SSH funcional en Oracle Linux 9 con SELinux.
- ✅ `[DEV.CR.12.LLM]` ~~OIDC~~ Cerrado (DT-001). API key estática mantenida. (2026-06-26)

### Verificaciones de Pipeline CI/CD (EPIC-007)

- ✅ `[DEV.CR.14.LLM]` Concurrency group impide deploys paralelos en main.
  - *Verificacion:* ✅ Implementado — `concurrency.group: deploy-${{ github.ref_name }}`. (🤖 Verified by sequentialized runs; 2026-06-26)
- ✅ `[DEV.CR.15.LLM]` Rollback automático restaura compose anterior si falla verificación.
  - *Verificacion:* ✅ Implementado — marker + restore + preflight auto-revert. (🤖 Verified by pipeline; 2026-06-26)
- ✅ `[DEV.CR.16.LLM]` Sync bidireccional Infisical↔GitHub funcional.
  - *Verificacion:* ✅ Implementado — push via script standalone, pull via runner con GH_TOKEN. 18/18 secrets verificados. (🤖 Verified by verify action; 2026-06-26)
- ✅ `[DEV.CR.17.LLM]` Preflight verifica 15 invariantes MASTER-SPEC post-deploy.
  - *Verificacion:* ✅ Implementado — health, MCP 3-step, SOUL.md, banks, skills, AGENTS.md, cron. (🤖 Verified by pipeline; 2026-06-26)
- 🔲 `[DEV.CR.18.LLM]` ~~Caddy basicauth protege management URLs, MCP público.~~ **Falsificada.**
  - *Verificacion original:* ✅ /dashboard → 401, /health → 200, /hindsight/mcp/ → 200. (🤖 Verified by curl; 2026-06-26)
  - *Re-verificación 2026-07-23:* ❌ **Ya no se cumple.** El `basicauth` fue removido del Caddyfile en `1de879b` («remove Hindsight basicauth, add URL verification») y `db17f50`, sin actualizar esta verificación ni [DT-002]. Medición actual: `/dashboard` → **200**, `/api/banks` → **200**, `/banks/` → 308. Las URLs de gestión de Hindsight (bancos de memoria) están **públicas en internet** vía Funnel. Ver [DT-002] para la decisión pendiente.
- ✅ `[DEV.CR.19.LLM]` Deploy incremental <5min sin cambios de infra.
  - *Verificacion:* ✅ ~4:25 con sandbox build condicional + Tailscale action + SSH mux. (🤖 Verified by pipeline timing; 2026-06-26)
- ✅ `[DEV.CR.20.LLM]` FUNNEL_DOMAIN parametrizado como GitHub variable.
  - *Verificacion:* ✅ 36 referencias hardcodeadas reemplazadas. (🤖 Verified by grep; 2026-06-26)

### Verificaciones de Publicacion de Knowledge Bases por MCP (EPIC-016)

> Ref: MASTER-SPEC §7.2

- ✅ `[DEV.CR.21.LLM]` kb-mcp sirve todas las KB de `/opt/kb` con la capa semantica activa.
  - *Resultado esperado:* `GET /kb/salud` lista cada KB con su conteo de entradas y `semantica: true`.
  - *Verificacion:* ✅ `{"kbs":[{"slug":"personal","entradas":129,"semantica":true},{"slug":"traza-ambiental","entradas":175,"semantica":true}]}`. (🤖 Verified by curl; 2026-07-23)

- ✅ `[DEV.CR.22.LLM]` Handshake MCP completo sin autenticacion y superficie de solo lectura.
  - *Resultado esperado:* `initialize` responde con `serverInfo`, `tools/list` devuelve exactamente tres herramientas (`consultar`, `leer`, `panorama`) y ninguna de escritura.
  - *Verificacion:* ✅ Ambas KB. Ademas `tools/call` de `panorama` devuelve inventario real. (🤖 Verified by curl JSON-RPC; 2026-07-23)

- ✅ `[DEV.CR.23.LLM]` Interoperabilidad de protocolo con los clientes MCP vigentes.
  - *Resultado esperado:* el servidor negocia las cuatro versiones en circulacion y no falla ante los metodos que los clientes sondean.
  - *Verificacion:* ✅ Devuelve la version solicitada en `2024-11-05`, `2025-03-26`, `2025-06-18` y `2025-11-25`. `ping`, `resources/list`, `prompts/list` y `resources/templates/list` responden sin error. Limite conocido y conforme a especificacion: sin `Accept: text/event-stream` devuelve 406. (🤖 Verified by curl; 2026-07-23)

- ✅ `[DEV.CR.24.LLM]` El descubrimiento OAuth no induce a un cliente a exigir login.
  - *Resultado esperado:* las rutas `/.well-known/oauth-*` y `/.well-known/openid-configuration*` devuelven 404, no la landing con 200.
  - *Verificacion:* ✅ Las cinco rutas devuelven 404. Antes respondian 200 con HTML por el catch-all del Caddyfile, lo que hacia fallar el conector de claude.ai con «no se pudo registrar con el servicio de inicio de sesion». (🤖 Verified by curl; 2026-07-23)

- ✅ `[DEV.CR.25.LLM]` La ruta con slash final resuelve a la URL canonica.
  - *Resultado esperado:* `POST /kb/<slug>/mcp/` redirige con 308 a `/kb/<slug>/mcp` conservando esquema y prefijo, y completa el handshake.
  - *Verificacion:* ✅ Ambas KB devuelven su `serverInfo` siguiendo el redirect. Antes emitia un 307 hacia `http://host/<slug>/mcp`, sin el prefijo `/kb` y degradado a http, porque `handle_path` despoja el prefijo antes de que el backend construya el redirect. Importa porque hay clientes que documentan la ruta con slash final. (🤖 Verified by curl; 2026-07-23)

- ✅ `[DEV.CR.26.LLM]` El despliegue de kb-mcp no altera ningun servicio preexistente.
  - *Resultado esperado:* tras cada cambio, `/health`, `/dashboard`, `/hermes/`, `/openapi.json` y la landing responden igual que en el baseline previo.
  - *Verificacion:* ✅ Medido antes y despues de cada intervencion (200, 200, 302, 200, 200). Contenedores de Hermes, Hindsight e Infisical sin recrear. (🤖 Verified by curl + docker ps; 2026-07-23)

- 🔲 `[DEV.CR.27.MIX]` Un tercero consulta la KB por MCP sin friccion.
  - *Resultado esperado:* el colega conecta el conector con la URL entregada y obtiene respuestas utiles sin asistencia.
  - *Verificacion:* 🔲 Pendiente de uso real. Pre-verificado por IA: conector de claude.ai y Claude Code verificados con consulta real (`¿que es un NFU?`, `¿quien financia la recoleccion?`). Falta la confirmacion del usuario final.

### Verificaciones de Resiliencia de la Mensajeria Multi-tenant (EPIC-017)

> Ref: MASTER-SPEC §7.1

- ✅ `[DEV.CR.28.LLM]` El bridge de cada tenant escucha de forma estable, no solo de forma instantanea.
  - *Resultado esperado:* el PID que ocupa el puerto del tenant se mantiene igual durante un muestreo sostenido, y `/health` responde `connected`.
  - *Verificacion:* ✅ `tito` en `:3001`, mismo PID en siete muestras a lo largo de 90 segundos, `{"status":"connected","queueLength":0}` y `gateway_state.json` con `"state":"connected"`. El contraste importa: en crashloop el puerto tambien responde, pero el PID cambia y hay ventanas largas sin nadie escuchando. (🤖 Verified by ss + curl; 2026-07-23)

- 🔲 `[DEV.CR.29.LLM]` El monitor de tenants no repite indefinidamente una alerta ya emitida.
  - *Resultado esperado:* ante una condicion persistente, `monitor-tenants.sh` alerta una vez y luego agrupa o silencia hasta que el estado cambie o se supere un umbral de escalamiento.
  - *Verificacion:* 🔲 Pendiente. Hoy emite la misma alerta cada 5 minutos sin dedupe: el incidente de `tito` produjo seis mensajes identicos antes de que el usuario interviniera (ver [DT-013]).
