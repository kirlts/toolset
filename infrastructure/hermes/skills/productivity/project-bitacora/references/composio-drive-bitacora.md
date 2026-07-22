# Bitácora en Google Drive vía Composio

Cómo escribir una entrada de bitácora en un Google Doc usando Composio MCP.

## Contexto

Los perfiles **trazambiental** y **desarrollo-trazambiental** tienen su bitácora en un Google Doc compartido, no en un archivo local. El ID del doc está definido en el SOUL.md del perfil como `drive-bitacora`.

## Flow

1. **Verificar conexión** con Google Drive/Google Docs en Composio:
   - `COMPOSIO_SEARCH_TOOLS` con `use_case: "write to google docs document"`
   - Si no hay conexión activa, iniciar con `COMPOSIO_MANAGE_CONNECTIONS` usando toolkit slugs: `['googledocs', 'googledrive']`

2. **Obtener el ID del doc** desde el SOUL.md del perfil activo. Buscar `drive-bitacora` o `REGLA ABSOLUTA — Bitácora`.

3. **Escribir la entrada** usando la tool de Google Docs para append (buscar tool slug tipo `GOOGLEDOCS_*` que permita insertar texto al final del documento).

4. **Formato de entrada** (mismo estándar que BITACORA.md):
   ```markdown
   ## YYYY-MM-DD — Título

   - Hecho/detalle relevante
   - Estado, ETA, responsable si aplica
   ```

## Tools relevantes (Composio)

Buscar vía `COMPOSIO_SEARCH_TOOLS`:
- Google Docs: `use_case: "append text to google docs document"`
- Google Drive: `use_case: "find file in google drive by name"`

Slugs típicos:
- `GOOGLEDOCS_DOCUMENTS_APPEND` o similar — append al doc
- `GOOGLEDRIVE_FIND_FILE` — buscar un doc por nombre si solo tienes el alias

## Pitfalls

- No asumir que el Google Doc existe — verificar con `GOOGLEDRIVE_FIND_FILE` usando el nombre del doc como respaldo si el ID directo falla.
- El formato de la entrada debe ser markdown simple (el Google Doc renderiza bien headers y bullets).
- Después de escribir, confirmar con el usuario mencionando el link del doc (se puede obtener el `webViewLink` de Drive).
- Si Composio no tiene Google Docs tool, usar Google Drive tool para exportar el doc, editarlo local, y re-subir.
