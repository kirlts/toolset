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
