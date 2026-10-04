"""hacer_zip.py — el ZIP de la release: dist/MSX_SD_Maker_<version>.zip con una carpeta MSX_SD_Maker_<version>/ que
lleva MSXsdmaker.exe, la carpeta sd/ (lo que se copia a la tarjeta: los ficheros de sd/ que estan en git; el programa usa
esta carpeta y, si falta, la copia que lleva dentro el .exe), LEEME.md, README.md y LICENCIAS.md (sin capturas: las
imagenes de la guia apuntan a las de GitHub) y la carpeta OCM-SDBIOS/ con su LEEME, donde se deja el pack de KdL para
el MSXBOOK (el pack NO va en el ZIP). Para usarlo:
descomprimir y ejecutar MSXsdmaker.exe. (Antes: construir_exe.bat.)
Uso: python hacer_zip.py"""
import hashlib
import os
import subprocess
import sys
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from sdmaker import VERSION  # noqa: E402

EXE = os.path.join(AQUI, "dist", "MSXsdmaker.exe")
CAPTURAS = "https://raw.githubusercontent.com/Papipapito/SD_Maker/main/paquete/capturas/"


def main():
    if not os.path.isfile(EXE):
        sys.exit("falta dist/MSXsdmaker.exe: ejecuta antes construir_exe.bat")
    fuentes = [os.path.join(AQUI, "MSXsdmaker.py")] + [os.path.join(r, f) for r, _, fs in os.walk(os.path.join(AQUI, "sdmaker"))
                                                        for f in fs if f.endswith(".py")]
    if max(os.path.getmtime(f) for f in fuentes) > os.path.getmtime(EXE):
        sys.exit("el .exe es mas viejo que el codigo: vuelve a ejecutar construir_exe.bat")
    carpeta = "MSX_SD_Maker_%s" % VERSION
    destino = os.path.join(AQUI, "dist", carpeta + ".zip")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(EXE, carpeta + "/MSXsdmaker.exe")
        for n in ("LEEME.md", "README.md", "LICENCIAS.md"):
            texto = open(os.path.join(AQUI, "paquete", n), "rb").read().decode("utf-8")
            z.writestr("%s/%s" % (carpeta, n), texto.replace("](capturas/", "](" + CAPTURAS).encode("utf-8"))
        z.write(os.path.join(AQUI, "OCM-SDBIOS", "LEEME.txt"), carpeta + "/OCM-SDBIOS/LEEME.txt")
        sd = subprocess.run(["git", "ls-files", "-z", "sd"], cwd=AQUI, capture_output=True, check=True).stdout
        for rel in sorted(x for x in sd.decode("utf-8").split("\0") if x):
            nombre = rel.rsplit("/", 1)[-1].lower()
            if nombre.startswith(".") or nombre.endswith((".bak", ".tmp")):      # el programa tampoco los copia
                continue
            z.write(os.path.join(AQUI, *rel.split("/")), "%s/%s" % (carpeta, rel))
    h = hashlib.md5(open(destino, "rb").read()).hexdigest()[:12]
    print("%s (%d bytes, md5 %s)" % (destino, os.path.getsize(destino), h))
    with zipfile.ZipFile(destino) as z:
        nombres = z.namelist()
    for n in nombres:
        if "/sd/" not in n:
            print("   " + n)
    print("   %s/sd/: %d ficheros" % (carpeta, sum("/sd/" in n for n in nombres)))


if __name__ == "__main__":
    main()
