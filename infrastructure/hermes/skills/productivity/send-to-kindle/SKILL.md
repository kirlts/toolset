---
name: send-to-kindle
description: Enviar PDFs a Kindle por Gmail usando Composio MCP — SINGLE SHOT, sin duplicados
status: fixed
---

# Enviar a Kindle (FIXED)

⚠️ **IMPORTANTE: SINGLE SHOT ESTRICTO.** NO reintentar. NO lanzar múltiples prompts.
Cada ejecución produce EXACTAMENTE 1 email. Si falla, reportar error, no reintentar.

## Regla de Oro

**UNA SOLA ejecución. CERO reintentos.** `GMAIL_SEND_EMAIL` con s3key hace timeout
pero el email SÍ se envía — reintentar = duplicado garantizado.

## Problema conocido

`GMAIL_SEND_EMAIL` con attachment vía s3key falla por timeout (MCP error -32001).
La respuesta no llega al cliente pero Gmail SÍ envió el email. **NO reintentar.**

## Flujo Único (validado)

### 1. Subir PDF a URL pública temporal

```bash
gh release create temp-pdf-$(date +%s) /ruta/al/archivo.pdf --repo kirlts/toolset --title "Temp PDF" --notes "Temporary"
```

### 2. Ejecutar UN SOLO envío vía MCP Composio directo (NO Kilo CLI)

Usar las MCP tools de Composio desde Hermes (no Kilo):

a) COMPOSIO_SEARCH_TOOLS para confirmar GMAIL activo
b) COMPOSIO_REMOTE_WORKBENCH:
   - Descargar PDF desde URL de GitHub Releases
   - Subir a S3 Composio → obtener s3key
c) GMAIL_CREATE_EMAIL_DRAFT con el s3key (1 sola vez)
d) GMAIL_SEND_DRAFT con el draft_id (1 sola vez)

**NO USAR Kilo CLI** — Kilo tiene su propia lógica de reintentos que causa duplicados.

### 3. Verificación

Después de enviar, buscar en Gmail sent folder:
```
query: "to:martin.gil.o.kindle@kindle.com" (últimos 5 min)
```
Confirmar que haya EXACTAMENTE 1 mensaje nuevo.

## Historial de Bugs

| Fecha | Incidente | Causa | Fix |
|---|---|---|---|
| 26-Jun-2026 | 8 copias del mismo PDF a Kindle (03:31-03:40 UTC) | Múltiples prompts Kilo + timeout-retry loop en GMAIL_SEND_EMAIL | Single shot directo desde Hermes MCP, sin Kilo, sin reintentos |

## Notas

- NO usar .env para secrets
- s3key se obtiene vía REMOTE_WORKBENCH (descarga desde URL pública → upload a S3)
- El workbench NO tiene acceso a filesystem local
- Validado: 26-Jun-2026, single shot sin duplicados
