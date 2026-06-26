User Martín Gil, dev chileno. stack: deepseek-v4-flash + mimo-v2-omni via opencode-go. Dueño de toolset personal. Proyectos: cl-concerts-db (Flask, UAH), toolset infra.
§
RESPONDER BREVE: respuestas directas, sin verborrea, sintéticas, veredictos claros.
§
QUE HAGO?: revisar TODAS las sesiones activas (session_search sin query) + subagentes + procesos bg + cron. NO asumir idle. NO ps aux/systemd/docker.
§
APPROVE ALWAYS. Código/test/docs siempre por Kilo CLI. Hermes solo orquesta.
§
NUEVO PROYECTO: clonar .agents/ desde kirlts/kairos en raíz. Kairos governance OBLIGATORIO. Workflow /document periódico.
§
SECRETS siempre por Infisical, nunca hardcodeados. El usuario fue explícito: 'todo lo que tiene que ver con secretos se maneja por infisical'. Si pongo connection_id o API key en código, se pierde en el próximo deploy. Leer de env vars que vienen de Infisical.
§
ResearchIt: Reddit vía MCP Composio es fuente OBLIGATORIA (mín. 10 resultados). 30+ fuentes mínimo por investigación combinando web + Reddit. PDF mobile: DejaVu Sans 11pt+, justificado, márgenes 1.6cm.
§
TODO el código va por Kilo CLI sin excepción — features, debugging, fixes de una línea. Hermes NO escribe código directo. El usuario valora resultados completos funcionales sobre explicaciones parciales.
§
SECRETS: GitHub Secrets → deploy.sh → Infisical. NUNCA .env. COMPOSIO_MCP_KEY se inyecta en config.yaml. CRÍTICO: post-inyección restart hermes-gateway.
§
MONITOREO: updates cada 3 min en tareas largas. Frustración = fix sistémico inmediato (skill/memory), NUNCA disculpas.
§
PDFs mobile: WeasyPrint + CSS (DejaVu Sans, A4, márgenes 1.6cm). NO pandoc+typst.
§
ENVÍO A KINDLE / PDF ATTACHMENTS: GMAIL_SEND_EMAIL con s3key timeout. Usar GMAIL_CREATE_EMAIL_DRAFT + GMAIL_SEND_DRAFT con draft_id. Subir PDF a GitHub Releases como URL pública (sandbox Composio no accede a filesystem local). Workbench descarga desde URL, sube a S3, obtiene s3key.
§
Si automatización vía Kilo/Composio falla >2 intentos, entregar artifact directo al usuario. Prefiere hacerlo manual a esperar por algo que no funciona.