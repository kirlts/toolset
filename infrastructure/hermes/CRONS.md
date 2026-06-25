# Cron Jobs Activos — Hermes Agent

> Última actualización: 2026-06-24
> Estos jobs se gestionan vía `cronjob` tool o `hermes cron` CLI.

---

## 1. `hermes-sync-files` — Sincronización diaria de archivos

| Campo | Valor |
|---|---|
| **Job ID** | `884851335a8f` |
| **Schedule** | Diario, 08:00 UTC (`0 8 * * *`) — 04:00 Chile |
| **Script** | `sync-hermes-to-repo.sh` |
| **No-agent** | `true` (script puro, sin LLM) |
| **Deliver** | `local` (solo escribe en disco) |
| **Estado** | ✅ Activo |
| **Último run** | 2026-06-24 05:31 UTC — OK |

### Qué hace
Copia y commitea los siguientes archivos de `~/.hermes/` al repo `toolset/infrastructure/hermes/`:
- `SOUL.md`
- `config.yaml`
- `memory/MEMORY.md` + `USER.md`
- `skills/` (snapshot completo, excluye `.curator_backups`, `.hub`, node_modules)
- `scripts/`
- `hooks/`
- `kilo.jsonc` (desde `~/.config/kilo/`)
- Redacta secrets (COMPOSIO_MCP_KEY) antes de commitear

### Dependencias
- `git` autenticado como `kirlts` vía HTTPS
- Push a `main` (no crea PRs)

---

## 2. `hermes-sync-banks` — Exportación diaria de banks Hindsight

| Campo | Valor |
|---|---|
| **Job ID** | `47b3ed7838a8` |
| **Schedule** | Diario, 08:00 UTC (`0 8 * * *`) — 04:00 Chile |
| **Prompt** | Descubre todos los banks, exporta a JSON, ejecuta reflect+retain diario, commitea |
| **No-agent** | `false` (usa LLM para procesar banks) |
| **Deliver** | `local` |
| **Estado** | ✅ Activo |
| **Último run** | 2026-06-24 05:33 UTC — OK |

### Qué hace
1. Descubre todos los banks vía `list_banks()`
2. Exporta cada bank como JSON → `infrastructure/hermes/banks/<bank>/YYYY-MM-DD.json`
3. Ejecuta `reflect` + `retain` diario sobre cada bank
4. Commitea y pushea todo al repo

### Banks actuales (8 activos)
| Bank | Facts | Propósito |
|---|---|---|
| `hermes` | ~44 | Perfil del usuario, estado del agente |
| `toolset` | ~202 | Infraestructura, decisiones técnicas |
| `kairos` | ~30 | Sistema de gobernanza |
| `cl-concerts-db` | ~14 | Proyecto música docta UAH |
| `yacv` | ~6 | YaCV resume builder |
| `evidencia-zero` | ~6 | Sanitización Ley Karin |
| `witral` | ~2 | Routing messaging→storage |
| `default` | ~52 | Banco por defecto |

## 3. `hermes-health-check` — Diagnóstico diario del sistema

| Campo | Valor |
|---|---|
| **Job ID** | `0a88e1791af5` |
| **Schedule** | Diario, 04:00 UTC (`0 4 * * *`) — 00:00 Chile |
| **Prompt** | Revisa CI/CD, mensajes pendientes, tareas pendientes, servicios |
| **Skills** | `github-pr-workflow`, `systematic-debugging` |
| **Deliver** | WhatsApp del usuario |
| **Estado** | ✅ Activo |
| **Creado** | 2026-06-25 |

### Qué revisa

1. **CI/CD** — Últimos 3 runs; si alguno falló, diagnostica y sugiere corrección
2. **Mensajes pendientes** — Respuestas sin contestar en WhatsApp >12h
3. **Tareas pendientes** — Banks de Hindsight con work pendiente
4. **Servicios core** — hindsight, infisical, caddy, hermes-webui, hermes-gateway
5. **Reporte al usuario** — Resumen por WhatsApp. Si todo bien, mensaje breve. Si hay problemas, detalle.

---

## Notas

- Ambos jobs corren secuencialmente (01:00 archivos, 02:00 banks)
- Los JSON dumps de banks son respaldo/auditoría; en runtime Hermes usa `recall` contra Hindsight MCP vivo
- Para modificar un job: `cronjob action=update job_id=<id> ...`
- Para pausar: `cronjob action=pause job_id=<id>`
