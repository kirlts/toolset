# MEMORY: Transferable Heuristics

> Repositorio de patrones y lecciones aplicables a cualquier proyecto de software.
> Archivo append-only.

## Consolidation Protocol

MEMORY.md is a working buffer. When it approaches capacity (~80% of 2200 chars):
1. Run `reflect(bank="toolset")` to synthesize learnings into structured observations.
2. Run `retain(bank="toolset")` to persist in Hindsight long-term memory.
3. Clear this buffer.

This prevents context saturation and ensures durable knowledge retention.

---

## [HEU-001] Tipo de credencial OAuth para servidores MCP remotos

**Date:** 2026-06-21
**Origin:** Resolucion de problemas de conexion con el servidor MCP nativo de Google Drive.
**Pattern:** El uso de credenciales de tipo Desktop OAuth en agentes que corren en entornos virtuales, contenedores remotos o terminales en la nube genera un fallo de redireccion (redirect_uri_mismatch). Esto ocurre porque las aplicaciones de escritorio asumen un servidor web local loopback (localhost) que no esta expuesto en la red publica del agente.
**Lesson:** Al configurar conexiones OAuth para agentes remotos o IDEs en la nube, se deben generar credenciales de tipo Aplicacion Web (Web Application) especificando la URL de callback correspondiente (ej. https://antigravity.google/oauth-callback).
**Source:** [Confirmed by user - no external source]

---

## [HEU-002] OpenSSH/PKCS#8 private key format incompatible with OCI CLI

**Date:** 2026-06-22
**Origin:** Depuración de autenticación de OCI CLI con API keys.
**Pattern:** Las claves generadas con `openssl genrsa` en versiones recientes de OpenSSL producen formato PKCS#8 (`-----BEGIN PRIVATE KEY-----`) en lugar del formato RSA tradicional (`-----BEGIN RSA PRIVATE KEY-----`). El OCI CLI/SDK puede rechazar estas claves con `ServiceError: NotAuthenticated` sin indicar que la causa es el formato de la clave, no la validez de la misma.
**Lesson:** Al generar claves API para OCI, forzar la conversión al formato tradicional: `openssl rsa -in <key.pem> -out <key_rsa.pem>`. Verificar el fingerprint con `openssl rsa -pubin -in <public.pem> -outform DER | openssl md5 -c` que debe coincidir con lo que muestra la consola de OCI.
**Source:** [Confirmed by user - verified empirically]

---

## [HEU-003] OCI Workload Identity Federation — flujo OIDC bloqueado en token exchange

**Date:** 2026-06-22
**Origin:** Intento fallido de autenticación OIDC desde GitHub Actions a OCI mediante Identity Propagation Trust.
**Pattern:** Aunque el Identity Propagation Trust esté correctamente configurado (issuer, oauthClients, clientClaimValues, rules) y la Confidential App esté activa con los grant types correctos, el endpoint `/oauth2/v1/token` del dominio OCI puede rechazar el JWT assertion con `invalid_request` genérico. Esto no es un error de configuración del trust sino un bloqueo a nivel del endpoint OAuth que requiere investigación adicional. Como workaround temporal, la API key funciona sin problemas para CI/CD.
**Lesson:** El camino OIDC nativo para OCI desde GitHub Actions no es plug-and-play. Requiere más investigación del endpoint OAuth del dominio, y posiblemente intervención del soporte de Oracle o exploración de rutas alternativas de autenticación. Tener el plan B de API key listo ahorra horas de bloqueo.
**Source:** [Confirmed by user - no external source]
