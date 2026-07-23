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
import contextlib
import datetime
import math
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

def crear_servidor(idx: Indice) -> FastMCP:
    """Un servidor MCP por KB. Las tres herramientas se cierran sobre su indice."""
    cfg = idx.cfg
    mcp = FastMCP(cfg.slug)
    ambitos = " · ".join(f"'{a}' = {cfg.polos[d]}" for a, d in sorted(cfg.alias.items())
                         if a != normalizar(d)) or "sin ámbitos"

    @mcp.tool()
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
    def panorama(tema: str | None = None) -> str:
        """Da una vista de conjunto: el inventario de la base, o el mapa de un tema.

        Úsala para orientarte antes de preguntar, o cuando la intención del usuario es
        panorámica y no puntual: «¿qué hay acá?», «¿de qué trata esto?», «¿qué se
        conecta con X?». Para responder una pregunta concreta, usa `consultar`.

        Sin argumentos: devuelve cuántas entradas hay, cómo se reparten por área, y las
        entradas más conectadas de cada una (los nodos centrales de la base). Con un
        tema: devuelve las entradas vecinas a ese tema en el grafo, cada una con una
        línea de resumen — la forma rápida de entender un área sin leerla completa.

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
    for idx in indices:
        mcp = crear_servidor(idx)
        mcp.settings.stateless_http = True  # el RC 2026-07-28 elimina las sesiones
        if seguridad:
            mcp.settings.transport_security = seguridad
        app = mcp.streamable_http_app()      # crea el session_manager
        servidores.append(mcp)
        rutas_http.append(Mount(f"/{idx.cfg.slug}", app=app))

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
