"""actualizar.py — poner al dia una tarjeta ya hecha, SIN formatear y sin borrar ni pisar nada del usuario.

Se trabaja por la unidad montada (letra en Windows, punto de montaje en macOS / Linux), con ficheros normales: nada de
escribir el disco en crudo. Este modulo recibe la RUTA de la raiz de la particion de arranque y no usa tkinter:
  analizar(raiz, ...)   -> Plan: lo detectado y lo que se haria; NO escribe nada.
  aplicar(plan, ...)    -> lo ejecuta, lo verifica y devuelve un Informe.
Cada fichero que lleva la version actual para esa tarjeta tiene un estado (ver ESTADOS):
  igual (nada), falta (se copia si su grupo ya esta en la tarjeta o el usuario lo pide), version nuestra antigua (se
  actualiza: su sha1 esta en huellas.py o en la marca SDMAKER.INF), huella desconocida (es del usuario: no se toca, y se
  puede forzar, guardando antes una copia .BAK) y configuracion del usuario (nunca se pisa). Lo nuestro que ya no va en la
  version nueva se queda donde esta y se lista como «ya no se usa». Los ficheros que no son nuestros no se miran.
Nombres sin distinguir mayusculas (FAT); se conserva el que ya tenga el fichero. Rutas de la tarjeta con "/"."""
import hashlib
import os
import re
import shutil
import stat
import sys
import time

from . import VERSION, contenido, huellas, idioma
from .idioma import t

NOMBRE_MARCA = "SDMAKER.INF"
TEMPORAL = "~SDMUPD.TMP"
CLUSTER = 64 * 1024         # para ver si cabe: cada fichero se redondea a un cluster grande (conservador)
MARGEN = 1 << 20

# Estados de cada fichero
IGUAL, ACTUALIZAR, ANADIR, CAMBIADO, SIN_USO, CONFIG = "igual", "actualizar", "anadir", "cambiado", "sin_uso", "config"
ESTADOS = (ACTUALIZAR, ANADIR, CAMBIADO, SIN_USO, CONFIG, IGUAL)

# Configuracion del usuario: si existe NUNCA se pisa ni se marca como «cambiado»; si falta, se copia.
CONFIG_USUARIO = ("IA/IA.CFG", "SOFARUN/SR.INI", "SOFARUN/SROM.INI", "SOFARUN/SSMS.INI", "MM/MM.HIS", "MM/MM.PHS")
CONFIG_PREFIJOS = ("HUB/CONFIG/",)
# Configuracion que los propios programas reescriben: solo se actualiza si sigue igual que alguna version publicada;
# si difiere, es del usuario y se conserva sin avisar.
CONFIG_SI_DIFIERE = ("MM/MM.CFG", "MUSICA/MBFM/MBFM.CFG", "MUSICA/MBWAVE/MBWAVE.CFG")

CONSERVAR = "conservar"     # destino: dejar el sistema de la tarjeta como esta
FPGA_SISTEMAS = ["nextor214", "nextor3", "nextor3beta2", "msxdos"]
SISTEMAS_GEN = set(FPGA_SISTEMAS)
GENERADOS = ("AUTOEXEC.BAT", "AUTOEXEC.BTM", "REBOOT.BAT", "MM/MMRET.DAT")
OBLIGATORIOS = ("NEXTOR.SYS", "COMMAND3.COM")     # al cambiar de Nextor, aunque los haya cambiado el usuario
BIOS_OCM = ["OCM-BIOS.DA%s" % c for c in "T0123456789"]
ALT_OCM = ["ALT-BIOS.DA%d" % i for i in range(10)]
FLASH = ("PLDFLASH.COM", "SMXFLASH.COM")


class ErrorActualizar(Exception):
    pass


class SinSitio(ErrorActualizar):
    pass


class SinConfirmar(ErrorActualizar):
    pass


def sha1(datos):
    return hashlib.sha1(datos).hexdigest()


def _k(ruta):
    return ruta.replace("\\", "/").upper()


def _ignorado(nombre):
    n = nombre.lower()
    return n.startswith(".") or n in ("system volume information", "$recycle.bin")


def _leer(ruta):
    with open(ruta, "rb") as f:
        return f.read()


# ------------------------------------------------------------------ la tarjeta como carpeta
class Tarjeta:
    """La raiz de la particion de arranque, con los nombres sin distinguir mayusculas (y sin lo que el sistema esconde)."""

    def __init__(self, raiz):
        self.raiz = os.path.abspath(raiz)
        self._ls = {}

    def listar(self, carpeta):
        if carpeta not in self._ls:
            try:
                nombres = os.listdir(carpeta)
            except OSError:
                nombres = []
            self._ls[carpeta] = {n.upper(): n for n in nombres if not _ignorado(n)}
        return self._ls[carpeta]

    def buscar(self, ruta):
        """Ruta real (con las mayusculas que tenga) de una ruta con "/", o None."""
        actual = self.raiz
        for p in ruta.split("/"):
            real = self.listar(actual).get(p.upper())
            if real is None:
                return None
            actual = os.path.join(actual, real)
        return actual

    def asegurar_carpeta(self, ruta):
        """Crea las carpetas que falten (con el nombre que se pide) y devuelve la ruta real."""
        actual = self.raiz
        for p in ruta.split("/"):
            if not p:
                continue
            real = self.listar(actual).get(p.upper())
            if real is None:
                os.mkdir(os.path.join(actual, p))
                self._ls.pop(actual, None)
                real = p
            actual = os.path.join(actual, real)
        return actual

    def olvidar(self):
        self._ls.clear()


def tiene_sistema(raiz):
    """Esa carpeta parece la particion de arranque de una tarjeta (para elegir entre varias unidades)."""
    tj = Tarjeta(raiz)
    return any(tj.buscar(f) for f in ("NEXTOR.SYS", "MSXDOS2.SYS", "COMMAND2.COM", NOMBRE_MARCA) + tuple(BIOS_OCM))


def elegir_arranque(carpetas):
    """De varias unidades de una tarjeta, las que tienen sistema: [(ruta, True|False)] en el mismo orden."""
    return [(c, tiene_sistema(c)) for c in carpetas if os.path.isdir(c)]


# ------------------------------------------------------------------ la marca SDMAKER.INF
def _opciones_texto(opciones):
    o = contenido.opciones_n3(opciones)
    return "yenslash=%d,bufinsert=%d,dirk=%s,btm=%d" % (o["yenslash"], o["bufinsert"], o["dirk"], o["btm"])


def texto_marca(ficheros, maquina, sistema, grupos, particiones, opciones):
    """SDMAKER.INF (ASCII, CRLF): quien hizo la tarjeta, como, y el sha1 de cada fichero escrito (ruta: sha1)."""
    L = ["MSX SD Maker", "VERSION=" + VERSION, "MAQUINA=" + maquina, "SISTEMA=" + sistema,
         "GRUPOS=" + ",".join(sorted(grupos)), "PARTICIONES=%d" % particiones, "OPCIONES=" + _opciones_texto(opciones),
         "[ficheros]"]
    L += ["%s %s" % (sha, ruta.replace("/", "\\")) for ruta, sha in sorted(ficheros.items())]
    return ("\r\n".join(L) + "\r\n").encode("ascii", "replace")


def leer_marca(tj):
    """dict con las claves de SDMAKER.INF en mayusculas y "ficheros" {RUTA: sha1}; None si no hay marca."""
    ruta = tj.buscar(NOMBRE_MARCA)
    if not ruta:
        return None
    try:
        texto = _leer(ruta).decode("ascii", "replace")
    except OSError:
        return None
    m = {"ficheros": {}}
    en_ficheros = False
    for linea in texto.splitlines():
        linea = linea.strip()
        if linea.lower() == "[ficheros]":
            en_ficheros = True
        elif en_ficheros:
            sha, _, r = linea.partition(" ")
            if len(sha) == 40 and r:
                m["ficheros"][_k(r)] = sha
        elif "=" in linea:
            k, _, v = linea.partition("=")
            m[k.strip().upper()] = v.strip()
    return m


def _sha_arbol(raiz):
    """{ruta: sha1} de todos los ficheros de un arbol de fatfs.Nodo (menos la propia marca)."""
    out = {}

    def rec(n, pre):
        for h in n.hijos:
            if h.es_dir:
                rec(h, pre + h.nombre + "/")
            elif (pre + h.nombre).upper() != NOMBRE_MARCA:
                out[pre + h.nombre] = sha1(h.leer())
    rec(raiz, "")
    return out


def poner_marca(raiz, maquina, sistema, grupos, particiones, opciones):
    """Mete SDMAKER.INF en el arbol de una tarjeta nueva (proceso.crear), con el sha1 de lo que lleva."""
    contenido.meter_datos(raiz, NOMBRE_MARCA, texto_marca(_sha_arbol(raiz), maquina, sistema, grupos, particiones,
                                                          opciones))


# ------------------------------------------------------------------ detectar el sistema
NOMBRES_SISTEMA = {"nextor214": "c.sistema.nextor214", "nextor3": "c.sistema.nextor3",
                   "nextor3beta2": "c.sistema.nextor3beta2", "nextor3beta1": "ac.sistema.nextor3beta1",
                   "msxdos": "c.sistema.msxdos", "otro": "ac.sistema.otro", CONSERVAR: "ac.sistema.conservar"}


def texto_sistema(clave, extra=""):
    return t(NOMBRES_SISTEMA.get(clave, "ac.sistema.otro"), extra) if clave == "otro" else t(NOMBRES_SISTEMA[clave])


def _clave_version(version, beta):
    """'2.1.4' / '3.0' (+ beta) -> nextor214, nextor3, nextor3beta2, nextor3beta1 o None."""
    if version.startswith("2."):
        return "nextor214"
    if version.startswith("3."):
        return "nextor3" if not beta else "nextor3beta%s" % beta
    return None


def clave_nextor_sys(datos):
    """Sistema de un NEXTOR.SYS: por su huella o por la version que lleva escrita. None si no se sabe."""
    clave = huellas.SISTEMA.get(sha1(datos)[:12])
    if clave:
        return clave
    m = re.search(rb"NEXTOR\.SYS version (\d+\.\d+(?:\.\d+)?)(?: beta (\d+))?", datos)
    return _clave_version(m.group(1).decode(), m.group(2) and m.group(2).decode()) if m else None


def clave_disco(datos):
    """Sistema del bloque DISK de una BIOS del OCM (primeros 128 KB): por la cadena del kernel; None si no hay Nextor."""
    m = re.search(rb"Nextor kernel version (\d+\.\d+(?:\.\d+)?)(?: beta (\d+))?", datos[:128 * 1024])
    return _clave_version(m.group(1).decode(), m.group(2) and m.group(2).decode()) if m else None


def _version_n(clave):
    return {"nextor214": 2}.get(clave, 3 if clave and clave.startswith("nextor3") else None)


def _detectar_sistema(tj):
    """(clave, extra): nextor214, nextor3, nextor3beta2, nextor3beta1, msxdos, otro (extra = lo que lleva) o None."""
    p = tj.buscar("NEXTOR.SYS")
    if p:
        clave = clave_nextor_sys(_leer(p))
        if clave:
            return clave, ""
        m = re.search(rb"NEXTOR\.SYS version ([ -~]{1,20})", _leer(p))
        return "otro", ("NEXTOR.SYS " + m.group(1).decode().strip()) if m else "NEXTOR.SYS"
    if tj.buscar("MSXDOS2.SYS") and tj.buscar("COMMAND2.COM"):
        return "msxdos", ""
    return None, ""


# ------------------------------------------------------------------ lineas conocidas (AUTOEXEC, MMRET)
_FIJAS = {}


def _lineas_autoexec_conocidas(raiz_sd):
    """Todas las lineas que contenido.autoexec puede escribir (menos PATH y MAPDRV, que se miran por su forma)."""
    clave = raiz_sd or ""
    if clave not in _FIJAS:
        todos = {g[0] for g in contenido.GRUPOS}
        lineas = set()
        for sistema in ("nextor214", "nextor3", "msxdos"):
            raiz = contenido.arbol(sistema, todos, 1, raiz_sd)
            for grupos in (todos, set()):
                for n in (1, 3):
                    for o in (None, {"yenslash": False, "bufinsert": True, "dirk": "0"}):
                        for maq in ("fpga", "ocm"):
                            for arranque in (True, False):
                                texto = contenido.autoexec(sistema, grupos, n, raiz, o, maq, arranque)
                                lineas.update(l.strip().lower() for l in texto.decode("ascii").strip("\x1a").splitlines())
        _FIJAS[clave] = lineas
    return _FIJAS[clave]


_RE_PATH = re.compile(r"^path\s+(a:\\|%1\\)[^;]*(;(a:\\|%1\\)[^;]*)*$")
_RE_MAPDRV = re.compile(r"^mapdrv [b-i]: [2-8] 1 (0|3-2)$")
_RE_ECO = re.compile(r"^echo (maped units [a-i](,[a-i])*|partitions 2-\d: .*)$")


def es_autoexec_nuestro(datos, raiz_sd=None):
    """Todas las lineas son de las que escribe este programa (de cualquier version)."""
    fijas = _lineas_autoexec_conocidas(raiz_sd)
    for linea in datos.decode("latin-1").strip("\x1a").splitlines():
        l = linea.strip().lower()
        if l and l not in fijas and not (_RE_PATH.match(l) or _RE_MAPDRV.match(l) or _RE_ECO.match(l)):
            return False
    return True


def es_mmret_nuestro(datos, raiz_sd=None):
    """Todas sus lineas estan en algun MMRET.DAT publicado (el ajustado solo quita lineas)."""
    conocidas = set(huellas.LINEAS_MMRET.split())
    try:
        conocidas.update(sha1(l)[:8] for l in _leer(os.path.join(raiz_sd or contenido.carpeta_sd(), "base", "MM",
                                                                 "MMRET.DAT")).split(b"\n"))
    except OSError:
        pass
    return all(not l or sha1(l)[:8] in conocidas for l in datos.split(b"\n"))


# ------------------------------------------------------------------ huellas
_TABLA = {}


def conocidas(ruta):
    """{sha12: mascara} de las versiones publicadas de ese fichero."""
    if not _TABLA:
        for r, texto in huellas.FICHEROS.items():
            _TABLA[r] = {p.split(":")[0]: int(p.split(":")[1], 16) for p in texto.split()}
    return _TABLA.get(_k(ruta), {})


def nombre_release(i):
    return huellas.TAGS[i] if i < len(huellas.TAGS) else "v" + VERSION


def release_de(entradas):
    """Textos de las versiones del SD Maker cuyo contenido mas se parece al de la tarjeta, o ""."""
    puntos = [0] * (len(huellas.TAGS) + 1)
    for e in entradas:
        if e.sha_actual and not e.generado:
            m = conocidas(e.ruta).get(e.sha_actual[:12], 0)
            for i in range(len(puntos)):
                if m >> i & 1:
                    puntos[i] += 1
    mejor = max(puntos)
    if not mejor:
        return ""
    idx = [i for i, p in enumerate(puntos) if p == mejor]
    return nombre_release(idx[0]) if len(idx) == 1 else "%s - %s" % (nombre_release(idx[0]), nombre_release(idx[-1]))


# ------------------------------------------------------------------ el plan
class Entrada:
    """Un fichero de la tarjeta: ruta (con "/", como se escribira), estado, grupo, y de donde sale lo nuevo."""

    def __init__(self, ruta, estado, grupo, nodo=None, real=None, sha_nueva=None, sha_actual=None):
        self.ruta, self.estado, self.grupo, self.nodo, self.real = ruta, estado, grupo, nodo, real
        self.sha_nueva, self.sha_actual = sha_nueva, sha_actual
        self.forzar = False
        self.obligatorio = False    # NEXTOR.SYS al cambiar de Nextor: no se puede desmarcar
        self.generado = False
        self.alt = None             # generados: nombre con el que se deja el nuevo si el usuario cambio el suyo
        self.alt_ok = False         # ... y ya esta ahi
        self.mtime = nodo.mtime if nodo is not None else None
        self._tam = None

    def datos(self):
        return self.nodo.leer()

    @property
    def tam(self):
        if self._tam is None:
            self._tam = len(self.datos()) if self.nodo is not None else 0
        return self._tam


def _recorrer(raiz):
    """({ruta: Nodo} de ficheros, [ruta de carpeta]) de un arbol de fatfs.Nodo."""
    ficheros, carpetas = {}, []

    def rec(n, pre):
        for h in n.hijos:
            if h.es_dir:
                carpetas.append(pre + h.nombre)
                rec(h, pre + h.nombre + "/")
            else:
                ficheros[pre + h.nombre] = h
    rec(raiz, "")
    return ficheros, carpetas


def _redondeo(n):
    return (n + CLUSTER - 1) // CLUSTER * CLUSTER


class Plan:
    """Lo detectado en la tarjeta y lo que se haria. Se puede cambiar (destino aparte, que va en analizar) con
    anadir_grupo() y forzar(); acciones() es lo que aplicar() escribe."""

    def __init__(self, tj):
        self.tj = tj
        self.raiz = tj.raiz
        self.maquina = "fpga"
        self.marca = None
        self.actual = (None, "")            # (clave, extra): el sistema que lleva
        self.destino = CONSERVAR
        self.ofrecidos = []                 # sistemas a los que se puede cambiar
        self.recomendado = None
        self.entradas = []                  # los ficheros de lo nuevo, con su estado (sin los generados)
        self.carpetas = []                  # [(ruta, grupo)]
        self.presentes = set()
        self.ausentes = []
        self.anadir = set()
        self.avisos = []
        self.release = ""
        self.fs = None
        self.particiones = 1
        self.opciones = None
        self.pack = None
        self.raiz_sd = None
        self.ocm = None                     # OCM: dict con la BIOS activa y las demas
        self.confirmado = False
        self.libre = None
        self.generar = False
        self.sin_uso = []
        self._gen = {}
        self._arboles = {}
        self.lista_grupos = []
        self.sistema_gen = "ninguno"        # el sistema con el que se hace el arbol de referencia

    # --- lo que se escribira
    def grupos_efectivos(self):
        return set(self.presentes) | set(self.anadir)

    def anadir_grupo(self, clave, si=True):
        if clave not in self.ausentes:
            raise ValueError(clave)
        (self.anadir.add if si else self.anadir.discard)(clave)

    def forzar(self, ruta, si=True):
        e = self.por_ruta(ruta)
        if e is None or e.estado != CAMBIADO:
            raise ValueError(ruta)
        e.forzar = si or e.obligatorio

    def por_ruta(self, ruta):
        for e in self.entradas + self.generados():
            if _k(e.ruta) == _k(ruta):
                return e
        return None

    def arbol(self, grupos):
        """El arbol que llevaria una tarjeta nueva con el sistema de destino y esos grupos (lo generan contenido.arbol)."""
        clave = frozenset(grupos)
        if clave not in self._arboles:
            sistema = self.sistema_gen
            ocm_ = None
            if self.maquina == "ocm" and sistema != "ninguno":
                ocm_ = {"pack": self.pack, "versiones": self.ocm["versiones"], "sistema": sistema}
            self._arboles[clave] = contenido.arbol(sistema, grupos, self.particiones, self.raiz_sd, self.opciones, ocm_)
        return self._arboles[clave]

    def generados(self):
        """AUTOEXEC.BAT / .BTM, REBOOT.BAT (OCM) y MM\\MMRET.DAT para los grupos que habra: como los haria una tarjeta
        nueva. Si el usuario cambio el suyo, se queda (el AUTOEXEC nuevo, como .NEW)."""
        clave = frozenset(self.grupos_efectivos())
        if clave in self._gen:
            return self._gen[clave]
        out = []
        if self.generar:
            raiz = self.arbol(clave)
            marca = (self.marca or {}).get("ficheros", {})
            for ruta in ("AUTOEXEC.BAT", "AUTOEXEC.BTM", "REBOOT.BAT", "MM/MMRET.DAT"):
                nodo = raiz
                for p in ruta.split("/"):
                    nodo = nodo.hijo(p) if nodo is not None else None
                if nodo is None:
                    continue
                datos = nodo.leer()
                real = self.tj.buscar(ruta)
                e = Entrada(nodo.nombre if "/" not in ruta else ruta, ANADIR, "mm" if "MMRET" in ruta else "sistema",
                            nodo, real, sha1(datos))
                e.generado = True
                if real is not None:
                    actual = _leer(real)
                    e.sha_actual = sha1(actual)
                    if e.sha_actual == e.sha_nueva:
                        e.estado = IGUAL
                    elif _k(ruta) in marca:
                        e.estado = ACTUALIZAR if marca[_k(ruta)] == e.sha_actual else CAMBIADO
                    elif ruta == "MM/MMRET.DAT":
                        e.estado = ACTUALIZAR if es_mmret_nuestro(actual, self.raiz_sd) else CAMBIADO
                    else:
                        e.estado = ACTUALIZAR if es_autoexec_nuestro(actual, self.raiz_sd) else CAMBIADO
                    if e.estado == CAMBIADO and ruta != "MM/MMRET.DAT":
                        e.alt = ruta.rsplit(".", 1)[0] + ".NEW"
                        otro = self.tj.buscar(e.alt)
                        e.alt_ok = bool(otro) and sha1(_leer(otro)) == e.sha_nueva
                out.append(e)
        self._gen[clave] = out
        return out

    def _activa(self, e):
        return e.grupo == "sistema" or e.grupo in self.grupos_efectivos()

    def acciones(self):
        """[(Entrada, modo)] que escribira aplicar(): modo "escribir", "forzar" (con copia .BAK) o "alt" (al lado)."""
        out = []
        for e in self.entradas + self.generados():
            if e.estado in (ACTUALIZAR, ANADIR) and (e.estado == ACTUALIZAR or self._activa(e)):
                out.append((e, "escribir"))
            elif e.estado == CAMBIADO:
                if e.forzar:
                    out.append((e, "forzar"))
                elif e.alt and not e.alt_ok:
                    out.append((e, "alt"))
        return out

    def dejados(self):
        """Las entradas «cambiado por el usuario» que no se tocan."""
        return [e for e in self.entradas + self.generados() if e.estado == CAMBIADO and not e.forzar]

    def carpetas_nuevas(self):
        return [r for r, g in self.carpetas if (g == "sistema" or g in self.grupos_efectivos())
                and self.tj.buscar(r) is None]

    def bios_a_cambiar(self):
        """(ruta real del OCM-BIOS.DA?, bytes del nuevo bloque DISK) o None."""
        if self.maquina != "ocm" or not self.ocm or not self.ocm.get("disco_nuevo"):
            return None
        return self.ocm["ruta"], self.ocm["disco_nuevo"]

    def bytes_necesarios(self):
        n = sum(_redondeo(e.tam) + (_redondeo(os.path.getsize(e.real)) if m == "forzar" else 0)
                for e, m in self.acciones())
        n += CLUSTER * len(self.carpetas_nuevas()) + _redondeo(1 << 16)     # + la marca
        return n + MARGEN

    def cabe(self):
        return self.libre is None or self.bytes_necesarios() <= self.libre

    def hay_trabajo(self):
        return bool(self.acciones() or self.bios_a_cambiar() or self.carpetas_nuevas())

    def cambia_sistema(self):
        """Cambia el NEXTOR.SYS o el sistema de una tarjeta de MSXimus / MSXnano (hay que tener flasheado su pack)."""
        if self.maquina != "fpga" or self.destino == CONSERVAR:
            return False
        if self.destino != self.actual[0]:
            return True
        return any(e.ruta.upper() == "NEXTOR.SYS" and m != "alt" for e, m in self.acciones())

    def confirmacion(self):
        """Texto de la confirmacion OBLIGATORIA antes de aplicar, o None."""
        if self.cambia_sistema():
            n = texto_sistema(self.destino).split(" (")[0]
            return t("ac.confirma_pack", n, n, n)
        return None

    def reinicio_ocm(self):
        return self.bios_a_cambiar() is not None

    def resumen(self):
        """{estado: [entradas]} (con los generados)."""
        out = {e: [] for e in ESTADOS}
        for e in self.entradas + self.generados():
            out[e.estado].append(e)
        return out

    def texto(self):
        """El plan en texto (para la linea de ordenes)."""
        r = self.resumen()
        L = [t("ac.t.maquina", t(contenido.MAQUINAS[self.maquina])),
             t("ac.t.sistema", texto_sistema(self.actual[0], self.actual[1]) if self.actual[0] else t("ac.sin_sistema"))]
        if self.marca:
            L.append(t("ac.t.marca", self.marca.get("VERSION", "?")))
        if self.release:
            L.append(t("ac.t.release", self.release))
        if self.fs:
            L.append(t("ac.t.fs", self.fs))
        L.append(t("ac.t.libre", idioma_mb(self.libre), idioma_mb(self.bytes_necesarios())) if self.libre is not None
                 else t("ac.t.necesario", idioma_mb(self.bytes_necesarios())))
        L.append(t("ac.t.destino", texto_sistema(self.destino)))
        L.append(t("ac.t.presentes", ", ".join(self.presentes_texto()) or "-"))
        for a in self.avisos:
            L.append("  ! " + a)
        if self.recomendado and self.destino != self.recomendado:
            L.append("  * " + t("ac.av.beta_a_final"))
        for estado, clave in ((ACTUALIZAR, "ac.t.actualizar"), (ANADIR, "ac.t.anadir"), (CAMBIADO, "ac.t.cambiado"),
                              (SIN_USO, "ac.t.sin_uso"), (CONFIG, "ac.t.config")):
            lista = [e for e in r[estado] if estado != ANADIR or self._activa(e)]
            if lista:
                L.append(t(clave, len(lista)))
                L += ["    " + e.ruta + (" -> " + e.alt if e.alt and not e.forzar else "") for e in lista[:200]]
        nuevos = [e for e in r[ANADIR] if not self._activa(e)]
        if nuevos:
            L.append(t("ac.t.no_lleva", ", ".join("%s (%d)" % (g, sum(1 for e in nuevos if e.grupo == g))
                                                 for g in self.ausentes if any(e.grupo == g for e in nuevos))))
        if not self.hay_trabajo():
            L.append(t("ac.t.nada" if self.presentes or self.actual[0] else "ac.t.vacia"))
        return "\n".join(L)

    def presentes_texto(self):
        return [g for g in self.lista_grupos if g in self.presentes]


def texto_grupo(clave):
    """El nombre de un grupo de programas (el de la casilla de la ventana principal)."""
    return t({g[0]: g[1] for g in contenido.GRUPOS + contenido.GRUPOS_OCM}[clave])


def idioma_mb(n):
    return idioma.decimal("%.1f MB" % (n / (1 << 20)))


# ------------------------------------------------------------------ analizar
def _detectar_fs(raiz):
    try:
        from . import dispositivos
        return dispositivos.sistema_de_ficheros(raiz)
    except Exception:
        return None


def _opciones_de_autoexec(tj, sistema, actual):
    """Las opciones de Nextor 3 que ya tiene el AUTOEXEC.BAT / .BTM de la tarjeta (si ya era de Nextor 3; si no, las de
    siempre)."""
    o = dict(contenido.OPCIONES_N3)
    if not (sistema or "").startswith("nextor3") or not (actual or "").startswith("nextor3"):
        return o
    bat, btm = tj.buscar("AUTOEXEC.BAT"), tj.buscar("AUTOEXEC.BTM")
    p = btm or bat
    o["btm"] = bool(btm)
    if p:
        lineas = [l.strip().lower() for l in _leer(p).decode("latin-1").splitlines()]
        o["yenslash"] = "yenslash on" in lineas
        o["bufinsert"] = "set bufinsert=on" in lineas
        o["dirk"] = "0" if "set dirk=0" in lineas else ""
    return o


def _particiones_de(tj, marca):
    """Cuantas particiones tiene la tarjeta: la marca, o las unidades que monta su AUTOEXEC; 1 si no se sabe."""
    if marca and marca.get("PARTICIONES", "").isdigit():
        return max(1, int(marca["PARTICIONES"]))
    p = tj.buscar("AUTOEXEC.BAT") or tj.buscar("AUTOEXEC.BTM")
    if p:
        texto = _leer(p).decode("latin-1")
        n = [int(x) for x in re.findall(r"(?im)^\s*mapdrv\s+\w:\s+(\d+)", texto)]
        if n:
            return max(n)
        m = re.search(r"(?i)partitions 2-(\d+)", texto)
        if m:
            return int(m.group(1))
    return 1


def _grupo_de(ruta, tops):
    return tops.get(ruta.split("/")[0].upper(), "sistema")


def _ocm_estado(plan, pack):
    """Las BIOS de una tarjeta OCM: la activa y las alternativas, con su Nextor."""
    tj = plan.tj
    activa = next((n for n in BIOS_OCM if tj.buscar(n)), None)
    info = {"ruta": tj.buscar(activa) if activa else None, "nombre": activa, "clave": None, "alts": [],
            "disco_nuevo": None, "versiones": []}
    if info["ruta"]:
        with open(info["ruta"], "rb") as f:
            info["clave"] = clave_disco(f.read(128 * 1024))
    for n in ALT_OCM:
        p = tj.buscar(n)
        if p:
            with open(p, "rb") as f:
                info["alts"].append((n, clave_disco(f.read(128 * 1024))))
    return info


def _huellas_pack(pack):
    """{ruta en la tarjeta (clave de _k): {sha1}} de lo que trae el pack de KdL, con Nextor 2 y con Nextor 3: una tarjeta
    OCM lleva esos ficheros, que no estan en huellas.py, y no son cambios del usuario."""
    out = {}

    def anotar(ruta, datos):
        out.setdefault(_k(ruta), set()).add(sha1(datos))
    for n, d, _ in pack.carpeta("make/sdcreate/os"):
        anotar(n, d)
        if n.upper() == "NEXTOR.SYS":
            anotar("N2XTOR.SYS", d)
    for sub, top in (("help", "HELP"), ("utils", "UTILS")):
        for n, d, _ in pack.carpeta("make/sdcreate/" + sub):
            anotar(top + "/" + n, d)
    for ruta, (d, _) in pack.n3xtor().items():
        anotar(ruta, d)
        if ruta.upper() in ("NEXTOR.SYS", "N3XTOR.SYS"):
            anotar("NEXTOR.SYS", d)
            anotar("N3XTOR.SYS", d)
    return out


def _discos_del_pack(pack):
    """{clave de sistema: disco} de los Nextor del pack (nextor214 -> nextor214, nextor3 -> nextor3 o su beta)."""
    out = {}
    for disco in ("nextor214", "nextor3"):
        if disco in getattr(pack, "nucleos", {}):
            try:
                clave = clave_disco(pack.rom(pack.nucleos[disco][0]))
            except ValueError:
                continue
            if clave and clave not in out:
                out[clave] = disco
    return out


def analizar(raiz, sistema=None, anadir=(), forzar=(), maquina=None, pack=None, particiones=None, raiz_sd=None,
             fs=None, aviso=None):
    """Mira la tarjeta (la carpeta raiz) y devuelve el Plan; no escribe nada. sistema = nextor214, nextor3,
    nextor3beta2, msxdos o conservar (por defecto, el que lleva); anadir = grupos que no lleva y se quieren; forzar =
    rutas «cambiadas por el usuario» que se quieren pisar (con copia .BAK); pack = el OCM-SDBIOS Pack (ocm.Pack)."""
    aviso = aviso or (lambda texto, fraccion=None: None)
    if not os.path.isdir(raiz):
        raise ErrorActualizar(t("ac.err.no_carpeta", raiz))
    tj = Tarjeta(raiz)
    plan = Plan(tj)
    plan.pack, plan.raiz_sd = pack, raiz_sd or contenido.carpeta_sd()
    plan.marca = leer_marca(tj)
    plan.fs = fs if fs is not None else _detectar_fs(raiz)
    if plan.fs and plan.fs.upper() not in ("FAT", "FAT16", "FAT12"):
        plan.avisos.append(t("ac.av.fat32", plan.fs) if plan.fs.upper() == "FAT32" else t("ac.av.otro_fs", plan.fs))
    hay_ocm = any(tj.buscar(n) for n in BIOS_OCM + ALT_OCM)
    plan.maquina = maquina or ("ocm" if hay_ocm else (plan.marca or {}).get("MAQUINA") or "fpga")
    ocm_ = plan.maquina == "ocm"

    # --- el sistema que lleva y al que se va
    aviso(t("ac.analizando"), 0.05)
    if ocm_:
        plan.ocm = _ocm_estado(plan, pack)
        clave = plan.ocm["clave"]
        plan.actual = (clave, "") if clave else (None, "")
        if not plan.ocm["ruta"]:
            plan.avisos.append(t("ac.av.sin_bios"))
        elif not clave:
            plan.avisos.append(t("ac.av.bios_sin_nextor"))
        discos = _discos_del_pack(pack) if pack is not None else {}
        plan.ofrecidos = list(discos) if clave else []
        if pack is None:
            plan.avisos.append(t("ac.av.sin_pack"))
    else:
        clave, extra = _detectar_sistema(tj)
        plan.actual = (clave, extra)
        plan.ofrecidos = list(FPGA_SISTEMAS)
        discos = {}
    if plan.actual[0] is None:
        plan.avisos.append(t("ac.av.sin_sistema"))
    elif plan.actual[0] == "otro":
        plan.avisos.append(t("ac.av.sistema_raro"))
    if sistema is None:
        sistema = plan.actual[0] if plan.actual[0] in plan.ofrecidos else CONSERVAR
    if sistema != CONSERVAR and sistema not in plan.ofrecidos:
        raise ErrorActualizar(t("ac.err.destino", sistema))
    plan.destino = sistema
    if plan.actual[0] in ("nextor3beta1", "nextor3beta2") and ("nextor3" in plan.ofrecidos):
        plan.recomendado = "nextor3"

    plan.opciones = _opciones_de_autoexec(tj, sistema if sistema != CONSERVAR else plan.actual[0], plan.actual[0])
    plan.particiones = particiones or _particiones_de(tj, plan.marca)
    plan.lista_grupos = [g[0] for g in contenido.grupos_de(plan.maquina)]

    # --- lo que llevaria una tarjeta nueva con ese destino
    todos = set(plan.lista_grupos)
    if sistema != CONSERVAR:
        plan.sistema_gen = sistema
    else:                       # el sistema no se toca, pero AUTOEXEC y MMRET se hacen para el que lleva
        plan.sistema_gen = plan.actual[0] if plan.actual[0] in SISTEMAS_GEN and not ocm_ else "ninguno"
    if ocm_:
        versiones = []
        if sistema != CONSERVAR:
            versiones.append(_version_n(sistema))
            versiones += [v for v in (_version_n(c) for _, c in plan.ocm["alts"]) if v and v not in versiones]
        plan.ocm["versiones"] = versiones
        if pack is None or sistema == CONSERVAR:
            plan.sistema_gen = "ninguno"
        elif plan.ocm["ruta"] and plan.actual[0] and sistema != plan.actual[0]:
            plan.ocm["disco_nuevo"] = pack.rom(pack.nucleos[discos[sistema]][0], 128 * 1024)
    plan.generar = plan.sistema_gen != "ninguno"
    ficheros, carpetas = _recorrer(plan.arbol(todos))
    for g in GENERADOS:
        for r in [r for r in ficheros if r.upper() == g]:
            del ficheros[r]
    tops = {}
    for clave_g, _, origenes, _, vacias in contenido.grupos_de(plan.maquina):
        for o in origenes:
            tops[os.path.basename(o).upper()] = clave_g
        for v in vacias:
            tops[v.upper()] = clave_g

    def grupo(ruta):
        if ocm_ and ruta.upper() in ("UTILS/" + f for f in FLASH):
            return "flash"
        return _grupo_de(ruta, tops)

    def del_plan(g):            # lo que se mira: los grupos de esta maquina y, si se toca, el sistema
        return g in todos or (g == "sistema" and sistema != CONSERVAR)
    ficheros = {r: n for r, n in ficheros.items() if del_plan(grupo(r))}
    carpetas = [r for r in carpetas if del_plan(grupo(r + "/x"))]

    # --- cada fichero
    aviso(t("ac.leyendo"), 0.15)
    marca = (plan.marca or {}).get("ficheros", {})
    del_pack = _huellas_pack(pack) if ocm_ and pack is not None else {}
    # al cambiar de Nextor, el NEXTOR.SYS y el COMMAND3.COM tienen que cambiar con el: si no, la maquina se queda en BASIC
    cambia_nextor = sistema != CONSERVAR and sistema != plan.actual[0] and _version_n(sistema) is not None
    n = max(1, len(ficheros))
    for i, (ruta, nodo) in enumerate(sorted(ficheros.items(), key=lambda x: x[0].upper())):
        if i % 40 == 0:
            aviso(t("ac.leyendo"), 0.15 + 0.7 * i / n)
        nuevo = nodo.leer()
        e = Entrada(ruta, ANADIR, grupo(ruta), nodo, tj.buscar(ruta), sha1(nuevo))
        if e.real is not None:
            if os.path.isdir(e.real):
                plan.avisos.append(t("ac.av.carpeta_en_medio", ruta))
                continue
            e.sha_actual = sha1(_leer(e.real))
            k = _k(ruta)
            conocida = conocidas(ruta)
            marcada = marca.get(k) == e.sha_actual
            antigua = marcada or e.sha_actual[:12] in conocida or e.sha_actual in del_pack.get(k, ())
            if e.sha_actual == e.sha_nueva:
                e.estado = IGUAL
            elif k in CONFIG_USUARIO or k.startswith(CONFIG_PREFIJOS):
                e.estado = CONFIG
            elif antigua:
                e.estado = ACTUALIZAR
            elif k in CONFIG_SI_DIFIERE:
                e.estado = CONFIG
            else:
                e.estado = CAMBIADO
                if cambia_nextor and k in OBLIGATORIOS:     # se sustituye siempre, con su copia .BAK
                    e.forzar = e.obligatorio = True
        plan.entradas.append(e)
    for ruta, g in sorted(((r, grupo(r + "/x")) for r in carpetas), key=lambda x: x[0].upper()):
        plan.carpetas.append((ruta, g))

    # --- grupos que lleva y que no
    vistos = {}
    for e in plan.entradas:
        if e.grupo != "sistema":
            vistos.setdefault(e.grupo, False)
            vistos[e.grupo] = vistos[e.grupo] or e.real is not None
    plan.presentes = {g for g, v in vistos.items() if v}
    plan.ausentes = [g for g in plan.lista_grupos if g not in plan.presentes]
    for g in anadir:
        if g not in plan.ausentes:
            raise ErrorActualizar(t("ac.err.grupo", g, ", ".join(plan.ausentes) or "-"))
        plan.anadir.add(g)

    # --- lo nuestro que ya no se usa: huellas conocidas (cualquier version) y lo que la marca dice que se escribio
    esperados = {_k(e.ruta) for e in plan.entradas} | set(GENERADOS)
    candidatas = {r: None for r in huellas.FICHEROS}
    candidatas.update({k: sha for k, sha in marca.items() if k != NOMBRE_MARCA and not _es_bios(k)})
    for ruta, sha_marca in candidatas.items():
        if ruta in esperados or not del_plan(_grupo_de(ruta, tops)):
            continue
        real = tj.buscar(ruta)
        if real is None or os.path.isdir(real):
            continue
        sha = sha1(_leer(real))
        if sha[:12] in conocidas(ruta) or sha == sha_marca:
            plan.entradas.append(Entrada(ruta, SIN_USO, _grupo_de(ruta, tops), real=real, sha_actual=sha))

    # --- forzar
    for r in forzar:
        e = plan.por_ruta(r)
        if e is None or e.estado != CAMBIADO:
            raise ErrorActualizar(t("ac.err.forzar", r))
        e.forzar = True

    plan.release = release_de(plan.entradas)
    plan.libre = _libre(raiz)
    if not plan.cabe():
        plan.avisos.append(t("ac.av.sin_sitio", idioma_mb(plan.bytes_necesarios()), idioma_mb(plan.libre)))
    aviso(t("ac.analizado"), 1.0)
    return plan


def _es_bios(k):
    """Lo que escribe proceso.crear en una tarjeta OCM y que aqui no se toca: las BIOS y BIOS.TXT."""
    return k.startswith(("OCM-BIOS.", "ALT-BIOS.")) or k == "BIOS.TXT"


def _libre(raiz):
    try:
        return shutil.disk_usage(raiz).free
    except OSError:
        return None


# ------------------------------------------------------------------ aplicar
class Informe:
    def __init__(self):
        self.actualizados, self.anadidos, self.forzados, self.alternativos = [], [], [], []
        self.dejados, self.sin_uso, self.errores, self.copias, self.carpetas = [], [], [], [], []
        self.bios = None
        self.reinicio = False
        self.segundos = 0

    def texto(self):
        L = [t("ac.i.resumen", len(self.actualizados) + len(self.forzados), len(self.anadidos), len(self.dejados),
               len(self.errores))]
        for clave, lista in (("ac.i.actualizados", self.actualizados), ("ac.i.anadidos", self.anadidos),
                             ("ac.i.forzados", self.forzados), ("ac.i.alternativos", self.alternativos),
                             ("ac.i.dejados", self.dejados), ("ac.i.sin_uso", self.sin_uso),
                             ("ac.i.copias", self.copias)):
            if lista:
                L.append(t(clave, len(lista)))
                L += ["    " + x for x in lista[:100]]
        if self.bios:
            L.append(t("ac.i.bios", self.bios))
        for e in self.errores:
            L.append("ERROR: " + e)
        if self.reinicio:
            L.append(t("ac.i.reinicio"))
        return "\n".join(L)


def _nombre_copia(tj, real):
    """Nombre libre para la copia de seguridad: MM.COM -> MM.BAK, y si existe, MM.BA1, MM.BA2... (ocupado = ni mayusculas)."""
    carpeta, nombre = os.path.split(real)
    base = os.path.splitext(nombre)[0]
    existentes = {n.upper() for n in os.listdir(carpeta)}
    for ext in ["BAK"] + ["BA%d" % i for i in range(1, 10)] + ["B%d" % i for i in range(10, 100)]:
        if (base + "." + ext).upper() not in existentes:
            return os.path.join(carpeta, base + "." + ext)
    raise ErrorActualizar(t("ac.err.sin_nombre_copia", nombre))


def _destino(tj, e, modo):
    """Ruta real donde va el fichero: el que ya hay (con su nombre), o uno nuevo con las carpetas que falten."""
    if modo != "alt" and e.real is not None:
        return e.real
    carpeta, _, nombre = e.ruta.rpartition("/")
    nombre = e.alt if modo == "alt" else nombre
    existente = tj.buscar((carpeta + "/" if carpeta else "") + nombre)
    return existente or os.path.join(tj.asegurar_carpeta(carpeta) if carpeta else tj.raiz, nombre)


def _escribir_seguro(tj, destino, datos, sha, mtime=None, copia=False):
    """Escribe datos en destino (ruta real, existente o no): a un temporal corto en la misma carpeta, fsync, se relee y
    compara el sha1 y se pone en su sitio con os.replace. Si algo falla, borra el temporal y deja el original. Con
    copia=True, antes guarda el que haya como .BAK."""
    carpeta = os.path.dirname(destino)
    tmp = os.path.join(carpeta, TEMPORAL)
    try:
        with open(tmp, "wb") as f:
            f.write(datos)
            f.flush()
            os.fsync(f.fileno())
        if sha1(_leer(tmp)) != sha:
            raise OSError(t("ac.err.no_coincide", os.path.basename(destino)))
        if mtime and mtime > 315532800:
            os.utime(tmp, (mtime, mtime))
        bak = None
        if os.path.exists(destino):
            if copia:
                bak = _nombre_copia(tj, destino)
                shutil.copy2(destino, bak)
            os.chmod(destino, stat.S_IREAD | stat.S_IWRITE)        # solo lectura: que se pueda sustituir
        os.replace(tmp, destino)
        return bak
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _quitar_appledouble(destino):
    """Borra el ._NOMBRE que macOS haya creado para un fichero que acabamos de escribir (y el del temporal)."""
    carpeta = os.path.dirname(destino)
    for nombre in (os.path.basename(destino), TEMPORAL):
        p = os.path.join(carpeta, "._" + nombre)
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def aplicar(plan, aviso=None, appledouble=None, carpeta_copias=None):
    """Escribe lo que dice el plan. Antes: la confirmacion obligatoria (plan.confirmado) y el sitio; despues, relee y
    compara todo lo escrito. Un fallo en un fichero deja el que habia y se anota en informe.errores; los demas siguen."""
    aviso = aviso or (lambda texto, fraccion=None: None)
    appledouble = sys.platform == "darwin" if appledouble is None else appledouble
    texto = plan.confirmacion()
    if texto and not plan.confirmado:
        raise SinConfirmar(texto)
    libre = _libre(plan.raiz)           # el sitio que hay AHORA (por si ha cambiado desde el analisis)
    if libre is not None:
        plan.libre = libre if plan.libre is None else min(plan.libre, libre)
    if not plan.cabe():
        raise SinSitio(t("ac.av.sin_sitio", idioma_mb(plan.bytes_necesarios()), idioma_mb(plan.libre)))
    t0 = time.time()
    tj = plan.tj
    informe = Informe()
    acciones = plan.acciones()
    # primero los programas, luego el sistema, luego lo generado; la BIOS del OCM, al final
    orden = lambda a: (a[0].generado, a[0].grupo == "sistema")
    acciones.sort(key=orden)
    escritos = []       # (ruta real, sha)
    ficheros_marca = {}
    total = len(acciones) + 2
    aviso(t("ac.aplicando"), 0.0)
    for r in plan.carpetas_nuevas():
        try:
            tj.asegurar_carpeta(r)
            informe.carpetas.append(r)
        except OSError as e:
            informe.errores.append(t("ac.err.carpeta", r, e))
    for i, (e, modo) in enumerate(acciones):
        aviso(t("ac.copiando", e.ruta), 0.05 + 0.8 * i / total)
        try:
            datos = e.datos()
            destino = _destino(tj, e, modo)
            bak = _escribir_seguro(tj, destino, datos, e.sha_nueva, e.mtime, copia=modo == "forzar")
            tj.olvidar()
            escritos.append((destino, e.sha_nueva))
            if appledouble:
                _quitar_appledouble(destino)
            if modo == "alt":
                informe.alternativos.append("%s -> %s" % (e.ruta, e.alt))
                informe.dejados.append(e.ruta)
                continue
            ficheros_marca[_k(e.ruta)] = e.sha_nueva
            if modo == "forzar":
                informe.forzados.append(e.ruta)
                if bak:
                    informe.copias.append("%s -> %s" % (e.ruta, os.path.basename(bak)))
            elif e.estado == ANADIR:
                informe.anadidos.append(e.ruta)
            else:
                informe.actualizados.append(e.ruta)
        except (OSError, ErrorActualizar) as ex:
            informe.errores.append(t("ac.err.fichero", e.ruta, ex))
    informe.dejados += [e.ruta for e in plan.dejados() if e.ruta not in informe.dejados]
    informe.sin_uso = [e.ruta for e in plan.entradas if e.estado == SIN_USO]
    for e in plan.entradas + plan.generados():
        if e.estado == IGUAL:
            ficheros_marca[_k(e.ruta)] = e.sha_nueva
    for e in plan.entradas:
        if e.estado == SIN_USO and e.sha_actual:
            ficheros_marca[_k(e.ruta)] = e.sha_actual
    # el cambio de Nextor en la BIOS del OCM: EN SITIO, sin crear ni renombrar (la IPL exige el fichero contiguo)
    cambio = plan.bios_a_cambiar()
    if cambio and not informe.errores:
        aviso(t("ac.bios_en_sitio"), 0.9)
        try:
            informe.bios = _bios_en_sitio(cambio[0], cambio[1], carpeta_copias, informe)
            informe.reinicio = True
        except (OSError, ErrorActualizar) as ex:
            informe.errores.append(t("ac.err.bios", ex))
    elif cambio:
        informe.errores.append(t("ac.err.bios_no_cambia"))
    # la marca, con lo que ha quedado bien
    if escritos or informe.carpetas:
        aviso(t("ac.marca"), 0.92)
        try:
            efectivos = plan.grupos_efectivos()
            sistema = plan.destino if plan.destino != CONSERVAR else (plan.actual[0] or "ninguno")
            datos = texto_marca(ficheros_marca, plan.maquina, sistema, efectivos, plan.particiones, plan.opciones)
            destino = plan.tj.buscar(NOMBRE_MARCA) or os.path.join(tj.raiz, NOMBRE_MARCA)
            _escribir_seguro(tj, destino, datos, sha1(datos))
            escritos.append((destino, sha1(datos)))
            if appledouble:
                _quitar_appledouble(destino)
        except OSError as ex:
            informe.errores.append(t("ac.err.fichero", NOMBRE_MARCA, ex))
    # se vuelve a leer todo lo escrito
    aviso(t("ac.verificando"), 0.96)
    tj.olvidar()
    for destino, sha in escritos:
        try:
            if sha1(_leer(destino)) != sha:
                informe.errores.append(t("ac.err.no_coincide", os.path.basename(destino)))
        except OSError as ex:
            informe.errores.append(t("ac.err.fichero", os.path.basename(destino), ex))
    informe.segundos = time.time() - t0
    aviso(t("ac.hecho" if not informe.errores else "ac.hecho_errores"), 1.0)
    return informe


def _bios_en_sitio(ruta, disco, carpeta_copias, informe):
    """Cambia SOLO el bloque DISK (los primeros 128 KB) del OCM-BIOS.DA? abriendolo r+b: sin crear ni renombrar, que la
    IPL exige el fichero contiguo y en su sitio. Antes, una copia en el PC (carpeta de ajustes)."""
    if len(disco) != 128 * 1024:
        raise ErrorActualizar(t("ac.err.disco_128"))
    carpeta = carpeta_copias or os.path.join(os.path.dirname(idioma.ruta_ajustes()), "copias")
    os.makedirs(carpeta, exist_ok=True)
    nombre = os.path.basename(ruta)
    copia = os.path.join(carpeta, "%s-%s%s" % (os.path.splitext(nombre)[0], time.strftime("%Y%m%d-%H%M%S"),
                                              os.path.splitext(nombre)[1]))
    shutil.copyfile(ruta, copia)
    tam = os.path.getsize(ruta)
    if os.path.getsize(copia) != tam:
        raise ErrorActualizar(t("ac.err.copia_bios", copia))
    with open(ruta, "r+b") as f:
        f.seek(0)
        f.write(disco)
        f.flush()
        os.fsync(f.fileno())
    with open(ruta, "rb") as f:
        if f.read(128 * 1024) != disco or os.path.getsize(ruta) != tam:
            raise ErrorActualizar(t("ac.err.no_coincide", nombre))
    informe.copias.append(copia)
    return nombre
