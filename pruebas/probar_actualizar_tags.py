"""Prueba LOCAL de «Actualizar tarjeta» contra tarjetas de versiones anteriores de verdad (se salta sin tags de git, o sin
git: en CI el checkout es de profundidad 1).

Para varias tags (v1.2, v1.4, v1.5, v1.7.0, v1.7.4) saca esa version con git archive a una carpeta temporal, hace con SU
contenido.arbol (en otro proceso: su codigo, no el de ahora) el arbol de una tarjeta de cada sistema que tuviera, lo vuelca
a una carpeta y le anade cosas del usuario (ROM, carpeta propia, ia.cfg con una clave falsa). Despues la actualiza con el
codigo actual y comprueba que lo nuestro queda igual que en una tarjeta nueva de ahora y que lo del usuario no se ha tocado.
Lo que salga como «cambiado» sin ser cambio del usuario es una huella que falta o un fichero generado por tarjeta que no se
reconoce: se imprime y hay que corregirlo (huellas.py con herramientas/hacer_huellas.py, o actualizar.py).

  python -m unittest pruebas.probar_actualizar_tags"""
import io
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest

from sdmaker import actualizar, contenido, idioma
from pruebas.probar_actualizar import borrar, escribir, instantanea, leer, sha

idioma.fijar("es")
RAIZ = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TAGS = ["v1.2", "v1.4", "v1.5", "v1.7.0", "v1.7.4"]
PARTICIONES = 3

# Se ejecuta con el codigo de la tag (sys.path[0] = su carpeta): su arbol, volcado a una carpeta.
GUION = r'''
import os, sys
sys.path.insert(0, sys.argv[1])
from sdmaker import contenido
sistema, destino, particiones = sys.argv[2], sys.argv[3], int(sys.argv[4])
if sistema not in contenido.SISTEMAS:
    sys.exit(3)
grupos = {g[0] for g in contenido.GRUPOS}
arbol = contenido.arbol(sistema, grupos, particiones)
def volcar(n, d):
    for h in n.hijos:
        p = os.path.join(d, h.nombre)
        if h.es_dir:
            os.makedirs(p, exist_ok=True)
            volcar(h, p)
        else:
            datos = h.datos if h.datos is not None else open(h.origen, "rb").read()
            open(p, "wb").write(datos)
            os.utime(p, (h.mtime, h.mtime))
volcar(arbol, destino)
print(",".join(sorted(grupos)))
'''


def git(*args):
    return subprocess.run(["git", *args], cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def tags_que_hay():
    try:
        r = git("tag", "--list")
    except OSError:
        return []
    return [t for t in TAGS if t in r.stdout.decode().split()] if r.returncode == 0 else []


@unittest.skipUnless(tags_que_hay(), "sin tags de git (checkout superficial) o sin git")
class TarjetasDeVersionesAnteriores(unittest.TestCase):
    informe = []

    @classmethod
    def tearDownClass(cls):
        print("\n== Tarjetas de versiones anteriores: %d casos" % len(cls.informe))
        for linea in cls.informe:
            print("  " + linea)

    def sacar(self, tag, destino):
        r = git("archive", "--format=tar", tag)
        self.assertEqual(r.returncode, 0, r.stderr)
        with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tf:
            tf.extractall(destino)

    def test_tags(self):
        for tag in tags_que_hay():
            with tempfile.TemporaryDirectory(prefix="sdmupd_tag_") as tmp:
                version = os.path.join(tmp, "version")
                os.mkdir(version)
                self.sacar(tag, version)
                for sistema in ("nextor214", "nextor3", "nextor3beta2", "msxdos"):
                    with self.subTest(tag=tag, sistema=sistema):
                        self.caso(tag, sistema, version, tmp)

    def caso(self, tag, sistema, version, tmp):
        tarjeta = os.path.join(tmp, "tarjeta_" + sistema)
        os.mkdir(tarjeta)
        r = subprocess.run([sys.executable, "-I", "-c", GUION, version, sistema, tarjeta, str(PARTICIONES)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if r.returncode == 3:
            return          # esa version no tenia ese sistema
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        grupos = set(r.stdout.strip().split(","))
        # lo del usuario
        def ruta(x):
            return os.path.join(tarjeta, *x.split("/"))
        os.makedirs(ruta("JUEGOS/MSX2"))
        escribir(ruta("JUEGOS/MSX2/GAME.ROM"), os.urandom(4000))
        escribir(ruta("MIJUEGO.ROM"), os.urandom(900))
        escribir(ruta("MM/MIO.ROM"), os.urandom(200))
        clave_falsa = b"groq key=gsk_CLAVE_FALSA_DE_PRUEBA\r\n"
        if os.path.isfile(ruta("IA/ia.cfg")):
            escribir(ruta("IA/ia.cfg"), clave_falsa)
        for r_ in ("JUEGOS/MSX2/GAME.ROM", "MIJUEGO.ROM", "MM/MIO.ROM"):
            os.utime(ruta(r_), (1_000_000_000, 1_000_000_000))
        propios = {k: v for k, v in instantanea(tarjeta).items()
                   if k.startswith("JUEGOS") or k in ("MIJUEGO.ROM", "MM/MIO.ROM")}

        plan = actualizar.analizar(tarjeta, fs="")
        clave = plan.actual[0]
        etiqueta = "%s %s -> detectado %s" % (tag, sistema, clave)
        self.assertIsNotNone(clave, etiqueta)
        self.assertEqual(plan.particiones, PARTICIONES, etiqueta)
        cambiados_ = [e for e in plan.resumen()[actualizar.CAMBIADO]]
        self.informe.append("%s: %d a actualizar, %d a anadir, %d ya no se usan, %d cambiados%s" % (
            etiqueta, len(plan.resumen()[actualizar.ACTUALIZAR]), len(plan.resumen()[actualizar.ANADIR]),
            len(plan.resumen()[actualizar.SIN_USO]), len(cambiados_),
            (": " + ", ".join(e.ruta for e in cambiados_)) if cambiados_ else ""))
        self.assertEqual([e.ruta for e in cambiados_], [], "huella que falta o fichero generado no reconocido: " + etiqueta)
        self.assertEqual(plan.presentes, grupos, etiqueta)
        plan.confirmado = True
        habia_trabajo = plan.hay_trabajo()
        inf = actualizar.aplicar(plan, appledouble=False)
        self.assertEqual(inf.errores, [], etiqueta)

        # lo nuestro queda igual que en una tarjeta nueva de ahora, con el mismo sistema, programas y particiones
        nueva = contenido.arbol(clave, grupos, PARTICIONES)
        distintos = []

        def comparar(n, pre):
            for h in n.hijos:
                if h.es_dir:
                    comparar(h, pre + h.nombre + "/")
                    continue
                p = ruta(pre + h.nombre)
                if not os.path.isfile(p):
                    distintos.append(pre + h.nombre + " (falta)")
                elif pre + h.nombre == "IA/ia.cfg":
                    if leer(p) != clave_falsa:
                        distintos.append("IA/ia.cfg (se ha pisado la clave)")
                elif sha(leer(p)) != sha(h.leer()):
                    distintos.append(pre + h.nombre)
        comparar(nueva, "")
        self.assertEqual(distintos, [], etiqueta)
        # lo del usuario, intacto
        ahora = instantanea(tarjeta)
        for k, v in propios.items():
            self.assertEqual(ahora[k], v, etiqueta + " " + k)
        # y no queda nada que hacer
        de_nuevo = actualizar.analizar(tarjeta, fs="")
        self.assertFalse(de_nuevo.hay_trabajo(), etiqueta + "\n" + de_nuevo.texto())
        if habia_trabajo:
            self.assertEqual(de_nuevo.marca["VERSION"], actualizar.VERSION)
        borrar(tarjeta)


if __name__ == "__main__":
    unittest.main()
