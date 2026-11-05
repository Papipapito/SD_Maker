"""hacer_huellas.py — genera sdmaker/huellas.py: las huellas (sha1) de TODAS las versiones que ha tenido cada fichero de
la tarjeta, sacadas de la historia de git (cada commit que toca sd/ y cada tag de version) y de sd/ tal como esta ahora.

  python herramientas/hacer_huellas.py

Hay que volver a pasarlo cada vez que cambia algo en sd/ (pruebas/probar_actualizar.py falla si falta alguno). Necesita
git y la historia completa (en CI el checkout es de profundidad 1: alli no se ejecuta, solo se usa el resultado).
Cada fichero de sd/ se lleva a su ruta de la tarjeta con contenido.rutas_tarjeta (igual que contenido.arbol). Los .BAT,
.TXT y .BTM de sd/ llevan CRLF en la tarjeta (.gitattributes los saca asi), aunque git los guarde con LF.
Formato: FICHEROS[ruta] = "sha12:mascara ..."; sha12 = los 12 primeros hex del sha1; mascara (hex) = bit i si esa version
esta en TAGS[i] (el bit len(TAGS) es sd/ de ahora). MM/MMRET.DAT no va en FICHEROS: la tarjeta lleva uno ajustado a lo
que contiene; sus lineas (sha1 de 8 hex) van en LINEAS_MMRET para reconocerlo. SISTEMA = sha12 de NEXTOR.SYS -> sistema."""
import hashlib
import os
import re
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.normpath(os.path.join(AQUI, ".."))
sys.path.insert(0, RAIZ)
from sdmaker import contenido  # noqa: E402

SALIDA = os.path.join(RAIZ, "sdmaker", "huellas.py")
CRLF = (".BAT", ".bat", ".TXT", ".BTM")
SISTEMA_DE = {"nextor-2.1.4": "nextor214", "nextor-3.0.0": "nextor3", "nextor-3.0.0-beta2": "nextor3beta2",
              "nextor-3.0.0-beta1": "nextor3beta1"}
GENERADO = "MM/MMRET.DAT"


def git(*args, entrada=None):
    p = subprocess.run(["git", *args], cwd=RAIZ, input=entrada, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        sys.exit("git %s: %s" % (" ".join(args), p.stderr.decode("utf-8", "replace")))
    return p.stdout


def clave_version(tag):
    return tuple(int(x) for x in re.findall(r"\d+", tag))


def arbol_de(commit):
    """{ruta relativa a sd/: blob} del commit."""
    out = {}
    for linea in git("ls-tree", "-r", "-z", commit, "sd/").split(b"\0"):
        if linea:
            meta, ruta = linea.split(b"\t", 1)
            out[ruta.decode("utf-8")[3:]] = meta.split()[2].decode()
    return out


def contenidos(blobs):
    """{blob: bytes}, con git cat-file --batch."""
    salida = git("cat-file", "--batch", entrada=("\n".join(sorted(blobs)) + "\n").encode())
    out, i = {}, 0
    while i < len(salida):
        fin = salida.index(b"\n", i)
        blob, _, tam = salida[i:fin].split()
        i = fin + 1 + int(tam)
        out[blob.decode()] = salida[fin + 1:i]
        i += 1
    return out


def como_en_tarjeta(rel, datos):
    return datos.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n") if rel.endswith(CRLF) else datos


def sha12(datos):
    return hashlib.sha1(datos).hexdigest()[:12]


def main():
    tags = sorted((t for t in git("tag", "--list").decode().split() if re.fullmatch(r"v\d+(\.\d+)*", t)),
                  key=clave_version)
    commits = git("log", "--all", "--format=%H", "--", "sd").decode().split()
    versiones = [(commit, 0) for commit in commits]
    versiones += [(git("rev-parse", t + "^{commit}").decode().strip(), 1 << i) for i, t in enumerate(tags)]
    arboles = [(arbol_de(c), bit) for c, bit in versiones]
    datos = contenidos({b for a, _ in arboles for b in a.values()})

    ficheros = {}       # ruta (mayusculas) -> {sha12: mascara}
    sistema = {}
    lineas = set()

    def anotar(rel, contenido_, bit):
        for ruta in contenido.rutas_tarjeta(rel):
            if ruta.upper() == GENERADO:
                lineas.update(sha12(l)[:8] for l in contenido_.split(b"\n"))
                continue
            d = ficheros.setdefault(ruta.upper(), {})
            d[sha12(contenido_)] = d.get(sha12(contenido_), 0) | bit
            partes = rel.split("/")
            if len(partes) == 2 and partes[1] == "NEXTOR.SYS" and partes[0] in SISTEMA_DE:
                sistema[sha12(contenido_)] = SISTEMA_DE[partes[0]]

    for arbol, bit in arboles:
        for rel, blob in arbol.items():
            anotar(rel, como_en_tarjeta(rel, datos[blob]), bit)
    actual = 1 << len(tags)         # sd/ tal como esta ahora en el disco
    base = os.path.join(RAIZ, "sd")
    for d, carpetas, nombres in os.walk(base):
        carpetas.sort()
        for n in sorted(nombres):
            p = os.path.join(d, n)
            with open(p, "rb") as f:
                anotar(os.path.relpath(p, base).replace(os.sep, "/"), f.read(), actual)

    lineas.discard(sha12(b"")[:8])
    with open(SALIDA, "w", encoding="utf-8", newline="\n") as f:
        f.write('"""huellas.py — GENERADO por herramientas/hacer_huellas.py: no se edita a mano (ver ese fichero)."""\n\n')
        f.write("TAGS = %r\n\n" % (tags,))
        f.write("SISTEMA = %r\n\n" % (dict(sorted(sistema.items())),))
        texto = " ".join(sorted(lineas))
        f.write("LINEAS_MMRET = (\n")
        for i in range(0, len(texto), 100):
            f.write("    %r\n" % (texto[i:i + 100] if i + 100 >= len(texto) else texto[i:i + 100]))
        f.write(")\n\n")
        f.write("FICHEROS = {\n")
        for ruta in sorted(ficheros):
            f.write("    %r: %r,\n" % (ruta, " ".join("%s:%x" % kv for kv in sorted(ficheros[ruta].items()))))
        f.write("}\n")
    print("huellas.py: %d rutas, %d versiones de ficheros, %d lineas de MMRET.DAT, tags %s" % (
        len(ficheros), sum(len(v) for v in ficheros.values()), len(lineas), ", ".join(tags)))


if __name__ == "__main__":
    main()
