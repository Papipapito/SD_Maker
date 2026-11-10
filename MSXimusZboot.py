"""MSXimusZboot — prepara la microSD de ARRANQUE (TF1) de la MSXimus Z: la formatea (FAT32 o FAT16) y le pone en la raiz
el BOOT.bin de la version elegida de msx.barcelona (oficial o beta, comprobado con la firma del manifiesto y el SHA-256)
o uno propio. Con ella la placa arranca de la SD (SW1 en OFF-OFF) y se graba sola en la QSPI desde F12 -> U -> A.

  MSXimusZboot                       abre la ventana
  MSXimusZboot versiones             las versiones publicadas (oficial y beta), con la firma comprobada
  MSXimusZboot listar                tarjetas que se pueden preparar
  MSXimusZboot imagen F.img [--tamano 1000M] [--canal oficial|beta | --boot BOOT.bin] [--variante nextor214]
                              [--esquema fat32|fat16]     una imagen de tarjeta (para probar, o para Rufus/dd)
  MSXimusZboot tarjeta N [mismas opciones] --si           prepara el disco N de "listar" (BORRA TODO)"""
import argparse
import sys

from sdmaker import dispositivos, idioma, zynq_boot


def _boot(a):
    if a.boot:
        with open(a.boot, "rb") as f:
            datos = f.read(zynq_boot.IMG_MAX + 1)
        print("BOOT.bin propio:", a.boot, zynq_boot.info_boot(datos) or "(sin ota_info)")
        return datos
    for canal, d, err in zynq_boot.bajar_manifiestos():
        if canal == a.canal:
            if not d:
                sys.exit("%s: %s" % (canal, err))
            ruta = zynq_boot.bajar_imagen(d, a.variante, lambda texto, f=None: print("  " + texto, end="\r"))
            print("\n%s %s %s -> %s" % (canal, d["version"], a.variante, ruta))
            with open(ruta, "rb") as f:
                return f.read()
    sys.exit("canal desconocido")


def _tam(texto):
    t = texto.upper().rstrip("B")
    mult = {"K": 1 << 10, "M": 1 << 20, "G": 1 << 30}.get(t[-1:], 1)
    return int(float(t.rstrip("KMG")) * mult)


def _crear(dev, a, datos):
    plan = zynq_boot.planificar(dev.sectores, a.esquema)
    inf = zynq_boot.crear(dev, plan, datos, aviso=lambda texto, f=None: print("  " + texto))
    print("particion:", inf["particiones"][0]["geometria"], "| %.1f s" % inf["segundos"])
    if inf["errores"]:
        sys.exit("ERRORES: %s" % inf["errores"])
    print("OK")


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--ayudante-zynq":
        sys.exit(zynq_boot.ejecutar_ayudante(sys.argv[2]))
    if len(sys.argv) == 1:
        from sdmaker import ventana_zynq
        ventana_zynq.main()
        return
    ap = argparse.ArgumentParser(prog="MSXimusZboot", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="orden", required=True)
    sub.add_parser("versiones")
    sub.add_parser("listar")
    for nombre in ("imagen", "tarjeta"):
        p = sub.add_parser(nombre)
        p.add_argument("destino")
        p.add_argument("--canal", default="oficial", choices=[c for c, _ in zynq_boot.CANALES])
        p.add_argument("--variante", default="nextor214", choices=zynq_boot.VARIANTES)
        p.add_argument("--boot", help="un BOOT.bin propio en vez de bajarlo")
        p.add_argument("--esquema", default="fat32", choices=["fat32", "fat16"])
        if nombre == "imagen":
            p.add_argument("--tamano", default="1000M")
        else:
            p.add_argument("--si", action="store_true", help="confirma que se borra la tarjeta")
    a = ap.parse_args()
    if a.orden == "versiones":
        for canal, d, err in zynq_boot.bajar_manifiestos():
            if not d:
                print("%-8s ERROR %s" % (canal, err))
                continue
            print("%-8s %s  serie %s  %s  (firma OK)" % (canal, d["version"], d.get("serie"), d.get("fecha")))
            for n in d["notas"]:
                print("           " + n)
            for v, e in sorted(d["imagenes"].items()):
                print("           %-13s %s  %d B  %s" % (v, e["fichero"], e["tamano"], e["sha256"][:16]))
    elif a.orden == "listar":
        for t in dispositivos.listar_tarjetas():
            print("%2d  %-10s %-5s %s  %s" % (t["numero"], dispositivos.formato_tamano(t["bytes"]), t["bus"],
                                             ",".join(t.get("letras") or []) or "-", t["modelo"]))
    elif a.orden == "imagen":
        datos = _boot(a)
        dev = dispositivos.Imagen(a.destino, _tam(a.tamano) // 512)
        try:
            _crear(dev, a, datos)
        finally:
            dev.cerrar()
    else:
        if not a.si:
            sys.exit("prepara el disco %s y BORRA TODO lo que tiene: repite con --si" % a.destino)
        datos = _boot(a)
        dev = dispositivos.Disco(int(a.destino))
        try:
            _crear(dev, a, datos)
        finally:
            dev.cerrar()


if __name__ == "__main__":
    idioma.actual()
    main()
