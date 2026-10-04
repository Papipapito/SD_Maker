"""hacer_zip.py — el ZIP de la release: dist/MSX_SD_Maker_<version>.zip con una carpeta MSX_SD_Maker_<version>/ que
lleva MSXsdmaker.exe y la estructura del paquete (LEEME.md, README.md, LICENCIAS.md, capturas/ y la carpeta
OCM-SDBIOS/ con su LEEME, donde se deja el pack de KdL para el MSXBOOK). Para usarlo:
descomprimir y ejecutar MSXsdmaker.exe. (Antes: construir_exe.bat.)
Uso: python hacer_zip.py"""
import hashlib
import os
import sys
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from sdmaker import VERSION  # noqa: E402

EXE = os.path.join(AQUI, "dist", "MSXsdmaker.exe")


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
            z.write(os.path.join(AQUI, "paquete", n), "%s/%s" % (carpeta, n))
        z.write(os.path.join(AQUI, "OCM-SDBIOS", "LEEME.txt"), carpeta + "/OCM-SDBIOS/LEEME.txt")
        for n in sorted(os.listdir(os.path.join(AQUI, "paquete", "capturas"))):
            z.write(os.path.join(AQUI, "paquete", "capturas", n), "%s/capturas/%s" % (carpeta, n))
    h = hashlib.md5(open(destino, "rb").read()).hexdigest()[:12]
    print("%s (%d bytes, md5 %s)" % (destino, os.path.getsize(destino), h))
    with zipfile.ZipFile(destino) as z:
        for n in z.namelist():
            print("   " + n)


if __name__ == "__main__":
    main()
