# Toolset

Infraestructura técnica para un solo developer autónomo. Deliberación en local (workstation), ejecución asíncrona en la nube (OCI Free Tier).

## Stack

| Servicio | Propósito | Acceso |
|---|---|---|
| **Hindsight** | Memoria vectorial centralizada (MCP) | `https://funnel/hindsight/mcp/` |
| **Hindsight CP** | Control Plane para banks | `https://funnel/dashboard` |
| **Infisical** | Gestión de secrets (API) | `https://funnel/api/status` |
| **Infisical UI** | Web UI para secrets | `https://funnel:8443/` |
| **Caddy** | Reverse proxy multi-servicio | `https://funnel/` |
| **Landing page** | Status de todos los servicios | `https://funnel/` |

> `funnel` = `toolset-oci-1-1.tail2d4c18.ts.net`

## Arquitectura

```
[Workstation: Kilo Code / Antigravity] <== Tailscale ==> [OCI: VM.Standard.A1.Flex]
                                                               |
                                                    ┌──────────┴──────────┐
                                                    │    Caddy (:8080)     │
                                                    ├──────────────────────┤
                                                    │ / → landing page    │
                                                    │ /health → Hindsight │
                                                    │ /api/status → Infi. │
                                                    │ /api/v1/* → Infi.   │
                                                    │ /dashboard → CP     │
                                                    │ /hindsight/* → API  │
                                                    │ /banks/* → CP       │
                                                    └──────────────────────┘
                                                    ┌──────────────────────┐
                                                    │ Infisical (:8443)   │
                                                    │ (via Funnel direct) │
                                                    └──────────────────────┘
```

## CI/CD Pipeline

Un push a `main` dispara dos jobs:

1. **OpenTofu**: Plan/Aplica infraestructura OCI (VCN, instancia, seguridad).
2. **Deploy Services**: Conecta via Tailscale + SSH, deploya Docker Compose.

El pipeline es 100% automático para todos los estados:
- **Instancia nueva**: OpenTofu crea todo → cloud-init bootstrap → deploy.sh configura servicios.
- **Mismo stack**: OpenTofu "No changes" → deploy.sh actualiza servicios.
- **Volumen wipeado**: Bootstrap recrea admin → proyecto → service token.

## GitHub Secrets

### Esenciales (bootstrap — el pipeline falla sin estos)

| Secret | Propósito |
|---|---|
| `OCI_API_KEY` | Clave API de OCI para OpenTofu (formato RSA PEM, `openssl rsa -in key.pem -out key_rsa.pem`) |
| `OCI_USER_OCID` | OCID del usuario API de OCI |
| `OCI_FINGERPRINT` | Fingerprint de la clave API en OCI Console |
| `OCI_TENANCY_OCID` | OCID del tenancy OCI |
| `TAILSCALE_AUTH_KEY` | Pre-auth key reusable de Tailscale (que no expire) |
| `SSH_PRIVATE_KEY` | Llave privada ED25519 para SSH al servidor OCI |
| `INFISICAL_ENCRYPTION_KEY` | `openssl rand -hex 16` — 32 hex chars para cifrado de Infisical |
| `INFISICAL_AUTH_SECRET` | `openssl rand -hex 32` — 64 hex chars para auth tokens de Infisical |
| `INFISICAL_DB_PASSWORD` | Password de PostgreSQL para Infisical (`infisical`) |

### Operacionales (necesarios para servicios runtime)

| Secret | Propósito |
|---|---|
| `OPENCODE_GO_API_KEY` | API key de OpenCode Go para Hindsight LLM + secretos runtime |
| `INFISICAL_SERVICE_TOKEN` | Service token `st.*` para CI/CD sync de secrets |
| `INFISICAL_ADMIN_EMAIL` | Email del admin de Infisical (`martin.gil.o@gmail.com`) |
| `INFISICAL_ADMIN_PASSWORD` | Password del admin de Infisical |
| `FUNNEL_DOMAIN` | Dominio del Funnel (`toolset-oci-1-1.tail2d4c18.ts.net`) |

### No esenciales (valores fijos/derivables)

| Secret | Propósito |
|---|---|
| `OCI_SSH_KEY_PUBLIC` | Llave pública SSH (derivable de `SSH_PRIVATE_KEY`) |

## Deploy Local (verificación)

```bash
export SSH_HOST="opc@toolset-oci-1-1"
export INFISICAL_ENCRYPTION_KEY="..."
export INFISICAL_AUTH_SECRET="..."
export INFISICAL_DB_PASSWORD="infisical"
export INFISICAL_SERVICE_TOKEN="st.xxx..."
export INFISICAL_ADMIN_EMAIL="..."
export INFISICAL_ADMIN_PASSWORD="..."
export OPENCODE_GO_API_KEY="sk-..."
export FUNNEL_DOMAIN="toolset-oci-1-1.tail2d4c18.ts.net"

./infrastructure/deploy.sh
```

## Banks (Hindsight Memory)

Los banks se nombran según `hindsight-<project-name>`. El bank `toolset` es el banco activo de este repositorio.

Ver: `docs/RULES.md` → Dynamic Routing by Project.

## URLs Operativas

| URL | Servicio |
|---|---|
| `https://funnel/` | Landing page + status |
| `https://funnel/health` | Health check (Hindsight) |
| `https://funnel/api/status` | Infisical API health |
| `https://funnel/dashboard` | Hindsight Control Plane |
| `https://funnel/hindsight/mcp/` | Hindsight MCP endpoint |
| `https://funnel/banks/toolset` | Bank toolset en CP |
| `https://funnel:8443/` | Infisical Web UI |

## Verificación

```bash
# Tests rápidos
curl https://funnel/health
curl https://funnel/api/status
curl https://funnel/hindsight/health
curl https://funnel/dashboard

# Tests detallados (dentro del servidor)
ssh opc@toolset-oci-1-1 "sudo docker compose -f /opt/toolset/docker-compose.yml ps"

# Todos los servicios deben mostrar "healthy"
```
