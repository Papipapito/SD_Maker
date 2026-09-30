"""publicar_paquete.py — copia el paquete de MSX SD Maker a la carpeta MSXsdmaker/ de un repositorio (MSXimus, MSXimus_138,
MSXimus_zynq, MSXnano): el .exe, las instrucciones (LEEME.md, README.md), LICENCIAS.md, las capturas y el codigo fuente
en fuente/. No hace commit: eso se hace en cada repo.
Uso: python publicar_paquete.py <raiz del repo> [<raiz de otro repo>...]      (antes: construir_exe.bat)"""
import os
import shutil
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTE = ["MSXsdmaker.py", "construir_exe.bat", "LEEME.md", ".gitignore", "sdmaker", "pruebas"]


def copiar(origen, destino):
    if os.path.isdir(origen):
        os.makedirs(destino, exist_ok=True)
        for n in sorted(os.listdir(origen)):
            if n == "__pycache__":
                continue
            copiar(os.path.join(origen, n), os.path.join(destino, n))
    else:
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        shutil.copy2(origen, destino)


def publicar(repo):
    dst = os.path.join(repo, "MSXsdmaker")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    exe = os.path.join(AQUI, "dist", "MSXsdmaker.exe")
    if not os.path.isfile(exe):
        sys.exit("falta dist/MSXsdmaker.exe: ejecuta antes construir_exe.bat")
    shutil.copy2(exe, dst)
    for n in ("LEEME.md", "README.md", "LICENCIAS.md", "capturas"):
        copiar(os.path.join(AQUI, "paquete", n), os.path.join(dst, n))
    for n in FUENTE:
        copiar(os.path.join(AQUI, n), os.path.join(dst, "fuente", n))
    total = sum(len(f) for _, _, f in os.walk(dst))
    print("%s: %d ficheros" % (dst, total))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for r in sys.argv[1:]:
        publicar(os.path.abspath(r))
