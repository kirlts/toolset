# MEMORY: Transferable Heuristics

> Repositorio de patrones y lecciones aplicables a cualquier proyecto de software.
> Archivo append-only.

## Consolidation Protocol

MEMORY.md is a working buffer. When it approaches capacity (~85% of 2200 chars):
1. Run `reflect(bank="hermes")` to synthesize learnings into structured observations.
2. Run `retain(bank="hermes")` to persist in Hindsight long-term memory.
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

---

## [HEU-004] GITHUB_OUTPUT multiline values require single-line workaround

**Date:** 2026-06-26
**Origin:** Pipeline falló porque `git diff --name-only` retorna múltiples líneas y `$GITHUB_OUTPUT` las rechaza.
**Pattern:** GitHub Actions `$GITHUB_OUTPUT` no soporta valores multiline. Si un script genera output con saltos de línea, falla con `Invalid format`.
**Lesson:** Para outputs condicionales usar flags booleanos por feature, no el raw multiline. Si se necesita el valor completo, usar delimiters: `echo "key<<EOF" >> $GITHUB_OUTPUT`.
**Source:** [Confirmed by user - no external source]

---

## [HEU-005] chattr +i en archivos deployados rompe deploys subsecuentes

**Date:** 2026-06-26
**Origin:** chattr +i en config.yaml de Hermes; el siguiente deploy no pudo sobrescribirlo.
**Pattern:** El flag immutable (`chattr +i`) previene writes de cualquier proceso, incluso sudo. Un deploy que intenta cp/chown sobre un archivo inmutable falla.
**Lesson:** Al inmutar archivos via deploy, hacer `chattr -i` antes de escribir y `chattr +i` después en el mismo SSH call. Esto asegura que el deploy siempre pueda actualizar el archivo.
**Source:** [Confirmed by user - no external source]
