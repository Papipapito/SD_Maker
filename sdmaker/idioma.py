"""idioma.py — castellano / inglés de la interfaz. Los textos están en textos_es.py y textos_en.py (diccionarios clave ->
texto, con % para los datos); t("clave", datos...) devuelve el del idioma actual. El idioma por defecto es el del
sistema; la elección se recuerda en el fichero de ajustes del usuario (ajustes.json). Sin gettext ni ficheros de datos."""
import json
import locale
import os
import subprocess
import sys

from . import textos_en, textos_es

IDIOMAS = [("es", "Español"), ("en", "English")]
TABLAS = {"es": textos_es.TEXTOS, "en": textos_en.TEXTOS}
CARPETA_AJUSTES = "MSXsdmaker"
FICHERO_AJUSTES = "ajustes.json"

_actual = None


def tr(lang, clave, *datos):
    """El texto de clave en el idioma lang (el actual si es None); con datos, aplicado con %."""
    texto = TABLAS.get(lang or actual(), textos_en.TEXTOS).get(clave)
    if texto is None:
        texto = textos_es.TEXTOS.get(clave, clave)
    return texto % datos if datos else texto


def t(clave, *datos):
    return tr(None, clave, *datos)


def existe(clave):
    return clave in TABLAS["es"]


def prefijos(clave):
    """El comienzo (hasta el primer %) del texto de clave en todos los idiomas: para reconocer un aviso sea cual sea
    el idioma con el que se emitió."""
    return tuple({tabla[clave].split("%")[0] for tabla in TABLAS.values()})


def miles(n):
    """1234567 -> 1.234.567 (castellano) o 1,234,567 (inglés)."""
    return format(n, ",").replace(",", "." if actual() == "es" else ",")


def decimal(texto):
    """Cambia el punto decimal de un número ya formateado con %.2f al del idioma."""
    return texto.replace(".", ",") if actual() == "es" else texto


# ------------------------------------------------------------------ idioma del sistema
def de_locale(texto):
    """'es_ES.UTF-8', 'es-MX', 'Spanish_Spain', 'es' -> 'es'; cualquier otro nombre -> 'en'; vacío, C o POSIX -> None."""
    t_ = (texto or "").strip().lower()
    if not t_ or t_ in ("c", "posix") or t_.startswith(("c.", "c@")):
        return None
    return "es" if t_.startswith(("es", "spanish", "castellano", "español")) else "en"


def _de_entorno():
    out = []
    for v in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        out += [x for x in os.environ.get(v, "").split(":") if x]
    return out


def _de_locale():
    out = []
    try:
        out.append(locale.getlocale()[0])
    except Exception:
        pass
    try:
        out.append(locale.getdefaultlocale()[0])
    except Exception:
        pass
    return [x for x in out if x]


def _de_windows():
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(85)
        if ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, len(buf)):
            return [buf.value]
    except Exception:
        pass
    return []


def _de_macos():
    """Los idiomas preferidos del usuario (dentro de una .app el LANG suele venir vacío)."""
    out = []
    try:
        r = subprocess.run(["/usr/bin/defaults", "read", "-g", "AppleLanguages"], capture_output=True, text=True,
                           timeout=5)
        out += [x.strip().strip('",()') for x in r.stdout.splitlines()]
    except Exception:
        pass
    try:
        import Foundation       # PyObjC, si lo hay
        out += list(Foundation.NSLocale.preferredLanguages() or [])
    except Exception:
        pass
    return [x for x in out if x]


def _candidatos():
    if sys.platform == "darwin":
        return _de_macos() + _de_entorno() + _de_locale()
    if sys.platform == "win32":
        return _de_windows() + _de_entorno() + _de_locale()
    return _de_entorno() + _de_locale()


def detectar():
    """'es' si el primer nombre de locale conocido empieza por es; 'en' en cualquier otro caso."""
    try:
        for c in _candidatos():
            d = de_locale(c)
            if d:
                return d
    except Exception:
        pass
    return "en"


# ------------------------------------------------------------------ ajustes del usuario
def ruta_ajustes():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, CARPETA_AJUSTES, FICHERO_AJUSTES)


def leer_ajustes():
    try:
        with open(ruta_ajustes(), "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def guardar_ajustes(cambios):
    """Mezcla cambios con los ajustes que ya hubiera. Si no se puede escribir, no pasa nada."""
    try:
        d = leer_ajustes()
        d.update(cambios)
        ruta = ruta_ajustes()
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8", newline="\n") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return True
    except Exception:
        return False


def actual():
    """El idioma en uso: el último fijado, o el de los ajustes del usuario, o el del sistema."""
    global _actual
    if _actual is None:
        elegido = leer_ajustes().get("idioma")
        _actual = elegido if elegido in TABLAS else detectar()
    return _actual


def fijar(lang, recordar=False):
    global _actual
    if lang not in TABLAS:
        raise ValueError("idioma: %s" % ", ".join(TABLAS))
    _actual = lang
    if recordar:
        guardar_ajustes({"idioma": lang})
