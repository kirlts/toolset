# GitHub Releases como File Host Intermediario para Composio

Cuando Composio MCP necesita un archivo local (para s3key, Google Drive upload, etc.)
pero no puede acceder al filesystem del VPS, y pasar base64 inline es inviable para
archivos > 100KB:

## Flujo

```bash
# 1. Subir a GitHub Releases
gh release create temp-upload-$(date +%s) /ruta/al/archivo.pdf \
  --repo kirlts/toolset \
  --title "Upload temporal" \
  --notes "Archivo temporal para operación MCP"

# 2. Obtener URL de descarga directa
#    https://github.com/<user>/<repo>/releases/download/<tag>/<filename>

# 3. Usar esa URL desde COMPOSIO_REMOTE_WORKBENCH
#    El workbench puede descargar desde URLs públicas

# 4. Eliminar después (opcional)
gh release delete temp-upload-$(date +%s) --repo kirlts/toolset -y
```

## Ventajas

- Sin dependencias externas (usa gh CLI ya autenticado)
- Sin límite de tamaño (GitHub acepta releases hasta 2GB)
- URL pública accesible desde cualquier workbench/sandbox
- Operación reversible

## Cuándo usarlo

| Archivo | Recomendación |
|---|---|
| < 50KB | Base64 inline |
| 50-500KB, Drive disponible | Google Drive |
| > 100KB, Drive falla | **GitHub Releases** |
