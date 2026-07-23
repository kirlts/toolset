# kb-mcp — servidor MCP de solo lectura para KBs de kb-template
# Multi-arch: se construye en el VPS (ARM64 / Ampere A1). Sin torch ni GPU.
FROM python:3.12-slim

# numpy y model2vec dan la capa semantica (embeddings estaticos, tabla de consulta
# token->vector). snowballstemmer da la morfologia espanola de la capa lexica.
# Versiones FIJAS a proposito: con tokenizers sin fijar, la 0.23 tokeniza distinto que
# la 0.22 y el mismo texto produce otro vector. El contenedor devolvia resultados
# semanticos incorrectos pese a cargar el mismo modelo. Reproducibilidad, no capricho.
RUN pip install --no-cache-dir \
        "mcp>=1.2" pyyaml \
        "snowballstemmer==3.0.1" \
        "numpy==2.4.6" \
        "tokenizers==0.22.2" \
        "model2vec==0.8.2" \
    && useradd --create-home --uid 10001 kb

# El modelo NO se hornea aqui a proposito. Cuantizarlo durante el build en ARM64
# producia pesos distintos a los validados (mismo codigo, mismo origen, otro
# model.safetensors) y las respuestas semanticas salian mal sin fallar. El artefacto
# validado se monta desde /opt/kb-modelo en modo lectura; ver INFRASTRUCTURE-MANIFEST.
# Si el montaje falta, el servidor arranca igual y queda solo con la capa lexica.

RUN pip install --no-cache-dir "uvicorn>=0.30" "starlette>=0.37"

USER kb
WORKDIR /app
COPY server.py /app/server.py

# Directorio que contiene una o varias KB (cada subdir con knowledge-base/ es una).
# Cada KB se sirve bajo /<slug>/mcp; no hay KB por defecto en la raiz.
ENV KB_ROOT=/kb
ENV KB_MODELO=/modelo
# Hosts legitimos para la proteccion anti-DNS-rebinding del SDK (se sobreescribe
# desde compose). Sin esto el servidor responde 421 detras del proxy.
ENV KB_ALLOWED_HOSTS=kb-mcp:8765,localhost:8765,127.0.0.1:8765
# El modelo va horneado; sin red al arrancar.
ENV HF_HUB_OFFLINE=1

EXPOSE 8765

# Sirve todas las KB bajo KB_ROOT, cada una en /<slug>/mcp. Sin KB por defecto en la
# raiz. Sin estado: el RC de MCP del 2026-07-28 elimina las sesiones de protocolo.
CMD ["sh", "-c", "python /app/server.py --kbs $KB_ROOT --transport streamable-http --host 0.0.0.0 --port 8765"]
