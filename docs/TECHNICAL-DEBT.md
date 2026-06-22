# Technical Debt

> Temporary and self-liquidating file. It is deleted when 100% of the tasks are completed.

| Symbol | Meaning |
|---|---|
| 🚨 | Critical block / urgent technical debt |

---

## [DT-001] Token Exchange OIDC Identity Propagation Trust no funcional

**Severity:** Medium
**Origin:** manual (CI/CD auth flow)
**Description:** El Identity Propagation Trust "GitHub Actions Toolset Trust" está correctamente creado en el dominio OCI, vinculado a la Confidential App `GitHubActions-OpenTofu`. Sin embargo, el endpoint `/oauth2/v1/token` rechaza el token OIDC de GitHub Actions con `invalid_request`. Se probaron sin éxito:
- Grant types: `urn:ietf:params:oauth:grant-type:token-exchange` y `urn:ietf:params:oauth:grant-type:jwt-bearer`
- Auth: Basic auth y form params
- Audiencias: `oci` y la URL completa del token endpoint
- `subject_token_type`: `urn:ietf:params:oauth:token-type:jwt` y `urn:ietf:params:oauth:token-type:id_token`

El pipeline funciona actualmente con API key (`OCI_API_KEY`) como puente temporal. La infraestructura OIDC permanece desplegada y lista para reactivarse.
**Remediation plan:** Investigar por qué el exchange falla. Posibles causas: (a) el dominio requiere un formato de assertion distinto, (b) restricciones de red/geografía en el endpoint OAuth, (c) el trust está mapeando mal el `sub` claim del JWT de GitHub.
**Status:** ☐ Pending

---

## [DT-002] Estrategia de autenticación para URLs de gestión expuestas por Tailscale Funnel

**Severity:** Low
**Origin:** planned (multi-service Funnel)
**Description:** Tailscale Funnel + Caddy expone servicios autogestionados vía HTTPS público en `https://toolset-oci-1.tail2d4c18.ts.net/`. Actualmente no hay autenticación en la capa de Funnel/Caddy. Algunas URLs permiten gestión (Infisical, Hindsight CP, Hermes en futuro) y otras son solo de observabilidad/MCP (health, API, MCP). Una vez Hermes esté operativo, se debe implementar una estrategia de auth que:

- Proteja las URLs de gestión (Infisical, Hindsight CP, Hermes) con autenticación.
- Mantenga públicas las URLs de observabilidad (health, API REST) y MCP (necesario para que harnesses se conecten sin auth).
- Opciones: Caddy `basicauth` (simple, global por path), forward auth con Infisical (más integrado), o `HINDSIGHT_CP_ACCESS_KEY` (específico de Hindsight).

**Remediation plan:** Definir e implementar post-TASK-006 (Hermes operativo).
**Status:** ☐ Pending
