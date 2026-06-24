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
User quiere versionar TODO el estado de Hermes en toolset repo DIARIO: SOUL.md, skills, config.yaml, scripts, memories, y banks como JSON export. El repo debe ser fuente de verdad del agente; la VM es host descartable.
§
User entiende que JSON dumps de banks (con fecha) son backup/audit/recovery, no runtime. Runtime usa recall/retain vs Hindsight MCP vivo. Preguntó: "si los guardas con fecha, el agente no tendrá problemas al invocarlos?" — respuesta correcta: no, porque nunca los lee.
§
Arquitectura aprobada: cron diario reflect→retain al bank hermes + sync al repo. Session start debe hacer recall al bank hermes. Reversibilidad vía git revert. Banks exportados como JSON para portabilidad.