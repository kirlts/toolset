# SearXNG `default_doi_resolver` — Pitfall ARM64/OL9

## Contexto

SearXNG >=2026.6.24 introdujo validación estricta de `default_doi_resolver` y `doi_resolvers` en `preferences.py`, línea 461. Si estas claves faltan o están mal ubicadas en settings.yml, el endpoint `/search` responde 500 con:

```
KeyError: 'default_doi_resolver'
```

## Causa raíz

La función `get_setting("default_doi_resolver")` busca la key a **root level** del settings (no anidada bajo `search:`). Además necesita `doi_resolvers` (plural, dict) para validar el valor.

## Config correcta

```yaml
# ROOT LEVEL — no bajo search:
doi_resolvers:
  oadoi.org: 'https://oadoi.org/'
  doi.org: 'https://doi.org/'

default_doi_resolver: 'oadoi.org'

search:
  safe_search: 0
  # ... resto de config ...
```

## Errores comunes

| Error | Causa | Fix |
|---|---|---|
| `KeyError: 'default_doi_resolver'` | Key ausente o mal indentada | Poner a root level |
| `ValidationException: Invalid value: "['oadoi.org']"` | `doi_resolvers` dict ausente | Agregar `doi_resolvers:` con keys válidas |
| Error persiste tras restart | Contenedor cachea config en memoria | Recrear container: `docker compose stop + rm -f + up -d` |
| `engine qwant failed: set engine to inactive` | qwant cambió su API | Disable qwant en settings.yml (`disabled: true`) |

## Script de verificación

```bash
# Test rápido
curl -s -o /dev/null -w "%{http_code}" "http://localhost:4000/search?q=test&format=json"
# 200 = OK, 500 = config problem

# Logs
docker logs researchit-searxng --tail 10 | grep -i error
```

## Referencia

- `isinstance(value, dict)` en `get_setting()` busca flat keys
- `DOI_RESOLVERS = list(settings['doi_resolvers'])` en `preferences.py:30`
- `MultipleChoiceSetting` valida contra `DOI_RESOLVERS`
