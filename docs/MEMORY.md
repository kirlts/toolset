# MEMORY: Transferable Heuristics

> Repositorio de patrones y lecciones aplicables a cualquier proyecto de software.
> Archivo append-only. Prohibido reducir, borrar o resumir su contenido previo.

| Symbol | Meaning |
|---|---|
| 🧠 | Heuristica transferible aprendida |

---

## [HEU-001] Tipo de credencial OAuth para servidores MCP remotos

**Date:** 2026-06-21
**Origin:** Resolucion de problemas de conexion con el servidor MCP nativo de Google Drive.
**Pattern:** El uso de credenciales de tipo Desktop OAuth en agentes que corren en entornos virtuales, contenedores remotos o terminales en la nube genera un fallo de redireccion (redirect_uri_mismatch). Esto ocurre porque las aplicaciones de escritorio asumen un servidor web local loopback (localhost) que no esta expuesto en la red publica del agente.
**Lesson:** Al configurar conexiones OAuth para agentes remotos o IDEs en la nube, se deben generar credenciales de tipo Aplicacion Web (Web Application) especificando la URL de callback correspondiente (ej. https://antigravity.google/oauth-callback).
**Source:** [Confirmed by user - no external source]
