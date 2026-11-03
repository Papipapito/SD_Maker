"""Pruebas del cambio de idioma (castellano / inglés): las dos tablas, el idioma por defecto y los ajustes del usuario."""
import glob
import os
import re
import tempfile
import unittest
from unittest import mock

from sdmaker import contenido, idioma, nextor_bios, ocm, textos_en, textos_es

AQUI = os.path.dirname(os.path.abspath(__file__))
FORMATO = re.compile(r"%[-#0 +]*\d*(?:\.\d+)?[sdrxXf]")


class TablasTest(unittest.TestCase):
    def test_mismas_claves(self):
        es, en = set(textos_es.TEXTOS), set(textos_en.TEXTOS)
        self.assertEqual(sorted(es - en), [], "faltan en inglés")
        self.assertEqual(sorted(en - es), [], "faltan en castellano")

    def test_sin_cadenas_vacias(self):
        for nombre, tabla in (("es", textos_es.TEXTOS), ("en", textos_en.TEXTOS)):
            for clave, texto in tabla.items():
                self.assertIsInstance(texto, str, (nombre, clave))
                self.assertTrue(texto.strip(), (nombre, clave))

    def test_mismos_datos_en_los_dos_idiomas(self):
        for clave, texto in textos_es.TEXTOS.items():
            self.assertEqual(sorted(FORMATO.findall(texto)), sorted(FORMATO.findall(textos_en.TEXTOS[clave])), clave)

    def test_todas_las_claves_del_codigo_existen(self):
        """Toda cadena "x.clave" del código que parezca una clave de texto está en las tablas."""
        patron = re.compile(r'"((?:v|vo|vn|c|o|nb|fh|pa|ve|ff|d|p|am|g)\.[A-Za-z0-9_.\-]+)"')
        dinamicas = ("v.disco", "v.grupo_mac.", "v.sistema_mac.")
        for ruta in glob.glob(os.path.join(AQUI, "..", "sdmaker", "*.py")):
            if os.path.basename(ruta).startswith("textos_"):
                continue
            with open(ruta, encoding="utf-8") as f:
                for clave in patron.findall(f.read()):
                    if clave not in dinamicas:
                        self.assertIn(clave, textos_es.TEXTOS, "%s: %s" % (os.path.basename(ruta), clave))
        for sufijo in (".mac", ".cl"):
            self.assertIn("v.disco" + sufijo, textos_es.TEXTOS)

    def test_textos_de_los_datos(self):
        """Los textos de contenido.py, ocm.py y nextor_bios.py que son clave existen; los demás son nombres propios."""
        es_clave = re.compile(r"^[a-z]+\.[a-z0-9_.\-]+$")
        textos = [v[0] for v in contenido.SISTEMAS.values()] + [g[1] for g in contenido.GRUPOS + contenido.GRUPOS_OCM]
        textos += list(contenido.MAQUINAS.values()) + [t for _, t in ocm.TIPOS] + list(ocm.NOMBRE_TIPO.values())
        textos += [t for _, t in ocm.TECLADOS] + [t for _, t, _ in ocm.EXTRAS] + [t for _, t, _ in ocm.LOGOS]
        textos += [b[1] for b in nextor_bios.PACK_BLOCKS]
        for texto in textos:
            if es_clave.match(texto):
                self.assertIn(texto, textos_es.TEXTOS, texto)
        for g in contenido.GRUPOS + contenido.GRUPOS_OCM:
            self.assertIn("v.grupo_mac." + g[0], textos_es.TEXTOS)


class DeteccionTest(unittest.TestCase):
    def test_nombres_de_locale(self):
        for nombre in ("es", "es_ES", "es_ES.UTF-8", "es-MX", "ES_ar", "Spanish_Spain", "spanish", "es_ES@euro"):
            self.assertEqual("es", idioma.de_locale(nombre), nombre)
        for nombre in ("en", "en_US.UTF-8", "en-GB", "fr_FR", "de", "ca_ES", "English_United States", "ja_JP"):
            self.assertEqual("en", idioma.de_locale(nombre), nombre)
        for nombre in ("", None, "C", "POSIX", "C.UTF-8", "  "):
            self.assertIsNone(idioma.de_locale(nombre), nombre)

    def detectar(self, entorno=(), locale=(), windows=(), macos=(), plataforma="linux"):
        with mock.patch.object(idioma, "_de_entorno", return_value=list(entorno)), \
                mock.patch.object(idioma, "_de_locale", return_value=list(locale)), \
                mock.patch.object(idioma, "_de_windows", return_value=list(windows)), \
                mock.patch.object(idioma, "_de_macos", return_value=list(macos)), \
                mock.patch.object(idioma.sys, "platform", plataforma):
            return idioma.detectar()

    def test_entorno_y_locale(self):
        self.assertEqual("es", self.detectar(entorno=["es_ES.UTF-8"]))
        self.assertEqual("en", self.detectar(entorno=["en_US.UTF-8"], locale=["es_ES"]))
        self.assertEqual("es", self.detectar(entorno=["C"], locale=["es_ES"]))
        self.assertEqual("es", self.detectar(locale=["Spanish_Spain"]))
        self.assertEqual("en", self.detectar(locale=["fr_FR"]))

    def test_sin_datos_es_ingles(self):
        self.assertEqual("en", self.detectar())
        self.assertEqual("en", self.detectar(entorno=["C", "POSIX"]))
        self.assertEqual("en", self.detectar(plataforma="darwin"))

    def test_windows(self):
        self.assertEqual("es", self.detectar(windows=["es-ES"], entorno=["en_US"], plataforma="win32"))
        self.assertEqual("en", self.detectar(windows=["en-US"], locale=["es_ES"], plataforma="win32"))
        self.assertEqual("es", self.detectar(locale=["es_ES"], plataforma="win32"))

    def test_macos_con_locale_vacio_dentro_de_la_app(self):
        # Finder abre la .app sin LANG: sirven los idiomas preferidos de «defaults read -g AppleLanguages»
        self.assertEqual("es", self.detectar(macos=["es-ES", "en-US"], plataforma="darwin"))
        self.assertEqual("en", self.detectar(macos=["en-GB", "es-ES"], plataforma="darwin"))
        self.assertEqual("es", self.detectar(macos=[], entorno=["es_ES.UTF-8"], plataforma="darwin"))

    def test_defaults_de_macos(self):
        salida = '(\n    "es-ES",\n    "en-ES"\n)\n'
        with mock.patch.object(idioma.subprocess, "run", return_value=mock.Mock(stdout=salida)):
            self.assertEqual(["es-ES", "en-ES"], idioma._de_macos())
        with mock.patch.object(idioma.subprocess, "run", side_effect=OSError("sin defaults")):
            self.assertEqual([], idioma._de_macos())

    def test_un_fallo_al_detectar_da_ingles(self):
        with mock.patch.object(idioma, "_candidatos", side_effect=RuntimeError("fallo")):
            self.assertEqual("en", idioma.detectar())


class AjustesTest(unittest.TestCase):
    def setUp(self):
        self.antes = idioma._actual
        self.tmp = tempfile.TemporaryDirectory()
        self.ruta = os.path.join(self.tmp.name, "MSXsdmaker", "ajustes.json")
        self.parche = mock.patch.object(idioma, "ruta_ajustes", return_value=self.ruta)
        self.parche.start()

    def tearDown(self):
        self.parche.stop()
        self.tmp.cleanup()
        idioma._actual = self.antes

    def test_rutas_por_sistema(self):
        self.parche.stop()
        try:
            with mock.patch.object(idioma.sys, "platform", "win32"), \
                    mock.patch.dict(os.environ, {"APPDATA": r"C:\Users\x\AppData\Roaming"}):
                self.assertEqual(os.path.join(r"C:\Users\x\AppData\Roaming", "MSXsdmaker", "ajustes.json"),
                                 idioma.ruta_ajustes())
            with mock.patch.object(idioma.sys, "platform", "darwin"):
                r = idioma.ruta_ajustes().replace("\\", "/")
                self.assertTrue(r.endswith("Library/Application Support/MSXsdmaker/ajustes.json"), r)
            with mock.patch.object(idioma.sys, "platform", "linux"), \
                    mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": ""}):
                r = idioma.ruta_ajustes().replace("\\", "/")
                self.assertTrue(r.endswith(".config/MSXsdmaker/ajustes.json"), r)
        finally:
            self.parche.start()

    def test_se_recuerda_el_idioma(self):
        idioma.fijar("en", recordar=True)
        self.assertTrue(os.path.isfile(self.ruta))
        with open(self.ruta, "rb") as f:
            self.assertNotIn(b"\r", f.read())
        idioma._actual = None
        self.assertEqual("en", idioma.actual())
        idioma.fijar("es", recordar=True)
        idioma._actual = None
        self.assertEqual("es", idioma.actual())

    def test_sin_fichero_manda_el_sistema(self):
        idioma._actual = None
        with mock.patch.object(idioma, "detectar", return_value="es"):
            self.assertEqual("es", idioma.actual())

    def test_fichero_roto_o_ilegible_se_ignora(self):
        os.makedirs(os.path.dirname(self.ruta))
        for contenido_ in (b"", b"{no es json", b"[1, 2]", b'{"idioma": "klingon"}', b"\xff\xfe\x00"):
            with open(self.ruta, "wb") as f:
                f.write(contenido_)
            idioma._actual = None
            with mock.patch.object(idioma, "detectar", return_value="en"):
                self.assertEqual("en", idioma.actual(), contenido_)

    def test_sin_permiso_para_escribir_no_falla(self):
        with mock.patch.object(idioma.os, "makedirs", side_effect=PermissionError("no")):
            self.assertFalse(idioma.guardar_ajustes({"idioma": "en"}))
            idioma.fijar("en", recordar=True)
        self.assertEqual("en", idioma.actual())

    def test_conserva_otros_ajustes(self):
        idioma.guardar_ajustes({"otro": 1})
        idioma.fijar("en", recordar=True)
        self.assertEqual({"otro": 1, "idioma": "en"}, idioma.leer_ajustes())

    def test_idioma_desconocido(self):
        with self.assertRaises(ValueError):
            idioma.fijar("fr")


class TraduccionTest(unittest.TestCase):
    def setUp(self):
        self.antes = idioma._actual

    def tearDown(self):
        idioma._actual = self.antes

    def test_cambia_con_el_idioma(self):
        idioma.fijar("es")
        self.assertEqual("Salir", idioma.t("v.salir"))
        idioma.fijar("en")
        self.assertEqual("Quit", idioma.t("v.salir"))
        self.assertEqual("Salir", idioma.tr("es", "v.salir"))

    def test_datos(self):
        self.assertEqual("versión 1.2", idioma.tr("es", "v.version", "1.2"))
        self.assertEqual("version 1.2", idioma.tr("en", "v.version", "1.2"))

    def test_clave_desconocida_o_texto_propio(self):
        self.assertEqual("MSX2+", idioma.tr("en", "MSX2+"))
        self.assertEqual("no.existe", idioma.tr("es", "no.existe"))

    def test_prefijos_del_aviso_de_copia(self):
        idioma.fijar("en")
        self.assertTrue(idioma.tr("es", "p.copiando", "A.COM").startswith(idioma.prefijos("p.copiando")))
        self.assertTrue(idioma.tr("en", "p.copiando", "A.COM").startswith(idioma.prefijos("p.copiando")))
        self.assertFalse("Hecho".startswith(idioma.prefijos("p.copiando")))

    def test_numeros(self):
        idioma.fijar("es")
        self.assertEqual("1.234.567", idioma.miles(1234567))
        self.assertEqual("1,86 GB", idioma.decimal("1.86 GB"))
        idioma.fijar("en")
        self.assertEqual("1,234,567", idioma.miles(1234567))
        self.assertEqual("1.86 GB", idioma.decimal("1.86 GB"))

    def test_descripcion_de_bios(self):
        r = ocm.receta()
        self.assertEqual("MSX2+, nextor214, teclado \\, logo MSX++, WiFi, BASIC'n turbo 2.1",
                         ocm.describir(r, None, "es"))
        self.assertEqual("MSX2+, nextor214, keyboard \\, logo MSX++, WiFi, BASIC'n turbo 2.1",
                         ocm.describir(r, None, "en"))
        idioma.fijar("en")
        self.assertEqual("empty: boots the flash BIOS (EPBIOS)", ocm.describir(ocm.receta(tipo="vacia")))
        self.assertEqual("vacía: arranca la BIOS de la flash (EPBIOS)", ocm.describir(ocm.receta(tipo="vacia"), None, "es"))

    def test_la_tarjeta_no_cambia_con_el_idioma(self):
        """AUTOEXEC.BAT y compañía salen igual en los dos idiomas."""
        from sdmaker.fatfs import Nodo
        raiz = Nodo("", es_dir=True)
        resultados = []
        for lang in ("es", "en"):
            idioma.fijar(lang)
            resultados.append(contenido.autoexec("nextor214", {"sofarun", "mm"}, 2, raiz))
        self.assertEqual(resultados[0], resultados[1])


if __name__ == "__main__":
    unittest.main()
