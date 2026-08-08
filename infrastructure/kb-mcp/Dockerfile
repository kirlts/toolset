# kb-mcp — servidor MCP de solo lectura para KBs de kb-template
# Multi-arch: se construye en el VPS (ARM64 / Ampere A1). Sin torch ni GPU: ver abajo por que el
# codificador se probo y se retiro el 2026-08-07.
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

# EL CODIFICADOR, Y POR QUE VUELVE DESPUES DE HABERSE RETIRADO EL 2026-08-07.
#
# Se agrego el 2026-08-07, dejo las TRES bases en `semantica:false` —incluidas dos que nada
# tenian que ver con el cambio— y se retiro el mismo dia. La causa que se escribio entonces fue
# que `sentence-transformers` arrastra `transformers`, que exigiria un `tokenizers` mas nuevo
# que el clavado arriba.
#
# ESA CAUSA SE COMPROBO EL 2026-08-08 Y NO SE REPRODUCE. Con estos pines exactos, en esta misma
# imagen base, pip resuelve el arbol entero sin mover `tokenizers` y `pip check` no encuentra
# nada roto: tokenizers 0.22.2, transformers 4.57.6, model2vec 0.8.2, sentence-transformers
# 5.1.2, torch 2.9.1+cpu. Y los dos cargadores —StaticModel y SentenceTransformer— conviven en
# el MISMO interprete, comprobado cargando los dos y vectorizando con cada uno.
#
# La causa REAL de aquella caida esta registrada en el propio servidor y es otra: habia DOS
# reglas para decidir si el modelo configurado es estatico, una de ellas miraba la forma del
# directorio, el artefacto montado en /modelo no cumplia esa forma, y se lo mando al cargador
# equivocado. Ver el comentario de `_cargar_modelo_crudo()` en server.py. Esa segunda regla ya
# no existe.
#
# QUE SE GANA, medido sobre las 81 preguntas juzgadas, con el criterio que importa —quien
# consulta esta base es SIEMPRE un agente, asi que pesa el conjunto devuelto y no el primer
# puesto—: las preguntas que NO traen su documento bajan de 27 a 20. El primer puesto sube de
# 35 a 37, que es lo de menos.
#
# COMO SE REVIERTE, y por eso el codificador NO es el valor por omision de esta imagen:
# `KB_MODELO` sigue apuntando a `/modelo`, o sea al estatico. Instalar la biblioteca no cambia
# el modelo; el cambio de modelo es UNA variable en docker-compose.yml, y volver atras es
# quitarla y reiniciar. Las dos familias quedan instaladas a proposito para que revertir no
# exija reconstruir la imagen.
RUN pip install --no-cache-dir \
        "torch==2.9.1" --extra-index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir \
        "sentence-transformers==5.1.2" \
        "transformers==4.57.6" \
    && pip check

# LOS PESOS SE HORNEAN, y aca si conviene, al reves que con el estatico. La advertencia de mas
# abajo es sobre CUANTIZAR durante el build, que en ARM64 producia pesos distintos a los
# validados. Un codificador no se cuantiza: se usa tal cual viene, asi que hornearlo da
# exactamente el mismo artefacto en cualquier arquitectura. Se hornea antes de bajar de
# privilegios, en una ruta que el usuario `kb` puede leer, porque el contenedor corre sin red
# al arrancar (HF_HUB_OFFLINE=1) y sin esto el modelo no existiria para el.
ENV HF_HOME=/opt/hf
RUN mkdir -p /opt/hf && \
    python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')" && \
    chmod -R a+rX /opt/hf

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
# UN HILO POR BIBLIOTECA DE CALCULO, y la razon es la RESPUESTA y no el rendimiento. El VPS
# tiene DOS nucleos. Con los valores por omision, torch abre un hilo por nucleo y la
# reconstruccion del indice se los come los dos, asi que quien consulta espera. Medido en
# contenedor: la peor latencia durante una recarga llegaba a 7,3 s (sin fallar ninguna). Con
# un hilo, la reconstruccion tarda mas y eso ya no le cuesta a nadie: desde que reconstruir
# no corta el servicio, cuanto tarda dejo de ser un problema de disponibilidad.
ENV OMP_NUM_THREADS=1
ENV TOKENIZERS_PARALLELISM=false

EXPOSE 8765

# Sirve todas las KB bajo KB_ROOT, cada una en /<slug>/mcp. Sin KB por defecto en la
# raiz. Sin estado: el RC de MCP del 2026-07-28 elimina las sesiones de protocolo.
# `exec` NO ES DECORATIVO: sin el, PID 1 es el shell y el servidor es su hijo, asi que
# `docker kill -s HUP kb-mcp` le llega al shell y el servidor nunca se entera. Y SIGHUP es
# como `sync-kb.sh` le pide al servidor que recargue el indice SIN reiniciar el contenedor
# —lo que elimina los 9 a 49 segundos en que la base no contestaba en cada cambio de
# contenido, 28 veces el 2026-08-07—. Comprobado: con `sh -c` sin `exec`, la senal no
# produce ninguna recarga y `/kb/salud` sigue en la misma generacion.
CMD ["sh", "-c", "exec python /app/server.py --kbs $KB_ROOT --transport streamable-http --host 0.0.0.0 --port 8765"]
