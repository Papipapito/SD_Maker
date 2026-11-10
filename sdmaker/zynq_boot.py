"""zynq_boot.py — la tarjeta de ARRANQUE (TF1) de la MSXimus Z: una FAT32 (o FAT16) con el BOOT.bin en la raiz.

Con ella la placa arranca de la SD (SW1 en OFF-OFF) y, desde F12 -> U -> A, se graba sola en la QSPI (Z1.4.4 o
posterior). Este modulo hace la parte que no es ventana:

* los manifiestos de https://msx.barcelona/wp-content/ota/zynq/ (oficial) y .../beta/ (los mismos que lee la placa,
  fpga/zynq/ota/ota_publicar.py del repo de la Zynq): version, fecha, notas y, por variante, fichero, tamano y SHA-256;
* la FIRMA del manifiesto (ECDSA P-256 + SHA-256, la clave publica de la placa, en Python puro: sin dependencias);
* la descarga a una cache del usuario, comprobada por tamano y SHA-256 (si ya esta y cuadra, no se vuelve a bajar);
* la comprobacion de un BOOT.bin cualquiera (cabecera de arranque del Zynq y la particion ota_info de make_boot.sh);
* crear(): la tarjeta entera sobre un dispositivo de dispositivos.py (tarjeta o imagen), con fatfs/particiones/verificar
  de SD Maker: borra el principio y el final, formatea, copia BOOT.bin, escribe la tabla AL FINAL y lo relee todo (CRC);
* el ayudante de macOS (una copia del ejecutable con permisos de administrador, como ayudante_macos.py)."""
import base64
import hashlib
import json
import os
import random
import re
import shlex
import ssl
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request

from . import dispositivos, fatfs, idioma, particiones, textos_zynq, verificar

textos_zynq.registrar()

VERSION_PROGRAMA = "0.9 beta"
SECTOR = 512
BASE = "https://msx.barcelona/wp-content/ota/zynq/"
CANALES = (("oficial", BASE), ("beta", BASE + "beta/"))
PLACA = "zynq7020-mini"
VARIANTES = ("nextor214", "nextor3", "nextor214-en", "nextor3-en")
NOMBRE_VARIANTE = {
    "es": {"nextor214": "Nextor 2.1.4, menús en castellano", "nextor3": "Nextor 3, menús en castellano",
           "nextor214-en": "Nextor 2.1.4, menús en inglés", "nextor3-en": "Nextor 3, menús en inglés"},
    "en": {"nextor214": "Nextor 2.1.4, Spanish menus", "nextor3": "Nextor 3, Spanish menus",
           "nextor214-en": "Nextor 2.1.4, English menus", "nextor3-en": "Nextor 3, English menus"},
}
IMG_MIN, IMG_MAX = 4096, 8 << 20       # lo que acepta la propia placa (F12 -> U -> A)
ETIQUETA = "MSXIMUS Z"
AGENTE = "MSXimusZboot/%s (+https://github.com/Papipapito/SD_Maker)" % VERSION_PROGRAMA.split()[0]

# La clave publica de las actualizaciones (fpga/zynq/ota/ota_publica.pem del repo de la Zynq).
CLAVE_PEM = """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAExzZ1rFrk2O0iDSTQRaA61UT4WKo+
Yys/FJTU9Pw9iMcadHlIoOP9R/q9sRT430sUDbN5thHJz+mCtqGUKCZ2VQ==
-----END PUBLIC KEY-----"""


# ------------------------------------------------------------------ ECDSA P-256 (solo verificar)
_P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
_A = _P - 3
_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
_G = (0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
      0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5)
_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B


def _suma(p, q):
    if p is None:
        return q
    if q is None:
        return p
    if p[0] == q[0]:
        if (p[1] + q[1]) % _P == 0:
            return None
        m = (3 * p[0] * p[0] + _A) * pow(2 * p[1], -1, _P) % _P
    else:
        m = (q[1] - p[1]) * pow(q[0] - p[0], -1, _P) % _P
    x = (m * m - p[0] - q[0]) % _P
    return x, (m * (p[0] - x) - p[1]) % _P


def _por(k, p):
    r = None
    while k:
        if k & 1:
            r = _suma(r, p)
        p = _suma(p, p)
        k >>= 1
    return r


def _clave_publica():
    der = base64.b64decode("".join(l for l in CLAVE_PEM.splitlines() if not l.startswith("-----")))
    punto = der[-65:]
    if punto[0] != 4:
        raise ValueError("clave publica no valida")
    x, y = int.from_bytes(punto[1:33], "big"), int.from_bytes(punto[33:], "big")
    if (y * y - (x * x * x + _A * x + _B)) % _P:
        raise ValueError("la clave publica no esta en la curva")
    return x, y


def verificar_ecdsa(mensaje, firma64, clave=None):
    """firma64 = r||s (32 + 32 bytes, big endian) sobre SHA-256(mensaje)."""
    if len(firma64) != 64:
        return False
    r, s = int.from_bytes(firma64[:32], "big"), int.from_bytes(firma64[32:], "big")
    if not (0 < r < _N and 0 < s < _N):
        return False
    e = int.from_bytes(hashlib.sha256(mensaje).digest(), "big")
    w = pow(s, -1, _N)
    q = clave or _clave_publica()
    x = _suma(_por(e * w % _N, _G), _por(r * w % _N, q))
    return x is not None and x[0] % _N == r


# ------------------------------------------------------------------ manifiestos
class ErrorManifiesto(Exception):
    pass


def leer_manifiesto(texto, canal="oficial", base=None, comprobar_firma=True):
    """El manifiesto (bytes) -> dict: version, serie, fecha, canal, notas, imagenes {variante: {...}}, base."""
    if not texto.startswith(b"MSXIMUS-OTA 1\n"):
        raise ErrorManifiesto(idioma.t("zb.manifiesto_raro"))
    i = texto.rfind(b"\nfirma=")
    if i < 0:
        raise ErrorManifiesto(idioma.t("zb.sin_firma"))
    firmado = texto[:i + 1]
    try:
        firma = bytes.fromhex(texto[i + 7:].strip().decode("ascii"))
    except ValueError:
        raise ErrorManifiesto(idioma.t("zb.firma_mala"))
    if comprobar_firma and not verificar_ecdsa(firmado, firma):
        raise ErrorManifiesto(idioma.t("zb.firma_mala"))
    d = {"canal": canal, "base": base, "notas": [], "imagenes": {}}
    for linea in firmado.decode("utf-8", "replace").splitlines()[1:]:
        if "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        if k == "notas":
            d["notas"].append(v)
        elif k == "imagen":
            partes = v.split()
            if len(partes) == 4 and re.fullmatch(r"[0-9a-f]{64}", partes[3]) and partes[2].isdigit():
                d["imagenes"][partes[0]] = {"variante": partes[0], "fichero": os.path.basename(partes[1]),
                                            "tamano": int(partes[2]), "sha256": partes[3]}
        elif k in ("placa", "version", "serie", "fecha", "canal"):
            d[k] = v
    if d.get("placa") != PLACA:
        raise ErrorManifiesto(idioma.t("zb.otra_placa", d.get("placa")))
    if not d.get("version") or not d["imagenes"]:
        raise ErrorManifiesto(idioma.t("zb.manifiesto_raro"))
    return d


def _contexto_ssl():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _abrir_url(url, timeout=30):
    pet = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    return urllib.request.urlopen(pet, timeout=timeout, context=_contexto_ssl())


def bajar_manifiestos(timeout=20):
    """[(canal, dict o None, error o None)] de los dos canales."""
    out = []
    for canal, base in CANALES:
        try:
            with _abrir_url(base + "manifiesto.txt", timeout) as r:
                texto = r.read(65536)
            out.append((canal, leer_manifiesto(texto, canal, base), None))
        except Exception as e:
            out.append((canal, None, "%s" % (e.reason if hasattr(e, "reason") else e)))
    return out


# ------------------------------------------------------------------ cache y descarga
def carpeta_cache():
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
        return os.path.join(base, "MSXimusZboot", "cache")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Caches/MSXimusZboot")
    return os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "MSXimusZboot")


def _sha256_fichero(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for trozo in iter(lambda: f.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def bajar_imagen(manifiesto, variante, aviso=None, cancelar=None):
    """Baja (o coge de la cache) el BOOT.bin de esa variante y lo comprueba. -> ruta del fichero."""
    aviso = aviso or (lambda texto, fraccion=None: None)
    e = manifiesto["imagenes"][variante]
    os.makedirs(carpeta_cache(), exist_ok=True)
    destino = os.path.join(carpeta_cache(), e["fichero"])
    if os.path.isfile(destino) and os.path.getsize(destino) == e["tamano"] and _sha256_fichero(destino) == e["sha256"]:
        aviso(idioma.t("zb.en_cache", e["fichero"]), 0.30)
        return destino
    temporal = destino + ".parcial"
    h = hashlib.sha256()
    hecho = 0
    with _abrir_url(manifiesto["base"] + e["fichero"], 60) as r, open(temporal, "wb") as f:
        while True:
            if cancelar and cancelar():
                raise RuntimeError(idioma.t("zb.cancelado"))
            trozo = r.read(1 << 16)
            if not trozo:
                break
            f.write(trozo)
            h.update(trozo)
            hecho += len(trozo)
            if hecho > IMG_MAX:
                raise ValueError(idioma.t("zb.tamano_raro", hecho))
            aviso(idioma.t("zb.bajando", e["fichero"], hecho * 100 // max(1, e["tamano"])),
                  0.30 * hecho / max(1, e["tamano"]))
    if hecho != e["tamano"] or h.hexdigest() != e["sha256"]:
        os.remove(temporal)
        raise ValueError(idioma.t("zb.descarga_mala", e["fichero"]))
    os.replace(temporal, destino)
    return destino


# ------------------------------------------------------------------ el BOOT.bin
def info_boot(datos):
    """Comprueba que es un BOOT.bin de Zynq y saca su ota_info. -> dict (puede estar vacio) o ValueError."""
    if not (IMG_MIN <= len(datos) <= IMG_MAX):
        raise ValueError(idioma.t("zb.tamano_raro", len(datos)))
    w = struct.unpack_from("<10I", datos, 0)
    if w[8] != 0xAA995566 or w[9] != 0x584C4E58:
        raise ValueError(idioma.t("zb.no_es_boot"))
    i = datos.find(b"MOTI1\nversion=")
    if i < 0:
        return {}
    texto = datos[i:i + 256].split(b"\0")[0].decode("ascii", "replace")
    return dict(l.split("=", 1) for l in texto.splitlines()[1:] if "=" in l)


# ------------------------------------------------------------------ la tarjeta
def planificar(sectores, esquema="fat32"):
    """fat32 = una FAT32 desde el sector 8192 (como el formateador de la SD Association); fat16 = una FAT16 de hasta
    2 GB desde el sector 1 (como el FDISK de Nextor). La placa arranca de las dos."""
    if esquema == "fat16":
        return particiones.planificar(sectores, "fat16-2g") if sectores > particiones.GB2 + 1 else \
            [particiones.Particion(1, 1, min(particiones.GB4, sectores - 1), particiones.TIPO_FAT16, activa=True)]
    return particiones.planificar(sectores, "fat32")


def crear(dev, plan, boot, etiqueta=ETIQUETA, aviso=None):
    """La tarjeta entera: BOOT.bin (bytes) en la raiz de la particion 1. Devuelve un informe como proceso.crear."""
    aviso = aviso or (lambda texto, fraccion=None: None)
    info_boot(boot)
    t0 = time.time()
    rnd = random.Random()
    aviso(idioma.t("p.borrando"), 0.35)
    uno = min(2048, dev.sectores)
    dev.escribir(0, bytes(uno * SECTOR))
    if dev.sectores > 4096:
        dev.escribir(dev.sectores - 2048, bytes(2048 * SECTOR))
    raiz = fatfs.Nodo("", es_dir=True)
    raiz.hijos.append(fatfs.Nodo("BOOT.bin", datos=boot))   # 8.3 + bit NT de extension en minusculas, como Windows
    p = plan[0]
    g = fatfs.geometria_fat32(p.sectores, p.lba) if p.tipo == particiones.TIPO_FAT32 else \
        fatfs.geometria_fat16_nextor(p.sectores)
    aviso(idioma.t("p.formateando", 1, g), 0.45)
    v = fatfs.Volumen(dev, p.lba, g, etiqueta[:11], rnd.getrandbits(32), ocultos=p.lba,
                      progreso=lambda ruta: aviso(idioma.t("p.copiando", ruta), 0.70))
    usados = v.formatear(raiz)
    aviso(idioma.t("p.tabla"), 0.85)
    for lba, s in particiones.sectores_tabla(dev.sectores, plan, rnd.getrandbits(32) | 1):
        dev.escribir(lba, s)
    aviso(idioma.t("p.verificando"), 0.92)
    errores = verificar.comprobar(dev, plan, [v])
    aviso(idioma.t("p.hecho" if not errores else "p.hecho_errores"), 1.0)
    return {"particiones": [{"numero": 1, "geometria": str(g), "etiqueta": etiqueta[:11], "clusters_usados": usados}],
            "ficheros": 1, "bytes": len(boot), "errores": errores, "segundos": time.time() - t0}


# ------------------------------------------------------------------ macOS: la copia con permisos de administrador
def datos_trabajo(tarjeta, plan, ruta_boot, etiqueta=ETIQUETA):
    return {"formato": 1, "idioma": idioma.actual(),
            "tarjeta": {k: tarjeta.get(k) for k in ("numero", "bytes", "modelo", "identidad")},
            "plan": [{"numero": p.numero, "lba": p.lba, "sectores": p.sectores, "tipo": p.tipo, "activa": p.activa,
                      "lba_ebr": p.lba_ebr} for p in plan],
            "boot": os.path.abspath(ruta_boot), "sha256": _sha256_fichero(ruta_boot), "etiqueta": etiqueta}


def _comando_ayudante(ruta):
    if getattr(sys, "frozen", False):
        return [sys.executable, "--ayudante-zynq", ruta]
    principal = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "MSXimusZboot.py"))
    return [sys.executable, principal, "--ayudante-zynq", ruta]


def _cadena_applescript(texto):
    return '"' + texto.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _leer_progreso(f, aviso):
    while True:
        linea = f.readline()
        if not linea:
            break
        try:
            d = json.loads(linea)
            aviso(d["texto"], d.get("fraccion"))
        except (ValueError, KeyError, TypeError):
            continue


def lanzar_macos(datos, aviso):
    """Pide la contrasena de administrador (dialogo de macOS), sigue el progreso y devuelve el informe. Las dos
    funciones de arriba son las de ayudante_macos.py, copiadas para no arrastrar al programa todo SD Maker (py7zr...)."""
    if sys.platform != "darwin":
        raise RuntimeError(idioma.t("am.solo_macos"))
    with tempfile.TemporaryDirectory(prefix="msximuszboot_") as tmp:
        trabajo = os.path.join(tmp, "trabajo.json")
        progreso = os.path.join(tmp, "progreso.jsonl")
        resultado = os.path.join(tmp, "resultado.json")
        with open(trabajo, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False)
        open(progreso, "w", encoding="utf-8").close()
        open(resultado, "w", encoding="utf-8").close()
        guion = "do shell script %s with administrator privileges" % _cadena_applescript(
            shlex.join(_comando_ayudante(trabajo)))
        p = subprocess.Popen(["/usr/bin/osascript", "-e", guion], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True)
        with open(progreso, "r", encoding="utf-8") as f:
            while p.poll() is None:
                _leer_progreso(f, aviso)
                time.sleep(0.1)
            _leer_progreso(f, aviso)
        salida, error = p.communicate()
        try:
            with open(resultado, "r", encoding="utf-8") as f:
                r = json.load(f)
        except (OSError, ValueError):
            r = {}
        if p.returncode or not r.get("ok"):
            if r.get("error"):
                raise RuntimeError(r["error"])
            detalle = (error or salida or "").strip()
            if "(-128)" in detalle or "cancel" in detalle.lower():
                raise PermissionError(idioma.t("am.cancelado"))
            raise PermissionError(detalle or idioma.t("am.sin_permisos"))
        for texto in r.get("avisos", []):
            aviso(texto, None)
        return r["informe"]


def ejecutar_ayudante(ruta_trabajo):
    """La copia privilegiada de macOS. Devuelve el codigo de salida."""
    carpeta = os.path.dirname(os.path.abspath(ruta_trabajo))
    resultado, progreso = os.path.join(carpeta, "resultado.json"), os.path.join(carpeta, "progreso.jsonl")

    def guardar(d):
        with open(resultado, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)

    try:
        if sys.platform != "darwin" or os.geteuid() != 0:
            raise PermissionError(idioma.t("am.necesita_admin"))
        with open(ruta_trabajo, "r", encoding="utf-8") as f:
            d = json.load(f)
        if d.get("idioma") in idioma.TABLAS:
            idioma.fijar(d["idioma"])
        if d.get("formato") != 1:
            raise ValueError(idioma.t("am.formato"))
        plan = [particiones.Particion(int(p["numero"]), int(p["lba"]), int(p["sectores"]), int(p["tipo"]),
                                      bool(p.get("activa")), p.get("lba_ebr")) for p in d["plan"]]
        if len(plan) != 1:
            raise ValueError(idioma.t("am.plan"))
        with open(d["boot"], "rb") as f:
            boot = f.read(IMG_MAX + 1)
        if hashlib.sha256(boot).hexdigest() != d["sha256"]:
            raise ValueError(idioma.t("zb.descarga_mala", os.path.basename(d["boot"])))
        with open(progreso, "a", encoding="utf-8", buffering=1) as log:
            def aviso(texto, fraccion=None):
                log.write(json.dumps({"texto": texto, "fraccion": fraccion}, ensure_ascii=False) + "\n")
            dev = dispositivos.DiscoMacOS(int(d["tarjeta"]["numero"]), esperada=d["tarjeta"])
            try:
                informe = crear(dev, plan, boot, str(d.get("etiqueta") or ETIQUETA), aviso)
            finally:
                dev.cerrar()
            avisos = [dev.aviso_cierre] if dev.aviso_cierre else []
        guardar({"ok": True, "informe": informe, "avisos": avisos})
        return 0
    except Exception as e:
        try:
            guardar({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})
        except Exception:
            pass
        return 1
