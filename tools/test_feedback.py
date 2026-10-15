"""Pruebas de feedback.py sin tocar GitHub: el corte en puntos y los títulos.

    python3 -m pytest ~/toolset/tools/test_feedback.py -q
"""
import tempfile
from pathlib import Path

import feedback

WORD = Path.home() / "devalis" / "Errores funcionales 3.docx"


def test_titulo_primera_oracion():
    assert feedback.titulo_de("No permite editar usuarios. Además otra cosa larga.") == \
        "No permite editar usuarios."


def test_titulo_corta_en_palabra():
    t = feedback.titulo_de("palabra " * 30)
    assert t.endswith("…") and len(t) <= feedback.LARGO_TITULO + 1 and not t.endswith(" …")


def test_titulo_corto_entero():
    assert feedback.titulo_de("Podríamos ver una miniatura del documento o foto?") == \
        "Podríamos ver una miniatura del documento o foto?"


def test_partir_puntos_imagen_pegada_al_numero():
    texto = "1. Uno.\n\n[]2. Dos\n\n[]\n\n3. Tres.[]\n\n14\n[]\n\nCatorce.\n"
    puntos = feedback.partir_puntos(texto)
    assert [n for n, _ in puntos] == [1, 2, 3, 14]
    assert [c.count("[]") for _, c in puntos] == [0, 2, 1, 1]


def test_word_de_pablo():
    if not WORD.exists():
        return
    with tempfile.TemporaryDirectory() as tmp:
        filas = feedback.filas_de_archivo(WORD, tmp)
    assert [n for n, _, _ in filas] == list(range(1, 25))
    assert sum(len(a) for _, _, a in filas) == 14
    por_numero = {n: (t, a) for n, t, a in filas}
    assert por_numero[1] == ("No permite editar usuarios.", [])
    assert por_numero[2][0] == "No responde el whatsApp" and len(por_numero[2][1]) == 2
    assert por_numero[3][1] == []
    assert por_numero[21][0] == "(solo imagen)"
