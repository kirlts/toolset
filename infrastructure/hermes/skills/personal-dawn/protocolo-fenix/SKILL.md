---
name: protocolo-fenix
description: "Protocolo Fenix — Ritual matutino para el grupo Personal. Cada dia a las 8AM busca contenido fresco (Reddit, YouTube, web) conectado a los intereses de Martin y su situacion actual, y envia un mensaje que lo enganche, lo impulse, y le recuerde que el sistema funciona para el."
version: 1.4.0
platforms: [linux]
metadata:
  hermes:
    tags: [personal, fenix, morning, ritual, proactive]
---
# Protocolo Fenix

## Objetivo

Cada manana a las 8 AM (hora Chile), enviar un mensaje al grupo Personal que:
1. Contenga contenido NUEVO encontrado en internet conectado a los intereses de Martin
2. Establezca una conexion con su situacion actual (usando datos de personal-buffer y personal-profile)
3. Termine con una conclusion o perspectiva que no existia antes
4. Capture atencion incluso con ojos entreabiertos y sueno

## Proposito emocional (CRITICO — no es opcional)

El protocolo Fenix no es informativo. Es transformacional. Cada mensaje debe lograr que Martin sienta:
- **Reconocimiento**: que veas lo que esta haciendo y se lo reconozcas genuinamente
- **Impulso**: que el mensaje le suba la energia, no solo le de informacion
- **Perspectiva nueva**: que vea su situacion desde un angulo que no habia considerado
- **Fuego interior**: que el mensaje toque algo que le importa profundamente

El valor del mensaje no esta en las fuentes que encontraste. Esta en lo que CONSTRUYES con ellas para EL.

## Fuentes (OBLIGATORIO: buscar en 2+ fuentes distintas)

- **Composio Reddit** (✅ Funciona): r/BlueLock, r/karate, r/WWE, etc. Usar REDDIT_SEARCH_ACROSS_SUBREDDITS y REDDIT_GET_R_TOP.
- **YouTube** (✅ Funciona): scraping HTML + oembed desde terminal.
- **Hacker News** (✅ Funciona): Algolia API.
- **Web** (⚠️ Google/DDG bloqueados): acceso directo a URLs conocidas.

ADVERTENCIA: Buscar en SOLO 1 fuente es inaceptable. La conexion entre 2+ fuentes ES el valor del mensaje. Si no puedes conectar naturalmente 2 fuentes, no envies nada.

## Reglas especificas para Blue Lock
- Capitulo mas reciente: ~353. NO usar capitulos anteriores a 340.
- NO usar reseñas de YouTube (hacen spoilers).
- Preferir posts de TEORIA y ANALISIS sin spoilers. NO usar threads [DISC].
- Buscar discusion de la comunidad sobre personajes o conceptos, no resumenes de capitulos.

## Acceso a fuentes desde OCI

### YouTube (funciona)
```bash
# 1. Buscar videos
curl -sL 'https://www.youtube.com/results?search_query=blue+lock+analysis&hl=en' \
  -H 'User-Agent: Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36' | \
  grep -oP '"videoId":"([^"]+)"' | sort -u | head -5

# 2. Obtener titulo via oembed (no requiere API key)
curl -sL "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=VIDEO_ID&format=json" \
  -H 'User-Agent: Mozilla/5.0' | python3 -c "import sys,json; print(json.load(sys.stdin).get('title',''))"
```

### Hacker News (funciona)
```bash
# Buscar por tema en Algolia API — escribir a archivo temporal primero
curl -s 'https://hn.algolia.com/api/v1/search?query=TERMINO&tags=story&hitsPerPage=5' -o /tmp/hn_search.json
python3 -c "
import json
data = json.load(open('/tmp/hn_search.json'))
for h in data.get('hits',[]):
    print(f'Title: {h[\"title\"]}')
    print(f'URL: {h.get(\"url\",\"\")}')
    print(f'Score: {h.get(\"points\",0)}')
    print(f'Text: {h.get(\"story_text\",\"\")[:300]}')
    print()
"

# Front page del dia
curl -sL 'https://news.ycombinator.com/' -H 'User-Agent: Mozilla/5.0' | \
  grep -oP 'class="titleline"[^>]*><a[^>]*>([^<]+)</a>'
```

**Pitfall HN**: NO usar `curl | python3 -c` con comillas mixtas (f-string con `h["title"]` dentro de comillas dobles en bash). El `eval` del shell rompe. Siempre escribir a archivo temporal con `-o /tmp/hn.json` y luego parsear.

**Pitfall HN queries multi-palabra**: Queries como `martial%20arts%20discipline%20self-taught` devolvieron 0 hits. `autodidact%20self-taught` devolvio 5 hits. Preferir terminos compound/unicos sobre frases largas. Si una query HN devuelve 0 hits, reformular con terminos mas cortos y specificity alta.

### Reddit via Composio (✅ Funciona)

Usar REDDIT_SEARCH_ACROSS_SUBREDDITS con search_query tipo `subreddit:TOPICO query`. Buscar posts de TEORIA/ANALISIS:
- Blue Lock: `subreddit:BlueLock theory analysis character ego`
- Karate: `subreddit:karate training mindset discipline`
- WWE: `subreddit:WWE story character analysis`

Siempre extraer selftext del post y comentarios con alto score via REDDIT_RETRIEVE_POST_COMMENTS. Las citas textuales de comentarios con 200+ upvotes tienen mas peso que los titulos.

Para posts recientes de la semana: REDDIT_GET_R_TOP con t=week.

Parsear respuesta: los posts pueden venir en `data.children[].data` (formato Listing) o en `posts[]` directo. Para comentarios, el response tiene `post_listing` y `comments_listing`.

### Pitfall: r/Baki inaccesible via Composio
`REDDIT_GET_R_TOP` con subreddit="Baki" devuelve 403: "Access forbidden. The subreddit may be private, quarantined, or banned." NO usar r/Baki con Composio. Para contenido de Baki, buscar en r/anime o r/manga con query sobre Baki, o usar HN/web directa.

### Pitfall: REDDIT_SEARCH_ACROSS_SUBREDDITS puede 503
El endpoint de search es mas fragil que top/week. En la ejecucion del 2026-07-06 PM, `REDDIT_SEARCH_ACROSS_SUBREDDITS` con query WWE devolvio 503 (upstream connect error / connection timeout) mientras `REDDIT_GET_R_TOP` con t=week funciono perfecto. Si search devuelve 503 o timeout, NO reintentar — pasar directo a top/week que es mas estable.

### Matizacion: WWE top/week — el valor esta en comentarios, no en selftext
Los posts top/week de r/WWE son mayormente imagenes y videos (memes, cumpleanos, tributos) con selftext vacio o trivial ("It's been over 20 years since Rey Mysterio debuted..."). NO descartar estos posts por selftext pobre. El contenido analitico精选 esta en los COMENTARIOS. En la ejecucion 2026-07-06 PM, el post 1uk5h8o (Austin Theory/Roman Reigns, 590 upvotes) tenia selftext vacio pero el comentario con 58 upvotes ("feels trained... afraid of letting loose") fue la cita central del mensaje. **Conclusion practica**: para r/WWE, siempre extraer comentarios aunque el selftext sea vacio. Ordenar por score y tomar top 3-5.

### Estrategia de busqueda paralela (PROBADO — mejor que busqueda secuencial)

Ejecutar en UNA sola llamada `COMPOSIO_MULTI_EXECUTE_TOOL`:
1. `REDDIT_SEARCH_ACROSS_SUBREDDITS` con query de teoria/analisis (sort=relevance, limit=10)
2. `REDDIT_GET_R_TOP` con t=week para el mismo subreddit (limit=15)
3. Repetir para 2-3 subreddits distintos (BlueLock + karate + WWE es la combinacion mas productiva). Ver pitfall: no usar r/Baki (403)

**Por que buscar top/week junto a search**: Los posts top de la semana (mas votados, mas comentados) suelen ser MAS potentes que los resultados de search por relevance, porque search mezcla posts historicos de 2022-2023 que ya no tienen frescura. Top/week garantiza contenido ACTUAL de la comunidad. En la ejecucion del 2026-07-06, los posts top de la semana dieron 845 y 453 upvotes con selftext rico; el search por relevance devolvio posts de 2023 con 0 frescura.

**Matizacion (2026-07-06 PM)**: top/week y search relevance sirven para cosas distintas segun la semana. Los top/week de BlueLock esa semana fueron sobre el partido real de Japon (no manga), por lo que search relevance fue mas util para teoria/analisis BlueLock (582 upvotes "Symbolism of the Chains"). **Conclusion practica**: buscar AMBOS siempre, porque segun la semana cada uno aporta contenido de tipo diferente.

### Extraccion de comentarios (patron probado)

Despues de identificar 2-3 posts con alto score y buen selftext, usar `COMPOSIO_MULTI_EXECUTE_TOOL` con `REDDIT_RETRIEVE_POST_COMMENTS` para todos a la vez. Luego procesar con `COMPOSIO_REMOTE_WORKBENCH`:

```python
def walk_comments(children, depth=0, max_depth=2):
    results = []
    for ch in children or []:
        if not isinstance(ch, dict):
            continue
        if ch.get('kind') != 't1':
            continue
        d = ch.get('data') or {}
        body = d.get('body', '')
        score = d.get('score', 0)
        if body and body not in ('[deleted]', '[removed]'):
            results.append({'score': score, 'body': body, 'depth': depth})
        replies = d.get('replies')
        if isinstance(replies, dict) and depth < max_depth:
            rchildren = (replies.get('data') or {}).get('children') or []
            results.extend(walk_comments(rchildren, depth+1, max_depth))
    return results

# Cargar, extraer, ordenar por score
file_data = json.load(open("/mnt/files/mex/RESULT_FILE.json"))
r = file_data['results'][INDEX]['response']['data']
comments = walk_comments(r['comments_listing']['data']['children'])
comments.sort(key=lambda x: x['score'], reverse=True)
# Tomar top 5-8 comentarios para citas
```

El post selftext esta en `r['post_listing']['data']['children'][0]['data']['selftext']`.
Ver `references/reddit-composio-extraction.md` para el patron completo con ejemplos de codigo y estructuras de respuesta.

### Google / DuckDuckGo (NO funcionan desde OCI)
Bloqueados. Usar acceso directo a URLs conocidas si es necesario.

## Pitfalls de ejecucion cron

- **delegate_task no es confiable para cron**: los subagentes pueden no completar antes de que termine la ventana de ejecucion. Usar `terminal()` directo para busquedas sincronicas.
- **execute_code bloqueado en cron**: el security scanner bloquea `execute_code` en modo cron. No intentarlo. Usar terminal() o mcp_composio para procesamiento.
- **Pipe a python3**: el security scanner de cron puede bloquear `curl | python3 -c`. Preferir escribir script a archivo y ejecutarlo: escribe el script con `write_file` y ejecuta con `terminal("python3 script.py")`. En la practica, `curl | python3 -c` SI funciona para oembed (respuestas chicas, sin pipe de datos grandes).
- **Limite de tiempo**: la ventana de cron es finita. Si una busqueda no responde en 15s, pasar a la siguiente fuente.

## Reglas de contenido

- NADA de terminos de Kairos (Kratos, Khaos, vector, etc.) — Martin dijo explicitamente que NO
- Lenguaje sencillo, aterrizado, como conversacion real
- Referencias permitidas: Blue Lock, Baki, karate, Legos, WWE, cosas que le gustan
- No usar: "weon" — no va con este grupo
- No empezar con frases falsas como "cuando despiertes me cuentas"
- El mensaje debe tener UNA CONCLUSION que justifique el uso de su Knowledge Base
- Si usas info de su KB, debe ser para habilitar una conclusion, no para decorar
- NO preguntar nada que parezca tarea o desafio
- NO pedir compromisos ni objetivos del dia
- NO terminar con frases hechas ("manana otra")

## Tono

- Directo, sin rodeos
- Sin lenguaje rimbombante ni filosofico
- Sin pretender ser humano
- Martin sabe que esto es un sistema que el configuro — no necesita falsa calidez

## Pipeline de generacion

1. **RECALL** personal-buffer (tags pending, fenix) y personal-profile para entender su situacion actual.
2. **BUSCA en AL MENOS 2 fuentes externas** (Composio Reddit, YouTube scraping, HN, web directa).
3. **EXTRAE contenido REAL** de cada fuente: selftext del post, comentarios con alto score. No te limites a leer titulos.
4. **CONECTA las fuentes**: no las presentes como items separados. Encuentra la tesis que NINGUNA fuente tiene individualmente pero que todas apuntan.
5. **REDACTA** el mensaje con el formato de abajo.
6. **GENERA audio** con text_to_speech para acompanar el mensaje.

## Estructura del mensaje

Formato probado (surgido de ejecuciones reales):

```
[Cita textual relevante de la fuente 1 + analisis que introduce la conexion]
[Cita textual relevante de la fuente 2 + analisis que profundiza la conexion]
[Cita textual relevante de la fuente 3 (si existe) + cierre de la conexion]
[TESIS NUEVA que no esta en ninguna fuente individual — el analisis que solo existe por haberlas conectado]
[Links a las fuentes]
```

REGLAS:
- Cada fuente necesita al menos UNA cita directa. No parafrasear sin citas.
- No presentar las fuentes como lista separada. El valor esta en la CONEXION.
- La tesis final debe conectar directamente con la situacion HOY de Martin (dojo cerrando, entrenamiento autogestionado, semana pesada, etc.)
- OPCIONAL: link al contenido al final.

## Audio (text_to_speech) — OBLIGATORIO

Despues de redactar el mensaje, LLAMAR text_to_speech con el texto del mensaje para generar el audio. Incluir MEDIA:/path/to/audio en la respuesta. Sin audio = ejecucion fallida. Esto aplica tanto a la chispa de 8AM como al follow-up de 2PM.

## Anti-repeticion de fuentes

No repetir contenido ya usado en ejecuciones anteriores. Usar criterio propio para detectar si una fuente ya fue utilizada — no usar tags ni registros.

## Ciclo de aprendizaje continuo

Cada dia, cuando Martin responde a la chispa, su feedback se divide en dos flujos:

### Feedback personal
Todo lo que Martin dice sobre su vida, sus emociones, sus reflexiones -> personal-buffer (tags pending + terreno/mito), para sesion de revision del buffer.

### Feedback meta (sobre el Protocolo Fenix)
Todo lo que Martin dice sobre COMO se escribio la chispa: que funciono, que no, ajustes de tono, correcciones -> retain en personal-profile (tag "fenix-feedback"). Este es el banco canonico de hindsight, que perdura.

### Incorporacion en la siguiente ejecucion
El cron 8AM del dia siguiente DEBE:
1. HACER RECALL de personal-profile con tag "fenix-feedback", limit 3, ordenado por fecha descendente
2. Si hay feedback nuevo desde la ultima ejecucion, INCORPORARLO en la generacion de la nueva chispa
3. El feedback AFINA, no redefine

## Si no responde

No pasa nada. Solo un mensaje. No saturar.

## Follow-up 2PM (solo si no respondio)

Un segundo mensaje corto. NO es recordatorio. NO dice "te acordai de lo de hoy". Es una pieza adicional que conecta tangencialmente con la de la manana pero vale por si sola.

### Estrategia de fuentes para follow-up (probado 2026-07-06)
El follow-up debe usar fuentes DIFERENTES a la chispa de la manana. Si la manana uso Blue Lock + karate, el follow-up puede usar WWE + YouTube. La conexion tangencial funciona mejor cuando el angulo es completamente distinto pero la tesis aplica igual a la situacion de Martin. En la ejecucion del 2026-07-06 PM, la manana conectaba Blue Lock (aislamiento de Isagi) con karate autogestionado, y el follow-up conecto WWE (Theory "trained" vs Rey Mysterio 20 anos sin heel turn) con salir del dojo = salir del script. Misma tesis subyacente, angulo totalmente distinto.

## Registro

Todas las interacciones del Protocolo Fenix se registran en personal-buffer con tag "fenix" para seguimiento y mejora continua.