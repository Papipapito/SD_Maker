# SD_Maker — tarjetas SD para los MSX en FPGA

*[English](README.md)*

**MSX SD Maker** prepara tarjetas SD para los MSX en FPGA, **MSXimus** (60K, 138K, Zynq), **MSXnano** y **Goa'uld**, y también para la **MSX Pico** y el **MSXBOOK / OneChipBook / 1chipMSX** (OCM-PLD): las particiona, las formatea, copia el sistema y deja una estructura de programas con su `AUTOEXEC.BAT`.

## Uso

Se reparte en un ZIP para Windows y otro para macOS, en las [releases](https://github.com/Papipapito/SD_Maker/releases/latest): descomprimir y ejecutar `MSXsdmaker.exe` o abrir `MSXsdmaker.app`. Pide permisos de administrador sólo al empezar a escribir la tarjeta entera.

1. **Tarjeta**: solo aparecen lectores SD/MMC y memorias USB extraíbles, nunca el disco del sistema. Se ve el tamaño y las particiones que tiene ahora.
2. **Particiones**:
   - FAT16 de 2 GB o de 4 GB, tantas como quepan (hasta 8, las que ve el menú del MSXimus). Opcionalmente, una última con lo que sobre.
   - O una FAT32 con toda la tarjeta. Nextor 2.1.4 y 3.0 no leen FAT32: sirve para el menú del MSXimus (ROM y DSK) y la MSX Pico, no para arrancar MSX-DOS.
3. **Sistema** en la partición 1: Nextor 2.1.4, Nextor 3.0 beta 2, MSX-DOS básico (`MSXDOS2.SYS` + `COMMAND2.COM`, y los de MSX-DOS 1) o ninguno.
4. **Programas**: SofaRun, Multi Mente, UTIL, WiFi/UNAPI, fuentes, música (los editores MoonBlaster Wave y MoonBlaster FM, de OPL4, RoboPlay y los reproductores de MWM y VGM), HUB, IA, mapper e indev, y las herramientas FPGA (`FPGA\MXUPDATE.COM`, que actualiza el core del MSXimus 60K/138K y del MSXnano, y `FPGA\MTVOL.COM`, que fija el volumen del FM y del Wave del OPL4). Se crean también `FHUNT` y `TMP` (el menú no puede crear carpetas) y `SAVES` y `SETTINGS` de SofaRun.

El `AUTOEXEC.BAT` se genera con lo elegido: `PATH`, alias de SofaRun y una línea `mapdrv c: 2 1 0` por cada partición de más (C: a H:, y la octava en B:, porque MSX-DOS no pasa de H:). Con Nextor 3 (1.1) lleva además las opciones del recuadro: `YENSLASH ON` (la orden interna de COMMAND3.COM desde la beta 2; el `yenslash` a secas solo diría el estado), `SET BUFINSERT=ON`, `SET DIRK=0` y, si se elige, se llama `AUTOEXEC.BTM`. Desde la 1.1, una tarjeta más pequeña que una partición entera (las de "2 GB") lleva una sola con todo, y la imagen pregunta siempre el tamaño (1800M por defecto: cabe en cualquier tarjeta de 2 GB).

Al acabar se relee todo lo escrito: la tabla de particiones y cada fichero por CRC.

**Z80BENCH 1.5.1** (SD Maker 1.5.2): incluye las pruebas de velocidad de memoria con F5 y soporte para Z380.

**Música y Multi Mente** (1.5): MoonBlaster FM, RoboPlay y MUSPLAY en `musica\`, y VGMPlay 1.4 delante del de SofaRun en el PATH. En Multi Mente, RETURN abre cada fichero con su programa (`MM\MMRET.DAT`, del que el programa quita al hacer la tarjeta las líneas cuyo programa no va) y la lista y File info enseñan los nombres largos (`MM.COM` parcheado, en `parches/mm-nombres-largos/`).

**MSXBOOK, OneChipBook y 1chipMSX** (1.4): con el OCM-SDBIOS Pack de KdL, que el usuario deja tal cual (el `.7z`) en la
carpeta `OCM-SDBIOS` junto al programa; no va en este repositorio porque sus BIOS llevan ROMs de sistema con derechos
de terceros. El programa (`sdmaker/ocm.py`) monta las BIOS como `make-sdb.cmd` (MSX2+, turboR, MSX2, MSX1, OCM-PLD
3.0-3.3.3 y vacía; Nextor 2.1.4, Nextor 3 o MegaSDHC; teclado, logo, WiFi y Extra-ROM), una principal y hasta diez de
reserva, y copia sistema, `HELP` y `UTILS` como `sdcreate.cmd`. `OCM-BIOS.DAT` queda el primero de la raíz, en el cluster
2 y contiguo: la IPL del OCM solo lee FAT16 en la primera partición, busca el fichero en la raíz y lo lee de un tirón.

Al abrirse mira en GitHub la última release de SD_Maker (`sdmaker/novedades.py`); si es mayor que la suya, lo dice y ofrece abrir la página de descarga. `python MSXsdmaker.py version` enseña las dos.

🚨 La primera vez, pruébalo con una tarjeta que no tenga nada que importe: borra la tarjeta entera.

## Cómo reparte la tarjeta

Igual que el `FDISK` de Nextor (`kernel/bank5/fdisk2.c`): partición 1 primaria, activa y en el sector 1; las demás lógicas dentro de una extendida, cada una con su EBR. Geometría FAT16 idéntica a la suya (cluster de 2 a 64 KB, como mucho 65.524 clusters, 512 entradas de raíz). La FAT32 empieza en el sector 8192 con los datos alineados a 4 MB.

## Contenido

Sale de `sd/` y va dentro de la aplicación empaquetada: `base/`, `nextor-2.1.4/`, `nextor-3.0.0-beta2/` y `extras/` (SOFARUN, hub, mapper, IA e indev de la SD de la MSX Pico, y FPGA con MXUPDATE.COM y MTVOL.COM); [`sd/LEEME.md`](sd/LEEME.md) explica cada carpeta. Para cambiar lo que se copia, se cambian esas carpetas y se vuelve a construir.

Casi todo lo de `sd/` es de terceros (Nextor, MSX-DOS, SofaRun, Multi Mente, las herramientas UNAPI...) y va bajo la responsabilidad del autor de este proyecto: autores y licencias en [`paquete/LICENCIAS.md`](paquete/LICENCIAS.md), con la licencia de Nextor. El programa es GPL v3 ([`LICENSE`](LICENSE)).

## Construir y probar

```bat
construir_exe.bat
```

En Windows, `construir_exe.bat` hace `dist\MSXsdmaker.exe`. En macOS, `construir_macos.sh` hace `dist/MSXsdmaker.app` y su ZIP. Los dos llevan una copia interna de `sd/` y el paquete añade también la carpeta externa para poder personalizar su contenido.

Línea de órdenes (con Python), útil para probar con imágenes:

```bash
python MSXsdmaker.py imagen prueba.img --tamano 8G --esquema fat16-2g --n 3 --sistema nextor214 --programas todos
```

Pruebas en WSL con herramientas ajenas al programa (`sfdisk`, `fsck.fat`, `mtools`):

```bash
bash pruebas/probar_imagenes.sh
```

Nueve casos: 3×200 MB, 2×2 GB con sobrante y Nextor 3, 2×4 GB con sobrante, FAT32 de 16 GB, MSX-DOS, vacía, 8 particiones, las opciones de Nextor 3 y una imagen de 1800 MB. En cada uno, la partición 1 se extrae y se compara con un árbol hecho con `cp`.

MSXBOOK (con Python de Windows y el pack de KdL):

```bash
python pruebas/probar_ocm.py "RUTA DEL PACK"
```

Con el pack descomprimido compara cada combinación de opciones con todas las BIOS que KdL trae hechas en `sdbios-*`
(las de Nextor y MegaSDHC salen idénticas). Luego hace cinco tarjetas y comprueba cada una con `pruebas/ipl_ocm.py`, que
lee la imagen como la IPL del OCM, además de las BIOS de reserva, el sistema, `HELP` y `UTILS`.

## Paquete para los repos de las máquinas

```bash
python publicar_paquete.py ../MSXimus_zynq ../MSXimus
```

Copia a la carpeta `MSXsdmaker/` de cada repo el `.exe` (antes, `construir_exe.bat`), las instrucciones, `LICENCIAS.md` y las capturas de `paquete/`, y el código en `fuente/`. No hace commit.

## Seguridad en macOS

La aplicación enumera con `diskutil` sólo medios físicos, externos y extraíbles de 512 bytes por sector. Excluye de
forma explícita todos los discos físicos de los que depende el volumen raíz de macOS, y vuelve a comprobar identidad y
tamaño justo antes de borrar. Desmonta la tarjeta, pide autorización de administrador para la operación y escribe por
`/dev/rdiskN`; la ventana nunca se ejecuta como root. La ruta de Windows no cambia. En Linux se pueden crear imágenes,
pero todavía no escribir la tarjeta directamente.
