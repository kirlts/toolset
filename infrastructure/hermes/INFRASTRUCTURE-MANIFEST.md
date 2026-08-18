# Infrastructure Manifest — Toolset Personal

> Single source of truth for ALL Hermes configuration files.
> Cada archivo .md operativo de Hermes DEBE estar listado aqui.
> Creado: 2026-06-28. Se actualiza cada vez que se modifica un archivo de configuracion.

---

## Structure

| File | Purpose | Sync to VPS | Last Updated |
|---|---|---|---|
| `infrastructure/hermes/SOUL.md` | Identidad, tono, algoritmo de ruteo, memoria del orquestador. ~70 lineas. Sin contenido operativo. | deploy.sh (sobrescribe) | 2026-06-28 |
| `infrastructure/hermes-context.md` | Contexto operativo de Hermes (AGENTS.md): capacidades, arquitectura, banks, reglas, routing detallado | deploy.sh -> ~/.hermes/context.md + /opt/toolset-repo/AGENTS.md | 2026-06-28 |
| `infrastructure/hermes/config.yaml` | Config estructural: MCP servers, external_skills_dirs, modelo, proveedor, credential_pool_strategies | deploy.sh + inject-composio-key.py | 2026-07-19 |
| `infrastructure/hermes/CRONS.md` | Documentacion de cron jobs activos | Repo (documentacion, no ejecutable) | 2026-06-28 |
| `infrastructure/hermes/scripts/populate-channel-aliases.sh` | Consulta bridge GET /chat/:id, escribe channel_aliases.json con {name, desc} | deploy.sh (paso 1b) | 2026-06-28 |
| `infrastructure/hermes/scripts/patch-bridge.sh` | Parchea bridge.js para exponer metadata.desc desde Baileys groupMetadata | deploy.sh (paso 1b) | 2026-06-29 |
| `infrastructure/hermes/scripts/monitor-credential-rotation.sh` | Monitorea auth.json para rotacion de credenciales y notifica via WhatsApp al grupo Toolset | deploy.sh (paso 1b) + cron (*/1 min) | 2026-07-19 |
| `infrastructure/hermes/whatsapp-groups.yaml` | Mapeo JID -> {type, name, desc, repo, profile, skills} para ruteo determinista | deploy.sh (paso 1b) -> ~/.hermes/ | 2026-06-28 |
| `infrastructure/hermes-skills/whatsapp-router/SKILL.md` | Skill de ruteo determinista de mensajes WhatsApp segun tipo de grupo | external_skills_dirs (repo clone) | 2026-06-28 |
| `infrastructure/hermes-skills/group-onboarding/SKILL.md` | Onboarding 3 fases MECE: crea bank, SOUL.md, YAML, perfil worker | external_skills_dirs (repo clone) | 2026-06-28 |
| `infrastructure/hermes-skills/kilo-code/SKILL.md` | Integracion Kilo CLI: umbral 50 lineas, contexto, recall/retain | external_skills_dirs (repo clone) | 2026-06-28 |
| `.agents/templates/profile-soul.md` | Template SOUL.md para perfiles worker. Placeholders: PROFILE_NAME, DOMAIN, TYPE, BANK_ID, etc. | Repo (referenciado por onboarding) | 2026-06-28 |
| `infrastructure/kilo.jsonc` | Configuracion de Kilo CLI: providers, MCP, permissions, agent.build.prompt | deploy.sh (genera + transfiere) | 2026-06-30 |
| `infrastructure/kilo-system-prompt.md` | **Source of truth** para system prompt de Kilo CLI. Inyectado en kilo.jsonc agent.build.prompt | deploy.sh (via generate-kilo-config.py) | 2026-06-30 |
| `infrastructure/kilo-prompt.md` | **[ELIMINADO 2026-07-05]** Legacy system prompt. Reemplazado por kilo-system-prompt.md | No aplica (eliminado) | 2026-07-05 (eliminado) |
| `scripts/generate-kilo-config.py` | Genera kilo.jsonc desde kilo-system-prompt.md. Ejecutado por deploy.sh | Repo (ejecutado por deploy.sh en CI/CD runner) | 2026-06-30 |
| `infrastructure/preflight.sh` | Verificacion post-deploy de invariantes MASTER-SPEC (15+ checks) | deploy.sh (copia) | 2026-06-30 |
| `docs/MASTER-SPEC.md` | Especificacion fundacional del proyecto | No aplica (documentacion) | 2026-06-28 |
| `docs/Hermes-integration.md` | Plan de integracion Hermes. Puede estar desactualizado tras iteraciones | No aplica (documentacion) | 2026-06-23 |
| `infrastructure/kb-mcp/README.md` | **Documento canónico del estado del servicio kb-mcp** (qué es, búsqueda híbrida, herramientas, despliegue, trampa del modelo ARM, sinergia con la estructura de la KB, auth pendiente). Leer este primero. | Repo (documentación) | 2026-07-23 |
| `infrastructure/kb-mcp/server.py` | Servidor MCP de solo lectura sobre KBs de kb-template: híbrido léxico+semántico+grafo+índices, recencia git. Sin escritura, sin estado | Imagen construida en VPS (docker compose build kb-mcp) | 2026-07-23 |
| `infrastructure/kb-mcp/Dockerfile` | Imagen de kb-mcp: python:3.12-slim, usuario no-root, ARM64 | docker compose build (en VPS) | 2026-07-23 |
| `infrastructure/kb-mcp/sync-kb.sh` | git pull de la KB + reindexado. Reinicia SOLO kb-mcp y solo si cambio el HEAD | deploy.sh (paso kb-mcp) + cron (*/15 min) | 2026-07-23 |
| `infrastructure/Caddyfile` | **Enrutado HTTP unico del VPS** (`:8080`, detras del Funnel): dashboard y API de Hindsight, Infisical, `/kb/*` (kb-mcp con direcciones-capacidad), `/okos-mapa/*` (prototipo estatico del mapa OKOS, publico) y la landing como catch-all. Corre con `admin off`: **no admite reload en caliente**, se aplica reiniciando el contenedor | deploy.sh (`tee` + validacion en el contenedor + `docker restart caddy` solo si cambio) | 2026-08-08 |

---

## Sync Mechanisms

| Mechanism | Files Affected |
|---|---|
| **deploy.sh** (CI/CD) | SOUL.md, context.md, config.yaml, whatsapp-groups.yaml, scripts/, memories/ |
| **external_skills_dirs** | skills en infrastructure/hermes-skills/ (cargados desde /opt/toolset-repo) |
| **Cron (populate-channel-aliases)** | channel_aliases.json (cada 10 min) |
| **Cron (hermes-sync-files)** | backup de ~/.hermes/ config al repo (diario) |
| **Cron (hermes-sync-banks)** | exportacion de banks Hindsight al repo (diario) |

---

## Update Procedure

Cuando se modifica un archivo de configuracion:

1. **Editar en repo** (nunca editar solo en VPS).
2. **Actualizar esta fila** en el MANIFEST (cambiar Last Updated a la fecha de hoy).
3. **Si es SOUL.md, config.yaml, o .env**: commit + push -> deploy.sh lo sincroniza.
4. **Si es una skill en infrastructure/hermes-skills/**: commit + push -> external_skills_dirs refresca en proxima sesion.
5. **Si es un script en infrastructure/hermes/scripts/**: commit + push -> deploy.sh lo copia.
6. **Si es una plantilla .agents/templates/**: commit + push -> referenciado por onboarding.
7. **Ejecutar DOC-01** (`/document` workflow + `reflect` + `retain`).

---

## Current Session Changes (2026-08-10)

**`/okos-mapa/`: el index.html publicado pasa de la maqueta v5 a la Torre v9 con datos reales.**
Solo cambio el ARCHIVO servido: ni Caddyfile ni Funnel se tocaron. La v9 embebe el contrato
vivo del mapa (292 piezas · 222 cintas · 4 dias de historia) y se regenera desde el repo
`okos-mapa` con `prototype/generar_digest.py` + `prototype/ensamblar_v9.py`. Respaldo del
anterior en `/opt/toolset/landing/okos-mapa/index.html.bak.1786393122`. Verificado desde
fuera: 200 con tamano exacto (876962), 404 en ruta inexistente, `/health` sin regresion,
navegador real sin errores de consola. **Exposicion nueva**: a diferencia de la v5 (maqueta
sin datos), la v9 lleva nombres de espacios de clientes, cuotas por plan y evidencia de
sondas; sigue sin `basic_auth` por decision del usuario.

---

## Current Session Changes (2026-08-08)

**Caddy: `/okos-mapa/` sirve el prototipo visual del mapa OKOS, estatico y publico.**
`infrastructure/Caddyfile` — **UPDATED**: bloque `handle /okos-mapa*` con `root
/usr/share/caddy/landing` + `file_server`, colocado antes del catch-all de la landing.
Sin `try_files`: aqui no hay SPA que enrutar, y un 404 debe ser un 404 y no la landing
con HTTP 200 (el mismo defecto que ya obligo al bloque `/.well-known/*`). Los archivos
—`index.html` mas `support.js` e `image-slot.js`— viven en `/opt/toolset/landing/okos-mapa/`
del VPS; no van en git porque el fuente es el repo `okos-mapa`, no este.

Queda publico via el Funnel que ya estaba encendido en el 443: **no se toco la
configuracion de Funnel**, asi que no hay superficie nueva expuesta mas alla de esa ruta.
URL: `https://toolset-oci-1-1.tail2d4c18.ts.net/okos-mapa/`. Es una maqueta sin datos en
vivo, para validar la forma del artefacto; sus rotulos igual se leen como estado real de
la plataforma, y hoy no lleva `basic_auth` (decision del usuario).

Aplicado con `docker restart caddy`, no con `caddy reload`: el Caddyfile declara `admin
off`, asi que el endpoint de recarga no existe y `reload` falla con `connection refused`
al 2019 — es la misma via que usa `deploy.sh`. Backup del anterior en el VPS
(`/opt/toolset/Caddyfile.bak.<epoch>`). Verificado desde fuera de la tailnet: DNS publico
→ ingress de Funnel, 200 y tamano exacto del archivo; navegador real contra la IP publica
renderiza sin errores de consola; y sin regresiones en `/`, `/dashboard`, `/health`,
con `/okos-mapa/no-existe.js` → 404.

---

## Session Changes (2026-07-26)

**kb-mcp: niveles de acceso por KB + retiro + frescura (server.py).** Tres capacidades nuevas,
todas opt-in por KB via su `kb/mcp.yaml` (una KB que no declara nada se sirve EXACTAMENTE igual
que antes — verificado con `personal`): (1) `niveles`: la misma KB montada mas de una vez, cada
nivel con un indice acotado por un campo del frontmatter y una lista de herramientas registradas
(lo no registrado no existe para ese cliente); (2) `retirado: true` en una entrada la saca de
TODOS los indices (git conserva); (3) `retencion` + `verificado`: el servidor rotula al servir
las entradas vencidas o sin sello ("tratar como no confirmada") — comparacion de fechas pura.
Hoy solo `okos` declara nivel (`publicado`) y calendario. Copias espejo sincronizadas
(kb-template, ~/kb-mcp). Validado en local contra las 3 KB antes de subir: 20/20 casos de uso de
dos puntos de vista, 0 fugas entre niveles.

**Caddy: direcciones-capacidad para okos (UD-004/D5 de kb-okos).** `/kb/okos/*` y
`/kb/okos-publicado/*` responden 404 hacia afuera; el acceso es via
`/kb/{$KB_TOKEN_COMPLETO}/okos/mcp` (total) y `/kb/{$KB_TOKEN_PUBLICADO}/okos-publicado/mcp`
(solo nivel publicado — el matcher incluye el slug para que este secreto NO alcance la vista
completa). 404 y no 401 a proposito: un 401 dispara el descubrimiento OAuth contra
`/.well-known/*` (que responde 404) y el cliente MCP falla confuso. Secretos en el `.env` del
VPS via passthrough del compose (`KB_TOKEN_COMPLETO`, `KB_TOKEN_PUBLICADO`), jamas en git; sin
valor la ruta falla CERRADA (validado con env vacios). `personal` y `traza-ambiental` siguen
abiertas sin cambio (decision del usuario pendiente).

**kb-mcp: tercera KB publicada — `okos`.** Una línea nueva en el bloque `KB_MANIFIESTO` de
`infrastructure/deploy.sh`: `okos master https://github.com/kirlts/kb-okos.git` (repo privado;
el clone funciona porque el VPS autentica via `gh auth git-credential`, igual que `personal` y
`traza-ambiental`, ambos también privados). Sin cambios en `server.py`, el compose, el Dockerfile
ni `sync-kb.sh` — el servidor descubre toda KB bajo `/opt/kb` solo. La KB queda en
`/kb/okos/mcp`. Contenido: trabajo de Martín en conversio-connect/OKOS (ontología
`comprobado`/`en-curso`, 20 entradas seed de la Semana 1, validadas con 26 casos de uso
objetivos al 100% contra el mismo `server.py` en local antes de publicar).

**fix(deploy): `ssh -n` en el loop de KB_MANIFIESTO.** Bug preexistente descubierto al agregar
la tercera KB: dentro del `while read`, el `ssh` sin `-n` consumía las líneas restantes del
manifiesto — solo la PRIMERA KB se procesaba y el resto moría en silencio (el log del run
30143520596 solo dice "traza-ambiental ya clonada"; `personal` nunca se re-verificaba y `okos`
nunca se clonó). Reproducido en local (`cat` dentro del loop se traga el stdin) y corregido con
`ssh -n`. Con 2 KBs ya clonadas el bug era invisible; con una KB nueva era bloqueante.

---

## Session Changes (2026-07-23)

**RETIRADO el 2026-07-24 por decision del usuario.** El recurso `encuadre` y todo el
codigo de perfiles se quitaron de `server.py`, el compose y el Dockerfile; el volumen
`/opt/kb-perfiles` se desmonto y borro del VPS. El servidor kb-mcp vuelve a servir solo
las dos KB (`personal`, `traza-ambiental`), como antes de esta sesion. Motivo: el perfil
pierde precision a medida que el usuario acumula datos propios sobre las personas que
modela, y sin un ciclo de re-verificacion no tiene forma de saber que envejecio. Se
conservan de esta sesion los arreglos de infraestructura que NO son de encuadre:
`mem_limit` 2000m (OOM en cada consulta), el invariante de skills del preflight, y el
rename del contenedor hindsight. El resto de esta entrada queda como registro historico.

**kb-mcp: recurso nuevo `encuadre`, perfiles de decision servidos por MCP.** Un perfil
dice como decide una persona del entorno de trabajo, que necesita ver para aceptar algo y
que hunde un mensaje, en dos direcciones: entrante (interpretar lo que dijo o hizo) y
saliente (encuadrar lo que se le va a pedir, proponer o reportar). Una sola herramienta,
`encuadrar(situacion, destino?, direccion?, tipo?)`, que devuelve `str`.

**No es una KB, y esa fue la decision de diseño que mas costo.** El primer bosquejo lo
modelaba como una base de conocimiento con repo propio, polos y nodos, por inercia de que
este servidor sirve KBs. Se descarto: la recuperacion es determinista (la seccion de la
direccion saliente, tipo X, del destino Y), asi que un indice no aporta y agrega una capa
que puede fallar; fragmentar el perfil en nodos complica lo unico que hay que hacer, que
es devolver secciones enteras; y el ciclo de edicion se volvia commit + push + esperar el
cron de 15 min, sobre un archivo que se va a editar seguido. Es lectura de archivo y
corte por encabezado, ~180 lineas sin dependencias nuevas. **Regla que queda:** si una
decision agrega infraestructura (un repo, un indice, un esquema) para servir un archivo de
texto que se lee por secciones, es la decision equivocada.

Se monta como recurso aparte en `/kb/encuadre/mcp`, NO como cuarta herramienta de cada KB:
colgando de "Trazambiental" heredaria su cabecera de dominio y el agente no sabria cuando
usarla, y una ruta propia es donde podra aplicarse la autorizacion pendiente [DT-011].
Datos en `/opt/kb-perfiles` montado `:ro` (no `/opt/kb-datos`, que queda reservado para
cuando haya algo que escribir). Los perfiles se releen en cada llamada, asi que editarlos
no exige reiniciar el contenedor. El recurso es opcional: sin volumen montado el servidor
arranca igual y no lo monta, que es lo que permite que el CMD pase `--perfiles` siempre.

Se probo por el protocolo real (stdio: initialize, tools/list, tools/call) mas los tres
casos de la prueba de aceptacion y ocho caminos de degradacion. Sin regresion: una KB real
(traza-ambiental, 175 nodos) sigue exponiendo sus tres herramientas y solo esas.

**Se descarto deducir el tipo de situacion de las palabras del usuario.** Sin un corpus
que pese los terminos, las palabras vacias mandan: "quiero que pague una cuenta de IA"
deducia `trabajo_invisible` en vez de `pedir_recurso`, por compartir "quiere" con su
descripcion. Ahora, ante un tipo ausente, devuelve el catalogo con la linea de cuando
aplica cada uno. Entregar los criterios de aceptacion de la situacion equivocada es peor
que pedir una llamada mas, porque el que llama los aplica creyendo que son los correctos.

**Pendiente que hay que decidir, no olvidar:** `encuadre` modela a personas reales y el
endpoint sigue sin auth, asi que cualquiera con la URL lo lee y `/kb/salud` enumera los
slugs. Se desplego con esa consecuencia asumida a sabiendas. Es el primer candidato a
quedar detras de la capa de tokens [DT-011].

**El conector de claude.ai no podia registrarse (Caddyfile).** El catch-all
(`try_files {path} index.html`) respondia la landing con HTTP 200 en las rutas de
descubrimiento OAuth; un cliente MCP lo lee como "este recurso exige OAuth", arranca el
flujo de login y falla —aunque el endpoint MCP responda 200 sin token. Se agregaron dos
bloques `handle` que devuelven 404 en `/.well-known/oauth-*` y
`/.well-known/openid-configuration*`, que es la respuesta correcta para un servidor sin
auth. Verificado: handshake completo sin token, `tools/list` con las tres herramientas,
consulta real por el conector. Baseline intacto (/health, /dashboard, /hermes/,
/openapi.json, /kb/salud, landing).

**deploy.sh: el Caddyfile se transferia y no se aplicaba, en silencio.** Dos defectos
encadenados: (a) `mv -f` rompe el inode del bind mount de archivo, asi que el contenedor
seguia viendo el archivo viejo; (b) nada recargaba Caddy, que corre con `admin off` y no
admite reload en caliente. Ahora se escribe con `tee`, se compara con `cmp` para saber si
cambio, se valida `caddy validate` DENTRO del contenedor y solo entonces se reinicia. Si
la config no adapta no se toca nada y el deploy avisa; si el restart falla, `|| true` por
[DT-010]. **Cualquier cambio futuro de rutas dependia de esto.**

**deploy.sh: credenciales git para las KB privadas.** Las KB son repos privados y git no
trae credenciales solo: el clon inicial y el cron `sync-kb.sh` fallaban con "could not
read Username" —el fetch aborta y la KB queda congelada en la version del dia del clon,
sin error visible. Se agrego `gh auth setup-git` (idempotente) antes de clonar.

**kb-mcp: la KB se describe sola al agente.** `server.py` publica el dominio de cada KB en
las `instructions` del servidor y en la cabecera de las tres herramientas, con la forma
que indica la guia de Anthropic para escribir herramientas de agentes (que hace, cuando
usarla, cuando NO, que NO devuelve). El texto combina lo que la KB declara en su
`kb/mcp.yaml` —campo `descripcion`, que existia y no se usaba— con los conceptos
centrales deducidos de los nodos mas referenciados del grafo, que no envejecen. Basta la
URL: el agente ya no depende del nombre que le ponga al conector quien lo instala.
Corregido de paso el listado de ambitos, que omitia todo polo cuyo alias coincidiera con
el nombre de su carpeta (en traza solo aparecia 'producto', nunca 'contexto').

**Divergencia documental detectada (no introducida en esta sesion).** [DEV.CR.18]
afirmaba `/dashboard → 401` por `basicauth`; el basicauth fue removido en `1de879b` y
`db17f50` sin actualizar la verificacion ni [DT-002]. Medicion real: `/dashboard` → 200,
`/api/banks` → 200 desde internet. Ademas `docker-compose.yml` sigue pasando
`FUNNEL_AUTH_USER`/`FUNNEL_AUTH_PASSWORD` a Caddy, variables que ninguna directiva
consume. [DT-002] reabierto; decision del usuario.

#
**Ajuste de ranking (revalidacion con jueces).** Tras revalidar con casos duros se
subio la calidad de recuperacion con mejoras del buscador: embeddings a 256 dims,
difusion por el grafo de wikilinks (vecinos de los top-resultados, excluyendo hubs),
senal de nombre por palabras compartidas, recencia como multiplicador con decaimiento
exponencial (practica 2026, no hard-sort), ambito invalido que degrada a busqueda
global, y leer() que no entrega homonimos por match debil. Modelo 256d en
/opt/kb-modelo-256 (mem_limit 1200m). Evaluador con gold: traza 9/9, personal 7/9 top-3.

**Techo identificado (NO es del buscador):** los casos que no suben requieren cambios
de CONTENIDO en las KB —faltan nodos-indice/glosario (definicion de NFU, indice de
proyectos), un changelog para "que es lo ultimo", y un mapa de siglas de dominio
(REP=Responsabilidad Extendida del Productor)— no mas ranking. Palanca futura barata:
un campo `sinonimos` en kb/mcp.yaml que expanda la consulta, declarativo por KB.

**pull_policy: build en kb-mcp (CRITICO).** kb-mcp es el unico servicio con build: y
sin imagen en registry; sin pull_policy el paso `docker compose pull` del pipeline
devuelve exit 1 y —por set -euo pipefail— aborta el deploy COMPLETO de Hermes.
Verificado. El dry-run de `up -d --remove-orphans` no recrea otros servicios.

---

## Session 10 (continuacion)

### Session 10 — kb-mcp evoluciona a multi-KB con busqueda hibrida

Sobre la base de la Session 9. Sin tocar Hermes en ningun momento (verificado tras cada
paso: /health, /dashboard, /hermes/, el MCP de Hindsight y `hermes -z` responden).

**Cambios funcionales:**
- **Multi-KB en un proceso.** Un solo modelo de embeddings cargado, N indices. Cada KB
  se sirve en `/kb/<slug>/mcp` (slug = nombre del repo); NO hay KB por defecto en la
  raiz. Sirviendo hoy: `traza-ambiental` (173) y `personal` (128). Segunda KB cuesta ~45 MB.
- **Rutas por nombre de repo**, predecibles. La autorizacion por-KB es una capa de tokens
  futura sobre `/kb/<slug>`; no se mezcla con el enrutamiento.
- **Busqueda hibrida:** lexica (FTS5/BM25 + raiz Snowball espanola: `residuo`->`residuos`;
  palabras vacias por frecuencia documental del corpus, no lista fija) + semantica
  (model2vec, embeddings estaticos sin torch: encuentra por sentido) + senal por nombre,
  fusionadas con RRF. Revalidado con jueces: 2.09/3 (traza) y 2.5/3 (personal) en casos duros.
- **Temporalidad desde git.** Cada nodo lleva su fecha de ultima modificacion; `consultar(
  orden="reciente")` ordena por ella. Requiere historial -> el clon paso de `--depth 1` a
  `--filter=blob:none` (historial completo de commits, 8 MB en vez de 154, sin binarios).
- **Descripciones de herramientas** al estandar Anthropic (writing-tools-for-agents).
- **Seguridad:** `leer` ya no entrega un homonimo por match debil de raiz; ofrece candidatos.

| File | Change |
|---|---|
| `infrastructure/kb-mcp/server.py` | **REESCRITO** — multi-KB, config por `kb/mcp.yaml`, busqueda hibrida, temporalidad git, tres herramientas (consultar/leer/panorama) |
| `infrastructure/kb-mcp/Dockerfile` | **UPDATED** — uvicorn+starlette (montaje multi-KB), CMD `--kbs $KB_ROOT`, versiones de tokenizers/numpy/model2vec fijas |
| `infrastructure/kb-mcp/sync-kb.sh` | **REESCRITO** — recorre todas las KB en /opt/kb, fetch sin --depth (preserva historial) |
| `infrastructure/docker-compose.yml` | **UPDATED** — monta /opt/kb completo (no una KB), KB_ROOT, mem_limit 1g |
| `infrastructure/Caddyfile` | **UPDATED** — `handle_path /kb/*` -> kb-mcp:8765 (rutas /kb/<repo>/mcp) |
| `infrastructure/deploy.sh` | **UPDATED** — manifiesto KB (clon blob:none por repo+rama), agregar KB = una linea |

**Estado:** ~815 MB RAM (mem_limit 1g), host con ~4 GB libres. Respaldos
`/opt/toolset/{Caddyfile,docker-compose.yml}.bak.20260723-133952`.

**Portado a kb-template** (para instanciar KB nuevas sin friccion): `tools/kb-mcp/`
(server + Dockerfile), `kb/mcp.yaml` (config declarativa de ejemplo), `docs/PUBLISH-AS-MCP.md`.

---

## Previous Session Changes (2026-07-23)

### Session 9 — kb-mcp: la KB de Trazambiental expuesta por MCP

Servicio nuevo y aislado. **No toca Hermes**: sin `depends_on`, sin puertos publicados al
host, sin escritura sobre la KB, y el bloque de `deploy.sh` es no-fatal de punta a punta
(`|| true`) para que un fallo suyo jamas aborte un deploy.

| File | Change |
|---|---|
| `infrastructure/kb-mcp/server.py` | **CREATED** — MCP de solo lectura. FTS5/BM25 con tokenizer `unicode61 remove_diacritics 2` (sin `porter`, que es solo ingles y degrada el espanol) + navegacion del grafo de wikilinks. Sin RAG vectorial |
| `infrastructure/kb-mcp/Dockerfile` | **CREATED** — `python:3.12-slim`, usuario no-root (uid 10001), construido en el VPS para ARM64 |
| `infrastructure/kb-mcp/sync-kb.sh` | **CREATED** — clon superficial + reindexado; reinicia solo `kb-mcp` y solo si el HEAD cambio |
| `infrastructure/docker-compose.yml` | **UPDATED** — servicio `kb-mcp` (`read_only`, `no-new-privileges`, `mem_limit: 512m`, bind `:ro`, sin `depends_on`) |
| `infrastructure/Caddyfile` | **UPDATED** — ruta `handle_path /kb-<sufijo>/*` → `kb-mcp:8765` con `flush_interval -1`. Sufijo no adivinable: la exposicion es publica via Funnel y el connector de claude.ai no soporta headers de auth fuera de su beta cerrada |
| `infrastructure/deploy.sh` | **UPDATED** — bloque `kb-mcp KB sync` (clon atomico + script + cron), todo no-fatal |
| `infrastructure/hermes/INFRASTRUCTURE-MANIFEST.md` | **UPDATED** — current session changes |

**Búsqueda:** híbrida. Capa léxica (FTS5/BM25 + expansión por raíz Snowball española:
`residuo` encuentra `residuos`) fusionada con capa semántica (embeddings estáticos
model2vec, sin torch: `castigos por no cumplir` llega a Sanciones y Multas). Tercera señal
por nombre de entrada. Herramientas: `consultar`, `leer`, `panorama` — sin jerga interna.

**⚠ El modelo NO se hornea en el build.** Cuantizarlo durante `docker build` en ARM64
produce pesos distintos a los validados (mismo código y origen, otro `model.safetensors`,
md5 `228fe3f1…` vs `28357215…`). No falla: devuelve resultados semánticos incorrectos en
silencio. El artefacto validado vive en `/opt/kb-modelo` (int8/128, 79 MB) y se monta `:ro`.
Para regenerarlo: `StaticModel.from_pretrained('minishlab/potion-multilingual-128M',
quantize_to='int8', dimensionality=128).save_pretrained(dir)` en x86_64, y copiarlo. Las
versiones de `tokenizers`, `numpy` y `model2vec` van fijas en el Dockerfile por la misma
razón: sin fijar, cambian los vectores.

**Estado en el VPS:** `/opt/kb/traza-ambiental`, rama `planning` (**`master` no contiene
la KB**: 0 archivos), 173 nodos, ~815 MB de RAM (mem_limit 1g; el grueso es el tokenizador multilingüe de 500.353 tokens). Sin la capa semántica serían ~60 MB. Aplicado quirurgicamente con
`docker compose up -d --no-deps kb-mcp` + `restart caddy`; nunca `up -d` global ni
`--remove-orphans` (borraria el stack `traza`, que vive en otro proyecto compose).
Respaldos: `/opt/toolset/{Caddyfile,docker-compose.yml}.bak.20260723-114217`.

**Deliberadamente NO hecho:** la ruta no se publica en la landing page, porque `deploy.sh`
la genera y es publica. Si se quiere auth real, el servidor ya lee `KB_ALLOWED_HOSTS` y
Caddy puede validar un Bearer desde Infisical.

---

## Previous Session Changes (2026-07-19)

### Session 8 — Credential Pool Fallback + WhatsApp Notification

| File | Change |
|---|---|
| `infrastructure/hermes/config.yaml` | **UPDATED** — `credential_pool_strategies` set to `opencode-go: fill_first` for rate-limit fallback |
| `infrastructure/deploy.sh` | **UPDATED** — added `OPENCODE_GO_API_KEY_FALLBACK` to required vars, Hermes .env, and credential pool setup block |
| `.github/workflows/deploy.yml` | **UPDATED** — added `OPENCODE_GO_API_KEY_FALLBACK` secret to Deploy and Sync secrets steps |
| `scripts/sync-infisical-secrets.py` | **UPDATED** — added `OPENCODE_GO_API_KEY_FALLBACK` to dev and prod scoped secrets |
| `infrastructure/hermes/scripts/monitor-credential-rotation.sh` | **CREATED** — monitors auth.json for pool rotation events and notifies via WhatsApp al grupo Toolset |
| `infrastructure/hermes/INFRASTRUCTURE-MANIFEST.md` | **UPDATED** — current session changes |

### Session 6 — Kilo CLI System Prompt Architecture

| File | Change |
|---|---|
| `infrastructure/kilo-system-prompt.md` | **CREATED** as single source of truth for Kilo CLI system prompt (30 lines, clean minimal). |
| `scripts/generate-kilo-config.py` | **CREATED** — reads kilo-system-prompt.md, injects into kilo.jsonc `agent.build.prompt` field. |
| `infrastructure/kilo.jsonc` | **UPDATED** — removed `kilo-prompt.md` from `instructions` array. System prompt now exclusively via `agent.build.prompt` (auto-generated). Escape sequences fixed for valid JSON. |
| `infrastructure/kilo-prompt.md` | **DEPRECATED** — replaced by kilo-system-prompt.md. No longer referenced in kilo.jsonc `instructions`. |
| `infrastructure/deploy.sh` | **UPDATED** — added kilo.jsonc regeneration from kilo-system-prompt.md (via generate-kilo-config.py) if source changed. Transfers kilo.jsonc to VPS for Kilo CLI config. Hindsight backup tar uses `--warning=no-file-changed` to prevent abort on hot backup. |
| `infrastructure/preflight.sh` | **UPDATED** — bank check uses list endpoint with grep -q profile name (not JSON parsing). Docker healthcheck filter only for compose services. Hindsight API check via localhost:8888 (not Funnel). WebUI check via Caddy proxy (port 8787 redirect). |
| `.github/workflows/deploy.yml` | **UPDATED** — preflight runs via single SSH on VPS (not local runner). SSH mux timeout increased for reliability. |

### Session 5 — Patch-bridge fix + Governance enforcement

| File | Change |
|---|---|
| infrastructure/hermes/scripts/patch-bridge.sh | **CREATED** at repo path. Fixed line 147 JS string syntax (`\\n" +` → `\\n' +\\n" +`). Previously only existed on VPS (`~/.hermes/patch-bridge.sh` — now backed up to `.bak`). |
| infrastructure/hermes/scripts/populate-channel-aliases.sh | **UPDATED** with YAML fallback: si bridge desc vacia, usa descripcion desde whatsapp-groups.yaml. |
| infrastructure/hermes/profiles/toolset/SOUL.md | **UPDATED** with enforcement rules: no direct git commits, no write_file/patch on repos, Kilo CLI mandatory, Kanban delegation for multi-step. |
| infrastructure/hermes/profiles/personal/SOUL.md | **UPDATED** with explicit "Sin Kanban" section. |
| infrastructure/preflight.sh | **REWRITTEN** parameterized: auto-discovers profiles from whatsapp-groups.yaml, discovers Docker services from compose, adds Kilo CLI MCP E2E, bridge.js injection verification, git state check, Kanban config check, WebUI check. |
| docs/RULES.md | **ADDED** GIT-03 rule prohibiting direct Hermes commits to toolset repo. |
| docs/MASTER-SPEC.md | **UPDATED** §7.1 MCP Lifecycle with preflight + bridge.js verification. |

### Session 4 — Bridge Injection + Identity Routing

| File | Change |
|---|---|
| infrastructure/hermes/SOUL.md | **REWRITTEN routing section.** Replaced fragile Spanish routing algorithm with RULE 0 in English: `[ROUTING]` block injects identity deterministically. Cross-profile delegation uses Kanban for out-of-scope tasks. Memory cycle scoped to active profile. |
| infrastructure/hermes/scripts/patch-bridge.sh | **EXTENDED with Patch 2.** Reads profile SOUL.md from `~/.hermes/profiles/<name>/SOUL.md` and injects FULL CONTENT as `=== PROFILE ACTIVATION: <name> ===` block. The LLM receives the complete profile identity with every message. |
| infrastructure/hermes/whatsapp-groups.yaml | **ADDED `scope:` field** to Personal (knowledge_base) and Toolset (infrastructure). |
| .agents/templates/profile-soul.md | **UPDATED ROUTE-03:** profile operates directly (no orchestrator reporting). **UPDATED ROUTE-03a:** mandatory cross-profile delegation for out-of-scope tasks. |
| infrastructure/hermes-skills/group-onboarding/SKILL.md | **UPDATED Step 2 & 3**: new template alignment, `scope:` in YAML, no `banks:` needed. |
| docs/MASTER-SPEC.md | UPDATED §7.1: routing architecture replaced with bridge injection + [ROUTING] identity. |
| docs/RULES.md | UPDATED ROUTE-01/02/03: bridge injection, identity routing, scope isolation. |
| infrastructure/hermes/INFRASTRUCTURE-MANIFEST.md | UPDATED: current session changes. |
| infrastructure/hermes/cloned-repos.yaml | **FIXED key rename**: `toolset-repo` → `toolset` (prevents auto-discovery false positive). **FIXED sync**: `cron` → `ci_cd` (handled by deploy.sh, not clone_repos). |
| infrastructure/deploy.sh | **ADDED** `cloned-repos.yaml` sync to `~/.hermes/` on every deploy. **FIXED** comment reference to match renamed key. |

### Session 3 — /document fixes

| File | Change |
|---|---|
| docs/CHANGELOG.md | FIXED: merged duplicate [0.4.0] sections, removed duplicate [Unreleased] with released content. |
| docs/REPOMAP.md | FIXED: generation date 2026-06-26 → 2026-06-29. |
| docs/VERIFICATION.md | FIXED: [DEV.CR.12.LLM] marked ✅ (DT-001 closed, OIDC deprecated). |
| docs/TODO.md | FIXED: coverage summary EPIC-004 corrected 4🤖4🧑8 → 3🤖1🧑4, total 25→24. |
| infrastructure/hermes/INFRASTRUCTURE-MANIFEST.md | FIXED: stray `||` on lines 85-88. UPDATED: session 3 changes. |

### Session 2 — Toolset & Personal Onboarding

| File | Change |
|---|---|
| infrastructure/hermes/SOUL.md | UPDATED: eliminada excepción hardcodeada de personal por regla universal de delegación según tarea. |
| infrastructure/hermes/whatsapp-groups.yaml | UPDATED: agregado grupo Toolset (JID 120363426816726918@g.us) con profile toolset, repo kirlts/toolset. |
| infrastructure/hermes-skills/group-onboarding/SKILL.md | UPDATED v4.2.0: added delegation criteria inference en Phase 0 y pregunta en Phase 3. |
| infrastructure/hermes/scripts/discover-new-repos.sh | UPDATED: cutoff por fecha absoluta (2026-06-28), no relativa. |
| infrastructure/hermes/cloned-repos.yaml | RESTORED: solo toolset, researchit, hermes-webui, personal. Repos viejos removidos. |
| infrastructure/hermes/CRONS.md | UPDATED: agregado cron discover-new-repos con documentación. |
| infrastructure/hermes/INFRASTRUCTURE-MANIFEST.md | UPDATED: registrados cambios de Session 3. |

### Session 1 — Onboarding Infrastructure

| File | Change |
|---|---|
| infrastructure/hermes/SOUL.md | REFACTORED: 254 -> 84 lineas. Routing sin tipos predefinidos — solo verifica si hay profile. |
| infrastructure/hermes-context.md | REFACTORED: referencia operativa completa. Workers Profile Inventory. Banks actualizados. |
| infrastructure/hermes/whatsapp-groups.yaml | LIMPIADO: sin type, sin profiles. Solo JID + name. Onboarding define todo. |
| infrastructure/deploy.sh | REMOVIDO: creacion de workers profiles. FIX: bridge patch independiente del populate. |
| infrastructure/hermes-skills/group-onboarding/SKILL.md | v4: sin tipos predefinidos. Mismas preguntas para todos los grupos. Sin defaults por categoria. |
| infrastructure/hermes-skills/whatsapp-router/SKILL.md | v4: sin tabla de tipos. Solo verifica profile field. |
| infrastructure/hermes-skills/group-onboarding/SKILL.md | v3: 3-phase MECE, DM handler, evolution preferences, dynamic description |
| .agents/templates/profile-soul.md | NEW: profile SOUL.md with placeholders, evolution + desc rules |
| docs/MASTER-SPEC.md | Updated 7.1 with multi-group routing, deterministic routing, onboarding |
| .github/workflows/deploy.yml | Removed **.md from paths-ignore (blocked SOUL.md + SKILL.md deploys) |
| infrastructure/deploy.sh | Added bridge patch, worker profiles, cron setup, whatsapp-groups.yaml deploy |
| infrastructure/deploy.sh | ADDED: GROQ_API_KEY to .env, ffmpeg static binary install for audio STT |
| infrastructure/hermes/config.yaml | CHANGED: stt.provider to groq, groq.model to whisper-large-v3-turbo |
| .github/workflows/deploy.yml | ADDED: GROQ_API_KEY secret to Deploy and Sync secrets steps |
| infrastructure/kilo.jsonc | ADDED: timeout 120000ms for hindsight-selfhosted MCP server |
| infrastructure/hermes/config.yaml | ADDED: timeout 120s for hindsight-selfhosted MCP server |
| infrastructure/hermes-skills/kilo-code/SKILL.md | REWRITTEN v2.0.0: governance-based delegation over line thresholds |
| infrastructure/hermes-skills/group-onboarding/SKILL.md | REWRITTEN v4.1.0: added Phase 0 Context Ingestion |
| .agents/templates/profile-soul.md | CHANGED: ROUTE-04 universal Kilo CLI (no line threshold) |
| infrastructure/hermes/cloned-repos.yaml | CREATED: manifest for repo cloning (native tools + cloned repos) |
| infrastructure/deploy.sh | REPLACED ad-hoc ResearchIt clone with clone_repos() reading cloned-repos.yaml |
| infrastructure/hermes/scripts/repo-pull-cron.sh | CREATED: silent git pull cron (5min, only notifies on conflict, max 1x/day) |

### Session 7 — Context Engineering + Banco Consolidation (2026-07-05)

| File | Change |
|---|---|
| `.github/workflows/deploy.yml` | **FIXED** line 58, 109, 226 restored from sed corruption. Pipeline CI/CD functional. |
| `infrastructure/kilo-prompt.md` | **DELETED** — conflicted with kilo-system-prompt.md, line 30-31 self-contradiction. |
| `infrastructure/kilo-system-prompt.md` | **REFACTORED** — reduced from 39 to 26 lines. Removed governance duplication. Added explicit recall params: `max_tokens=1024, budget="low"` with `query`. Added anti-recency-bias section. |
| `infrastructure/kilo.jsonc` | **REGENERATED** — model deepseek-v4-pro, reasoning=true, qwen3.7-plus fallback, workflow discovery. |
| `infrastructure/hermes/SOUL.md` | **FIXED** recall: `max_tokens` 16384→4096, `budget` high→mid. Added `query`. `bank=` → `bank_id=`. |
| `infrastructure/hermes/profiles/toolset/SOUL.md` | **ADDED** Memory Cycle. Bank `toolset`→`toolset-profile`. |
| `infrastructure/hermes/profiles/personal/SOUL.md` | **FIXED** recall budget. `bank=` → `bank_id=`. |
| `infrastructure/hermes/profiles/chat/SOUL.md` | **FIXED** recall budget. `bank=` → `bank_id=`. |
| `infrastructure/hermes/profiles/wwe/SOUL.md` | **FIXED** recall: 16384/high → 4096/mid. Created in repo (was VPS-only). |
| `.agents/templates/profile-soul.md` | **FIXED** recall template: 16384/high → 4096/mid. |
| `docs/RULES.md` | **FIXED** bank naming: `<profile>-profile` sin excepciones. recall params agregados. |
| `docs/CHANGELOG.md` | **ADDED** v0.6.0 with all session changes. |
| `AGENTS.md` + `infrastructure/hermes-context.md` | **FIXED** bank naming, ROUTE-07, budget, recall params. |
| `infrastructure/deploy.sh` | **FIXED** landing page + SOUL.md path (hermes/SOUL.md no Hermes-SOUL.md). |
| `infrastructure/hermes-skills/toolset-ops/SKILL.md` | **FIXED** bank refs, budget, tabla actualizada. |
| `infrastructure/hermes-skills/kilo-code/SKILL.md` | **REWRITTEN** v1.3.0: arquitectura system prompt, anti-corrupción, recency-bias preamble. |
| `infrastructure/hermes-skills/whatsapp-router/SKILL.md` | **FIXED** budget params. |
| `infrastructure/hermes-skills/onboarding/SKILL.md` | **REWRITTEN** v5.0.0: Phase 4 TTS, retrocompatibilidad update vs re-onboard. |
| `infrastructure/hermes/skills/` (17 files) | **FIXED** bank naming, recall params, `bank`→`bank_id`, budget unificado. |
| `infrastructure/Hermes-SOUL.md` | **DELETED** (obsoleto en inglés, junio 28). |
| `infrastructure/kilo-recall-policy.md` | **CREATED** incident documentation. |
| `infrastructure/hermes/scripts/repo-pull-cron.sh` | **FIXED** ahora git pull ALL repos (ci_cd, deploy, cron). |
| `infrastructure/hermes/scripts/populate-channel-aliases.sh` | **EXTENDED** auto-cleanup orphaned WhatsApp groups. |
| `infrastructure/hermes/config.yaml` | **FIXED** TTS enabled (es-CL-LorenzoNeural), fallback_providers qwen3.7-plus, reasoning_full=true, reasoning_effort=xhigh. |
| `infrastructure/hermes/cloned-repos.yaml` | **UPDATED** schema (TTS field, metadata). |
| Hindsight bank `toolset` (741 facts) | **DELETED** — data was older system. `toolset-profile` (0 facts) es canónico fresco. |
| Server-side `recall_max_tokens` | **APPLIED** a 10 bancos Hindsight: 4096 max. |

---

## Second tenant on the VPS: user `kirlts` (Claude Code workloads) — 2026-08-18

The host gained a second, isolated user running Claude Code sessions and
knowledge-base workloads, subordinate to the operator's notebook by design:
its repos update by `git pull` from their real remotes, its Claude identity is
a fast-forward clone of a private personal config repo exported from the
notebook, and its secrets arrive inventoried through a sync script (systemd
user timer on the notebook, 30 min). Rule enforced by tooling: nothing
untracked-and-undeclared lives on the VPS; drift self-repairs (evidence diff
kept) and the persistent tmux session self-relaunches — refusing to run
without Remote Control. Control surface: the `vps` command on the notebook
(interactive TUI: sessions, services, sync health, account/model). The bridge
sources live in that private repo, not here; this row exists so this manifest
keeps being the single inventory of what runs on the host.

| File | Purpose | Sync to VPS | Last Updated |
|---|---|---|---|
| `infrastructure/vps-guardias/tailscaled-memoria.conf` | Memory ceiling + Restart=always for tailscaled (the host's only door) | manual install 2026-08-18 (CI paused); source of truth here | 2026-08-18 |
| `infrastructure/vps-guardias/reciclar-tailscaled.sh` | Daily conditional recycle of tailscaled (>600 MB only) | manual install → /usr/local/sbin | 2026-08-18 |
| `infrastructure/vps-guardias/censar-tailnet.sh` | Daily census of CI nodes in the tailnet (detects non-ephemeral auth key) | manual install → /usr/local/sbin | 2026-08-18 |
| `infrastructure/vps-guardias/reciclar-tailscaled.units` | systemd oneshot + daily 04:15 timer for both guards | manual install → /etc/systemd/system | 2026-08-18 |

**Host renamed 2026-08-18**: `toolset-vnic` → `vps-oracle`. The old name was
OCI's VNIC display name and surfaced as the device name in the Claude mobile
app. Verified safe before the change: no container uses the host's hostname,
Hermes only carried it in past logs and transcripts, and the Funnel and its
certificates use the Tailscale name (`toolset-oci-1-1.tail2d4c18.ts.net`),
which is independent. `/etc/hosts` keeps BOTH names — OCI's internal
resolution uses the long `.oraclevcn.com` form, and dropping it would leave
sudo waiting on resolution. Backup at `/etc/hosts.antes-de-vps-oracle`.

Context for the guards: tailscaled had grown to 2.2 GB RSS in 54 days while
the CI registered one permanent tailnet node per run (763 dead nodes, purged;
auth key reissued as ephemeral). Container memory limits applied live the
same day (hindsight 2g, infisical 1g) — pending in docker-compose.yml.
