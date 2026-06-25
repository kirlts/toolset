# ⚙️ Toolset Personal

> Un solo dev. Una VM gratis. Control total desde el celu.

[![OCI](https://img.shields.io/badge/OCI-Free_Tier-red?logo=oracle)](https://cloud.oracle.com)
[![ARM64](https://img.shields.io/badge/arch-ARM64-blue?logo=arm)](https://www.arm.com)
[![OpenTofu](https://img.shields.io/badge/IaC-OpenTofu-9cf?logo=opentofu)](https://opentofu.org)
[![Tailscale](https://img.shields.io/badge/net-Tailscale-555?logo=tailscale)](https://tailscale.com)
[![Hermes](https://img.shields.io/badge/agent-Hermes-8B5CF6?logo=codeium)](https://hermes-agent.nousresearch.com)
[![DeepSeek](https://img.shields.io/badge/llm-DeepSeek_V4_Flash-FFD43B)](https://deepseek.com)

---

## 🤷 ¿Para qué existe esto?

Porque ser dev autónomo no debería significar estar esclavizado a:

- **Render, Railway, Vercel,Fly.io** → te cambian los precios, te crece la cuenta, te lockean.
- **SaaS de AI** → pagas por asiento, por token, por API call, por repositorio.
- **Infraestructura cloud grande** → gratis los primeros 12 meses, después te sangran.
- **CI/CD ajeno** → GitHub Actions, CircleCI, etc.: útiles, pero dependes de su disponibilidad.

**Toolset es la alternativa**: una VM ARM64 en el Free Tier de OCI (*0.0 CLP/mes*, no caduca), con un agente AI que orquesta todo via WhatsApp, memoria persistente que no olvida tus decisiones, y un pipeline CI/CD que reconstruye todo desde cero si explota.

> El objetivo no es ahorrar plata. Es **tener soberanía técnica** con lo mínimo indispensable. Trabajas desde tu laptop (Kilo Code, Antigravity), ejecutas en la nube, y monitorizas desde el teléfono.

---

## 🧠 Filosofía

| Principio | Qué significa en la práctica |
|---|---|
| **Deliberación local, ejecución cloud** | Las decisiones pesadas las tomas en tu workstation con modelos de frontera. La nube solo ejecuta — compila, testea, deploya, responde. |
| **Mobile-first operations** | No necesitas abrir un IDE para mergear un PR, revisar logs, o reiniciar un servicio. Se lo pides a Hermes por WhatsApp y él lo hace. |
| **Memoria centralizada** | Cada decisión arquitectónica, cada bug recurrente, cada preferencia tuya queda registrada en Hindsight. No se pierde entre sesiones ni entre máquinas. |
| **Recuperabilidad total** | Si la VM explota: `tofu apply` + esperar 8 minutos → todo funcionando otra vez. El estado está en OCI Object Storage y los secrets en Infisical. |
| **Cero vendor lock-in** | Todo es OSS. Hermes, Hindsight, Infisical, OpenTofu, Caddy, PostgreSQL. Si OCI falla, cambias el provider de OpenTofu y deployas en otro lado. |
| **Sin suscripciones recurrentes** | OCI Free Tier (200 GB boot volume, 12 GB RAM, 4 OCPU). Tailscale Free (3 users, 100 devices). Todo corre adentro. |

---

## 📡 Stack

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
│  │  Volumes: postgres · redis · hindsight · landing              │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
                          ▲
                          │ Tailscale (WireGuard)
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│  🖥️ Workstation                    📱 WhatsApp                     │
│  Kilo Code · Antigravity           Hermes Chat                      │
│  VS Code · gh CLI                  Comandos de voz                  │
└──────────────────────────────────────────────────────────────────────┘
```

## 🧩 Servicios

| Servicio | Para qué sirve | Cómo accedes |
|---|---|---|
| **Hermes Agent** | Tu asistente técnico en WhatsApp. Orquesta deploys, ejecuta código, diagnostica errores, gestiona GitHub | WhatsApp (+56 9 3641 4929) · WebUI |
| **Hindsight** | Memoria que no se olvida. Cada decisión, preferencia y aprendizaje se guarda y se recupera por contexto | `{funnel}/hindsight/mcp/` · MCP |
| **Infisical** | Donde viven los secrets (API keys, tokens, passwords). Sync automático con GitHub Actions | `{funnel}:8443` |
| **Caddy** | Reverse proxy que une todo bajo un mismo dominio + landing page | `{funnel}/` |
| **Hermes WebUI** | Interfaz web para hablar con Hermes desde el navegador | `{funnel}/hermes/` · `{funnel}:8787` |

> `funnel` = `toolset-oci-1-1.tail2d4c18.ts.net`

## 🧠 Los Banks (memoria por proyecto)

Cada repo tiene su propia memoria aislada en Hindsight. Así Hermes sabe el contexto de cada proyecto cuando trabajas en él:

| Bank | Proyecto | Qué recuerda |
|---|---|---|
| `toolset` | Este repo | Infraestructura, CI/CD, decisiones técnicas (~194 facts) |
| `hermes` | Tu perfil | Preferencias, estado del agente, contexto personal (~34 facts) |
| `kairos` | Gobernanza | Reglas, workflows, skills del sistema |
| `cl-concerts-db` | UAH · Música docta | Decisiones del proyecto Flask |
| `yacv` | Resume builder | Features, bugs, decisiones |
| `witral` | Routing datos | Pipeline messaging→storage |
| `evidencia-zero` | Ley Karin | Sanitización de datos |

Los banks se respaldan diario como JSON en `infrastructure/hermes/banks/`.

---

## 🔄 CI/CD: Cómo se mantiene vivo

Un push a `main` revive todo automágicamente:

### 1. OpenTofu (plan/apply)
Crea o actualiza la infra en OCI: VCN, subnets, instancia, reglas de seguridad, volumen de boot.
El state vive en OCI Object Storage, no en GitHub.

### 2. Deploy services (Docker Compose + Hermes)
Conecta via Tailscale, extiende el disco a 100 GB, y deploya:
```
deploy.sh:
  ◇ Transfiere .env, Caddyfile, docker-compose.yml, SOUL.md, config.yaml
  ◇ docker compose pull + up -d (caddy, hindsight, infisical, postgres, redis)
  ◇ Verifica health de cada servicio (hasta 4 intentos, 30s entre cada uno)
  ◇ Si es primera vez: bootstrap admin de Infisical, crea proyecto, genera service token
  ◇ Sincroniza secrets a Infisical (dev + prod)
  ◇ Reverse-sync: secrets nuevos desde Infisical → GitHub Secrets
  ◇ Genera landing page con estado actual
```

### ⏰ Sync diario (sin intervención humana)

| Hora (UTC) | Qué pasa |
|---|---|
| **01:00** | Se versionan SOUL.md, config.yaml, skills, scripts, memory → commit + push |
| **02:00** | Se exportan todos los memory banks como JSON → reflect + retain → commit + push |

Si algo falla, el próximo ciclo lo reintenta. No hay páginas rotas.

---

## 🔐 Secrets (no hardcodees nada)

| Grupo | Qué incluye |
|---|---|
| **Infraestructura** | `OCI_API_KEY` · `OCI_USER_OCID` · `OCI_FINGERPRINT` · `OCI_TENANCY_OCID` · `TAILSCALE_AUTH_KEY` · `SSH_PRIVATE_KEY` |
| **Infisical** | `ENCRYPTION_KEY` · `AUTH_SECRET` · `DB_PASSWORD` · `SERVICE_TOKEN` · `ADMIN_EMAIL` · `ADMIN_PASSWORD` |
| **Runtime** | `OPENCODE_GO_API_KEY` · `HERMES_LLM_*` · `HERMES_WEBUI_PASSWORD` · `COMPOSIO_API_KEY` · `WHATSAPP_ALLOWED_USERS` |

Viven en GitHub Secrets y se replican a Infisical en cada deploy. Bidireccional: Hermes puede crear secrets en Infisical y el pipeline los sincroniza de vuelta a GitHub.

---

## 🌐 URLs

| URL | Qué es |
|---|---|
| `{funnel}/` | Landing page + estado de todos los servicios |
| `{funnel}/health` | Health check de Hindsight |
| `{funnel}/dashboard` | Control Plane de Hindsight (tus banks) |
| `{funnel}/hindsight/mcp/` | Endpoint MCP para que los agentes consulten memoria |
| `{funnel}/hermes/` | Hermes WebUI (desde el celu, sin app) |
| `{funnel}:8443/` | Infisical Web UI |
| `{funnel}:8787/` | Hermes WebUI (directo, sin Caddy) |

---

## 🧪 ¿Funciona?

```bash
# Desde cualquier lado
curl https://{funnel}/health
curl https://{funnel}/api/status

# Desde el servidor
ssh opc@toolset-oci-1-1 "sudo docker compose ps"
```

Todos los servicios deben mostrar `healthy`.

---

## 🚀 Deploy manual (para probar cambios localmente)

```bash
export SSH_HOST="opc@toolset-oci-1-1"
export INFISICAL_ENCRYPTION_KEY="..."
export INFISICAL_AUTH_SECRET=***
# ... más secrets ...
./infrastructure/deploy.sh
```

---

<p align="center">
  <sub>Toolset Personal · OCI Free Tier sa-valparaiso-1 · ARM64 · Hecho en 🇨🇱<br>
  Sin suscripciones · Sin vendor lock-in · Sin que te crezca la cuenta</sub>
</p>
