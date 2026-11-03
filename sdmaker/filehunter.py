"""Cliente de la API pública de File-Hunter usado por el menú de MSXnano.

SD Maker no lleva ROMs: busca y descarga únicamente cuando el usuario lo
pide. La respuesta de descarga incluye tamaño y CRC-32; ambos se verifican
antes de dejar el fichero en la caché privada del usuario.
"""
import binascii
import os
import re
import tempfile
import urllib.parse
import urllib.request

from . import idioma

HOST = "api.file-hunter.com"
BASE_API = "http://api.file-hunter.com/MSXnano.php?base=1BA0&type=rom&msx=&char="
AGENTE = "MSXnano/1.9"


def buscar(texto, timeout=30):
    """Devuelve [{indice, nombre, kb, load}] como la fase 1 del menú MSXnano."""
    texto = texto.strip()
    if len(texto) < 2:
        raise ValueError(idioma.t("fh.dos_caracteres"))
    datos = _get(BASE_API + urllib.parse.quote_plus(texto), timeout)
    pos, registros = 0, []
    while True:
        if pos + 4 > len(datos):
            raise ValueError(idioma.t("fh.busqueda_incompleta"))
        if datos[pos:pos + 4] == b"\0\0\0\0":
            pos += 4
            break
        if pos + 7 > len(datos):
            raise ValueError(idioma.t("fh.registro_incompleto"))
        kb = int.from_bytes(datos[pos + 4:pos + 6], "little")
        registros.append({"indice": len(registros), "kb": kb, "load": datos[pos + 6]})
        pos += 7
    for r in registros:
        fin = datos.find(b"\0", pos)
        if fin < 0:
            raise ValueError(idioma.t("fh.nombre_incompleto"))
        r["nombre"] = datos[pos:fin].decode("latin-1", "replace")
        pos = fin + 1
    return registros


def descargar(texto, resultado, timeout=60, tamano_esperado=16 * 1024):
    """Descarga por el índice de la consulta, verifica metadatos y devuelve la ruta local."""
    url = "%s%s&download=%d" % (BASE_API, urllib.parse.quote_plus(texto.strip()), resultado["indice"])
    datos = _get(url, timeout)
    salto = datos.find(b"\n")
    if salto < 0:
        raise ValueError(idioma.t("fh.sin_meta"))
    meta_raw, contenido = datos[:salto].decode("latin-1", "replace"), datos[salto + 1:]
    meta = {}
    for parte in meta_raw.split(","):
        if ":" in parte:
            clave, valor = parte.split(":", 1)
            meta[clave.strip().lower()] = valor.strip()
    try:
        tamano = int(meta["size"])
        crc_esperado = int(meta["crc"], 16)
    except (KeyError, ValueError) as e:
        raise ValueError(idioma.t("fh.meta_rara")) from e
    if tamano != len(contenido):
        raise ValueError(idioma.t("fh.descarga_incompleta", len(contenido), tamano))
    crc = binascii.crc32(contenido) & 0xFFFFFFFF
    if crc != crc_esperado:
        raise ValueError(idioma.t("fh.crc", crc, crc_esperado))
    if tamano != tamano_esperado:
        raise ValueError(idioma.t("fh.tam", meta.get("name", resultado["nombre"]), tamano, tamano_esperado))
    nombre = _nombre_seguro(meta.get("name") or resultado["nombre"])
    destino_dir = carpeta_cache()
    os.makedirs(destino_dir, exist_ok=True)
    destino = os.path.join(destino_dir, nombre)
    fd, temporal = tempfile.mkstemp(prefix=".descarga-", dir=destino_dir)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(contenido)
        os.replace(temporal, destino)
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)
    return destino


def carpeta_cache():
    """Carpeta privada del usuario; nunca forma parte del paquete distribuido."""
    import sys
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "MSX SD Maker", "File-Hunter")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Caches/MSX SD Maker/File-Hunter")
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "msx-sd-maker", "file-hunter")


def _get(url, timeout):
    peticion = urllib.request.Request(url, headers={
        "Host": HOST, "User-Agent": AGENTE, "Connection": "close",
    })
    with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
        return respuesta.read()


def _nombre_seguro(nombre):
    nombre = os.path.basename(nombre.replace("\\", "/"))
    nombre = re.sub(r"[^A-Za-z0-9._()\[\] -]", "_", nombre).strip(" .")
    if not nombre.lower().endswith(".rom"):
        nombre += ".rom"
    return nombre or "file-hunter.rom"
