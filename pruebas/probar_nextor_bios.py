import hashlib
import unittest
from pathlib import Path

from sdmaker import contenido, nextor_bios


class CreadorNextorTest(unittest.TestCase):
    def setUp(self):
        self.bancos = 7
        self.base = bytearray(self.bancos * nextor_bios.BANK_SIZE)
        self.base[:255] = bytes(range(255))
        self.base[nextor_bios.BASE_BANK_COUNT_OFFSET] = self.bancos
        self.mapper_base = bytes(range(48))
        self.base[nextor_bios.BANK_SIZE - 48:nextor_bios.BANK_SIZE] = self.mapper_base
        self.driver = bytearray(b"D" * nextor_bios.BANK_SIZE)
        self.driver[256:256 + len(nextor_bios.DRIVER_SIGNATURE)] = nextor_bios.DRIVER_SIGNATURE

    def test_crea_rom_y_parchea_banco_del_driver(self):
        rom = nextor_bios.crear_rom(bytes(self.base), bytes(self.driver))
        self.assertEqual(len(rom), 8 * nextor_bios.BANK_SIZE)
        inicio = 7 * nextor_bios.BANK_SIZE
        self.assertEqual(rom[inicio:inicio + 255], self.base[:255])
        self.assertEqual(rom[inicio + 255], 7)
        self.assertEqual(rom[(8 * nextor_bios.BANK_SIZE) - 48:], self.mapper_base)
        self.assertEqual(rom[:7 * nextor_bios.BANK_SIZE], self.base)

    def test_mapper_8k_extra_y_teclas(self):
        mapper = b"\xff\x00\x60" + b"\x07\x32\x00\x60\xc9"
        extra = b"EXTRA"
        rom = nextor_bios.crear_rom(bytes(self.base), bytes(self.driver), mapper=mapper, extra=extra, teclas=0x1002)
        codigo = mapper[3:].ljust(48, b"\0")
        for banco in range(8):
            inicio = banco * nextor_bios.BANK_SIZE
            self.assertEqual(rom[inicio + 0xF7:inicio + 0xFA], b"\x32\x00\x60")
            self.assertEqual(rom[inicio + nextor_bios.BANK_SIZE - 48:(banco + 1) * nextor_bios.BANK_SIZE], codigo)
        self.assertEqual(rom[nextor_bios.MAPPER_INIT_OFFSET:nextor_bios.MAPPER_INIT_OFFSET + 48], codigo)
        self.assertEqual(rom[nextor_bios.BOOT_KEYS_OFFSET:nextor_bios.BOOT_KEYS_OFFSET + 2], b"\x02\x10")
        for banco in (0, 3):
            inicio = banco * nextor_bios.BANK_SIZE + nextor_bios.EXTRA_OFFSET
            self.assertEqual(rom[inicio:inicio + 5], extra)

    def test_rechaza_driver_nextor_2_y_entradas_invalidas(self):
        with self.assertRaisesRegex(ValueError, "Nextor 3"):
            nextor_bios.crear_rom(bytes(self.base), bytes(nextor_bios.BANK_SIZE))
        with self.assertRaisesRegex(ValueError, "48 bytes"):
            nextor_bios.crear_rom(bytes(self.base), bytes(self.driver), mapper=bytes(49))
        with self.assertRaisesRegex(ValueError, "4000h"):
            nextor_bios.crear_rom(bytes(self.base), bytes(self.driver), direccion_8k=0x2000)

    def test_actualiza_pack_y_conserva_los_demas_bloques(self):
        rom_vieja = nextor_bios.crear_rom(bytes(self.base), bytes(self.driver))
        pack = bytearray(b"P" * (512 * 1024 + 6))
        inicio = nextor_bios.PACK_NEXTOR_OFFSET
        pack[inicio:inicio + len(rom_vieja)] = rom_vieja
        base_final = bytearray(self.base)
        base_final[0x1234] = 0xA5
        nuevo = nextor_bios.actualizar_pack_bios(bytes(pack), bytes(base_final))
        self.assertEqual(len(nuevo), len(pack))
        self.assertEqual(nuevo[:inicio], pack[:inicio])
        self.assertEqual(nuevo[inicio + nextor_bios.PACK_NEXTOR_SIZE:],
                         pack[inicio + nextor_bios.PACK_NEXTOR_SIZE:])
        self.assertEqual(nuevo[inicio + 0x1234], 0xA5)
        self.assertEqual(nuevo[inicio + 7 * nextor_bios.BANK_SIZE + 256:
                              inicio + 7 * nextor_bios.BANK_SIZE + 256 + len(nextor_bios.DRIVER_SIGNATURE)],
                         nextor_bios.DRIVER_SIGNATURE)

    def test_archivos_finales_oficiales(self):
        carpeta = Path(__file__).parents[1] / "sd" / "nextor-3.0.0"
        esperados = {
            "Nextor-3.0.0.base.dat": "f90516f8648984cc1cc16787c4449160be1f1c3c3d893580cb55b6e7c7130a98",
            "NEXTOR.SYS": "b2d37b035bf352367ee2500309c3f09c985f68413333e94a55c761ee6b5111c3",
            "COMMAND3.COM": "8afd16453e9ef5c0ac8d87a0852cafc051e5d24bed32c2a0e09900153504efcf",
        }
        for nombre, esperado in esperados.items():
            self.assertEqual(hashlib.sha256((carpeta / nombre).read_bytes()).hexdigest(), esperado)
        self.assertEqual(len(list((carpeta / "bin").glob("*.COM"))), 26)

    def test_herramientas_finales_en_utils(self):
        raiz = contenido.arbol("nextor3", set(), 1)
        self.assertIsNone(raiz.hijo("BIN"))
        tools = raiz.hijo("UTILS")
        self.assertIsNotNone(tools)
        self.assertIsNotNone(tools.hijo("EMUFILE.COM"))
        autoexec = raiz.hijo("AUTOEXEC.BAT").leer().decode("ascii")
        self.assertIn("%1\\UTILS", autoexec)

    def test_personaliza_bloques_y_conserva_configuracion(self):
        pack = bytes((i // nextor_bios.BANK_SIZE) & 0xFF for i in range(nextor_bios.PACK_SIZE)) + b"CONFIG"
        nueva_main = b"M" * (32 * 1024)
        nuevo_logo = b"L" * (16 * 1024)
        salida = nextor_bios.personalizar_pack(pack, {"main": nueva_main, "logo": nuevo_logo})
        self.assertEqual(salida[0x60000:0x68000], nueva_main)
        self.assertEqual(salida[0x7C000:0x80000], nuevo_logo)
        self.assertEqual(salida[-6:], b"CONFIG")
        self.assertEqual(salida[:0x60000], pack[:0x60000])
        with self.assertRaisesRegex(ValueError, "protegido"):
            nextor_bios.personalizar_pack(pack, {"menu2": b"X" * (16 * 1024)})


if __name__ == "__main__":
    unittest.main()
