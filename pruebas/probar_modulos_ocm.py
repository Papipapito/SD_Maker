"""Prueba aislada de los módulos ROM personalizados de las BIOS OCM."""
import os
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, ".."))
from sdmaker import idioma, ocm  # noqa: E402

idioma.fijar("es")     # la prueba comprueba mensajes en castellano


class PackFalso:
    def __init__(self):
        k = ocm.K
        tamanos = {
            "DISK.ROM": 128 * k, "A1WSXBSL.ROM": 32 * k, "XBASIC21.ROM": 16 * k,
            "A1XXJIS1.ROM": 128 * k, "A1XXJIS2.ROM": 128 * k, "KNMSXPPL.ROM": 32 * k,
            "MSX2PMUS.ROM": 16 * k, "2PEXTRTC.ROM": 16 * k, "ESP8266E.ROM": 16 * k,
            "FREE16KB.ROM": 16 * k, "CUSTOM.ROM": 16 * k,
        }
        self.roms = {n: bytes([i + 1]) * tam for i, (n, tam) in enumerate(tamanos.items())}
        self.nucleos = {"nextor214": ("DISK.ROM", "Nextor de prueba")}

    def rom(self, nombre, tam=None):
        datos = self.roms[nombre.upper()]
        if tam is not None and len(datos) != tam:
            raise ValueError("tamaño incorrecto")
        return datos

    def texto_disco(self, disco):
        return disco

    def roms_de_tamano(self, tam):
        return [n for n, d in self.roms.items() if len(d) == tam]


def main():
    pack = PackFalso()
    base = ocm.receta(wifi=True)
    normal = ocm.construir_dat(pack, base)
    assert len(normal) == 512 * ocm.K

    # En el formato moderno: EXTRA 160-176K, MUSIC 176-192K y OPTION 240-256K.
    offsets = {"extra": 160 * ocm.K, "music": 176 * ocm.K, "option": 240 * ocm.K}
    personalizada = pack.rom("CUSTOM.ROM")
    for bloque, inicio in offsets.items():
        r = ocm.receta(base, modulos={bloque: {"origen": "pack", "nombre": "CUSTOM.ROM"}})
        dat = ocm.construir_dat(pack, r)
        fin = inicio + 16 * ocm.K
        assert dat[inicio:fin] == personalizada, bloque
        assert dat[:inicio] == normal[:inicio] and dat[fin:] == normal[fin:], bloque

    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "UTILIDAD.ROM")
        with open(ruta, "wb") as f:
            f.write(b"U" * 16 * ocm.K)
        r = ocm.receta(base, modulos={"extra": {"origen": "archivo", "ruta": ruta}})
        dat = ocm.construir_dat(pack, r)
        assert dat[offsets["extra"]:offsets["extra"] + 16 * ocm.K] == b"U" * 16 * ocm.K

        mala = os.path.join(tmp, "DEMASIADO-GRANDE.ROM")
        with open(mala, "wb") as f:
            f.write(b"X" * 32 * ocm.K)
        r = ocm.receta(base, modulos={"music": {"origen": "archivo", "ruta": mala}})
        try:
            ocm.construir_dat(pack, r)
        except ValueError as e:
            assert "exactamente" in str(e) and "16 KB" in str(e)
        else:
            raise AssertionError("se aceptó una ROM de 32 KB en un bloque de 16 KB")

    # Las recetas antiguas, que no contienen "modulos", siguen produciendo el mismo resultado predeterminado.
    antigua = {k: v for k, v in base.items() if k != "modulos"}
    assert ocm.construir_dat(pack, antigua) == normal

    # El selector no mezcla ROM de SUB/CBIOS sólo porque también midan 16 KB.
    class Inventario:
        def roms_de_tamano(self, tam):
            return ["FREE16KB.ROM", "XBASIC21.ROM", "MSX2PMUS.ROM", "MSXTRMUS.ROM", "2PEXTRTC.ROM",
                    "ESP8266E.ROM", "ESP8266M.ROM", "MSXTROPT.ROM", "MSXPPOPT.ROM", "CBIOSOPT.ROM"]
    inventario = Inventario()
    assert ocm.Pack.roms_para_modulo(inventario, "extra", "msx2p") == ["FREE16KB.ROM", "XBASIC21.ROM"]
    assert ocm.Pack.roms_para_modulo(inventario, "music", "msx2p") == ["FREE16KB.ROM", "MSX2PMUS.ROM"]
    assert ocm.Pack.roms_para_modulo(inventario, "music", "turbor") == ["FREE16KB.ROM", "MSXTRMUS.ROM"]
    assert ocm.Pack.roms_para_modulo(inventario, "option", "msx2p") == [
        "FREE16KB.ROM", "ESP8266E.ROM", "MSXPPOPT.ROM"]
    print("MÓDULOS OCM: bloques, aislamiento, archivo externo y compatibilidad: OK")


if __name__ == "__main__":
    main()
