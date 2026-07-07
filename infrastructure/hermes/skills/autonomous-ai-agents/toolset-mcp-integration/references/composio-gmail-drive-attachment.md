# Composio Gmail — Attachment via Google Drive

## Problema Original

Composio Gmail `GMAIL_SEND_EMAIL` requiere un `s3key` para adjuntar archivos. El `s3key` se obtiene subiendo el archivo al S3 de Composio. El método estándar es `COMPOSIO_REMOTE_WORKBENCH`, pero:

1. El sandbox no tiene acceso al filesystem del VPS → no puede leer `/home/opc/...`
2. Pasar el base64 inline (>128KB para un PDF de 96KB) es inviable como string en código Python

## Solución Validada

**Upload a Google Drive → Gmail desde Drive attachment.**

### Prompt para Kilo CLI

```
INSTRUCCIÓN PERMANENTE: Sigue las reglas de .agents/ y Docs/RULES.md.
Usa recall/retain en Hindsight con bank_id del repo activo.

## TAREA: [enviar/subir/etc.]

1. Archivo: /path/to/file.pdf

2. PRIMERO: usa COMPOSIO_SEARCH_TOOLS para encontrar:
   - La tool de Google Drive para subir/upload archivos
   - La tool de Gmail para enviar email con attachment desde Google Drive

3. SUBE el archivo a Google Drive usando la tool de Drive.
   - Asigna nombre al archivo
   - Obtén el fileId

4. ENVÍA el email por Gmail adjuntando el archivo desde Drive:
   - From: correo-del-usuario@gmail.com
   - To: destinatario@ejemplo.com
   - Subject: "Asunto del email"
   - Body: "Texto del cuerpo"
   - Attachment: el archivo desde Google Drive (usando el fileId)

5. IMPORTANTE: NO uses COMPOSIO_REMOTE_WORKBENCH.
   Usa directamente las tools de Google Drive.

6. Reporta el resultado: message ID de Gmail y fileId de Drive.
```

### Notas

- La conexión de Google Drive se autoriza vía OAuth igual que Gmail (link de Composio)
- Si el link expira (~10 min), relanzar Kilo: la autorización persiste
- El usuario debe abrir el link de autorización en el navegador
- Una vez autorizado, las ejecuciones subsecuentes no piden auth de nuevo

### Referencia

Incidente 25 Jun 2026: deploy #196, Composio MCP key injection sin gateway restart.
