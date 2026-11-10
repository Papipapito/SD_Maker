"""hacer_guia.py — la mini guia en PDF (castellano y despues ingles, una pagina cada uno) de la primera instalacion de la
MSXimus Z con MSXimusZboot: el programa en el ordenador, SW1 antes y despues, la ranura TF1 y los pasos en la placa.

    python zynq/guia/hacer_guia.py [salida.pdf]        (por defecto zynq/guia/MSXimusZ_instalacion_ES_EN.pdf)

Necesita reportlab. Las capturas del programa (programa_es.png / programa_en.png) se rehacen a mano cuando cambie la
ventana; la foto de TF1 es zynq/tf1-ranura.png. Si existen zynq/sw1_sd.png y zynq/sw1_qspi.png (fotos reales de SW1),
se usan en lugar del dibujo."""
import os
import sys

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

AQUI = os.path.dirname(os.path.abspath(__file__))
ZYNQ = os.path.dirname(AQUI)
sys.path.insert(0, os.path.dirname(ZYNQ))
from sdmaker import zynq_boot  # noqa: E402

TEXTOS = {
    "es": {
        "titulo": "MSXimus Z · Primera instalación",
        "sub": "Con la tarjeta de arranque, sin Vivado. Unos diez minutos.",
        "pc": "1. En el ordenador: la tarjeta de arranque",
        "pc_pasos": [
            "Abre MSXimusZboot (Windows: pide permiso de administrador; macOS: lo pide al escribir).",
            "Mete una microSD de 1 GB o más en el lector. Se BORRA entera.",
            "Elige la tarjeta, la versión «Oficial» y la variante (se puede cambiar luego).",
            "Deja FAT32 y pulsa «Preparar la tarjeta». El programa baja el BOOT.bin de",
            "msx.barcelona, comprueba la firma y el SHA-256, formatea, lo copia y lo relee.",
            "Sácala con seguridad cuando diga que está lista.",
        ],
        "placa": "2. En la placa",
        "antes": "ANTES de dar corriente", "antes2": "SW1 en OFF-OFF: arranca de la SD",
        "despues": "AL ACABAR, sin corriente", "despues2": "SW1 en ON-OFF: arranca de la QSPI",
        "tf1": "La tarjeta en TF1: lado del HDMI, la ranura de la izquierda (en rojo).",
        "dibujo": "Dibujo orientativo: guíate por las letras ON y los números impresos en SW1. SW1 solo se lee al dar corriente.",
        "pasos": [
            "Placa SIN corriente. Tarjeta de arranque en TF1; la del MSX (SD Maker), si la tienes, en TF2.",
            "SW1 en OFF-OFF. HDMI a la pantalla, teclado USB en P3 y, si tienes, el cable de red en J3.",
            "Dale corriente: sale el logo y el menú, cargados desde la tarjeta. Aún no se ha grabado nada.",
            "Pulsa F12 y luego U: la página se llama «BOOT.bin de la SD».",
            "Pulsa A (enseña la versión de la tarjeta) y luego A dos veces seguidas: graba la ranura A.",
            "Tarda alrededor de un minuto. No apagues mientras graba.",
            "Cuando ponga «Grabada en la ranura A»: quita la corriente y pon SW1 en ON-OFF.",
            "Dale corriente: arranca sola de la QSPI. F12 → P prepara TF1 para los perfiles (la borra:",
            "el BOOT.bin ya no hace falta) y, con red, F12 → U busca la última versión.",
        ],
        "numeros": [1, 2, 3, 4, 5, None, 6, 7, None],
        "negro": "¿Pantalla negra con SW1 en OFF-OFF? La tarjeta tiene que estar en TF1 (no en TF2) y SW1 bien puesto: "
                 "SW1 solo se lee al dar la corriente.",
        "pie": "MSXimus Z · github.com/Papipapito/MSXimus_Z · msx.barcelona · MSXimusZboot %s",
    },
    "en": {
        "titulo": "MSXimus Z · First installation",
        "sub": "With the boot card, no Vivado. About ten minutes.",
        "pc": "1. On the computer: the boot card",
        "pc_pasos": [
            "Open MSXimusZboot (Windows: it asks for administrator rights; macOS: when writing).",
            "Put a microSD of 1 GB or more in the reader. It is ERASED.",
            "Choose the card, the «Official» version and the variant (it can be changed later).",
            "Keep FAT32 and press «Prepare the card». The program downloads the BOOT.bin from",
            "msx.barcelona, checks the signature and the SHA-256, formats, copies and reads it back.",
            "Eject it safely when it says it is ready.",
        ],
        "placa": "2. On the board",
        "antes": "BEFORE powering on", "antes2": "SW1 at OFF-OFF: boots from the SD",
        "despues": "WHEN DONE, powered off", "despues2": "SW1 at ON-OFF: boots from the QSPI",
        "tf1": "The card in TF1: HDMI side, the slot on the left (in red).",
        "dibujo": "Illustrative drawing: go by the ON letters and the numbers printed on SW1. SW1 is only read at power on.",
        "pasos": [
            "Board powered OFF. Boot card in TF1; the MSX card (SD Maker), if you have it, in TF2.",
            "SW1 at OFF-OFF. HDMI to the screen, USB keyboard on P3 and, if you have it, network cable on J3.",
            "Power on: the logo and the menu show up, loaded from the card. Nothing written yet.",
            "Press F12 and then U: the page for the BOOT.bin on the SD card.",
            "Press A (it shows the card's version) and then A twice in a row: it writes slot A.",
            "It takes about a minute. Do not power off while it writes.",
            "When it says it is written to slot A: power off and set SW1 to ON-OFF.",
            "Power on: it boots by itself from the QSPI. F12 → P prepares TF1 for the profiles (it erases",
            "it: the BOOT.bin is no longer needed) and, with a network, F12 → U looks for the latest version.",
        ],
        "numeros": [1, 2, 3, 4, 5, None, 6, 7, None],
        "negro": "Black screen with SW1 at OFF-OFF? The card must be in TF1 (not TF2) and SW1 set right: SW1 is only "
                 "read at power on.",
        "pie": "MSXimus Z · github.com/Papipapito/MSXimus_Z · msx.barcelona · MSXimusZboot %s",
    },
}

ROJO, ROJO_OSC, GRIS, VERDE, AZUL = (HexColor("#c62828"), HexColor("#7f1010"), HexColor("#555555"),
                                     HexColor("#1b5e20"), HexColor("#0d47a1"))


def fuentes():
    for normal, negrita in ((r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
                            ("/Library/Fonts/Arial Unicode.ttf", "/Library/Fonts/Arial Unicode.ttf"),
                            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")):
        if os.path.isfile(normal) and os.path.isfile(negrita):
            pdfmetrics.registerFont(TTFont("Guia", normal))
            pdfmetrics.registerFont(TTFont("Guia-B", negrita))
            return "Guia", "Guia-B"
    return "Helvetica", "Helvetica-Bold"


def sw1(c, x, y, palancas, f, fb):
    """El mismo dibujo que la ventana del programa. (x, y) = esquina inferior izquierda. 30 x 23 mm."""
    w, h = 30 * mm, 23 * mm
    c.setFillColor(ROJO)
    c.setStrokeColor(ROJO_OSC)
    c.rect(x, y, w, h, fill=1, stroke=1)
    c.setFillColor(white)
    c.setFont(fb, 8)
    c.drawString(x + 1.5 * mm, y + h - 4 * mm, "ON")
    c.setStrokeColor(white)
    c.line(x + 7.5 * mm, y + h - 4.5 * mm, x + 7.5 * mm, y + h - 1 * mm)
    c.line(x + 6.7 * mm, y + h - 2 * mm, x + 7.5 * mm, y + h - 1 * mm)
    c.line(x + 8.3 * mm, y + h - 2 * mm, x + 7.5 * mm, y + h - 1 * mm)
    for i, arriba in enumerate(palancas):
        cx = x + (10 + i * 11.5) * mm
        c.setFillColor(HexColor("#f5f5f5"))
        c.setStrokeColor(GRIS)
        c.rect(cx, y + 5 * mm, 7 * mm, 12.5 * mm, fill=1, stroke=1)
        c.setFillColor(HexColor("#263238"))
        py = y + 11.2 * mm if arriba else y + 5.5 * mm
        c.rect(cx + 0.8 * mm, py, 5.4 * mm, 5.8 * mm, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont(fb, 8)
        c.drawCentredString(cx + 3.5 * mm, y + 1.3 * mm, str(i + 1))
        c.setFillColor(VERDE if arriba else HexColor("#222222"))
        c.drawCentredString(cx + 3.5 * mm, y - 4 * mm, "ON" if arriba else "OFF")


def imagen(c, ruta, x, y, ancho):
    im = ImageReader(ruta)
    w, h = im.getSize()
    alto = ancho * h / w
    c.drawImage(im, x, y - alto, ancho, alto)
    c.setStrokeColor(HexColor("#bbbbbb"))
    c.rect(x, y - alto, ancho, alto, fill=0, stroke=1)
    return alto


def pagina(c, lang, f, fb):
    t = TEXTOS[lang]
    W, H = A4
    m = 16 * mm
    y = H - m
    c.setFillColor(HexColor("#111111"))
    c.setFont(fb, 20)
    c.drawString(m, y - 6 * mm, t["titulo"])
    c.setFont(f, 11)
    c.setFillColor(GRIS)
    c.drawString(m, y - 12 * mm, t["sub"])
    c.setFont(fb, 9)
    c.setFillColor(AZUL)
    c.drawRightString(W - m, y - 6 * mm, "ES" if lang == "es" else "EN")
    y -= 22 * mm

    # 1. ordenador
    c.setFillColor(HexColor("#111111"))
    c.setFont(fb, 13)
    c.drawString(m, y, t["pc"])
    c.setFont(f, 9.5)
    yy = y - 6 * mm
    for linea in t["pc_pasos"]:
        c.drawString(m, yy, ("   " if linea.startswith("msx.barcelona") else "• ") + linea)   # la 5.ª sigue a la 4.ª
        yy -= 5.2 * mm
    ancho = 96 * mm
    alto = imagen(c, os.path.join(AQUI, "programa_%s.png" % lang), (W - ancho) / 2, yy - 1 * mm, ancho)
    y = yy - alto - 10 * mm

    # 2. placa
    c.setFont(fb, 13)
    c.drawString(m, y, t["placa"])
    y -= 7 * mm
    for i, (k1, k2, palancas, foto) in enumerate((("antes", "antes2", (False, False), "sw1_sd.png"),
                                                  ("despues", "despues2", (True, False), "sw1_qspi.png"))):
        x = m + i * 52 * mm
        c.setFont(fb, 9.5)
        c.setFillColor(HexColor("#111111"))
        c.drawString(x, y, t[k1])
        c.setFont(f, 9)
        c.drawString(x, y - 4.5 * mm, t[k2])
        ruta = os.path.join(ZYNQ, foto)
        if os.path.isfile(ruta):
            imagen(c, ruta, x, y - 7 * mm, 40 * mm)
        else:
            sw1(c, x + 4 * mm, y - 33 * mm, palancas, f, fb)
    alto = imagen(c, os.path.join(ZYNQ, "tf1-ranura.png"), W - m - 66 * mm, y + 1 * mm, 66 * mm)
    c.setFont(f, 8.5)
    c.setFillColor(GRIS)
    for i, trozo in enumerate(simpleSplit(t["tf1"], f, 8.5, 66 * mm)):
        c.drawString(W - m - 66 * mm, y - alto - (3 + 4 * i) * mm, trozo)
    y -= 48 * mm
    c.setFont(f, 8.5)
    c.drawString(m, y, t["dibujo"])
    y -= 8 * mm
    c.setFillColor(HexColor("#111111"))
    for n, linea in zip(t["numeros"], t["pasos"]):
        if n is not None:
            c.setFillColor(ROJO)
            c.circle(m + 2.6 * mm, y + 1.2 * mm, 2.6 * mm, fill=1, stroke=0)
            c.setFillColor(white)
            c.setFont(fb, 8.5)
            c.drawCentredString(m + 2.6 * mm, y + 0.2 * mm, str(n))
        c.setFillColor(HexColor("#111111"))
        c.setFont(f, 9.5)
        c.drawString(m + 8 * mm, y, linea)
        y -= 6 * mm if n is not None else 6.5 * mm
    y -= 3 * mm
    c.setFillColor(HexColor("#fff4e0"))
    c.setStrokeColor(HexColor("#e0a040"))
    c.rect(m, y - 9 * mm, W - 2 * m, 12 * mm, fill=1, stroke=1)
    c.setFillColor(HexColor("#7a4100"))
    c.setFont(f, 9)
    texto = t["negro"]
    corte = texto.rfind(" ", 0, 118)
    c.drawString(m + 3 * mm, y - 1.2 * mm, texto[:corte])
    c.drawString(m + 3 * mm, y - 6 * mm, texto[corte + 1:])
    c.setFont(f, 8)
    c.setFillColor(GRIS)
    c.drawCentredString(W / 2, 7 * mm, t["pie"] % zynq_boot.VERSION_PROGRAMA)


def main():
    salida = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "MSXimusZ_instalacion_ES_EN.pdf")
    f, fb = fuentes()
    c = canvas.Canvas(salida, pagesize=A4)
    c.setTitle("MSXimus Z · Primera instalación / First installation")
    c.setAuthor("MSXimus")
    for lang in ("es", "en"):
        pagina(c, lang, f, fb)
        c.showPage()
    c.save()
    print(salida)


if __name__ == "__main__":
    main()
