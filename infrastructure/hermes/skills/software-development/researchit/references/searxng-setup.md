# SearXNG en ARM64/OL9 — Configuración

## Contenedor Docker

SearXNG está en el docker-compose de toolset (`infrastructure/docker-compose.yml`):

```yaml
searxng:
  image: searxng/searxng:latest
  container_name: researchit-searxng
  restart: unless-stopped
  ports:
    - "4000:8080"
  user: root  # REQUIRED en ARM64/SELinux — el usuario searxng no puede escribir /etc/searxng/
  environment:
    - SEARXNG_BASE_URL=http://localhost:4000/
  cap_drop:
    - ALL
  cap_add:
    - CHOWN - SETUID - SETGID
  networks:
    - toolset-net
```

## Configuración Inicial

Al primer inicio sin settings.yml custom, SearXNG genera uno por defecto con `use_default_settings: true`. Para habilitar JSON output y bind externo:

```bash
docker exec researchit-searxng sh -c "cat > /etc/searxng/settings.yml << 'EOF'
use_default_settings: true
server:
  secret_key: \"researchit-searxng-local\"
  bind_address: \"0.0.0.0\"
  limiter: false
  image_proxy: false
search:
  formats:
    - html
    - json
EOF"
docker restart researchit-searxng
```

## API

```
GET http://localhost:4000/search?q={query}&format=json&language=es
```

Respuesta: `{results: [{title, url, content, engine, score}]}`

## Engines Disponibles (default)

google, duckduckgo, brave, bing, qwant, startpage, wikipedia

## Troubleshooting

| Problema | Causa | Solución |
|----------|-------|----------|
| Container restart loop | Permisos /etc/searxng/settings.yml | Usar `user: root` |
| 403 Forbidden | `bind_address: 127.0.0.1` o limiter activo | Set `bind_address: 0.0.0.0` y `limiter: false` |
| Empty JSON response | JSON format no habilitado | Agregar `search.formats: [html, json]` |
| SELinux blocking bind mount | SELinux enforcing | No usar bind mounts. Dejar que el container genere su settings.yml solo. |
