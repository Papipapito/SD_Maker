"""parchear.py — aplica mmlfn.asm (nombres largos en la lista y en File info) al MM.COM original de Multi Mente 2.07_A.

Uso:  python parchear.py MM.COM.original MM.COM.nuevo [--simbolos fichero.sym]
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
    0x0100: (b"\xC3\xC4\x5C", 0xC3, "start"),
    0x3E4A: (b"\x21\xFF\x5F", 0xCD, "lstart"),
    0x3E88: (b"\x11\x35\xC9", 0xC3, "hookfib"),
    0x3E82: (b"\x2A\x8C\x3E", 0xC3, "pass"),
    0x33BF: (b"\xCD\x76\x13", 0xCD, "lstname"),
    0x34C3: (b"\xCD\xC4\x36", 0xCD, "prep"),
    0x34D5: (b"\xCD\xBA\x13", 0xCD, "tname"),
    0x3547: (b"\xCD\xC3\x35", 0xCD, "mydate"),
}
# 586Fh: LD (HL),FFh / LD A,(F24Fh) -> CALL takeseg / NOP / NOP
GANCHO5 = (0x586F, b"\x36\xFF\x3A\x4F\xF2", "takeseg")
# trozos de codigo muerto de MM: (inicio, simbolo del final, limite exclusivo)
MUERTOS = [(0x3D07, "fin3d07", 0x3D2B), (0x3D60, "fin3d60", 0x3DDE), (0x3DDF, "fin3ddf", 0x3E03)]
MARCAS = 0x5FBF         # MM usa desde aqui (marcas, _DPARM, registros): el arranque cae aqui al cargar
P3ORG = 0xCB92          # MM usa hasta CB91h


def ensamblar(simbolos_a=None):
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
    if simbolos_a:
        shutil.copyfile(os.path.join(AQUI, "mmlfn.sym"), simbolos_a)
    for f in ("mmlfn.hex", "mmlfn.sym"):
        os.remove(os.path.join(AQUI, f))
    return memoria, simbolos


def main():
    args = sys.argv[1:]
    simbolos_a = None
    if "--simbolos" in args:
        i = args.index("--simbolos")
        simbolos_a = args[i + 1]
        del args[i:i + 2]
    if len(args) != 2:
        sys.exit(__doc__)
    orig, salida = args
    d = bytearray(open(orig, "rb").read())
    if hashlib.sha1(d).hexdigest() != SHA1_ORIGINAL:
        sys.exit("%s no es el MM.COM 2.07_A original (sha1 %s)" % (orig, SHA1_ORIGINAL))
    memoria, s = ensamblar(simbolos_a)
    fin_com = BASE + len(d)                     # 5CF3h
    assert d[0x3D5D - BASE:0x3D60 - BASE] == b"\xC3\x4A\x3E", "3D5Dh no es JP 3E4Ah"
    for dir_, (antes, op, sim) in GANCHOS.items():
        o = dir_ - BASE
        assert d[o:o + 3] == antes, "%04X: %s" % (dir_, d[o:o + 3].hex())
        d[o:o + 3] = bytes((op, s[sim] & 0xFF, s[sim] >> 8))
    dir_, antes, sim = GANCHO5
    o = dir_ - BASE
    assert d[o:o + 5] == antes, "%04X: %s" % (dir_, d[o:o + 5].hex())
    d[o:o + 5] = bytes((0xCD, s[sim] & 0xFF, s[sim] >> 8, 0, 0))
    # pasmo rellena los huecos entre ORG: solo se copian los trozos
    for ini, fin, limite in MUERTOS:
        assert s[fin] <= limite, "el trozo de %04Xh pasa de %04Xh" % (ini, limite - 1)
        for a in range(ini, s[fin]):
            d[a - BASE] = memoria[a]
        print("%04Xh-%04Xh: %d de %d bytes" % (ini, s[fin] - 1, s[fin] - ini, limite - ini))
    # File info (version 1): detras del final de MM.COM, hasta las marcas
    assert s["name"] > fin_com and s["finvar"] <= MARCAS, "las variables pasan de %04Xh" % (MARCAS - 1)
    d.extend(b"\x00" * (MARCAS - fin_com))
    for a in range(s["name"], s["fincod"]):
        d[a - BASE] = memoria[a]
    print("%04Xh-%04Xh: %d bytes; variables hasta %04Xh (sobran %d)"
          % (fin_com, s["fincod"] - 1, s["fincod"] - fin_com, s["finvar"] - 1, MARCAS - s["finvar"]))
    # el arranque y, detras, lo que copia a la pagina 3
    assert s["start"] == MARCAS and s["p3org"] == P3ORG
    for a in range(s["start"], s["img"]):
        d.append(memoria[a])
    for a in range(P3ORG, s["p3end"]):
        d.append(memoria[a])
    assert len(d) == s["img"] - BASE + s["p3end"] - P3ORG
    print("arranque %04Xh-%04Xh; pagina 3 %04Xh-%04Xh (%d bytes en el fichero), variables hasta %04Xh"
          % (s["start"], s["img"] - 1, P3ORG, s["p3end"] - 1, s["p3end"] - P3ORG, s["p3fin"] - 1))
    print("cima del TPA minima %04Xh; el marco de File info sin tabla no baja de %02X00h"
          % (s["p3fin"] + s["stkneed"], s["stkmin"]))
    open(salida, "wb").write(d)
    print("%s: %d bytes, sha1 %s" % (salida, len(d), hashlib.sha1(d).hexdigest()))


if __name__ == "__main__":
    main()
