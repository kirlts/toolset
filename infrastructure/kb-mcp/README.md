# kb-mcp — servidor MCP de solo lectura para KBs de kb-template

Documento canónico del estado del servicio. El historial de cambios vive en
`infrastructure/hermes/INFRASTRUCTURE-MANIFEST.md`; esto describe **qué es y cómo opera hoy**.

## Qué es

Un servidor MCP que expone una o varias bases de conocimiento (KBs construidas con
`kb-template`) como herramientas consultables por un agente (claude.ai, Claude Code,
Hermes). **Solo lectura**: no expone ninguna herramienta de escritura.

Un solo proceso sirve **todas** las KBs bajo `/opt/kb`, cargando el modelo de embeddings
una vez. Cada KB se expone en su propia ruta, por el nombre de su repositorio:

```
https://toolset-oci-1-1.tail2d4c18.ts.net/kb/<slug>/mcp
```

Sirviendo hoy: `traza-ambiental` (175 nodos) y `personal` (129 nodos).

## Las tres herramientas

| Herramienta | Qué hace |
|---|---|
| `consultar(pregunta, ambito?, orden?, limite?)` | Busca y devuelve pasajes con fuente, fecha de última modificación y entradas conectadas. `orden="reciente"` ordena por recencia. |
| `leer(tema)` | Texto íntegro de una entrada, por nombre aproximado. Ante match débil no entrega homónimos: ofrece candidatos. |
| `panorama(tema?)` | Sin tema: inventario de la base. Con tema: el mapa de esa área (o el Inventario si es un índice). |

Descripciones al estándar de Anthropic (nombres naturales, no IDs; pocas herramientas
potentes; contexto explícito). La superficie es la de un bibliotecario: no expone al que
consulta la topología interna (polos, wikilinks, frontmatter).

## Cómo busca (híbrido, sin RAG vectorial pesado ni LLM interno)

Cuatro señales fusionadas con Reciprocal Rank Fusion ponderado:

1. **Léxica** — SQLite FTS5 + BM25, con expansión morfológica española (Snowball):
   `residuo` halla `residuos`. Sin `porter` (es solo inglés). Palabras vacías por
   frecuencia documental del corpus, no por lista fija.
2. **Semántica** — embeddings estáticos `model2vec` (256 dims, int8), sin torch ni GPU.
   Encuentra por significado aunque no compartan vocabulario.
3. **Nombre** — coincidencia exacta, por subcadena o por raíces compartidas.
4. **Grafo** — difusión: los vecinos de los mejores resultados suben (excluyendo hubs).

Además: **recencia** como multiplicador con decaimiento exponencial (no hard-sort), con
fecha por nodo sacada del historial git. E **índices de directorio**: para preguntas de
listado, un índice que enumera a sus hijos gana (boost solo si la pregunta pide enumerar).

## Sinergia con la estructura de la KB

El servidor no puede rellenar lo que la KB no estructura. Dos palancas del lado del
contenido, que el gate de cada KB (`validate.py`, bloque `[13]`) señala como deuda:

- **Nodo-concepto para término recurrente:** un concepto usado sin nodo propio (p.ej.
  «NFU», «responsabilidad extendida del productor») rankea mal. Darle nodo atómico —sin
  inventar hechos, estructurando lo que ya vive disperso— lo lleva a primer lugar.
- **Índice temático:** una pregunta de listado («qué proyectos hay») necesita un nodo que
  los enumere. El MCP lo prioriza y muestra su `## Inventario`.

El KPI del servicio no es «¿se puede encontrar a mano?» sino la **relevancia de lo que
entrega por caso de uso** — un test end-to-end que mide *estructuración*, no contenido
factual.

## Despliegue

| Pieza | Dónde |
|---|---|
| Servicio | `docker-compose.yml` → servicio `kb-mcp`. `pull_policy: build` (se construye, no vive en registry — sin esto el `compose pull` del pipeline aborta el deploy). `read_only`, `no-new-privileges`, `mem_limit: 1200m`, sin `depends_on`. |
| Ruta pública | `Caddyfile` → `handle_path /kb/*` → `kb-mcp:8765`, `flush_interval -1`. |
| Clones de KB | `deploy.sh`, bloque `kb-mcp KB sync`: manifiesto `slug rama repo`, clon `--filter=blob:none` (historial completo para la recencia, 8 MB en vez de 154). |
| Sync | `sync-kb.sh` (cron */15 min): `git pull` de cada KB, reindexa solo si cambió. |
| Modelo | Montado desde `/opt/kb-modelo-256` (int8/256, ~140 MB). |

**Agregar una KB nueva son dos pasos:** una línea en el manifiesto `KB_MANIFIESTO` de
`deploy.sh`, y desplegar. Queda en `/kb/<slug>/mcp`.

## ⚠ El modelo NO se hornea en el build

Cuantizar el modelo durante `docker build` en ARM64 produce pesos distintos a los
validados (mismo código y origen, otro `model.safetensors`): las respuestas semánticas
salen mal **en silencio**. El artefacto validado se genera en x86_64
(`StaticModel.from_pretrained('minishlab/potion-multilingual-128M', quantize_to='int8')
.save_pretrained(dir)`), se copia a `/opt/kb-modelo-256` y se monta `:ro`. Las versiones
de `tokenizers`, `numpy` y `model2vec` van **fijas** en el Dockerfile por la misma razón.
Sin el modelo, el servidor arranca igual y degrada a solo búsqueda léxica.

## ⚠ El catch-all del proxy rompe el descubrimiento OAuth

Un servidor MCP sin autenticación debe responder **404** en las rutas de descubrimiento
(`/.well-known/oauth-protected-resource…`, `…/oauth-authorization-server`,
`…/openid-configuration`): así el cliente concluye «no hay auth» y conecta directo.

El catch-all del `Caddyfile` (`try_files {path} index.html`) servía la landing con **HTTP
200** a esas rutas. claude.ai lo leía como «este recurso exige OAuth», arrancaba el flujo
de login y fallaba con *«no se pudo registrar con el servicio de inicio de sesión»* —
aunque el endpoint MCP respondiera 200 sin token. Resuelto con dos bloques `handle` que
responden 404 antes del catch-all. Al agregar la capa de tokens, se reemplazan por la
metadata real (RFC 9728) en vez de eliminarlos.

Nota operativa: el sitio corre con `admin off`, así que `caddy reload` no funciona; los
cambios de `Caddyfile` requieren `docker restart caddy` (validar antes con
`docker exec caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile`).
El bind mount es de archivo: escribir con `tee` preserva el inode, `mv` lo rompe y el
contenedor seguiría viendo el archivo viejo.

## Autorización (pendiente, por diseño)

Hoy sin auth: la ruta es pública vía Tailscale Funnel. El diseño la deja lista para una
capa de tokens **por KB** sobre `/kb/<slug>` — el enrutamiento por nombre de repo no se
mezcla con la autorización. `personal` y `traza-ambiental` comparten el mismo endpoint sin
aislamiento; cerrar eso es el trabajo de auth pendiente.

## Recursos

~850 MB de RAM en régimen (el grueso es el tokenizador multilingüe de 500.353 tokens; la
tabla int8 son 128 MB). Portado a la plantilla en `kb-template/tools/kb-mcp/` para que las
KBs nuevas lo hereden; ver `kb-template/docs/PUBLISH-AS-MCP.md`.
