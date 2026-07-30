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
import collections
import contextlib
import copy
import datetime
import math
import textwrap
import os
import re
import sqlite3
import subprocess
import unicodedata
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

try:
    import snowballstemmer
    _STEM = snowballstemmer.stemmer("spanish").stemWord
except ImportError:  # sin stemmer se degrada a busqueda exacta, no se cae
    _STEM = None

try:
    import numpy as np
    from model2vec import StaticModel
except ImportError:  # sin capa semantica queda solo la lexica, no se cae
    np = None
    StaticModel = None

MODELO = os.environ.get("KB_MODELO", "minishlab/potion-multilingual-128M")

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
OPERADORES = re.compile(r'["*:()]|\b(AND|OR|NOT|NEAR)\b')
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
        return ""
    abiertos = [b for b in bloques
                if any("**Estado:**" in x and "abierto" in x.lower() for x in b)]
    elegido = (abiertos or bloques)[0]
    return " ".join(" ".join(elegido).split())


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


def fechas_git(raiz: Path, base: Path) -> dict[str, tuple[int, int]]:
    """Por cada .md, (primer commit, ultimo commit) segun git. La temporalidad de
    un grafo que crece vive en su historial, no en el frontmatter. Un solo `git log`
    recorre todo: O(commits), no O(archivos*commits). Devuelve {} si no hay historial
    (p.ej. clon shallow) para degradar a orden alfabetico sin fallar."""
    try:
        salida = subprocess.run(
            ["git", "-C", str(raiz), "log", "--format=%at", "--name-only",
             "--no-renames", "--", "knowledge-base"],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return {}

    fechas: dict[str, tuple[int, int]] = {}
    ts = 0
    for linea in salida.splitlines():
        linea = linea.strip()
        if linea.isdigit():
            ts = int(linea)
        elif linea.endswith(".md") and ts:
            try:
                rel = str(Path(linea).relative_to("knowledge-base"))
            except ValueError:
                continue
            prev = fechas.get(rel)
            # Se recorre de mas nuevo a mas viejo: primer avistamiento = ultimo commit.
            if prev is None:
                fechas[rel] = (ts, ts)
            else:
                fechas[rel] = (ts, prev[1])
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
            creado, modificado = fechas.get(str(rel), (0, 0))
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
                es_indice=es_indice,
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
        return " OR ".join(grupos) if grupos else consulta

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
        if self.modelo is None:
            return
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
                textos.append(f"{nombre} — {titulo}\n{sub[:1500]}")
                self.orden.append(nombre)
                self.es_cabecera.append(False)
        V = self.modelo.encode(textos).astype("float32")
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
        orden = (self.orden[i] for i in np.argsort(-(self.vectores @ v)))
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
            partes.append(f"actualizada {datetime.date.fromtimestamp(n.modificado).isoformat()}")
        # Frescura declarada al lector en cada resultado. Comparacion de fechas pura
        # (calendario por tipo, kb/mcp.yaml `retencion`); el juicio de si la entrada
        # sigue siendo verdad pertenece a la calibracion, no al servidor.
        plazo = self.cfg.retencion.get(str(n.meta.get("tipo")))
        if plazo:
            sello = n.meta.get("verificado")
            try:
                fecha_sello = (sello if isinstance(sello, datetime.date)
                               else datetime.date.fromisoformat(str(sello)))
            except (TypeError, ValueError):
                fecha_sello = None
            if fecha_sello is None:
                partes.append("sin fecha de verificación — tratar como no confirmada")
            elif (datetime.date.today() - fecha_sello).days > plazo:
                partes.append(f"re-verificación VENCIDA (sellada {fecha_sello.isoformat()}) "
                              "— tratar como no confirmada")
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
        return "\n*También en esta entrada:* " + " · ".join(fuera[:8])

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

    def _extracto_bruto(self, nombre: str, consulta_fts: str, extendido: bool = False) -> str:
        # Primero: la SUB-ENTRADA que mejor calza, servida entera. Es la unidad atómica de
        # esta base —título, ficha de campos y evidencia— así que servirla completa entrega
        # la respuesta en vez de una ventana adivinada alrededor de una coincidencia. Las
        # cuatro máquinas de ventana que siguen abajo existían por no tener esta unidad, y
        # quedan como respaldo para el acierto puramente semántico, donde no hay coincidencia
        # literal que localizar.
        try:
            fila = self.db.execute(
                "SELECT sub, crudo FROM subdocs WHERE subdocs MATCH ? AND nombre = ? "
                "ORDER BY rank LIMIT 1", (consulta_fts, nombre)).fetchone()
            if fila and fila[0]:
                plano = " ".join(fila[1].split())
                tope = 2600 if extendido else 1800
                if len(plano) <= tope:
                    return plano
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


def con_dominio(cabecera: str):
    """Antepone la cabecera de dominio al docstring, antes de que FastMCP lo lea.

    Se aplica por dentro de @mcp.tool() —el decorador de mas abajo corre primero—,
    asi que el registro ya ve la descripcion completa. Evita duplicar el texto o
    tocar la API privada del gestor de herramientas.
    """
    def decorar(fn):
        fn.__doc__ = f"{cabecera}\n\n{textwrap.dedent(fn.__doc__ or '').strip()}"
        return fn
    return decorar


def crear_servidor(idx: Indice, herramientas: list[str] | None = None) -> FastMCP:
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
        f"Base de conocimiento «{cfg.nombre}» ({len(idx.nodos)} entradas)"
        + (f" sobre {cfg.descripcion}" if cfg.descripcion else "")
        + ". "
        + (f"Cubre, entre otros: {', '.join(centrales)}. " if centrales else "")
        + "Es la fuente propia del equipo sobre ese dominio, con su vocabulario y sus "
          "fuentes: consúltala siempre que la pregunta caiga ahí, incluso si crees "
          "saber la respuesta, porque aquí está la versión vigente y contrastable. "
          "No la uses para preguntas ajenas a ese dominio: no contiene conocimiento "
          "general ni el contenido de otras bases, y no devuelve nada que no esté "
          f"escrito en ella. Ámbitos para acotar la búsqueda: {ambitos}. "
          "Es de solo lectura: ninguna de sus herramientas modifica la base."
    )

    mcp = FastMCP(cfg.slug, instructions=(
        f"{dominio}\n\n"
        "Tres herramientas, en orden de uso habitual: `consultar` para preguntar sin "
        "saber dónde está la respuesta; `leer` para el texto íntegro de una entrada "
        "que ya sabes cómo se llama; `panorama` para ver qué cubre la base o el mapa "
        "de un tema. Cada resultado trae su fecha de última actualización y las "
        "entradas conectadas, para seguir el hilo sin volver a buscar. Es de solo "
        "lectura: no hay forma de modificar la base desde aquí. El contenido es una "
        "obra en curso de madurez desigual; cita las fuentes que cada entrada declara "
        "cuando la respuesta vaya a sostener una decisión."
    ))

    def registrar(fn):
        """Registra la herramienta solo si este nivel la incluye. Si no, la funcion
        queda definida pero nunca se declara al cliente: no aparece en el listado ni
        se puede invocar."""
        return mcp.tool()(fn) if permitida(fn.__name__) else fn

    # Preguntas por PROPIEDAD (estado, tipo, fecha) que la búsqueda por significado
    # contesta mal por diseño: devuelve lo más parecido, no todo lo que cumple. En vez
    # de confiar en que quien consulte se acuerde de `listar`, el servidor lo detecta y
    # lo dice en la respuesta. Que una sesión nueva use bien la base no puede depender
    # de que haya leído la documentación (decisión de Martín, 2026-07-29).
    POR_PROPIEDAD = re.compile(
        r"(qu[eé]\s+(se\s+)?(arregl|resolvi|resuelt|cerr)|"
        r"qu[eé]\s+(est[aá]|hay|queda|falta)\s+(abierto|pendiente|sin\s+resolver)|"
        r"qu[eé]\s+.{0,20}(mostrar|mostrarle|ense[nñ]ar).{0,20}(fundador|direcci[oó]n|project|pm)|"
        r"qu[eé]\s+(medicion|hallazgo|plan|pedido)e?s\s+hay|"
        r"lista\s+de\s+(hallazgos|pendientes|resueltos))", re.I)

    @registrar
    @con_dominio(dominio)
    def consultar(pregunta: str, ambito: str | None = None,
                  orden: str = "relevancia", limite: int = 6,
                  detalle: str = "normal") -> str:
        """Busca en esta base de conocimiento y devuelve los pasajes más relevantes.

        Esta es la herramienta de entrada: úsala siempre que tengas una pregunta y no
        sepas de antemano en qué entrada está la respuesta. Si ya conoces el nombre de
        la entrada que quieres, usa `leer` en su lugar; si quieres un mapa del terreno
        antes de preguntar, usa `panorama`.

        Escribe la pregunta en lenguaje natural, como se la harías a una persona.
        Singular y plural, género y tildes son indiferentes ("residuo" halla
        "residuos", "gestion" halla "Gestión"), y encuentra por significado aunque tu
        pregunta no comparta ninguna palabra con el texto. Para exigir una frase
        textual, enciérrala en comillas dobles.

        Devuelve una lista de entradas; por cada una: su título, su ámbito, su fecha de
        última actualización, un extracto del pasaje pertinente, y los títulos de las
        entradas conectadas a ella (para seguir el hilo con `leer` sin volver a
        buscar). El contenido es una obra en curso con entradas de madurez desigual:
        cada una cita sus fuentes y conviene contrastar lo importante contra ellas.

        No devuelve el texto completo de las entradas, solo el extracto pertinente de
        cada una: para el contenido íntegro, llama después a `leer` con el título que
        esta herramienta te devolvió. Tampoco completa con conocimiento externo — si la
        base no dice nada del tema, responde que no encontró nada, y esa respuesta es
        informativa: significa que la base no lo cubre.

        Parámetros:
          pregunta: la consulta en lenguaje natural (obligatoria).
          ambito: acota a un área de la base (los valores dependen de cada base; si
                  te equivocas, la herramienta te devuelve los disponibles). Omítelo
                  para buscar en toda la base.
          orden: 'relevancia' (por defecto) o 'reciente'. Usa 'reciente' cuando la
                 intención es temporal —«¿qué bitácoras hay?», «lo último sobre X»—:
                 la pregunta acota el tema y la fecha de git decide el orden.
          limite: número de entradas a devolver (1–20, por defecto 6).
          detalle: 'normal' (por defecto) o 'extendido'. Con 'extendido' cada
                 entrada trae un pasaje ~3× más largo alrededor de la coincidencia
                 y el doble de entradas conectadas. Úsalo cuando necesites que una
                 sola llamada rinda el máximo contexto; los extractos siguen siendo
                 parciales — para el texto íntegro la vía sigue siendo `leer`.
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
        except sqlite3.OperationalError as e:
            return f"No pude interpretar esa consulta ({e}). Prueba con palabras sueltas."

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
            if cercania is not None and cercania < 0.15:
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
                if sin_calce == len(grupos_fts) or (cercania is not None
                                                    and cercania < 0.32):
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
                    if len(idx.relacionados(nom)) > umbral_hub:
                        puntaje[nom] = sc * 0.55

        if reciente:
            # Dos partes. (a) Sembrar el pozo con lo MAS NUEVO del corpus aunque no sea
            # tematicamente top: "¿qué es lo último?" debe poder traer el commit mas
            # reciente aunque no matchee la consulta. (b) Recencia como MULTIPLICADOR de
            # la relevancia, no como orden que la reemplaza (el hard-sort por fecha es el
            # error que la practica de 2026 desaconseja: un nodo irrelevante pero nuevo
            # no debe dominar). "Ahora" es el commit mas nuevo, sin depender del reloj.
            recientes = idx.recientes(polo, tope=n * 2)
            for pos, nom in enumerate(recientes):
                puntaje[nom] = puntaje.get(nom, 0.0) + 0.5 / (5 + pos)
            ahora = max((nd.modificado for nd in idx.nodos.values()), default=0)
            HALF_LIFE = 45 * 86400  # media vida de 45 dias
            for nom in list(puntaje):
                mod = idx.nodos[nom].modificado
                if mod:
                    puntaje[nom] *= 1 + 5.0 * math.exp(-(ahora - mod) / HALF_LIFE)
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
            cabeza = list(ganadores)
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
        if hubs and not exacto:
            sin_hub = [g for g in ganadores if g not in hubs]
            if sin_hub:
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
        if POR_PROPIEDAD.search(pregunta):
            # Decirle al lector «usá otra herramienta» es peor que usarla por él: en una
            # pregunta por propiedad la respuesta exacta ya se puede calcular acá, y hacerlo
            # ahorra un viaje y evita que se quede con el resultado aproximado, que es
            # justamente el que engaña. Si el filtro no se puede deducir o la llamada falla,
            # queda el aviso solo — nunca menos que antes.
            q = pregunta.lower()
            filtro = None
            if re.search(r"resuelt|arregl|cerr", q):
                filtro = "resuelto"
            elif re.search(r"abierto|pendiente|sin\s+resolver|falta|queda", q):
                filtro = "abierto"
            exacto_txt = ""
            if filtro:
                try:
                    exacto_txt = listar(estado=filtro)
                except Exception:
                    exacto_txt = ""
            if exacto_txt:
                redirigir = (
                    "⚠ Preguntaste por una PROPIEDAD (estado, tipo, fecha), no por un tema. La "
                    "búsqueda por significado devuelve lo más parecido, no todo lo que cumple, "
                    f"así que acá va primero la respuesta EXACTA —listar(estado=\"{filtro}\")— y "
                    "después lo que encontró la búsqueda.\n\n"
                    f"{exacto_txt}\n\n── y esto encontró la búsqueda por significado ──\n\n")
            else:
                redirigir = ("⚠ Esta pregunta es por una PROPIEDAD (estado, tipo, fecha), no por un "
                             "tema. La búsqueda por significado devuelve lo más parecido, no todo lo "
                             "que cumple, así que puede faltarte algo. Para la respuesta exacta y "
                             "completa usa `listar` — por ejemplo listar(estado=\"resuelto\") o "
                             "listar(estado=\"abierto\"). Abajo va lo que encontró la búsqueda.\n\n")
        partes = [redirigir + aviso + f"{len(ganadores)} entrada(s) sobre «{pregunta}»\n"]
        for nom in ganadores:
            partes.append(
                f"### {idx.fuente(idx.nodos[nom])}\n{idx.extracto(nom, args[0], extendido)}")
            if vecinos := idx.relacionados(nom)[:12 if extendido else 6]:
                partes.append(f"*Conecta con:* {', '.join(vecinos)}")
            partes.append("")
        partes.append("Usa leer(tema) para el texto completo de cualquiera de estas.")
        return "\n".join(partes)

    @registrar
    @con_dominio(dominio)
    def leer(tema: str) -> str:
        """Devuelve el texto íntegro y verbatim de una entrada, por su nombre.

        Úsala cuando ya sabes qué entrada quieres —normalmente porque `consultar` te
        la mostró, o el usuario la nombró— y necesitas su contenido completo, no un
        extracto. Si no sabes el nombre exacto, usa `consultar` primero.

        Acepta el nombre aproximado: resuelve tildes, mayúsculas y coincidencias
        parciales, y prefiere la entrada base sobre sus variantes. Devuelve el título,
        el ámbito, la fecha de última actualización, el cuerpo Markdown completo tal
        como está escrito, y al final las entradas conectadas más las variantes de
        nombre que existan, si las hay.

        No busca por tema ni por significado: solo resuelve nombres. Si el nombre que
        pasas no identifica con claridad a una entrada, no devuelve contenido —nunca
        adivina entre homónimos— sino la lista de candidatas para que elijas.

        Parámetros:
          tema: el nombre (o una aproximación) de la entrada a leer.
        """
        candidatos, confianza = idx.resolver(tema)
        if not candidatos:
            return f"No encontré una entrada llamada «{tema}». Prueba con consultar()."
        # Match debil (solo raices compartidas): NO se entrega contenido, porque puede
        # ser un homonimo. Se ofrecen candidatos —por raiz Y por significado, para
        # captar sinonimos y siglas: "responsabilidad extendida" sugiere "Ley 20.920
        # (Ley REP)" via semantica aunque el titulo no comparta las palabras.
        if confianza == "debil":
            sugeridos = list(dict.fromkeys(candidatos[:4] + idx.semejantes(tema, tope=5)))[:8]
            lista = "\n".join(f"  - {c}" for c in sugeridos)
            return (f"No hay una entrada que se llame exactamente «{tema}». Puede que "
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
    @con_dominio(dominio)
    def listar(estado: str | None = None, tipo: str | None = None,
               desde: str | None = None, mostrable: bool | None = None) -> str:
        """Lista sub-entradas filtrando por sus campos. Exacto, no por parecido.

        `consultar` busca por significado y devuelve lo más cercano. Esto es lo otro:
        recorre las fichas de campos y devuelve TODAS las que cumplen, sin ranking y sin
        omitir ninguna. Úsala cuando la pregunta es por una propiedad y no por un tema.

        Para qué sirve, en concreto:
          · «¿qué se arregló esta semana?» → listar(estado="resuelto", desde="2026-07-27")
          · «¿qué le puedo mostrar al fundador?» → listar(estado="resuelto", mostrable=True)
          · «¿qué está abierto?» → listar(estado="abierto")
          · «¿qué mediciones hay?» → listar(tipo="medicion")

        Parámetros:
          estado:    vigente · resuelto · abierto · aceptado · registrado
          tipo:      hallazgo · funcionamiento · medicion · contexto
          desde:     fecha ISO; solo lo verificado en esa fecha o después
          mostrable: True devuelve solo lo que puede verse fuera del equipo técnico;
                     False, solo lo interno. Se omite para no filtrar por eso.
        """
        filas = []
        for nombre, nd in idx.nodos.items():
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
                if estado and campos.get("Estado", "").lower() != estado.lower():
                    continue
                if tipo and campos.get("Tipo", "").lower() != tipo.lower():
                    continue
                if mostrable is not None:
                    pub = campos.get("Publicable", "").lower() in ("sí", "si", "true")
                    if pub != mostrable:
                        continue
                fecha = campos.get("Verificado") or campos.get("Checkpoint") or ""
                if desde and fecha < desde:
                    continue
                filas.append((fecha, nombre, titulo, campos))
        if not filas:
            return "Nada cumple ese filtro. Prueba aflojando alguno, o usa panorama()."
        filas.sort(key=lambda x: (x[0], x[1]), reverse=True)
        criterio = " · ".join(x for x in [
            f"estado={estado}" if estado else None,
            f"tipo={tipo}" if tipo else None,
            f"desde={desde}" if desde else None,
            ("mostrable" if mostrable else "solo interno") if mostrable is not None else None,
        ] if x) or "sin filtro"
        salida = [f"{len(filas)} sub-entrada(s) — {criterio}\n"]
        actual = None
        for fecha, nombre, titulo, campos in filas:
            if nombre != actual:
                salida.append(f"\n**{nombre}**")
                actual = nombre
            marca = campos.get("Tipo", "")
            salida.append(f"  · {fecha or 'sin fecha'} — {titulo}" + (f"  ({marca})" if marca else ""))
        return "\n".join(salida)

    @registrar
    @con_dominio(dominio)
    def panorama(tema: str | None = None) -> str:
        """Da una vista de conjunto: el inventario de la base, o el mapa de un tema.

        Úsala para orientarte antes de preguntar, o cuando la intención del usuario es
        panorámica y no puntual: «¿qué hay acá?», «¿de qué trata esto?», «¿qué se
        conecta con X?». Para responder una pregunta concreta, usa `consultar`.

        Sin argumentos: devuelve cuántas entradas hay, cómo se reparten por área, y las
        entradas más conectadas de cada una (los nodos centrales de la base). Con un
        tema: devuelve las entradas vecinas a ese tema en el grafo, cada una con una
        línea de resumen — la forma rápida de entender un área sin leerla completa.

        No responde preguntas de contenido ni devuelve el texto de las entradas: sirve
        para saber qué existe y cómo se relaciona, no qué dice. Para lo segundo, usa
        `consultar` o `leer`.

        Parámetros:
          tema: opcional. El nombre de una entrada para ver su vecindario; si se omite,
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
                return f"«{nodo.nombre}» no está conectada a otras entradas todavía."
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
        lineas = [f"**{cfg.nombre}** — {len(idx.nodos)} entradas"
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

def cargar_modelo():
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


def descubrir(raiz: Path) -> list[Path]:
    """Cada subdirectorio con knowledge-base/ es una KB."""
    return sorted(d for d in raiz.iterdir() if (d / "knowledge-base").is_dir())


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

    modelo = cargar_modelo()  # una sola vez, compartido por todas las KB
    indices = [Indice(r, modelo) for r in rutas]
    for i in indices:
        print(f"[kb-mcp] {i.cfg.slug}: {len(i.nodos)} entradas, "
              f"polos={list(i.cfg.polos)}, semantica={'sí' if i.vectores is not None else 'no'}",
              flush=True)

    if a.transport == "stdio":
        if len(indices) > 1:
            p.error("stdio sirve una sola KB; usa --kb una vez")
        crear_servidor(indices[0]).run(transport="stdio")
        return

    import uvicorn
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route

    hosts = [h.strip() for h in os.environ.get("KB_ALLOWED_HOSTS", "").split(",") if h.strip()]
    seguridad = TransportSecuritySettings(
        allowed_hosts=hosts,
        allowed_origins=[f"https://{h}" for h in hosts] + [f"http://{h}" for h in hosts],
    ) if hosts else None

    # Cada KB SOLO bajo su slug: /<slug>/mcp. No hay KB por defecto en la raiz —
    # siempre hay que nombrar la KB. Esto deja lista una futura autorizacion por-KB:
    # cada ruta es un recurso distinto que un token podra habilitar o no.
    servidores, rutas_http = [], []

    def montar(idx: Indice, ruta: str, herramientas: list[str] | None = None) -> FastMCP:
        mcp = crear_servidor(idx, herramientas)
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
                                     cfg_nivel.get("herramientas")))
            print(f"[kb-mcp]   nivel '{nombre}': {len(vista.nodos)} entradas, "
                  f"herramientas={cfg_nivel.get('herramientas') or 'todas'}", flush=True)

    async def salud(_):
        return JSONResponse({"kbs": [{"slug": i.cfg.slug, "entradas": len(i.nodos),
                                      "semantica": i.vectores is not None} for i in indices]})

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        async with contextlib.AsyncExitStack() as pila:
            for s in servidores:
                await pila.enter_async_context(s.session_manager.run())
            yield

    app = Starlette(routes=[Route("/salud", salud)] + rutas_http, lifespan=lifespan)
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
