#!/usr/bin/env python3
"""
Servidor MCP de solo lectura para una KB construida con kb-template.

Indexa el Markdown en SQLite FTS5 (BM25, tokenizer apto para espanol) y expone
busqueda lexica + navegacion del grafo de wikilinks. Sin escritura, sin estado.

    python server.py --kb ~/traza-ambiental                    # stdio (Claude Code)
    python server.py --kb ~/traza-ambiental --transport http   # para el VPS
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# --- parseo ------------------------------------------------------------------

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n?", re.S)
WIKILINK = re.compile(r"\[\[([^\[\]|#]+?)(?:#[^\[\]|]*)?(?:\|[^\[\]]*)?\]\]")

# Campos de grafo en kb-template. depende_de es escalar; los otros, listas.
CAMPOS_GRAFO = ("depende_de", "se_descompone_en", "se_relaciona_con")


def _wikilinks(valor) -> list[str]:
    """Extrae nombres de nodo de un campo de frontmatter (str, lista o vacio)."""
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
    def __init__(self, raiz: Path):
        self.raiz = raiz.expanduser().resolve()
        self.base = self.raiz / "knowledge-base"
        if not self.base.is_dir():
            raise SystemExit(f"No existe {self.base} — ¿es una KB de kb-template?")
        self.nodos: dict[str, Nodo] = {}
        self.backlinks: dict[str, set[str]] = {}
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.construir()

    def construir(self) -> None:
        self.nodos.clear()
        self.backlinks.clear()

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

        # Backlinks: por campos de grafo y por menciones en prosa.
        for nodo in self.nodos.values():
            destinos = {d for ds in nodo.enlaces.values() for d in ds} | set(nodo.menciona)
            for destino in destinos:
                if destino in self.nodos and destino != nodo.nombre:
                    self.backlinks.setdefault(destino, set()).add(nodo.nombre)

        self._fts()

    def _fts(self) -> None:
        db = self.db
        db.executescript("DROP TABLE IF EXISTS docs;")
        # remove_diacritics 2 normaliza correctamente todos los latinos (el 1 tiene
        # un bug conocido con codepoints multi-diacritico). Sin 'porter': es solo ingles.
        db.execute(
            "CREATE VIRTUAL TABLE docs USING fts5("
            "  nombre, cuerpo, polo UNINDEXED, tipo UNINDEXED,"
            "  estado UNINDEXED, vigencia UNINDEXED,"
            "  tokenize='unicode61 remove_diacritics 2'"
            ")"
        )
        db.executemany(
            "INSERT INTO docs (nombre, cuerpo, polo, tipo, estado, vigencia)"
            " VALUES (?,?,?,?,?,?)",
            [
                (
                    n.nombre,
                    n.cuerpo,
                    n.polo,
                    str(n.meta.get("tipo") or ""),
                    str(n.meta.get("estado") or ""),
                    str(n.meta.get("vigencia") or ""),
                )
                for n in self.nodos.values()
            ],
        )
        db.commit()


# --- servidor ----------------------------------------------------------------

mcp = FastMCP("kb")
IDX: Indice


def _ficha(n: Nodo) -> str:
    m = n.meta
    partes = [f"**{n.nombre}** · {n.polo}"]
    for campo in ("tipo", "estado", "vigencia"):
        if m.get(campo):
            partes.append(f"{campo}={m[campo]}")
    return " · ".join(partes)


@mcp.tool()
def buscar(
    consulta: str,
    polo: str | None = None,
    tipo: str | None = None,
    estado: str | None = None,
    limite: int = 8,
) -> str:
    """Busca en el texto de la KB con ranking BM25 y devuelve extractos.

    consulta: terminos sueltos, o sintaxis FTS5 ("a AND b", "frase exacta", pref*).
    polo: 'Contexto' (lo que ES) o 'Trazambiental' (lo que se CONSTRUYE).
    tipo: norma_legal, factor_externo, requisito_tecnico, hecho_negativo,
          decision_del_humano, regla_de_negocio.
    estado: borrador, verificado, con_vacios.
    """
    filtros, args = [], [consulta]
    for campo, valor in (("polo", polo), ("tipo", tipo), ("estado", estado)):
        if valor:
            filtros.append(f"AND {campo} = ?")
            args.append(valor)
    args.append(max(1, min(limite, 25)))

    try:
        filas = IDX.db.execute(
            "SELECT nombre, snippet(docs, 1, '', '', ' … ', 20) "
            f"FROM docs WHERE docs MATCH ? {' '.join(filtros)} "
            "ORDER BY rank LIMIT ?",
            args,
        ).fetchall()
    except sqlite3.OperationalError as e:
        return f"Consulta FTS5 invalida ({e}). Prueba con terminos simples o entre comillas."

    if not filas:
        return f"Sin resultados para «{consulta}»" + (" con esos filtros." if filtros else ".")

    salida = [f"{len(filas)} resultado(s) para «{consulta}»:\n"]
    for nombre, frag in filas:
        salida.append(f"### {_ficha(IDX.nodos[nombre])}\n{frag.strip()}\n")
    salida.append("\nUsa leer_nodo(nombre) para el texto completo.")
    return "\n".join(salida)


@mcp.tool()
def leer_nodo(nombre: str) -> str:
    """Devuelve el Markdown completo y verbatim de un nodo, con su frontmatter."""
    nodo = IDX.nodos.get(nombre)
    if not nodo:
        cerca = [n for n in IDX.nodos if nombre.lower() in n.lower()][:8]
        sugerencia = "\n".join(f"  - {c}" for c in cerca)
        return f"No existe el nodo «{nombre}».\n" + (
            f"¿Quisiste decir?\n{sugerencia}" if cerca else "Usa listar() para ver los nodos."
        )
    cabecera = yaml.safe_dump(nodo.meta, allow_unicode=True, sort_keys=False).strip()
    return f"<!-- {nodo.ruta} -->\n---\n{cabecera}\n---\n{nodo.cuerpo}"


@mcp.tool()
def vecinos(nombre: str) -> str:
    """Muestra el grafo alrededor de un nodo: de que depende, en que se descompone,
    con que se relaciona, y que otros nodos lo enlazan (backlinks)."""
    nodo = IDX.nodos.get(nombre)
    if not nodo:
        return f"No existe el nodo «{nombre}». Usa buscar() o listar() para ubicarlo."

    def bloque(titulo: str, nombres) -> str:
        vivos = [n for n in nombres if n in IDX.nodos]
        rotos = [n for n in nombres if n not in IDX.nodos]
        if not vivos and not rotos:
            return ""
        lineas = [f"**{titulo}**"]
        lineas += [f"  - {n}" for n in sorted(vivos)]
        lineas += [f"  - {n}  ⚠ enlace roto" for n in sorted(rotos)]
        return "\n".join(lineas)

    secciones = [_ficha(nodo), ""]
    etiquetas = {
        "depende_de": "Depende de",
        "se_descompone_en": "Se descompone en",
        "se_relaciona_con": "Se relaciona con",
    }
    for campo, etiqueta in etiquetas.items():
        if b := bloque(etiqueta, nodo.enlaces.get(campo, [])):
            secciones.append(b)
    if b := bloque("Lo enlazan (backlinks)", IDX.backlinks.get(nombre, set())):
        secciones.append(b)

    solo_prosa = sorted(set(nodo.menciona) & IDX.nodos.keys() - {nombre})
    if solo_prosa:
        secciones.append("**Menciona en prosa**\n" + "\n".join(f"  - {n}" for n in solo_prosa))

    return "\n\n".join(s for s in secciones if s)


@mcp.tool()
def listar(
    polo: str | None = None,
    tipo: str | None = None,
    estado: str | None = None,
    vigencia: str | None = None,
) -> str:
    """Inventario de nodos filtrable por polo, tipo, estado y vigencia.
    Sin filtros devuelve el resumen agregado de la KB."""
    sel = [
        n for n in IDX.nodos.values()
        if (not polo or n.polo == polo)
        and (not tipo or n.meta.get("tipo") == tipo)
        and (not estado or n.meta.get("estado") == estado)
        and (not vigencia or n.meta.get("vigencia") == vigencia)
    ]
    if not any([polo, tipo, estado, vigencia]):
        def cuenta(campo):
            c: dict[str, int] = {}
            for n in IDX.nodos.values():
                c[str(n.meta.get(campo) or "—")] = c.get(str(n.meta.get(campo) or "—"), 0) + 1
            return ", ".join(f"{k}: {v}" for k, v in sorted(c.items(), key=lambda x: -x[1]))

        polos: dict[str, int] = {}
        for n in IDX.nodos.values():
            polos[n.polo] = polos.get(n.polo, 0) + 1
        return (
            f"{len(IDX.nodos)} nodos en la KB.\n\n"
            f"**Polo**: {', '.join(f'{k}: {v}' for k, v in sorted(polos.items(), key=lambda x: -x[1]))}\n"
            f"**tipo**: {cuenta('tipo')}\n"
            f"**estado**: {cuenta('estado')}\n"
            f"**vigencia**: {cuenta('vigencia')}\n\n"
            "Filtra con listar(polo=..., tipo=..., estado=...) o busca con buscar(consulta)."
        )
    if not sel:
        return "Ningun nodo coincide con esos filtros."
    sel.sort(key=lambda n: (n.polo, n.nombre))
    return f"{len(sel)} nodo(s):\n\n" + "\n".join(f"- {_ficha(n)}" for n in sel)


@mcp.tool()
def recargar() -> str:
    """Reindexa la KB desde disco. Usar despues de un git pull."""
    IDX.construir()
    return f"Reindexados {len(IDX.nodos)} nodos desde {IDX.base}."


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
        # que declarar los Host legitimos: el nombre del servicio en la red interna
        # y el dominio publico. Se mantiene la proteccion, no se desactiva.
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
