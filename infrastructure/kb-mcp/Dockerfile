# kb-mcp — servidor MCP de solo lectura para KBs de kb-template
# Multi-arch: se construye en el VPS (ARM64 / Ampere A1). Con torch CPU, sin GPU.
#
# TRAE TORCH DESDE EL 2026-08-07, y el encabezado decia lo contrario a proposito hasta ese dia. El
# motivo del cambio esta medido sobre las 81 preguntas juzgadas de kb-okos: la tabla de embeddings
# estaticos deja 28 de 81 preguntas sin traer su documento; un codificador real deja 20. Para el
# consumidor que esta base tiene de verdad —un agente, que puede volver a preguntar— eso es pasar de
# encontrar lo buscado el 83 % de las veces al 93 %.
#
# En ARM no hay ruedas CUDA, asi que `pip install torch` trae la version CPU y pesa ~427 MB.
FROM python:3.12-slim

# GIT, y no es una dependencia de desarrollo: el servidor lee la FECHA de cada entrada del historial
# de versiones (`fechas_git()`), porque la temporalidad de un grafo que crece vive en su historial y
# no en el encabezado de los archivos. La imagen `slim` no trae git, asi que en el contenedor esa
# funcion caia por su propio degradado —devuelve vacio y no falla— y el servidor real NO LE DECIA A
# NADIE cuando se actualizo ninguna entrada: cero fichas con fecha, el orden «reciente» sin operar, y
# el multiplicador de recencia del ranking apagado. O sea que en produccion un hecho de hoy no le
# ganaba a un plan de anteayer, que es exactamente lo que la recencia existe para lograr.
#
# COMO SE SUPO, y por que la causa NO era la que se penso primero: una evaluacion del 2026-08-05
# midio que el remoto no traia fechas y lo atribuyo a que el contenedor no tenia historial. El clon
# SI trae historial completo —`--filter=blob:none` se eligio a proposito para eso—; lo que faltaba
# era el programa para leerlo. Comprobado dentro del contenedor: `command -v git` no devuelve nada.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# numpy y model2vec dan la capa semantica (embeddings estaticos, tabla de consulta
# token->vector). snowballstemmer da la morfologia espanola de la capa lexica.
# Versiones FIJAS a proposito: con tokenizers sin fijar, la 0.23 tokeniza distinto que
# la 0.22 y el mismo texto produce otro vector. El contenedor devolvia resultados
# semanticos incorrectos pese a cargar el mismo modelo. Reproducibilidad, no capricho.
RUN pip install --no-cache-dir \
# TECHO DE VERSION, y es obligatorio: `mcp` 2.0.0 salio el 2026-08-05 y movio
# `mcp.server.fastmcp`, que es lo que este servidor importa en su linea 35. La imagen se
# reconstruyo ese dia por otro motivo, pip trajo la version nueva sin preguntar, y el
# contenedor entro en reinicio perpetuo con la base entera sin conector. La dependencia
# estaba declarada sin techo desde el principio: cualquier reconstruccion de ese dia lo
# habria roto igual, sin que nadie hubiera cambiado una linea del servidor.
        "mcp>=1.2,<2" pyyaml \
        "snowballstemmer==3.0.1" \
        "numpy==2.4.6" \
        "tokenizers==0.22.2" \
        "model2vec==0.8.2" \
    && useradd --create-home --uid 10001 kb

# EL CODIFICADOR. `model2vec` se conserva arriba a proposito: `KB_MODELO` puede volver al modelo
# estatico sin reconstruir la imagen, que es la reversion de este cambio. Versiones fijas por la
# misma razon que las de arriba —una tokenizacion distinta produce otro vector— y porque el modelo
# se hornea abajo con ESTA version.
RUN pip install --no-cache-dir \
        "sentence-transformers==5.7.0" \
        "torch==2.13.0"

# EL MODELO VA HORNEADO, y aca si —a diferencia del estatico, cuya cuantizacion en ARM producia
# pesos distintos a los validados—. Este no se cuantiza: se descarga tal cual, asi que el artefacto
# es identico al medido. Se hornea porque el contenedor arranca con `HF_HUB_OFFLINE=1` y sin red.
ENV HF_HOME=/opt/hf
RUN mkdir -p /opt/hf && python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')" \
    && chown -R 10001:10001 /opt/hf

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
# EL MODELO POR NOMBRE, no por ruta montada: el codificador viene horneado en la imagen y se resuelve
# desde `HF_HOME`. Para volver al estatico basta `KB_MODELO=/modelo` en compose —el montaje
# `/opt/kb-modelo-256` se conserva justamente para que esa reversion no necesite reconstruir nada.
ENV KB_MODELO=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
# DONDE SE CACHEAN LOS VECTORES. Sin un volumen de escritura montado aca el servidor arranca igual y
# recalcula todo, que es el comportamiento anterior: el codigo degrada bien a proposito. Con volumen,
# un reinicio recalcula solo los textos que cambiaron. Medido: 49,3 s sin cache contra 8,7 s con
# cache, y el indice sin ningun modelo ya cuesta 7,9 s — o sea que el codificador agrega 0,8 s.
# Importa porque `sync-kb.sh` reinicia este contenedor en cada cambio de contenido: 28 veces el
# 2026-08-07. Ver MASTER-SPEC 7.2 y HEU-013.
ENV KB_VECTORES=/vectores/kb-mcp.npz
# Hosts legitimos para la proteccion anti-DNS-rebinding del SDK (se sobreescribe
# desde compose). Sin esto el servidor responde 421 detras del proxy.
ENV KB_ALLOWED_HOSTS=kb-mcp:8765,localhost:8765,127.0.0.1:8765
# El modelo va horneado; sin red al arrancar.
ENV HF_HUB_OFFLINE=1

EXPOSE 8765

# Sirve todas las KB bajo KB_ROOT, cada una en /<slug>/mcp. Sin KB por defecto en la
# raiz. Sin estado: el RC de MCP del 2026-07-28 elimina las sesiones de protocolo.
CMD ["sh", "-c", "python /app/server.py --kbs $KB_ROOT --transport streamable-http --host 0.0.0.0 --port 8765"]
