#!/usr/bin/env python3
"""
Servidor MCP de solo lectura para KBs construidas con kb-template.

Sirve VARIAS KB desde un solo proceso: el modelo de embeddings se carga una vez y
cada KB tiene su propio indice. Nada del dominio esta escrito aqui — los polos, sus
etiquetas y el nombre salen de cada repo (kb/mcp.yaml, o se derivan del arbol).

La superficie es la de un bibliotecario: consultar, leer, panorama. La topologia
interna (polos, wikilinks, frontmatter) se usa para responder mejor, pero no se le
pide al que consulta que la conozca.

    python server.py --kb ~/traza-ambiental                      # stdio, una KB
    python server.py --kbs /opt/kb --transport streamable-http   # http, todas
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import contextlib
import copy
import datetime
import json
import math
import signal
import textwrap
import hashlib
import sys
import os
import re
import sqlite3
import subprocess
import threading
import time
import unicodedata
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from mcp.server.transport_security import TransportSecuritySettings

# UN ANALIZADOR MORFOLÓGICO POR HILO, y no uno solo compartido. Snowball guarda estado
# mutable adentro del objeto: usarlo desde dos hilos a la vez corrompe ese estado y sale
# `IndexError: string index out of range` en cualquier palabra, no en una en particular.
#
# NO es una precaución teórica. Antes del 2026-08-08 el índice se construía únicamente al
# arrancar, cuando nadie estaba consultando todavía, así que jamás había dos hilos acá. Desde
# que el índice se reconstruye EN CALIENTE (ver `Planta`) el hilo que reconstruye analiza las
# quinientas sub-entradas mientras el que atiende analiza la pregunta de quien consulta.
# Medido con el servidor bajo carga: la reconstrucción abortaba y, sobre 111 peticiones, una
# de un usuario real devolvía ese mismo error. Reproducible: `producto/probar-recarga-sin-corte.py`.
try:
    import snowballstemmer
    _STEMMERS = threading.local()

    def _stem_por_hilo(palabra: str) -> str:
        s = getattr(_STEMMERS, "st", None)
        if s is None:
            s = _STEMMERS.st = snowballstemmer.stemmer("spanish")
        return s.stemWord(palabra)

    _STEM = _stem_por_hilo
except ImportError:  # sin stemmer se degrada a busqueda exacta, no se cae
    _STEM = None

try:
    import numpy as np
    from model2vec import StaticModel
except ImportError:  # sin capa semantica queda solo la lexica, no se cae
    np = None
    StaticModel = None

# EL MODELO POR OMISIÓN PASÓ DE ESTÁTICO A UN CODIFICADOR REAL. Medido el 2026-08-07 sobre las 81
# preguntas juzgadas, mismo corpus, mismo puntaje, cambiando SOLO la representación:
#
#   estático potion-multilingual-128M   1er 35/81 = 43 %   top-3 43   sin traer el documento 28
#   MiniLM multilingüe (ahora)          1er 37/81 = 45 %   top-3 49   sin traer el documento 20
#   e5-small                            1er 35/81 = 43 %   top-3 47   sin traer el documento 20
#   e5-small con sus prefijos           1er 35/81 = 43 %   top-3 46   sin traer el documento 26
#   e5-base con sus prefijos            1er 34/81 = 41 %   top-3 46   sin traer el documento 28
#
# Por qué importa más de lo que dice el «1er lugar»: quien consulta esta base es cada vez más un
# agente, que puede pedir de nuevo. Medido con esa forma de uso: encuentra el documento en la primera
# consulta el 75 % de las veces (era 65 %) y el 93 % insistiendo (era 83 %).
#
# LO QUE SE PROBÓ Y NO GANÓ, para que nadie lo repita: el modelo más grande (e5-base) es el PEOR de
# los cinco, y los prefijos que e5 pide para su uso canónico EMPEORAN su número en este corpus.
#
# El estático se había elegido por memoria: el contenedor moría a 1,2 GB. Hoy el límite es 2 GB, el
# VPS tiene 4,2 GB libres, y medido en hardware equivalente (2 núcleos) esto cuesta 48 ms por consulta
# y ~30 s de arranque para los 519 vectores. `KB_MODELO` revierte a lo anterior sin tocar código.
MODELO = os.environ.get(
    "KB_MODELO", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# Palabras vacias del castellano. Sin esta lista, una consulta ajena al dominio calzaba por
# piezas gramaticales: "receta de pan de masa madre" traia entradas porque "mas" aparece en
# "más" (el indice normaliza tildes), y "cual es la capital de Francia" por el "cual" de
# "la condicion bajo la cual". El filtro por frecuencia no las atrapa: son comunes en la
# lengua, no en el corpus. Se listan en su forma sin tildes, que es como se normalizan.
VACIAS = frozenset("""
a al algo alguna algunas alguno algunos ante antes aqui asi aun aunque cada como con contra
cual cuales cuando de del desde donde dos e el ella ellas ellos en entre era eran es esa esas
ese eso esos esta estan estas este esto estos ha han hasta hay la las le les lo los mas me
mi mientras mis mucha muchas mucho muchos muy nada ni no nos nuestra nuestro o os otra otras
otro otros para pero poco por porque que quien quienes se sea segun ser si sin sobre solo son
su sus tal tambien tan tanto te tiene tienen todo todos tras un una unas uno unos y ya
""".split())

# --- parseo ------------------------------------------------------------------

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n?", re.S)
WIKILINK = re.compile(r"\[\[([^\[\]|#]+?)(?:#[^\[\]|]*)?(?:\|[^\[\]]*)?\]\]")
PALABRA = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,}")
# Sintaxis de busqueda ESCRITA A PROPOSITO por quien pregunta: comillas, comodin,
# parentesis, booleanos. Los dos puntos estuvieron en esta lista hasta el 2026-07-30 y
# eran un error: en FTS5 `:` filtra por columna, pero en castellano es puntuacion
# corriente, asi que cualquier pregunta con dos puntos se pasaba cruda al indice —con
# sus `¿`, sus comillas angulares y sus tildes— y FTS5 la rechazaba por sintaxis. La
# capa lexica devolvia CERO resultados y nadie se enteraba, porque el error se tragaba
# rio abajo. Medido: 5 de 79 preguntas de la bateria de pertinencia caian por esto.
OPERADORES = re.compile(r'["*()]|\b(AND|OR|NOT|NEAR)\b')
# Marcadores de intencion enumerativa: la respuesta es un indice, no un nodo suelto.
LISTADO = re.compile(r"\b(lista|listar|listado|cuales|cuáles|todos|todas|enumera|"
                     r"que proyectos|qué proyectos|que hay|qué hay|inventario)\b")

# Pregunta definicional: "que es X", "quienes son", "de que trata". Es justo cuando el nodo
# panoramico —el mas conectado— ES la respuesta correcta, asi que se le levanta la penalizacion
# de hub. Sin esto, preguntar "que es esta plataforma" no devolvia la entrada de la plataforma.
DEFINICIONAL = re.compile(r"\b(que es|qué es|que son|qué son|quien es|quién es|quienes son|"
                          r"quiénes son|de que trata|de qué trata|en que consiste|"
                          r"en qué consiste)\b")

# Pesos del orden de resultados (opcion B del plan de pertinencia). Los escribe
# tools/entrenar-ranker.py; embebidos para que viajen con el servidor a cualquier
# despliegue. Vacio = el reordenamiento no opera y el orden queda como siempre.
# NOTA sobre el peso de `centralidad`, fijado en 0 el 2026-07-30 por medición, no por gusto:
# es un prior de popularidad del grafo, y en esta base «Accesos requeridos» está declarada como
# vecina por casi todo, así que ganaba preguntas ajenas —«cómo funciona el cobro», «qué tan
# probada está la plataforma»— con el coseno empatado y sin evidencia léxica. Medido sobre las 81
# preguntas juzgadas, quitarlo mejora 3 de 4: nota correcta servida 29→30%, top-3 55→57, fuera del
# listado 19→17, primer lugar igual. El entrenador lo vuelve a poner positivo porque optimiza
# primer lugar sobre el subconjunto de entrenamiento; si se reentrena, revisar contra esta nota.
RANKER_PESOS = {'kb': 'okos', 'mu': [0.351663, 4.062396, 0.546557, 0.081794, 0.034301, 0.0, 0.542179, 0.94143, 0.100488], 'sigma': [0.126125, 4.938254, 0.252806, 0.236047, 0.182001, 1e-06, 0.23785, 0.115645, 0.135562], 'w': [0.085658, 0.415418, 0.180627, 1.218747, -0.401717, 0.0, 0.0, -0.075452, 0.013916], 'b': -1.938051}

FICHA_CAMPO = re.compile(r"^-\s+\*\*[^*]+:\*\*.*$", re.MULTILINE)


def ficha_pendiente(nodo) -> str:
    """La ficha de campos de una sub-entrada ABIERTA del compromiso.

    Un compromiso se consulta para saber en qué está y a quién espera, y eso vive en
    la ficha —«Estado», «Espera a», «Checkpoint»—, no en la prosa. La ventana del
    extracto la saltaba, y el índice de hermanas la sirve parafraseada, que no es lo
    mismo para quien tiene que actuar. Medido el 2026-07-30: dos casos de la batería
    en rojo por esto, uno de ellos el del Project Manager preguntando qué conseguir.
    Se prefiere una sub-entrada abierta; si no hay, la primera que haya.
    """
    lineas = nodo.cuerpo.split("\n")
    bloques, actual = [], []
    for l in lineas:
        if FICHA_CAMPO.match(l):
            actual.append(l.strip())
        elif actual:
            bloques.append(actual)
            actual = []
    if actual:
        bloques.append(actual)
    if not bloques:
        # Una entrada SIN ficha en el cuerpo la tiene en el encabezado del archivo: son los planes
        # y las preguntas de `en-curso`, un archivo cada uno, escritos por el conducto. Antes esto
        # devolvia vacio y el extracto salia sin un solo campo, asi que quien preguntaba «que esta
        # abierto» recibia prosa sin estado y «que problemas hay» recibia prosa sin tipo. Medido el
        # 2026-08-05: es la causa de los dos casos de la familia INTENCION en rojo, que se venian
        # diagnosticando como un problema de vocabulario o de ventana del extracto.
        m = nodo.meta or {}
        pares = [("Estado", m.get("estado")), ("Tipo", m.get("tipo")),
                 ("Impacto", m.get("impacto")), ("Checkpoint", m.get("checkpoint")),
                 ("Espera a", m.get("espera_a"))]
        campos = [f"- **{k}:** {v}" for k, v in pares if v]
        return " ".join(campos)
    abiertos = [b for b in bloques
                if any("**Estado:**" in x and "abierto" in x.lower() for x in b)]
    elegido = (abiertos or bloques)[0]
    return " ".join(" ".join(elegido).split())


def _subentradas_con_campos(cuerpo: str) -> list[tuple[str, dict]]:
    """(título, campos de su ficha) por cada sub-entrada. Mismo criterio que el portón.

    Existe porque la frescura y el filtrado necesitan los CAMPOS de cada sub-entrada, no solo su
    texto: la retención se declara por tipo de sub-entrada, y ese tipo vive en su ficha.
    """
    fuera = []
    for bloque in re.split(r"(?m)^###\s+", cuerpo)[1:]:
        titulo = bloque.split("\n", 1)[0].strip()
        campos = {}
        for linea in bloque.splitlines()[1:]:
            m = re.match(r"-\s+\*\*([^:*]+):\*\*\s*(.+?)\s*$", linea)
            if m:
                campos[m.group(1).strip()] = m.group(2).strip()
            elif campos and linea.strip():
                break          # la ficha es el bloque contiguo que sigue al título
        fuera.append((titulo, campos))
    return fuera


def subentradas(cuerpo: str) -> list[tuple[str, str]]:
    """Parte una entrada en sus unidades atómicas: (título, texto).

    La primera es la cabecera —todo lo anterior a la primera sub-entrada— que es lo que
    responde «qué es esto». Las demás son las sub-entradas, cada una con su título, su
    ficha de campos y su evidencia. Esta es la unidad sobre la que la base está diseñada
    y sobre la que se recupera desde el 2026-07-30: antes se indexaba la entrada entera
    —hasta 40.000 caracteres— y una sub-entrada corta y precisa no podía ganarle a la
    dilución de la frecuencia de términos.
    """
    partes = re.split(r"(?m)^### ", cuerpo)
    salida = [("", partes[0])]
    for sub in partes[1:]:
        titulo = sub.split("\n", 1)[0].strip()
        salida.append((titulo, sub))
    return salida


LIMITE_DECLARADO = re.compile(r"(?:\*\*)?Por confirmar[^\n]*", re.IGNORECASE)


def limite_declarado(nodo) -> str:
    """El «Por confirmar…» que la entrada declara en su RESUMEN.

    La regla de la casa dice que el límite va arriba, y la prosa la cumple. Pero el
    extracto no empieza arriba: es una ventana centrada en el pasaje que mejor calza,
    así que un límite escrito en «Qué es» no llegaba nunca al lector cuando el acierto
    caía en una sub-entrada. Medido el 2026-07-30: dos casos de la batería en rojo por
    esto, con la prosa correcta. Se sirve el límite por mecanismo en vez de pedirle a
    cada nota que lo repita.
    """
    m = re.search(r"##\s*Qué es(.*?)(?=\n##\s|\Z)", nodo.cuerpo, re.S)
    zona = m.group(1) if m else nodo.cuerpo[:1500]
    hit = LIMITE_DECLARADO.search(zona)
    return " ".join(hit.group(0).split()) if hit else ""


def links_de_padre(nodo) -> set:
    """Nombres que el nodo declara como su padre (`depende_de`). Sirve para detectar
    hubs: si muchas entradas declaran a la misma como padre, esa es un índice de hecho
    aunque su nombre no coincida con el del directorio."""
    v = nodo.meta.get("depende_de")
    if not v:
        return set()
    crudo = v if isinstance(v, list) else [v]
    return {x.strip() for c in crudo for x in WIKILINK.findall(str(c))}


CAMPOS_GRAFO = ("depende_de", "se_descompone_en", "se_relaciona_con")
NO_POLO = {"assets", ".obsidian", ".trash"}


# LA FICHA DE CADA SUB-ENTRADA, FUERA DEL TEXTO QUE SE VECTORIZA — perilla, apagada por omisión.
#
# La hipótesis es de Martín, 2026-08-07: la recuperación no se degradó solo por volumen, sino por
# «todos los campos y parámetros que le fuimos agregando». Es medible y era razonable a priori: cada
# sub-entrada arranca con cinco líneas de ficha —estado, tipo, verificado, publicable, impacto— que
# son IDÉNTICAS entre las quinientas y pico sub-entradas del corpus, así que empujan todos los
# vectores hacia un mismo centro y achatan la discriminación justo a medida que la base crece.
#
# `KB_SIN_FICHA=1` las saca del texto que se vectoriza. No las saca de la base ni de la respuesta:
# se siguen sirviendo y se sigue filtrando por ellas — lo único que cambia es qué se le da al modelo
# de embeddings. El resultado de medirlo queda escrito acá abajo cuando esté.
_LINEA_DE_FICHA = re.compile(r"(?m)^\s*-\s*\*\*[A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]{3,20}:\*\*.*$")


def _es_modelo_estatico(nombre: str) -> bool:
    """¿El modelo configurado es una tabla estática (model2vec) o un codificador?"""
    return "potion" in nombre or "model2vec" in nombre or nombre.startswith("/")


def _umbral_aviso() -> float:
    """El corte de cercanía del AVISO, ATADO AL MODELO. Ver la calibración abajo.

    UNA ESCALA DE SIMILITUD NO VIAJA ENTRE MODELOS, y esto costó descubrirlo con la batería en la
    mano: al cambiar el codificador, el 0,32 calibrado para el modelo estático dejó de significar lo
    mismo y la base pasó a servir seis resultados de relleno ante «qué se le pone al mate para que no
    amargue» SIN avisar. Medido el 2026-08-07 sobre 9 preguntas ajenas y las 81 juzgadas:

        modelo estático, 0,32   →  avisa 7 de 9 ajenas  ·  3 avisos falsos de 81
        MiniLM,          0,32   →  avisa 5 de 9         ·  7 falsos
        MiniLM,          0,42   →  avisa 7 de 9         ·  9 falsos
        MiniLM,          0,45   →  avisa 7 de 9         ·  10 falsos

    Las dos distribuciones se SOLAPAN con MiniLM —las ajenas llegan a 0,408 y las legítimas bajan a
    0,162—, así que ningún número las separa solo: lo que separa es la conjunción con la señal
    léxica. Se elige 0,45 y no 0,42, que da el mismo 7 de 9: los 0,04 de más son margen contra que
    el corpus mueva la escala, y cuestan un aviso falso. Un aviso falso deja los resultados intactos
    debajo; una pregunta ajena sin aviso se sirve como si fuera respuesta.

    EL VALOR SE DERIVA DEL MODELO Y NO SE ESCRIBE FIJO, a propósito: `KB_MODELO` es la reversión de
    todo este cambio, y un umbral que se quedara en 0,45 dejaría el modelo viejo peor calibrado que
    antes —revertir habría empeorado algo, en silencio—. `KB_AVISO` sigue estando para volver a
    medirlo cuando el corpus mueva la escala otra vez.
    """
    fijo = os.environ.get("KB_AVISO")
    if fijo:
        return float(fijo)
    return 0.32 if _es_modelo_estatico(MODELO) else 0.45


# Las claves que este proceso vio en CUALQUIERA de sus índices. Ver `_vectorizar_con_cache`.
_CLAVES_VIVAS: set[str] = set()


def _vectorizar_con_cache(modelo, textos: list[str]):
    """Calcula los vectores, reusando los que ya se calcularon para un texto idéntico.

    POR QUÉ, con el número que lo hizo obligatorio. El índice se reconstruye AL ARRANCAR, y el
    contenedor se reinicia cada vez que el contenido cambia —`sync-kb.sh` mira cada 15 minutos y
    reinicia si hubo commit—. Con la tabla estática eso era instantáneo. Con un codificador de verdad
    cuesta ~30 s en el hardware del VPS, y el 2026-08-07 hubo **28 reinicios en un día**: serían
    catorce minutos diarios de servicio caído, en tandas de medio minuto, mientras alguien pregunta.

    Un reinicio típico cambia una o dos sub-entradas de quinientas. Cacheando por el HASH DEL TEXTO,
    el arranque recalcula solo lo que cambió y vuelve a costar un segundo.

    Degrada bien a propósito: si `KB_VECTORES` no está o no se puede escribir —hoy el contenedor va
    en modo lectura y no tiene volumen para esto— se comporta exactamente como antes, recalculando
    todo. O sea que este código es seguro de desplegar ANTES que el volumen, y el volumen es una
    mejora separada que se puede revisar aparte.
    """
    ruta = os.environ.get("KB_VECTORES")
    clave = lambda t: hashlib.sha256((MODELO + "\x00" + t).encode("utf-8")).hexdigest()
    # LAS CLAVES SE ACUMULAN ENTRE ÍNDICES, y sin esto el caché servía para UNA sola base.
    # Al guardar se conserva «solo lo que el índice usa hoy», para que el archivo no crezca con
    # cada texto que existió alguna vez. Correcto con una KB; con TRES en el mismo proceso, cada
    # una guardaba únicamente sus claves y borraba las de las otras dos, así que el arranque
    # recalculaba dos bases enteras siempre. Medido el 2026-08-08: el archivo quedaba con las
    # claves de la última base indexada y ninguna más. Acumulando en el proceso, las tres
    # sobreviven y la poda sigue existiendo — lo que se descarta es lo que ya no usa NINGUNA.
    previo: dict[str, "np.ndarray"] = {}
    if ruta:
        try:
            with np.load(ruta, allow_pickle=False) as z:
                previo = {k: z[k] for k in z.files}
        except Exception:
            previo = {}
    claves = [clave(t) for t in textos]
    faltan = [i for i, k in enumerate(claves) if k not in previo]
    if faltan:
        nuevos = modelo.encode([textos[i] for i in faltan])
        for j, i in enumerate(faltan):
            previo[claves[i]] = np.asarray(nuevos[j], dtype="float32")
    V = np.stack([previo[k] for k in claves]).astype("float32")
    if ruta and faltan:
        try:
            # Solo lo que el índice usa hoy: si no, el archivo crece con cada texto que existió
            # alguna vez y el arranque se lo lee entero para nada.
            # SE ESCRIBE POR DESCRIPTOR, no por nombre: `np.savez` le agrega «.npz» a un nombre que
            # no lo tenga, así que el temporal terminaba en otro archivo y el `replace` fallaba —
            # silenciosamente, porque este bloque traga excepciones. Medido: dos arranques seguidos
            # costaban lo mismo y el caché no existía.
            _CLAVES_VIVAS.update(claves)
            tmp = ruta + ".nuevo"
            with open(tmp, "wb") as fh:
                np.savez(fh, **{k: previo[k] for k in _CLAVES_VIVAS if k in previo})
            os.replace(tmp, ruta)
        except Exception:
            pass
    return V


def _para_vector(sub: str) -> str:
    if os.environ.get("KB_SIN_FICHA") != "1":
        return sub
    return _LINEA_DE_FICHA.sub("", sub)


def normalizar(palabra: str) -> str:
    desc = unicodedata.normalize("NFD", palabra.lower())
    return "".join(c for c in desc if unicodedata.category(c) != "Mn")


def raiz(palabra: str) -> str:
    base = normalizar(palabra)
    # Se probo colapsar los diptongos (ue→o, ie→e) para reunificar prueba/probar — y empeoro
    # el caso que queria arreglar: «qué tan probada está la plataforma» paso a calzar con TODO
    # lo que dice "pruebas", y el plan «Conectar las pruebas…» le gano a la entrada del
    # subsistema (posicion 3 → 5, medido A/B el 2026-07-27). Misma leccion que la exencion de
    # hubs que este archivo ya documenta: ajustar el ranking sin una escala de relevancia
    # calibrada es prueba y error, y la red de regresion es quien decide. No reintentar a ciegas.
    return _STEM(base) if _STEM else base


def _wikilinks(valor) -> list[str]:
    if not valor:
        return []
    crudos = valor if isinstance(valor, list) else [valor]
    salida = []
    for item in crudos:
        if not isinstance(item, str):
            continue
        encontrados = WIKILINK.findall(item)
        salida.extend(n.strip() for n in (encontrados or [item]) if n.strip())
    return salida


# --- configuracion por KB ----------------------------------------------------

@dataclass
class ConfigKB:
    """Todo lo especifico del dominio vive aca, y se lee del repo de la KB."""
    slug: str
    nombre: str
    descripcion: str
    polos: dict[str, str]          # directorio -> etiqueta legible
    alias: dict[str, str]          # alias en minusculas -> directorio
    # Niveles de acceso declarados por la KB. Opcional: sin `niveles`, la KB se
    # sirve entera en su ruta de siempre y nada cambia (el caso de toda KB que no
    # opte por esto). Cada nivel se nombra por lo que HACE, no por quien lo usa:
    #   nombre_nivel: {campo, valor, herramientas, etiqueta}
    # `campo`/`valor` seleccionan que entradas entran (por un campo del frontmatter
    # que la propia KB define); `herramientas` acota que herramientas se registran.
    # El servidor no sabe que significa ninguno de esos valores: solo compara.
    niveles: dict[str, dict] = field(default_factory=dict)
    # Calendario de re-verificacion por tipo (dias). Opcional. Si una entrada de un
    # tipo listado lleva `verificado: YYYY-MM-DD` mas viejo que su plazo, el servidor
    # lo declara junto a la fuente en cada resultado — el lector (una IA) ve la
    # frescura sin que nadie tenga que editar el archivo. Comparacion de fechas pura:
    # el juicio de si la entrada SIGUE siendo verdad es de la calibracion, no de aqui.
    retencion: dict[str, int] = field(default_factory=dict)
    # Tipos cuyo archivo es un CONTENEDOR: su contenido son las sub-entradas, y cada una es una
    # instancia del tipo. Los demas tipos SON la unidad, y sus secciones son partes de ella. El
    # servidor no sabe que significa ninguno de estos nombres: solo compara. Vacio = ningun tipo
    # se hereda a las secciones, que es el comportamiento de toda KB que no declare esto.
    tipos_contenedores: list[str] = field(default_factory=list)
    # DOCUMENTOS DE FUERA DE `knowledge-base/` QUE TAMBIÉN SE INDEXAN. Opcional y vacío por omisión,
    # que es el comportamiento de toda KB que no lo declare.
    #
    # Por qué existe: las REGLAS que gobiernan una base viven en su documentación, no en su corpus,
    # así que la base recuerda sus defectos y no su criterio. Cuatro iteraciones de evaluación chocaron
    # con lo mismo: el sistema que decide qué trabajo tomar no puede leer el criterio con que se
    # decide. Se indexan con `publicable: false` forzado — son instrumentales por definición y no
    # escalan a dirección.
    documentos_extra: list[str] = field(default_factory=list)

    @classmethod
    def desde(cls, ruta: Path) -> "ConfigKB":
        base = ruta / "knowledge-base"
        dirs = sorted(d.name for d in base.iterdir() if d.is_dir() and d.name not in NO_POLO)

        cfg = {}
        archivo = ruta / "kb" / "mcp.yaml"
        if archivo.is_file():
            try:
                cfg = yaml.safe_load(archivo.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                cfg = {}

        polos_cfg = cfg.get("polos") or {}
        polos, alias = {}, {}
        for d in dirs:
            entrada = polos_cfg.get(d) or {}
            if isinstance(entrada, str):
                entrada = {"etiqueta": entrada}
            polos[d] = entrada.get("etiqueta") or d
            alias[normalizar(entrada.get("alias") or d)] = d
            alias[normalizar(d)] = d

        extra = [str(x) for x in (cfg.get("documentos_extra") or [])]
        niveles = cfg.get("niveles") or {}
        if not isinstance(niveles, dict):
            niveles = {}
        retencion = cfg.get("retencion") or {}
        if not isinstance(retencion, dict):
            retencion = {}
        retencion = {t: int(d) for t, d in retencion.items()
                     if isinstance(d, (int, float)) and int(d) > 0}

        return cls(
            slug=cfg.get("slug") or ruta.name,
            nombre=cfg.get("nombre") or ruta.name,
            descripcion=cfg.get("descripcion") or "",
            polos=polos,
            alias=alias,
            niveles=niveles,
            retencion=retencion,
            tipos_contenedores=[str(t).strip().lower()
                                for t in (cfg.get("tipos_contenedores") or [])],
            documentos_extra=extra,
        )


SECCION = re.compile(r"^##\s+(.+?)\s*$", re.M)


@dataclass
class Nodo:
    nombre: str
    ruta: str
    polo: str
    cuerpo: str
    meta: dict
    enlaces: dict[str, list[str]] = field(default_factory=dict)
    menciona: list[str] = field(default_factory=list)
    modificado: int = 0   # timestamp del ultimo commit que toco el archivo (git)
    modificado_iso: str = ""   # su fecha EN LA ZONA DEL AUTOR: la que el autor vio al commitear
    creado: int = 0       # timestamp del primer commit
    es_indice: bool = False  # Directory Index Node (§R3): stem == nombre del directorio

    def seccion(self, titulo: str) -> str:
        """Devuelve el cuerpo de una seccion H2 (p.ej. 'Inventario'), o cadena vacia."""
        m = re.search(rf"^##\s+{re.escape(titulo)}\s*$", self.cuerpo, re.M | re.I)
        if not m:
            return ""
        resto = self.cuerpo[m.end():]
        sig = SECCION.search(resto)
        return (resto[:sig.start()] if sig else resto).strip()


def _commits_sin_crecimiento(raiz: Path, entorno: dict) -> list[str]:
    """Los commits que NO agregaron contenido: reescrituras, renombres, barridos de vocabulario.

    POR QUÉ, y es el defecto que invalidaba la capacidad entera. La primera versión tomaba el
    último toque de cualquier línea como «cuándo creció». No es lo mismo. El 2026-08-08 un barrido
    de vocabulario —«corrida» pasa a «iteración» en 55 entradas— hizo que todas esas sub-entradas
    declararan haber crecido a las 21:49, y preguntar «qué pasó en la última hora» devolvió 262
    secciones: casi la base entera. Con más confianza que antes de tener la capacidad.

    La corrección la tenía escrita el propio encargo y no se leyó bien: Martín dijo «ver qué
    porciones han CRECIDO», y eso en un diff es el verde, no el amarillo. Un commit que sustituye
    una palabra tiene tantas líneas agregadas como borradas; uno que agrega una nota, no. Así que
    se ignoran los que no dejan saldo positivo en el archivo, y la autoría de esas líneas vuelve a
    su commit anterior — que es exactamente cuándo el contenido apareció.
    """
    try:
        salida = subprocess.run(
            ["git", "-C", str(raiz), "-c", "core.quotepath=false", "-c", "safe.directory=*",
             "log", "--format=%x00%H", "--numstat", "--no-renames", "--", "knowledge-base"],
            capture_output=True, text=True, timeout=60, check=True, env=entorno).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    ignorar, commit, saldo = [], None, 0
    for linea in salida.split("\n"):
        if linea.startswith("\x00"):
            if commit and saldo <= 0:
                ignorar.append(commit)
            commit, saldo = linea[1:].strip(), 0
        elif linea.strip() and commit:
            campos = linea.split("\t")
            if len(campos) >= 2 and campos[0].isdigit() and campos[1].isdigit():
                saldo += int(campos[0]) - int(campos[1])
    if commit and saldo <= 0:
        ignorar.append(commit)
    return ignorar


def fechas_subentrada(raiz: Path) -> tuple[dict[str, dict[str, int]], dict]:
    """Cuándo CRECIÓ por última vez cada sub-entrada, derivado del historial línea por línea.

    Devuelve (mapa, diagnóstico). El diagnóstico no es adorno: la primera versión degradaba MUDA
    —el 41 % de las sub-entradas se quedaba sin fecha y el sistema reportaba igual que si
    funcionara entero—, y eso es peor que no tener la capacidad, porque nadie sale a buscar lo que
    no se queja. Ahora se cuenta y se publica en `/salud`.

    POR QUÉ HACE FALTA. `fechas_git()` da UNA fecha por ARCHIVO, y las entradas de esta base tienen
    hasta 70 sub-entradas: todas reciben la misma marca aunque las separen días. Con del orden de
    setenta publicaciones diarias, «qué se hizo hoy en la tarde» devuelve cincuenta cosas sin orden
    interno.

    EL MÉTODO ES DE MARTÍN: «ver qué porciones de un documento han crecido antes que otras, similar
    al mecanismo del DIFF». Una atribución línea por línea POR ARCHIVO —no una búsqueda del
    historial por sub-entrada—, ignorando los commits que no agregaron nada (ver arriba).

    NO SALE A LA RED. `GIT_NO_LAZY_FETCH=1`: sobre un clon sin contenidos históricos el blame
    fallaría pidiéndolos de a uno —2 s por archivo, 411 archivos, el arranque no termina— así que
    tiene prohibido intentarlo y falla en el acto. Más un techo de tiempo como segunda línea.
    """
    base = raiz / "knowledge-base"
    diag = {"archivos": 0, "con_fecha": 0, "sin_fecha": 0, "ignorados": 0, "segundos": 0.0}
    if os.environ.get("KB_FECHA_SUBENTRADA", "0") not in ("1", "si", "sí", "true"):
        diag["apagada"] = True
        return {}, diag

    entorno = dict(os.environ, GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
    try:
        archivos = [(str(f.relative_to(raiz)), str(f.relative_to(base)))
                    for f in sorted(base.rglob("*.md"))]
    except OSError:
        return {}, diag
    diag["archivos"] = len(archivos)

    t0 = time.monotonic()
    ignorar = _commits_sin_crecimiento(raiz, entorno)
    diag["ignorados"] = len(ignorar)
    ruta_ignorar = None
    if ignorar:
        with contextlib.suppress(OSError):
            import tempfile
            fh = tempfile.NamedTemporaryFile("w", suffix=".revs", delete=False)
            fh.write("\n".join(ignorar) + "\n"); fh.close()
            ruta_ignorar = fh.name

    techo = float(os.environ.get("KB_TECHO_BLAME_S", "90"))
    fuera: dict[str, dict[str, int]] = {}
    for n_arch, (r, clave) in enumerate(archivos):
        if time.monotonic() - t0 > techo:
            print(f"[kb-mcp] {raiz.name}: la fecha por sub-entrada pasó el techo de {techo:.0f}s "
                  f"con {n_arch} de {len(archivos)} archivos.", file=sys.stderr, flush=True)
            break
        orden = ["git", "-C", str(raiz), "-c", "core.quotepath=false", "-c", "safe.directory=*",
                 "blame", "--line-porcelain"]
        if ruta_ignorar:
            orden += [f"--ignore-revs-file={ruta_ignorar}"]
        try:
            salida = subprocess.run(orden + ["--", r], capture_output=True, text=True,
                                    timeout=20, check=True, env=entorno).stdout
        except (subprocess.SubprocessError, OSError):
            continue
        actual, titulo = 0, None
        por_titulo: dict[str, int] = {}
        for linea in salida.split("\n"):
            if linea.startswith("author-time "):
                actual = int(linea.split(" ", 1)[1])
            elif linea.startswith("\t"):
                texto = linea[1:]
                if texto.startswith("### "):
                    titulo = texto[4:].strip()
                if titulo is not None and actual > por_titulo.get(titulo, 0):
                    por_titulo[titulo] = actual
        if por_titulo:
            fuera[clave] = por_titulo
    if ruta_ignorar:
        with contextlib.suppress(OSError):
            os.unlink(ruta_ignorar)
    # SE CUENTAN SUB-ENTRADAS, NO ARCHIVOS, y la diferencia no es cosmética: contando archivos, un
    # plan de una sola pieza —que no tiene sub-entradas y por eso no aparece acá— se anotaba como
    # «sin fecha» y ensuciaba el número, mientras que un archivo con 70 sub-entradas cuya autoría
    # falla contaba como UNO. O sea que el indicador podía mostrarse mal estando bien, y bien
    # estando mal. La unidad del problema es la sub-entrada: se cuenta esa.
    esperadas = 0
    for r, clave in archivos:
        with contextlib.suppress(OSError):
            esperadas += sum(1 for l in (base / clave).read_text(
                encoding="utf-8", errors="replace").splitlines() if l.startswith("### "))
    logradas = sum(len(v) for v in fuera.values())
    diag["segundos"] = round(time.monotonic() - t0, 2)
    diag["subentradas"] = esperadas
    diag["con_fecha"] = logradas
    diag["sin_fecha"] = max(0, esperadas - logradas)
    if esperadas and logradas < esperadas:
        print(f"[kb-mcp] {raiz.name}: la fecha por sub-entrada alcanzó a "
              f"{logradas} de {esperadas} ({100*logradas//esperadas} %). Las que faltan usan la "
              f"fecha del archivo. Causa habitual: contenidos históricos ausentes del clon — "
              f"`git -C <kb> fetch --refetch origin <rama>`.", file=sys.stderr, flush=True)
    return fuera, diag


def fechas_git(raiz: Path, base: Path) -> dict[str, tuple[int, int]]:
    """Por cada .md, (primer commit, ultimo commit) segun git. La temporalidad de
    un grafo que crece vive en su historial, no en el frontmatter. Un solo `git log`
    recorre todo: O(commits), no O(archivos*commits). Devuelve {} si no hay historial
    (p.ej. clon shallow) para degradar a orden alfabetico sin fallar."""
    try:
        # `core.quotepath=false` NO es cosmético: sin él git entrecomilla y escapa toda ruta con un
        # carácter no ASCII —`"knowledge-base/comprobado/Autenticaci\303\263n….md"`—, el filtro por
        # sufijo `.md` de más abajo la descarta, y esa entrada queda sin fecha. Medido el 2026-08-05
        # en esta base: 38 de 70 archivos sin fecha, y eran EXACTAMENTE los 38 con tilde o ñ en el
        # nombre. En castellano eso no es un caso borde: es más de la mitad del corpus. Y con la
        # fecha se apaga todo lo que cuelga de ella —la ficha que dice cuándo se actualizó una
        # entrada, el orden por reciente y el multiplicador de recencia del ranking—, que es
        # justamente lo que haría que un hecho de hoy le gane a un plan de anteayer.
        # `safe.directory=*` previene el modo de falla que seguiría al instalar git en el contenedor:
        # git se niega a operar en un repositorio cuyo dueño es otro usuario —«detected dubious
        # ownership»— y en un contenedor eso es lo normal, no la excepción. Va en la invocación y no
        # en un archivo de configuración a propósito: así no depende de qué usuario corre el proceso
        # ni de que alguien se acuerde de configurar la imagen. El degradado de esta función es
        # silencioso, así que un rechazo de git acá se vería igual que no tener historial: nada.
        salida = subprocess.run(
            ["git", "-C", str(raiz), "-c", "core.quotepath=false",
             "-c", "safe.directory=*",
             # `%ad --date=short` es la fecha QUE EL AUTOR VIO, ya en su zona. El epoch de `%at` es
             # UTC y sirve para ordenar, pero formatearlo con la zona del proceso corre el día: el
             # contenedor corre en UTC y Martín commitea en UTC−4, así que a 19 de 75 entradas el
             # servidor les mostraba la fecha del día SIGUIENTE —todo lo escrito después de las ocho
             # de la tarde—. Medido el 2026-08-06. Se traen las dos: una para ordenar y otra para
             # decir. Separadas por tabulación porque ningún nombre de archivo la lleva.
             "log", "--format=%at%x09%ad", "--date=short", "--name-only",
             "--no-renames", "--", "knowledge-base"],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return {}

    fechas: dict[str, tuple[int, int, str]] = {}
    ts, iso = 0, ""
    for linea in salida.splitlines():
        linea = linea.strip()
        if "\t" in linea and linea.split("\t", 1)[0].isdigit():
            crudo, _, iso = linea.partition("\t")
            ts, iso = int(crudo), iso.strip()
        elif linea.isdigit():          # historial sin la fecha (formato viejo): se sigue ordenando
            ts, iso = int(linea), ""
        elif linea.endswith(".md") and ts:
            try:
                rel = str(Path(linea).relative_to("knowledge-base"))
            except ValueError:
                continue
            prev = fechas.get(rel)
            # Se recorre de mas nuevo a mas viejo: primer avistamiento = ultimo commit.
            if prev is None:
                fechas[rel] = (ts, ts, iso)
            else:
                fechas[rel] = (ts, prev[1], prev[2])
    return fechas


SUB_H = re.compile(r"^(##|###)\s+(.+?)\s*$", re.M)
FICHA = re.compile(r"^-\s+\*\*([^:*]+):\*\*\s*(.+?)\s*$", re.M)


def _coercer(v):
    """Lleva el valor de una ficha al mismo terreno que el que declara el nivel. El
    frontmatter escribe booleanos y la ficha escribe palabras; sin esto «no» nunca seria
    distinto de `True` y el recorte no haria nada."""
    t = str(v).strip().lower().rstrip(".")
    if t in ("si", "s\u00ed", "yes", "true", "1"):
        return True
    if t in ("no", "false", "0"):
        return False
    return t


def recortar_subentradas(cuerpo: str, campo: str, valor) -> str:
    """Quita las sub-entradas cuya ficha declara `campo` con un valor distinto de `valor`.

    Una entrada agrupa un sujeto entero, asi que puede mezclar contenido de distinta
    visibilidad. El nivel restringido decide por ARCHIVO; cada sub-entrada puede declarar
    la suya. Sin este recorte ese campo es decorativo: se escribe «no» y el contenido
    llega igual — que es exactamente lo que se midio el 2026-07-27, con un hallazgo
    interno servido entero al nivel de direccion.

    Quien NO declara el campo se queda: hereda la visibilidad de su entrada. Eso es lo
    que hace el recorte compatible con todo lo escrito antes de que el campo existiera.

    Caen tambien los titulos de seccion que quedan sin nada debajo: una seccion vacia
    delata por su solo nombre que ahi habia algo que no se muestra.
    """
    cabeceras = list(SUB_H.finditer(cuerpo))
    if not cabeceras:
        return cuerpo
    fuera: list[tuple[int, int]] = []
    for i, m in enumerate(cabeceras):
        if m.group(1) != "###":
            continue
        fin = cabeceras[i + 1].start() if i + 1 < len(cabeceras) else len(cuerpo)
        campos = {k.strip().lower(): v for k, v in FICHA.findall(cuerpo[m.start():fin])}
        declarado = campos.get(campo.strip().lower())
        if declarado is not None and _coercer(declarado) != _coercer(valor):
            fuera.append((m.start(), fin))
    for ini, fin in reversed(fuera):
        cuerpo = cuerpo[:ini] + cuerpo[fin:]
    while True:
        cabeceras = list(SUB_H.finditer(cuerpo))
        vacia = next((m for i, m in enumerate(cabeceras)
                      if m.group(1) == "##"
                      and not cuerpo[m.end():(cabeceras[i + 1].start()
                                              if i + 1 < len(cabeceras)
                                              else len(cuerpo))].strip()), None)
        if vacia is None:
            return cuerpo.rstrip() + "\n"
        sig = next((c.start() for c in cabeceras if c.start() > vacia.start()), len(cuerpo))
        cuerpo = cuerpo[:vacia.start()] + cuerpo[sig:]


# El polo con que se agrupan los documentos de reglas. No es un directorio del corpus: es una
# etiqueta, para que `panorama` no los mezcle con los subsistemas y para que quien lea sepa que está
# viendo el criterio y no un hecho sobre la plataforma.
POLO_REGLAS = "reglas"


class Indice:
    def __init__(self, ruta: Path, modelo=None):
        self.raiz = ruta.expanduser().resolve()
        self.base = self.raiz / "knowledge-base"
        if not self.base.is_dir():
            raise SystemExit(f"No existe {self.base} — ¿es una KB de kb-template?")
        self.cfg = ConfigKB.desde(self.raiz)
        self.modelo = modelo
        self.nodos: dict[str, Nodo] = {}
        self.backlinks: dict[str, set[str]] = {}
        self.vocabulario: dict[str, set[str]] = {}
        self.formas: set[str] = set()
        self.frecuencia: dict[str, float] = {}
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.construir()

    def construir(self) -> None:
        self.nodos.clear(); self.backlinks.clear()
        self.vocabulario.clear(); self.formas.clear()
        fechas = fechas_git(self.raiz, self.base)
        # La marca de tiempo POR SUB-ENTRADA, derivada del historial. Ver `fechas_subentrada`:
        # la del archivo no alcanza porque una entrada de esta base tiene decenas de notas.
        self.fechas_sub, self.diag_fechas_sub = fechas_subentrada(self.raiz)

        for ruta in sorted(self.base.rglob("*.md")):
            texto = ruta.read_text(encoding="utf-8", errors="replace")
            meta: dict = {}
            if m := FRONTMATTER.match(texto):
                try:
                    meta = yaml.safe_load(m.group(1)) or {}
                except yaml.YAMLError:
                    meta = {}
                cuerpo = texto[m.end():]
            else:
                cuerpo = texto
            if isinstance(meta, dict) and meta.get("retirado") is True:
                # Retirada: fuera de servicio con etiqueta. No se indexa en NINGUN
                # nivel; git conserva el archivo y su historia. Es la disposicion
                # final del ciclo de curaduria, no un borrado.
                continue
            rel = ruta.relative_to(self.base)
            creado, modificado, modificado_iso = fechas.get(str(rel), (0, 0, ""))
            # Directory Index Node: el nodo que representa una carpeta y enumera a sus
            # hijos. Dos convenciones validas, ambas presentes en KB reales:
            #  (a) dentro de la carpeta —motor/Motor.md (§R3 estricto);
            #  (b) hermano de la carpeta —Contexto.md junto a Contexto/ (folder-note).
            es_indice = (len(rel.parts) >= 2 and ruta.stem.lower() == ruta.parent.name.lower()) \
                or (ruta.parent / ruta.stem).is_dir()
            nodo = Nodo(
                nombre=ruta.stem,
                ruta=str(rel),
                polo=rel.parts[0] if len(rel.parts) > 1 else "(raiz)",
                cuerpo=cuerpo,
                meta=meta if isinstance(meta, dict) else {},
                enlaces={c: _wikilinks(meta.get(c)) for c in CAMPOS_GRAFO},
                menciona=sorted({n.strip() for n in WIKILINK.findall(cuerpo)}),
                creado=creado,
                modificado=modificado,
                modificado_iso=modificado_iso,
                es_indice=es_indice,
            )
            self.nodos[nodo.nombre] = nodo

        # LOS DOCUMENTOS DECLARADOS FUERA DEL CORPUS, si la KB los pidió. Entran como nodos de un
        # polo propio y con `publicable: false` FORZADO —no leído de su frontmatter, que no tienen—
        # porque son las reglas del instrumental y no escalan a dirección.
        #
        # Se les fuerza además `tipo: regla`, así se pueden pedir por propiedad: la pregunta «con qué
        # criterio se decide qué entra» pasa a tener respuesta exacta y no solo semántica.
        for rel_extra in self.cfg.documentos_extra:
            ruta = self.raiz / rel_extra
            if not ruta.is_file():
                continue
            texto = ruta.read_text(encoding="utf-8", errors="replace")
            cuerpo = texto[m.end():] if (m := FRONTMATTER.match(texto)) else texto
            creado, modificado, modificado_iso = fechas_git(self.raiz, ruta.parent).get(
                ruta.name, (0, 0, ""))
            nodo = Nodo(
                nombre=ruta.stem, ruta=rel_extra, polo=POLO_REGLAS, cuerpo=cuerpo,
                meta={"publicable": False, "tipo": "regla", "estado": "vigente"},
                enlaces={c: [] for c in CAMPOS_GRAFO},
                menciona=sorted({n.strip() for n in WIKILINK.findall(cuerpo)}),
                creado=creado, modificado=modificado, modificado_iso=modificado_iso,
                es_indice=False,
            )
            self.nodos[nodo.nombre] = nodo

        for nodo in self.nodos.values():
            destinos = {d for ds in nodo.enlaces.values() for d in ds} | set(nodo.menciona)
            for destino in destinos:
                if destino in self.nodos and destino != nodo.nombre:
                    self.backlinks.setdefault(destino, set()).add(nodo.nombre)

        self._vocabulario()
        self._fts()
        self._semantica()

    # -- morfologia y estadistica del corpus -----------------------------------

    def _vocabulario(self) -> None:
        """Agrupa palabras por raiz y mide en cuantas entradas aparece cada una.
        Esa frecuencia decide que terminos no discriminan — sin listas escritas a
        mano, y recalculada por KB: «Estado» es palabra vacia en un corpus
        regulatorio chileno y puede no serlo en otro."""
        docs_por_raiz: dict[str, set[str]] = {}
        for nombre, nodo in self.nodos.items():
            for palabra in PALABRA.findall(nodo.nombre + " " + nodo.cuerpo):
                forma = normalizar(palabra)
                if not forma:
                    continue
                r = raiz(palabra)
                self.vocabulario.setdefault(r, set()).add(forma)
                self.formas.add(forma)
                docs_por_raiz.setdefault(r, set()).add(nombre)
        total = max(len(self.nodos), 1)
        self.frecuencia = {r: len(d) / total for r, d in docs_por_raiz.items()}

    def expandir(self, consulta: str) -> str:
        if OPERADORES.search(consulta):
            return consulta
        terminos = [t for t in PALABRA.findall(consulta) if normalizar(t) not in VACIAS]
        utiles = [t for t in terminos if self.frecuencia.get(raiz(t), 0.0) <= 0.5] or terminos
        grupos = []
        for termino in utiles:
            base = normalizar(termino)
            formas = self.vocabulario.get(raiz(termino), set()) | {base}
            if base not in self.formas and len(formas) == 1:
                grupos.append(f'"{base}"*')
                continue
            grupos.append("(" + " OR ".join(f'"{f}"' for f in sorted(formas)) + ")")
        # OR + BM25: los terminos raros pesan por su IDF. Con AND, una pregunta larga
        # solo sobrevivia en los textos legales extensos, que no responden nada.
        if grupos:
            return " OR ".join(grupos)
        # Sin grupos no se devuelve la consulta cruda: llevaria `¿`, `«`, `?` y demas
        # puntuacion que FTS5 rechaza. Se entrecomillan sus palabras, que es siempre
        # sintaxis valida; si no hay ninguna, se devuelve una consulta valida que no
        # calza con nada, para que la capa lexica aporte cero en vez de reventar.
        palabras = [normalizar(t) for t in PALABRA.findall(consulta)]
        return " OR ".join(f'"{p}"' for p in palabras) if palabras else '""'

    def _fts(self) -> None:
        db = self.db
        db.executescript("DROP TABLE IF EXISTS docs;")
        # Sin 'porter': ese stemmer es solo ingles. La morfologia espanola se resuelve
        # expandiendo la consulta, no ensuciando el indice.
        db.execute(
            "CREATE VIRTUAL TABLE docs USING fts5("
            "  nombre, cuerpo, polo UNINDEXED,"
            "  tokenize='unicode61 remove_diacritics 2')"
        )
        db.executemany(
            "INSERT INTO docs (nombre, cuerpo, polo) VALUES (?,?,?)",
            [(n.nombre, n.cuerpo, n.polo) for n in self.nodos.values()],
        )
        # Y el MISMO corpus partido en sub-entradas. Recuperar sobre lo chico y devolver
        # lo grande («small-to-big»): la relevancia se decide en la unidad atómica, donde
        # la frecuencia de términos significa algo, y la respuesta se sirve con su entrada
        # padre. Medido el 2026-07-30: con el índice solo por entrada, 21 de 81 preguntas
        # juzgadas no traían la entrada correcta en ninguna posición — falla de generación
        # de candidatos, que ningún ajuste de pesos puede arreglar.
        db.executescript("DROP TABLE IF EXISTS subdocs;")
        db.execute(
            "CREATE VIRTUAL TABLE subdocs USING fts5("
            "  nombre, sub, cuerpo, crudo UNINDEXED, polo UNINDEXED,"
            "  tokenize='unicode61 remove_diacritics 2')"
        )
        db.executemany(
            "INSERT INTO subdocs (nombre, sub, cuerpo, crudo, polo) VALUES (?,?,?,?,?)",
            # `cuerpo` lleva el nombre y el título antepuestos porque pesan en el calce;
            # `crudo` es lo que se sirve, sin esa repetición.
            [(n.nombre, t, f"{n.nombre} — {t}\n{c}" if t else f"{n.nombre}\n{c}", c, n.polo)
             for n in self.nodos.values() for t, c in subentradas(n.cuerpo)],
        )
        db.commit()

    def _semantica(self) -> None:
        """Vectoriza la cabecera de cada entrada Y cada una de sus sub-entradas.

        Antes se vectorizaba `cuerpo[:2000]` y nada mas. Con entradas de 41.000
        caracteres eso dejaba el 95% del contenido invisible para la busqueda
        semantica, y producia dos efectos medidos el 2026-07-29:

          · Entradas cuya cabecera es generica se volvian atractores universales:
            «Accesos requeridos» salia primera para «que le puedo prometer sobre
            redes sociales», «hay algun riesgo de seguridad» y «que tan probada
            esta la plataforma» — tres preguntas sin relacion entre si.
          · Lo escrito hondo era irrecuperable: la nota de precios de Meta y la del
            identificador nuevo de WhatsApp existian y no se encontraban.

        Ahora cada sub-entrada se vectoriza por separado y la entrada puntua con su
        MEJOR sub-entrada. Se sigue devolviendo una entrada por resultado —no
        cambia el contrato— pero deja de depender de que lo importante caiga en los
        primeros 2.000 caracteres.

        El motivo original para no fragmentar (con embeddings estaticos los trozos
        cortos son mas ruidosos que el promedio del documento) no aplica a esta
        granularidad: una sub-entrada no es un trozo arbitrario sino una unidad con
        su titulo, su ficha de campos y su evidencia — que es exactamente la unidad
        sobre la que esta base esta disenada.
        """
        self.vectores = None
        self.orden: list[str] = []
        self.es_cabecera: list[bool] = []
        # SIN MODELO SE SIGUE CONSTRUYENDO LO QUE NO ES VECTORIAL, y esto no es prolijidad: era una
        # caída. Este `return` temprano dejaba el índice a medio armar —sin `filas`, sin `subs_norm`—
        # y `consultar` moría con `AttributeError: 'Indice' object has no attribute 'subs_norm'`. O
        # sea que el degradado que todo el archivo promete —«sin capa semántica queda solo la léxica,
        # no se cae»— no existía: se caía.
        #
        # Estuvo latente desde siempre porque el modelo estático se montaba desde la imagen y NUNCA
        # fallaba en producción. El 2026-08-07, al pasar a un codificador que sí puede no cargar, la
        # ruta se ejercitó por primera vez y tumbó la búsqueda del servidor real. Es el patrón que
        # esta base ya tiene registrado dos veces: una defensa que nadie ejecutó nunca no es una
        # defensa, es una declaración.
        _sin_vectores = self.modelo is None
        textos: list[str] = []
        for nombre in self.nodos:
            cuerpo = self.nodos[nombre].cuerpo
            partes = re.split(r"(?m)^### ", cuerpo)
            # La cabecera (todo lo anterior a la primera sub-entrada) representa a la
            # entrada como sujeto: es lo que responde «que es esto».
            textos.append(f"{nombre}\n{partes[0][:2000]}")
            self.orden.append(nombre)
            self.es_cabecera.append(True)
            for sub in partes[1:]:
                # El titulo va repetido a proposito: pesa, y es lo que un lector busca.
                titulo = sub.split("\n", 1)[0]
                textos.append(f"{nombre} — {titulo}\n{_para_vector(sub)[:1500]}")
                self.orden.append(nombre)
                self.es_cabecera.append(False)
        if not _sin_vectores:
            V = _vectorizar_con_cache(self.modelo, textos)
            self.vectores = V / np.clip(np.linalg.norm(V, axis=1, keepdims=True), 1e-9, None)
        # Posiciones de todos los vectores de cada entrada, para puntuarla por su MEJOR
        # sub-entrada en vez de por su cabecera (ver `rasgos`).
        self.filas: dict[str, list[int]] = {}
        for i, nom in enumerate(self.orden):
            self.filas.setdefault(nom, []).append(i)
        # Las unidades atómicas, normalizadas una sola vez: los rasgos las necesitan para
        # medir cobertura donde significa algo. Sobre la entrada entera, una de 40.000
        # caracteres contiene casi cualquier palabra y el rasgo valía ~1 para todas.
        # Los TÍTULOS de las notas, normalizados. En esta base cada uno es una afirmación
        # escrita a mano —«Meta empieza a cobrar por mensajes que hoy son gratis»— y por eso
        # es la señal más informativa del corpus. Hasta el 2026-07-30 el orden solo miraba el
        # título de la ENTRADA, que es un sustantivo genérico («Canales de mensajería»).
        self.titulos_sub: dict[str, list[list[str]]] = {
            nom: [[w for w in PALABRA.findall(normalizar(t)) if w not in VACIAS]
                  for t, _ in subentradas(nd.cuerpo) if t]
            for nom, nd in self.nodos.items()
        }
        # {entrada: {título de la sub-entrada: cuándo creció por última vez}}, indexado por el
        # NOMBRE de la entrada y no por su ruta, que es como lo piden quienes lo usan.
        self.fecha_de_sub: dict[str, dict[str, int]] = {}
        for nom, nd in self.nodos.items():
            porc = getattr(self, "fechas_sub", {}).get(nd.ruta)
            if porc:
                self.fecha_de_sub[nom] = porc

        self.subs_norm: dict[str, list[str]] = {
            nom: [normalizar(f"{t} {c}") for t, c in subentradas(nd.cuerpo)]
            for nom, nd in self.nodos.items()
        }

    def semejantes(self, consulta: str, tope: int = 12) -> list[str]:
        if self.modelo is None or self.vectores is None:
            return []
        v = self.modelo.encode([consulta]).astype("float32")[0]
        v = v / max(float(np.linalg.norm(v)), 1e-9)
        # `self.nodos` puede venir acotado por restringir(): se filtra aca porque los
        # vectores y su orden se comparten entre niveles (se calculan una sola vez).
        #
        # Desde el 2026-07-29 hay VARIOS vectores por entrada (cabecera + una por
        # sub-entrada), asi que el mismo nombre aparece repetido: se queda con su
        # mejor posicion. Es «puntuar la entrada por su mejor sub-entrada» sin
        # cambiar el contrato de devolver una entrada por resultado.
        sims = self.vectores @ v
        # EL ATRACTOR POR TAMAÑO, Y SU CORRECCIÓN MEDIBLE. Puntuar la entrada por su MEJOR
        # sub-entrada le da a una entrada de 47 sub-entradas cuarenta y siete tiros a la mejor y a
        # una de 3 solamente tres: el máximo de n muestras crece con n aunque el tema no tenga nada
        # que ver. Medido el 2026-08-06 con el instrumento de pertinencia: entre el corpus del 30 de
        # julio y el de hoy, la precisión en primer lugar cayó 10 preguntas de 81 **con el mismo
        # código**, y las entradas de `comprobado` pasaron de 10,3 a 16,1 sub-entradas de media —
        # «Motor de mensajes» de 14 a 47.
        #
        # Se descuenta `log(nº de tiros)`, que es como crece esa ventaja. El valor por omisión es
        # CERO —o sea el comportamiento de siempre, byte por byte— porque cuánto descontar es una
        # pregunta empírica y la contesta `tools/pertinencia.py --ablacion`, no una intuición.
        penal = float(os.environ.get("KB_ATRACTOR_PENAL", "0"))
        if penal:
            mejor: dict[str, float] = {}
            tiros: dict[str, int] = {}
            for i, nom in enumerate(self.orden):
                if nom not in self.nodos:
                    continue
                tiros[nom] = tiros.get(nom, 0) + 1
                if sims[i] > mejor.get(nom, -2.0):
                    mejor[nom] = float(sims[i])
            ajustado = {nom: s - penal * math.log(tiros[nom]) for nom, s in mejor.items()}
            return sorted(ajustado, key=lambda n: -ajustado[n])[:tope]
        orden = (self.orden[i] for i in np.argsort(-sims))
        vistos: dict[str, None] = {}
        for n in orden:
            if n in self.nodos and n not in vistos:
                vistos[n] = None
                if len(vistos) >= tope:
                    break
        return list(vistos)

    def cercania_maxima(self, consulta: str) -> float | None:
        """Similitud del vecino semantico mas cercano, en [0,1]. Es la senal de si la
        consulta cae siquiera cerca del dominio de la base; la usa el piso de pertinencia."""
        if self.modelo is None or self.vectores is None or not self.nodos:
            return None
        v = self.modelo.encode([consulta]).astype("float32")[0]
        v = v / max(float(np.linalg.norm(v)), 1e-9)
        sims = self.vectores @ v
        # SOLO cabeceras: desde que hay un vector por sub-entrada (2026-07-29), mirar
        # todos infla el maximo por azar y una consulta ajena al dominio deja de
        # declararse ajena. La cabecera es la que representa el sujeto de la entrada,
        # y el sujeto es lo que define si la base cubre o no lo preguntado.
        visibles = [i for i, n in enumerate(self.orden)
                    if n in self.nodos and self.es_cabecera[i]]
        return float(max(sims[i] for i in visibles)) if visibles else None

    def rasgos(self, pregunta: str, nombres: list[str]) -> dict[str, list[float]]:
        """Vector de rasgos por candidato, para el orden con pesos entrenados.

        La MISMA función alimenta el entrenamiento (tools/entrenar-ranker.py) y el
        servicio: si divergieran, los pesos quedarían calibrados contra rasgos que el
        servidor no calcula. Todo es determinista y ya estaba pagado en el arranque
        —vectores, índice léxico, grafo—; nada de esto agrega dependencias.
        """
        q_norm = normalizar(pregunta)
        terminos = [tt for tt in PALABRA.findall(q_norm) if tt not in VACIAS]
        grupos = [self.vocabulario.get(raiz(tt), set()) | {tt} for tt in terminos]
        v = None
        if self.modelo is not None and self.vectores is not None:
            v = self.modelo.encode([pregunta]).astype("float32")[0]
            v = v / max(float(np.linalg.norm(v)), 1e-9)
        # bm25 de una vez para todos los candidatos que calzan
        bm = {}
        try:
            fts = self.expandir(pregunta)
            # Sobre SUB-ENTRADAS, quedándose con la mejor de cada entrada. La misma decisión
            # que en la generación de candidatos: la relevancia se juzga en la unidad donde
            # la frecuencia de términos significa algo, y se atribuye a la entrada padre.
            # bm25() NO se puede usar dentro de un agregado —SQLite responde «unable to
            # use function bm25 in the requested context»— y la excepción se tragaba
            # silenciosamente dejando el rasgo léxico en cero para TODOS los candidatos.
            # Vivió así desde el 2026-07-30 por la mañana: el entrenamiento vio el rasgo
            # como constante y le asignó peso 0,000, y el orden pasó a decidirlo la
            # centralidad del grafo. Se calcula en una subconsulta y se agrega afuera.
            # bm25() solo se puede usar DIRECTO sobre la tabla FTS: ni dentro de un
            # agregado ni envuelto en una subconsulta —SQLite responde «unable to use
            # function bm25 in the requested context»—. La excepción se tragaba en
            # silencio y el rasgo léxico quedaba en cero para TODOS los candidatos. Vivió
            # así desde la mañana del 2026-07-30, y el entrenamiento, viendo el rasgo
            # constante, le asignó peso 0,000: el orden pasó a decidirlo la centralidad
            # del grafo, que es un prior y no evidencia. Se agrega en Python.
            for nom, sc in self.db.execute(
                    "SELECT nombre, bm25(subdocs) FROM subdocs WHERE subdocs MATCH ?",
                    (fts,)):
                if nom not in bm or sc < bm[nom]:
                    bm[nom] = sc  # más negativo = mejor, convención FTS5
        except sqlite3.OperationalError:
            pass
        peor_bm = max(bm.values()) if bm else 0.0
        umbral_hub = max(6, min(25, int(len(self.nodos) * 0.45)))
        fuera: dict[str, list[float]] = {}
        for nom in nombres:
            nd = self.nodos[nom]
            cuerpo_n = normalizar(nd.cuerpo)
            titulo_n = normalizar(nom)
            pal_tit = [w for w in PALABRA.findall(titulo_n) if w not in VACIAS]
            cos = 0.0
            if v is not None and nom in getattr(self, "filas", {}):
                # MEJOR de sus vectores, no el de su cabecera. `self.orden.index(nom)`
                # devolvía siempre la primera aparición —la cabecera— así que lo escrito
                # hondo no llegaba nunca a la decisión de orden, solo a la de candidatos.
                cos = float(max(self.vectores[i] @ v for i in self.filas[nom]))
            # Cobertura en la MEJOR sub-entrada, no en el cuerpo entero: es la diferencia
            # entre «la palabra aparece en algún lugar de estas 40.000 letras» y «esta nota
            # habla de esto». Medido el 2026-07-30: sobre el cuerpo entero el rasgo valía
            # cerca de 1 para casi todos los candidatos, o sea no discriminaba nada.
            subs_n = self.subs_norm.get(nom) or [cuerpo_n]
            cobertura = (max(sum(1 for g in grupos if any(f in sn for f in g))
                             for sn in subs_n) / len(grupos)) if grupos else 0.0
            tit_en_preg = (sum(1 for w in pal_tit if w in q_norm) / len(pal_tit)) if pal_tit else 0.0
            # Calce con el TÍTULO DE UNA NOTA: qué fracción de las palabras de algún título
            # de nota aparece en la pregunta. Es el equivalente del rasgo de título de
            # entrada, sobre la unidad donde los títulos dicen algo concreto.
            mejor_sub_tit = 0.0
            for pal in self.titulos_sub.get(nom, []):
                if pal:
                    mejor_sub_tit = max(mejor_sub_tit,
                                        sum(1 for w in pal if w in q_norm) / len(pal))
            fuera[nom] = [
                cos,
                # bm25 reescalado a "más alto = mejor", 0 si no calzó
                (peor_bm - bm[nom]) if nom in bm else 0.0,
                cobertura,
                tit_en_preg,
                1.0 if (titulo_n in q_norm or q_norm in titulo_n) else 0.0,
                1.0 if nd.es_indice else 0.0,
                min(1.0, len(self.relacionados(nom)) / max(umbral_hub, 1)),
                math.log(1 + len(nd.cuerpo)) / 10.0,
                mejor_sub_tit,
            ]
        return fuera

    def restringir(self, campo: str, valor) -> "Indice":
        """Devuelve una vista de este indice con solo las entradas cuyo `campo` del
        frontmatter vale `valor`. Comparte el indice lexico, los vectores y el modelo
        —construirlos de nuevo costaria tanto como el arranque entero—; lo unico propio
        es el diccionario de entradas visibles, y de ahi cuelga todo lo demas: buscar,
        leer, los vecinos y el panorama recorren `self.nodos`."""
        vista = copy.copy(self)
        visibles = {n: nd for n, nd in self.nodos.items() if nd.meta.get(campo) == valor}
        # Y dentro de cada entrada visible, se recorta lo que declare otra visibilidad.
        # Se hace ACA, sobre el cuerpo, y no al servir el extracto: asi ninguna funcion
        # que lea `cuerpo` mas adelante puede olvidarse del recorte. `menciona` se
        # recalcula sobre el texto recortado — si no, el nombre de una entrada interna
        # citada solo dentro de lo recortado seguiria saliendo en «Conecta con».
        vista.nodos = {}
        for n, nd in visibles.items():
            recortado = recortar_subentradas(nd.cuerpo, campo, valor)
            vista.nodos[n] = nd if recortado == nd.cuerpo else replace(
                nd, cuerpo=recortado,
                menciona=sorted({x.strip() for x in WIKILINK.findall(recortado)}))
        # Indice lexico propio: el compartido se construyo con los cuerpos SIN recortar, y
        # el extracto usa su fragmento como localizador. Cuando ese fragmento ya no existe
        # en el cuerpo recortado, `extracto` devolvia el fragmento crudo — texto recortado
        # servido tal cual. Es la fuga que se midio el 2026-07-27, y no se cierra recortando
        # solo el cuerpo: hay que recortar tambien lo que el buscador puede encontrar.
        # Los vectores siguen compartidos a proposito: reencodear cuesta el arranque entero
        # y solo influyen en el ORDEN, nunca en el texto que se entrega.
        vista.db = sqlite3.connect(":memory:", check_same_thread=False)
        vista._fts()
        return vista

    # -- ayudas ---------------------------------------------------------------

    def resolver(self, tema: str) -> tuple[list[str], str]:
        """Devuelve (candidatos, confianza). confianza: 'fuerte' si el nombre coincide
        exacto o por subcadena; 'debil' si solo comparten raices. La distincion importa
        para seguridad: pedir "responsabilidad extendida" NO debe entregar el contenido
        de "Trazabilidad Extendida Post-Valorización" como si fuera lo pedido —comparten
        la raiz "extendid" pero son cosas distintas."""
        if tema in self.nodos:
            return [tema], "fuerte"
        objetivo = normalizar(tema)
        if exactos := [n for n in self.nodos if normalizar(n) == objetivo]:
            return exactos, "fuerte"
        if contiene := [n for n in self.nodos if objetivo in normalizar(n)]:
            return sorted(contiene, key=len), "fuerte"
        pedido = {raiz(p) for p in PALABRA.findall(tema)}
        if not pedido:
            return [], "debil"
        puntuados = []
        for n in self.nodos:
            if comunes := pedido & {raiz(p) for p in PALABRA.findall(n)}:
                puntuados.append((len(comunes), -len(n), n))
        return [n for _, _, n in sorted(puntuados, reverse=True)], "debil"

    def relacionados(self, nombre: str) -> list[str]:
        nodo = self.nodos.get(nombre)
        if not nodo:
            return []
        vecinos = {d for ds in nodo.enlaces.values() for d in ds}
        vecinos |= self.backlinks.get(nombre, set()) | set(nodo.menciona)
        return sorted(v for v in vecinos if v in self.nodos and v != nombre)

    def fuente(self, n: Nodo) -> str:
        etiqueta = self.cfg.polos.get(n.polo, n.polo)
        partes = [n.nombre, etiqueta]
        if n.modificado:
            # La fecha del AUTOR, no la del proceso que sirve: `date.fromtimestamp` usa la zona
            # local, y el contenedor corre en UTC mientras se commitea en UTC−4. Se conserva el
            # cálculo por epoch como respaldo para un historial que no traiga la fecha.
            partes.append("actualizada " + (n.modificado_iso
                          or datetime.date.fromtimestamp(n.modificado).isoformat()))
        # Frescura declarada al lector en cada resultado. Comparacion de fechas pura
        # (calendario por tipo, kb/mcp.yaml `retencion`); el juicio de si la entrada
        # sigue siendo verdad pertenece a la calibracion, no al servidor.
        # LA RETENCIÓN SE DECLARA POR TIPO DE SUB-ENTRADA Y ACÁ SE CONSULTABA POR EL TIPO DEL
        # ARCHIVO. Los dos vocabularios no se cruzan en un solo valor: los archivos son `plan`,
        # `sistema`, `pregunta`, `requerido`; la retención está declarada para `hallazgo`,
        # `funcionamiento`, `medicion`, `contexto`. Así que el plazo salía vacío SIEMPRE y el aviso
        # nunca disparaba: cubría 2 de 61 entradas, por coincidencia. Cuarta iteración pidiéndolo, y la
        # palabra «re-verificación» no aparecía en ninguna de las 54 respuestas de la última.
        #
        # Todavía no se nota —la base tiene doce días y los plazos son de 90 a 180— y es justamente
        # por eso que había que arreglarlo ahora: el mecanismo que protege al consumidor autónomo de
        # actuar sobre un hecho vencido estaba apagado ANTES de estrenarse, y el día que importe nadie
        # va a estar mirando. Se cuenta por sub-entrada y se dice cuántas, porque un nodo-sujeto puede
        # tener una sola afirmación vencida entre veinte frescas.
        hoy = datetime.date.today()
        vencidas, sin_sello = [], []
        for titulo, campos in _subentradas_con_campos(n.cuerpo):
            plazo = self.cfg.retencion.get(str(campos.get("Tipo", "")).lower())
            if not plazo:
                continue
            crudo = campos.get("Verificado") or campos.get("Declarado")
            try:
                sello = datetime.date.fromisoformat(str(crudo).strip())
            except (TypeError, ValueError):
                sin_sello.append(titulo)
                continue
            if (hoy - sello).days > plazo:
                vencidas.append((titulo, sello))
        if vencidas:
            mas = f" y {len(vencidas) - 1} más" if len(vencidas) > 1 else ""
            t0, f0 = vencidas[0]
            partes.append(f"re-verificación VENCIDA en «{t0[:40]}» (sellada {f0.isoformat()}){mas}"
                          " — tratar esa afirmación como no confirmada")
        elif sin_sello:
            partes.append(f"{len(sin_sello)} sección(es) sin fecha de comprobación — tratarlas como "
                          "no confirmadas")
        return " · ".join(partes)

    def recientes(self, polo: str | None = None, tope: int = 12) -> list[str]:
        """Entradas ordenadas por ultima modificacion (git), de nueva a vieja. Se
        excluyen los indices/hubs (muchos backlinks): se tocan en casi todos los
        commits, asi que su fecha no informa sobre novedad de contenido."""
        candidatos = [n for n in self.nodos.values()
                      if (not polo or n.polo == polo) and n.modificado
                      and len(self.relacionados(n.nombre)) <= 25]
        candidatos.sort(key=lambda n: -n.modificado)
        return [n.nombre for n in candidatos[:tope]]

    def _indice_subentradas(self, nombre: str, ini: int, ancho: int) -> str:
        """Linea final del extracto: las sub-entradas que la ventana dejo FUERA, cada una
        con su ficha minima (estado, a quien espera). Existe porque la ventana muestra un
        solo pedazo de un nodo-sujeto, y quien pregunta por el pedido que espera al Project
        Manager recibia siempre el pedazo del pedido del fundador — alargar la ventana no
        lo arreglaba, porque el ancla era la misma (tercera evaluacion, 2026-07-27). Con
        esta linea, lo que la ventana no muestra al menos queda ENUMERADO con su estado, y
        el lector sabe que hay mas y que se llama asi. Se construye del cuerpo ya recortado
        por nivel: lo invisible no aparece ni aca."""
        cuerpo = self.nodos[nombre].cuerpo
        fuera = []
        for m in re.finditer(r"^###\s+(.+?)\s*$", cuerpo, re.M):
            if ini <= m.start() < ini + ancho:
                continue
            fin = cuerpo.find("\n### ", m.end())
            bloque = cuerpo[m.end():fin if fin > 0 else len(cuerpo)]
            campos = dict(re.findall(r"^-\s+\*\*([^:*]+):\*\*\s*(.+?)\s*$", bloque, re.M))
            # El tipo va primero: sin el, un logro cerrado y un problema viejo se leen
            # igual en la lista (quinta evaluacion) — y el tipo es justo lo que permite
            # armar el informe sin abrir cada entrada.
            ficha = " · ".join(x for x in (campos.get("Tipo"), campos.get("Estado")) if x)
            if espera := campos.get("Espera a"):
                ficha += f", espera a {espera}"
            fuera.append(f"«{m.group(1)}»" + (f" ({ficha})" if ficha else ""))
        if not fuera:
            return ""
        return "\n*Otras secciones de este documento:* " + " · ".join(fuera[:8])

    def extracto(self, nombre: str, consulta_fts: str, extendido: bool = False) -> str:
        """Sirve el pasaje, y garantiza que el límite declarado viaje con él."""
        texto = self._extracto_bruto(nombre, consulta_fts, extendido)
        nodo = self.nodos.get(nombre)
        if nodo is None:
            return texto
        if "por confirmar" not in texto.lower():
            lim = limite_declarado(nodo)
            if lim:
                texto = f"{lim} […] {texto}"
        # Un compromiso siempre dice en qué está y a quién espera, aunque la ventana
        # haya caído lejos de su ficha.
        if getattr(nodo, "polo", "") == "en-curso" and "**Estado:**" not in texto:
            ficha = ficha_pendiente(nodo)
            if ficha:
                texto = f"{ficha} […] {texto}"
        return texto

    def _recortar_sub(self, crudo: str, consulta_fts: str, tope: int) -> str:
        """Una sub-entrada que excede el tope, recortada en vez de descartada.

        Se conservan las DOS cosas por las que se sirve una sub-entrada, y en este orden:

          1. Su CABECERA —el título y la ficha de campos—, porque ahí viven «Estado»,
             «Espera a» y «Checkpoint». Quien pregunta qué está abierto necesita el campo,
             no la prosa: servir el pasaje sin la ficha repite el defecto que
             `ficha_pendiente` vino a cerrar.
          2. El PASAJE donde cae la coincidencia, que es lo que responde la pregunta.

        Si no se puede localizar la coincidencia, se sirve la cabecera más el comienzo de la
        prosa: sigue siendo la sub-entrada correcta, que es más de lo que daba el descarte.
        """
        lineas = crudo.split("\n")
        cabecera: list[str] = []
        for i, l in enumerate(lineas):
            if i == 0 or l.strip().startswith("#") or FICHA_CAMPO.match(l) or not l.strip():
                cabecera.append(l)
                continue
            break
        cab = " ".join(" ".join(cabecera).split())
        resto = " ".join(" ".join(lineas[len(cabecera):]).split())
        if not resto:
            return cab[:tope]
        SEP = " […] "
        margen = tope - len(cab) - len(SEP) * 2
        # Una cabecera que ya se come el presupuesto: se sirve sola, recortada al tope. No se
        # devuelve "" —eso reabriría el descarte por la ventana de atrás.
        if margen < 200:
            return (cab[:tope - len(SEP)] + SEP) if len(cab) > tope else cab
        # Dónde cae la coincidencia. Las formas del FTS vienen entrecomilladas por expandir(),
        # así que se buscan sobre el resto normalizado — sin acentos y en minúsculas, igual que
        # las indexó el índice.
        formas = re.findall(r'"([^"]+)"', consulta_fts) or []
        plano_norm = normalizar(resto)
        pos = min((p for p in (plano_norm.find(normalizar(f)) for f in formas if f) if p >= 0),
                  default=-1)
        if pos < 0:
            return cab + SEP + _hasta_palabra(resto, margen) + (
                SEP.rstrip() if len(resto) > margen else "")
        ini = max(0, pos - margen // 3)
        fin = min(len(resto), ini + margen)
        ini = max(0, fin - margen)          # si la coincidencia está al final, se usa todo el ancho
        # EL CORTE CAE EN UN LÍMITE DE PALABRA, no en el carácter que toque. Cortar por índice deja
        # el extracto abriendo con media palabra o con una comilla de cierre huérfana: medido el
        # 2026-08-07, 10 de 48 respuestas empezaban así, y quien lee —cada vez más otra IA— no tiene
        # cómo saber si eso es el texto o un error. Solo se mueve el borde; no se agrega ni se quita
        # contenido, y el ancho pedido se respeta porque solo se recorta hacia adentro.
        pasaje = _desde_palabra(resto, ini, fin)
        return (cab + SEP + pasaje + (SEP.rstrip() if fin < len(resto) else ""))

    def _hermanas_de(self, nombre: str, titulo_servido: str) -> str:
        """Las OTRAS sub-entradas del nodo, para que el lector sepa qué más hay y cómo se llama.

        Es la misma línea que `_indice_subentradas` produce para los caminos de ventana, pero
        anclada en el título servido en vez de en un rango de caracteres: acá se sabe exactamente
        cuál se entregó, así que enumerar el resto es exacto y no aproximado.
        """
        cuerpo = self.nodos[nombre].cuerpo
        objetivo = " ".join(str(titulo_servido).split()).lower()
        fuera = []
        for m in re.finditer(r"^###\s+(.+?)\s*$", cuerpo, re.M):
            titulo = m.group(1).strip()
            if " ".join(titulo.split()).lower() == objetivo:
                continue
            fin = cuerpo.find("\n### ", m.end())
            bloque = cuerpo[m.end():fin if fin > 0 else len(cuerpo)]
            campos = dict(re.findall(r"^-\s+\*\*([^:*]+):\*\*\s*(.+?)\s*$", bloque, re.M))
            ficha = " · ".join(x for x in (campos.get("Tipo"), campos.get("Estado")) if x)
            if espera := campos.get("Espera a"):
                ficha += f", espera a {espera}"
            fuera.append(f"«{titulo}»" + (f" ({ficha})" if ficha else ""))
        if not fuera:
            return ""
        return "\n\n*Otras secciones de este documento:* " + " · ".join(fuera[:12])

    def _extracto_bruto(self, nombre: str, consulta_fts: str, extendido: bool = False) -> str:
        # Primero: la SUB-ENTRADA que mejor calza, servida entera. Es la unidad atómica de
        # esta base —título, ficha de campos y evidencia— así que servirla completa entrega
        # la respuesta en vez de una ventana adivinada alrededor de una coincidencia. Las
        # cuatro máquinas de ventana que siguen abajo existían por no tener esta unidad, y
        # quedan como respaldo para el acierto puramente semántico, donde no hay coincidencia
        # literal que localizar.
        try:
            # EL CALCE DE PALABRAS NO PUEDE SER EL ÚNICO CRITERIO PARA ELEGIR QUÉ SE SIRVE. Cuando
            # una entrada tiene dos secciones sobre lo mismo —una resuelta y su sucesora vigente—,
            # elegir solo por rank es una lotería entre ellas, y perderla significa servir como
            # actual una afirmación que la propia base ya superó. Medido el 2026-08-05: en dos de
            # tres consultas dirigidas se servía una sección `resuelto` del día anterior mientras la
            # vigente quedaba en el puesto 2 y en el 6, sin siquiera enumerarse.
            #
            # Se traen las cuatro mejores por rank y se prefiere la que NO está cerrada, respetando
            # el rank dentro de cada grupo. Es un desempate, no un reordenamiento: una sección
            # vigente solo le gana a una resuelta que ya estaba entre las mejores por relevancia, y
            # el caso normal —una sola candidata— no cambia en nada.
            filas = self.db.execute(
                "SELECT sub, crudo FROM subdocs WHERE subdocs MATCH ? AND nombre = ? "
                "ORDER BY rank LIMIT 4", (consulta_fts, nombre)).fetchall()
            fila = None
            if filas:
                def _cerrada(crudo: str) -> bool:
                    m = re.search(r"^-\s+\*\*Estado:\*\*\s*(.+?)\s*$", crudo or "", re.M)
                    return bool(m) and m.group(1).strip().lower() in ("resuelto", "aceptado")
                fila = min(enumerate(filas),
                           key=lambda par: (_cerrada(par[1][1]), par[0]))[1]
            if fila and fila[0]:
                plano = " ".join(fila[1].split())
                tope = 2600 if extendido else 1800
                # LAS HERMANAS SE ENUMERAN TAMBIÉN ACÁ. Esta línea existe porque un nodo-sujeto
                # agrupa muchas afirmaciones y servir una sola deja al lector sin saber que hay más
                # —tercera evaluación, 2026-07-27—, pero solo se anexaba en los caminos de ventana
                # adivinada. Cuando el camino de sub-entrada pasó a ser el habitual, la venda dejó de
                # aplicarse: medido el 2026-08-06, 15 de 160 tarjetas (9,4 %) la traían. Cuarta
                # iteración pidiéndolo.
                if len(plano) <= tope:
                    return plano + self._hermanas_de(nombre, fila[0])
                # Y SI NO CABE, SE RECORTA — no se descarta. Descartarla y caer a la ventana
                # adivinada era el defecto repetido de tres evaluaciones seguidas («entrada
                # correcta, sección equivocada»), y tenía tamaño medido: 220 de las 341
                # sub-entradas de esta base (64 %) exceden el tope, así que la «unidad atómica»
                # que celebra el comentario de arriba estaba apagada para dos tercios del corpus.
                # Casos medidos el 2026-08-05: se descartaba por 270 caracteres, por 272 y por
                # 2.441. Perder una sub-entrada por 270 caracteres no es una decisión, es un
                # accidente del umbral.
                recortada = self._recortar_sub(fila[1], consulta_fts, tope)
                if recortada:
                    return recortada + self._hermanas_de(nombre, fila[0])
        except sqlite3.OperationalError:
            pass
        """Pasaje alrededor de la coincidencia; si el acierto vino de la capa
        semantica no hay coincidencia literal, asi que se muestra la apertura."""
        # (El extracto de un indice NO se fuerza al Inventario: empeoraba las preguntas
        #  definicionales —"¿qué es Kairós?" devolvia la tabla de hijos en vez de la
        #  definicion. El Inventario se ofrece en panorama(), que es la via explicita.)
        try:
            fila = self.db.execute(
                "SELECT snippet(docs, 1, '', '', ' … ', 64) FROM docs "
                "WHERE docs MATCH ? AND nombre = ? LIMIT 1",
                (consulta_fts, nombre),
            ).fetchone()
            if fila and fila[0]:
                pasaje = fila[0].strip()
                # El snippet crudo de FTS5 tope 64 tokens (su maximo) se queda corto: la
                # entrada correcta salia primera y la respuesta igual no servia porque el
                # extracto cortaba ANTES del dato —el numero, la remediacion, el pedido
                # concreto—, que en un nodo-sujeto suele vivir en una sub-entrada mas abajo.
                # Medido en dos evaluaciones seguidas: pasaba en 4 de 8 preguntas. Por eso el
                # snippet se usa como LOCALIZADOR y la ventana se recorta del cuerpo a su
                # alrededor, tambien en el modo por defecto; extendido solo agranda la ventana.
                ancho = 1400 if extendido else 900
                cuerpo = self.nodos[nombre].cuerpo
                # Si el cuerpo entero cabe en la ventana con un margen razonable, se sirve
                # entero. Recortar 200 caracteres de una entrada de 1.100 no ahorra nada y
                # pierde justo la cola — medido el 2026-07-27: dos compromisos de ~1.100
                # caracteres cortaban en «…ese acceso» y «Queda por confirmar…», dejando
                # fuera la frase que respondia la pregunta, que en el molde de en-curso
                # vive al final de la seccion de estado.
                plano_entero = " ".join(cuerpo.split())
                if len(plano_entero) <= ancho * 1.4:
                    return plano_entero
                fragmento = pasaje.split(" … ")[0]
                # snippet() antepone/pospone la elipsis cuando recorta bordes;
                # esos marcadores no existen en el cuerpo y romperian el find.
                fragmento = fragmento.removeprefix("… ").removesuffix(" …")
                pos = cuerpo.find(fragmento)
                # El snippet localiza UNA coincidencia, y en un nodo-sujeto con varias
                # sub-entradas suele ser la equivocada: preguntar por la memoria del motor
                # centraba la ventana en la sub-entrada de funciones de borde (medido
                # 2026-07-27, y antes «pasaba en 4 de 8 preguntas» con la ventana crudo).
                # Se puntua cada coincidencia por que tan RARO es lo que cae en su ventana,
                # y gana la mas densa. Tres decisiones que costaron una depuracion cada una:
                # 1) Se cuenta por GRUPO de expansion, no por forma — «mensaje»+«mensajes»
                #    es un concepto, no dos puntos.
                # 2) Cada grupo pesa por su rareza EN EL CORPUS (1/(1+df)), no en el nodo:
                #    pesar por rareza local hacia que cualquier termino unico dominara —
                #    «motor» aparece una vez en el cuerpo y arrastraba la ventana, pero el
                #    nodo entero es sobre el motor: no discrimina nada. «memoria» esta en
                #    dos entradas del corpus: esa es la pregunta. El titulo se excluye del
                #    barrido por la misma razon — es el sujeto, no una pista.
                # 3) La ventana arranca poco ANTES de la coincidencia, no centrada: centrar
                #    gastaba media ventana mirando hacia atras y cortaba la causa que viene
                #    despues del enunciado (medido: la limpieza fallida quedaba sin su causa).
                grupos = [{normalizar(f) for f in re.findall(r'"([^"]+)"', g)}
                          for g in re.split(r'\)\s+OR\s+\(|^\(|\)$',
                                            consulta_fts.strip()) if g.strip()]
                grupos = [g for g in grupos if g]
                sin_titulo = normalizar(cuerpo)
                fin_titulo = sin_titulo.find("\n")
                # Si la pregunta es esencialmente el TITULO del nodo, no hay nada que
                # localizar: quien pregunta por el sujeto entero se lleva la apertura, que
                # es donde la regla de orden coloca el «por confirmar» y lo abierto. La
                # densidad aca solo estorba — movia la ventana a la sub-entrada mas cargada
                # y el limite declarado arriba no llegaba nunca (regresion medida en la
                # bateria el 2026-07-27).
                palabras_titulo = {normalizar(w) for w in PALABRA.findall(nombre)}
                es_el_titulo = grupos and all(g & palabras_titulo for g in grupos)
                if len(grupos) > 1 and not es_el_titulo:
                    ocurrencias = []   # (posicion, indice de grupo)
                    peso = {}
                    for gi, g in enumerate(grupos):
                        pps = [m.start() for f in g
                               for m in re.finditer(re.escape(f), sin_titulo)
                               if m.start() > fin_titulo][:60]
                        if not pps:
                            continue
                        try:
                            df = self.db.execute(
                                "SELECT count(*) FROM docs WHERE docs MATCH ?",
                                (" OR ".join(f'"{f}"' for f in sorted(g)),)
                            ).fetchone()[0]
                        except sqlite3.OperationalError:
                            df = 1
                        peso[gi] = 1.0 / (1 + df)
                        ocurrencias += [(pp, gi) for pp in pps]

                    def score_en(p0):
                        presentes = {gi for pp, gi in ocurrencias
                                     if p0 - 120 <= pp < p0 + ancho}
                        return sum(peso[gi] for gi in presentes)

                    mejor = max((pp for pp, _ in ocurrencias),
                                key=score_en, default=None)
                    if mejor is not None and (pos < 0
                                              or score_en(mejor) > score_en(pos)):
                        pos, fragmento = mejor, cuerpo[mejor:mejor + 20]
                    # SEGUNDA VENTANA (2026-07-28, tercer juez que tropieza con esto): en un
                    # nodo-sujeto grande, una pregunta compuesta —«quién consume X y qué se
                    # rompe si Y»— calza fuerte en DOS sub-entradas alejadas, y una sola
                    # ventana entrega media respuesta por bien elegida que este. Si existe
                    # otra zona con la mitad o mas del puntaje de la mejor y FUERA de su
                    # alcance, se sirven dos ventanas mas cortas en vez de una larga: misma
                    # longitud total, respuesta completa.
                    segunda = None
                    if pos >= 0 and ocurrencias:
                        lejos = [pp for pp, _ in ocurrencias
                                 if abs(pp - pos) > ancho]
                        if lejos:
                            cand2 = max(lejos, key=score_en)
                            if score_en(cand2) >= score_en(pos) * 0.5:
                                segunda = cand2
                    if segunda is not None:
                        w = int(ancho * 0.55)
                        a, b = sorted((pos, segunda))
                        v1 = " ".join(cuerpo[max(0, a - 80):max(0, a - 80) + w].split())
                        v2 = " ".join(cuerpo[max(0, b - 80):max(0, b - 80) + w].split())
                        pre = "… " if a > 80 else ""
                        post = " …" if b - 80 + w < len(cuerpo) else ""
                        return (f"{pre}{v1} […] {v2}{post}"
                                f"{self._indice_subentradas(nombre, a - 80, (b - a) + w)}")
                if pos >= 0:
                    ini = max(0, pos - 120)
                    ventana = " ".join(cuerpo[ini:ini + ancho].split())
                    pre = "… " if ini > 0 else ""
                    post = " …" if ini + ancho < len(cuerpo) else ""
                    return f"{pre}{ventana}{post}{self._indice_subentradas(nombre, ini, ancho)}"
                # Nada calzo en este cuerpo: o el indice quedo desfasado, o apunta a algo
                # que este nivel no puede ver. En ningun caso se devuelve el fragmento del
                # indice — solo se muestra el cuerpo que SI corresponde. El indice de
                # sub-entradas va TAMBIEN aca: este es justamente el camino que toma un
                # acierto puramente semantico, donde la ventana es la apertura y todas las
                # sub-entradas quedan fuera de ella.
                aplanado = " ".join(cuerpo.split())
                tope = 1400 if extendido else 900
                if len(aplanado) <= tope:
                    return aplanado
                return aplanado[:tope] + " …" + self._indice_subentradas(nombre, 0, tope)
        except sqlite3.OperationalError:
            pass
        # Acierto puramente semantico: el snippet lexico no devolvio fila, asi que la
        # ventana es la apertura del nodo. El indice de sub-entradas importa MAS aca que
        # en ningun otro camino — todas quedan fuera de la ventana.
        cuerpo = " ".join(self.nodos[nombre].cuerpo.split())
        tope = 1400 if extendido else 900
        if len(cuerpo) > tope:
            return cuerpo[:tope] + " …" + self._indice_subentradas(nombre, 0, tope)
        return (cuerpo[:tope] + " …") if len(cuerpo) > tope else cuerpo


# --- herramientas ------------------------------------------------------------

def temas_centrales(idx: Indice, tope: int = 10) -> list[str]:
    """Los conceptos de los que trata esta KB, derivados del grafo.

    Un cliente MCP decide si llamar a una herramienta leyendo su descripcion. Si esta
    dice solo "busca en la base de conocimiento", el agente no tiene como saber que
    ESTA base habla de neumaticos y no de reposteria: acaba decidiendo por el nombre
    del conector, que es una señal debil. La descripcion tiene que nombrar el dominio.

    No se declara a mano —seria una cosa mas que mantener por KB, y quedaria vieja—:
    se deduce de los nodos mas referenciados, que por construccion del grafo bipolar
    son los conceptos centrales. Se excluyen indices y tableros, que son navegacion.
    """
    grado: collections.Counter[str] = collections.Counter()
    for nodo in idx.nodos.values():
        for vecino in idx.relacionados(nodo.nombre):
            grado[vecino] += 1
    return [nom for nom, _ in grado.most_common(60)
            if nom in idx.nodos and not idx.nodos[nom].es_indice
            and not nom.startswith("00-")][:tope]


def con_dominio(base: str, nucleo: str):
    """Mete el dominio DENTRO del primer parrafo del docstring, no antes ni despues.

    Dos intentos anteriores fallaron por el mismo motivo de fondo —suponer que el
    cliente entrega el texto entero— y cada uno lo pago en un extremo distinto:

      · Anteponer el parrafo de dominio completo (hasta el 2026-07-30): las tres
        herramientas empezaban con los MISMOS 1.100 caracteres, y como lo visible
        eran los primeros, el modelo no podia distinguir `consultar` de `leer`.
      · Ponerlo al final, «donde ser recortado no cuesta nada» (ese mismo dia):
        costaba todo. Medido contra claude.ai el 2026-07-30 por la tarde, el modelo
        reprodujo EXACTAMENTE el primer parrafo de cada herramienta y declaro no
        saber «el dominio tematico exacto, ni cuantos documentos contiene» —los dos
        datos que estaban en la cola—. Y declaro no tener descripcion del servidor:
        las instrucciones, 1.871 caracteres, no le llegaron. Que en Claude Code SI
        lleguen no las salva; el fundador entra por claude.ai.

    De ahi la regla: **el primer parrafo tiene que bastarse solo**, y no puede
    delegar nada en las instrucciones del servidor. Asi que el primer parrafo lleva
    (1) el verbo propio de la herramienta al inicio, que es lo unico que la
    distingue, con el nombre de la base incrustado, y (2) el nucleo del dominio,
    inmediatamente despues. Lo demas —parametros, matices— va detras, y si se
    recorta se pierde detalle, no el sentido.
    """
    def decorar(fn):
        propio = textwrap.dedent(fn.__doc__ or '').strip()
        primera, _, resto = propio.partition("\n")
        fn.__doc__ = f"{primera.format(base=base)} {nucleo}" + (f"\n{resto}" if resto else "")
        return fn
    return decorar


# ── Preguntas por PROPIEDAD, y el filtro que las contesta exacto ─────────────────
# Viven ACÁ, a nivel de módulo, y no dentro de `crear_servidor`, por una razón que se pagó: dentro
# de la clausura no hay forma de ejercitarlas sin levantar el servidor entero, así que cada arreglo
# de esta zona se venía verificando por lectura. Dos de ellos resultaron incoherentes entre sí —el
# detector aceptaba «resolvió» y la deducción no—, y eso es exactamente lo que una prueba de tres
# líneas habría cazado. Acá se pueden importar y probar: `tools/test_por_propiedad.py`.
# LOS VERBOS DE ALGO TERMINADO, EN UN SOLO LUGAR. Los leen las TRES piezas que tienen que estar de
# acuerdo: el detector que decide si la pregunta es por propiedad, la rama que deduce «resuelto» y
# la que deduce su negación. Tenerlos duplicados es exactamente cómo se separan — la base ya tiene
# registrado que «el detector y la deducción llegaron a contradecirse: uno aceptaba resolvió y la
# otra no», y el 2026-08-06 volvió a pasar al agregar «logró» a una sola de las tres.
# `consigui` va aparte de `consegui` porque el castellano lo dice irregular: «consiguió».
_TERMINADO = ("resuelt|resolv|arregl|cerr|solucion|logr|consigui|consegui|avanz|complet|"
              "termin|finaliz|entreg")

# LOS VERBOS DE EMPEZAR, que la negación no conocía. Solo sabía negar verbos de TERMINAR, así que
# «qué planes para arreglar problemas NO ARRANCARON» no entraba a la rama negativa, caía en la
# positiva por el «arreglar» de la subordinada, y contestaba `resuelto` — el inverso exacto, que es
# el peor error de esta función. Encontrado el 2026-08-07 sondeando el borde de otro arreglo, no por
# una pregunta real; es la misma familia que ya se desbordó cuatro veces, del otro lado del verbo.
# Lo que NO arregla esto: que un verbo de terminar en una subordinada («planes PARA ARREGLAR») le
# gane al sujeto de la pregunta. Eso está registrado como hallazgo aparte y necesita más que una
# lista.
_ARRANCADO = "arranc|empez|comenz|inici|parti[oó]|partier"


_POR_PROPIEDAD = re.compile(
    # LA FORMA NEGATIVA, con su propia alternativa y bien holgada. «Qué está mal y todavía no se
    # arregló» tiene seis palabras entre el «qué» y el verbo, así que ninguna de las formas de abajo
    # la reconocía — y no reconocerla es peor que en los otros casos: la deducción SÍ la entiende,
    # así que lo único que faltaba para contestar bien era que el detector la dejara pasar.
    # Y LOS VERBOS DE EMPEZAR VIAJAN CON LOS DE TERMINAR EN LA RAMA NEGATIVA, no en la positiva. La
    # deducción aprendió a negarlos el 2026-08-07 y esto no, así que «qué no empezó todavía» ni
    # llegaba a la deducción: el detector la descartaba antes y la pregunta se contestaba por tema.
    # Es la tercera vez que una lista de verbos se separa de su gemela y el efecto es el mismo:
    # media función entiende la pregunta y la otra media no la deja pasar. Solo en la rama NEGATIVA
    # a propósito — «qué empezó esta semana» no es una pregunta por propiedad, es por tramo de
    # tiempo, y meterla acá le prometería una respuesta exacta que no hay con qué componer.
    rf"(qu[eé]\s+.{{0,44}}\bno\s+.{{0,14}}({_TERMINADO}|{_ARRANCADO})|"
    r"qu[eé]\s+.{0,44}\bsin\s+(arreglar|resolver|cerrar|solucionar)|"
    # El sustantivo del medio vale también acá: «qué PROBLEMAS se resolvieron» se preguntaba igual
    # que «qué se resolvió» y solo la segunda calzaba.
    rf"qu[eé]\s+((\w+|\w+\s+\w+)\s+)?(se\s+)?({_TERMINADO})|"
    # Y el orden inverso —el estado ANTES del verbo—: «qué trabajo pendiente queda» es la misma
    # pregunta que «qué queda pendiente», y el español admite las dos sin preferencia.
    r"qu[eé]\s+((\w+|\w+\s+\w+)\s+)?(abierto|pendiente|trabado|frenado|detenido)s?\s+"
    r"(queda|hay|est[aá]|falta|sigue)|"
    # El sustantivo del medio: «qué TRABAJO está abierto» es la primera pregunta de toda iteración de
    # delegación, y no calzaba porque el patrón exigía «qué está abierto» pegado. Medido el
    # 2026-08-05 sobre el servidor real: no disparaba, así que se servía lo más parecido en vez de
    # la lista completa. Se admiten hasta dos palabras —«qué trabajo pendiente queda»—.
    r"qu[eé]\s+((\w+|\w+\s+\w+)\s+)?(est[aá]|hay|queda|falta)\s+"
    r"(abierto|pendiente|sin\s+resolver|trabado|frenado|detenido|esperando)|"
    # «Qué está trabado esperando» y sus variantes: el bloqueo es una propiedad, no un tema.
    r"qu[eé]\s+.{0,24}(trabado|frenado|bloqueado|esperando|a\s+la\s+espera)|"
    # PREGUNTARLE A ALGUIEN ES LA MISMA FORMA QUE MOSTRARLE, y faltaba. «Qué tengo que
    # PREGUNTARLE al Project Manager cuando lo vea» es la pregunta canónica antes de una reunión y
    # no activaba nada: se contestaba por tema, con seis documentos que no declaran a quién espera
    # nada. Pasaba en verde por casualidad —según qué fragmentos trajera el buscador— y el cambio de
    # modelo lo destapó: es un caso que medía la suerte, no el mecanismo.
    r"qu[eé]\s+.{0,20}(mostrar|mostrarle|ense[nñ]ar|preguntar|preguntarle|consultarle|pedirle)"
    r".{0,20}(fundador|direcci[oó]n|project|pm|jefe)|"
    r"qu[eé]\s+(medicion|hallazgo|plan|pedido)e?s\s+hay|"
    # Las palabras del LECTOR, que no son las de la base. Quien pregunta dice «problemas»,
    # «riesgos» o «fallas»; la base llama a eso `hallazgo` y prohibe la jerga en la prosa, asi
    # que el detector solo reconocia un vocabulario que nadie usa al preguntar. Medido el
    # 2026-08-05: «que problemas hay hoy en la plataforma» —la pregunta de direccion— no
    # activaba la respuesta exacta, y el defecto se venia declarando «por diseno del
    # escalamiento» desde tres evaluaciones atras. No lo era: el recorte por nivel ya protege a
    # direccion, y esto solo decide si se le sirve la lista completa o lo mas parecido.
    r"qu[eé]\s+(problema|riesgo|falla|defecto|pendiente)s?\s+(hay|existe|tiene|queda)|"
    r"(problema|riesgo|falla)s?\s+(abierto|vigente|sin\s+resolver)|"
    r"lista\s+de\s+(hallazgos|pendientes|resueltos))", re.I)


# EL PRETÉRITO, POR SU MORFOLOGÍA Y NO POR UNA LISTA DE VERBOS. Es lo que distingue «hoy» fecha de
# «hoy» adverbio de actualidad: «qué se HIZO hoy» pregunta por un tramo de tiempo, «qué problemas
# HAY hoy» pregunta por el estado presente y contestarla con las últimas horas esconde el resto.
#
# Se probó primero al revés —una lista de verbos de estado: hay, está, existe, queda, sigue— y se
# descartó midiéndola: mataba «qué se abrió AYER y SIGUE abierto» y «qué se cerró HOY y ya no HAY
# que hacer», que son temporales de verdad con un verbo de estado en la otra mitad de la oración.
# Cualquier arreglo por adyacencia era una regla sobre el orden de las palabras, y la lista seguía
# abierta: «corren hoy», «se puede cobrar hoy» y «existen hoy» habrían pedido tres parches más.
#
# El pretérito, en cambio, es una regla CERRADA: `-ó`, `-aron`, `-ieron`, más los nueve irregulares
# que el castellano tiene y no va a tener más. No hay verbo nuevo que agregarle.
_PRETERITO = re.compile(
    r"\b\w+(ó|aron|ieron|eron)\b"
    r"|\b(hizo|hicieron|fue|fueron|hubo|dijo|dijeron|puso|pusieron|vino|vinieron"
    r"|tuvo|tuvieron|estuvo|estuvieron|supo|supieron|quiso|quisieron)\b")

# El texto con que `listar` dice que no encontró nada. ES UNA CONSTANTE Y NO UN LITERAL SUELTO
# porque `consultar` tiene que reconocerlo: una respuesta anunciada como EXACTA que llega diciendo
# «nada cumple» es la peor forma de la promesa incumplida, y distinguirla es comparar una cadena.
SIN_RESULTADOS_LISTAR = "Nada cumple ese filtro. Prueba aflojando alguno, o usa panorama()."


def _hasta_palabra(txt: str, tope: int) -> str:
    """`txt` recortado a `tope`, cerrando en el último límite de palabra. Nunca crece."""
    if len(txt) <= tope:
        return txt
    corte = txt.rfind(" ", 0, tope)
    return txt[:corte if corte > tope * 2 // 3 else tope].rstrip(" ,;:·|\"'«»([{")


def _desde_palabra(txt: str, ini: int, fin: int) -> str:
    """El tramo `[ini:fin]` movido a límites de palabra por los dos lados. Solo recorta.

    Si el inicio cae dentro de una palabra, se avanza al espacio siguiente; si el final cae dentro
    de una, se retrocede al anterior. Los signos que quedan colgando en los extremos —una comilla
    de cierre sin apertura, una coma inicial— se sacan: son ruido que el lector no puede distinguir
    de un defecto.
    """
    if ini > 0 and txt[ini - 1] not in " \t":
        sig = txt.find(" ", ini)
        if 0 <= sig < fin:
            ini = sig + 1
    if fin < len(txt) and txt[fin] not in " \t":
        ant = txt.rfind(" ", ini, fin)
        if ant > ini:
            fin = ant
    return txt[ini:fin].strip(" ,;:·|\"'«»([{)]}")


def marcar_vencimiento(valor: str | None) -> str:
    """El campo `Vence`, con su vencimiento INTERPRETADO y no solo transcrito.

    El servidor tenía el dato y no lo leía: una sub-entrada pasada de su propia fecha seguía
    diciendo «Estado: vigente» al lado, y en `listar` —el inventario del que depende el sistema de
    delegación— el campo no aparecía nunca. Medido el 2026-08-07: dos sub-entradas vencidas se
    sirvieron así, una de ellas una llave de lectura que había caducado tres días antes.

    Es exactamente el modo de fallo que la especificación declara para el consumidor que ejecuta sin
    dudar: un humano que lee «vence 2026-08-04» hace la cuenta; el que ejecuta, no. Interpretar una
    fecha que ya está escrita no es inventar contenido — es dejar de esconder lo que el dato dice.
    """
    if not valor:
        return ""
    v = str(valor).strip().strip("'\"").rstrip(".")
    try:
        f = datetime.date.fromisoformat(v[:10])
    except ValueError:
        return v
    dias = (datetime.date.today() - f).days
    if dias > 0:
        return f"{v} ⚠ VENCIÓ hace {dias} día(s) — no lo tomes por vigente sin volver a comprobarlo"
    if dias > -8:
        return f"{v} (vence en {-dias} día(s))"
    return v

# Cuántos renglones del listado exacto se pegan dentro de una respuesta de `consultar`. NO limita a
# `listar` llamada directamente —ahí la completitud ES el producto—: limita la copia que viaja
# incrustada en otra respuesta, que además trae debajo la búsqueda por significado.
TOPE_LISTADO_INCRUSTADO = 30


def _recortar_listado(txt: str, etiqueta: str) -> str:
    """Recorta el listado a `TOPE_LISTADO_INCRUSTADO` renglones y DECLARA lo que dejó fuera.

    Se corta en el límite de un renglón —nunca a mitad— y se conservan los encabezados de documento
    de los renglones que sobreviven, para que lo servido siga siendo legible como lo que es.
    """
    lineas = txt.splitlines()
    filas = [i for i, l in enumerate(lineas) if l.lstrip().startswith("· ")]
    if len(filas) <= TOPE_LISTADO_INCRUSTADO:
        return txt
    corte = filas[TOPE_LISTADO_INCRUSTADO]
    fuera = len(filas) - TOPE_LISTADO_INCRUSTADO
    orden = f"listar({etiqueta.replace(' · ', ', ')})" if etiqueta else "listar(...)"
    return ("\n".join(lineas[:corte]).rstrip()
            + f"\n\n… y {fuera} más que cumplen el mismo filtro, recortados acá para que la "
              f"respuesta sea legible.\nPedí la lista completa con `{orden}`: ahí salen todos, sin "
              f"recorte.")


def deducir_desde(pregunta: str, hoy: str) -> str | None:
    """La ventana temporal que la pregunta pide, como fecha ISO desde la cual mirar.

    POR QUÉ HACE FALTA. `listar` acepta `desde` y funciona, pero la deducción no lo componía nunca:
    «qué se cerró HOY» devolvía las 106 secciones resueltas de toda la vida de la base y 26.854
    caracteres. La respuesta era correcta y perfectamente inútil — quien pregunta por hoy y recibe
    todo tiene que filtrar a mano lo que el filtro tenía que filtrar. Tercera iteración pidiéndolo.

    Se deducen solo ventanas que el castellano dice sin ambigüedad. «Últimamente» o «hace poco» no
    entran a propósito: inventarles un número sería ponerle al lector un corte que no pidió.

    LA ASIMETRÍA QUE GOBIERNA LAS DOS DECISIONES DE ABAJO. Una ventana que no se aplica sale
    verbosa: el lector recibe más de lo que pidió y filtra a ojo. Una ventana que se aplica de más
    ESCONDE, y lo que esconde no deja rastro en la respuesta. Ante la duda, no se recorta.
    """
    import datetime as _dt
    q = pregunta.lower()
    base = _dt.date.fromisoformat(hoy)
    # «HOY» Y «AYER» SON TAMBIÉN ADVERBIOS DE ACTUALIDAD, no solo de fecha: «qué problemas hay HOY
    # en la plataforma» pregunta por el estado presente, y contestarla con lo capturado en las
    # últimas horas es esconder el resto. Medido el 2026-08-06: esa consulta fue la ÚNICA de 54
    # repetidas que bajó de nota, porque el filtro se estrechó hasta vaciarse y la respuesta
    # prometida como exacta llegó vacía. Sin el pretérito, «hoy» no acota nada: enuncia el presente.
    # ── VENTANAS DE MENOS DE UN DÍA ────────────────────────────────────────────────────────
    # Se agregan el 2026-08-08 por encargo de Martín: «si hago setenta publicaciones en un día y
    # después pregunto qué se hizo hoy en la tarde, no va a tener cómo responder, porque es
    # demasiada información». Recién ahora tienen sentido: hasta hoy el filtro solo sabía de días,
    # así que deducir una hora no habría tenido dónde aplicarse. Ahora `listar` la acepta y la
    # marca de tiempo por sub-entrada existe (ver `fechas_subentrada`).
    #
    # SE PIDE PRETÉRITO, igual que «hoy» y por el mismo motivo documentado abajo: «qué pasa esta
    # tarde» no es una pregunta por una ventana. Y solo entran las formas que el castellano dice
    # sin ambigüedad — «recién» o «hace un rato» quedan fuera a propósito, porque inventarles un
    # número sería ponerle al lector un corte que no pidió.
    #
    # LA MAÑANA NO SE ACOTA, y es deliberado: `listar` no tiene límite superior, así que «esta
    # mañana» solo podría traducirse a «desde las 00:00», que es lo mismo que «hoy». Devolver eso
    # con nombre de mañana prometería un recorte que no ocurre. Ante la duda, no se recorta.
    if _PRETERITO.search(q):
        m_h = re.search(r"[uú]ltim[ao]s?\s+(\d+)?\s*horas?", q)
        if m_h:
            n_h = int(m_h.group(1)) if m_h.group(1) else 1
            return (_dt.datetime.now() - _dt.timedelta(hours=n_h)).strftime("%Y-%m-%d %H:%M")
        # La tarde y la noche, con los cortes que usa el castellano corriente.
        if re.search(r"\b(esta|hoy\s+(a|en|por)\s+la|de\s+la)\s+tarde\b|\bhoy\s+.{0,12}tarde\b", q):
            return f"{hoy} 12:00"
        if re.search(r"\b(esta|hoy\s+(a|en|por)\s+la|de\s+la)\s+noche\b", q):
            return f"{hoy} 19:00"

    if re.search(r"\b(hoy|ayer)\b", q) and _PRETERITO.search(q):
        return hoy if "hoy" in q else (base - _dt.timedelta(days=1)).isoformat()
    m = re.search(r"[uú]ltim[oa]s?\s+(\d+)\s+d[ií]as?", q)
    if m:
        return (base - _dt.timedelta(days=int(m.group(1)))).isoformat()
    # «LOS ÚLTIMOS DÍAS», SIN NÚMERO. El patrón de arriba exige un dígito, así que «qué se resolvió
    # en los últimos días» no traía ventana: devolvía 110 secciones y 33.693 caracteres, la
    # respuesta más larga de las 72 de la tanda del 2026-08-06, y creciendo iteración a iteración.
    # Entra —a diferencia de «últimamente»— porque nombra la unidad, «días», y solo le falta el
    # número; y la ventana elegida no queda escondida: `listar` imprime `desde=<fecha>` en su
    # criterio y la respuesta exacta la trae en su etiqueta, así que el lector ve el corte y puede
    # pedir otro. Siete días, el mismo valor que «esta semana», por no inventar una tercera unidad.
    # «LA SEMANA PASADA» — medido el 2026-08-07: la evaluación preguntó «qué se resolvió desde la
    # semana pasada» y devolvió las 101 secciones resueltas de toda la historia, mientras la misma
    # pregunta con «esta semana» acotaba bien. Es la forma más natural en castellano para la ventana
    # que el informe semanal necesita, y es la que dirección usa. Se agrega a la rama que ya existe
    # —siete días, la misma unidad— en vez de inventar una ventana nueva.
    if re.search(r"(esta|[uú]ltima)\s+semana|semana\s+pasada|[uú]ltimos\s+siete\s+d[ií]as"
                 r"|(los\s+[uú]ltimos|estos)\s+d[ií]as", q):
        return (base - _dt.timedelta(days=7)).isoformat()
    if re.search(r"(este|[uú]ltimo)\s+mes|[uú]ltimos\s+treinta\s+d[ií]as", q):
        return (base - _dt.timedelta(days=30)).isoformat()
    return None


def deducir_filtro(pregunta: str) -> tuple[str | None, str | None]:
    """De una pregunta por propiedad, el `(estado, tipo)` con que se contesta exacta.

    El estado manda sobre el tipo cuando la pregunta dice las dos cosas —«qué problemas quedan
    abiertos»— porque es el filtro más restrictivo.

    Y CUANDO LA PALABRA DEL LECTOR IMPLICA VIGENCIA, el estado va JUNTO con el tipo. Preguntar «qué
    problemas hay» y recibir los hallazgos resueltos mezclados con los vivos no es una respuesta
    exacta: es una lista donde hay que filtrar a mano lo que el filtro tenía que filtrar. Medido el
    2026-08-05 contra el servidor real: `tipo=hallazgo` solo devuelve 153 secciones; sumando
    `estado=vigente`, 97 — las que de verdad están abiertas.
    """
    q = pregunta.lower()
    # LA NEGACIÓN INVIERTE LA PREGUNTA, y sin mirarla la respuesta era la opuesta a la pedida.
    # «Qué está mal y todavía NO se arregló» disparaba con «arregló» y devolvía las 103 secciones
    # RESUELTAS: exactamente lo contrario, servido como respuesta exacta y con el aire de autoridad
    # que tiene una lista completa. Tres iteraciones seguidas lo pidieron. Es el peor error posible en
    # esta función, porque no falla ni se queda corta: contesta lo inverso.
    # Y LA LISTA DE FORMAS DE NEGAR NO ALCANZABA. Se enumeraban tres —«no se resolvió», «todavía
    # no», y el literal «sin arreglar»— y el castellano tiene más: «sin cerrar» caía en la rama
    # positiva de abajo por su `cerr` y devolvía lo RESUELTO, y «sin solucionar» no deducía nada.
    # Medido el 2026-08-06 ejecutando la función. Se generaliza a `sin <verbo>` con los verbos que
    # esta función ya conoce, en vez de agregar la cuarta excepción a una lista que el castellano
    # siempre va a poder desbordar con una palabra más.
    # LAS DOS RAMAS COMPARTEN LA MISMA LISTA DE VERBOS, y eso no es elegancia: es la única forma de
    # que no se separen. El 2026-08-06, al agregar «logró/completó/entregó» a la rama positiva sin
    # tocar la negativa, «qué NO se logró todavía» pasó a contestar `resuelto` — el mismo error
    # inverso que esa misma iteración acababa de arreglar, reintroducido en el acto de arreglarlo.
    # Con una lista sola, agregar un verbo lo agrega a las dos caras o a ninguna.
    # LA PERÍFRASIS ROMPÍA LA NEGACIÓN, y con eso la respuesta salía INVERTIDA. El patrón enumeraba
    # los auxiliares —«no se», «no ha», «no fueron»— y el castellano tiene muchos más: «qué problemas
    # NO SE VAN A arreglar» y «qué NO SE PUDO cerrar» caían fuera y devolvían lo RESUELTO. Medido el
    # 2026-08-07 ejecutando la función. Es la cuarta vez que esta lista se desborda con una forma que
    # nadie había escrito, así que se deja de enumerar: se admite un HUECO ACOTADO entre el «no» y el
    # verbo, igual que `_POR_PROPIEDAD` ya hace con `.{0,14}` para el mismo problema.
    #
    # Acotado y no libre: sin tope, un «no» de una oración alcanzaría el verbo de la siguiente.
    if re.search(rf"\bno\s+(?:\w+\s+){{0,3}}?({_TERMINADO}|{_ARRANCADO})", q) or \
       re.search(r"(todav[ií]a|aun|a[úu]n)\s+no\b", q) or \
       re.search(r"\bsin\s+(resolver|resuelto|arreglar|cerrar|solucionar|terminar|lograr|"
                 r"conseguir|completar|entregar|avanzar|terminado)", q):
        # LA NEGACIÓN YA NO CONTESTA LO INVERSO, PERO TAMPOCO CONTESTABA LO PEDIDO. Devolvía
        # `estado=abierto` y ningún tipo, así que «qué problemas todavía no se arreglaron» traía
        # todos los compromisos abiertos —planes, pedidos de acceso, preguntas— y ni un hallazgo.
        # Medido el 2026-08-07: tres preguntas con negación de la tanda recibieron una lista que no
        # respondía. La deducción se quedaba a mitad de camino: acertaba el estado y perdía el tema.
        #
        # Y NO SE COMBINA `abierto` CON `tipo=hallazgo`, que es lo que parecía obvio: los hallazgos
        # viven en el polo de los hechos, donde el estado es `vigente`, no `abierto`. Esa combinación
        # devuelve CERO secciones bajo un encabezado que promete respuesta exacta —peor que una lista
        # de más—. Un problema que no se arregló ES un hallazgo vigente, y así se contesta, igual que
        # la rama de más abajo ya lo hacía para la forma afirmativa de la misma pregunta.
        #
        # Y SOLO SI LA PREGUNTA NO NOMBRA OTRO TIPO. «Qué planes para arreglar problemas no
        # arrancaron» nombra los dos, y ahí el sujeto es el plan: deducir `hallazgo` porque aparece
        # la palabra «problemas» sería quedarse con el complemento, que es el error que esta misma
        # función ya cometió con «qué falta para cerrar la compra».
        if (re.search(r"problema|riesgo|falla|defecto|hallazgo", q)
                and not re.search(r"\bplan|pedido|acceso|pregunta|compromiso|tarea", q)):
            return "vigente", "hallazgo"
        return "abierto", None
    # LO QUE FALTA MANDA SOBRE EL VERBO QUE LO ACOMPAÑA, así que `falta` y `queda` viajan acá
    # arriba y no en la rama de más abajo: «qué falta para cerrar la compra» disparaba `cerr` y le
    # servía a dirección las 95 secciones RESUELTAS. Medido el 2026-08-06. Es el sujeto de la
    # pregunta, no su complemento.
    if re.search(r"\bfalta|\bqueda[nr]?\b|\brestan?\b", q):
        return "abierto", None
    # «QUÉ SE LOGRÓ ESTA SEMANA» ES LA PREGUNTA CANÓNICA DE DIRECCIÓN, y no deducía ningún estado:
    # devolvía 145 secciones con lo abierto y lo resuelto mezclados, bajo el encabezado que promete
    # una respuesta exacta. Un logro es algo terminado; mezclarlo con lo que está en curso es
    # contestar otra pregunta. Medido el 2026-08-06.
    # Va DESPUÉS de las ramas de negación y de `falta|queda` a propósito: «qué falta para lograr X»
    # ya se resolvió como abierto ahí, y esta no puede ganarle.
    if re.search(rf"({_TERMINADO})", q):
        return "resuelto", None
    # `propuesto` es un estado real del corpus —17 planes esperando decisión de Martín, o sea justo
    # los que el sistema de delegación NO puede empezar— y no tenía rama: preguntarlo devolvía los
    # abiertos. Va antes que la rama de lo abierto porque «esperando una decisión» calza con las
    # dos y la más específica gana.
    #
    # Y NO CAPTURA «esperando una decisión» a secas, aunque sea la forma natural de nombrarlos: eso
    # también describe algo TRABADO, que es otra cosa —lo trabado ya empezó—. El detector por
    # propiedad tiene un caso que lo fija («qué está trabado esperando una decisión» → abierto) y se
    # respetó en vez de reescribirlo: bajar el listón para que un cambio propio pase es falsear la
    # medición. Pide el nombre del estado, o la forma que solo aplica a lo que aún no arrancó.
    if re.search(r"propuest|sin (aceptar|aprobar)|"
                 r"esperando (el |la )?(visto bueno|aprobaci[oó]n)", q):
        return "propuesto", None
    # `\bqueda` con límite de palabra: sin él, `queda` calzaba dentro de «busqueda», así que TODA
    # pregunta sobre el buscador de esta base se contestaba con la lista de lo pendiente.
    # Comprobado el 2026-08-06 con cuatro formulaciones distintas: las cuatro daban `abierto`.
    if re.search(r"abierto|pendiente|sin\s+resolver|\bqueda|trabado|frenado|"
                 r"detenido|esperando|bloqueado", q):
        return "abierto", None
    # LO QUE HAY QUE PREGUNTARLE A ALGUIEN ES, LITERALMENTE, LO QUE ESPERA DE ESA PERSONA. El tipo
    # `requerido` es el único cuyas sub-entradas declaran `Espera a`, así que la pregunta canónica de
    # antes de una reunión —«qué tengo que preguntarle al Project Manager cuando lo vea»— tiene un
    # filtro exacto y no lo deducía: se contestaba por tema, con seis documentos que no dicen a quién
    # espera nada. El caso que lo vigilaba pasaba en verde por casualidad, según qué fragmentos
    # trajera el buscador, y al cambiar de modelo se destapó.
    #
    # SIN ESTADO A PROPÓSITO: lo pendiente y lo ya resuelto con esa persona son ambos material de una
    # reunión —«esto quedó cerrado» es tan reportable como «esto sigue trabado»—, y la ficha de cada
    # sección declara el suyo. Es la misma consulta cuyos siete resultados tres iteraciones leyeron como
    # pendientes estando cerrados; por eso `listar` ahora advierte que los estados se cuentan.
    # Y SOLO LOS VERBOS DE PEDIR, no los de mostrar: «qué le puedo MOSTRAR al fundador» es otra
    # pregunta —lo presentable, que se filtra por `mostrable`— y «qué tengo que PREGUNTARLE» es lo
    # que lo espera a él. Meterlas en la misma rama las contesta igual y son distintas; lo cazó el
    # caso del detector que ya fijaba la primera.
    if re.search(r"\b(preguntar|preguntarle|pedirle|consultarle|reclamarle)\b"
                 r".{0,24}\b(fundador|direcci[oó]n|project\s*manager|\bpm\b|jefe)", q):
        return None, "requerido"
    if re.search(r"problema|riesgo|falla|defecto|hallazgo", q):
        return "vigente", "hallazgo"
    return None, None


def crear_servidor(idx: Indice, herramientas: list[str] | None = None,
                   descripcion: str | None = None, cierre: str | None = None,
                   ambitos_texto: str | None = None) -> FastMCP:
    """Un servidor MCP por KB. Las tres herramientas se cierran sobre su indice.

    `herramientas` acota cuales se registran (None = todas). Se usa para servir la
    misma KB en mas de un nivel de acceso: cada nivel recibe su propio indice —ya
    acotado por Indice.restringir()— y su propia lista. Una herramienta que no se
    registra no existe para ese cliente: no aparece en el listado ni se puede invocar,
    que es mas fuerte que comprobar un permiso al ejecutarla."""
    cfg = idx.cfg
    permitida = (lambda n: True) if herramientas is None else (lambda n: n in herramientas)
    def alias_visible(directorio: str) -> str:
        """El alias con que se nombra un polo al agente: el declarado en mcp.yaml si
        lo hay, si no el nombre de la carpeta. (Un polo tiene siempre al menos dos
        entradas en `alias` —la declarada y la del directorio—; mostrarlas todas, o
        filtrar por 'difiere del directorio', dejaba polos fuera de la lista.)"""
        declarados = sorted(a for a, d in cfg.alias.items()
                            if d == directorio and a != normalizar(directorio))
        return declarados[0] if declarados else normalizar(directorio)

    ambitos = " · ".join(f"'{alias_visible(d)}' = {cfg.polos[d]}"
                         for d in sorted(cfg.polos)) or "sin ámbitos"

    # Que trata esta KB, en una linea. Va en las instrucciones del servidor y como
    # cabecera de cada herramienta: es lo que permite al agente decidir si esta
    # pregunta es para esta base o no.
    # Dos fuentes que se suman: lo que la KB declara de si misma (kb/mcp.yaml, opcional
    # y estable) y lo que se deduce de su grafo (siempre al dia, sin mantencion). Ni una
    # ni otra es obligatoria; con las dos la descripcion es precisa Y no envejece.
    # Forma segun la guia de Anthropic para descripciones de herramientas ("Define
    # tools" / "Writing tools for agents"): la descripcion es el factor que mas pesa
    # en que el agente elija bien, y debe decir QUE hace, CUANDO usarla, cuando NO, y
    # que NO devuelve —haciendo explicito el contexto que uno da por sabido, incluida
    # la terminologia de nicho. Por eso el dominio se nombra aqui y no se espera que
    # el agente lo infiera del nombre del conector, que lo elige quien lo instala.
    centrales = temas_centrales(idx)
    dominio = (
        f"«{cfg.nombre}» — colección de {len(idx.nodos)} documentos"
        # `split()`+`join`: el texto viene de un bloque YAML plegado, que deja un salto
        # de línea al final. Ese salto quedaba ANTES del punto —«…decisiones)\n.»— y el
        # cliente cortaba ahí la descripción, dejándola partida a media frase. Visto el
        # 2026-07-30 en el conector de claude.ai: llegaba hasta «como líder…».
        #
        # `descripcion` puede venir del NIVEL. Un nivel no es la misma base con menos
        # filas: es otra cosa para otro lector. La recortada la lee quien financia el
        # trabajo, y describirla con las palabras del nivel completo —«compromisos
        # vivos de Martín», «madurez desigual»— le habla de la cocina en vez de del
        # plato. Peor: cualquier insinuación de que hay una versión con más contenido
        # convierte una herramienta que debía dar alivio en una que da sospecha.
        + (f" sobre {' '.join(str(descripcion or cfg.descripcion).split())}"
           if (descripcion or cfg.descripcion) else "")
        + ". "
        + (f"Cubre, entre otros: {', '.join(centrales)}. " if centrales else "")
        + "Es la fuente propia del equipo sobre ese dominio, con su vocabulario y sus "
          "fuentes: consúltala siempre que la pregunta caiga ahí, incluso si crees "
          "saber la respuesta, porque aquí está la versión vigente y contrastable. "
          "No la uses para preguntas ajenas a ese dominio: no contiene conocimiento "
          "general ni el contenido de otras bases, y no devuelve nada que no esté "
          f"escrito en ella. Ámbitos para acotar la búsqueda: {ambitos_texto or ambitos}. "
          "Es de solo lectura: ninguna de sus herramientas modifica la base."
    )

    # El parrafo de herramientas se ARMA con las que este nivel declara de verdad.
    # Estuvo escrito a mano hasta el 2026-07-30 y decia siempre «Tres herramientas:
    # consultar, leer, panorama». En el nivel recortado eso era falso por los dos
    # lados: `panorama` no se declara ahi, y `listar` —que si se declara, y es la que
    # contesta «que esta esperando de mi»— no se nombraba. Es decir, la unica
    # instruccion que el cliente lee le prometia una herramienta inexistente y le
    # escondia una util. Un texto fijo describiendo algo variable envejece solo.
    COMO_SE_USA = {
        "consultar": "`consultar` para preguntar sin saber dónde está la respuesta",
        "leer": "`leer` para el texto íntegro de un documento que ya sabes cómo se llama",
        "listar": "`listar` para filtrar por propiedades —qué está abierto, qué se "
                  "resolvió, de qué tipo— en vez de por tema",
        "panorama": "`panorama` para ver qué cubre la base o el mapa de un tema",
    }
    disponibles = [t for t in COMO_SE_USA if permitida(t)]
    CUANTAS = {1: "Una herramienta", 2: "Dos herramientas", 3: "Tres herramientas",
               4: "Cuatro herramientas"}
    parrafo_herramientas = (
        f"{CUANTAS.get(len(disponibles), f'{len(disponibles)} herramientas')}, en orden "
        f"de uso habitual: {'; '.join(COMO_SE_USA[t] for t in disponibles)}. "
    ) if disponibles else ""

    # Lo que se incrusta en el PRIMER párrafo de cada herramienta: el nombre de la base
    # y el núcleo de su dominio, en dos frases. No puede ser el párrafo largo —no cabe—
    # ni puede faltar —el cliente puede no entregar las instrucciones del servidor—.
    # El núcleo se saca de la descripción cortándola en su primera raya: la descripción
    # está escrita como «núcleo — desglose», así que lo de antes de la raya es el
    # resumen que ya existe, sin pedir un campo nuevo que alguien tendría que mantener
    # al día aparte (y que envejecería sin que nada avise).
    etiqueta = f"«{cfg.nombre}»"
    resumen = " ".join(str(descripcion or cfg.descripcion or "").split())
    resumen = re.split(r"\s+[—–]\s+", resumen)[0]
    if len(resumen) > 110:
        resumen = resumen[:107].rsplit(" ", 1)[0] + "…"
    contexto = (f"Son {len(idx.nodos)} documentos"
                + (f" sobre {resumen}" if resumen else "")
                + ". Solo lectura; no devuelve nada que no esté escrito ahí.")

    mcp = FastMCP(cfg.slug, instructions=(
        f"{dominio}\n\n"
        f"{parrafo_herramientas}"
        + (cierre or
           "Cada resultado trae su fecha de última actualización y los documentos "
           "relacionados, para seguir el hilo sin volver a buscar. Es de solo "
           "lectura: no hay forma de modificar esta colección desde aquí. El contenido es "
           "una obra en curso de madurez desigual; cita las fuentes que cada documento "
           "declara cuando la respuesta vaya a sostener una decisión.")
    ))

    def registrar(fn):
        """Registra la herramienta solo si este nivel la incluye. Si no, la funcion
        queda definida pero nunca se declara al cliente: no aparece en el listado ni
        se puede invocar."""
        # Anotaciones: el protocolo tiene campos para declarar que una herramienta no
        # modifica nada y no sale al mundo. Decirlo así es más fuerte que prometerlo en
        # la prosa —un cliente puede mostrarlo o actuar sobre ello, y no depende de que
        # el modelo lea la descripción hasta el final, que es justo lo que no pasa
        # cuando el texto se recorta. Recomendación de la guía de Anthropic sobre
        # escribir herramientas para agentes (2026).
        return mcp.tool(annotations=ToolAnnotations(
            readOnlyHint=True,      # ninguna de las cuatro escribe en la base
            destructiveHint=False,
            idempotentHint=True,    # la misma llamada devuelve lo mismo
            openWorldHint=False,    # el universo es esta base y nada más
        ))(fn) if permitida(fn.__name__) else fn

    # Preguntas por PROPIEDAD (estado, tipo, fecha) que la búsqueda por significado
    # contesta mal por diseño: devuelve lo más parecido, no todo lo que cumple. En vez
    # de confiar en que quien consulte se acuerde de `listar`, el servidor lo detecta y
    # lo dice en la respuesta. Que una sesión nueva use bien la base no puede depender
    # de que haya leído la documentación (decisión de Martín, 2026-07-29).
    POR_PROPIEDAD = _POR_PROPIEDAD

    @registrar
    @con_dominio(etiqueta, contexto)
    def consultar(pregunta: str, ambito: str | None = None,
                  orden: str = "relevancia", limite: int = 6,
                  detalle: str = "normal") -> str:
        """Busca en {base} y devuelve los fragmentos que responden a la pregunta.

        Empieza siempre por acá cuando tengas una pregunta y no sepas en qué documento
        está la respuesta. Si ya sabes el título del documento, usa `leer`; si quieres
        ver qué hay antes de preguntar, usa `panorama`.

        Escribe la pregunta en lenguaje natural. Singular y plural, género y tildes
        son indiferentes ("gestion" halla "Gestión"), y encuentra por significado
        aunque tu pregunta no comparta ninguna palabra con el texto; para exigir una
        frase textual, enciérrala en comillas dobles.

        Devuelve, por documento: su título, su categoría, la fecha en que se actualizó
        por última vez, el fragmento que responde, y los títulos de los documentos
        relacionados (para seguir el hilo con `leer` sin volver a buscar). NO devuelve
        el texto completo —para eso llama a `leer` con el título que esta te dio— ni
        completa con conocimiento externo: si no encuentra nada, esa respuesta es
        informativa.

        SI LO QUE LLEGÓ NO RESPONDE, NO TE RINDAS EN EL PRIMER INTENTO: medido sobre 81
        preguntas reales, la primera consulta trae el documento correcto 3 de cada 4
        veces, y quien insiste llega a 9 de cada 10. En ese orden, que va de lo barato a
        lo caro:
          1. Repetí con `limite=20`. Es lo que más rescata: la mitad de lo que falta
             aparece ahí, porque pedir más no es solo ver más — cambia qué considera el
             buscador.
          2. Si tu pregunta es por una PROPIEDAD y no por un tema —qué está abierto, qué
             se resolvió, qué espera una decisión, qué hay desde tal fecha— usá `listar`.
             Esa devuelve TODAS las que cumplen, sin ranking y sin omitir ninguna; acá,
             en cambio, competís contra el resto por seis lugares.
          3. Mirá `panorama` sin argumentos para ver qué cubre esta colección, o con un
             tema para su mapa, y volvé a preguntar con las palabras que usa la casa.
             Preguntar dos veces con vocabulario distinto rinde más que una pregunta larga.
          4. Y si tras eso no aparece, decilo así: que esta colección no lo cubre. Es una
             respuesta útil y verificable, y es preferible a completar con lo más parecido.

        Parámetros:
          pregunta: la consulta en lenguaje natural (obligatoria).
          ambito: acota la búsqueda a una categoría; si te equivocas, te devuelve las
                  disponibles. Omítelo para buscar en todo.
          orden: 'relevancia' (por defecto) o 'reciente'. 'reciente' cuando la
                 intención es temporal —«lo último sobre X»—.
          limite: documentos a devolver (1–20, por defecto 6).
          detalle: 'normal' (por defecto) o 'extendido' —fragmento ~3× más largo y el
                 doble de documentos relacionados, para que una sola llamada rinda más—.
        """
        extendido = normalizar(detalle).startswith("extend")
        polo, aviso = None, ""
        if ambito:
            polo = cfg.alias.get(normalizar(ambito))
            if not polo:
                # Degradar a busqueda global en vez de fallar: si el agente pasa un
                # ambito que esta KB no tiene, es mejor responder algo util y avisar
                # que devolver un error y dejarlo sin nada.
                aviso = f"(No reconocí el ámbito «{ambito}»; busqué en toda la base.)\n\n"

        n = max(1, min(limite, 20))
        reciente = normalizar(orden).startswith("recien")
        # Con orden reciente el pozo debe ser generoso: se trae mucho match lexico y
        # luego la fecha decide. Asi "bitácoras recientes" incluye las bitacoras aunque
        # no sean lo mas relevante por tema (comparten el termino, no el ranking top).
        tope_lex = 60 if reciente else 12
        filtros, args = [], [idx.expandir(pregunta)]
        if polo:
            filtros.append("AND polo = ?")
            args.append(polo)
        try:
            # El indice lexico es compartido entre niveles (se construye una vez), asi
            # que se filtra por las entradas visibles de ESTE nivel.
            # Sobre SUB-ENTRADAS, quedándose con la mejor posición de cada entrada. Es la
            # cara léxica de lo que la capa semántica ya hacía: decidir en la unidad
            # atómica y devolver el padre. Sobre el índice por entrada, una nota corta y
            # exacta perdía contra la dilución de una entrada de 40.000 caracteres.
            vistos: dict[str, None] = {}
            for fila in idx.db.execute(
                    f"SELECT nombre FROM subdocs WHERE subdocs MATCH ? "
                    f"{' '.join(f.replace('docs.', 'subdocs.') for f in filtros)} "
                    f"ORDER BY rank LIMIT {tope_lex * 4}", args).fetchall():
                if fila[0] in idx.nodos and fila[0] not in vistos:
                    vistos[fila[0]] = None
                    if len(vistos) >= tope_lex:
                        break
            lexico = list(vistos)
            if not lexico:
                # Respaldo: el índice por entrada. Una consulta cuyos términos se reparten
                # entre varias sub-entradas puede no calzar en ninguna y sí en la entrada.
                lexico = [f[0] for f in idx.db.execute(
                    f"SELECT nombre FROM docs WHERE docs MATCH ? {' '.join(filtros)} "
                    f"ORDER BY rank LIMIT {tope_lex}", args).fetchall() if f[0] in idx.nodos]
        except sqlite3.OperationalError:
            # Antes esto abortaba la consulta entera con «no pude interpretar». Pero la
            # capa semantica no depende de la sintaxis de FTS5 y sigue sirviendo: se
            # degrada a ella en vez de dejar al que pregunta sin nada. La causa habitual
            # —puntuacion castellana confundida con operadores— se corrigio en
            # OPERADORES el 2026-07-30; esto es la red por si aparece otra.
            lexico = []

        semantico = [s for s in idx.semejantes(pregunta)
                     if not polo or idx.nodos[s].polo == polo]

        # Senal por nombre. Dos formas, de mas a menos fuerte:
        #  (a) el nombre es subcadena de la pregunta o viceversa (match casi exacto);
        #  (b) el nombre comparte >=2 raices de contenido con la pregunta —asi
        #      "Certificado de Valorización" gana para "documento que certifica la
        #      valorización" aunque el titulo no aparezca literal en la consulta.
        objetivo = normalizar(pregunta)
        raices_preg = {raiz(p) for p in PALABRA.findall(pregunta)
                       if idx.frecuencia.get(raiz(p), 0.0) <= 0.5}
        subcadena, por_palabras = [], []
        for nom in idx.nodos:
            if polo and idx.nodos[nom].polo != polo:
                continue
            nn = normalizar(nom)
            if objetivo in nn or nn in objetivo:
                subcadena.append(nom)
            elif len(raices_preg & {raiz(p) for p in PALABRA.findall(nom)}) >= 2:
                por_palabras.append(nom)
        subcadena.sort(key=len)
        por_palabras.sort(
            key=lambda nom: -len(raices_preg & {raiz(p) for p in PALABRA.findall(nom)}))
        por_nombre = subcadena + por_palabras

        # Piso de pertinencia. La capa semantica SIEMPRE devuelve los vecinos mas cercanos,
        # por lejos que esten: sin este corte la base contesta con aplomo "receta de pan de
        # masa madre" y quien pregunta —cada vez mas seguido, otra IA— no tiene como saber
        # que no habia nada. Se descarta solo si se cumplen las TRES condiciones: ninguna
        # coincidencia literal, ningun nombre de entrada parecido, y similitud por debajo del
        # piso. Un corte por similitud a secas no servia: medida sobre dos bases reales, la
        # franja de lo pertinente en una se solapa con la de lo ajeno en la otra. Exigir
        # ademas cero senal lexica y de nombre deja pasar toda pregunta con vocabulario del
        # dominio, que es el caso normal.
        if not lexico and not por_nombre and idx.vectores is not None:
            cercania = idx.cercania_maxima(pregunta)
            # 0.15 es deliberadamente bajo. Medido sobre dos bases reales, la franja de lo
            # pertinente empieza cerca de 0.26 y la de lo ajeno llega hasta 0.25: no hay corte
            # limpio. Ante esa superposicion se prefiere el falso positivo —devolver algo
            # flojo, que quien pregunta puede descartar— sobre el falso negativo: negar una
            # pregunta legitima es el error caro. Con 0.30 la base llegaba a rechazar "que
            # problemas de seguridad hay". Asi solo se corta lo inequivocamente ajeno; lo del
            # dominio vecino (otra herramienta de software) igual pasa, y esa es una
            # limitacion conocida que se atrapa en la capa de juicio, no aqui.
            # EL PISO SE SUBIÓ A 0,22, Y EL NÚMERO VIEJO ERA DE OTRAS BASES. El comentario de
            # arriba lo midió «sobre dos bases reales» y concluyó que la franja de lo pertinente
            # empieza en 0,26 y la de lo ajeno llega a 0,25 — sin corte limpio. En ESTA base, medido
            # el 2026-08-07, la separación es ancha: las dos consultas ajenas del catálogo dan 0,1575
            # («capital de Francia») y 0,1533 («receta de pan de masa madre»), y la legítima más
            # barata que existe —«qué problemas de seguridad hay», sin ninguna señal de nombre— da
            # 0,3005. Entre 0,16 y 0,30 no hay nada.
            #
            # 0,22 queda en el medio de ese hueco, con 0,08 de margen bajo la legítima más floja. NO
            # se sube más: a 0,30 la base rechazaba esa pregunta, y negar una legítima es el error
            # caro — el mismo criterio que puso 0,15 en su momento, con datos nuevos.
            #
            # Se comprobó contra las 81 preguntas juzgadas de `tools/pertinencia.py`: cero denegadas.
            # La perilla existe para volver a medirlo cuando el corpus vuelva a mover la escala.
            #
            # ⚠ LOS DOS EJEMPLOS DE ARRIBA NO LLEGAN ACÁ, y por eso esta calibración describe menos
            # de lo que parece. Medido el 2026-08-07 sobre 16 sondas: «capital de Francia» (0,1575) y
            # «receta de pan de masa madre» (0,1533) están bajo el piso y NO se niegan, porque este
            # bloque está detrás de `not lexico` y las dos calzan literalmente por alguna palabra
            # («capital», «receta»). O sea que el número no las corta: las corta —o no— la señal
            # léxica, antes.
            #
            # Y con el piso real ninguna sonda medida alcanza esta rama: las únicas que pasan el
            # filtro léxico son palabras raras sueltas y frases como «la crin de un caballo», y esas
            # dan 0,30 de cercanía, arriba del piso. EN OPERACIÓN ESTA RAMA NO DISPARA HOY. No se
            # retira —es la defensa de último recurso si el AVISO cambia— y queda cubierta por
            # `NEG-001`, que la alcanza a propósito moviendo el piso. Lo que se retira es la
            # impresión de que 0,22 está filtrando algo: hoy filtra el AVISO, que sí dispara.
            if cercania is not None and cercania < float(os.environ.get("KB_PISO", "0.22")):
                return (f"No encontré nada sobre «{pregunta}» en esta base. "
                        "Es una respuesta informativa: esta base no cubre ese tema.")

        # AVISO de posible fuera-de-dominio (2026-07-27, tercera evaluación). Tres personas
        # reales hicieron preguntas legítimas que esta base no cubre —costos, idiomas, borrado
        # de datos— y recibieron seis resultados de relleno indistinguibles de una respuesta.
        # El corte duro de arriba no los atrapa (0.15 es solo para lo inequívocamente ajeno) y
        # suprimir resultados sería el error caro. Esto es distinto: un AVISO encabezando la
        # respuesta, con los resultados intactos debajo. Señal COMBINADA, medida ese día sobre
        # 4 preguntas fuera + 8 dentro (0 falsos avisos): algún concepto de la pregunta no
        # existe en el índice léxico, Y la cercanía semántica queda bajo 0.32 — cada señal por
        # separado ya se probó antes y no separaba (la nota de abajo documenta ese intento).
        # El margen es delgado (0.300 fuera vs 0.344 dentro): si aparece un falso aviso, se
        # recalibra con esa medición, no a ojo.
        if idx.vectores is not None:
            # Los grupos se reconstruyen con la MISMA regla que expandir() —termino
            # informativo → sus formas conocidas— en vez de parsear su texto: el texto
            # mezcla grupos con parentesis y terminos sueltos con comodin, y parsearlo
            # se rompia justo en las preguntas que mas importaba atrapar.
            terminos_inf = [p for p in PALABRA.findall(pregunta)
                            if normalizar(p) not in VACIAS]
            sin_calce, grupos_fts = 0, []
            for termino in terminos_inf:
                formas = idx.vocabulario.get(raiz(termino), set()) | {normalizar(termino)}
                consulta_g = " OR ".join(f'"{f}"' for f in sorted(formas))
                grupos_fts.append(consulta_g)
                try:
                    if not idx.db.execute("SELECT 1 FROM docs WHERE docs MATCH ? LIMIT 1",
                                          (consulta_g,)).fetchone():
                        sin_calce += 1
                except sqlite3.OperationalError:
                    pass
            if grupos_fts and sin_calce:
                cercania = idx.cercania_maxima(pregunta)
                # EL UMBRAL ES DEL MODELO, NO DEL SISTEMA. 0,32 se calibró sobre la escala del
                # modelo estático, y una escala no viaja entre codificadores: medido el 2026-08-07,
                # con MiniLM las preguntas ajenas llegan a 0,408 y las legítimas bajan hasta 0,162
                # —se solapan—, así que ningún número separa las dos por sí solo. Lo que sí separa
                # es la CONJUNCIÓN con la señal léxica, y por eso el umbral se volvió perilla:
                # se recalibra por medición cuando cambia el modelo, no a ojo.
                if sin_calce == len(grupos_fts) or (
                        cercania is not None and cercania < _umbral_aviso()):
                    aviso += ("⚠ Puede que esta base no cubra lo preguntado: parte "
                              "de la pregunta no calza con nada de lo escrito. Los "
                              "resultados de abajo son lo más cercano, no una "
                              "respuesta confirmada.\n\n")

        # NOTA (2026-07-27) — se probó y se descartó un aviso de "respuesta solo por parecido":
        # marcar la respuesta cuando ninguna entrada menciona literalmente lo preguntado, para
        # que un nivel restringido no devuelva relleno indistinguible de una respuesta real.
        # Ninguna variante alcanzó una señal confiable (la mejor acertó 6 de 11 casos): el
        # nombre de quien mantiene la base aparece en casi todas sus entradas y basta para
        # anclar cualquier consulta, y acotar el anclaje a términos raros arrastró falsos
        # avisos sobre preguntas legítimas. Tampoco sirve un corte por similitud: medido sobre
        # casos reales, una pregunta CON respuesta puntuó 0,194 y una SIN respuesta 0,217.
        # Sin un reranker —descartado por la regla de no meter un modelo en el camino de
        # servir— no hay escala de relevancia calibrada. Queda como limitación conocida: la
        # detecta la capa de juicio de la evaluación, no el servidor.
        puntaje: dict[str, float] = {}
        for ranking, peso in ((por_nombre[:5], 1.6), (semantico, 1.0), (lexico, 0.6)):
            for pos, nom in enumerate(ranking):
                puntaje[nom] = puntaje.get(nom, 0.0) + peso / (10 + pos)

        # Difusion por el grafo curado: los vecinos de los mejores resultados reciben un
        # aporte. Es la ventaja de esta KB —wikilinks puestos a mano— aplicada al ranking:
        # preguntar "empresa del fundador" trae SAUCO porque es vecina de "Mercado del NFU",
        # aunque su texto no diga "fundador". Se excluyen los hubs (muchos vecinos) para no
        # arrastrar nodos-indice genericos, y el aporte es pequeño: reordena, no manda.
        # El umbral de hub es PROPORCIONAL al corpus. Fijo en 25 estaba calibrado para una
        # base de ~176 entradas; en una de 16 ningun nodo lo alcanza, asi que su indice
        # principal difundia hacia todo y ganaba cualquier consulta puntual. La cota
        # superior de 25 deja intactas las bases grandes (130 y 176 entradas dan 25 igual).
        # Un hub se define por la FRACCION del corpus con que conecta, no por un conteo suelto:
        # con 20% (len//5) una entrada de contenido bien enlazada cruzaba el umbral apenas la
        # base crecia y se hundia sola —paso de verdad: al llegar a 7 vecinos sobre 19 entradas,
        # el nodo de pedidos abiertos quedaba penalizado y desaparecia de las consultas que mas
        # importaban—. Un hub real conecta con cerca de la mitad de todo. La cota de 25 deja
        # intactas las bases grandes (130 y 176 entradas dan 25 igual).
        umbral_hub = max(6, min(25, int(len(idx.nodos) * 0.45)))
        cabeza = sorted(puntaje, key=lambda x: -puntaje[x])[:8]
        for nom in cabeza:
            vecinos = idx.relacionados(nom)
            if len(vecinos) > umbral_hub:  # hub: conecta con casi todo, su vecindad no informa
                continue
            for v in vecinos:
                if not polo or idx.nodos[v].polo == polo:
                    puntaje[v] = puntaje.get(v, 0.0) + 0.12 * puntaje[nom]

        # Boost a los indices de directorio (§R3). Un indice YA enumera a sus hijos en
        # su seccion Inventario, asi que es la respuesta canonica a preguntas de listado
        # ("¿qué proyectos hay?", "lista de X"). Boost fuerte si la pregunta pide enumerar,
        # suave en general —para que un indice relevante suba pero no ahogue a un nodo
        # concreto cuando se pregunta por una cosa puntual.
        # SOLO cuando la pregunta pide enumerar. Un boost general contaminaba las
        # preguntas puntuales: los indices genericos (Inicio, Contexto) subian y
        # desplazaban al nodo concreto que respondia.
        # La pregunta que nombra un TIPO de compromiso («qué planes hay abiertos», «qué
        # preguntas siguen sin respuesta») debe favorecer a las entradas de ese tipo. Sin
        # esto, «planes abiertos» traia una decision y ningun plan: el vocabulario del tipo
        # vive en el frontmatter, no en la prosa, asi que ninguna capa lo veia. Solo aplica
        # cuando la palabra aparece; una pregunta comun no toca nada.
        TIPOS = {"plan": ("plan", "planes"), "pregunta": ("pregunta", "preguntas"),
                 "requerido": ("pedido", "pedidos", "requerido", "requeridos"),
                 "decision": ("decision", "decisiones"),
                 "hallazgo": ("hallazgo", "hallazgos", "problema", "problemas"),
                 "medicion": ("medicion", "mediciones", "medida", "medidas")}
        palabras_pregunta = set(PALABRA.findall(normalizar(pregunta)))
        tipos_pedidos = {tp for tp, formas in TIPOS.items()
                         if palabras_pregunta & set(formas)}
        # Preguntar por AVANCES o por lo ya comprobado debe favorecer lo cerrado y lo
        # verificado por sobre lo abierto. Sin esto, «qué avances hubo ya comprobados»
        # devolvía 4 pendientes y el único cierre real en la posición 3 (tercera
        # evaluación, confirmado con tres preguntas distintas): el buscador solo ve texto,
        # y el estado vive en la ficha. Mismo mecanismo aditivo que el empuje por tipo.
        AVANCE = {"avance", "avances", "comprobado", "comprobados", "comprobo",
                  "funcionando", "resuelto", "resueltos", "cerrado", "cerrados",
                  "logrado", "logrados", "completado", "completados"}
        palabras_avance = set(PALABRA.findall(normalizar(pregunta)))
        if palabras_avance & AVANCE and puntaje:
            tope_av = max(puntaje.values())
            for nom in list(puntaje):
                nd = idx.nodos[nom]
                cerrado = ("**Estado:** resuelto" in nd.cuerpo
                           or str(nd.meta.get("estado")) == "resuelto"
                           or (nd.polo != "en-curso"
                               and "**Estado:** resuelto" in nd.cuerpo))
                if cerrado:
                    puntaje[nom] += tope_av * 0.6

        if tipos_pedidos and puntaje:
            # El empuje es PROPORCIONAL al tope, como el del titulo exacto: un piso fijo
            # (0.02) no movia nada contra puntajes reales de 0.2 — se probo y los planes
            # seguian fuera del top-5. Aditivo, no multiplicativo: conserva el orden de
            # relevancia ENTRE las entradas del tipo, y las sube en bloque por sobre lo
            # que no es del tipo pedido.
            tope_sc = max(puntaje.values())
            for nom in list(puntaje) + [n for n in idx.nodos if n not in puntaje]:
                nd = idx.nodos[nom]
                tiene = (str(nd.meta.get("tipo")) in tipos_pedidos
                         or any(f"**Tipo:** {tp}" in nd.cuerpo for tp in tipos_pedidos))
                if tiene:
                    puntaje[nom] = puntaje.get(nom, 0.0) + tope_sc * 0.8

        if LISTADO.search(normalizar(pregunta)):
            for nom, sc in list(puntaje.items()):
                if idx.nodos[nom].es_indice:
                    puntaje[nom] = sc * 1.9
                elif len(idx.relacionados(nom)) > umbral_hub:
                    # Una entrada que conecta con casi todo NO es un indice: no enumera nada,
                    # solo nombra de paso a cada subsistema. Sin esta mitad, una pregunta de
                    # listado la dejaba con su puntaje intacto mientras el resto competia, y
                    # ganaba —"cuales son los accesos que faltan" devolvia el mapa de la
                    # plataforma antes que la entrada de los accesos, medido el 2026-07-27—.
                    # Es el mismo castigo que la rama de al lado, que hasta ahora no cubria
                    # las preguntas de listado.
                    puntaje[nom] = sc * 0.55
        else:
            # Mitad simetrica del boost anterior. Un nodo que conecta con casi todo el corpus
            # habla de todo, asi que su vector queda cerca de CUALQUIER consulta y su texto
            # comparte vocabulario con todas: sin esto gana hasta preguntas que no son de la
            # base. Se atenua, no se excluye —sigue siendo la respuesta correcta cuando de
            # verdad se pregunta por el conjunto—, y solo cuando la pregunta es puntual.
            # Se probo eximir de la penalizacion a los que calzaban por nombre o por
            # coincidencia literal —la bitacora pierde "que paso el primer dia del onboarding",
            # que es lo unico que ella responde— y fue peor: no arreglo ese caso y degrado
            # otros cinco. La red de regresion lo atrapo. Queda como esta: la penalizacion es
            # burda pero su efecto neto es positivo, y el ajuste fino del ranking sin una
            # escala de relevancia calibrada es prueba y error con resultado impredecible.
            if not DEFINICIONAL.search(normalizar(pregunta)):
                for nom, sc in list(puntaje.items()):
                    # LA EXENCIÓN POR NOMBRE LITERAL SE PROBÓ Y SE MIDIÓ INERTE — 2026-08-07.
                    # El handoff de esa iteración recomendó eximir a la entrada cuyo nombre aparece
                    # LITERAL en la pregunta, distinguiéndola del calce por raíces que el párrafo de
                    # arriba ya declara fallado. Se implementó y se midió con `pertinencia.py`:
                    # 36/81 con la exención y 36/81 sin ella, y el caso que la motivaba —«cuántos
                    # clientes tiene OKOS hoy»— devuelve exactamente los mismos tres documentos en
                    # los dos sentidos. No mueve nada, ni para bien ni para mal.
                    # Se revirtió: un arreglo que no cambia nada es peor que ninguno, porque queda
                    # como código que alguien va a creer que hace algo. La causa por la que esa
                    # entrada se pierde NO es esta penalización, y el diagnóstico sigue abierto.
                    if len(idx.relacionados(nom)) > umbral_hub:
                        puntaje[nom] = sc * 0.55

        # LA RECENCIA COMO MULTIPLICADOR SE APLICA SIEMPRE, y esto es lo que faltaba. El bloque
        # entero vivía dentro de `if reciente:`, así que el multiplicador solo operaba cuando alguien
        # pedía explícitamente ese orden — o sea casi nunca. Medido el 2026-08-06: por eso derivar la
        # media vida del corpus el día anterior no movió la pertinencia ni un punto. Se estaba afinando
        # un factor que en el orden normal no se aplicaba.
        #
        # La distinción la hace el propio comentario de abajo y no se respetaba: SEMBRAR el pozo con
        # lo más nuevo es propio de «lo último sobre X» —cambia qué entra—, pero PONDERAR por recencia
        # es parte de la relevancia en toda consulta: es lo que hace que un hecho de hoy le gane a un
        # plan de anteayer cuando los dos calzan parecido. Sigue siendo multiplicador y no orden: un
        # nodo irrelevante pero nuevo no domina.
        # LOS DOS NÚMEROS DE LA RECENCIA SON AJUSTABLES DESDE EL ENTORNO, y no por comodidad: es lo
        # que vuelve la ABLACIÓN una capacidad en vez de un parche. Hasta el 2026-08-06, decidir si
        # este multiplicador ayudaba o estorbaba exigía editar el servidor, medir, y desandar — así
        # que nadie lo hacía y el factor se afinaba a ciegas. Con `tools/pertinencia.py --ablacion`
        # se mide cada variante contra las preguntas juzgadas y el número decide.
        # Los valores por omisión son EXACTAMENTE los que había: sin variables de entorno, esto se
        # comporta igual que antes.
        # LA MEDIA VIDA ES FIJA EN 45 DÍAS, Y DERIVARLA DEL CORPUS FUE EL ERROR. La versión anterior
        # la calculaba como `rango // 3`; en una base que se escribe TODOS LOS DÍAS ese rango se
        # achica solo, dio 3,6 días, y con eso la recencia dejó de ser un desempate para volverse el
        # criterio dominante: ×5,989 para algo de hoy contra ×4,693 para algo de ayer.
        #
        # Medido el 2026-08-06 con el instrumento de pertinencia sobre las 81 preguntas juzgadas, y
        # contra la batería, que es lo que lo vuelve una decisión y no una opinión:
        #   · precisión en 1er lugar   32/81 → 35/81   (+3, igual que apagarla del todo)
        #   · batería                  394/397 → 395/397, con `INT-001` volviendo a verde
        # O sea: el mecanismo servía y su constante no. Se conserva el desempate por recencia y se
        # le saca la propiedad que lo volvía dominante — que la base crezca no puede achicar la
        # media vida.
        ampl = float(os.environ.get("KB_RECENCIA_AMPLITUD", "5.0"))
        ahora = max((nd.modificado for nd in idx.nodos.values()), default=0)
        _dias = float(os.environ.get("KB_RECENCIA_MEDIA_VIDA_DIAS", "45"))
        HALF_LIFE = int(_dias * 86400)
        if ampl:
            for nom in list(puntaje):
                mod = idx.nodos[nom].modificado
                if mod:
                    puntaje[nom] *= 1 + ampl * math.exp(-(ahora - mod) / HALF_LIFE)

        if reciente:
            # Sembrar el pozo con lo MÁS NUEVO del corpus aunque no calce temáticamente: «¿qué es lo
            # último?» debe poder traer el commit más reciente aunque no matchee la consulta. Esto sí
            # es propio de este orden, porque cambia QUÉ entra y no solo en qué posición queda.
            recientes = idx.recientes(polo, tope=n * 2)
            for pos, nom in enumerate(recientes):
                puntaje[nom] = puntaje.get(nom, 0.0) + 0.5 / (5 + pos)
        # Pedir algo por su nombre EXACTO lo devuelve primero, sin excepcion. Sin esta regla,
        # dos entradas cuyos titulos se contienen entre si se tapaban mutuamente: preguntar
        # "Pruebas automaticas" devolvia "Conectar las pruebas automaticas a la publicacion",
        # porque la mas larga contiene la frase y gana por la capa lexica. Es un choque que se
        # repite cada vez que un plan se llama parecido al subsistema que responde, o sea,
        # siempre — y se vuelve mas frecuente cuanto mas crece la base.
        exacto = next((nom for nom in puntaje if normalizar(nom) == objetivo), None)
        if exacto and puntaje:
            puntaje[exacto] = max(puntaje.values()) * 1.5

        ganadores = sorted(puntaje, key=lambda x: -puntaje[x])[:n]

        # Orden con pesos entrenados (opcion B del plan de pertinencia). La mezcla a mano
        # de arriba elige QUIENES entran; esta capa decide EN QUE ORDEN se muestran, con
        # una formula calibrada sobre etiquetas generadas del propio corpus y evaluada
        # contra 67 preguntas juzgadas que el entrenamiento nunca ve. Se reordena una
        # cabeza acotada y el puntaje original queda de desempate — si los pesos estan
        # vacios, nada cambia.
        # Los empujes de intencion son CONTRATOS, no sugerencias: «que planes hay» debe
        # encabezar con planes, un titulo exacto debe ganar, «avances» favorece lo cerrado.
        # El orden entrenado no compite con eso (medido: sin esta guarda rompia el caso
        # INT-006 de la bateria). Solo reordena preguntas sin intencion declarada.
        intencion = bool(tipos_pedidos or (palabras_avance & AVANCE)
                         or LISTADO.search(normalizar(pregunta)) or exacto)
        # Los pesos van amarrados a la base con que se calibraron: la normalizacion
        # (mu/sigma) es de SU corpus, y aplicarla a otra base reordenaria sus resultados
        # en silencio con una calibracion ajena. Otra base sirve su orden de siempre
        # hasta tener pesos propios.
        if (RANKER_PESOS and puntaje and not intencion
                and RANKER_PESOS.get("kb") == idx.cfg.slug):
            # Se reordena EXACTAMENTE el lote que se iba a servir — la misma distribucion
            # con que se entreno (candidatos = top-n del orden base). Ampliar la cabeza a
            # mas candidatos que el lote seria aplicar el modelo fuera de su distribucion.
            # LA CABEZA PUEDE SER MÁS ANCHA QUE EL LOTE — perilla, apagada por omisión (0).
            #
            # Medido el 2026-08-07: como el reordenador ve exactamente los `n` que se iban a servir,
            # CUÁNTOS documentos pidas decide QUÉ documentos llega a considerar. La misma pregunta
            # con límite 6 y con límite 20 no devuelve el mismo orden truncado: devuelve otro orden.
            # Sobre las 81 preguntas juzgadas, 15 de las 29 cuyo documento no aparece pidiendo 6 SÍ
            # aparecen pidiendo 20, y varias en posición 2, 4 o 6 — o sea que el documento correcto
            # existía, puntuaba alto, y no entraba al lote que el reordenador miraba.
            # `KB_CABEZA=<k>` le da k candidatos del orden base y recorta a n DESPUÉS.
            #
            # SE MIDIÓ Y SE DEJA APAGADO. Sobre las 81 preguntas juzgadas, sirviendo siempre 6:
            #     cabeza = el lote (hoy)  p@1 35/81 = 43 %   top-3 43   fuera 29
            #     cabeza = 12 candidatos  p@1 35/81 = 43 %   top-3 44   fuera 31
            #     cabeza = 20 candidatos  p@1 33/81 = 40 %   top-3 45   fuera 30
            #     cabeza = 30 candidatos  p@1 33/81 = 40 %   top-3 45   fuera 30
            # O sea: ensanchar la cabeza CAMBIA primer lugar por top-3. El reordenador, con más
            # candidatos, reparte la respuesta correcta entre la 2ª y la 3ª y deja entrar a otra en
            # la 1ª — que es exactamente lo que su propio comentario anticipa arriba: fuera de la
            # distribución con que se entrenó. La no-monotonía es real y su causa está acá, pero
            # esta no es su cura. La perilla queda porque volver a medirla cuesta una línea, y
            # porque el día que se reentrene el reordenador con cabezas anchas hay que volver a
            # mirarla — con la calibración vieja, no.
            _k = int(os.environ.get("KB_CABEZA", "0") or 0)
            cabeza = (sorted(puntaje, key=lambda x: -puntaje[x])[:max(_k, n)] if _k > 0
                      else list(ganadores))
            F = idx.rasgos(pregunta, cabeza)
            _mu, _sg, _w, _b = (RANKER_PESOS[k] for k in ("mu", "sigma", "w", "b"))
            def _score(nom):
                return sum(wi * ((f - m) / (s or 1.0)) for f, m, s, wi
                           in zip(F[nom], _mu, _sg, _w)) + _b
            ganadores = sorted(cabeza, key=lambda x: (-_score(x), -puntaje[x]))[:n]

        # Un índice no contiene respuestas: enumera lo que existe. Preguntar «¿cómo
        # funciona el cobro?» y recibir la tabla de contenidos es la peor respuesta
        # posible, porque parece correcta. Medido el 2026-07-29: tres de cuatro
        # preguntas de la forma «¿cómo funciona X en okos?» devolvían el nodo hub
        # OKOS en primer lugar, y «¿qué hay pendiente?» devolvía el índice del polo.
        #
        # Un hub no es solo el nodo cuyo nombre es el del directorio (`es_indice`):
        # OKOS no lo era por esa regla y era el peor infractor. Lo que lo delata es
        # estructural — es el padre declarado de casi todas las entradas, así que su
        # texto menciona todos los sujetos y calza con cualquier pregunta.
        #
        # `panorama` existe justo para las preguntas panorámicas. Así que acá salen del
        # lote, salvo que dejarían la respuesta vacía o que la pregunta los nombre.
        hubs = {nom for nom, nd in idx.nodos.items()
                if nd.es_indice or sum(1 for x in idx.nodos.values()
                                       if nom in links_de_padre(x)) >= 4}
        # Excepcion que esta poda no heredo. La penalizacion BLANDA de hub (mas arriba) ya
        # exime a las preguntas definicionales, y su comentario dice por que: "que es esta
        # plataforma" tiene al nodo panoramico como respuesta correcta. Esta poda DURA se
        # agrego despues y solo miraba `exacto`, que exige que la pregunta sea el titulo
        # entero. "que es OKOS" no lo es, asi que OKOS quedaba fuera de su propia respuesta:
        # la consulta devolvia cuatro entradas y ninguna era la que se preguntaba.
        # Se exige que la pregunta lo NOMBRE ademas de ser definicional: sin esa segunda
        # condicion, "como funciona el cobro en okos" volveria a devolver el hub, que es
        # justo el caso medido el 2026-07-29 que motivo esta poda.
        # NOMBRARLO COMO SUJETO ALCANZA; nombrarlo como LUGAR no. Medido el 2026-08-07: la poda
        # solo perdonaba a un hub en preguntas definicionales, asi que «cuantos clientes tiene OKOS
        # hoy» —que lo nombra y no es definicional— quedaba fuera de su propia respuesta, con la
        # peor nota posible tres evaluaciones seguidas y devolviendo MENOS documentos de los pedidos
        # porque uno se podaba en silencio.
        #
        # Ampliarlo a «que lo nombre» a secas NO sirve, y esto se midio antes de elegir: reabre el
        # caso que motivo la poda el 2026-07-29 —«como funciona el cobro EN okos» volvia a devolver
        # el hub— y `pertinencia.py` no lo detecta, porque esa pregunta no esta entre sus 81. O sea
        # que ahi la falla es muda, que es justo lo que no se delega.
        #
        # La distincion que separa los dos casos es gramatical y barata: si el nombre viene detras
        # de una preposicion locativa, es el LUGAR donde ocurre lo preguntado y la pregunta es sobre
        # otra cosa. Si no, es el sujeto.
        _loc = re.compile(r"\b(en|de|del|dentro de|para|sobre|con)\s+$")
        def _como_sujeto(g):
            i = objetivo.find(normalizar(g))
            return i >= 0 and not _loc.search(objetivo[:i])
        nombrado_definicional = {g for g in ganadores
                                 if normalizar(g) in objetivo
                                 and (DEFINICIONAL.search(objetivo) or _como_sujeto(g))}
        if hubs and not exacto:
            sin_hub = [g for g in ganadores if g not in hubs or g in nombrado_definicional]
            if sin_hub:
                # LO PODADO SE REPONE, y no es un detalle de conteo. Esta poda corre DESPUÉS de
                # recortar a `n`, así que cada hub que saca deja un hueco: pedir 6 devuelve 5, y el
                # documento que habría entrado sexto —que existe, puntuó y no es hub— no se sirve.
                # El comentario de arriba ya había visto el síntoma en un caso («devolviendo MENOS
                # documentos de los pedidos porque uno se podaba en silencio») y arregló ESE caso
                # ampliando la excepción, no la clase.
                #
                # Se repone desde el mismo orden base que produjo el lote, saltando los hubs y lo
                # ya servido. No toca la distribución que ve el reordenador —ya corrió, sobre `n`
                # candidatos— ni el criterio de la poda: solo deja de castigar a quien preguntó por
                # una decisión que se tomó sobre otro documento.
                if len(sin_hub) < len(ganadores):
                    for g in sorted(puntaje, key=lambda x: -puntaje[x]):
                        if len(sin_hub) >= n:
                            break
                        if g not in sin_hub and (g not in hubs or g in nombrado_definicional):
                            sin_hub.append(g)
                ganadores = sin_hub

        # Un problema no viaja solo (regla de escalamiento, servida). Si un ganador trae
        # un hallazgo, su respondedor VIVO —el compromiso de en-curso que lo cita— entra
        # al lote aunque no haya puntuado: quien pregunta por el problema recibe el plan
        # en la misma respuesta, no como un nombre suelto en «Conecta con». Medido en la
        # quinta evaluación: el hallazgo del correo salía primero y su plan aparecia solo
        # de nombre. Reemplaza al ultimo ganador (no agranda el lote) y a lo mas uno por
        # respuesta — es un rescate, no un canal paralelo de ranking. La cita es curada
        # (`menciona` del respondedor), asi que no depende de ningun umbral.
        # SOLO cuando el problema ES la pregunta — el nodo con hallazgo va primero—: el
        # rescate reemplaza al último puesto, y eso desaloja a alguien. Con la condición
        # amplia («algún ganador trae hallazgo») desalojaba resultados pertinentes en
        # preguntas que no eran sobre el problema: se midió con «¿la limpieza de multimedia
        # funciona?», donde el quinto ganador traía un hallazgo ajeno y el rescate botó del
        # sexto puesto justo a la entrada que respondía.
        if len(ganadores) > 1 and "**Tipo:** hallazgo" in idx.nodos[ganadores[0]].cuerpo:
            g = ganadores[0]
            vivos = [nom for nom, nd in idx.nodos.items()
                     if nd.polo == "en-curso" and g in nd.menciona
                     and str(nd.meta.get("estado")) != "resuelto"]
            if vivos and not any(v in ganadores for v in vivos):
                ganadores[-1] = max(vivos, key=lambda v: puntaje.get(v, 0.0))

        if not ganadores:
            return (f"Nada sobre «{pregunta}». Busqué por palabras y por significado. "
                    "Prueba otras palabras, o usa panorama() para ver qué cubre.")

        redirigir = ""
        # LA VENTANA TEMPORAL SE DEDUCE SIEMPRE, no solo cuando el detector de propiedad dispara.
        # «Qué se hizo hoy» no nombra ninguna propiedad y sí nombra una fecha; con la deducción
        # metida dentro del `if`, la fecha se calculaba y se tiraba. Medido el 2026-08-06 con la
        # función pura: de las 13 consultas temporales de la tanda, `deducir_desde` acertaba en 9 y
        # solo 2 la usaban. Calcular una ventana y descartarla es peor que no calcularla — el
        # trabajo está hecho y el que pregunta no lo recibe.
        desde_f = deducir_desde(pregunta, datetime.date.today().isoformat())
        # SI LA PREGUNTA TRAE TEMA, NO SE LE ANTEPONE UNA LISTA CIEGA AL TEMA.
        #
        # Al deducir un estado, la deducción DESCARTA el tema: «qué problemas de seguridad hay» se
        # contesta con todos los hallazgos vigentes, de seguridad o no. El propio encabezado lo
        # declaraba —«exacta sobre el filtro y ciega al tema»—, y un rótulo no es una mitigación:
        # medido el 2026-08-07, 12 de 55 respuestas se abrieron con esa lista, y SEIS preguntas
        # distintas recibieron el MISMO bloque. El lector que no puede dudar se lleva la lista
        # entera como si contestara lo que preguntó.
        #
        # `por_nombre` es la señal de tema que el código ya calcula: la pregunta nombra una entrada,
        # literal o por dos raíces de contenido poco frecuentes. Cuando eso pasa, la búsqueda por
        # significado ya la contesta y la lista solo agrega ruido — así que queda el aviso de que
        # existe `listar`, que es lo que había antes de que la lista se compusiera sola.
        #
        # El arreglo de fondo es otro y es más grande: que `listar` acepte un tema. Esto es el
        # paliativo, y se declara como tal.
        # SUPRIMIR EL BLOQUE ENTERO ERA DEMASIADO: se llevaba puesta la prueba de que la deducción
        # compuso el filtro correcto —el defecto de la respuesta inversa, cinco iteraciones de
        # historia—, y dos casos de la batería cayeron con razón. Cuando la pregunta trae tema NO se
        # calla: se NOMBRA el filtro que corresponde sin pegar la lista. El lector se lleva la orden
        # exacta para su intención y la respuesta sigue siendo sobre su tema.
        trae_tema = bool(por_nombre)
        if POR_PROPIEDAD.search(pregunta) or desde_f:
            # Decirle al lector «usá otra herramienta» es peor que usarla por él: en una
            # pregunta por propiedad la respuesta exacta ya se puede calcular acá, y hacerlo
            # ahorra un viaje y evita que se quede con el resultado aproximado, que es
            # justamente el que engaña. Si el filtro no se puede deducir o la llamada falla,
            # queda el aviso solo — nunca menos que antes.
            # La deducción vive a nivel de módulo —`deducir_filtro`— para que se pueda probar sin
            # levantar el servidor. Antes estaba acá dentro, y por eso el detector y la deducción
            # llegaron a contradecirse: uno aceptaba «resolvió» y la otra no.
            # La ventana temporal se compone con el resto: «qué se cerró hoy» son las dos cosas —lo
            # resuelto Y desde hoy—, y servir solo la primera mitad devuelve toda la historia.
            filtro, tipo_f = deducir_filtro(pregunta)
            exacto_txt, etiqueta_filtro = "", ""
            if filtro or tipo_f or desde_f:
                kw = {k: v for k, v in (("estado", filtro), ("tipo", tipo_f),
                                        ("desde", desde_f)) if v}
                try:
                    exacto_txt = listar(**kw)
                    etiqueta_filtro = " · ".join(f'{k}="{v}"' for k, v in kw.items())
                except Exception:
                    exacto_txt = ""
                # UNA LISTA VACÍA NO ES UNA RESPUESTA EXACTA. `listar` no devuelve cadena vacía
                # cuando no encuentra nada: devuelve la frase que lo explica, y esa frase es cierta
                # pero no es lo que el encabezado promete. El 2026-08-06, «qué problemas hay hoy en
                # la plataforma» sirvió bajo «acá va primero la respuesta EXACTA» el texto «Nada
                # cumple ese filtro», con 19 hallazgos vigentes en la base. Se cae al aviso
                # genérico, que es lo que había antes de que existiera la deducción: nunca menos.
                if exacto_txt.startswith(SIN_RESULTADOS_LISTAR):
                    exacto_txt = ""
                if trae_tema:            # el filtro se nombra; la lista ciega al tema no se pega
                    exacto_txt = ""
                # NI SIN TOPE. El arreglo de arriba cubrió el extremo vacío y dejó vivo el opuesto:
                # esta rama pegaba la salida ENTERA de `listar`, y «qué se logró esta semana» —la
                # consulta más natural de dirección— devolvía 166 renglones y ~47.000 caracteres.
                # La rama que elige QUÉ servir no miraba el TAMAÑO de lo que sirve.
                #
                # Se recorta declarando: el que pregunta ve cuántos quedaron fuera y con qué orden
                # exacto pedirlos. Un recorte declarado es información; uno callado es una
                # afirmación falsa sobre la completitud, que es justo lo que este bloque promete.
                elif exacto_txt:
                    exacto_txt = _recortar_listado(exacto_txt, etiqueta_filtro)
            if exacto_txt:
                # «EXACTA SOBRE ESA PROPIEDAD», y no «exacta» a secas. El filtro es exacto sobre lo
                # que filtra y CIEGO AL TEMA: «riesgo con los datos personales» sirve los 19
                # hallazgos vigentes sin ningún recorte temático, y anunciarlo como la respuesta
                # exacta invita a leer 19 renglones como si los 19 fueran del tema preguntado.
                redirigir = (
                    "⚠ Preguntaste por una PROPIEDAD (estado, tipo, fecha), no por un tema. La "
                    "búsqueda por significado devuelve lo más parecido, no todo lo que cumple, así "
                    f"que acá va primero la respuesta EXACTA SOBRE ESA PROPIEDAD —listar("
                    f"{etiqueta_filtro})—, exacta sobre el filtro y ciega al tema, y después "
                    "lo que encontró la búsqueda.\n\n"
                    f"{exacto_txt}\n\n── y esto encontró la búsqueda por significado ──\n\n")
            else:
                # SI SE PUDO DEDUCIR EL FILTRO, SE NOMBRA. Es la diferencia entre «usá otra
                # herramienta» —que le devuelve el trabajo al lector— y «usá ESTA orden», que es
                # la que corresponde a lo que preguntó. Y es además lo que deja comprobable que la
                # deducción acertó: el caso de la batería busca ese filtro en la respuesta.
                orden = (f'listar({etiqueta_filtro.replace(" · ", ", ")})' if etiqueta_filtro
                         else 'listar(estado="abierto")')
                redirigir = ("⚠ Esta pregunta es por una PROPIEDAD (estado, tipo, fecha) además de "
                             "por un tema. La búsqueda por significado devuelve lo más parecido, no "
                             "todo lo que cumple, así que puede faltarte algo. Abajo va lo que "
                             "encontró la búsqueda sobre tu tema; para la lista exacta y completa "
                             f"—de todos los temas— usá `{orden}`.\n\n")
        partes = [redirigir + aviso + f"{len(ganadores)} documento(s) sobre «{pregunta}»\n"]
        for nom in ganadores:
            partes.append(
                f"### {idx.fuente(idx.nodos[nom])}\n{idx.extracto(nom, args[0], extendido)}")
            if vecinos := idx.relacionados(nom)[:12 if extendido else 6]:
                partes.append(f"*Conecta con:* {', '.join(vecinos)}")
            partes.append("")
        partes.append("Usa leer(tema) para el texto completo de cualquiera de estas.")
        return "\n".join(partes)

    @registrar
    @con_dominio(etiqueta, contexto)
    def leer(tema: str) -> str:
        """Devuelve de {base} el texto completo de un documento, por su título, íntegro.

        Úsala cuando ya sabes qué documento quieres —normalmente porque `consultar` te
        lo mostró, o el usuario lo nombró— y necesitas todo su contenido, no un
        fragmento. Si no sabes el título exacto, usa `consultar` primero.

        Acepta el nombre aproximado: resuelve tildes, mayúsculas y coincidencias
        parciales, y prefiere el documento base sobre sus variantes. Devuelve el título,
        la categoría, la fecha de última actualización, el cuerpo Markdown completo tal
        como está escrito, y al final los documentos enlazados más las variantes de
        nombre que existan, si las hay.

        No busca por tema ni por significado: solo resuelve nombres. Si el nombre que
        pasas no identifica con claridad a un documento, no devuelve contenido —nunca
        adivina entre homónimos— sino la lista de opciones para que elijas.

        Parámetros:
          tema: el título (o una aproximación) del documento a leer.
        """
        candidatos, confianza = idx.resolver(tema)
        if not candidatos:
            return f"No encontré un documento llamado «{tema}». Prueba con consultar()."
        # Match debil (solo raices compartidas): NO se entrega contenido, porque puede
        # ser un homonimo. Se ofrecen candidatos —por raiz Y por significado, para
        # captar sinonimos y siglas: "responsabilidad extendida" sugiere "Ley 20.920
        # (Ley REP)" via semantica aunque el titulo no comparta las palabras.
        if confianza == "debil":
            sugeridos = list(dict.fromkeys(candidatos[:4] + idx.semejantes(tema, tope=5)))[:8]
            lista = "\n".join(f"  - {c}" for c in sugeridos)
            return (f"No hay un documento que se llame exactamente «{tema}». Puede que "
                    f"busques una de estas:\n{lista}\n\nO usa consultar(«{tema}») para "
                    "buscar por significado en vez de por nombre.")
        # Antes se pedia desambiguar apenas habia dos candidatas, lo que fricciona
        # cuando una es la principal y la otra una variante ("— Texto oficial"). Se
        # devuelve la mejor (la mas corta gana empates: el nombre base) y se avisa
        # de las otras al final, en vez de frenar al usuario con una pregunta.
        elegido = candidatos[0]
        nodo = idx.nodos[elegido]
        otras = [c for c in candidatos[1:6] if c != elegido]
        salida = [f"# {nodo.nombre}", f"*{idx.fuente(nodo)}*", "", nodo.cuerpo.strip()]
        if vecinos := idx.relacionados(nodo.nombre):
            salida += ["", "---", "**Conecta con:** " + ", ".join(vecinos)]
        if otras:
            salida += ["", f"*También existen variantes: {', '.join(otras)} "
                       "— pídelas por su nombre si quieres alguna.*"]
        return "\n".join(salida)

    @registrar
    @con_dominio(etiqueta, contexto)
    def listar(estado: str | None = None, tipo: str | None = None,
               desde: str | None = None, mostrable: bool | None = None,
               fuente: str | None = None) -> str:
        """Filtra secciones de {base} por sus campos: estado, tipo, fecha. Exacto, no por parecido.

        `consultar` busca por significado y devuelve lo más parecido. Esto es lo otro:
        revisa los campos de cada sección y devuelve TODAS las que cumplen, sin ranking
        y sin omitir ninguna. Úsala cuando la pregunta es por una propiedad —en qué
        estado está, de qué tipo es, desde qué fecha— y no por un tema.

        Para qué sirve, en concreto:
          · «¿qué se arregló esta semana?» → listar(estado="resuelto", desde="2026-07-27")
          · «¿qué le puedo mostrar al fundador?» → listar(estado="resuelto", mostrable=True)
          · «¿qué está abierto?» → listar(estado="abierto")
          · «¿qué mediciones hay?» → listar(tipo="medicion")
          · «¿qué hay dicho pero no comprobado?» → listar(fuente="declaracion")

        Parámetros:
          estado:    vigente · resuelto · abierto · aceptado · registrado
          tipo:      hallazgo · funcionamiento · medicion · contexto
          desde:     fecha ISO; solo lo verificado o declarado en esa fecha o después
          mostrable: True devuelve solo lo que puede verse fuera del equipo técnico;
                     False, solo lo interno. Se omite para no filtrar por eso.
          fuente:    verificacion · declaracion. Lo comprobado contra el sistema, o lo
                     que alguien dijo. Es la distinción sobre la que descansa todo acá.

        DOS COSAS QUE HAY QUE LEER EN LO QUE DEVUELVE, y no suponer:
          · CADA SECCIÓN TRAE SU `Estado`. Que vuelva llena no significa que haya algo
            pendiente: un filtro por tipo puede devolver siete cosas y estar las siete
            cerradas. Contá los estados antes de decir «hay siete pendientes» — eso pasó
            de verdad, tres veces seguidas, y llegó a un informe.
          · CADA SECCIÓN TRAE SU FECHA Y SI FUE `Verificado` o `Declarado`. Lo que vaya a
            sostener una decisión se cita con esa fecha, y lo declarado se trata como
            dicho por alguien, no como comprobado.

        Si no devuelve nada, el filtro es correcto y el conjunto está vacío: eso es una
        respuesta, no un error. Antes de concluirlo, comprobá que el estado y el tipo que
        pediste existan en esta colección —los valores válidos son los de arriba— y probá
        aflojando un filtro, empezando por `desde`.
        """
        filas = []
        for nombre, nd in idx.nodos.items():
            if nd.es_indice:
                continue
            secciones: list[tuple[str, dict]] = []
            for bloque in re.split(r"(?m)^### ", nd.cuerpo)[1:]:
                titulo = bloque.split("\n", 1)[0].strip()
                ficha = re.match(r"[^\n]*\n\n((?:- \*\*[^\n]+\n)+)", bloque)
                if not ficha:
                    continue
                campos = {}
                for linea in ficha.group(1).splitlines():
                    mm = re.match(r"-\s+\*\*([^:*]+):\*\*\s*(.+?)\s*$", linea)
                    if mm:
                        campos[mm.group(1).strip()] = mm.group(2).strip()
                secciones.append((titulo, campos))
            # Entrada SIN sub-entradas: su ficha vive en el frontmatter. Son los planes y
            # las preguntas de `en-curso` (uno por archivo, sin `###`). Sin esto quedaban
            # invisibles a `listar` —medido el 2026-07-30: `listar(estado="abierto")` solo
            # veía «Accesos requeridos», la única con sub-entradas—, y son justo los planes
            # abiertos y las preguntas al negocio que el informe semanal pide por propiedad.
            m = nd.meta
            unidad = {"Estado": str(m.get("estado", "")),
                      "Tipo": str(m.get("tipo", "")),
                      "Publicable": "sí" if m.get("publicable") else "no"}
            for campo, clave in (("Verificado", "verificado"), ("Declarado", "declarado"),
                                 ("Checkpoint", "checkpoint"), ("Vence", "vence")):
                if m.get(clave):
                    unidad[campo] = str(m.get(clave))
            if not secciones:
                secciones.append((nd.nombre, unidad))
            tipo_archivo = str(m.get("tipo", "") or "").lower()
            # QUÉ ES UNA UNIDAD LISTABLE, que es la pregunta que este filtro tiene que contestar
            # bien. La KB declara en su config qué tipos son CONTENEDORES —un conjunto de pedidos de
            # acceso: el archivo agrupa y cada sub-entrada es un pedido con su estado—. Los demás
            # tipos SON la unidad: un plan o una pregunta de negocio es una cosa, y sus secciones son
            # partes de ella, no instancias.
            #
            # Sin esa distinción el filtro se equivoca en las DOS direcciones, y las dos se midieron:
            #   · 2026-08-05 — una entrada con secciones no era recuperable por su propio tipo:
            #     `listar(tipo="requerido")` contestaba «nada cumple ese filtro» teniendo la base una
            #     entrada declarada así, y es una de las cinco secciones del informe semanal.
            #   · 2026-08-06 — al arreglar eso heredando el tipo a TODA sección, preguntar por las
            #     preguntas de negocio devolvía 12 resultados con 8 de ruido: las secciones internas
            #     de una pregunta se hacían pasar por preguntas. El arreglo devolvió una capacidad y
            #     rompió otra, que es lo que pasa cuando se arregla el caso sin mirar a los vecinos.
            es_contenedor = tipo_archivo in (idx.cfg.tipos_contenedores or [])
            if secciones and tipo and not es_contenedor and tipo.lower() == tipo_archivo:
                # El archivo ES la unidad de su tipo: se entrega él, no sus partes.
                secciones = [(nd.nombre, unidad)]
            for titulo, campos in secciones:
                if estado and campos.get("Estado", "").lower() != estado.lower():
                    continue
                heredable = tipo_archivo if es_contenedor else ""
                if tipo and tipo.lower() not in (campos.get("Tipo", "").lower(), heredable):
                    continue
                if mostrable is not None:
                    pub = campos.get("Publicable", "").lower() in ("sí", "si", "true")
                    if pub != mostrable:
                        continue
                # `Declarado` es la otra mitad del par de procedencia (2026-08-03): un hecho que
                # alguien dijo lleva su fecha ahí. Sin esto, `desde=` los dejaba fuera del
                # filtro, que es justo lo contrario de lo que el par busca —hacer visible de
                # dónde salió cada hecho, no esconderlo.
                # LA FUENTE ES FILTRABLE, y era la única propiedad de la doctrina que no lo era. La
                # distinción `Verificado`/`Declarado` —lo comprobado contra lo que alguien dijo— es
                # aquello sobre lo que descansa toda esta base, y no se podía pedir como categoría:
                # medido el 2026-08-07, preguntar por lo declarado devolvía 14.477 caracteres con
                # CERO apariciones de la marca. Sin esto, la sección «lo no comprobable» del informe
                # semanal no se compila y hay que leer el corpus entero a ojo.
                if fuente:
                    f = normalizar(fuente)
                    tiene_v, tiene_d = bool(campos.get("Verificado")), bool(campos.get("Declarado"))
                    if f.startswith("verific") and not tiene_v:
                        continue
                    if f.startswith("declar") and not tiene_d:
                        continue
                    if not (f.startswith("verific") or f.startswith("declar")):
                        return ("«fuente» es `verificacion` (lo comprobado contra el sistema) o "
                                "`declaracion` (lo que alguien dijo). Son las dos mitades del par "
                                "sobre el que descansa esta base.")
                fecha = (campos.get("Verificado") or campos.get("Declarado")
                         or campos.get("Checkpoint") or "")
                # LA HORA SALE DEL HISTORIAL, no de la ficha. La ficha guarda el DÍA, y con esta
                # base recibiendo del orden de setenta publicaciones diarias el día no discrimina
                # nada: preguntar por lo de hoy devuelve cincuenta cosas sin orden interno. La marca
                # fina se deriva de cuándo creció de verdad cada sub-entrada (ver
                # `fechas_subentrada`), así que es verdad comprobable y no un campo que alguien
                # tenga que acordarse de llenar — ni exige migrar las ~500 sub-entradas ya escritas.
                # SI LA SUB-ENTRADA NO TIENE MARCA PROPIA, VALE LA DEL ARCHIVO. Un archivo sin
                # encabezados de sección —casi todos los planes— es UNA sola unidad, así que la
                # fecha del archivo ES su fecha; excluirlo sería peor que no tener hora. Sin este
                # respaldo, pedir con hora dejaba fuera en silencio a las 80 entradas de 105 que no
                # tienen secciones: medido con el instrumento temporal, la cobertura caía de 0,78 a
                # 0,67 en las preguntas de ventana larga mientras la contaminación mejoraba — o sea
                # el filtro parecía más limpio porque escondía la mitad del corpus.
                sello = ((idx.fecha_de_sub.get(nombre) or {}).get(titulo)
                         or nd.modificado or 0)
                # LA HORA VIAJA CON SU DESFASE. Criterio de Martín, 2026-08-08: quien consulta
                # esta base es siempre una IA, y una de ellas trabaja para el fundador, que está
                # en otra zona horaria. «No podemos mitigar esto del lado del fundador, pero sí
                # podemos exponer en qué zona se registró cada hora, y de esa forma cualquier
                # inteligencia artificial va a saber de inmediato cómo resolver la discrepancia».
                #
                # Es más fuerte que configurar bien la zona del servidor: una hora con desfase se
                # interpreta sola aunque el servidor esté mal configurado, y una hora desnuda no
                # se puede rescatar aunque esté bien. El desfase convierte un dato que hay que
                # creer en un dato que se puede convertir.
                fina = (_con_desfase(sello) if sello else fecha)
                if desde:
                    # LAS DOS CONDICIONES SE EXIGEN JUNTAS CUANDO HAY HORA, y sin esto el filtro
                    # se contradecía: `2026-08-08` devolvía 18 secciones y `2026-08-08 00:00` —el
                    # mismo instante— devolvía 53. Una ventana más angosta no puede devolver más.
                    #
                    # La causa es que las dos fechas responden preguntas distintas y las dos son
                    # legítimas: la de la ficha es CUÁNDO SE VERIFICÓ el hecho, que es lo que su
                    # autor declara; la derivada es CUÁNDO SE ESCRIBIÓ, que sale del historial.
                    # Pedir por día siempre significó lo primero y se conserva. Pedir por hora
                    # exige ahora las dos, así que la ventana con hora es siempre un subconjunto
                    # de su día — que es lo único que quien pregunta puede suponer sin leer esto.
                    if fecha < desde[:10]:
                        continue
                    if len(desde) > 10 and (not sello or fina[:16] < desde[:16]):
                        continue
                filas.append((fina, nombre, titulo, campos, tipo_archivo))
        if not filas:
            return SIN_RESULTADOS_LISTAR
        filas.sort(key=lambda x: (x[0], x[1]), reverse=True)
        criterio = " · ".join(x for x in [
            f"estado={estado}" if estado else None,
            f"tipo={tipo}" if tipo else None,
            f"desde={desde}" if desde else None,
            f"fuente={fuente}" if fuente else None,
            ("mostrable" if mostrable else "solo interno") if mostrable is not None else None,
        ] if x) or "sin filtro"
        # LA ZONA SE DECLARA UNA VEZ, ARRIBA. Las horas de cada línea ya traen su desfase, pero
        # decirlo también acá le ahorra a quien lee tener que inferirlo de la primera fila —y sobre
        # todo se lo dice cuando NO hay filas, que es justo cuando alguien podría concluir que «no
        # pasó nada esta tarde» estando en otro huso y preguntando por otra tarde.
        cab = f"{len(filas)} sección(es) — {criterio}"
        if any(len(f[0]) > 10 for f in filas) or (desde and len(desde) > 10):
            cab += f"\nHoras en {zona_declarada()}; cada una trae su desfase."
        salida = [cab + "\n"]
        actual = None
        for fecha, nombre, titulo, campos, tipo_archivo in filas:
            if nombre != actual:
                salida.append(f"\n**{nombre}**")
                actual = nombre
            # Los campos se escriben en la MISMA forma en toda la base —`- **Campo:** valor`— y no
            # en una abreviatura propia de esta herramienta. Antes el tipo salia entre parentesis,
            # asi que la respuesta le llevaba el dato al lector y ningun consumidor podia leerlo con
            # la forma que el resto del sistema usa. Y de paso se declara el campo por el que se
            # filtro: quien recibe una lista tiene que poder saber por que esa lista es esa.
            # LA FICHA DICE DE DÓNDE SALE LA FECHA Y DE DÓNDE SALE EL TIPO, porque las dos cosas
            # cambian lo que el dato significa:
            #  · `Verificado` contra `Declarado` es la distinción sobre la que descansa toda la
            #    doctrina de esta base —lo comprobado contra lo que alguien dijo—, y esta herramienta
            #    imprimía la fecha pelada. Medido el 2026-08-06: de las 63 fichas que alimentan las
            #    cinco secciones del informe semanal, CERO declaraban su método.
            #  · Y cuando el tipo se heredó del archivo contenedor, la sección no lo declara en su
            #    propia ficha: `listar(tipo="decision")` devolvía nueve renglones y ninguno decía por
            #    qué estaba ahí. Se marca como heredado en vez de inventarle un campo que no tiene.
            #  · `ESPERA A` ES MEDIA SECCIÓN DEL INFORME SEMANAL y no llegaba por acá. El estándar
            #    pide, para «Requerido», a quién espera cada pedido y desde cuándo; medido el
            #    2026-08-06, el campo no aparecía en NINGUNO de los 62 renglones de las cinco
            #    secciones. `_hermanas_de` sí lo imprime: la información llegaba por un camino y no
            #    por el otro, que es la peor forma de un hueco porque parece cubierto.
            campo_fecha = ("Verificado" if campos.get("Verificado") else
                           "Declarado" if campos.get("Declarado") else
                           "Checkpoint" if campos.get("Checkpoint") else "")
            tipo_mostrado = campos.get("Tipo")
            if not tipo_mostrado and tipo_archivo:
                tipo_mostrado = f"{tipo_archivo} (del documento)"
            partes_f = [f"- **{k}:** {v}" for k, v in
                        (("Tipo", tipo_mostrado), ("Estado", campos.get("Estado")),
                         ("Espera a", campos.get("Espera a")),
                         ("Vence", marcar_vencimiento(campos.get("Vence")))) if v]
            sello = (f"{campo_fecha} {fecha}" if campo_fecha and fecha
                     else (fecha or "sin fecha"))
            salida.append(f"  · {sello} — {titulo}"
                          + ("  " + " ".join(partes_f) if partes_f else ""))
        return "\n".join(salida)

    @registrar
    @con_dominio(etiqueta, contexto)
    def panorama(tema: str | None = None) -> str:
        """Vista de conjunto de {base}: qué documentos hay, o cómo se relacionan por tema.

        Úsala para orientarte antes de preguntar, o cuando la intención del usuario es
        panorámica y no puntual: «¿qué hay acá?», «¿de qué trata esto?», «¿qué se
        conecta con X?». Para responder una pregunta concreta, usa `consultar`.

        Sin argumentos: devuelve cuántos documentos hay, cómo se reparten por categoría,
        y los más relacionados de cada una (los centrales). Con un
        tema: devuelve los documentos vecinos a ese tema en el grafo, cada uno con una
        línea de resumen — la forma rápida de entender un área sin leerla completa.

        No responde preguntas de contenido ni devuelve el texto de los documentos: sirve
        para saber qué existe y cómo se relaciona, no qué dice. Para lo segundo, usa
        `consultar` o `leer`.

        Parámetros:
          tema: opcional. El título de un documento para ver su vecindario; si se omite,
                se devuelve el inventario general de la base.
        """
        if tema:
            candidatos, _ = idx.resolver(tema)
            if not candidatos:
                return f"No encontré «{tema}». Prueba con consultar()."
            nodo = idx.nodos[candidatos[0]]
            vecinos = idx.relacionados(nodo.nombre)
            # Si el tema es un indice de directorio, su Inventario ya enumera y describe
            # a los hijos: es mejor respuesta que reconstruir el vecindario del grafo.
            if nodo.es_indice and (inv := nodo.seccion("Inventario")):
                return f"**{nodo.nombre}** — índice del área. Contiene:\n\n{inv[:1200]}"
            if not vecinos:
                return f"«{nodo.nombre}» no está conectado a otros documentos todavía."
            lineas = [f"Mapa alrededor de **{nodo.nombre}** ({len(vecinos)} conectadas)\n"]
            for v in vecinos:
                lineas.append(f"- **{v}** — {' '.join(idx.nodos[v].cuerpo.split())[:110]}…")
            return "\n".join(lineas)

        # Inventario con las entradas mas conectadas por polo: un panorama util
        # nombra los nodos centrales, no solo cuenta. Los hubs del grafo son la
        # mejor aproximacion barata a "lo importante de cada area".
        por_polo: dict[str, list[str]] = {}
        for nombre, nodo in idx.nodos.items():
            por_polo.setdefault(nodo.polo, []).append(nombre)
        lineas = [f"**{cfg.nombre}** — {len(idx.nodos)} documentos"
                  + (f" sobre {cfg.descripcion}" if cfg.descripcion else "") + ".\n"]
        for d, etiqueta in cfg.polos.items():
            nombres = por_polo.get(d)
            if not nombres:
                continue
            # Los indices de directorio son la espina navegable del area; se muestran
            # primero. Se completan con los nodos mas conectados que no sean indices.
            indices = [n for n in nombres if idx.nodos[n].es_indice]
            otros = sorted((n for n in nombres if not idx.nodos[n].es_indice),
                           key=lambda n: -len(idx.relacionados(n)))
            destacados = (indices + otros)[:8]
            etiq = "índices y más conectadas" if indices else "más conectadas"
            lineas.append(f"**{etiqueta}** ({len(nombres)}) — {etiq}: " + ", ".join(destacados))
        lineas.append("\nEs una obra en curso: contrasta lo importante contra la fuente "
                      "citada en cada entrada.")
        lineas.append("Pregunta con consultar(), o usa panorama('tema') para el mapa de un área.")
        return "\n".join(lineas)

    return mcp


# --- arranque ----------------------------------------------------------------

class ModeloSerializado:
    """Envuelve al modelo para que UN SOLO hilo lo use a la vez.

    NO es defensa preventiva: se agregó después de reproducir el fallo. Desde que el índice
    se reconstruye en caliente (ver `Planta`), el hilo que reconstruye llama a `encode()`
    para vectorizar las quinientas sub-entradas mientras el bucle de eventos llama a
    `encode()` para vectorizar la pregunta de quien está consultando. Ni la tabla estática
    ni el tokenizador de un codificador son reentrantes, y el resultado medido fue
    `IndexError: string index out of range` — una vez en la reconstrucción, que quedó
    abortada, y una vez en una consulta de un usuario, sobre 111 peticiones.

    Es la clase de fallo que nunca aparecía antes porque el índice solo se construía al
    arrancar, cuando todavía no había nadie atendido. El cambio en caliente lo destapó, y
    por eso el candado va acá y no en cada sitio de llamada: hay tres, y el cuarto que
    alguien agregue no se va a acordar.

    Costo: las consultas esperan como mucho un lote de vectorización, que es del orden de
    decenas de milisegundos. Medido después del arreglo: 0 fallos sobre 300 peticiones
    durante dos recargas seguidas, con la latencia máxima igual a la de antes.
    """

    def __init__(self, modelo):
        self._modelo = modelo
        self._candado = threading.Lock()
        # SE VECTORIZA POR LOTES CHICOS, y el motivo es la latencia de QUIEN CONSULTA, no la
        # velocidad de la reconstrucción. Con el candado tomado por el lote entero —las 500
        # sub-entradas de una vez— una pregunta que llega en medio espera a que termine todo:
        # medido, la peor latencia durante una recarga pasaba de 0,8 s a 3,2 s. Troceando, el
        # que consulta espera como mucho un lote. Se mide con `producto/probar-recarga-sin-corte.py`.
        self._lote = max(1, int(os.environ.get("KB_LOTE_VECTORES", "32")))

    def encode(self, textos):
        if len(textos) <= self._lote:
            with self._candado:
                return self._modelo.encode(textos)
        partes = []
        for i in range(0, len(textos), self._lote):
            with self._candado:
                partes.append(np.asarray(self._modelo.encode(textos[i:i + self._lote])))
        return np.concatenate(partes)

    def __getattr__(self, nombre):  # cualquier otro atributo pasa tal cual
        return getattr(self._modelo, nombre)


def _cargar_modelo_crudo():
    """Carga el modelo de embeddings estáticos: int8, con la dimensión COMPLETA (256).

    Antes se truncaba además a 128 dimensiones, o sea se tiraba la mitad de la
    representación de un modelo que YA es estático —y por tanto el eslabón más débil de
    toda la cadena de recuperación—. Elegido por medición sobre las 81 preguntas juzgadas,
    con la memoria del contenedor como restricción real (límite 1,95 GB, ~855 MB en reposo):

      int8/128 (antes) : tabla  64 MB · 1er lugar 52% · fuera 19 · nota 29%
      int8/256 (ahora) : tabla 128 MB · 1er lugar 54% · fuera 17 · nota 30%
      float32/256      : tabla 512 MB · 1er lugar 56% · fuera 18 · nota 30%

    float32 gana dos puntos en primer lugar y cuesta 384 MB más en reposo, que en ese
    contenedor es pasar de 1,0 a 1,3 GB — y con un límite de 1,2 GB el kernel ya había
    matado este contenedor antes, así que el margen no es teórico. Las diferencias entre las
    tres son de una o dos preguntas sobre 81 —ruido— EXCEPTO el recall, donde las 256
    dimensiones ganan claro. Así que se toman las dimensiones y se deja la cuantización.
    """
    # DOS FAMILIAS DE MODELO, Y SE DISTINGUEN POR EL NOMBRE. Los estáticos (`potion`, model2vec) son
    # una tabla token→vector y se cargan con StaticModel; un codificador de verdad se carga con
    # sentence-transformers. Se intenta el codificador primero y se cae al estático si no está
    # instalado, para que la imagen vieja siga arrancando en vez de quedarse sin capa semántica.
    # UNA SOLA REGLA PARA DECIDIR SI ES ESTÁTICO, y es la misma que usa el umbral del AVISO. Acá
    # había una segunda, más lista y equivocada: miraba si el directorio traía `config.json` sin
    # `modules.json`. El artefacto montado en `/modelo` no cumplió esa forma, así que se clasificó
    # como codificador, `sentence-transformers` no lo pudo cargar, y el `return None` de abajo —que
    # existe para no colgar el arranque bajando 470 MB— lo mató en vez de dejarlo caer al cargador
    # correcto. Resultado, comprobado en producción el 2026-08-07 con `/kb/salud`: `semantica:false`
    # en las TRES bases, incluidas dos que nada tienen que ver con este cambio.
    #
    # Dos reglas para la misma pregunta se separan; una sola no puede. Si es una RUTA es el
    # artefacto montado, y eso lo carga el cargador estático: no hay nada que adivinar.
    if not _es_modelo_estatico(MODELO):
        try:
            from sentence_transformers import SentenceTransformer
            return SentenceTransformer(MODELO)
        except Exception as e:
            # RUIDOSO A PROPÓSITO. El degradado silencioso de más abajo —quedarse sin capa semántica
            # y seguir sirviendo— es correcto para una falla del modelo, y sería MENTIRA acá: si el
            # modelo configurado es un codificador y la biblioteca no está, lo que corre no es una
            # versión degradada del sistema, es OTRO sistema. Una batería que se corra así mide
            # solo-léxico y reporta el número como si fuera el del buscador.
            print(f"[kb-mcp] AVISO: KB_MODELO={MODELO} pide un codificador y no se pudo cargar "
                  f"({type(e).__name__}). Sin `sentence-transformers` la capa semántica queda "
                  f"APAGADA y cualquier medición hecha así NO describe al servidor. "
                  f"Instalalo, o poné KB_MODELO al modelo estático.", file=sys.stderr)
            # Y NO SE CAE AL CARGADOR ESTÁTICO CON ESTE NOMBRE. Hacerlo intenta bajar un repositorio
            # de 470 MB para leerlo como una tabla que no es: se queda colgado descargando y el
            # servidor no arranca. Sin la biblioteca, este modelo no existe: se sigue sin capa
            # semántica, que es el degradado honesto y ya está avisado arriba.
            return None
    if StaticModel is None:
        return None
    try:
        if Path(MODELO).is_dir():
            # Un modelo ya cuantizado en disco se carga tal cual: re-cuantizarlo lo
            # expandiría a float32 primero.
            return StaticModel.from_pretrained(MODELO)
        return StaticModel.from_pretrained(MODELO, quantize_to="int8")
    except Exception:
        return None


def cargar_modelo():
    """El modelo que usa todo el servidor, ya serializado. Ver `ModeloSerializado`."""
    m = _cargar_modelo_crudo()
    return ModeloSerializado(m) if m is not None else None


def descubrir(raiz: Path) -> list[Path]:
    """Cada subdirectorio con knowledge-base/ es una KB."""
    return sorted(d for d in raiz.iterdir() if (d / "knowledge-base").is_dir())


def armar_rutas(indices: list["Indice"], seguridad) -> tuple[list, list]:
    """Monta cada KB y cada uno de sus niveles, y devuelve (servidores, rutas HTTP).

    Estaba adentro de `main()`. Se sacó afuera porque ahora se llama UNA VEZ POR GENERACIÓN
    del índice: cuando el contenido cambia se arma un juego nuevo de servidores mientras el
    viejo sigue atendiendo. Ver `Planta`.
    """
    from starlette.routing import Mount

    servidores, rutas_http = [], []

    def montar(idx: "Indice", ruta: str, herramientas: list[str] | None = None,
               descripcion: str | None = None, cierre: str | None = None,
               ambitos_texto: str | None = None) -> FastMCP:
        mcp = crear_servidor(idx, herramientas, descripcion, cierre, ambitos_texto)
        mcp.settings.stateless_http = True  # el RC 2026-07-28 elimina las sesiones
        if seguridad:
            mcp.settings.transport_security = seguridad
        rutas_http.append(Mount(ruta, app=mcp.streamable_http_app()))  # crea el session_manager
        return mcp

    for idx in indices:
        # Ruta de siempre: la KB entera. Una KB que no declara niveles termina aca y
        # se comporta exactamente igual que antes de que los niveles existieran.
        servidores.append(montar(idx, f"/{idx.cfg.slug}"))

        # Un montaje mas por cada nivel declarado, con su propio indice acotado y su
        # propia lista de herramientas. Son procesos de busqueda independientes sobre
        # los mismos datos: lo que un nivel no incluye, no existe para el.
        for nombre, cfg_nivel in (idx.cfg.niveles or {}).items():
            if not isinstance(cfg_nivel, dict) or not cfg_nivel.get("campo"):
                print(f"[kb-mcp] {idx.cfg.slug}: nivel '{nombre}' sin campo; se omite", flush=True)
                continue
            vista = idx.restringir(cfg_nivel["campo"], cfg_nivel.get("valor", True))
            servidores.append(montar(vista, f"/{idx.cfg.slug}-{nombre}",
                                     cfg_nivel.get("herramientas"),
                                     cfg_nivel.get("descripcion"),
                                     cfg_nivel.get("cierre"),
                                     cfg_nivel.get("ambitos")))
            print(f"[kb-mcp]   nivel '{nombre}': {len(vista.nodos)} entradas, "
                  f"herramientas={cfg_nivel.get('herramientas') or 'todas'}", flush=True)

    return servidores, rutas_http


# ── LA PLANTA: el índice se cambia sin cortar el servicio ────────────────────────────────
#
# POR QUÉ EXISTE, y es un requisito de Martín del 2026-08-08, no una optimización.
# Hasta hoy `sync-kb.sh` REINICIABA EL CONTENEDOR ENTERO en cada cambio de contenido —28
# veces el 2026-08-07— y durante ese reinicio la base NO CONTESTA A NADIE. Con la tabla
# estática eran ~8,7 s cada vez; con un codificador de verdad son 49 s sin caché, o sea
# catorce minutos diarios de servicio caído. Eso era lo que volvía indesplegable al
# codificador, y por eso se arregla acá y no en el que reinicia.
#
# Su instrucción, textual: «mientras la base vieja sigue andando y se está reconstruyendo,
# tú sirves una copia; y solo cuando la versión nueva y desplegada esté 100% disponible,
# haces un cambio que toma menos de un segundo y dejas de servir el caché».
#
# Eso es exactamente lo que hace esta clase, y las tres propiedades importan:
#
#   1. EL ÍNDICE NUEVO SE CONSTRUYE EN UN HILO (`asyncio.to_thread`). Si se construyera en
#      el bucle de eventos, la generación vieja no podría atender mientras tanto y no
#      habríamos arreglado nada — habríamos movido la caída de lugar.
#   2. EL CAMBIO ES UNA ASIGNACIÓN DE PUNTERO, después de que la generación nueva ya está
#      montada y con sus gestores de sesión andando. No hay ninguna ventana en que no haya
#      un índice servible.
#   3. SI LA CONSTRUCCIÓN FALLA, NO SE CAMBIA NADA. La generación vieja sigue sirviendo y
#      el error queda a la vista en `/salud`. Un contenido roto ya no puede tumbar la base:
#      antes el reinicio se llevaba puesto lo que había, que es la forma en que el
#      2026-08-07 las tres bases quedaron sin capa semántica.
#
# EL DISPARADOR ES SIGHUP Y NO UNA RUTA HTTP, a propósito. Caddy proxea `/kb/*` entero al
# backend sin exigir secreto (así es como `/kb/salud` es público hoy), de modo que
# cualquier ruta nueva quedaría alcanzable desde internet por cualquiera. Una señal no
# tiene superficie de red: la manda quien ya está adentro del servidor.
#
# QUÉ TENDRÍA QUE PASAR PARA QUE ESTO DIJERA QUE NO: si el índice nuevo no se puede
# construir, `recargar()` devuelve False, `/salud` publica `error_ultima_recarga` y la
# generación NO avanza. `sync-kb.sh` lee ese código de salida y lo dice con hora. La forma
# de sabotearlo está probada: se le da una KB con un `mcp.yaml` ilegible y la generación se
# queda donde estaba, sirviendo.
class Planta:
    """Sostiene la generación viva del servidor y sabe cambiarla sin cortar el servicio."""

    def __init__(self, fijas: list[Path], directorio: Path | None, seguridad, modelo,
                 gracia: float = 30.0):
        # LAS RUTAS SE VUELVEN A DESCUBRIR EN CADA GENERACIÓN, no se congelan al arrancar.
        # Con la lista congelada, una KB agregada a /opt/kb no aparecía hasta un reinicio de
        # verdad — o sea que el cambio en caliente arreglaba el caso frecuente y dejaba mudo
        # el caso nuevo, que es peor que no arreglar nada porque nadie lo esperaría. Se
        # encontró probando el sabotaje: la KB rota que la prueba metía no la veía nadie.
        self.fijas, self.directorio = fijas, directorio
        self.seguridad, self.modelo = seguridad, modelo
        # Cuánto se deja viva la generación anterior después del cambio, para que las
        # peticiones que ya estaban en vuelo terminen contra el índice con el que
        # empezaron. Cerrarla en el acto cortaría justamente lo que esto viene a evitar.
        self.gracia = gracia
        self.generacion = 0
        self.app = None
        self.indices: list["Indice"] = []
        self._pila: contextlib.AsyncExitStack | None = None
        self.recargando = False
        self.ultima_recarga: str | None = None
        self.ultimo_error: str | None = None
        self.duracion_ultima: float | None = None
        self._lock = asyncio.Lock()

    # ── construcción ──────────────────────────────────────────────────────────────────
    def rutas(self) -> list[Path]:
        r = list(self.fijas)
        if self.directorio:
            r += descubrir(self.directorio)
        return r

    def _construir_indices(self) -> list["Indice"]:
        """CPU pura. Se llama SIEMPRE desde un hilo, nunca desde el bucle de eventos.

        SE LE BAJA LA PRIORIDAD AL HILO, y no es cosmético. En Linux la prioridad es por hilo,
        así que esto solo afecta a la reconstrucción y deja al que atiende ganando el reparto de
        CPU. Sin esto, medido en contenedor con el codificador, la peor latencia de una consulta
        durante una recarga llegaba a 7,3 s: el servidor contestaba todo —cero fallos— pero
        contestaba tarde, y el VPS tiene DOS núcleos, o sea que ahí sería peor. Lo único que se
        paga es que la reconstrucción tarde un poco más, y eso ya no le cuesta nada a nadie:
        desde que no corta el servicio, cuánto tarda dejó de ser un problema de disponibilidad.
        """
        with contextlib.suppress(OSError, AttributeError):
            os.nice(10)
        rutas = self.rutas()
        if not rutas:
            raise RuntimeError("no hay ninguna KB que servir")
        return [Indice(r, self.modelo) for r in rutas]

    async def _montar(self, indices: list["Indice"]):
        from starlette.applications import Starlette
        servidores, rutas_http = armar_rutas(indices, self.seguridad)
        pila = contextlib.AsyncExitStack()
        try:
            for s in servidores:
                await pila.enter_async_context(s.session_manager.run())
        except BaseException:
            # Si un gestor de sesión no arranca, se deshace lo que sí arrancó y se
            # propaga: una generación a medio montar no se sirve jamás.
            await pila.aclose()
            raise
        return Starlette(routes=rutas_http), pila

    def _anunciar(self, indices: list["Indice"]) -> None:
        for i in indices:
            print(f"[kb-mcp] {i.cfg.slug}: {len(i.nodos)} entradas, "
                  f"polos={list(i.cfg.polos)}, "
                  f"semantica={'sí' if i.vectores is not None else 'no'}", flush=True)

    async def arrancar(self) -> None:
        t0 = time.monotonic()
        indices = await asyncio.to_thread(self._construir_indices)
        app, pila = await self._montar(indices)
        self.app, self._pila, self.indices = app, pila, indices
        self.generacion = 1
        self.duracion_ultima = round(time.monotonic() - t0, 2)
        self.ultima_recarga = datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds")
        self._anunciar(indices)
        print(f"[kb-mcp] generación 1 en línea en {self.duracion_ultima}s", flush=True)

    async def recargar(self) -> tuple[bool, str]:
        """Construye una generación nueva y la cambia. Devuelve (cambió, detalle)."""
        if self._lock.locked():
            return False, "ya hay una recarga en curso"
        async with self._lock:
            self.recargando = True
            t0 = time.monotonic()
            try:
                indices = await asyncio.to_thread(self._construir_indices)
                app, pila = await self._montar(indices)
            except Exception as e:
                self.ultimo_error = f"{type(e).__name__}: {e}"
                self.recargando = False
                # La traza entera va al REGISTRO y el mensaje corto a `/salud`. Sin la traza,
                # la primera recarga que falló de verdad —un IndexError por usar el modelo
                # desde dos hilos a la vez— hubo que reproducirla a mano para ubicarla.
                import traceback
                print(f"[kb-mcp] RECARGA FALLÓ, sigue sirviendo la generación "
                      f"{self.generacion}: {self.ultimo_error}\n" + traceback.format_exc(),
                      file=sys.stderr, flush=True)
                return False, self.ultimo_error

            # ── EL CAMBIO. Todo lo caro ya pasó; esto es asignar punteros. ──
            vieja = self._pila
            self.app, self._pila, self.indices = app, pila, indices
            self.generacion += 1
            self.duracion_ultima = round(time.monotonic() - t0, 2)
            self.ultima_recarga = datetime.datetime.now(datetime.timezone.utc).isoformat(
                timespec="seconds")
            self.ultimo_error = None
            self.recargando = False
            self._anunciar(indices)
            print(f"[kb-mcp] generación {self.generacion} en línea "
                  f"(se armó en {self.duracion_ultima}s, sin cortar el servicio)", flush=True)
            asyncio.get_running_loop().create_task(self._jubilar(vieja))
            return True, f"generación {self.generacion}"

    async def _jubilar(self, pila) -> None:
        if pila is None:
            return
        await asyncio.sleep(self.gracia)
        with contextlib.suppress(Exception):
            await pila.aclose()

    async def apagar(self) -> None:
        if self._pila is not None:
            with contextlib.suppress(Exception):
                await self._pila.aclose()
            self._pila = None

    # ── lo que se publica ─────────────────────────────────────────────────────────────
    def salud(self) -> dict:
        """El estado sale del proceso vivo, no de un documento que alguien mantenga.

        Las tres claves de siempre —`kbs`, con `slug`, `entradas` y `semantica`— se
        conservan tal cual: `sync-kb.sh`, el handoff y la batería las leen. Lo que se
        agrega dice si el cambio en caliente está funcionando, que hasta hoy no se podía
        saber desde afuera.
        """
        return {
            "kbs": [{"slug": i.cfg.slug, "entradas": len(i.nodos),
                     "semantica": i.vectores is not None} for i in self.indices],
            "generacion": self.generacion,
            "recargando": self.recargando,
            "desde": self.ultima_recarga,
            "armado_en_s": self.duracion_ultima,
            "error_ultima_recarga": self.ultimo_error,
            "modelo": MODELO,
            # LA DEGRADACIÓN SE PUBLICA. La primera versión de la fecha por sub-entrada perdía el
            # 41 % de las sub-entradas —el blame fallaba en los archivos más activos— y reportaba
            # exactamente igual que si funcionara entera. Una capacidad a medias que no se queja no
            # se arregla nunca: nadie sale a buscar lo que no duele.
            "fecha_por_subentrada": [
                dict(kb=i.cfg.slug, **getattr(i, "diag_fechas_sub", {}))
                for i in self.indices],
        }

    def __repr__(self) -> str:  # útil en el registro
        return f"<Planta gen={self.generacion} kbs={[i.cfg.slug for i in self.indices]}>"


def _con_desfase(epoca: int) -> str:
    """`2026-08-08 17:48 −04:00` — la hora local del servidor, diciendo cuál es.

    El signo se escribe con el menos tipográfico a propósito: el guion corriente se confunde con
    el separador de la fecha cuando alguien lee la línea rápido, y quien lee esto casi siempre es
    un modelo que después tiene que restar horas.
    """
    t = datetime.datetime.fromtimestamp(epoca).astimezone()
    off = t.strftime("%z")  # p.ej. -0400
    return f"{t.strftime('%Y-%m-%d %H:%M')} {'−' if off[0] == '-' else '+'}{off[1:3]}:{off[3:]}"


def zona_declarada() -> str:
    """Cómo se nombra la zona en la que este servidor registra las horas."""
    ahora = datetime.datetime.now().astimezone()
    off = ahora.strftime("%z")
    # El nombre solo se agrega si DICE algo. En muchos sistemas `tzname()` devuelve el propio
    # desfase —«-04»— y entonces la línea quedaba «UTC−4 (-04)», que repite el dato y ensucia.
    nombre = (ahora.tzname() or "").strip()
    util = nombre and not re.fullmatch(r"[+-]?\d{2}(:?\d{2})?", nombre)
    return f"UTC{'−' if off[0] == '-' else '+'}{int(off[1:3])}" + (f" ({nombre})" if util else "")


async def _responder_json(send, codigo: int, cuerpo: dict) -> None:
    datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
    await send({"type": "http.response.start", "status": codigo,
                "headers": [(b"content-type", b"application/json; charset=utf-8"),
                            (b"content-length", str(len(datos)).encode())]})
    await send({"type": "http.response.body", "body": datos})


def main() -> None:
    p = argparse.ArgumentParser(description="Servidor MCP de solo lectura para KBs de kb-template")
    p.add_argument("--kb", action="append", default=[], help="Raiz de una KB (repetible)")
    p.add_argument("--kbs", help="Directorio que contiene varias KB")
    p.add_argument("--transport", default="stdio", choices=["stdio", "streamable-http"])
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    a = p.parse_args()

    rutas = [Path(k) for k in a.kb]
    if a.kbs:
        rutas += descubrir(Path(a.kbs))
    if not rutas:
        p.error("indica --kb RUTA o --kbs DIRECTORIO")

    modelo = cargar_modelo()  # una sola vez, compartido por todas las KB y por todas las generaciones

    if a.transport == "stdio":
        if len(rutas) > 1:
            p.error("stdio sirve una sola KB; usa --kb una vez")
        idx = Indice(rutas[0], modelo)
        print(f"[kb-mcp] {idx.cfg.slug}: {len(idx.nodos)} entradas, "
              f"polos={list(idx.cfg.polos)}, "
              f"semantica={'sí' if idx.vectores is not None else 'no'}", flush=True)
        crear_servidor(idx).run(transport="stdio")
        return

    import uvicorn

    hosts = [h.strip() for h in os.environ.get("KB_ALLOWED_HOSTS", "").split(",") if h.strip()]
    seguridad = TransportSecuritySettings(
        allowed_hosts=hosts,
        allowed_origins=[f"https://{h}" for h in hosts] + [f"http://{h}" for h in hosts],
    ) if hosts else None

    planta = Planta([Path(k) for k in a.kb], Path(a.kbs) if a.kbs else None,
                    seguridad, modelo, gracia=float(os.environ.get("KB_GRACIA", "30")))

    def _pedir_recarga() -> None:
        """Manejador de SIGHUP. Solo agenda: el trabajo va en el bucle, nunca en la señal."""
        asyncio.get_running_loop().create_task(planta.recargar())

    async def raiz(scope, receive, send):
        """ASGI de afuera. Es fino a propósito: solo `/salud` y el delegado a la generación viva.

        Todo lo demás lo atiende `planta.app`, que es la aplicación Starlette de la
        generación actual. Leer el puntero en cada petición es lo que permite cambiarlo:
        una petición que llega un microsegundo después del cambio ya va a la nueva, y las
        que estaban en vuelo terminan contra la vieja, que sigue montada durante la gracia.
        """
        if scope["type"] == "lifespan":
            while True:
                mensaje = await receive()
                if mensaje["type"] == "lifespan.startup":
                    try:
                        await planta.arrancar()
                    except BaseException as e:  # noqa: BLE001 — hay que reportarlo al servidor
                        await send({"type": "lifespan.startup.failed",
                                    "message": f"{type(e).__name__}: {e}"})
                        return
                    with contextlib.suppress(NotImplementedError, RuntimeError, AttributeError):
                        asyncio.get_running_loop().add_signal_handler(
                            signal.SIGHUP, _pedir_recarga)
                        print("[kb-mcp] SIGHUP recarga el índice sin cortar el servicio",
                              flush=True)
                    await send({"type": "lifespan.startup.complete"})
                elif mensaje["type"] == "lifespan.shutdown":
                    await planta.apagar()
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope["type"] == "http" and scope.get("path") == "/salud":
            await _responder_json(send, 200, planta.salud())
            return
        actual = planta.app
        if actual is None:
            await _responder_json(send, 503, {"error": "el índice todavía no está armado"})
            return
        await actual(scope, receive, send)

    uvicorn.run(raiz, host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
