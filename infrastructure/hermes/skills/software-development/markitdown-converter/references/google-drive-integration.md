# Google Drive → MarkItDown Integration

Flujo comprobado para obtener un Google Doc desde Drive y convertirlo a Markdown con markitdown.

## Pipeline completo

```
Google Drive (Google Doc nativo)
  → Composio GOOGLEDRIVE_FIND_FILE (buscar por nombre)
  → Composio GOOGLEDRIVE_DOWNLOAD_FILE (exportar como PDF)
  → curl (descargar desde S3 URL temporal)
  → markitdown (convertir PDF a Markdown)
  → LLM (analizar el Markdown)
```

## Paso a paso

### 1. Buscar el archivo

Usar Composio con GOOGLEDRIVE_FIND_FILE. El nombre debe ir con `contains` para coincidencias parciales:

```json
{
  "q": "name contains 'Nombre del Documento'",
  "fields": "files(id,name,mimeType,webViewLink,modifiedTime)",
  "corpora": "allDrives"
}
```

Respuesta incluye `id`, `mimeType` (ej: `application/vnd.google-apps.document` para Google Docs nativos), y `webViewLink`.

### 2. Exportar el documento

Si es un Google Doc nativo (mimeType `application/vnd.google-apps.document`), NO se descarga directamente — se **exporta**. Usar GOOGLEDRIVE_DOWNLOAD_FILE con `mime_type`:

```json
{
  "fileId": "<id-del-archivo>",
  "mime_type": "application/pdf"
}
```

La respuesta incluye `downloaded_file_content.s3url` — una URL temporal en S3 (expira en 1 hora). No intentes guardar el PDF inline; baja la URL.

Export MIME types útiles:
| Formato | mime_type |
|---------|-----------|
| PDF | `application/pdf` |
| DOCX | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| Markdown | `text/markdown` |
| Texto plano | `text/plain` |
| HTML | `text/html` |

### 3. Descargar el PDF desde S3

```bash
curl -sL -o /tmp/documento.pdf "<s3url>"
```

Sync `sync_response_to_workbench=true` al exportar para tener la URL manejable. La URL S3 es sensible a caracteres especiales — entrecomillarla siempre.

### 4. Convertir a Markdown

```bash
markitdown /tmp/documento.pdf 2>/dev/null
```

### 5. Analizar

Leer el output de markitdown (stdout) directamente. No volver a leer el PDF original.

## Pitfalls conocidos

- **No confundir fileId con URL**: El fileId de Google Drive es un string opaco tipo `1TMAy4tHzWuCioxSK5hvbu8aHIQAZ3jYElGUCb9vpuiM`. No pasar URLs completas.
- **S3 URL expira**: La URL de `downloaded_file_content.s3url` tiene `X-Amz-Expires=3600` (1 hora). Descargar inmediatamente después de obtenerla.
- **Google Docs nativos NO son archivos**: No se pueden descargar con GOOGLEDRIVE_DOWNLOAD_FILE sin `mime_type`. Siempre hay que exportarlos.
- **El wrapper `gdown` no existe**: No intentar `gdown` ni scripts caseros. Usar Composio + Google Drive.
- **No background**: Descargar y convertir en foreground. No mandar el curl a background — necesitas el resultado para continuar.
