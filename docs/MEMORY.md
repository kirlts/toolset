# MEMORY: Transferable Heuristics

> Repositorio de patrones y lecciones aplicables a cualquier proyecto de software.
> Archivo append-only.

## Consolidation Protocol

MEMORY.md is a working buffer. When it approaches capacity (~85% of 2200 chars):
1. Run `reflect(bank_id="hermes")` to synthesize learnings into structured observations.
2. Run `retain(bank_id="hermes")` to persist in Hindsight long-term memory.
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

---

## [HEU-006] Un bind mount de ARCHIVO se ata al inode: `mv` lo desconecta en silencio

**Date:** 2026-07-23
**Origin:** deploy.sh transferia el Caddyfile con `sudo mv -f`. El archivo en disco cambiaba, el contenedor seguia sirviendo la version anterior, y ningun paso fallaba.
**Pattern:** Docker resuelve un bind mount de archivo individual al inode existente al montar, no a la ruta. Cualquier escritura no in-place (`mv`, `sed -i`, y el guardado atomico de casi todo editor moderno) crea un inode nuevo y deja al contenedor apuntando al viejo. Con directorios no ocurre: el inode del directorio no cambia, solo su contenido.
**Lesson:** Para actualizar un archivo bind-mounteado desde un script de deploy, escribir in-place (`tee`, `cat >`) y nunca `mv`. El sintoma es cruel porque no hay error: el deploy reporta exito y el servicio corre con configuracion vieja. Corolario: transferir no es aplicar. Hay que verificar por separado si el proceso necesita recarga.
**Source:** [moby/moby#6011](https://github.com/moby/moby/issues/6011), [Docker Docs: Bind mounts](https://docs.docker.com/engine/storage/bind-mounts/)

---

## [HEU-007] Un catch-all que responde 200 rompe el descubrimiento por `/.well-known/`

**Date:** 2026-07-23
**Origin:** El conector de claude.ai fallaba con «no se pudo registrar con el servicio de inicio de sesion» contra un servidor MCP que no usa autenticacion.
**Pattern:** Los protocolos modernos descubren capacidades pidiendo rutas `/.well-known/`, y distinguen «no soportado» de «soportado» por el codigo de estado: 404 significa que no aplica. Un reverse proxy con catch-all tipo `try_files {path} index.html` responde 200 con HTML a CUALQUIER ruta desconocida, incluidas esas. El cliente concluye lo contrario de la realidad y arranca un flujo que no existe.
**Lesson:** Todo servidor detras de un catch-all debe devolver 404 explicito en las rutas de descubrimiento que no implementa. Vale para OAuth (RFC 8414, RFC 9728), OpenID Connect y cualquier negociacion basada en `/.well-known/`. Sintoma reconocible: un cliente exige autenticacion contra un servicio que no la tiene.
**Source:** [RFC 9728: OAuth 2.0 Protected Resource Metadata](https://datatracker.ietf.org/doc/html/rfc9728)

---

## [HEU-008] Un proxy que despoja el prefijo produce redirects rotos

**Date:** 2026-07-23
**Origin:** `/kb/<slug>/mcp/` devolvia un 307 hacia `http://host/<slug>/mcp`: sin el prefijo y degradado a http.
**Pattern:** Cuando el proxy quita el prefijo de ruta antes de pasar la peticion (`handle_path` en Caddy, `strip_prefix` en otros), la aplicacion ignora que ese prefijo existe. Cualquier URL absoluta que construya (redirects de canonicalizacion, `Location`, enlaces) sale sin el prefijo, y si ademas habla http con el proxy, sin TLS. Es invisible mientras nadie pida una ruta que dispare un redirect: basta un slash final.
**Lesson:** O la aplicacion conoce su prefijo publico (montarla con el prefijo completo, o propagar `X-Forwarded-Prefix` y honrarlo), o el proxy canonicaliza en su borde antes de enrutar. Al publicar una ruta, probar sus variantes: con slash final, sin el, y siguiendo el redirect.
**Source:** [MDN: X-Forwarded-Proto](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Forwarded-Proto)

---

## [HEU-009] La descripcion de una herramienta decide si el agente la usa bien

**Date:** 2026-07-23
**Origin:** Un servidor MCP cuyas herramientas decian «busca en esta base de conocimiento» sin nombrar el dominio. El agente solo podia inferirlo del nombre del conector, que lo elige quien lo instala.
**Pattern:** Anthropic documenta que la descripcion es «by far the most important factor in tool performance», y que debe cubrir cuatro cosas: que hace, cuando usarla y cuando NO, que significa cada parametro, y que informacion NO devuelve. El criterio rector es escribirla como el onboarding de alguien nuevo, explicitando el contexto que uno da por sabido, incluida la terminologia de nicho.
**Lesson:** Al exponer un servicio por MCP, la descripcion debe nombrar el dominio concreto y sus limites, no describir el mecanismo. Conviene derivar del propio contenido lo que envejece (los temas que cubre) y declarar a mano solo el encuadre, para que no quede vieja sin que nadie la mantenga.
**Source:** [Anthropic: Define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use), [Writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)

---

## [HEU-010] `pkill -f` mata al shell que lo invoca cuando el patrón viaja en su propia línea de comandos

**Date:** 2026-07-23
**Origin:** Un `pkill -f "bridge.js --port 3001"` dentro de un `ssh '...'` cerró la conexión de golpe, sin imprimir nada y sin ejecutar los pasos siguientes.
**Pattern:** `-f` compara el patrón contra la línea de comandos completa de cada proceso. Un shell que ejecuta un script contiene el texto del script en su propio argv, así que si el patrón aparece ahí, el shell se convierte en su propia víctima. `pkill` se excluye a sí mismo del match, pero no excluye a su padre. Un `|| true` no protege: el shell no falla, recibe una señal. El síntoma es una terminación limpia y muda que se confunde con un problema de red o de permisos.
**Lesson:** Romper la auto-coincidencia con una clase de caracteres, `pkill -f "bridge[.]js --port 3001"`, que matchea el proceso real pero no el literal del script. Es el mismo truco que `ps aux | grep "[s]sh"`. Vale para todo comando que filtre por línea de comandos, incluidos `pgrep` y `killall -r`. Regla general: al buscar procesos por su texto, verificar siempre si el propio buscador queda dentro del conjunto buscado.
**Source:** [Wikipedia: pkill](https://en.wikipedia.org/wiki/Pkill), [pgrep and pkill: Linux scripting process management friends](https://opensourcehacker.com/2012/11/26/pgrep-and-pkill-your-linux-scripting-process-management-friends/)

---

## [HEU-011] Un supervisor que reinicia sin backoff disfraza una falla permanente de falla intermitente

**Date:** 2026-07-23
**Origin:** Un chequeo cada 5 minutos reportaba un bridge de WhatsApp «no escuchando» de forma errática. No era errático: el proceso estaba en crashloop y el chequeo caía en puntos distintos del ciclo.
**Pattern:** Cuando un supervisor relanza de inmediato un proceso que falla por una causa permanente, el servicio alterna entre arriba y abajo varias veces por minuto. Cualquier observador externo que muestree a intervalos fijos obtiene resultados contradictorios, y esa contradicción desvía el diagnóstico hacia la red, hacia el propio monitor o hacia una supuesta condición de carrera, cuando la causa es estable y está en los logs del proceso. Los orquestadores maduros evitan justo esto: Kubernetes marca `CrashLoopBackOff` y espacia los reintentos de forma exponencial, convirtiendo el parpadeo en un estado nombrado y visible.
**Lesson:** Ante un síntoma intermitente en un proceso supervisado, la primera hipótesis es el crashloop, no la intermitencia real. Se confirma barato: muestrear el PID varias veces seguidas y contar reinicios en el log. Un PID que cambia entre muestras es un ciclo, no un servicio inestable. Al diseñar supervisión, todo reinicio automático necesita backoff creciente y un tope que declare el estado degradado; sin eso, el sistema oculta la falla en vez de exhibirla.
**Source:** [Kubernetes Health Checks and Probes (CrashLoopBackOff y backoff exponencial)](https://betterstack.com/community/guides/monitoring/kubernetes-health-checks/)

---

## [HEU-012] Una opción de configuración que el parser descarta en silencio produce una defensa fantasma

**Date:** 2026-08-04
**Origin:** Un agente declaraba respaldo de modelo en su YAML desde hacía un mes. El parser sólo aceptaba entradas con forma de diccionario, la entrada estaba escrita como cadena suelta, y la descartaba sin advertir. El respaldo no existió nunca: el CLI del propio sistema respondía «No fallback providers configured» mientras el changelog afirmaba lo contrario.
**Pattern:** El valor mal formado no rompe el arranque ni aparece en los logs; simplemente deja de existir. Como la garantía que sostenía era un camino de excepción (respaldo, reintento, límite), su ausencia sólo se manifiesta el día del incidente que debía cubrir, y ese día el diagnóstico apunta al componente que falló, no a la defensa que nunca estuvo. La literatura mide la magnitud: entre el 14% y el 93% de los parámetros críticos carecen de código que valide su valor, y sólo entre el 7% y el 15% de los problemas de configuración emiten un mensaje que señale el parámetro culpable; un mensaje que sí lo señala acorta el diagnóstico entre 3 y 13 veces.
**Lesson:** El estado efectivo de una configuración se lee con el comando que la interpreta, nunca con el archivo. Toda garantía declarada en configuración (respaldos, umbrales, listas de permitidos) se verifica por interrogación del sistema y esa comprobación se convierte en invariante de despliegue. Al escribir el parser, la contraparte: una entrada con forma inválida se rechaza ruidosamente en el arranque en vez de filtrarse, porque un filtro silencioso convierte un error de sintaxis en una promesa falsa.
**Source:** [Yin et al., An Empirical Study on Configuration Errors in Commercial and Open Source Systems, SOSP 2011](https://www.sigops.org/s/conferences/sosp/2011/current/2011-Cascais/printable/12-yin.pdf), [Xu et al., Early Detection of Configuration Errors to Reduce Failure Damage](https://tianyin.github.io/pub/pcheck.pdf)

---

## [HEU-013] El costo de arranque de un servicio se multiplica por su frecuencia de reinicio, y esa frecuencia vive en otro archivo

**Date:** 2026-08-07
**Origin:** `kb-mcp` reconstruye su índice semántico AL ARRANCAR. Con una tabla de embeddings estáticos eso era instantáneo, así que nadie lo contó como costo. Al evaluar reemplazarla por un codificador real —que mejora la recuperación de forma medible— el arranque pasó a costar ~30 s. El dato que cambió la decisión no estaba en ese componente: `sync-kb.sh`, un cron aparte, **reinicia el contenedor cada vez que el contenido cambia**. Medido ese día: 28 reinicios en una jornada, o sea ~14 minutos diarios de servicio caído en tandas de medio minuto, contra un servicio que un equipo acababa de empezar a consultar.
**Pattern:** El costo de arranque y la frecuencia de reinicio se declaran en componentes distintos y nadie los multiplica. Un cambio que se lee barato en su propio archivo («treinta segundos, una vez») se convierte en un problema de disponibilidad por una decisión tomada en otro lado y en otro momento. La industria mide la misma asimetría en el sentido del costo: desde que el proveedor factura la fase de inicialización, la frecuencia de arranques en frío pasó de ser un problema de latencia a uno de gasto, con incrementos del 10 al 50 % en funciones con inicialización pesada. Y la contramedida es la misma en los dos dominios: precalentar o persistir lo caro en vez de recalcularlo.
**Lesson:** Antes de adoptar cualquier cosa que cueste al arrancar, se mide **cuántas veces arranca el proceso en un día real**, y ese número se busca FUERA del componente —en el cron, el supervisor, el orquestador—. Si el producto de las dos cifras no es aceptable, la salida no es descartar la mejora: es persistir el artefacto caro indexado por el hash de su entrada, de modo que un reinicio recalcule solo lo que cambió. Se implementa degradando bien: si no hay dónde escribir, el sistema se comporta como antes, y así el código se puede desplegar antes que el volumen que lo hace rendir.
**Source:** [Cold Start Latency in Serverless Computing: A Systematic Review (arXiv 2310.08437)](https://arxiv.org/html/2310.08437v2), [AWS Lambda cold starts: impact and cost](https://edgedelta.com/company/knowledge-center/aws-lambda-cold-start-cost), [Index warm-up and cold starts in AI databases](https://theaidatabaseblog.com/learn/index-warm-up-and-cold-starts/)
