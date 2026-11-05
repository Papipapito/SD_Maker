"""Pruebas de «Actualizar tarjeta» (sdmaker/actualizar.py), en carpetas temporales y sin la historia de git (en CI el
checkout es de profundidad 1): se hace una tarjeta con contenido.arbol, se vuelca a una carpeta y se actualiza.
Para tener una «version nueva» distinta de la que lleva la tarjeta se usa una copia de sd/ con un fichero cambiado.

  python -m unittest pruebas.probar_actualizar"""
import hashlib
import io
import os
import shutil
import stat
import sys
import tempfile
import unittest
import zipfile
import zlib
from unittest import mock

from sdmaker import actualizar, contenido, dispositivos, huellas, idioma, ocm, particiones, proceso, verificar

idioma.fijar("es")
GRUPOS = {"sofarun", "mm", "util", "wifi", "fonts", "hub", "ia"}
UNA = "base/MM/MM.COM"          # un fichero de sd/ que se cambia para tener una version nueva
K = 1024


def sha(datos):
    return hashlib.sha1(datos).hexdigest()


def volcar(nodo, carpeta):
    for h in nodo.hijos:
        p = os.path.join(carpeta, h.nombre)
        if h.es_dir:
            os.makedirs(p, exist_ok=True)
            volcar(h, p)
        else:
            with open(p, "wb") as f:
                f.write(h.leer())
            os.utime(p, (h.mtime, h.mtime))


def instantanea(carpeta):
    """{ruta: (sha1, mtime_ns)} de todo lo que hay."""
    out = {}
    for d, carpetas, ficheros in os.walk(carpeta):
        for n in ficheros:
            p = os.path.join(d, n)
            with open(p, "rb") as f:
                out[os.path.relpath(p, carpeta).replace(os.sep, "/")] = (sha(f.read()), os.stat(p).st_mtime_ns)
        for n in carpetas:
            out[os.path.relpath(os.path.join(d, n), carpeta).replace(os.sep, "/") + "/"] = None
    return out


def borrar(carpeta):
    def corregir(funcion, ruta, _):
        os.chmod(ruta, stat.S_IWRITE)
        funcion(ruta)
    if sys.version_info >= (3, 12):
        shutil.rmtree(carpeta, onexc=corregir)
    else:
        shutil.rmtree(carpeta, onerror=corregir)


def escribir(ruta, datos):
    with open(ruta, "wb") as f:
        f.write(datos)


def leer(ruta):
    with open(ruta, "rb") as f:
        return f.read()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sdmupd_")
        self.addCleanup(borrar, self.tmp)
        self.sd = contenido.carpeta_sd()
        self.tarjeta = os.path.join(self.tmp, "tarjeta")
        os.mkdir(self.tarjeta)

    def hacer(self, sistema="nextor214", grupos=GRUPOS, particiones=1, opciones=None, marca=True, destino=None):
        """Una tarjeta como la que haria proceso.crear, volcada a una carpeta."""
        destino = destino or self.tarjeta
        arbol = contenido.arbol(sistema, grupos, particiones, None, opciones)
        if marca:
            actualizar.poner_marca(arbol, "fpga", sistema, grupos, particiones, opciones)
        volcar(arbol, destino)
        return destino

    def sd_nuevo(self, cambios=None):
        """Copia de sd/ con ficheros cambiados ({ruta relativa a sd/: bytes}): la «version nueva»."""
        copia = os.path.join(self.tmp, "sd_nuevo")
        if not os.path.isdir(copia):
            shutil.copytree(self.sd, copia)
        for ruta, datos in (cambios or {UNA: leer(os.path.join(self.sd, UNA)) + b"\0NUEVA VERSION"}).items():
            escribir(os.path.join(copia, *ruta.split("/")), datos)
        return copia

    def analiza(self, **kw):
        kw.setdefault("fs", "")
        return actualizar.analizar(kw.pop("raiz", self.tarjeta), **kw)

    def ruta(self, r):
        """Ruta real de r (sin distinguir mayusculas: en Linux la carpeta puede llamarse hub y no HUB)."""
        return actualizar.Tarjeta(self.tarjeta).buscar(r) or os.path.join(self.tarjeta, *r.split("/"))


class HuellasAlDia(unittest.TestCase):
    def test_todo_lo_que_hay_ahora_en_sd_esta_en_huellas(self):
        """Si falla: python herramientas/hacer_huellas.py (con la historia de git) y subir sdmaker/huellas.py."""
        faltan = []
        for sistema in ("nextor214", "nextor3", "nextor3beta2", "msxdos"):
            arbol = contenido.arbol(sistema, {g[0] for g in contenido.GRUPOS}, 1)
            ficheros, _ = actualizar._recorrer(arbol)
            for ruta, nodo in ficheros.items():
                if (ruta.upper() not in actualizar.GENERADOS and nodo.origen is not None
                        and sha(nodo.leer())[:12] not in actualizar.conocidas(ruta)):
                    faltan.append(ruta)
        self.assertEqual(sorted(set(faltan)), [], "huellas.py esta desfasado: python herramientas/hacer_huellas.py")
        mmret = leer(os.path.join(contenido.carpeta_sd(), "base", "MM", "MMRET.DAT"))
        self.assertTrue(actualizar.es_mmret_nuestro(mmret))
        lineas = {sha(l)[:8] for l in mmret.split(b"\n") if l}
        self.assertTrue(lineas <= set(huellas.LINEAS_MMRET.split()), "las lineas de MMRET.DAT no estan en huellas.py")

    def test_el_nextor_sys_de_cada_sistema_se_reconoce(self):
        sd = contenido.carpeta_sd()
        for carpeta, clave in (("nextor-2.1.4", "nextor214"), ("nextor-3.0.0", "nextor3"),
                               ("nextor-3.0.0-beta2", "nextor3beta2")):
            self.assertEqual(huellas.SISTEMA.get(sha(leer(os.path.join(sd, carpeta, "NEXTOR.SYS")))[:12]), clave)
            self.assertEqual(actualizar.clave_nextor_sys(leer(os.path.join(sd, carpeta, "NEXTOR.SYS"))), clave)


class TarjetaAlDia(Base):
    def test_nada_que_hacer_y_analizar_no_escribe(self):
        self.hacer()
        antes = instantanea(self.tarjeta)
        plan = self.analiza()
        self.assertFalse(plan.hay_trabajo(), plan.texto())
        self.assertEqual(plan.actual[0], "nextor214")
        self.assertEqual(plan.marca["VERSION"], actualizar.VERSION)
        self.assertEqual(antes, instantanea(self.tarjeta))
        self.assertEqual(plan.presentes, GRUPOS)

    def test_analizar_con_trabajo_no_escribe_nada(self):
        self.hacer()
        escribir(self.ruta("MM/MM.COM"), b"viejo")       # cambiado por el usuario
        os.remove(self.ruta("UTIL/DI.COM"))               # falta
        antes = instantanea(self.tarjeta)
        plan = self.analiza(raiz=self.tarjeta, raiz_sd=self.sd_nuevo())
        self.assertTrue(plan.hay_trabajo())
        self.assertEqual(antes, instantanea(self.tarjeta))

    def test_la_marca_lleva_todo_lo_que_escribe_proceso_crear(self):
        arbol = contenido.arbol("nextor3", GRUPOS, 3, None, None)
        actualizar.poner_marca(arbol, "fpga", "nextor3", GRUPOS, 3, None)
        volcar(arbol, self.tarjeta)
        m = actualizar.leer_marca(actualizar.Tarjeta(self.tarjeta))
        self.assertEqual((m["MAQUINA"], m["SISTEMA"], m["PARTICIONES"]), ("fpga", "nextor3", "3"))
        self.assertEqual(set(m["GRUPOS"].split(",")), GRUPOS)
        sin_marca = instantanea(self.tarjeta)
        self.assertEqual(len(m["ficheros"]), sum(1 for r in sin_marca if not r.endswith("/")) - 1)
        for ruta, s in m["ficheros"].items():
            self.assertEqual(sha(leer(self.ruta(ruta))), s, ruta)

    def test_proceso_crear_pone_la_marca_y_ninguno_no(self):
        """proceso.crear escribe SDMAKER.INF en la particion de arranque, salvo con el sistema «Ninguno»."""
        def crear(sistema, grupos):
            img = os.path.join(self.tmp, "%s.img" % sistema)
            dev = dispositivos.Imagen(img, 140 * 1024 * 2)
            try:
                plan = particiones.planificar(dev.sectores, "fat16-2g", 2, False, 64 * 1024 * 2)
                inf = proceso.crear(dev, plan, sistema, grupos, "MSX", opciones=None)
                self.assertEqual(inf["errores"], [])
                return verificar.LectorFat(dev, plan[0].lba).listar()
            finally:
                dev.cerrar()
        con = crear("nextor214", {"util"})
        arbol = contenido.arbol("nextor214", {"util"}, 2)
        actualizar.poner_marca(arbol, "fpga", "nextor214", {"util"}, 2, None)
        marca = arbol.hijo("SDMAKER.INF").datos
        self.assertEqual(con["/SDMAKER.INF"], (zlib.crc32(marca), len(marca)))
        self.assertIn(b"PARTICIONES=2", marca)
        self.assertNotIn("/SDMAKER.INF", crear("ninguno", set()))
        self.assertNotIn("/SDMAKER.INF", crear("ninguno", set()))


class VersionAntigua(Base):
    def test_se_actualiza_lo_marcado_y_lo_de_las_huellas(self):
        self.hacer()
        nuevo = self.sd_nuevo()
        plan = self.analiza(raiz_sd=nuevo)
        e = plan.por_ruta("MM/MM.COM")
        self.assertEqual(e.estado, actualizar.ACTUALIZAR)
        # sin marca: la huella (la version actual esta en huellas.py) tambien vale
        os.remove(self.ruta("SDMAKER.INF"))
        plan = self.analiza(raiz_sd=nuevo)
        self.assertEqual(plan.por_ruta("MM/MM.COM").estado, actualizar.ACTUALIZAR)
        self.assertIsNone(plan.marca)
        antes = instantanea(self.tarjeta)
        plan.confirmado = True
        inf = actualizar.aplicar(plan, appledouble=False)
        self.assertEqual(inf.errores, [])
        despues = instantanea(self.tarjeta)
        self.assertEqual(sha(leer(self.ruta("MM/MM.COM"))), sha(leer(os.path.join(nuevo, "base", "MM", "MM.COM"))))
        cambiados = {r for r in despues if despues[r] != antes.get(r)}
        self.assertEqual(cambiados, {"MM/MM.COM", "SDMAKER.INF"})
        self.assertFalse(self.analiza(raiz_sd=nuevo).hay_trabajo())

    def test_idempotencia(self):
        self.hacer()
        nuevo = self.sd_nuevo()
        plan = self.analiza(raiz_sd=nuevo)
        actualizar.aplicar(plan, appledouble=False)
        despues = instantanea(self.tarjeta)
        plan2 = self.analiza(raiz_sd=nuevo)
        self.assertFalse(plan2.hay_trabajo(), plan2.texto())
        self.assertEqual(plan2.acciones(), [])
        self.assertEqual(plan2.marca["VERSION"], actualizar.VERSION)
        self.assertEqual(despues, instantanea(self.tarjeta))

    def test_solo_lectura(self):
        self.hacer()
        os.chmod(self.ruta("MM/MM.COM"), stat.S_IREAD)
        plan = self.analiza(raiz_sd=self.sd_nuevo())
        inf = actualizar.aplicar(plan, appledouble=False)
        self.assertEqual(inf.errores, [])
        self.assertTrue(leer(self.ruta("MM/MM.COM")).endswith(b"NUEVA VERSION"))

    def test_se_conserva_el_nombre_que_ya_tenia(self):
        self.hacer()
        os.rename(self.ruta("MM/MM.COM"), os.path.join(self.ruta("MM"), "mm.com"))
        plan = self.analiza(raiz_sd=self.sd_nuevo())
        actualizar.aplicar(plan, appledouble=False)
        self.assertIn("mm.com", os.listdir(self.ruta("MM")))
        self.assertNotIn("MM.COM", os.listdir(self.ruta("MM")))
        self.assertTrue(leer(self.ruta("MM/mm.com")).endswith(b"NUEVA VERSION"))

    def test_falta_en_un_grupo_que_lleva_se_copia(self):
        self.hacer()
        os.remove(self.ruta("UTIL/DI.COM"))
        plan = self.analiza()
        self.assertEqual(plan.por_ruta("UTIL/DI.COM").estado, actualizar.ANADIR)
        actualizar.aplicar(plan, appledouble=False)
        self.assertTrue(os.path.isfile(self.ruta("UTIL/DI.COM")))
        self.assertFalse(self.analiza().hay_trabajo())


class DelUsuario(Base):
    def usuario(self):
        """Lo que pone el usuario: ROM, carpeta propia, un fichero dentro de una carpeta nuestra."""
        os.makedirs(self.ruta("JUEGOS/MSX2"))
        escribir(self.ruta("JUEGOS/MSX2/GAME.ROM"), os.urandom(5000))
        escribir(self.ruta("MIJUEGO.ROM"), os.urandom(1000))
        escribir(self.ruta("MM/MIO.ROM"), os.urandom(300))
        escribir(self.ruta("autoexec.bak"), b"mi copia")
        for r in ("JUEGOS/MSX2/GAME.ROM", "MIJUEGO.ROM", "MM/MIO.ROM", "autoexec.bak"):
            os.utime(self.ruta(r), (1_000_000_000, 1_000_000_000))

    def test_lo_del_usuario_queda_intacto_byte_a_byte_y_con_su_fecha(self):
        self.hacer()
        self.usuario()
        propios = {r: v for r, v in instantanea(self.tarjeta).items() if r.split("/")[0] in ("JUEGOS", "MIJUEGO.ROM")
                   or r in ("MM/MIO.ROM", "autoexec.bak")}
        self.assertTrue(propios)
        plan = self.analiza(raiz_sd=self.sd_nuevo())
        actualizar.aplicar(plan, appledouble=False)
        ahora = instantanea(self.tarjeta)
        for r, v in propios.items():
            self.assertEqual(ahora[r], v, r)

    def test_cambiado_se_deja_y_forzado_se_actualiza_con_bak(self):
        self.hacer()
        escribir(self.ruta("MM/MM.COM"), b"mi MM.COM")
        escribir(self.ruta("WIFI/FH.COM"), b"mi FH")
        nuevo = self.sd_nuevo()
        plan = self.analiza(raiz_sd=nuevo)
        self.assertEqual(plan.por_ruta("MM/MM.COM").estado, actualizar.CAMBIADO)
        self.assertEqual({e.ruta for e in plan.dejados()}, {"MM/MM.COM", "WIFI/FH.COM"})
        # nada que escribir salvo la marca: lo cambiado se queda
        self.assertEqual(plan.acciones(), [])
        self.assertEqual(plan.hay_trabajo(), False)
        # forzar uno
        plan = self.analiza(raiz_sd=nuevo, forzar=["mm/mm.com"])
        inf = actualizar.aplicar(plan, appledouble=False)
        self.assertEqual(inf.errores, [])
        self.assertEqual(leer(self.ruta("MM/MM.BAK")), b"mi MM.COM")
        self.assertTrue(leer(self.ruta("MM/MM.COM")).endswith(b"NUEVA VERSION"))
        self.assertEqual(leer(self.ruta("WIFI/FH.COM")), b"mi FH")
        # otra vez cambiado y forzado: no se pisa la copia anterior
        escribir(self.ruta("MM/MM.COM"), b"otra vez mia")
        plan = self.analiza(raiz_sd=nuevo, forzar=["MM/MM.COM"])
        actualizar.aplicar(plan, appledouble=False)
        self.assertEqual(leer(self.ruta("MM/MM.BAK")), b"mi MM.COM")
        self.assertEqual(leer(self.ruta("MM/MM.BA1")), b"otra vez mia")

    def test_forzar_algo_que_no_esta_cambiado_es_un_error(self):
        self.hacer()
        with self.assertRaises(actualizar.ErrorActualizar):
            self.analiza(forzar=["MM/MM.COM"])

    def test_configuracion_nunca_se_pisa_ni_se_marca_cambiada(self):
        self.hacer()
        mios = {"IA/ia.cfg": b"groq key=gsk_FALSA", "SOFARUN/SR.INI": b"[SYSTEM]\nSAVEPATH=Z:\\", "SOFARUN/SROM.INI": b"x",
                "SOFARUN/SSMS.INI": b"y", "MM/MM.HIS": b"historia", "MM/MM.PHS": b"lista", "HUB/CONFIG/BASEURL": b"http://x",
                "HUB/CONFIG/IDB/HUB": b"idb"}
        for r, d in mios.items():
            escribir(self.ruta(r), d)
        # la version nueva de cada uno de ellos es otra
        nuevo = self.sd_nuevo({"extras/IA/ia.cfg": b"plantilla nueva", "extras/SOFARUN/SR.INI": b"ini nuevo",
                               "extras/SOFARUN/SROM.INI": b"n", "extras/SOFARUN/SSMS.INI": b"n",
                               "base/MM/MM.HIS": b"n", "base/MM/MM.PHS": b"n", "extras/hub/CONFIG/BASEURL": b"n",
                               "extras/hub/CONFIG/IDB/HUB": b"n"})
        plan = self.analiza(raiz_sd=nuevo)
        for r in mios:
            self.assertEqual(plan.por_ruta(r).estado, actualizar.CONFIG, r)
        self.assertEqual(plan.dejados(), [])
        actualizar.aplicar(plan, appledouble=False)
        for r, d in mios.items():
            self.assertEqual(leer(self.ruta(r)), d, r)

    def test_configuracion_que_falta_se_copia(self):
        self.hacer()
        os.remove(self.ruta("IA/ia.cfg"))
        plan = self.analiza()
        self.assertEqual(plan.por_ruta("IA/ia.cfg").estado, actualizar.ANADIR)
        actualizar.aplicar(plan, appledouble=False)
        self.assertTrue(os.path.isfile(self.ruta("IA/ia.cfg")))

    def test_mm_cfg_se_actualiza_solo_si_es_una_version_publicada(self):
        self.hacer()
        nuevo = self.sd_nuevo({"base/MM/MM.CFG": b"cfg nueva"})
        self.assertEqual(self.analiza(raiz_sd=nuevo).por_ruta("MM/MM.CFG").estado, actualizar.ACTUALIZAR)
        escribir(self.ruta("MM/MM.CFG"), b"cfg del usuario")
        plan = self.analiza(raiz_sd=nuevo)
        self.assertEqual(plan.por_ruta("MM/MM.CFG").estado, actualizar.CONFIG)
        actualizar.aplicar(plan, appledouble=False)
        self.assertEqual(leer(self.ruta("MM/MM.CFG")), b"cfg del usuario")

    def test_appledouble_y_sistema_se_ignoran(self):
        self.hacer()
        escribir(self.ruta("._MM.COM"), b"basura apple")
        escribir(self.ruta("._JUEGO.ROM"), b"basura apple")
        os.makedirs(self.ruta(".Spotlight-V100"))
        escribir(self.ruta(".Spotlight-V100/x"), b"s")
        os.makedirs(self.ruta("System Volume Information"))
        escribir(self.ruta("System Volume Information/IndexerVolumeGuid"), b"g")
        plan = self.analiza(raiz_sd=self.sd_nuevo())
        self.assertEqual([e.ruta for e, _ in plan.acciones()], ["MM/MM.COM"])
        # el ._ de un fichero que escribimos nosotros se borra; el de otro, no
        escribir(self.ruta("MM/._MM.COM"), b"apple")
        escribir(self.ruta("MM/._MIO.ROM"), b"apple")
        actualizar.aplicar(plan, appledouble=True)
        self.assertFalse(os.path.exists(self.ruta("MM/._MM.COM")))
        self.assertTrue(os.path.exists(self.ruta("MM/._MIO.ROM")))
        self.assertTrue(os.path.exists(self.ruta("._MM.COM")))
        self.assertTrue(os.path.exists(self.ruta(".Spotlight-V100/x")))
        self.assertTrue(os.path.exists(self.ruta("System Volume Information/IndexerVolumeGuid")))


class Generados(Base):
    def test_autoexec_cambiado_se_deja_y_el_nuevo_va_como_new(self):
        self.hacer(particiones=3)
        mio = b"PATH A:\\;C:\\MIS\r\nECHO hola\r\n\x1a"
        escribir(self.ruta("AUTOEXEC.BAT"), mio)
        plan = self.analiza(raiz_sd=self.sd_nuevo())
        e = plan.por_ruta("AUTOEXEC.BAT")
        self.assertEqual((e.estado, e.alt), (actualizar.CAMBIADO, "AUTOEXEC.NEW"))
        actualizar.aplicar(plan, appledouble=False)
        self.assertEqual(leer(self.ruta("AUTOEXEC.BAT")), mio)
        self.assertEqual(leer(self.ruta("AUTOEXEC.NEW")),
                         contenido.arbol("nextor214", GRUPOS, 3).hijo("AUTOEXEC.BAT").datos)
        # la segunda vez ya esta al lado: nada que hacer
        self.assertFalse(self.analiza(raiz_sd=self.sd_nuevo()).hay_trabajo())

    def test_autoexec_con_la_huella_de_la_marca_se_sustituye(self):
        """Si el AUTOEXEC es el que escribimos (su sha1 esta en la marca), se sustituye al cambiar los programas."""
        self.hacer(grupos=GRUPOS - {"hub"}, particiones=2)
        plan = self.analiza()
        self.assertNotIn("hub", plan.presentes)
        plan.anadir_grupo("hub")
        self.assertEqual(plan.por_ruta("AUTOEXEC.BAT").estado, actualizar.ACTUALIZAR)
        actualizar.aplicar(plan, appledouble=False)
        self.assertIn(b"HUBG", leer(self.ruta("AUTOEXEC.BAT")))
        self.assertIn(b"%1" + bytes([92]) + b"hub", leer(self.ruta("AUTOEXEC.BAT")))
        self.assertTrue(os.path.isfile(self.ruta("hub/HUBG.COM")))
        self.assertFalse(self.analiza().hay_trabajo())
        # y el que el usuario retoca despues ya no se pisa (la marca ya no coincide)
        escribir(self.ruta("AUTOEXEC.BAT"), leer(self.ruta("AUTOEXEC.BAT")) + b"echo mio" + bytes([13, 10]))
        plan = self.analiza(raiz_sd=self.sd_nuevo())
        self.assertEqual(plan.por_ruta("AUTOEXEC.BAT").estado, actualizar.CAMBIADO)

    def test_autoexec_sin_marca_se_reconoce_por_sus_lineas(self):
        self.hacer(sistema="nextor3", particiones=3, marca=False)
        # con una opcion distinta en la tarjeta: se respeta (la saca de su AUTOEXEC)
        texto = leer(self.ruta("AUTOEXEC.BAT")).replace(b"YENSLASH ON\r\n", b"")
        escribir(self.ruta("AUTOEXEC.BAT"), texto)
        plan = self.analiza()
        self.assertFalse(plan.hay_trabajo(), plan.texto())
        self.assertFalse(plan.opciones["yenslash"])
        escribir(self.ruta("AUTOEXEC.BAT"), texto + b"echo mi linea\r\n")
        self.assertEqual(self.analiza().por_ruta("AUTOEXEC.BAT").estado, actualizar.CAMBIADO)

    def test_particiones_se_deducen_del_autoexec_sin_marca(self):
        self.hacer(particiones=4, marca=False)
        self.assertEqual(self.analiza().particiones, 4)
        self.assertFalse(self.analiza().hay_trabajo())

    def test_btm(self):
        self.hacer(sistema="nextor3", opciones={"btm": True}, marca=False)
        plan = self.analiza()
        self.assertTrue(plan.opciones["btm"])
        self.assertFalse(plan.hay_trabajo(), plan.texto())

    def test_mmret_ajustado_se_regenera_y_el_cambiado_no(self):
        self.hacer(grupos={"mm", "util"})        # sin musica ni sofarun: MMRET sin esas lineas
        plan = self.analiza()
        self.assertFalse(plan.hay_trabajo())
        # el MMRET de una tarjeta sin marca, el publicado entero, es nuestro
        os.remove(self.ruta("SDMAKER.INF"))
        shutil.copyfile(os.path.join(self.sd, "base", "MM", "MMRET.DAT"), self.ruta("MM/MMRET.DAT"))
        e = self.analiza().por_ruta("MM/MMRET.DAT")
        self.assertEqual(e.estado, actualizar.ACTUALIZAR)
        # con una linea del usuario, no
        escribir(self.ruta("MM/MMRET.DAT"), leer(self.ruta("MM/MMRET.DAT")) + b"\n.XYZ\tMIPROGRAMA $V\r\n")
        plan = self.analiza()
        self.assertEqual(plan.por_ruta("MM/MMRET.DAT").estado, actualizar.CAMBIADO)
        self.assertIsNone(plan.por_ruta("MM/MMRET.DAT").alt)


class Unidades(Base):
    def test_unidades_de_una_tarjeta_y_cual_es_la_de_arranque(self):
        otra = os.path.join(self.tmp, "datos")
        os.mkdir(otra)
        escribir(os.path.join(otra, "JUEGO.ROM"), b"x")
        self.hacer(grupos={"util"})
        # Windows: letras; macOS: puntos de montaje (y "letras" puede llevar nombres de volumen sin montar)
        self.assertEqual(dispositivos.carpetas_montadas({"letras": [self.tarjeta, "Z:/no_existe/"]}), [self.tarjeta])
        self.assertEqual(dispositivos.carpetas_montadas({"letras": ["MSX"], "montajes": [otra]}), [otra])
        self.assertEqual(dispositivos.carpetas_montadas({"letras": ["MSX"], "montajes": []}), [])
        self.assertEqual(actualizar.elegir_arranque([otra, self.tarjeta]), [(otra, False), (self.tarjeta, True)])

    def test_la_marca_sola_ya_dice_que_es_de_arranque(self):
        self.hacer(grupos={"util"})
        os.remove(self.ruta("NEXTOR.SYS"))
        self.assertTrue(actualizar.tiene_sistema(self.tarjeta))


class Sistemas(Base):
    def test_se_reconoce_el_sistema(self):
        for sistema, esperado in (("nextor214", "nextor214"), ("nextor3", "nextor3"), ("nextor3beta2", "nextor3beta2"),
                                  ("msxdos", "msxdos")):
            borrar(self.tarjeta)
            os.mkdir(self.tarjeta)
            self.hacer(sistema=sistema, grupos={"util"})
            plan = self.analiza()
            self.assertEqual(plan.actual[0], esperado, sistema)
            self.assertEqual(plan.destino, esperado)
            self.assertFalse(plan.hay_trabajo(), (sistema, plan.texto()))

    def test_beta2_recomienda_la_final(self):
        self.hacer(sistema="nextor3beta2", grupos={"util"})
        plan = self.analiza()
        self.assertEqual(plan.recomendado, "nextor3")
        self.assertEqual(plan.destino, "nextor3beta2")      # no se fuerza

    def test_tarjeta_que_no_es_nuestra_se_dice_y_se_puede_seguir(self):
        escribir(self.ruta("COSAS.TXT"), b"hola")
        plan = self.analiza()
        self.assertIsNone(plan.actual[0])
        self.assertEqual(plan.destino, actualizar.CONSERVAR)
        self.assertTrue(plan.avisos)
        self.assertEqual(plan.presentes, set())
        self.assertFalse(plan.hay_trabajo())

    def test_nextor_de_otra_version(self):
        self.hacer(grupos={"util"})
        escribir(self.ruta("NEXTOR.SYS"), b"\0NEXTOR.SYS version 2.20\0 resto")
        plan = self.analiza()
        self.assertEqual(plan.actual[0], "nextor214")     # por la cadena de version
        escribir(self.ruta("NEXTOR.SYS"), b"\0NEXTOR.SYS version 9.0\0 resto")
        self.assertEqual(self.analiza().actual[0], "otro")

    def test_cambio_2_a_3_y_3_a_2_en_fpga(self):
        self.hacer(sistema="nextor214", particiones=2)
        plan = self.analiza(sistema="nextor3")
        self.assertIn("nextor3", plan.ofrecidos)
        self.assertIsNotNone(plan.confirmacion())
        with self.assertRaises(actualizar.SinConfirmar):
            actualizar.aplicar(plan, appledouble=False)
        antes = instantanea(self.tarjeta)
        self.assertEqual(antes, instantanea(self.tarjeta))
        plan.confirmado = True
        inf = actualizar.aplicar(plan, appledouble=False)
        self.assertEqual(inf.errores, [])
        n3 = os.path.join(self.sd, "nextor-3.0.0")
        self.assertEqual(leer(self.ruta("NEXTOR.SYS")), leer(os.path.join(n3, "NEXTOR.SYS")))
        self.assertEqual(leer(self.ruta("COMMAND3.COM")), leer(os.path.join(n3, "COMMAND3.COM")))
        self.assertEqual(leer(self.ruta("UTILS/MAPDRV.COM")), leer(os.path.join(n3, "bin", "MAPDRV.COM")))
        self.assertIn(b"YENSLASH ON", leer(self.ruta("AUTOEXEC.BAT")))
        # lo del 2 se queda y se dice que ya no se usa
        self.assertTrue(os.path.isfile(self.ruta("COMMAND2.COM")))
        plan = self.analiza()
        self.assertEqual(plan.actual[0], "nextor3")
        self.assertIn("COMMAND2.COM", [e.ruta for e in plan.resumen()[actualizar.SIN_USO]])
        self.assertFalse(plan.hay_trabajo(), plan.texto())
        # y de vuelta
        plan = self.analiza(sistema="nextor214")
        plan.confirmado = True
        self.assertEqual(actualizar.aplicar(plan, appledouble=False).errores, [])
        self.assertEqual(leer(self.ruta("NEXTOR.SYS")), leer(os.path.join(self.sd, "nextor-2.1.4", "NEXTOR.SYS")))
        self.assertNotIn(b"YENSLASH ON", leer(self.ruta("AUTOEXEC.BAT")))
        self.assertTrue(os.path.isfile(self.ruta("COMMAND3.COM")))
        plan = self.analiza()
        self.assertEqual(plan.actual[0], "nextor214")
        self.assertFalse(plan.hay_trabajo(), plan.texto())

    def test_misma_familia_con_otro_nextor_sys_tambien_pide_confirmar(self):
        self.hacer(sistema="nextor3beta2", grupos={"util"})
        plan = self.analiza(sistema="nextor3")
        self.assertIsNotNone(plan.confirmacion())
        self.assertIsNone(self.analiza(sistema="nextor3beta2").confirmacion())

    def test_conservar_no_toca_el_sistema(self):
        self.hacer(sistema="nextor214", grupos={"util"})
        escribir(self.ruta("COMMAND2.COM"), b"mi command")
        plan = self.analiza(sistema="conservar", raiz_sd=self.sd_nuevo())
        self.assertIsNone(plan.confirmacion())
        self.assertEqual(plan.por_ruta("COMMAND2.COM"), None)

    def test_la_tarjeta_pide_que_el_destino_exista(self):
        self.hacer()
        with self.assertRaises(actualizar.ErrorActualizar):
            self.analiza(sistema="nextor9")


class Programas(Base):
    def test_los_que_no_lleva_se_anaden_solo_si_se_piden(self):
        self.hacer(grupos={"mm", "util"}, particiones=2)
        plan = self.analiza()
        self.assertIn("sofarun", plan.ausentes)
        self.assertEqual(plan.acciones(), [])
        actualizar.aplicar(plan, appledouble=False)       # sin nada que hacer: no escribe
        self.assertFalse(os.path.exists(self.ruta("SOFARUN")))
        plan = self.analiza(anadir=["sofarun"])
        self.assertTrue(plan.hay_trabajo())
        antes = instantanea(self.tarjeta)
        inf = actualizar.aplicar(plan, appledouble=False)
        self.assertEqual(inf.errores, [])
        self.assertTrue(os.path.isfile(self.ruta("SOFARUN/SR.COM")))
        self.assertTrue(os.path.isdir(self.ruta("SAVES")))
        self.assertIn(b"alias .ROM srom", leer(self.ruta("AUTOEXEC.BAT")))
        despues = instantanea(self.tarjeta)
        for r, v in antes.items():
            if r not in ("AUTOEXEC.BAT", "SDMAKER.INF", "MM/MMRET.DAT"):
                self.assertEqual(despues[r], v, r)
        # y ahora esta en la tarjeta: se actualiza con ella
        self.assertIn("sofarun", self.analiza().presentes)
        self.assertFalse(self.analiza().hay_trabajo())

    def test_anadir_un_grupo_que_ya_lleva_es_un_error(self):
        self.hacer()
        with self.assertRaises(actualizar.ErrorActualizar):
            self.analiza(anadir=["mm"])

    def test_lo_nuestro_que_ya_no_va_se_queda_y_se_lista(self):
        self.hacer()
        # un fichero que sd/ tuvo en otra version y ya no tiene: su huella esta en huellas.py
        rutas = [r for r in huellas.FICHEROS if r not in {a.upper() for a in instantanea(self.tarjeta)}
                 and r.startswith("UTIL/")]
        self.assertTrue(rutas)
        ruta = rutas[0]
        d = actualizar.conocidas(ruta)
        self.assertTrue(d)
        # no se puede fabricar una version vieja de verdad: se da por conocida (huellas parcheadas) la que se pone
        contenido_ = b"fichero viejo nuestro"
        escribir(self.ruta(ruta), contenido_)
        with mock.patch.dict(actualizar._TABLA, {ruta: {sha(contenido_)[:12]: 0}}):
            plan = self.analiza()
            self.assertIn(ruta, [e.ruta.upper() for e in plan.resumen()[actualizar.SIN_USO]])
            actualizar.aplicar(plan, appledouble=False)
        self.assertEqual(leer(self.ruta(ruta)), contenido_)


class Seguridad(Base):
    def test_sin_sitio_no_escribe_nada(self):
        self.hacer()
        nuevo = self.sd_nuevo()
        self.assertTrue(self.analiza(raiz_sd=nuevo).cabe())
        with mock.patch.object(actualizar, "_libre", return_value=100):
            plan = self.analiza(raiz_sd=nuevo)
        self.assertFalse(plan.cabe())
        self.assertTrue(any("No cabe" in a for a in plan.avisos), plan.avisos)
        antes = instantanea(self.tarjeta)
        with self.assertRaises(actualizar.SinSitio):
            actualizar.aplicar(plan, appledouble=False)
        self.assertEqual(antes, instantanea(self.tarjeta))

    def test_un_fallo_a_mitad_no_deja_el_fichero_roto(self):
        self.hacer()
        nuevo = self.sd_nuevo({UNA: b"NUEVO MM.COM", "base/UTIL/DI.COM": b"NUEVO DI"})
        plan = self.analiza(raiz_sd=nuevo)
        original = leer(self.ruta("MM/MM.COM"))
        real = os.replace

        def falla(origen, destino, *a, **k):
            if os.path.basename(destino).upper() == "MM.COM":
                raise OSError("disco lleno (simulado)")
            return real(origen, destino, *a, **k)
        with mock.patch("os.replace", side_effect=falla):
            inf = actualizar.aplicar(plan, appledouble=False)
        self.assertEqual(leer(self.ruta("MM/MM.COM")), original)
        self.assertEqual(len(inf.errores), 1)
        self.assertIn("MM/MM.COM", inf.errores[0])
        self.assertEqual(leer(self.ruta("UTIL/DI.COM")), b"NUEVO DI")
        for d, _, ficheros in os.walk(self.tarjeta):
            self.assertNotIn(actualizar.TEMPORAL, ficheros)
        # la marca no dice que MM.COM sea el nuevo
        m = actualizar.leer_marca(actualizar.Tarjeta(self.tarjeta))
        self.assertNotEqual(m["ficheros"].get("MM/MM.COM"), sha(b"NUEVO MM.COM"))

    def test_lo_escrito_se_verifica(self):
        """Si lo que queda en la tarjeta no es lo que se escribio (un temporal que se corrompe), se informa y no se pone."""
        self.hacer()
        plan = self.analiza(raiz_sd=self.sd_nuevo())
        original = leer(self.ruta("MM/MM.COM"))
        leer_bien = actualizar._leer

        def leer_mal(ruta):
            datos = leer_bien(ruta)
            return datos[:-1] + b"?" if os.path.basename(ruta) == actualizar.TEMPORAL else datos
        with mock.patch.object(actualizar, "_leer", side_effect=leer_mal):
            inf = actualizar.aplicar(plan, appledouble=False)
        self.assertTrue(inf.errores)
        self.assertEqual(leer(self.ruta("MM/MM.COM")), original)
        self.assertNotIn(actualizar.TEMPORAL, os.listdir(self.ruta("MM")))

    def test_ficheros_ajenos_a_la_tarjeta_no_se_miran(self):
        self.hacer()
        escribir(self.ruta("MM/MM.COM.bak"), b"x")
        escribir(self.ruta("PROGRAMAS.DAT"), b"y")
        plan = self.analiza()
        self.assertEqual([e for e in plan.entradas if e.ruta in ("MM/MM.COM.bak", "PROGRAMAS.DAT")], [])


# ------------------------------------------------------------------ OCM (MSXBOOK, 1chipMSX): con un pack de mentira
def pack_falso(kdl=False):
    """Un OCM-SDBIOS Pack minimo, con ROM de relleno del tamano justo, para montar BIOS con ocm.construir_dat."""
    def disco(version):
        return (b"\0" * 0x100 + b"B@Nextor kernel version " + version + b"\0").ljust(128 * K, b"\xff")
    roms = {"FREE16KB.ROM": 16, "A1WSXBSL.ROM": 32, "XBASIC21.ROM": 16, "MSX2PMUS.ROM": 16, "2PEXTRTC.ROM": 16,
            "KNMSXPPL.ROM": 32, "ESP8266E.ROM": 16, "A1XXJIS1.ROM": 128, "A1XXJIS2.ROM": 128}
    f = {"make/roms/" + n: (bytes([i + 1]) * (kb * K), 1.0) for i, (n, kb) in enumerate(roms.items())}
    f["make/roms/NEXTOR214.ROM"] = (disco(b"2.1.4"), 1.0)
    f["make/roms/NEXTOR3.ROM"] = (disco(b"3.0"), 1.0)
    f["make/make-sdb.cmd"] = (b"echo 1 = Nextor Kernel v2.1.4 Single Slot\r\necho 2 = Nextor Kernel v3.0 Single Slot\r\n"
                              b'if "%ID%"=="1" set DISK=NEXTOR214.ROM\r\nif "%ID%"=="2" set DISK=NEXTOR3.ROM\r\n', 1.0)
    f["readme.txt"] = (b"OCM-SDBIOS Pack v9.9.9", 1.0)
    base = os.path.join(contenido.carpeta_sd())
    f["make/sdcreate/os/MSXDOS2.SYS"] = (b"MSXDOS2 de mentira", 1.0)
    f["make/sdcreate/os/COMMAND2.COM"] = (b"COMMAND2 de mentira", 1.0)
    f["make/sdcreate/os/NEXTOR.SYS"] = (leer(os.path.join(base, "nextor-2.1.4", "NEXTOR.SYS")), 1.0)
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("NEXTOR.SYS", leer(os.path.join(base, "nextor-3.0.0", "NEXTOR.SYS")))
        zf.writestr("COMMAND3.COM", leer(os.path.join(base, "nextor-3.0.0", "COMMAND3.COM")))
        zf.writestr("UTILS/N3TOOL.COM", b"herramienta de Nextor 3")
        zf.writestr("HELP/N3.HLP", b"ayuda de Nextor 3")
    if kdl:     # como un pack real: su NEXTOR.SYS no es de los publicados y Nextor 3 trae otra version de la herramienta
        f["make/sdcreate/os/NEXTOR.SYS"] = (f["make/sdcreate/os/NEXTOR.SYS"][0] + b"KdL", 1.0)
        with zipfile.ZipFile(z, "a") as zf:
            zf.writestr("UTILS/OCMINFO.COM", b"ocminfo de Nextor 3")
            zf.writestr("HELP/AYUDA.HLP", b"ayuda de Nextor 3")
    f["make/sdcreate/os/N3XTOR.ZIP"] = (z.getvalue(), 1.0)
    f["make/sdcreate/help/AYUDA.HLP"] = (b"ayuda", 1.0)
    f["make/sdcreate/utils/SDBIOS.BTM"] = (b"sdbios", 1.0)
    f["make/sdcreate/utils/OCMINFO.COM"] = (b"ocminfo", 1.0)
    f["make/sdcreate/utils/PLDFLASH.COM"] = (b"pldflash", 1.0)
    return ocm.Pack("pack-falso", f)


class OCM(Base):
    def setUp(self):
        super().setUp()
        self.pack = pack_falso()
        self.carpeta_copias = os.path.join(self.tmp, "copias")

    def hacer_ocm(self, activa="nextor214", alt=None, grupos=frozenset({"mm", "hub"})):
        bios = [("OCM-BIOS.DAT", ocm.receta(disco=activa))]
        if alt:
            bios.append(("ALT-BIOS.DA1", ocm.receta(disco=alt)))
        datos = {"pack": self.pack, "bios": bios}
        arbol = contenido.arbol("nextor214", set(grupos), 1, None, None, datos)
        actualizar.poner_marca(arbol, "ocm", ocm.sistema_de(bios), set(grupos), 1, None)
        volcar(arbol, self.tarjeta)
        return arbol

    def test_lo_del_pack_real_no_es_cambio_del_usuario(self):
        self.pack = pack_falso(kdl=True)
        self.hacer_ocm()
        os.remove(self.ruta(actualizar.NOMBRE_MARCA))       # tarjeta sin marca: solo cuentan las huellas
        plan = self.analiza(pack=self.pack, sistema="nextor3")
        self.assertEqual([e.ruta for e in plan.dejados() if e.grupo == "sistema"], [])
        inf = actualizar.aplicar(plan, appledouble=False, carpeta_copias=self.carpeta_copias)
        self.assertEqual(inf.errores, [])
        n3 = self.pack.n3xtor()
        self.assertEqual(leer(self.ruta("NEXTOR.SYS")), n3["NEXTOR.SYS"][0])
        self.assertEqual(leer(self.ruta("UTILS/OCMINFO.COM")), b"ocminfo de Nextor 3")
        self.assertEqual(leer(self.ruta("HELP/AYUDA.HLP")), b"ayuda de Nextor 3")
        # y vuelta a Nextor 2
        inf = actualizar.aplicar(self.analiza(pack=self.pack, sistema="nextor214"), appledouble=False,
                                 carpeta_copias=self.carpeta_copias)
        self.assertEqual(inf.errores, [])
        self.assertTrue(leer(self.ruta("NEXTOR.SYS")).endswith(b"KdL"))
        self.assertEqual(leer(self.ruta("UTILS/OCMINFO.COM")), b"ocminfo")

    def test_nextor_sys_desconocido_se_cambia_con_copia_al_cambiar_de_nextor(self):
        self.hacer_ocm()
        with open(self.ruta("NEXTOR.SYS"), "wb") as f:
            f.write(b"un NEXTOR.SYS que no conocemos")
        plan = self.analiza(pack=self.pack, sistema="nextor3")
        plan.forzar("NEXTOR.SYS", False)                    # no se puede desmarcar
        inf = actualizar.aplicar(plan, appledouble=False, carpeta_copias=self.carpeta_copias)
        self.assertEqual(inf.errores, [])
        self.assertEqual(leer(self.ruta("NEXTOR.SYS")), self.pack.n3xtor()["NEXTOR.SYS"][0])
        self.assertEqual(leer(self.ruta("NEXTOR.BAK")), b"un NEXTOR.SYS que no conocemos")

    def test_nada_que_hacer(self):
        self.hacer_ocm()
        plan = self.analiza(pack=self.pack)
        self.assertEqual((plan.maquina, plan.actual[0]), ("ocm", "nextor214"))
        self.assertFalse(plan.hay_trabajo(), plan.texto())
        self.assertIsNone(plan.confirmacion())

    def test_el_bloque_disk_se_cambia_en_sitio_y_el_resto_queda_intacto(self):
        self.hacer_ocm()
        dat = self.ruta("OCM-BIOS.DAT")
        antes = leer(dat)
        inodo = os.stat(dat).st_ino
        plan = self.analiza(pack=self.pack, sistema="nextor3")
        self.assertIsNone(plan.confirmacion())
        self.assertIsNotNone(plan.bios_a_cambiar())
        inf = actualizar.aplicar(plan, appledouble=False, carpeta_copias=self.carpeta_copias)
        self.assertEqual(inf.errores, [])
        despues = leer(dat)
        self.assertEqual(len(despues), len(antes))
        self.assertEqual(despues[:128 * K], self.pack.rom("NEXTOR3.ROM"))
        self.assertEqual(despues[128 * K:], antes[128 * K:])
        self.assertEqual(os.stat(dat).st_ino, inodo)      # el mismo fichero: ni creado ni renombrado
        self.assertTrue(inf.reinicio)
        copias = os.listdir(self.carpeta_copias)
        self.assertEqual(len(copias), 1)
        self.assertEqual(leer(os.path.join(self.carpeta_copias, copias[0])), antes)
        # sistema, UTILS y HELP como en una tarjeta nueva con Nextor 3
        n3 = self.pack.n3xtor()
        self.assertEqual(leer(self.ruta("NEXTOR.SYS")), n3["NEXTOR.SYS"][0])
        self.assertEqual(leer(self.ruta("COMMAND3.COM")), n3["COMMAND3.COM"][0])
        self.assertTrue(os.path.isfile(self.ruta("UTILS/N3TOOL.COM")))
        self.assertEqual(self.analiza(pack=self.pack).actual[0], "nextor3")
        self.assertFalse(self.analiza(pack=self.pack).hay_trabajo())

    def test_alt_bios_se_listan_y_no_se_tocan_y_hay_n3xtor(self):
        self.hacer_ocm(activa="nextor214", alt="nextor3")
        self.assertTrue(os.path.isfile(self.ruta("N3XTOR.SYS")))
        alt = leer(self.ruta("ALT-BIOS.DA1"))
        plan = self.analiza(pack=self.pack)
        self.assertEqual(plan.ocm["alts"], [("ALT-BIOS.DA1", "nextor3")])
        self.assertFalse(plan.hay_trabajo(), plan.texto())
        # con la principal en Nextor 3, la alternativa en 2 necesita N2XTOR.SYS (XSYS3) y N3XTOR.SYS sobra
        plan = self.analiza(pack=self.pack, sistema="nextor3")
        actualizar.aplicar(plan, appledouble=False, carpeta_copias=self.carpeta_copias)
        self.assertEqual(leer(self.ruta("ALT-BIOS.DA1")), alt)
        self.assertEqual(leer(self.ruta("NEXTOR.SYS")), self.pack.n3xtor()["NEXTOR.SYS"][0])
        plan = self.analiza(pack=self.pack)
        self.assertIn("N3XTOR.SYS", [e.ruta for e in plan.resumen()[actualizar.SIN_USO]])
        self.assertTrue(os.path.isfile(self.ruta("N3XTOR.SYS")))      # nunca se borra
        self.assertFalse(plan.hay_trabajo(), plan.texto())

    def test_n2xtor_cuando_la_alternativa_lleva_el_otro_nextor(self):
        self.hacer_ocm(activa="nextor3", alt="nextor214")
        self.assertTrue(os.path.isfile(self.ruta("N2XTOR.SYS")))
        plan = self.analiza(pack=self.pack)
        self.assertFalse(plan.hay_trabajo(), plan.texto())
        os.remove(self.ruta("N2XTOR.SYS"))
        self.assertEqual(self.analiza(pack=self.pack).por_ruta("N2XTOR.SYS").estado, actualizar.ANADIR)

    def test_sin_pack_no_se_cambia_la_bios_ni_se_tocan_utils_y_help(self):
        self.hacer_ocm()
        escribir(self.ruta("UTILS/OCMINFO.COM"), b"cambiado")
        escribir(self.ruta("HELP/AYUDA.HLP"), b"cambiado")
        plan = self.analiza(pack=None)
        self.assertIsNone(plan.bios_a_cambiar())
        self.assertEqual(plan.ofrecidos, [])
        self.assertTrue(plan.avisos)
        self.assertIsNone(plan.por_ruta("UTILS/OCMINFO.COM"))
        self.assertIsNone(plan.por_ruta("HELP/AYUDA.HLP"))
        # los demas grupos si
        os.remove(self.ruta("MM/CS.COM"))
        self.assertEqual(self.analiza(pack=None).por_ruta("MM/CS.COM").estado, actualizar.ANADIR)

    def test_utils_distinto_sin_marca_es_cambiado(self):
        self.hacer_ocm()
        os.remove(self.ruta("SDMAKER.INF"))
        escribir(self.ruta("UTILS/OCMINFO.COM"), b"de otro pack")
        self.assertEqual(self.analiza(pack=self.pack).por_ruta("UTILS/OCMINFO.COM").estado, actualizar.CAMBIADO)
        self.hacer_ocm()        # con marca (la escribimos nosotros): version antigua
        escribir(self.ruta("UTILS/OCMINFO.COM"), b"de otro pack")
        self.assertEqual(self.analiza(pack=self.pack).por_ruta("UTILS/OCMINFO.COM").estado, actualizar.CAMBIADO)

    def test_el_disco_se_reconoce_por_la_cadena(self):
        self.assertEqual(actualizar.clave_disco(self.pack.rom("NEXTOR214.ROM")), "nextor214")
        self.assertEqual(actualizar.clave_disco(self.pack.rom("NEXTOR3.ROM")), "nextor3")
        self.assertEqual(actualizar.clave_disco(b"\0" * 1000 + b"Nextor kernel version 3.0 beta 2 "), "nextor3beta2")
        self.assertIsNone(actualizar.clave_disco(b"MegaSDHC"))


if __name__ == "__main__":
    unittest.main()
