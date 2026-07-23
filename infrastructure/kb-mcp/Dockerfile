# kb-mcp — servidor MCP de solo lectura para KBs de kb-template
# Multi-arch: se construye en el VPS (ARM64 / Ampere A1).
FROM python:3.12-slim

RUN pip install --no-cache-dir "mcp>=1.2" pyyaml \
    && useradd --create-home --uid 10001 kb

USER kb
WORKDIR /app
COPY server.py /app/server.py

# La KB se monta en modo lectura desde el host (bind ro).
ENV KB_PATH=/kb
# Hosts legitimos para la proteccion anti-DNS-rebinding del SDK (se sobreescribe
# desde compose). Sin esto el servidor responde 421 detras del proxy.
ENV KB_ALLOWED_HOSTS=kb-mcp:8765,localhost:8765,127.0.0.1:8765

EXPOSE 8765

# Sin estado: el RC de MCP del 2026-07-28 elimina las sesiones de protocolo.
CMD ["sh", "-c", "python /app/server.py --kb $KB_PATH --transport streamable-http --host 0.0.0.0 --port 8765"]
