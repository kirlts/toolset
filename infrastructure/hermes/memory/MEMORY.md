gh autenticado como kirlts vía HTTPS/token (no SSH). Usar `gh repo clone <owner>/<repo>` en vez de `git clone git@github.com:...` para clonar.
§
User does NOT want to be asked for approval on terminal heredoc/script execution. The phrase was "Todo será approve always, no me molestes para eso". When running commands that trigger approval dialogs, just proceed — user considers it noise.
§
User Martín Gil, dueño de toolset personal. Trabaja en proyecto cl-concerts-db (jpgil/cl-concerts-db), plataforma Flask para catálogo de música docta en Chile, Universidad Alberto Hurtado.
§
User espera que se sigan las reglas de SOUL.md — usa Kilo CLI para tareas de código, no tools directas.
§
User valora respuestas breves, directas, sin verborrea. Prefiere análisis sintético con veredictos claros, especialmente para comunicar a terceros no técnicos.
§
Proyecto cl-concerts-db tiene ambiente staging en UAH (172.16.8.58, usuario clconcert2, vía VPN). Rama master es producción protegida. El técnico UAH que gestiona despliegue se llama Óscar.
§
KILO-01: toda invocación a Kilo CLI DEBE prepender instrucción permanente sobre deepseek v4 único + seguir .agents/ + docs/RULES.md. Documentado en SOUL.md §Reglas y en ambos skills kilo-code §PREAMBLE OBLIGATORIO.
§
Sync diario implementado: 2 cron jobs (01:00 archivos, 02:00 banks Hindsight). SOUL.md + skills + config + memory + scripts versionados en toolset infra/hermes/. Banks exportados JSON diarios (backup/audit). Session start DEBE recall(bank=hermes).
§
Cuando pregunten 'que haces'/'en que estas': revisar TODAS las sesiones activas via session_search() (sin query = browse mode) + subagentes delegados + procesos bg + cron jobs. NO asumir idle. NO incluir ps aux/systemd/docker. En 24-jun-2026 fallé esto y el usuario me corrigió.