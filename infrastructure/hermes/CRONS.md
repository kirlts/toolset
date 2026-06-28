# Cron Jobs Activos — Hermes Agent

> Última actualización: 2026-06-28
> Estos jobs se gestionan vía `cronjob` tool o `hermes cron` CLI.
> Los cron se crean desde el canal que define su propósito. Si un cron pertenece al ámbito de un perfil específico (ej: personal), se entrega a ese canal. Si es transversal, se entrega por DM del orquestador.

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
| **Último run** | 2026-06-28 01:00 UTC — OK |

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
| **Schedule** | Diario, 02:00 UTC (`0 2 * * *`) — 22:00 Chile |
| **Prompt** | Descubre todos los banks, exporta a JSON, ejecuta reflect+retain diario, commitea |
| **No-agent** | `false` (usa LLM para procesar banks) |
| **Deliver** | `local` |
| **Estado** | ✅ Activo |
| **Último run** | 2026-06-28 02:19 UTC — OK |

### Qué hace
1. Descubre todos los banks vía `list_banks()`
2. Exporta cada bank como JSON → `infrastructure/hermes/banks/<bank>/YYYY-MM-DD.json`
3. Ejecuta `reflect` + `retain` diario sobre cada bank
4. Commitea y pushea todo al repo

### Banks actuales (10 activos)
| Bank | Facts | Propósito |
|---|---|---|
| `hermes` | ~44 | Perfil del usuario, estado del agente |
| `toolset` | ~445 | Infraestructura, decisiones técnicas |
| `personal-buffer` | ~3 | Buffer de staging del perfil personal |
| `personal-profile` | 0 | Banco canónico del perfil personal |
| `kairos` | ~68 | Sistema de gobernanza |
| `researchit` | ~124 | Deep research engine |
| `cl-concerts-db` | ~45 | Proyecto música docta UAH |
| `yacv` | ~29 | YaCV resume builder |
| `evidencia-zero` | ~30 | Sanitización Ley Karin |
| `witral` | ~11 | Routing messaging→storage |

---

## 3. `populate-channel-aliases` — Sincronización de nombres de grupos WhatsApp

| Campo | Valor |
|---|---|
| **Job ID** | `populate-channel-aliases` (cron del sistema, no Hermes) |
| **Schedule** | Cada 10 minutos |
| **Script** | `populate-channel-aliases.sh` |
| **No-agent** | `true` (script puro, sin LLM) |
| **Deliver** | `local` (solo escribe en disco) |
| **Estado** | ✅ Activo |

### Qué hace
1. Lee `channel_directory.json` para descubrir grupos WhatsApp
2. Consulta `GET /chat/<jid>` en el bridge (`localhost:3000`) para cada grupo
3. Obtiene el nombre humano (`metadata.subject` desde Baileys groupMetadata)
4. Escribe `channel_aliases.json` para que Hermes resuelva JIDs a nombres
5. Solo actualiza entradas cuando cambian (evita escritura innecesaria)

### Dependencias
- Bridge de WhatsApp corriendo en `127.0.0.1:3000`
- `channel_directory.json` generado por Hermes gateway (cada 5 min)

---

## 4. `hermes-health-check` — Diagnóstico diario del sistema

| Campo | Valor |
|---|---|
| **Job ID** | `0a88e1791af5` |
| **Schedule** | Diario, 04:00 UTC (`0 4 * * *`) — 00:00 Chile |
| **Prompt** | Revisa CI/CD, mensajes pendientes, tareas pendientes, servicios |
| **Skills** | `github-pr-workflow`, `systematic-debugging` |
| **Deliver** | WhatsApp del usuario (orquestador) |
| **Estado** | ⚠️ Activo — último run falló (2026-06-26) |
| **Creado** | 2026-06-25 |

### Qué revisa
1. **CI/CD** — Últimos 3 runs; si alguno falló, diagnostica y sugiere corrección
2. **Mensajes pendientes** — Respuestas sin contestar en WhatsApp >12h
3. **Tareas pendientes** — Banks de Hindsight con work pendiente
4. **Servicios core** — hindsight, infisical, caddy, hermes-webui, hermes-gateway
5. **Reporte al usuario** — Resumen por WhatsApp. Si todo bien, mensaje breve. Si hay problemas, detalle.

---

## 5. `sesion-revision-personal` — Recordatorio de revisión de buffer personal

| Campo | Valor |
|---|---|
| **Job ID** | `ff80f6f321e1` |
| **Schedule** | One-shot: 2026-06-29 03:00 UTC (23:00 Chile 28 jun) |
| **Prompt** | Recordatorio para la primera sesión de revisión del buffer personal |
| **No-agent** | `false` |
| **Deliver** | `whatsapp:120363429377303869@g.us` (grupo Personal) |
| **Estado** | ✅ Agendado |

### Qué hace
Recuerda a Martín que es hora de revisar las entradas del buffer `personal-buffer` y clasificarlas como Terreno, Mito, Descartado o Diferido.

### Nota de diseño
Este cron se entrega exclusivamente al canal Personal porque pertenece al ámbito del perfil `personal`. No es un cron del orquestador — es un cron de perfil. En el futuro, los cron de perfil se entregan al canal del perfil correspondiente.

---

## 6. `hermes-deploy-watch` — Monitor de deploys (PAUSADO)

| Campo | Valor |
|---|---|
| **Job ID** | `9d95e690ba92` |
| **Schedule** | Cada 3 minutos |
| **Script** | `deploy-watch.sh` |
| **No-agent** | `true` |
| **Deliver** | WhatsApp del usuario (orquestador) |
| **Estado** | ⏸️ Pausado (desde 2026-06-25) |

---

## Estándar de gestión de cron

| Aspecto | Regla |
|---|---|
| **Creación** | Se crean vía `cronjob action=create` desde el chat donde se solicitan |
| **Delivery** | Si el cron pertenece a un perfil (ej: personal), delivery a ese canal. Si es transversal, al DM del orquestador. |
| **Versionado** | Todo cron nuevo se registra en este archivo (`CRONS.md`) en el repo toolset |
| **Actualización** | `cronjob action=update job_id=<id> ...` |
| **Pausa/Reanudación** | `cronjob action=pause/resume job_id=<id>` |
| **Eliminación** | `cronjob action=remove job_id=<id>`. Al eliminar, actualizar CRONS.md. |
| **One-shot vs recurrente** | Usar `repeat` para controlar: omitir = forever, 1 = una vez, N = N veces |
