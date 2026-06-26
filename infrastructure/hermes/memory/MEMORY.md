User Martín Gil, dev chileno. stack: deepseek-v4-flash + mimo-v2-omni via opencode-go. Dueño de toolset personal. Proyectos: cl-concerts-db (Flask, UAH), toolset infra.
§
RESPONDER BREVE: respuestas directas, sin verborrea, sintéticas, veredictos claros.
§
QUE HAGO?: revisar TODAS las sesiones activas (session_search sin query) + subagentes + procesos bg + cron. NO asumir idle. NO ps aux/systemd/docker.
§
APPROVE ALWAYS: NO pedir confirmación. Todo código/test/docs por Kilo CLI (kilo run --auto). Hermes solo orquesta.
§
NUEVO PROYECTO: clonar .agents/ desde kirlts/kairos en raíz. Kairos governance OBLIGATORIO. Workflow /document periódico.
§
SECRETS siempre por Infisical, nunca hardcodeados. El usuario fue explícito: 'todo lo que tiene que ver con secretos se maneja por infisical'. Si pongo connection_id o API key en código, se pierde en el próximo deploy. Leer de env vars que vienen de Infisical.
§
ResearchIt: Reddit vía MCP Composio es fuente OBLIGATORIA (mín. 10 resultados). 30+ fuentes mínimo por investigación combinando web + Reddit. PDF mobile: DejaVu Sans 11pt+, justificado, márgenes 1.6cm.
§
TODO el código va por Kilo CLI sin excepción — features, debugging, fixes de una línea. Hermes NO escribe código directo. El usuario valora resultados completos funcionales sobre explicaciones parciales.
§
SECRETS pipeline: GitHub Secrets → deploy.sh → Infisical VPS. NADIE crea .env. COMPOSIO_MCP_KEY se inyecta en config.yaml. CRÍTICO: post-inyección DEBE restart hermes-gateway (key nueva solo se carga al reiniciar).
§
MONITOREO: dar updates REGULARES al usuario cada tool call relevante durante deploys/monitoreo. NO esperar al resultado final. Cada paso = update inmediato. Esto es OBLIGATORIO.