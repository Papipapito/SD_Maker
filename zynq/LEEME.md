# MSXimusZboot: la tarjeta de arranque de la MSXimus Z (beta 0.9)

Programa para Windows y macOS que deja lista la microSD de **TF1** con la que una MSXimus Z nueva arranca por primera vez
y se graba sola en su memoria QSPI (Z1.4.4 o posterior, sin Vivado). Es el paso 1 de la *Puesta en funcionamiento* del
capítulo 02 del manual de la Zynq, hecho de un golpe:

1. **La tarjeta**: lista los lectores SD/MMC y las memorias USB extraíbles (nunca el disco del sistema), como SD Maker.
2. **La versión**: lee los manifiestos de `https://msx.barcelona/wp-content/ota/zynq/` (oficial) y `.../beta/` (los
   mismos que lee la placa), **comprueba su firma** (ECDSA P-256 con la clave pública de las actualizaciones, en Python
   puro) y enseña versión, fecha y novedades. La variante (Nextor 2.1.4 o 3, menús en castellano o inglés) se puede
   cambiar después desde la placa. También vale un `BOOT.bin` del ordenador (se comprueba su cabecera de arranque).
3. **El formato**: una FAT32 desde el sector 8192 (como el formateador de la SD Association) o una FAT16 de hasta 2 GB.

**Preparar la tarjeta** baja el `BOOT.bin` a una caché del usuario y lo comprueba por tamaño y SHA-256 contra el
manifiesto (si ya estaba y cuadra, no lo vuelve a bajar). Después borra la tarjeta, la formatea, copia `BOOT.bin` a la raíz
(entrada 8.3 `BOOT.BIN` con el bit de extensión en minúsculas, como lo deja Windows), escribe la tabla de particiones al
final y lo relee todo con CRC. Al acabar abre la ventana de los pasos en la placa: SW1 en OFF-OFF antes, F12 → U → A,
y SW1 en ON-OFF después, con la foto de la ranura TF1. **Guardar como imagen…** hace lo mismo sobre un `.img` de
1000 MiB (para Rufus, balenaEtcher o `dd`).

Usa los módulos de SD Maker (`dispositivos`, `particiones`, `fatfs`, `verificar`, `idioma`); lo propio está en
`sdmaker/zynq_boot.py` (manifiestos, firma, descarga, la tarjeta y el ayudante de macOS), `sdmaker/ventana_zynq.py` (la
ventana), `sdmaker/textos_zynq.py` (los textos, castellano e inglés) y `MSXimusZboot.py` (la entrada, con línea de
órdenes: `versiones`, `listar`, `imagen F.img`, `tarjeta N --si`).

## Construir

* Windows: `construir_zboot.bat` → `dist\MSXimusZboot.exe` (un solo fichero; pide administrador al abrirse).
* macOS: `construir_zboot_macos.sh` → `dist/MSXimusZboot_macOS_arm64.zip` (pide la contraseña al escribir la tarjeta).
* GitHub Actions: `.github/workflows/construir_zboot.yml` construye los dos cuando cambia en `main` alguno de sus
  ficheros (o a mano, con *Run workflow*).
* Ya construido: va en la [release de la MSXimus Z](https://github.com/Papipapito/MSXimus_Z/releases/latest)
  (`MSXimusZboot.exe` y `MSXimusZboot_macOS_arm64.zip`), junto a los `BOOT.bin`.
* Pruebas: `python -m unittest -v pruebas.probar_zynq_boot` (sin red: firma con el manifiesto real como dato, un
  manifiesto alterado, la cabecera del `BOOT.bin`, y la tarjeta FAT32/FAT16 sobre una imagen releída).

## La guía en PDF

`zynq/guia/hacer_guia.py` → `zynq/guia/MSXimusZ_instalacion_ES_EN.pdf` (una página en castellano y otra en inglés).

## Pendiente

* **Fotos reales de SW1**: si se dejan `zynq/sw1_sd.png` (OFF-OFF) y `zynq/sw1_qspi.png` (ON-OFF), el programa y la
  guía las usan en lugar del dibujo orientativo.
* Probarlo con una tarjeta de verdad en Windows y en macOS (la escritura en macOS es la de SD Maker, con el mismo
  ayudante, pero este programa no se ha ejecutado todavía en un Mac).
