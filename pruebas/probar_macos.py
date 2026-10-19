"""Pruebas no destructivas de la enumeración y las barreras de seguridad de macOS."""
import os
import stat
import tempfile
import unittest
from unittest import mock

from sdmaker import dispositivos


@unittest.skipUnless(os.sys.platform == "darwin", "sólo macOS")
class DispositivosMacOSTest(unittest.TestCase):
    def setUp(self):
        self.lista = {
            "WholeDisks": ["disk0", "disk4", "disk5", "disk6"],
            "AllDisksAndPartitions": [
                {"DeviceIdentifier": "disk4", "Partitions": [
                    {"DeviceIdentifier": "disk4s1", "Size": 2_000_000_000, "Content": "DOS_FAT_16",
                     "VolumeName": "MSX", "MountPoint": "/Volumes/MSX"}]},
                {"DeviceIdentifier": "disk5", "Partitions": []},
                {"DeviceIdentifier": "disk6", "Partitions": []},
            ],
        }
        base = {"WholeDisk": True, "Internal": False, "OSInternalMedia": False, "WritableMedia": True,
                "DeviceBlockSize": 512, "BusProtocol": "USB", "TotalSize": 4_000_000_000,
                "IORegistryEntryName": "Lector USB", "DeviceTreePath": "IOService:/lector"}
        self.infos = {
            "disk0": dict(base, RemovableMedia=True, IORegistryEntryName="Arranque externo"),
            "disk4": dict(base, RemovableMedia=True),
            "disk5": dict(base, RemovableMedia=False, Ejectable=False, IORegistryEntryName="SSD externo"),
            "disk6": dict(base, RemovableMedia=True, DeviceBlockSize=4096, IORegistryEntryName="4K"),
        }

    def fake_plist(self, *args):
        if args == ("list", "-plist", "external", "physical"):
            return self.lista
        if args == ("info", "-plist", "/"):
            return {"DeviceIdentifier": "disk2s1", "APFSPhysicalStores": [{"APFSPhysicalStore": "disk0s2"}]}
        if args[:2] == ("info", "-plist"):
            return self.infos[args[2].replace("/dev/", "")]
        raise AssertionError(args)

    def test_solo_tarjeta_extraible_de_512_y_no_sistema(self):
        with mock.patch.object(dispositivos, "_diskutil_plist", side_effect=self.fake_plist):
            tarjetas = dispositivos.listar_tarjetas()
        self.assertEqual([4], [t["numero"] for t in tarjetas])
        self.assertEqual(["/Volumes/MSX"], tarjetas[0]["letras"])
        self.assertEqual("DOS_FAT_16", tarjetas[0]["particiones"][0]["tipo"])

    def test_usb_fijo_solo_si_se_pide_expresamente(self):
        with mock.patch.object(dispositivos, "_diskutil_plist", side_effect=self.fake_plist):
            tarjetas = dispositivos.listar_tarjetas(incluir_usb_fijos=True)
        self.assertEqual([4, 5], [t["numero"] for t in tarjetas])

    def test_rechaza_si_cambia_identidad_o_tamano(self):
        actual = {"bytes": 1024, "modelo": "A", "identidad": "ruta-a"}
        self.assertTrue(dispositivos._misma_tarjeta(actual, dict(actual)))
        self.assertFalse(dispositivos._misma_tarjeta(actual, {"bytes": 2048, "modelo": "A", "identidad": "ruta-a"}))
        self.assertFalse(dispositivos._misma_tarjeta(actual, {"bytes": 1024, "modelo": "A", "identidad": "ruta-b"}))

    def test_lectura_escritura_alineada_y_limites(self):
        with tempfile.TemporaryFile() as f:
            f.truncate(4096)
            d = dispositivos.DiscoMacOS.__new__(dispositivos.DiscoMacOS)
            d.f, d.sectores = f.fileno(), 8
            d.escribir(2, b"A" * 512)
            self.assertEqual(b"A" * 512, d.leer(2))
            with self.assertRaises(OSError):
                d.escribir(8, b"B" * 512)
            with self.assertRaises(OSError):
                d.leer(7, 2)

    def test_no_abre_un_fichero_ordinario_como_dispositivo(self):
        tarjeta = {"numero": 4, "bytes": 4096, "sectores": 8, "modelo": "A", "identidad": "x"}
        llamadas = []
        with mock.patch.object(dispositivos, "_discos_sistema", return_value={"disk0"}), \
                mock.patch.object(dispositivos, "_buscar_tarjeta", return_value=tarjeta), \
                mock.patch.object(dispositivos, "_diskutil", side_effect=lambda *a: llamadas.append(a)), \
                mock.patch.object(dispositivos.os, "stat", return_value=mock.Mock(st_mode=stat.S_IFREG)):
            with self.assertRaises(PermissionError):
                dispositivos.DiscoMacOS(4, esperada=tarjeta)
        self.assertEqual(("unmountDisk", "/dev/disk4"), llamadas[0])
        self.assertEqual(("mountDisk", "/dev/disk4"), llamadas[-1])


if __name__ == "__main__":
    unittest.main()
