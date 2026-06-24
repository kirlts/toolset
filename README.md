# ⚙️ Toolset Personal

> Infraestructura cloud autogestionada para un solo developer — orquestación remota, memoria persistente, CI/CD automatizado.

[![OCI](https://img.shields.io/badge/OCI-Free_Tier-red?logo=oracle)](https://cloud.oracle.com)
[![ARM64](https://img.shields.io/badge/arch-ARM64-blue?logo=arm)](https://www.arm.com)
[![OpenTofu](https://img.shields.io/badge/IaC-OpenTofu-9cf?logo=opentofu)](https://opentofu.org)
[![Tailscale](https://img.shields.io/badge/net-Tailscale-555?logo=tailscale)](https://tailscale.com)
[![Hermes](https://img.shields.io/badge/agent-Hermes-8B5CF6?logo=codeium)](https://hermes-agent.nousresearch.com)
[![DeepSeek](https://img.shields.io/badge/llm-DeepSeek_V4_Flash-FFD43B)](https://deepseek.com)

---

## 📡 Arquitectura

```
┌──────────────────────────────────────────────────────────────────────┐
│                        OCI · sa-valparaiso-1                         │
│                 VM.Standard.A1.Flex · ARM64 · 4 Cores                 │
│                                                                       │
│  ┌─────────┐   ┌──────────┐   ┌───────────┐   ┌──────────────────┐  │
│  │ Hermes  │   │ Hindsight│   │ Infisical │   │  Hermes WebUI    │  │
│  │ Gateway │──▶│  Memory  │──▶│ Secrets   │   │  (Caddy /hermes) │  │
│  │ (Agent) │   │  (MCP)   │   │ Manager   │   │  :8888           │  │
│  └────┬────┘   └──────────┘   └─────┬─────┘   └──────────────────┘  │
│       │                             │                                │
│       │     ┌───────────────────────┘                                │
│       │     ▼                                                       │
│       │  ┌──────────┐                                               │
│       └──│  Caddy   │──▶ / → Landing · /health · /dashboard          │
│          │ :8080    │──▶ /hindsight/* · /api/v1/* · /hermes/         │
│          └──────────┘                                                │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Volumes: postgres (Infisical) · redis · hindsight · landing │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
                          ▲
                          │ Tailscale
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Laptop · Kilo Code · VS Code · `gh` CLI · WhatsApp                │
└──────────────────────────────────────────────────────────────────────┘
```

## 🚀 Stack

| Servicio | Rol | Acceso |
|---|---|---|
| **Hermes Agent** | Orquestador conversacional + gateway multi-platform | WhatsApp · WebUI |
| **Hindsight** | Memoria vectorial MCP — recall, retain, reflect | `{funnel}/hindsight/mcp/` |
| **Hindsight CP** | Control Plane para memory banks | `{funnel}/dashboard` |
| **Infisical** | Secretos cifrados + sync a GitHub Actions | `{funnel}:8443` |
| **Caddy** | Reverse proxy + landing page + TLS | `{funnel}/` |
| **PostgreSQL** | DB de Infisical | Interno Docker |
| **Redis** | Cache de Infisical | Interno Docker |

> `funnel` = `toolset-oci-1-1.tail2d4c18.ts.net`

## 🧠 Memory Banks (Hindsight)

Cada repositorio activo tiene su propio banco aislado de memoria persistente:

| Bank | Proyecto | Facts |
|---|---|---|
| `toolset` | Infraestructura, CI/CD, decisiones técnicas | ~194 |
| `hermes` | Perfil usuario, preferencias, estado agente | ~34 |
| `kairos` | Gobernanza, reglas, skills | nuevo |
| `cl-concerts-db` | Catálogo música docta UAH | ~9 |
| `yacv` | Resume builder | nuevo |
| `witral` | Routing datos messaging→storage | nuevo |
| `evidencia-zero` | Sanitización datos, Ley Karin | nuevo |

Los banks se sincronizan diario a `infrastructure/hermes/banks/` como JSON.

## 🔄 CI/CD Pipeline

Un **push a `main`** dispara:

### 1️⃣ OpenTofu — Infraestructura OCI
```
Plan/Aplica: VCN · Instancia · Seguridad · Volumen
State remoto en OCI Object Storage (toolset-opentofu-state)
```

### 2️⃣ Deploy Services — Docker Compose + Hermes
```
Tailscale → SSH → deploy.sh:
  • Extiende LVM a 100GB
  • Transfiere .env, Caddyfile, docker-compose.yml
  • rsync: SOUL.md, config.yaml, skills, scripts, memory
  • docker compose pull + up -d
  • Verifica health de caddy, hindsight, infisical
  • Bootstrap admin + proyecto + service token en Infisical
  • Sync secrets a Infisical (dev + prod)
  • Reverse sync: Infisical → GitHub Secrets
  • Genera landing page dinámica
```

### ⏰ Sync Diario Automático

| Hora (UTC) | Job | Qué sincroniza |
|---|---|---|
| **01:00** | `hermes-sync-files` | SOUL.md, config.yaml, skills, scripts, memory |
| **02:00** | `hermes-sync-banks` | Exporta TODOS los banks Hindsight → JSON + git commit |

## 🔐 Secrets

Gestionados vía **GitHub Secrets** + **Infisical** (sync bidireccional):

| Categoría | Secrets |
|---|---|
| **Esenciales** | `OCI_API_KEY` · `OCI_USER_OCID` · `OCI_FINGERPRINT` · `OCI_TENANCY_OCID` · `TAILSCALE_AUTH_KEY` · `SSH_PRIVATE_KEY` · `INFISICAL_ENCRYPTION_KEY` · `INFISICAL_AUTH_SECRET` · `INFISICAL_DB_PASSWORD` |
| **Runtime** | `OPENCODE_GO_API_KEY` · `INFISICAL_SERVICE_TOKEN` · `HERMES_LLM_PROVIDER` · `HERMES_LLM_MODEL` · `HERMES_WEBUI_PASSWORD` · `COMPOSIO_API_KEY` · `WHATSAPP_ALLOWED_USERS` |

## 🌐 URLs Operativas

| URL | Servicio |
|---|---|
| `{funnel}/` | Landing page + status |
| `{funnel}/health` | Health check (Hindsight) |
| `{funnel}/dashboard` | Hindsight Control Plane |
| `{funnel}/hindsight/mcp/` | Hindsight MCP endpoint |
| `{funnel}/hermes/` | Hermes WebUI (mobile-friendly) |
| `{funnel}/banks/toolset` | Bank toolset en CP |
| `{funnel}:8443/` | Infisical Web UI |
| `{funnel}:8787/` | Hermes WebUI (funnel directo) |

## 🧪 Verificación Rápida

```bash
# Health checks
curl https://{funnel}/health
curl https://{funnel}/api/status
curl https://{funnel}/hindsight/health

# Estado servicios (dentro del servidor)
ssh opc@toolset-oci-1-1 "sudo docker compose -f /opt/toolset/docker-compose.yml ps"
```

## 🛠 Deploy Manual (verificación local)

```bash
export SSH_HOST="opc@toolset-oci-1-1"
export INFISICAL_ENCRYPTION_KEY="..."
export INFISICAL_AUTH_SECRET="..."
# ... + resto de secrets ...
./infrastructure/deploy.sh
```

---

<p align="center">
  <sub>Toolset Personal · OCI Free Tier · ARM64 · Hecho en 🇨🇱</sub>
</p>
