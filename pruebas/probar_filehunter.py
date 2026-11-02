"""Pruebas del protocolo binario de la API de File-Hunter."""
import binascii
import os
import tempfile
import unittest
from unittest import mock

from sdmaker import filehunter


class FileHunterTest(unittest.TestCase):
    def test_busqueda_binaria(self):
        cuerpo = (b"\x01\x00\x00\x00\x10\x00\x00" +
                  b"\x02\x00\x00\x00\x30\x00\x00" +
                  b"\x00\x00\x00\x00" + b"Utilidad\x00MSX-AUDIO\x00")
        with mock.patch.object(filehunter, "_get", return_value=cuerpo):
            resultados = filehunter.buscar("mu")
        self.assertEqual([(0, 16, "Utilidad"), (1, 48, "MSX-AUDIO")],
                         [(x["indice"], x["kb"], x["nombre"]) for x in resultados])

    def test_descarga_crc_y_tamano(self):
        rom = bytes(range(256)) * 64
        crc = binascii.crc32(rom) & 0xFFFFFFFF
        cuerpo = ("type:mirrored,start:,size:16384,crc:%08x,name:UTIL.rom\n" % crc).encode() + rom
        resultado = {"indice": 3, "kb": 16, "nombre": "UTIL"}
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(filehunter, "_get", return_value=cuerpo), \
                mock.patch.object(filehunter, "carpeta_cache", return_value=tmp):
            ruta = filehunter.descargar("util", resultado)
            self.assertEqual(os.path.basename(ruta), "UTIL.rom")
            with open(ruta, "rb") as f:
                self.assertEqual(f.read(), rom)

    def test_rechaza_rom_que_no_cabe(self):
        rom = b"X" * (48 * 1024)
        crc = binascii.crc32(rom) & 0xFFFFFFFF
        cuerpo = ("size:49152,crc:%08x,name:AUDIO.rom\n" % crc).encode() + rom
        with mock.patch.object(filehunter, "_get", return_value=cuerpo):
            with self.assertRaisesRegex(ValueError, "exactamente 16384"):
                filehunter.descargar("audio", {"indice": 0, "kb": 48, "nombre": "AUDIO"})


if __name__ == "__main__":
    unittest.main()
