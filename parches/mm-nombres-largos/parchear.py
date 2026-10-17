"""parchear.py — aplica mmlfn.asm (nombre largo en File info) al MM.COM original de Multi Mente 2.07_A.

Uso:  python parchear.py MM.COM.original MM.COM.nuevo
El original (23.539 bytes) esta en git antes del parche:  git show bd3beb9:sd/base/MM/MM.COM > MM.COM.original
Necesita pasmo (http://pasmo.speccy.org/): en el PATH o, en Windows, dentro de WSL."""
import hashlib
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = 0x100
SHA1_ORIGINAL = "db7316e2b8f17deb1c34df909e2b8da8133e1601"
# direccion: (bytes originales, opcode nuevo, simbolo)
GANCHOS = {
    0x3E88: (b"\x11\x35\xC9", 0xC3, "hookfib"),
    0x34C3: (b"\xCD\xC4\x36", 0xCD, "prep"),
    0x34D5: (b"\xCD\xBA\x13", 0xCD, "name"),
    0x3547: (b"\xCD\xC3\x35", 0xCD, "mydate"),
}
# trozos de codigo muerto de MM: (inicio, simbolo del final, limite exclusivo)
MUERTOS = [(0x3D07, "fin3d07", 0x3D2B), (0x3D60, "fin3d60", 0x3DDE), (0x3DDF, "fin3ddf", 0x3E03)]


def ensamblar():
    for f in ("mmlfn.hex", "mmlfn.sym"):
        if os.path.exists(os.path.join(AQUI, f)):
            os.remove(os.path.join(AQUI, f))
    orden = ["pasmo", "--hex", "mmlfn.asm", "mmlfn.hex", "mmlfn.sym"]
    if not shutil.which("pasmo") and shutil.which("wsl"):
        orden = ["wsl"] + orden
    r = subprocess.run(orden, cwd=AQUI, capture_output=True, text=True)
    if r.returncode:
        sys.exit("pasmo: " + r.stdout + r.stderr)
    simbolos = {}
    for linea in open(os.path.join(AQUI, "mmlfn.sym")):
        p = linea.split()
        if len(p) >= 3 and p[1].upper() == "EQU":
            simbolos[p[0].lower()] = int(p[2].rstrip("Hh"), 16)
    memoria = {}
    for linea in open(os.path.join(AQUI, "mmlfn.hex")):
        linea = linea.strip()
        if not linea.startswith(":"):
            continue
        b = bytes.fromhex(linea[1:])
        n, dir_, tipo = b[0], b[1] << 8 | b[2], b[3]
        if tipo == 0:
            for i in range(n):
                memoria[dir_ + i] = b[4 + i]
    for f in ("mmlfn.hex", "mmlfn.sym"):
        os.remove(os.path.join(AQUI, f))
    return memoria, simbolos


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    orig, salida = sys.argv[1], sys.argv[2]
    d = bytearray(open(orig, "rb").read())
    if hashlib.sha1(d).hexdigest() != SHA1_ORIGINAL:
        sys.exit("%s no es el MM.COM 2.07_A original (sha1 %s)" % (orig, SHA1_ORIGINAL))
    memoria, s = ensamblar()
    fin_com = BASE + len(d)                     # 5CF3h
    assert d[0x3D5D - BASE:0x3D60 - BASE] == b"\xC3\x4A\x3E", "3D5Dh no es JP 3E4Ah"
    for dir_, (antes, op, sim) in GANCHOS.items():
        o = dir_ - BASE
        assert d[o:o + 3] == antes, "%04X: %s" % (dir_, d[o:o + 3].hex())
        d[o:o + 3] = bytes((op, s[sim] & 0xFF, s[sim] >> 8))
    # pasmo rellena los huecos entre ORG: solo se copian los trozos
    for ini, fin, limite in MUERTOS:
        assert s[fin] <= limite, "el trozo de %04Xh pasa de %04Xh" % (ini, limite - 1)
        for a in range(ini, s[fin]):
            d[a - BASE] = memoria[a]
        print("%04Xh-%04Xh: %d de %d bytes" % (ini, s[fin] - 1, s[fin] - ini, limite - ini))
    assert s["name"] > fin_com and s["finvar"] <= 0x5FBF, "las variables pasan de 5FBEh"
    d.extend(b"\x00" * (s["fincod"] - fin_com))
    for a in range(s["name"], s["fincod"]):
        d[a - BASE] = memoria[a]
    open(salida, "wb").write(d)
    print("%04Xh-%04Xh: %d bytes anadidos; variables hasta %04Xh (limite 5FBEh, sobran %d)"
          % (fin_com, s["fincod"] - 1, s["fincod"] - fin_com, s["finvar"] - 1, 0x5FBF - s["finvar"]))
    print("%s: %d bytes, sha1 %s" % (salida, len(d), hashlib.sha1(d).hexdigest()))


if __name__ == "__main__":
    main()
