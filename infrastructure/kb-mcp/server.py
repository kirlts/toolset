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
import datetime
import math
import textwrap
import os
import re
import sqlite3
import subprocess
import unicodedata
from dataclasses import dataclass, field
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

# --- parseo ------------------------------------------------------------------

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n?", re.S)
WIKILINK = re.compile(r"\[\[([^\[\]|#]+?)(?:#[^\[\]|]*)?(?:\|[^\[\]]*)?\]\]")
PALABRA = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,}")
OPERADORES = re.compile(r'["*:()]|\b(AND|OR|NOT|NEAR)\b')
# Marcadores de intencion enumerativa: la respuesta es un indice, no un nodo suelto.
LISTADO = re.compile(r"\b(lista|listar|listado|cuales|cuáles|todos|todas|enumera|"
                     r"que proyectos|qué proyectos|que hay|qué hay|inventario)\b")

CAMPOS_GRAFO = ("depende_de", "se_descompone_en", "se_relaciona_con")
NO_POLO = {"assets", ".obsidian", ".trash"}


def normalizar(palabra: str) -> str:
    desc = unicodedata.normalize("NFD", palabra.lower())
    return "".join(c for c in desc if unicodedata.category(c) != "Mn")


def raiz(palabra: str) -> str:
    base = normalizar(palabra)
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

        return cls(
            slug=cfg.get("slug") or ruta.name,
            nombre=cfg.get("nombre") or ruta.name,
            descripcion=cfg.get("descripcion") or "",
            polos=polos,
            alias=alias,
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
        terminos = PALABRA.findall(consulta)
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
        db.commit()

    def _semantica(self) -> None:
        """Vectoriza cada entrada completa (no fragmentos: con embeddings estaticos
        los trozos cortos son mas ruidosos que el promedio del documento)."""
        self.vectores = None
        self.orden: list[str] = []
        if self.modelo is None:
            return
        self.orden = list(self.nodos)
        textos = [self.nodos[n].cuerpo[:2000] for n in self.orden]
        V = self.modelo.encode(textos).astype("float32")
        self.vectores = V / np.clip(np.linalg.norm(V, axis=1, keepdims=True), 1e-9, None)

    def semejantes(self, consulta: str, tope: int = 12) -> list[str]:
        if self.modelo is None or self.vectores is None:
            return []
        v = self.modelo.encode([consulta]).astype("float32")[0]
        v = v / max(float(np.linalg.norm(v)), 1e-9)
        return [self.orden[i] for i in np.argsort(-(self.vectores @ v))[:tope]]

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
        if n.modificado:
            fecha = datetime.date.fromtimestamp(n.modificado).isoformat()
            return f"{n.nombre} · {etiqueta} · actualizada {fecha}"
        return f"{n.nombre} · {etiqueta}"

    def recientes(self, polo: str | None = None, tope: int = 12) -> list[str]:
        """Entradas ordenadas por ultima modificacion (git), de nueva a vieja. Se
        excluyen los indices/hubs (muchos backlinks): se tocan en casi todos los
        commits, asi que su fecha no informa sobre novedad de contenido."""
        candidatos = [n for n in self.nodos.values()
                      if (not polo or n.polo == polo) and n.modificado
                      and len(self.relacionados(n.nombre)) <= 25]
        candidatos.sort(key=lambda n: -n.modificado)
        return [n.nombre for n in candidatos[:tope]]

    def extracto(self, nombre: str, consulta_fts: str) -> str:
        """Pasaje alrededor de la coincidencia; si el acierto vino de la capa
        semantica no hay coincidencia literal, asi que se muestra la apertura."""
        # (El extracto de un indice NO se fuerza al Inventario: empeoraba las preguntas
        #  definicionales —"¿qué es Kairós?" devolvia la tabla de hijos en vez de la
        #  definicion. El Inventario se ofrece en panorama(), que es la via explicita.)
        try:
            fila = self.db.execute(
                "SELECT snippet(docs, 1, '', '', ' … ', 52) FROM docs "
                "WHERE docs MATCH ? AND nombre = ? LIMIT 1",
                (consulta_fts, nombre),
            ).fetchone()
            if fila and fila[0]:
                return fila[0].strip()
        except sqlite3.OperationalError:
            pass
        cuerpo = " ".join(self.nodos[nombre].cuerpo.split())
        return (cuerpo[:440] + " …") if len(cuerpo) > 440 else cuerpo


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


def crear_servidor(idx: Indice) -> FastMCP:
    """Un servidor MCP por KB. Las tres herramientas se cierran sobre su indice."""
    cfg = idx.cfg
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

    @mcp.tool()
    @con_dominio(dominio)
    def consultar(pregunta: str, ambito: str | None = None,
                  orden: str = "relevancia", limite: int = 6) -> str:
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
        """
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
            lexico = [f[0] for f in idx.db.execute(
                f"SELECT nombre FROM docs WHERE docs MATCH ? {' '.join(filtros)} "
                f"ORDER BY rank LIMIT {tope_lex}", args).fetchall()]
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

        # Fusion reciproca ponderada: el nombre manda, la semantica entiende la
        # intencion, la lexica corrige cuando importa la palabra exacta.
        puntaje: dict[str, float] = {}
        for ranking, peso in ((por_nombre[:5], 1.6), (semantico, 1.0), (lexico, 0.6)):
            for pos, nom in enumerate(ranking):
                puntaje[nom] = puntaje.get(nom, 0.0) + peso / (10 + pos)

        # Difusion por el grafo curado: los vecinos de los mejores resultados reciben un
        # aporte. Es la ventaja de esta KB —wikilinks puestos a mano— aplicada al ranking:
        # preguntar "empresa del fundador" trae SAUCO porque es vecina de "Mercado del NFU",
        # aunque su texto no diga "fundador". Se excluyen los hubs (muchos vecinos) para no
        # arrastrar nodos-indice genericos, y el aporte es pequeño: reordena, no manda.
        cabeza = sorted(puntaje, key=lambda x: -puntaje[x])[:8]
        for nom in cabeza:
            vecinos = idx.relacionados(nom)
            if len(vecinos) > 25:  # hub: conecta con casi todo, su vecindad no informa
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
        if LISTADO.search(normalizar(pregunta)):
            for nom, sc in list(puntaje.items()):
                if idx.nodos[nom].es_indice:
                    puntaje[nom] = sc * 1.9

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
        ganadores = sorted(puntaje, key=lambda x: -puntaje[x])[:n]

        if not ganadores:
            return (f"Nada sobre «{pregunta}». Busqué por palabras y por significado. "
                    "Prueba otras palabras, o usa panorama() para ver qué cubre.")

        partes = [aviso + f"{len(ganadores)} entrada(s) sobre «{pregunta}»\n"]
        for nom in ganadores:
            partes.append(f"### {idx.fuente(idx.nodos[nom])}\n{idx.extracto(nom, args[0])}")
            if vecinos := idx.relacionados(nom)[:6]:
                partes.append(f"*Conecta con:* {', '.join(vecinos)}")
            partes.append("")
        partes.append("Usa leer(tema) para el texto completo de cualquiera de estas.")
        return "\n".join(partes)

    @mcp.tool()
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

    @mcp.tool()
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


# --- perfiles de decision ----------------------------------------------------
#
# Esto NO es una KB y a proposito no reusa nada de Indice. Un perfil es un solo
# Markdown que se lee por secciones: la recuperacion es determinista (dame la seccion
# de la direccion saliente, tipo "pedir_recurso", del destino "alan"), asi que un
# indice no aportaria nada y agregaria una capa que puede fallar. Fragmentar el perfil
# en nodos ademas complicaria lo unico que hay que hacer, que es devolver secciones
# enteras: habria que reensamblarlas despues de haberlas partido.
#
# Comparte con las KB el proceso, el transporte y las convenciones, no la naturaleza.
# Por eso se monta como recurso aparte en su propia ruta y NO como una cuarta
# herramienta de cada KB: una herramienta de encuadre colgando de "Trazambiental"
# heredaria su cabecera de dominio y el agente no sabria cuando usarla. Ademas deja la
# futura autorizacion por ruta (DT-011) con donde aplicarse, que es lo que pide UD-022.
#
# Los perfiles se releen en CADA llamada, no al arrancar: asi editar un perfil tiene
# efecto inmediato sin reiniciar el contenedor. Son archivos de decenas de KB, el costo
# es despreciable. Lo unico que se calcula al arrancar es la cabecera de dominio, asi
# que agregar un destino nuevo si pide reinicio para que la descripcion lo nombre.

SLUG_ENCUADRE = "encuadre"

H3 = re.compile(r"^###\s+(.+?)\s*$", re.M)
# Cabecera de una situacion saliente: "### saliente: pedir_recurso - Pedir recursos".
# El slug no lleva espacios ni guiones, asi que " - " separa sin ambiguedad.
CAB_TIPO = re.compile(r"saliente\s*:\s*([a-z0-9_]+)\s*-\s*(.+)", re.I)
# Primera linea en cursiva del cuerpo de un tipo ("*Cuando: ...*"): alimenta el catalogo.
CUANDO = re.compile(r"\s*\*([^*]+)\*\s*$", re.M)


@dataclass
class Perfil:
    slug: str
    nombre: str
    archivo: str
    meta: dict
    bloques: dict[str, str]   # titulo H2 normalizado -> texto ('destino', 'entrante', ...)
    tipos: dict[str, dict]    # slug de tipo -> {titulo, cuando, texto}, en orden del archivo

    def bloque(self, nombre: str) -> str:
        return self.bloques.get(nombre, "").strip()

    def cabecera(self) -> str:
        """Quien es el destino, con su procedencia. Va en toda respuesta: sin ella el
        material de una situacion se lee como una regla generica y deja de ser el
        perfil de alguien."""
        meta = []
        if actualizado := self.meta.get("actualizado"):
            meta.append(f"perfil actualizado {actualizado}")
        fuentes = self.meta.get("fuentes")
        if fuentes:
            lista = fuentes if isinstance(fuentes, list) else [fuentes]
            meta.append("fuentes: " + "; ".join(str(f) for f in lista))
        partes = [f"### Destino: {self.nombre}"]
        if meta:
            partes.append(f"*{' · '.join(meta)}*")
        if cuerpo := self.bloque("destino"):
            partes += ["", cuerpo]
        return "\n".join(partes)


def _secciones_h2(cuerpo: str) -> dict[str, str]:
    """{titulo normalizado: texto}. El preambulo (todo lo anterior al primer H2) se
    descarta: ahi viven el titulo del archivo y las notas para quien lo edita."""
    partes = SECCION.split(cuerpo)
    return {normalizar(partes[i]): partes[i + 1].strip()
            for i in range(1, len(partes) - 1, 2)}


def _partir_tipos(texto: str) -> tuple[str, dict[str, dict]]:
    """Separa el bloque saliente en (preambulo comun, tipos de situacion)."""
    partes = H3.split(texto)
    preambulo = partes[0].strip()
    tipos: dict[str, dict] = {}
    ultimo = None
    for i in range(1, len(partes) - 1, 2):
        cab, cuerpo = partes[i].strip(), partes[i + 1].strip()
        m = CAB_TIPO.fullmatch(cab)
        if not m:
            # Un H3 que no declara un tipo se conserva donde estaba en vez de
            # descartarse: un encabezado mal escrito no debe hacer desaparecer texto.
            suelto = f"### {cab}\n\n{cuerpo}"
            if ultimo:
                tipos[ultimo]["texto"] += "\n\n" + suelto
            else:
                preambulo = f"{preambulo}\n\n{suelto}".strip()
            continue
        ultimo = normalizar(m.group(1))
        # La linea de "cuando" se saca del cuerpo: se emite aparte, bajo el titulo de
        # la situacion, y si quedara tambien en el texto saldria dos veces.
        primera = CUANDO.match(cuerpo)
        tipos[ultimo] = {"titulo": m.group(2).strip(),
                         "cuando": primera.group(1).strip() if primera else "",
                         "texto": cuerpo[primera.end():].strip() if primera else cuerpo}
    return preambulo, tipos


def cargar_perfiles(directorio: Path) -> tuple[dict[str, Perfil], str]:
    """Lee el directorio de perfiles. Devuelve (perfiles por slug, calibracion comun).

    Un archivo es un perfil si su frontmatter declara `destino`. Un archivo cuyo nombre
    empieza con guion bajo y trae un bloque `## calibracion` aporta la calibracion comun
    a todos los destinos (`_calibracion.md`). Cualquier otro se ignora, y por eso el
    guion bajo es parte de la convencion y no decorativo: sin el, un README junto a los
    perfiles seria candidato a aportar calibracion segun que encabezados tuviera.
    """
    perfiles: dict[str, Perfil] = {}
    comun = ""
    for ruta in sorted(directorio.glob("*.md")):
        try:
            texto = ruta.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue  # un archivo ilegible no puede tumbar al resto
        meta: dict = {}
        cuerpo = texto
        if m := FRONTMATTER.match(texto):
            try:
                meta = yaml.safe_load(m.group(1)) or {}
            except yaml.YAMLError:
                meta = {}
            cuerpo = texto[m.end():]
        if not isinstance(meta, dict):
            meta = {}
        bloques = _secciones_h2(cuerpo)
        slug = normalizar(str(meta.get("destino") or ""))
        if not slug:
            if ruta.name.startswith("_"):
                comun = comun or bloques.get("calibracion", "").strip()
            continue
        preambulo, tipos = _partir_tipos(bloques.get("saliente", ""))
        bloques["saliente"] = preambulo
        perfiles[slug] = Perfil(slug=slug, nombre=str(meta.get("nombre") or ruta.stem),
                                archivo=ruta.name, meta=meta, bloques=bloques, tipos=tipos)
    return perfiles, comun


def _catalogo_destinos(perfiles: dict[str, Perfil], motivo: str) -> str:
    lineas = [motivo, "", f"Destinos disponibles ({len(perfiles)}):"]
    for p in perfiles.values():
        lineas.append(f'  - `{p.slug}`: {p.nombre}')
    lineas.append("")
    lineas.append('Vuelve a llamar indicando destino, por ejemplo destino="'
                  + next(iter(perfiles)) + '".')
    return "\n".join(lineas)


def _catalogo_tipos(perfil: Perfil, motivo: str, situacion: str = "") -> str:
    """Ante un tipo ausente o irreconocible NO se adivina: se devuelve el catalogo.

    Se probo deducirlo de las palabras de la situacion y se descarto: sin un corpus
    que pese los terminos, las palabras vacias mandan y el resultado era erratico
    ("quiero que pague una cuenta de IA" deducia `trabajo_invisible` por compartir
    "quiere" con su descripcion, en vez de `pedir_recurso`). Entregar los criterios de
    aceptacion de la situacion equivocada es peor que pedir una llamada mas, porque el
    modelo los aplicaria creyendo que son los correctos.
    """
    lineas = [motivo]
    if situacion.strip():
        lineas.append(f"\nLo que quieres plantear: «{situacion.strip()}»")
    lineas += ["", f"Tipos de situación saliente para {perfil.nombre}:"]
    for slug, t in perfil.tipos.items():
        detalle = f" ({t['cuando']})" if t["cuando"] else ""
        lineas.append(f"  - `{slug}`: {t['titulo']}{detalle}")
    lineas += ["", 'Vuelve a llamar con el tipo que corresponda, por ejemplo tipo="'
               + next(iter(perfil.tipos)) + '".',
               'Si lo que necesitas es entender algo que este destino dijo o hizo, en '
               'cambio, llama con direccion="entrante" y sin tipo.']
    return "\n".join(lineas)


def crear_servidor_encuadre(directorio: Path) -> FastMCP | None:
    """Un recurso MCP sobre un directorio de perfiles. None si no hay ninguno."""
    perfiles, _ = cargar_perfiles(directorio)
    if not perfiles:
        return None

    quienes = ", ".join(p.nombre for p in perfiles.values())
    # Misma forma que la cabecera de las KB (guia de Anthropic para descripciones de
    # herramientas): que hace, cuando usarla, cuando NO, y que no devuelve. Aca importa
    # sobre todo lo ultimo, porque la confusion previsible es creer que redacta el texto.
    dominio = (
        f"Perfiles de decisión de {len(perfiles)} persona(s) del entorno de trabajo de "
        f"OKOS: {quienes}. No es una base de conocimiento consultable: cada perfil dice "
        "cómo decide esa persona, qué necesita ver para aceptar algo y qué hunde un "
        "mensaje, con sus afirmaciones marcadas como verificadas, hipótesis o contexto "
        "no verificable. Úsalo antes de escribirle a alguien del equipo, o para "
        "interpretar algo que esa persona dijo o hizo. No contiene documentación técnica "
        "del producto ni conocimiento general, y no redacta nada: devuelve el material "
        "del perfil y la regla de decisión, y el texto lo escribes tú."
    )

    mcp = FastMCP(SLUG_ENCUADRE, instructions=(
        f"{dominio}\n\n"
        "Una sola herramienta, `encuadrar`, que funciona en dos direcciones: "
        "'entrante' para interpretar algo que el destino dijo o hizo, y 'saliente' para "
        "encuadrar algo que se le quiere pedir, proponer o reportar. Es un bibliotecario, "
        "no un autor: entrega la materia prima y los criterios, y el trabajo de evaluar "
        "el caso concreto contra esos criterios es tuyo. Una de sus salidas válidas, y a "
        "menudo la más valiosa, es concluir que todavía no conviene mandar el mensaje y "
        "decir qué falta para que cumpla. Es de solo lectura: no modifica ningún perfil."
    ))

    @mcp.tool()
    @con_dominio(dominio)
    def encuadrar(situacion: str, destino: str | None = None,
                  direccion: str = "saliente", tipo: str | None = None) -> str:
        """Devuelve el material del perfil de una persona que aplica a una situación.

        Úsala en dos casos. Uno, antes de escribirle algo a alguien del equipo: te
        devuelve qué necesita ver esa persona para aceptarlo, qué lo hunde, ejemplos
        reales del proyecto y la regla de decisión que hay que aplicar antes de redactar
        (dirección 'saliente'). Dos, cuando esa persona dijo o hizo algo y quieres saber
        qué significa en su marco (dirección 'entrante'). No la uses para preguntas sobre
        el producto, el código o el negocio: solo modela cómo decide gente concreta.

        Devuelve texto del perfil, en bloques: quién es el destino y qué optimiza; el
        material de la dirección y la situación pedidas; y la regla de calibración, que
        va siempre. Cada afirmación viene marcada como VERIFICADO (comprobado con un
        comando reproducible), HIPOTESIS (lectura interpretativa) o CONTEXTO (no
        verificable), y esa marca hay que conservarla al usarla.

        Lo que NO hace, y es lo importante: no redacta el mensaje, no evalúa tu caso y
        no decide por ti. Devuelve la materia prima y los criterios; contrastar tu
        insumo concreto contra ellos es trabajo tuyo, y si no los cumple, la respuesta
        correcta no es un texto mejor escrito sino decir que todavía no conviene
        mandarlo y qué falta. Tampoco adivina: si no le indicas el destino o el tipo de
        situación y hay más de una opción posible, devuelve el catálogo para que
        vuelvas a llamar, en vez de elegir por ti.

        Parámetros:
          situacion: en texto libre, qué quieres decir o qué quieres entender. El
                     servidor no la interpreta ni la usa para elegir por ti: la
                     devuelve citada cuando te pide que elijas el tipo, para que no
                     pierdas el hilo. Su valor está en obligarte a formular el caso
                     antes de recibir los criterios con que se juzga.
          destino: a quién va dirigido, por su slug (por ejemplo "alan"). Si lo omites
                   y hay más de un perfil, devuelve la lista de destinos.
          direccion: 'saliente' (por defecto) para algo que quieres decir, 'entrante'
                     para algo que el destino dijo o hizo y quieres interpretar.
          tipo: la categoría de situación saliente (por ejemplo "pedir_recurso",
                "mala_noticia"). Solo aplica a la dirección saliente. Si lo omites,
                devuelve el catálogo de tipos de ese destino, cada uno con una línea
                que dice cuándo aplica, para que vuelvas a llamar con el correcto.
        """
        try:
            perfiles, comun = cargar_perfiles(directorio)
        except OSError as e:
            return (f"No pude leer los perfiles en {directorio} ({e}). Es un problema de "
                    "la instalación del servidor, no de tu llamada.")
        if not perfiles:
            return (f"No hay ningún perfil en {directorio}. Un perfil es un archivo .md "
                    "cuyo frontmatter declara `destino`.")

        avisos: list[str] = []

        clave = normalizar(destino or "")
        if clave:
            elegido = perfiles.get(clave)
            if elegido is None:
                # Coincidencia parcial por slug o por nombre, y solo si es inequivoca.
                cerca = [p for p in perfiles.values()
                         if clave in p.slug or clave in normalizar(p.nombre)]
                if len(cerca) != 1:
                    return _catalogo_destinos(perfiles, f"No reconocí el destino «{destino}».")
                elegido = cerca[0]
        elif len(perfiles) == 1:
            elegido = next(iter(perfiles.values()))
            avisos.append(f"(No indicaste destino; hay uno solo, «{elegido.nombre}».)")
        else:
            return _catalogo_destinos(perfiles, "No indicaste destino y hay más de uno.")

        d = normalizar(direccion or "")
        entrante = d.startswith("entr")
        if not entrante and not d.startswith("sal"):
            # Degradar y avisar, como hace `consultar` con un ambito desconocido.
            avisos.append(f"(No reconocí la dirección «{direccion}»; asumí 'saliente'. "
                          "Las dos posibles son 'saliente' y 'entrante'.)")

        # Primero se resuelve el contenido y se juntan los avisos; el ensamblado va
        # despues, entero. Mezclar las dos cosas hacia que un aviso decidido tarde
        # (el del tipo deducido) quedara fuera de una salida ya empezada.
        cuerpo: list[str] = []
        if entrante:
            material = elegido.bloque("entrante")
            if not material:
                return (f"El perfil de {elegido.nombre} no tiene material de dirección "
                        "entrante, así que no hay base para interpretar lo que hizo. "
                        "Decirlo es la respuesta correcta: no lo deduzcas del material "
                        "saliente, que describe otra cosa.")
            if tipo:
                avisos.append("(Ignoré el tipo: la dirección entrante no tiene tipos.)")
            cuerpo = ["### Dirección entrante: cómo leer lo que hace este destino", "",
                      material, ""]
            pie = ('*Usa encuadrar(direccion="saliente", tipo=…) si en vez de entender '
                   'necesitas decirle algo a este destino.*')
        else:
            if not elegido.tipos:
                return (f"El perfil de {elegido.nombre} no describe ninguna situación "
                        "saliente todavía.")
            clave_tipo = normalizar(tipo or "")
            if clave_tipo and clave_tipo not in elegido.tipos:
                cerca = [k for k, t in elegido.tipos.items()
                         if clave_tipo in k or clave_tipo in normalizar(t["titulo"])]
                if len(cerca) != 1:
                    return _catalogo_tipos(
                        elegido, f"No reconocí el tipo «{tipo}» para {elegido.nombre}.",
                        situacion)
                clave_tipo = cerca[0]
            if not clave_tipo:
                return _catalogo_tipos(
                    elegido, "No indicaste el tipo de situación y no lo doy por "
                             "adivinado, porque aplicar los criterios de la situación "
                             "equivocada es peor que preguntar.", situacion)

            elegida = elegido.tipos[clave_tipo]
            cuerpo = [f"### Situación: {elegida['titulo']} (dirección saliente)"]
            if elegida["cuando"]:
                cuerpo.append(f"*{elegida['cuando']}*")
            cuerpo.append("")
            if preambulo := elegido.bloque("saliente"):
                cuerpo += [preambulo, ""]
            cuerpo += [elegida["texto"], ""]
            pie = ('*Usa encuadrar(direccion="entrante") si en vez de decir algo '
                   'necesitas entender algo que este destino dijo o hizo.*')

        partes = list(avisos) + ([""] if avisos else [])
        partes += [elegido.cabecera(), ""] + cuerpo
        if calibracion := (elegido.bloque("calibracion") or comun):
            partes += ["### Calibración (no negociable)", "", calibracion, ""]
        else:
            partes.append("*(No encontré ningún bloque de calibración en la instalación: "
                          "el material de arriba va sin su regla de calibración, tenlo "
                          "presente al usarlo.)*\n")
        partes.append(pie)
        return "\n".join(partes)

    return mcp


# --- arranque ----------------------------------------------------------------

def cargar_modelo():
    if StaticModel is None:
        return None
    try:
        if Path(MODELO).is_dir():
            # Ya viene cuantizado (int8/128). Re-cuantizarlo lo expandiria a float32.
            return StaticModel.from_pretrained(MODELO)
        return StaticModel.from_pretrained(MODELO, quantize_to="int8", dimensionality=128)
    except Exception:
        return None


def descubrir(raiz: Path) -> list[Path]:
    """Cada subdirectorio con knowledge-base/ es una KB."""
    return sorted(d for d in raiz.iterdir() if (d / "knowledge-base").is_dir())


def main() -> None:
    p = argparse.ArgumentParser(description="Servidor MCP de solo lectura para KBs de kb-template")
    p.add_argument("--kb", action="append", default=[], help="Raiz de una KB (repetible)")
    p.add_argument("--kbs", help="Directorio que contiene varias KB")
    p.add_argument("--perfiles", help="Directorio de perfiles de decision (un .md por destino)")
    p.add_argument("--transport", default="stdio", choices=["stdio", "streamable-http"])
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    a = p.parse_args()

    rutas = [Path(k) for k in a.kb]
    if a.kbs:
        rutas += descubrir(Path(a.kbs))
    if not rutas and not a.perfiles:
        p.error("indica --kb RUTA, --kbs DIRECTORIO o --perfiles DIRECTORIO")

    modelo = cargar_modelo() if rutas else None  # una vez, compartido por todas las KB
    indices = [Indice(r, modelo) for r in rutas]
    for i in indices:
        print(f"[kb-mcp] {i.cfg.slug}: {len(i.nodos)} entradas, "
              f"polos={list(i.cfg.polos)}, semantica={'sí' if i.vectores is not None else 'no'}",
              flush=True)

    # El recurso de perfiles es opcional y NO tumba el arranque si falta: el CMD del
    # contenedor pasa --perfiles siempre, y el directorio puede no estar montado todavia.
    encuadre = None
    if a.perfiles:
        dir_perfiles = Path(a.perfiles).expanduser()
        if not dir_perfiles.is_dir():
            print(f"[kb-mcp] {SLUG_ENCUADRE}: no existe {dir_perfiles}, no se monta",
                  flush=True)
        elif (encuadre := crear_servidor_encuadre(dir_perfiles)) is None:
            print(f"[kb-mcp] {SLUG_ENCUADRE}: sin perfiles en {dir_perfiles}, no se monta",
                  flush=True)
        else:
            destinos, _ = cargar_perfiles(dir_perfiles)
            print(f"[kb-mcp] {SLUG_ENCUADRE}: {len(destinos)} destino(s), "
                  f"{', '.join(destinos)}", flush=True)

    if a.transport == "stdio":
        if len(indices) + (1 if encuadre else 0) > 1:
            p.error("stdio sirve un solo recurso; usa --kb una vez, o solo --perfiles")
        (encuadre or crear_servidor(indices[0])).run(transport="stdio")
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
    # Cada recurso es un slug: las KB y, si esta montado, el de perfiles de decision.
    recursos = [(idx.cfg.slug, crear_servidor(idx)) for idx in indices]
    if encuadre:
        recursos.append((SLUG_ENCUADRE, encuadre))

    servidores, rutas_http = [], []
    for slug, mcp in recursos:
        mcp.settings.stateless_http = True  # el RC 2026-07-28 elimina las sesiones
        if seguridad:
            mcp.settings.transport_security = seguridad
        app = mcp.streamable_http_app()      # crea el session_manager
        servidores.append(mcp)
        rutas_http.append(Mount(f"/{slug}", app=app))

    async def salud(_):
        estado = {"kbs": [{"slug": i.cfg.slug, "entradas": len(i.nodos),
                           "semantica": i.vectores is not None} for i in indices]}
        if encuadre:
            destinos, _c = cargar_perfiles(Path(a.perfiles).expanduser())
            estado["perfiles"] = {"slug": SLUG_ENCUADRE, "destinos": sorted(destinos)}
        return JSONResponse(estado)

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
