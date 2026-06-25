User Martín Gil, dueño de toolset personal. Trabaja en proyecto cl-concerts-db (jpgil/cl-concerts-db), plataforma Flask para catálogo de música docta en Chile, Universidad Alberto Hurtado.
§
User valora respuestas breves, directas, sin verborrea. Prefiere análisis sintético con veredictos claros, especialmente para comunicar a terceros no técnicos.
§
Cuando pregunten 'que haces'/'en que estas': revisar TODAS las sesiones activas via session_search() (sin query = browse mode) + subagentes delegados + procesos bg + cron jobs. NO asumir idle. NO incluir ps aux/systemd/docker. En 24-jun-2026 fallé esto y el usuario me corrigió.
§
User espera APPROVE ALWAYS: no pedir confirmación para ningún comando. Toda generación de código, testeo y documentación DELEGAR a Kilo CLI (kilo run --auto). Hermes solo orquesta a alto nivel. Seguir SOUL.md y KILO-01 estrictamente.
§
Todo proyecto nuevo DEBE clonar .agents/ desde kirlts/kairos en la raíz. Reglas .agents/ son OBLIGATORIAS. Workflow /document debe ejecutarse periódicamente. Kairos governance es requisito.
§
SECRETS siempre por Infisical, nunca hardcodeados. El usuario fue explícito: 'todo lo que tiene que ver con secretos se maneja por infisical'. Si pongo connection_id o API key en código, se pierde en el próximo deploy. Leer de env vars que vienen de Infisical.
§
ResearchIt: Reddit vía MCP Composio es fuente OBLIGATORIA (mín. 10 resultados). 30+ fuentes mínimo por investigación combinando web + Reddit. PDF mobile: DejaVu Sans 11pt+, justificado, márgenes 1.6cm.
§
TODO el código va por Kilo CLI sin excepción — features, debugging, fixes de una línea. Hermes NO escribe código directo. El usuario valora resultados completos funcionales sobre explicaciones parciales.
§
SESSION LEARNINGS (24-jun-2026): Typst escaping order critical (links→code→escape). @ and <> cause label errors. PDF mobile: DejaVu Sans 11pt justified, sin cmarker. .env masked values (***) break Python loading — always use set -a + source. ResearchIt: 30+ sources default, Reddit via Composio MCP.