# Envío de PDFs por Gmail vía Composio MCP + Kilo CLI

Cuando necesites enviar un PDF por Gmail pero no tengas acceso directo a Composio MCP
(porque el gateway no lo cargó), usa Kilo CLI que sí tiene su propia configuración MCP.

## Requisitos

- `COMPOSIO_MCP_KEY` debe estar disponible como env var en el shell
- Composio MCP configurado en `~/.config/kilo/kilo.jsonc`
- El usuario debe autorizar la conexión OAuth de Gmail (link de ~10 min de validez)

## Flujo Básico

1. Kilo usa `COMPOSIO_SEARCH_TOOLS` para encontrar la tool de Gmail
2. `COMPOSIO_MANAGE_CONNECTIONS` para conectar Gmail (genera link OAuth)
3. Usuario autoriza en navegador
4. Kilo envía el email con el PDF adjunto

## Problema: Archivos Locales y s3key

La tool `GMAIL_SEND_EMAIL` de Composio requiere un `s3key` para adjuntar archivos.
El `s3key` se obtiene subiendo el archivo al S3 de Composio, típicamente vía
`COMPOSIO_REMOTE_WORKBENCH`. **Problema:** el sandbox del workbench NO tiene acceso
al filesystem local del VPS, y pasar base64 inline de archivos > 100KB es inviable.

## Solución 1: Google Drive (preferida)

Subir el archivo a Google Drive (Composio tiene acceso) y adjuntarlo desde Drive:
1. Kilo usa tool de Google Drive para upload del PDF local → obtiene fileId
2. Kilo usa GMAIL_SEND_EMAIL con attachment desde Drive

## Solución 2: GitHub Releases (fallback)

Ver `toolset-mcp-integration/references/github-releases-file-host.md`:
1. Subir PDF a GitHub Releases con `gh release create`
2. Kilo descarga desde URL pública en el workbench
3. Sube a S3 y obtiene s3key
4. Envía email

## Datos del usuario

- From: martin.gil.o@gmail.com
- Kindle: martin.gil.o.kindle@kindle.com
- Gmail ya autenticado en Composio
