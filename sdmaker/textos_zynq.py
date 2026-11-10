"""textos_zynq.py — los textos del programa de la tarjeta de arranque de la MSXimus Z (MSXimusZboot.py), en castellano e
ingles. Se anaden a las tablas de idioma.py con registrar(): asi no tocan textos_es.py / textos_en.py de SD Maker."""
from . import idioma

ES = {
    # zynq_boot.py
    "zb.manifiesto_raro": "el servidor no ha devuelto un manifiesto de actualizaciones de la MSXimus Z",
    "zb.sin_firma": "el manifiesto no lleva firma",
    "zb.firma_mala": "la firma del manifiesto no es válida (no viene de msx.barcelona o está dañado)",
    "zb.otra_placa": "el manifiesto es de otra placa (%s)",
    "zb.en_cache": "%s ya estaba descargado y comprobado",
    "zb.bajando": "Bajando %s: %d %%",
    "zb.cancelado": "cancelado",
    "zb.tamano_raro": "un BOOT.bin de la MSXimus Z mide unos 6 MB, entre 4 KB y 8 MB (este, %d bytes)",
    "zb.no_es_boot": "no es un BOOT.bin de Zynq (le falta la cabecera de arranque)",
    "zb.descarga_mala": "%s no cuadra con el manifiesto (tamaño o SHA-256): bórralo y vuelve a intentarlo",

    # ventana_zynq.py
    "zv.titulo": "MSXimus Z · Tarjeta de arranque (TF1)",
    "zv.intro": "Prepara la microSD con la que la MSXimus Z arranca por primera vez y se instala sola en su memoria "
                "QSPI. La tarjeta se BORRA entera: usa una de 1 GB o más que no tenga nada que quieras guardar.",
    "zv.paso1": "1. La tarjeta",
    "zv.refrescar": "Buscar otra vez",
    "zv.sin_tarjetas": "(no se ve ninguna tarjeta: mete la microSD en el lector y pulsa «Buscar otra vez»)",
    "zv.tarjeta_txt": "%s  ·  %s  ·  %s",
    "zv.paso2": "2. La versión",
    "zv.cargando": "Mirando las versiones publicadas en msx.barcelona…",
    "zv.canal_oficial": "Oficial: %s (%s)",
    "zv.canal_beta": "Beta: %s (%s), para probar",
    "zv.canal_error": "%s: no se puede leer (%s)",
    "zv.oficial": "Oficial",
    "zv.beta": "Beta",
    "zv.propio": "Un BOOT.bin que ya tengo en el ordenador…",
    "zv.propio_elegido": "Un BOOT.bin del ordenador: %s",
    "zv.variante": "Variante:",
    "zv.variante_nota": "Se puede cambiar después desde la propia placa.",
    "zv.notas": "Novedades: %s",
    "zv.paso3": "3. Formato",
    "zv.fat32": "FAT32 (recomendado)",
    "zv.fat16": "FAT16 (tarjetas pequeñas o lectores antiguos)",
    "zv.preparar": "Preparar la tarjeta",
    "zv.imagen": "Guardar como imagen…",
    "zv.como": "¿Cómo se instala?",
    "zv.listo": "Listo.",
    "zv.elige_tarjeta": "Elige primero la tarjeta.",
    "zv.elige_version": "Elige una versión (o un BOOT.bin del ordenador).",
    "zv.admin": "Para escribir la tarjeta hace falta abrir el programa como administrador. ¿Lo vuelvo a abrir así?",
    "zv.borrar_titulo": "Se va a borrar la tarjeta",
    "zv.borrar": "Se BORRARÁ TODO lo que hay en:\n\n%s\n\ny quedará con una partición %s y, en su raíz, el BOOT.bin de "
                 "%s.\n\n¿Seguimos?",
    "zv.fin_ok": "La tarjeta está lista: %s en la raíz, comprobado byte a byte.\n\nSácala con seguridad y sigue los pasos "
                 "de la ventana que se abre ahora.",
    "zv.fin_errores": "La tarjeta se ha escrito, pero al releerla no cuadra:\n%s\n\nPrueba otra vez o con otra tarjeta.",
    "zv.error": "No se ha podido preparar la tarjeta:\n%s",
    "zv.boot_malo": "Ese fichero no sirve: %s",
    "zv.boot_titulo": "Elige el BOOT.bin",
    "zv.boot_tipo": "BOOT.bin de la MSXimus Z",
    "zv.imagen_titulo": "Guardar la imagen de la tarjeta",
    "zv.imagen_tipo": "Imagen de tarjeta",
    "zv.imagen_ok": "Imagen guardada: %s\n(se graba con Rufus, balenaEtcher o dd)",
    "zv.esperando_admin": "Esperando la contraseña de administrador…",
    "zv.version_boot": "%s, %s",

    # Pasos de la instalacion
    "zp.titulo": "Cómo se instala la MSXimus Z",
    "zp.antes": "ANTES de dar corriente: SW1 en OFF-OFF\n(arranca de la tarjeta)",
    "zp.despues": "AL ACABAR, sin corriente: SW1 en ON-OFF\n(arranca de la QSPI, para siempre)",
    "zp.dibujo": "Dibujo orientativo: guíate por las letras «ON» y los números impresos en el propio SW1. "
                 "SW1 solo se lee al dar la corriente.",
    "zp.foto_tf1": "La tarjeta va en TF1: mirando la placa por el lado del HDMI, la ranura de su izquierda (en rojo).",
    "zp.pasos": (
        "1.  Placa SIN corriente. La tarjeta de arranque en TF1; la del MSX (SD Maker), si la tienes, en TF2.\n"
        "2.  SW1 en OFF-OFF. HDMI a la pantalla, teclado USB en P3 y, si tienes, el cable de red en J3.\n"
        "3.  Dale corriente: sale el logo y el menú, cargados desde la tarjeta. Todavía no se ha grabado nada.\n"
        "4.  Pulsa F12 y luego U: la página se llama «BOOT.bin de la SD».\n"
        "5.  Pulsa A: enseña la versión de la tarjeta. Pulsa A dos veces seguidas para grabarla en la ranura A.\n"
        "     Tarda alrededor de un minuto. No apagues mientras graba.\n"
        "6.  Cuando ponga «Grabada en la ranura A», quita la corriente y pon SW1 en ON-OFF.\n"
        "7.  Dale corriente: arranca sola de la QSPI. F12 → P prepara TF1 para los perfiles (borra la tarjeta,\n"
        "     el BOOT.bin ya no hace falta) y, con red, F12 → U busca la última versión."),
    "zp.negro": "Si la pantalla se queda negra con SW1 en OFF-OFF: comprueba que la tarjeta está en TF1 (no en TF2) y que "
                "SW1 está bien. Esta tarjeta ya lleva el BOOT.bin con su nombre exacto y en la raíz.",
    "zp.cerrar": "Cerrar",
}

EN = {
    "zb.manifiesto_raro": "the server did not return a MSXimus Z update manifest",
    "zb.sin_firma": "the manifest is not signed",
    "zb.firma_mala": "the manifest signature is not valid (it does not come from msx.barcelona or it is damaged)",
    "zb.otra_placa": "the manifest is for another board (%s)",
    "zb.en_cache": "%s was already downloaded and checked",
    "zb.bajando": "Downloading %s: %d %%",
    "zb.cancelado": "cancelled",
    "zb.tamano_raro": "a MSXimus Z BOOT.bin is about 6 MB, between 4 KB and 8 MB (this one, %d bytes)",
    "zb.no_es_boot": "not a Zynq BOOT.bin (no boot header)",
    "zb.descarga_mala": "%s does not match the manifest (size or SHA-256): delete it and try again",

    "zv.titulo": "MSXimus Z · Boot card (TF1)",
    "zv.intro": "Prepares the microSD card the MSXimus Z boots from the first time, to install itself in its QSPI "
                "memory. The card is ERASED: use one of 1 GB or more with nothing you want to keep.",
    "zv.paso1": "1. The card",
    "zv.refrescar": "Look again",
    "zv.sin_tarjetas": "(no card found: put the microSD in the reader and press «Look again»)",
    "zv.tarjeta_txt": "%s  ·  %s  ·  %s",
    "zv.paso2": "2. The version",
    "zv.cargando": "Looking at the versions published on msx.barcelona…",
    "zv.canal_oficial": "Official: %s (%s)",
    "zv.canal_beta": "Beta: %s (%s), for testing",
    "zv.canal_error": "%s: cannot be read (%s)",
    "zv.oficial": "Official",
    "zv.beta": "Beta",
    "zv.propio": "A BOOT.bin I already have on this computer…",
    "zv.propio_elegido": "A BOOT.bin from this computer: %s",
    "zv.variante": "Variant:",
    "zv.variante_nota": "It can be changed later from the board itself.",
    "zv.notas": "What's new: %s",
    "zv.paso3": "3. Format",
    "zv.fat32": "FAT32 (recommended)",
    "zv.fat16": "FAT16 (small cards or old readers)",
    "zv.preparar": "Prepare the card",
    "zv.imagen": "Save as image…",
    "zv.como": "How do I install it?",
    "zv.listo": "Ready.",
    "zv.elige_tarjeta": "Choose the card first.",
    "zv.elige_version": "Choose a version (or a BOOT.bin from this computer).",
    "zv.admin": "Writing the card needs the program to run as administrator. Open it again that way?",
    "zv.borrar_titulo": "The card will be erased",
    "zv.borrar": "EVERYTHING will be ERASED on:\n\n%s\n\nIt will get one %s partition with the BOOT.bin of %s in its "
                 "root.\n\nGo ahead?",
    "zv.fin_ok": "The card is ready: %s in the root, checked byte by byte.\n\nEject it safely and follow the steps in the "
                 "window that opens now.",
    "zv.fin_errores": "The card was written, but it does not read back right:\n%s\n\nTry again or use another card.",
    "zv.error": "The card could not be prepared:\n%s",
    "zv.boot_malo": "That file is no good: %s",
    "zv.boot_titulo": "Choose the BOOT.bin",
    "zv.boot_tipo": "MSXimus Z BOOT.bin",
    "zv.imagen_titulo": "Save the card image",
    "zv.imagen_tipo": "Card image",
    "zv.imagen_ok": "Image saved: %s\n(write it with Rufus, balenaEtcher or dd)",
    "zv.esperando_admin": "Waiting for the administrator password…",
    "zv.version_boot": "%s, %s",

    "zp.titulo": "How to install the MSXimus Z",
    "zp.antes": "BEFORE powering on: SW1 at OFF-OFF\n(boots from the card)",
    "zp.despues": "WHEN DONE, powered off: SW1 at ON-OFF\n(boots from the QSPI, from then on)",
    "zp.dibujo": "Illustrative drawing: go by the «ON» letters and the numbers printed on SW1 itself. "
                 "SW1 is only read at power on.",
    "zp.foto_tf1": "The card goes in TF1: looking at the board from the HDMI side, the slot on its left (in red).",
    "zp.pasos": (
        "1.  Board powered OFF. The boot card in TF1; the MSX card (SD Maker), if you have it, in TF2.\n"
        "2.  SW1 at OFF-OFF. HDMI to the screen, USB keyboard on P3 and, if you have it, the network cable on J3.\n"
        "3.  Power on: the logo and the menu show up, loaded from the card. Nothing has been written yet.\n"
        "4.  Press F12 and then U: the page is the one for the BOOT.bin on the SD card.\n"
        "5.  Press A: it shows the version on the card. Press A twice in a row to write it to slot A.\n"
        "     It takes about a minute. Do not power off while it writes.\n"
        "6.  When it says it is written to slot A, power off and set SW1 to ON-OFF.\n"
        "7.  Power on: it boots by itself from the QSPI. F12 → P prepares TF1 for the profiles (it erases the card,\n"
        "     the BOOT.bin is no longer needed) and, with a network, F12 → U looks for the latest version."),
    "zp.negro": "If the screen stays black with SW1 at OFF-OFF: check that the card is in TF1 (not TF2) and SW1. This "
                "card already has the BOOT.bin with its exact name, in the root.",
    "zp.cerrar": "Close",
}


def registrar():
    idioma.TABLAS["es"].update(ES)
    idioma.TABLAS["en"].update(EN)
