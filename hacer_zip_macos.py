"""Crea el paquete de macOS conservando ejecutables, enlaces y metadatos del bundle con ``ditto``."""
import hashlib
import os
import platform
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from sdmaker import VERSION  # noqa: E402

APP = os.path.join(AQUI, "dist", "MSXsdmaker.app")
CAPTURAS = "https://raw.githubusercontent.com/Papipapito/SD_Maker/main/paquete/capturas/"


def _copiar_sd(destino):
    datos = subprocess.run(["git", "ls-files", "-z", "sd"], cwd=AQUI, capture_output=True, check=True).stdout
    for rel in sorted(x for x in datos.decode("utf-8").split("\0") if x):
        nombre = rel.rsplit("/", 1)[-1].lower()
        if nombre.startswith(".") or nombre.endswith((".bak", ".tmp")):
            continue
        salida = os.path.join(destino, *rel.split("/"))
        os.makedirs(os.path.dirname(salida), exist_ok=True)
        shutil.copy2(os.path.join(AQUI, *rel.split("/")), salida)


def main():
    if not os.path.isdir(APP):
        sys.exit("falta dist/MSXsdmaker.app: ejecuta antes construir_macos.sh")
    arquitectura = {"arm64": "arm64", "x86_64": "x86_64"}.get(platform.machine(), platform.machine())
    nombre = "MSX_SD_Maker_%s_macOS_%s" % (VERSION, arquitectura)
    carpeta = os.path.join(AQUI, "dist", nombre)
    destino = carpeta + ".zip"
    shutil.rmtree(carpeta, ignore_errors=True)
    os.makedirs(carpeta)
    shutil.copytree(APP, os.path.join(carpeta, "MSXsdmaker.app"), symlinks=True)
    for n in ("LEEME.md", "README.md", "LICENCIAS.md"):
        with open(os.path.join(AQUI, "paquete", n), "r", encoding="utf-8") as f:
            texto = f.read().replace("](capturas/", "](" + CAPTURAS)
        with open(os.path.join(carpeta, n), "w", encoding="utf-8") as f:
            f.write(texto)
    os.makedirs(os.path.join(carpeta, "OCM-SDBIOS"))
    shutil.copy2(os.path.join(AQUI, "OCM-SDBIOS", "LEEME.txt"), os.path.join(carpeta, "OCM-SDBIOS", "LEEME.txt"))
    _copiar_sd(carpeta)
    if os.path.exists(destino):
        os.unlink(destino)
    subprocess.run(["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", carpeta, destino], check=True)
    with open(destino, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    print("%s (%d bytes, sha256 %s)" % (destino, os.path.getsize(destino), sha))


if __name__ == "__main__":
    main()
