#!/usr/bin/env python3
"""
Servidor MCP de solo lectura para una KB construida con kb-template.

La superficie es la de un bibliotecario: se le pregunta, se le pide leer algo, o se
le pide el panorama. La topologia interna (polos, wikilinks, frontmatter) se usa para
responder mejor, pero no se le pide al que consulta que la conozca.

    python server.py --kb ~/traza-ambiental                    # stdio (Claude Code)
    python server.py --kb ~/traza-ambiental --transport http   # para el VPS
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
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

# Embeddings estaticos: tabla de consulta token->vector, sin torch ni GPU.
# int8 + 128 dims deja la tabla en ~64 MB y no degrada el ranking a esta escala.
MODELO = os.environ.get("KB_MODELO", "minishlab/potion-multilingual-128M")

# --- parseo ------------------------------------------------------------------

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n?", re.S)
WIKILINK = re.compile(r"\[\[([^\[\]|#]+?)(?:#[^\[\]|]*)?(?:\|[^\[\]]*)?\]\]")
PALABRA = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,}")
OPERADORES = re.compile(r'["*:()]|\b(AND|OR|NOT|NEAR)\b')

CAMPOS_GRAFO = ("depende_de", "se_descompone_en", "se_relaciona_con")

# Vocabulario interno -> palabras del mundo real.
AMBITOS = {
    "contexto": "Contexto",
    "producto": "Trazambiental",
}


def normalizar(palabra: str) -> str:
    """Minuscula y sin diacriticos, igual que el tokenizer del indice."""
    desc = unicodedata.normalize("NFD", palabra.lower())
    return "".join(c for c in desc if unicodedata.category(c) != "Mn")


def raiz(palabra: str) -> str:
    """Raiz Snowball espanola sobre la forma normalizada."""
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


@dataclass
class Nodo:
    nombre: str
    ruta: str
    polo: str
    cuerpo: str
    meta: dict
    enlaces: dict[str, list[str]] = field(default_factory=dict)
    menciona: list[str] = field(default_factory=list)


class Indice:
    def __init__(self, raiz_repo: Path):
        self.raiz = raiz_repo.expanduser().resolve()
        self.base = self.raiz / "knowledge-base"
        if not self.base.is_dir():
            raise SystemExit(f"No existe {self.base} — ¿es una KB de kb-template?")
        self.nodos: dict[str, Nodo] = {}
        self.backlinks: dict[str, set[str]] = {}
        self.vocabulario: dict[str, set[str]] = {}
        self.formas: set[str] = set()
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.construir()

    def construir(self) -> None:
        self.nodos.clear()
        self.backlinks.clear()
        self.vocabulario.clear()
        self.formas.clear()

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
            nodo = Nodo(
                nombre=ruta.stem,
                ruta=str(rel),
                polo=rel.parts[0] if len(rel.parts) > 1 else "(raiz)",
                cuerpo=cuerpo,
                meta=meta if isinstance(meta, dict) else {},
                enlaces={c: _wikilinks(meta.get(c)) for c in CAMPOS_GRAFO},
                menciona=sorted({n.strip() for n in WIKILINK.findall(cuerpo)}),
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

    def _semantica(self) -> None:
        """Vectoriza cada entrada completa. Es lo que permite encontrar por sentido:
        'castigos por no cumplir' llega a Sanciones y Multas sin compartir palabras.

        Se embebe el documento entero y no fragmentos: con embeddings estaticos los
        trozos cortos resultan mas ruidosos que el promedio del documento completo
        (verificado sobre este corpus).
        """
        self.modelo = None
        self.vectores = None
        self.orden: list[str] = []
        if StaticModel is None:
            return
        try:
            if Path(MODELO).is_dir():
                # Modelo ya horneado en int8/128 por el Dockerfile: cargarlo tal cual.
                # Re-cuantizarlo lo expandiria a float32 primero (~500 MB de pico).
                self.modelo = StaticModel.from_pretrained(MODELO)
            else:
                self.modelo = StaticModel.from_pretrained(
                    MODELO, quantize_to="int8", dimensionality=128
                )
        except Exception:
            self.modelo = None
            return
        self.orden = list(self.nodos)
        # Solo el cuerpo: anteponer el titulo desplazaba el vector hacia el nombre
        # y empeoraba el ranking (verificado sobre este corpus).
        textos = [self.nodos[n].cuerpo[:2000] for n in self.orden]
        V = self.modelo.encode(textos).astype("float32")
        normas = np.linalg.norm(V, axis=1, keepdims=True)
        self.vectores = V / np.clip(normas, 1e-9, None)

    def semejantes(self, consulta: str, tope: int = 25) -> list[str]:
        """Entradas mas cercanas por significado, de mayor a menor."""
        if self.modelo is None or self.vectores is None:
            return []
        v = self.modelo.encode([consulta]).astype("float32")[0]
        v = v / max(float(np.linalg.norm(v)), 1e-9)
        puntajes = self.vectores @ v
        return [self.orden[i] for i in np.argsort(-puntajes)[:tope]]

    # -- morfologia espanola ---------------------------------------------------

    def _vocabulario(self) -> None:
        """Agrupa cada palabra del corpus por su raiz, y mide en cuantas entradas
        aparece cada raiz. Esa frecuencia documental es la que decide que terminos
        no discriminan — sin listas de palabras vacias escritas a mano."""
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
        """Consulta natural -> consulta FTS5 morfologicamente laxa.

        Cada termino se reemplaza por todas las formas del corpus que comparten su
        raiz: "residuo" -> ("residuo" OR "residuos" OR "residuales"). El indice sigue
        siendo el texto original, asi que los extractos se leen tal como estan escritos.
        Si el usuario usa sintaxis FTS5 explicita, la consulta se respeta sin tocar.
        """
        if OPERADORES.search(consulta):
            return consulta

        terminos = PALABRA.findall(consulta)
        # Un termino presente en mas de la mitad de las entradas no separa nada.
        # Se descarta salvo que sea lo unico que se pregunto.
        utiles = [t for t in terminos if self.frecuencia.get(raiz(t), 0.0) <= 0.5]
        if not utiles:
            utiles = terminos

        grupos = []
        for termino in utiles:
            base = normalizar(termino)
            formas = self.vocabulario.get(raiz(termino), set()) | {base}
            if base not in self.formas and len(formas) == 1:
                grupos.append(f'"{base}"*')
                continue
            grupos.append("(" + " OR ".join(f'"{f}"' for f in sorted(formas)) + ")")

        # Se unen con OR y se deja que BM25 pondere: los terminos raros pesan mas que
        # los comunes por su IDF. Con AND, una pregunta larga solo sobrevivia en los
        # textos legales extensos, que contienen todas las palabras y no responden nada.
        return " OR ".join(grupos) if grupos else consulta

    # -- indice ----------------------------------------------------------------

    def _fts(self) -> None:
        db = self.db
        db.executescript("DROP TABLE IF EXISTS docs;")
        # Sin 'porter': ese stemmer es solo ingles. La morfologia espanola se
        # resuelve expandiendo la consulta (ver expandir), no ensuciando el indice.
        db.execute(
            "CREATE VIRTUAL TABLE docs USING fts5("
            "  nombre, cuerpo, polo UNINDEXED,"
            "  tokenize='unicode61 remove_diacritics 2'"
            ")"
        )
        db.executemany(
            "INSERT INTO docs (nombre, cuerpo, polo) VALUES (?,?,?)",
            [(n.nombre, n.cuerpo, n.polo) for n in self.nodos.values()],
        )
        db.commit()

    # -- ayudas ----------------------------------------------------------------

    def resolver(self, tema: str) -> list[str]:
        """Nombres de entrada que mejor coinciden con lo pedido, de exacto a laxo."""
        if tema in self.nodos:
            return [tema]
        objetivo = normalizar(tema)
        exactos = [n for n in self.nodos if normalizar(n) == objetivo]
        if exactos:
            return exactos
        contiene = [n for n in self.nodos if objetivo in normalizar(n)]
        if contiene:
            return sorted(contiene, key=len)
        # Ultimo recurso: coincidencia por raices compartidas.
        pedido = {raiz(p) for p in PALABRA.findall(tema)}
        if not pedido:
            return []
        puntuados = []
        for n in self.nodos:
            comunes = pedido & {raiz(p) for p in PALABRA.findall(n)}
            if comunes:
                puntuados.append((len(comunes), -len(n), n))
        return [n for _, _, n in sorted(puntuados, reverse=True)]

    def relacionados(self, nombre: str) -> list[str]:
        """Vecindario inmediato en el grafo, sin distinguir la clase de enlace."""
        nodo = self.nodos.get(nombre)
        if not nodo:
            return []
        vecinos = {d for ds in nodo.enlaces.values() for d in ds}
        vecinos |= self.backlinks.get(nombre, set())
        vecinos |= set(nodo.menciona)
        return sorted(v for v in vecinos if v in self.nodos and v != nombre)


# --- servidor ----------------------------------------------------------------

mcp = FastMCP("kb")
IDX: Indice


def _fuente(n: Nodo) -> str:
    mundo = "el contexto" if n.polo == "Contexto" else "lo que construimos"
    return f"{n.nombre} · {mundo}"


def _extracto(nombre: str, consulta_fts: str) -> str:
    """Pasaje alrededor de la coincidencia; si el acierto vino de la capa semantica
    no hay coincidencia literal que resaltar, asi que se muestra la apertura."""
    try:
        fila = IDX.db.execute(
            "SELECT snippet(docs, 1, '', '', ' … ', 34) FROM docs "
            "WHERE docs MATCH ? AND nombre = ? LIMIT 1",
            (consulta_fts, nombre),
        ).fetchone()
        if fila and fila[0]:
            return fila[0].strip()
    except sqlite3.OperationalError:
        pass
    cuerpo = " ".join(IDX.nodos[nombre].cuerpo.split())
    return (cuerpo[:280] + " …") if len(cuerpo) > 280 else cuerpo


@mcp.tool()
def consultar(pregunta: str, ambito: str | None = None, limite: int = 6) -> str:
    """Pregunta cualquier cosa a la base de conocimiento de Trazambiental.

    Devuelve los pasajes relevantes con su fuente, y las entradas conectadas a cada
    uno, para que puedas profundizar sin buscar de nuevo. Escribe en lenguaje natural:
    singular, plural, genero y tildes dan igual ("residuo" encuentra "residuos",
    "gestion" encuentra "Gestión"). Para una frase literal, usa comillas.

    ambito (opcional): 'contexto' para la ley, el mercado y los actores;
                       'producto' para lo que estamos construyendo.
    """
    polo = None
    if ambito:
        polo = AMBITOS.get(normalizar(ambito))
        if not polo:
            return "El ámbito debe ser 'contexto' o 'producto'. Omítelo para buscar en todo."

    n = max(1, min(limite, 20))

    # Capa lexica: BM25 sobre el texto original, con la consulta expandida por raiz.
    filtros, args = [], [IDX.expandir(pregunta)]
    if polo:
        filtros.append("AND polo = ?")
        args.append(polo)
    try:
        lexico = [
            f[0] for f in IDX.db.execute(
                "SELECT nombre FROM docs WHERE docs MATCH ? "
                f"{' '.join(filtros)} ORDER BY rank LIMIT 12",
                args,
            ).fetchall()
        ]
    except sqlite3.OperationalError as e:
        return f"No pude interpretar esa consulta ({e}). Prueba con palabras sueltas."

    # Capa semantica: cercania por significado, aunque no compartan vocabulario.
    semantico = [
        s for s in IDX.semejantes(pregunta, tope=12)
        if not polo or IDX.nodos[s].polo == polo
    ]

    # Tercera senal: el nombre de la entrada. Si preguntan por «Ley 20.920», esa
    # entrada debe salir aunque su texto no sea el que mas se parece a la consulta.
    objetivo = normalizar(pregunta)
    por_nombre = [
        nombre for nombre in IDX.nodos
        if (not polo or IDX.nodos[nombre].polo == polo)
        and (objetivo in normalizar(nombre) or normalizar(nombre) in objetivo)
    ]
    por_nombre.sort(key=len)

    # Fusion reciproca ponderada. El nombre manda, la semantica entiende la intencion
    # de una pregunta, y la lexica corrige cuando importa la palabra exacta. Con pesos
    # iguales las leyes largas ahogaban al resto.
    puntaje: dict[str, float] = {}
    for ranking, peso in ((por_nombre[:5], 1.6), (semantico, 1.0), (lexico, 0.6)):
        for pos, nombre in enumerate(ranking):
            puntaje[nombre] = puntaje.get(nombre, 0.0) + peso / (10 + pos)
    ganadores = sorted(puntaje, key=lambda x: -puntaje[x])[:n]

    if not ganadores:
        return (
            f"Nada sobre «{pregunta}»"
            + (f" en el ámbito '{ambito}'." if ambito else ".")
            + "\nBusqué por palabras y por significado. Prueba con otras palabras,"
              " o usa panorama() para ver qué cubre la base."
        )

    partes = [f"{len(ganadores)} entrada(s) sobre «{pregunta}»\n"]
    for nombre in ganadores:
        nodo = IDX.nodos[nombre]
        extracto = _extracto(nombre, args[0])
        partes.append(f"### {_fuente(nodo)}\n{extracto}")
        if vecinos := IDX.relacionados(nombre)[:6]:
            partes.append(f"*Conecta con:* {', '.join(vecinos)}")
        partes.append("")
    partes.append("Usa leer(tema) para el texto completo de cualquiera de estas entradas.")
    return "\n".join(partes)


@mcp.tool()
def leer(tema: str) -> str:
    """Trae el texto completo de una entrada, tal como está escrito.

    Acepta el nombre aproximado: si hay varias candidatas, las lista. Al final
    incluye las entradas conectadas, para seguir tirando del hilo.
    """
    candidatos = IDX.resolver(tema)
    if not candidatos:
        return (
            f"No encontré una entrada llamada «{tema}».\n"
            "Prueba con consultar() para buscarlo por contenido."
        )
    if len(candidatos) > 1 and normalizar(candidatos[0]) != normalizar(tema):
        listado = "\n".join(f"  - {c}" for c in candidatos[:10])
        return f"Hay varias entradas que podrían ser «{tema}»:\n{listado}\n\nPide una por su nombre."

    nodo = IDX.nodos[candidatos[0]]
    salida = [f"# {nodo.nombre}", f"*{_fuente(nodo)}*", "", nodo.cuerpo.strip()]
    if vecinos := IDX.relacionados(nodo.nombre):
        salida += ["", "---", "**Conecta con:** " + ", ".join(vecinos)]
    return "\n".join(salida)


@mcp.tool()
def panorama(tema: str | None = None) -> str:
    """Muestra qué contiene la base, o el mapa alrededor de un tema.

    Sin argumentos: el inventario general. Con un tema: las entradas conectadas a él,
    que es la forma rápida de entender un área sin leerla entera.
    """
    if tema:
        candidatos = IDX.resolver(tema)
        if not candidatos:
            return f"No encontré «{tema}». Prueba con consultar() para buscarlo por contenido."
        nodo = IDX.nodos[candidatos[0]]
        vecinos = IDX.relacionados(nodo.nombre)
        if not vecinos:
            return f"«{nodo.nombre}» no está conectada a otras entradas todavía."
        lineas = [f"Mapa alrededor de **{nodo.nombre}** ({len(vecinos)} entradas conectadas)\n"]
        for v in vecinos:
            resumen = " ".join(IDX.nodos[v].cuerpo.split())[:110]
            lineas.append(f"- **{v}** — {resumen}…")
        return "\n".join(lineas)

    por_polo: dict[str, int] = {}
    for n in IDX.nodos.values():
        por_polo[n.polo] = por_polo.get(n.polo, 0) + 1
    return (
        f"La base tiene **{len(IDX.nodos)} entradas** sobre trazabilidad de residuos en Chile.\n\n"
        f"- **El contexto** ({por_polo.get('Contexto', 0)}): la Ley REP y sus decretos, los "
        "actores del mercado, el ecosistema de neumáticos fuera de uso. Lo que *es*.\n"
        f"- **Lo que construimos** ({por_polo.get('Trazambiental', 0)}): decisiones de producto, "
        "reglas de negocio, requisitos del MVP. Lo que *estamos haciendo*.\n\n"
        "Es una obra en curso: hay entradas más maduras que otras, así que conviene "
        "contrastar lo importante contra la fuente citada en cada una.\n\n"
        "Pregunta con consultar(), y usa panorama('tema') para ver un área concreta."
    )


def main() -> None:
    global IDX
    p = argparse.ArgumentParser(description="Servidor MCP de solo lectura para una KB")
    p.add_argument("--kb", required=True, help="Raiz del repo de la KB")
    p.add_argument("--transport", default="stdio", choices=["stdio", "streamable-http"])
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    a = p.parse_args()

    IDX = Indice(Path(a.kb))

    if a.transport == "streamable-http":
        mcp.settings.host, mcp.settings.port = a.host, a.port
        mcp.settings.stateless_http = True  # el RC 2026-07-28 elimina las sesiones

        # El SDK trae proteccion anti-DNS-rebinding activa con lista vacia, asi que
        # rechaza (421) cualquier Host que no sea localhost. Detras de un proxy hay
        # que declarar los Host legitimos. Se mantiene la proteccion, no se desactiva.
        hosts = [h.strip() for h in os.environ.get("KB_ALLOWED_HOSTS", "").split(",") if h.strip()]
        if hosts:
            mcp.settings.transport_security = TransportSecuritySettings(
                allowed_hosts=hosts,
                allowed_origins=[f"https://{h}" for h in hosts] + [f"http://{h}" for h in hosts],
            )

        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
