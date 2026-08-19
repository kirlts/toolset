# Reddit via Composio — Patron de extraccion probado

## Flujo completo (3 fases)

### Fase 1: Busqueda paralela (1 llamada MULTI_EXECUTE)

Ejecutar en paralelo en UNA sola llamada `COMPOSIO_MULTI_EXECUTE_TOOL`:
- `REDDIT_SEARCH_ACROSS_SUBREDDITS` con query de teoria (sort=relevance, limit=10)
- `REDDIT_GET_R_TOP` con t=week para el mismo subreddit (limit=15)
- Repetir para 2-3 subreddits (BlueLock + karate es la combinacion mas productiva)

Los resultados se guardan en `/mnt/files/mex/<filename>.json`. Procesar con `COMPOSIO_REMOTE_WORKBENCH`.

### Fase 2: Identificar posts con contenido rico

Criterios para seleccionar posts:
- **Score alto** (preferir 50+ upvotes, idealmente 200+)
- **Selftext largo** (100+ caracteres) — el selftext es el cuerpo del post, mas rico que el titulo
- **Frescura** (posts de la semana tienen prioridad sobre posts historicos)
- **No spoilers** (para Blue Lock: evitar threads [DISC] y reseñas de capitulos)

Los posts top de la semana (REDDIT_GET_R_TOP t=week) suelen ser MAS potentes que los de search por relevance porque search mezcla posts historicos. En la ejecucion del 2026-07-06:
- r/karate top/week: 845 upvotes ("white belt 20 years"), 453 upvotes ("10th Dan"), 100 upvotes ("Over 40 Karate beginner")
- r/BlueLock top/week: 3656 upvotes ("Ego was right"), 3621 ("Thank you Bluelock" sobre partido real de Japon)
- r/karate search relevance: posts de 2022-2023 con 0 frescura

NOTA: Los top/week de BlueLock esta semana fueron en su mayoria sobre el partido real de Japon (no manga), por lo que para contenido de teoria/analisis BlueLock, el search por relevance fue mas util (582 upvotes "Symbolism of the Chains", 199 upvotes "Prodigies Guide"). **Conclusion practica**: buscar AMBOS (top/week + search relevance) porque sirven para diferentes tipos de contenido segun la semana.

### Fase 3: Extraccion de comentarios (1 llamada MULTI_EXECUTE)

Para 2-5 posts seleccionados, llamar `REDDIT_RETRIEVE_POST_COMMENTS` con `article` = ID del post (base-36, sin prefijo t3_). Procesar con workbench:

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

file_data = json.load(open("/mnt/files/mex/RESULT_FILE.json"))

def process_post(idx):
    r = file_data['results'][idx]['response']['data']
    # Selftext del post
    post_data = r['post_listing']['data']['children'][0]['data']
    print(post_data['title'])
    print(post_data['selftext'][:1500])
    # Comentarios ordenados por score
    comments = walk_comments(r['comments_listing']['data']['children'])
    comments.sort(key=lambda x: x['score'], reverse=True)
    for c in comments[:6]:
        print(f"  Score:{c['score']} | {c['body'][:400]}")
```

## Estructura de respuestas

### REDDIT_SEARCH_ACROSS_SUBREDDITS
- Posts en `data.posts[]` (formato directo) — acceso en workbench: `file_data['results'][0]['response']['data']['posts']`
- Campos clave: `id`, `title`, `selftext`, `score`, `num_comments`, `permalink`, `created_utc`, `created_datetime`

### REDDIT_GET_R_TOP
- Posts en `data.data.children[].data` (formato Listing, kind=t3)
- **Pitfall doble anidacion `data`**: En workbench, `file_data['results'][i]['response']['data']` ya ES el listing (`{kind: "Listing", data: {children: [...], after: ...}}`). Para obtener los children:
  ```python
  r = file_data['results'][i]['response']['data']
  d = r.get('data', r)  # bajar un nivel si existe
  children = d.get('children', [])
  ```
  Si haces `r.get('children', [])` directo, obtienes lista vacia.
- Mismos campos que search

### REDDIT_RETRIEVE_POST_COMMENTS
- `data.post_listing.data.children[0].data` — metadata del post (incluye selftext)
- `data.comments_listing.data.children[]` — arbol de comentarios (kind=t1)
- Comentarios anidados en `replies.data.children[]` (recursivo)
- Filtrar kind=="t1", excluir body=="[deleted]" o "[removed]"

## Pitfalls

- **IDs de posts**: el parametro `article` de REDDIT_RETRIEVE_POST_COMMENTS espera el ID base-36 sin prefijo t3_. Ejemplo: `1ukaneb` (no `t3_1ukaneb`).
- **No buscar solo 1 subreddit**: La combinacion BlueLock + karate produce conexiones mas ricas que cualquiera por si solo. Buscar en 2-3 subreddits distintos.
- **No limitarse a titulos**: El valor del mensaje esta en las citas textuales del selftext y comentarios con alto score. Sin citas, el mensaje pierde peso.
- **HN Algolia pipe**: No hacer `curl | python3 -c` con f-strings que contienen `h["title"]` dentro de comillas dobles en bash. El eval del shell rompe. Usar `-o /tmp/hn.json` y luego parsear.
- **HN Algolia queries multi-palabra**: Queries como `martial arts discipline self-taught` (espacios codificados `%20`) devolvieron 0 hits. `autodidact self-taught` devolvio 5 hits. **Preferir terminos compound/unicos sobre frases largas**. Si una query HN devuelve 0 hits, reformular con terminos mas cortos y specificity alta.