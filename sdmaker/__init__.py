"""MSXsdmaker: tarjetas SD para MSXimus, MSXnano, MSX Pico y MSXBOOK / 1chipMSX (OCM-PLD)."""
import os
import sys

VERSION = "1.5.2"


def carpeta_programa():
    """Carpeta junto al ejecutable o, en macOS, junto al paquete ``.app``."""
    if not getattr(sys, "frozen", False):
        return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    carpeta = os.path.dirname(sys.executable)
    if sys.platform == "darwin" and os.path.basename(carpeta) == "MacOS":
        contents = os.path.dirname(carpeta)
        app = os.path.dirname(contents)
        if os.path.basename(contents) == "Contents" and app.lower().endswith(".app"):
            return os.path.dirname(app)
    return carpeta
