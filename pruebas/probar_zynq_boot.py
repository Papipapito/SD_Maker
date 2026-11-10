"""probar_zynq_boot.py - el programa de la tarjeta de arranque de la MSXimus Z (sdmaker/zynq_boot.py), sin red."""
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from sdmaker import dispositivos, idioma, particiones, verificar, zynq_boot  # noqa: E402

# El manifiesto oficial publicado el 10/11/2026 (Z1.4.4), tal cual: firmado con la clave de las actualizaciones.
MANIFIESTO = b'''MSXIMUS-OTA 1
placa=zynq7020-mini
version=Z1.4.4
serie=2026111004
fecha=2026-11-10
notas=Instala la A desde la SD
notas=Sin Vivado: FAT16/FAT32
notas=Vuelve a bajar perfiles
imagen=nextor214 BOOT_Z1.4.4_nextor214.bin 6344256 cd954935620c771227d6f8f2a550c0f6a099fb4c4de534fa053b3bf4499ba2fa
imagen=nextor3 BOOT_Z1.4.4_nextor3.bin 6344256 0b23886b2edd4b5e1158ce48e49b467910ccf69318c4958537c9e2704c8b409f
imagen=nextor214-en BOOT_Z1.4.4_nextor214-en.bin 6344256 576a06768d5fed52d02e61a4496b4624243be700742a04c610209f3e3b2122c6
imagen=nextor3-en BOOT_Z1.4.4_nextor3-en.bin 6344256 b1fbfe4d1f9d27e6eb46f3afe6c6f2d8b6d7e3ddec335f1850861652d9ed248e
perfil=MUSICA Z1.4.4 PERFIL_MUSICA_Z1.4.4.mxp 1251840 e832855acf103fd5de09484f9b4e428928d8e1a55c0b948f5b7fb6c7976ae66d 2690464 2026111004
perfil=DUAL Z1.4.4 PERFIL_DUAL_Z1.4.4.mxp 1332736 b8b19dd41c79f7b5c20efa8b9eefe8c1d46f41b1de1bd22267d0e86a950fc57d 2642368 2026111004
perfil=TR Z1.4.4 PERFIL_TR_Z1.4.4.mxp 1038336 862d021f58fc7ad3f85e170a230e469b47d62478cec93a98e6deb23bd5a0603e 2731912 2026111004
perfil=TRV Z1.4.4 PERFIL_TRV_Z1.4.4.mxp 1343488 38a3c06725eb0c4bc0ace62c6b99408ebafe243359d5971be2baed35aec9b8fc 2872968 2026111004
firma=c8b000f13f7e8d86cdbd148bd1d39133798143961d81eb325afe32f7826e81b7eac888bc4fb2cca1b2f8eb96d4562fdeb26a6ee1cb7037d707bab66ce6e58330
'''


def boot_falso(tam=64 * 1024, version="Z9.9.9", variante="nextor214"):
    b = bytearray(os.urandom(tam))
    struct.pack_into("<II", b, 0x20, 0xAA995566, 0x584C4E58)
    info = ("MOTI1\nversion=%s\nvariante=%s\nplaca=zynq7020-mini\n" % (version, variante)).encode() + b"\0"
    b[0x1000:0x1000 + len(info)] = info
    return bytes(b)


class Firma(unittest.TestCase):
    def setUp(self):
        idioma.fijar("es")

    def test_manifiesto_real(self):
        d = zynq_boot.leer_manifiesto(MANIFIESTO, "oficial", zynq_boot.BASE)
        self.assertEqual(d["version"], "Z1.4.4")
        self.assertEqual(sorted(d["imagenes"]), sorted(zynq_boot.VARIANTES))
        self.assertEqual(d["imagenes"]["nextor214"]["tamano"], 6344256)

    def test_alterado(self):
        for cambio in ((b"version=Z1.4.4", b"version=Z1.4.5"), (b"cd954935", b"cd954936")):
            with self.assertRaises(zynq_boot.ErrorManifiesto):
                zynq_boot.leer_manifiesto(MANIFIESTO.replace(*cambio))

    def test_firma_cortada(self):
        with self.assertRaises(zynq_boot.ErrorManifiesto):
            zynq_boot.leer_manifiesto(MANIFIESTO[:MANIFIESTO.rfind(b"firma=")])


class Boot(unittest.TestCase):
    def test_info(self):
        self.assertEqual(zynq_boot.info_boot(boot_falso())["version"], "Z9.9.9")

    def test_no_es_boot(self):
        with self.assertRaises(ValueError):
            zynq_boot.info_boot(bytes(64 * 1024))
        with self.assertRaises(ValueError):
            zynq_boot.info_boot(boot_falso(tam=1024))


class Tarjeta(unittest.TestCase):
    def crear(self, esquema, mb):
        boot = boot_falso(6 << 20)
        with tempfile.TemporaryDirectory() as tmp:
            dev = dispositivos.Imagen(os.path.join(tmp, "t.img"), (mb << 20) // 512)
            try:
                plan = zynq_boot.planificar(dev.sectores, esquema)
                inf = zynq_boot.crear(dev, plan, boot)
                self.assertEqual(inf["errores"], [])
                lector = verificar.LectorFat(dev, plan[0].lba)
                leido = lector.listar()
                self.assertEqual(len(leido), 1)      # solo BOOT.bin (el nombre 8.3 lo mira test_nombre_corto)
                return plan, dev, inf
            finally:
                dev.cerrar()

    def test_fat32(self):
        plan, _, inf = self.crear("fat32", 200)
        self.assertEqual(plan[0].tipo, particiones.TIPO_FAT32)
        self.assertEqual(plan[0].lba, 8192)

    def test_fat16(self):
        plan, _, inf = self.crear("fat16", 120)
        self.assertEqual(plan[0].tipo, particiones.TIPO_FAT16)

    def test_nombre_corto(self):
        from sdmaker import fatfs
        corto, nt, largo = fatfs.nombre_corto("BOOT.bin", set())
        self.assertEqual((corto, nt, largo), (b"BOOT    BIN", 0x10, False))


class Ecdsa(unittest.TestCase):
    def test_clave_en_curva(self):
        x, y = zynq_boot._clave_publica()
        self.assertTrue(x > 0 and y > 0)

    def test_firma_rechaza_ceros(self):
        self.assertFalse(zynq_boot.verificar_ecdsa(b"x", bytes(64)))


if __name__ == "__main__":
    unittest.main()