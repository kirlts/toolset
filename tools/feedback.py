#!/usr/bin/env python3
"""Punto de entrada común del feedback: una fila por reporte en kirlts/feedback.

Sale del dibujo «Idea QA» (2026-10-15): tres proyectos, tres canales, una caja, un Dev.
La caja es el repositorio kirlts/feedback; cada issue es una fila.

    feedback nueva --proyecto okos --qa "Alan" --canal whatsapp --texto "..." [--evidencia F...]
    feedback listar [--proyecto P] [--estado nuevo|en-curso|respondido]
    feedback responder N --texto "..."
    feedback desde-archivo ARCHIVO --proyecto P --qa Q [--canal en-persona] [--fecha AAAA-MM-DD]
    feedback desde-github REPO --proyecto P [--etiqueta qa]
    feedback pendientes [--proyecto P]   # salida corta para inyectar en una sesión

desde-archivo lee lo que pandoc lea (docx, md, txt, odt) y crea una fila por punto numerado,
con las imágenes que el punto trae. La numeración es la del documento.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

REPO = "kirlts/feedback"
CLON = Path.home() / "feedback"
PROYECTOS = ("okos", "devalis", "otro")
CANALES = ("whatsapp", "github", "en-persona")
ESTADOS = ("nuevo", "en-curso", "respondido")
LARGO_TITULO = 80


def gh(*args, entrada=None):
    r = subprocess.run(["gh", *args], text=True, capture_output=True, input=entrada)
    if r.returncode != 0:
        sys.exit(f"gh {' '.join(args[:2])}: {r.stderr.strip()}")
    return r.stdout


def issues(estado=None, proyecto=None, todas=False):
    args = ["issue", "list", "-R", REPO, "--limit", "500", "--json",
            "number,title,labels,body,createdAt,url,state"]
    args += ["--state", "all" if todas else "open"]
    if estado:
        args += ["--label", f"estado:{estado}"]
    if proyecto:
        args += ["--label", f"proyecto:{proyecto}"]
    return json.loads(gh(*args))


def etiqueta(issue, prefijo):
    for l in issue["labels"]:
        if l["name"].startswith(prefijo + ":"):
            return l["name"].split(":", 1)[1]
    return ""


def campo(issue, nombre):
    m = re.search(rf"^\| {re.escape(nombre)} \| (.*?) \|$", issue["body"], re.M)
    return m.group(1) if m else ""


_TODAS = None


def existe(origen):
    global _TODAS
    if not origen:
        return None
    if _TODAS is None:
        _TODAS = issues(todas=True)
    for i in _TODAS:
        if campo(i, "Origen") == origen:
            return i
    return None


def titulo_de(texto):
    """La primera oración, o los primeros 80 caracteres cortados en una palabra."""
    t = re.sub(r"\s+", " ", texto.strip())
    m = re.match(r"(.{10,%d}?[.!?])(\s|$)" % LARGO_TITULO, t)
    if m:
        return m.group(1)
    if len(t) <= LARGO_TITULO:
        return t
    corte = t.rfind(" ", 0, LARGO_TITULO)
    return t[:corte if corte > 20 else LARGO_TITULO] + "…"


_EVIDENCIA_PENDIENTE = False


def guardar_evidencia(archivos, clave):
    """Copia los archivos al clon y devuelve enlaces. El push se hace una vez, al final."""
    global _EVIDENCIA_PENDIENTE
    if not archivos:
        return []
    if not CLON.exists():
        sys.exit(f"Falta el clon en {CLON}: gh repo clone {REPO} {CLON}")
    destino = CLON / "evidencia" / clave
    destino.mkdir(parents=True, exist_ok=True)
    enlaces = []
    for a in archivos:
        a = Path(a)
        shutil.copy(a, destino / a.name)
        enlaces.append(f"https://github.com/{REPO}/blob/main/evidencia/{clave}/{a.name}?raw=true")
    _EVIDENCIA_PENDIENTE = True
    return enlaces


def publicar_evidencia():
    if not _EVIDENCIA_PENDIENTE:
        return
    subprocess.run(["git", "-C", str(CLON), "add", "evidencia"], check=True)
    subprocess.run(["git", "-C", str(CLON), "commit", "-q", "-m",
                    f"evidencia: {date.today().isoformat()}"], check=True)
    subprocess.run(["git", "-C", str(CLON), "push", "-q"], check=True)


def nueva(proyecto, qa, canal, texto, evidencia=(), origen="", fecha=None, titulo=None):
    previa = existe(origen)
    if previa:
        print(f"ya existe\t#{previa['number']}\t{previa['url']}")
        return previa
    fecha = fecha or date.today().isoformat()
    titulo = titulo or titulo_de(texto)
    clave = (f"{fecha}-{proyecto}-{re.sub(r'[^a-z0-9]+', '-', qa.lower())[:20]}-"
             f"{hashlib.sha1((origen or texto).encode()).hexdigest()[:6]}")
    enlaces = guardar_evidencia(evidencia, clave)
    cuerpo = "\n".join([
        "| Columna | Valor |", "|---|---|",
        f"| Proyecto | {proyecto} |",
        f"| QA | {qa} |",
        f"| Canal | {canal} |",
        f"| Fecha | {fecha} |",
        f"| Origen | {origen} |",
        f"| Evidencia | {' '.join(enlaces) if enlaces else '(sin evidencia)'} |",
        "", "## Qué reportó", "", texto.strip(), "",
    ] + [f"![evidencia]({e})" for e in enlaces])
    url = gh("issue", "create", "-R", REPO, "--title", titulo, "--body", cuerpo,
             "--label", f"proyecto:{proyecto}", "--label", f"canal:{canal}",
             "--label", "estado:nuevo").strip()
    print(f"{url}\t{proyecto}\t{qa}\t{canal}\t{titulo}")
    return {"url": url}


def listar(proyecto=None, estado=None):
    filas = issues(estado=estado, proyecto=proyecto, todas=bool(estado == "respondido"))
    print("N\tProyecto\tQA\tCanal\tEstado\tFecha\tQué reportó")
    for i in sorted(filas, key=lambda x: x["number"]):
        print("\t".join([f"#{i['number']}", etiqueta(i, "proyecto"), campo(i, "QA"),
                         etiqueta(i, "canal"), etiqueta(i, "estado"), campo(i, "Fecha"),
                         i["title"]]))


def responder(numero, texto):
    i = json.loads(gh("issue", "view", str(numero), "-R", REPO, "--json", "number,labels,body,url"))
    qa, canal = campo(i, "QA"), etiqueta(i, "canal")
    gh("issue", "comment", str(numero), "-R", REPO, "--body",
       f"## Respuesta al QA\n\n{texto.strip()}\n\n{date.today().isoformat()} · por {canal} a {qa}")
    gh("issue", "edit", str(numero), "-R", REPO, "--remove-label", "estado:nuevo",
       "--remove-label", "estado:en-curso", "--add-label", "estado:respondido")
    gh("issue", "close", str(numero), "-R", REPO)
    origen = campo(i, "Origen")
    if canal == "github" and re.match(r"https://github\.com/[^/]+/[^/]+/issues/\d+$", origen):
        gh("issue", "comment", origen, "--body", texto.strip())
        print(f"#{numero}\trespondido\tenviada a {qa} en {origen}")
        return
    print(f"#{numero}\trespondido\tfalta enviarla por {canal} a {qa}")


# pandoc deja «[]» donde iba cada imagen. El número de un punto abre línea, a veces con una
# imagen pegada delante («[]2. …»), a veces sin punto («14»).
_PUNTO = r"[ \t]*(?:\[\][ \t]*)?\d{1,3}[.)]?(?:[ \t]+|\n)"


def partir_puntos(texto):
    """Devuelve [(número, cuerpo con sus «[]»)] en el orden del documento."""
    partes = re.split(r"\n(?=" + _PUNTO + ")", "\n" + texto)
    puntos = []
    for p in partes:
        m = re.match(r"[ \t]*((?:\[\][ \t]*)?)(\d{1,3})[.)]?(?:[ \t]+|\n)(.*)", p, re.S)
        if m:
            puntos.append((int(m.group(2)), m.group(1) + m.group(3)))
    return puntos


def leer_archivo(archivo, carpeta_medios):
    texto = subprocess.run(["pandoc", str(archivo), "-t", "plain", "--wrap=none",
                            f"--extract-media={carpeta_medios}"], text=True,
                           capture_output=True, check=True).stdout
    media = Path(carpeta_medios) / "media"
    medios = sorted(media.glob("*"), key=lambda p: int(re.sub(r"\D", "", p.name) or 0)) \
        if media.exists() else []
    return texto, medios


def filas_de_archivo(archivo, carpeta_medios):
    """[(número, texto limpio, [imágenes])] de un documento con puntos numerados."""
    texto, medios = leer_archivo(archivo, carpeta_medios)
    filas, indice = [], 0
    for n, cuerpo in partir_puntos(texto):
        k = cuerpo.count("[]")
        adjuntos = medios[indice:indice + k]
        indice += k
        limpio = cuerpo.replace("[]", "").strip()
        filas.append((n, limpio or "(solo imagen)", adjuntos))
    return filas


def desde_archivo(archivo, proyecto, qa, canal="en-persona", fecha=None):
    archivo = Path(archivo)
    fecha = fecha or date.fromtimestamp(archivo.stat().st_mtime).isoformat()
    with tempfile.TemporaryDirectory() as tmp:
        for n, texto, adjuntos in filas_de_archivo(archivo, tmp):
            nueva(proyecto, qa, canal, texto, adjuntos, origen=f"{archivo.name}#{n}", fecha=fecha)
        publicar_evidencia()


def desde_github(repo, proyecto, etiqueta_qa="qa"):
    args = ["issue", "list", "-R", repo, "--state", "open", "--limit", "200",
            "--json", "number,title,body,url,author,createdAt"]
    if etiqueta_qa:
        args += ["--label", etiqueta_qa]
    for i in json.loads(gh(*args)):
        nueva(proyecto, i["author"]["login"], "github", i["body"] or i["title"],
              origen=i["url"], fecha=i["createdAt"][:10], titulo=i["title"])


def pendientes(proyecto=None):
    filas = [i for i in issues(proyecto=proyecto) if etiqueta(i, "estado") != "respondido"]
    if not filas:
        return
    print(f"FEEDBACK DE QA SIN RESPONDER ({len(filas)}), en https://github.com/{REPO}/issues:")
    for i in sorted(filas, key=lambda x: x["number"]):
        print(f"· #{i['number']} [{etiqueta(i, 'proyecto')}] {campo(i, 'QA')} por "
              f"{etiqueta(i, 'canal')} ({campo(i, 'Fecha')}): {i['title']}")
    print("Responder: feedback responder N --texto \"...\"")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="orden", required=True)
    a = s.add_parser("nueva")
    a.add_argument("--proyecto", required=True, choices=PROYECTOS)
    a.add_argument("--qa", required=True)
    a.add_argument("--canal", required=True, choices=CANALES)
    a.add_argument("--texto", required=True)
    a.add_argument("--evidencia", nargs="*", default=[])
    a.add_argument("--origen", default="")
    a = s.add_parser("listar")
    a.add_argument("--proyecto", choices=PROYECTOS)
    a.add_argument("--estado", choices=ESTADOS)
    a = s.add_parser("responder")
    a.add_argument("numero", type=int)
    a.add_argument("--texto", required=True)
    a = s.add_parser("desde-archivo", aliases=["desde-docx"])
    a.add_argument("archivo")
    a.add_argument("--proyecto", required=True, choices=PROYECTOS)
    a.add_argument("--qa", required=True)
    a.add_argument("--canal", default="en-persona", choices=CANALES)
    a.add_argument("--fecha")
    a = s.add_parser("desde-github")
    a.add_argument("repo")
    a.add_argument("--proyecto", required=True, choices=PROYECTOS)
    a.add_argument("--etiqueta", default="qa")
    a = s.add_parser("pendientes")
    a.add_argument("--proyecto", choices=PROYECTOS)
    o = p.parse_args()
    if o.orden == "nueva":
        nueva(o.proyecto, o.qa, o.canal, o.texto, o.evidencia, o.origen)
        publicar_evidencia()
    elif o.orden == "listar":
        listar(o.proyecto, o.estado)
    elif o.orden == "responder":
        responder(o.numero, o.texto)
    elif o.orden in ("desde-archivo", "desde-docx"):
        desde_archivo(o.archivo, o.proyecto, o.qa, o.canal, o.fecha)
    elif o.orden == "desde-github":
        desde_github(o.repo, o.proyecto, o.etiqueta)
    elif o.orden == "pendientes":
        pendientes(o.proyecto)


if __name__ == "__main__":
    main()
