# Ficheros para la tarjeta SD

Se copia a la raíz de la SD: **el contenido de `base/`** + **el
contenido de la carpeta de la versión de Nextor que lleve el pack flasheado**.

```
sd/
├── base/     ← común a todo (va siempre)
│   ├── AUTOEXEC.BAT         monta C:/D:/E: con MAPDRV y arma el PATH
│   ├── UTIL/                135 utilidades (está en el PATH)
│   ├── WIFI/                cliente WiFi/UNAPI (está en el PATH)
│   ├── musica/              MWMPLAY y VGMPLAY (está en el PATH) y los editores de OPL4: mbwave/ (MoonBlaster
│   │                        Wave 1.17) y mbfm/ (MoonBlaster for MoonSound FM 1.03A, del MBFM.zip, 12 ficheros)
│   │   └── roboplay/        RoboPlay 2.1 de ToriHino (también en el PATH): los 39 ficheros de dsk/ del commit
│   │                        609add63 de gitlab.com/torihino/roboplay, iguales byte a byte
│   ├── FHUNT/   ← 🚨 VACÍA A PROPÓSITO: NO BORRAR
│   └── TMP/     ← 🚨 VACÍA A PROPÓSITO: NO BORRAR
├── nextor-2.1.4/            NEXTOR.SYS + COMMAND2.COM + MSXDOS2.SYS…
├── nextor-3.0.0-beta2/      NEXTOR.SYS + COMMAND3.COM + bin/ (las 25 herramientas oficiales)
└── extras/                  SOFARUN, hub, mapper, IA, indev.com (de la SD de la MSX Pico, 30/09) y FPGA
                             (MXUPDATE.COM 1.2 del MSXimus, md5 de9757601a04: se actualiza solo desde msx.barcelona;
                             MTVOL.COM 1.0.2 de MoonTANG, md5 10a0e6cde1b7: volumen FM/Wave del OPL4, fuente tools/msx/mtvol.asm de MoonTANG)
```

**Más fácil: MSX SD Maker** (este repositorio) particiona, formatea y copia todo esto a una tarjeta, con el
`AUTOEXEC.BAT` hecho según lo que se elija. Ver [`../LEEME.md`](../LEEME.md).

## 🚨 FHUNT y TMP tienen que existir aunque estén vacías

El menú **ya no puede crear carpetas**: se le quitó esa capacidad el 01/09/2026
porque crear entradas de directorio y asignar clústeres era lo que corrompía
tarjetas. Si `FHUNT` no existe, las descargas del File-Hunter fallan. Se crea
desde DOS con `MKDIR`, o dejándola aquí.

## Por qué las herramientas de Nextor están "duplicadas" (y no lo están)

`UTIL/` lleva **20 herramientas de Nextor en la versión de la era Nextor 2**, que
es la que corresponde al `nextor-2.1.4` que arranca hoy. `nextor-3.0.0-beta2/bin/`
lleva las **oficiales de Nextor 3** (las 25 del `tools.zip` de la beta 2: v1.1, más EMUFILE 3.0,
NEXBOOT 3.0, XDIR 1.2 y DEVINFO 1.3).

**No mezclar las dos versiones en la misma SD.** No es redundancia: es
emparejamiento de versión. Ejemplo real de por qué importa — `MAPDRV` cambió:

| | Uso |
|---|---|
| vieja (UTIL) | `<drive>: <partition> [<device>[-<LUN>] [<slot>]]` |
| v1.3 (tools/) | `<drive>: <partition> [<device>] [<slot>[:<seg>]]` |

Desapareció el LUN y apareció el segmento (para drivers en RAM). Las órdenes del
`AUTOEXEC.BAT` actual (`mapdrv c: 2 1 0`) se interpretan igual en las dos, así
que hoy no rompe — pero no hay que dar por hecho que todas se comportan igual.

Por eso se eliminó `nextor-2.1.4/tools/`: duplicaba en versión NUEVA herramientas
que `UTIL/` ya tenía en la versión vieja, y cuál se ejecutaba dependía del orden
del PATH. `CHKDSK.COM` sí se conservó (no estaba en `UTIL/`).

## Al probar Nextor 3

1. Copiar `base/` + `nextor-3.0.0-beta2/` a la raíz de la SD.
2. **Primero `DRVTEST.COM 3-2`** 🚨 con el subslot: el Nextor vive en el slot
   **3-2**, que es EXPANDIDO. `drvtest 1|2|3` a secas responde *"Invalid disk
   driver"*. Mapa del slot 3: 3-0 mapper de RAM · 3-1 sub-ROM/logo/menú ·
   **3-2 Nextor + registros del lector SD** · 3-3 megaram.
   Luego `drvtest 3-2 -d 1` para las consultas de dispositivo. Mismo formato en
   `devinfo 3-2` y `drvinfo 3-2`; `drivers` no lleva slot.

3. Luego `DRIVERS.COM`, `DEVINFO.COM`, y ya `_FDISK` / `CHKDSK` / copias grandes.

🚨 Nextor 3 **desactiva al arrancar cualquier kernel Nextor 2** de la máquina, y
con nuestro driver **no se puede cambiar la SD en caliente**.

## Pendiente de decidir

- **`SFTP.COM` está dos veces y son distintos**: `UTIL/` (24.239 B) y `WIFI/`
  (13.704 B). Ambas carpetas están en el PATH, así que se ejecuta la que primero
  aparezca. Conviene quedarse con una.
- `SFTP.TXT` sí es idéntico en las dos (duplicado inofensivo).
- `COMMAND2.COM` está en `UTIL/` y en `nextor-2.1.4/`: es correcto, cumplen
  papeles distintos (uno en el PATH, otro como fichero de sistema de la raíz).

## 🚨 DRVTEST no se puede redirigir a la SD

`drvtest 3-2 -d 1 > info.txt` falla con *"Disk error writing drive A"*. **No es un
bug del driver** (comprobado 02/09: `copy con`, `dir > x.txt` y crear directorios
funcionan): DRVTEST llama a las rutinas del driver **directamente**, conmutando
la página 1 al slot 3-2, y nuestros registros del lector SD están **mapeados en
memoria en esa misma página**. Si DOS vuelca el fichero redirigido en ese momento,
reentra en el driver con la ventana SDC abierta.

**Solución: redirigir al disco RAM**, que no toca la tarjeta:
```
ramdisk 256
drvtest 3-2 -d 1 > H:\info.txt
copy H:\info.txt A:```
(el comando es `ramdisk`, no `ralloc`; la letra la dice él al crearlo)

Es el tercer argumento independiente para sacar los registros del SD a **puertos
de E/S** en la 3.5: mata este conflicto, el solape con el kernel de Nextor 3, y
habilita los drivers cargables en RAM.

## `base/WIFI/FH.COM` — File-Hunter Browser

Cliente de DOS para [file-hunter.com](https://file-hunter.com): busca, navega y
**descarga ROM/DSK/CAS/VGM directamente al MSX** por UNAPI TCP/IP. Interfaz de
80 columnas con pestañas y filtro por generación (MSX1/2/2+/turboR).

- **v1.0.4** de [nataliapc/msx_filehunterbrowser](https://github.com/nataliapc/msx_filehunterbrowser), **MIT** (licencia en `FH_LICENSE.TXT`).
- Requiere **MSX2 o superior**, **MSX-DOS 2.x o Nextor**, y un dispositivo de red
  con UNAPI — o sea, el ESP32 del cacharro.
- `WIFI/` ya está en el PATH del `AUTOEXEC.BAT`, así que se lanza con `FH` desde
  cualquier sitio.

Es la alternativa **desde DOS** al File-Hunter que lleva el propio menú de
arranque: el del menú vive en la BIOS y escribe con nuestro driver; este usa
MSX-DOS/Nextor, así que no toca nada de la FAT por su cuenta.

## Criterio de `base/UTIL/` (Albert, 02/09)

**`UTIL/` = solo utilidades genéricas.** Todo lo que dependa del sistema vive en
la carpeta de su versión de Nextor. El 02/09 se movieron allí **21 herramientas**
(CHKDSK, XCOPY, XDIR, MAPDRV, DEVINFO, DRIVERS, NEXBOOT, RALLOC, UNDEL, VSFT,
Z80MODE…) y se quitó `COMMAND2.COM`, que ya está en `nextor-2.1.4/` como fichero
de sistema.

Recuerda: las de `UTIL` eran de la **era Nextor 2** ⇒ están ahora en
`nextor-2.1.4/bin/`. Las de `nextor-3.0.0-beta2/bin/` son las oficiales de Nextor 3,
más nuevas. **No mezclar las dos versiones en la misma tarjeta.**

## Limpieza de `UTIL/` del 02/09: fuera lo de otras máquinas

Venían heredadas de una SD vieja de Flashjacks. **Borradas** (flasheaban hardware
ajeno y no pintaban nada aquí): `PLDFLASH.COM` y `SMXFLASH.COM` (flashean la PLD
de una One Chip MSX / SM-X), `FBL-UPD.COM` (firmware de un cartucho Flashjacks),
`SDBIOS.BTM` (script del OCM-SDBIOS), `SWAPEIDI.COM` y `FASTSCSI.COM` (Sunrise
IDE / MegaSCSI).

**Movidas a `MSXBOOK-nextor3/sd/`**, que sí es una máquina de la familia OCM:
`VGARATIO.COM`, `SLOTMODE.COM`, `EXTCLOCK.COM`. Y se borraron de aquí
`OCMINFO.COM` y `SETSMART.COM` porque **allí ya había versiones más nuevas**
(SETSMART v1.5 de 2025 del pack OCM-SDBIOS v3.8.1 de KdL, frente a la v1.3 de
2022 que arrastraba esta SD).

Nota: esas herramientas de KdL hablan por los **puertos SWIO del estándar OCM**
(40h-43h), que este RTL también implementa (`switched_io_ports`) — o sea que no
son del todo ajenas. Pero su sitio natural es el Onechipbook.

## Programas que necesita Multi Mente (`MM/`)

Los programas que llaman las teclas (`MM.CFG`, que CS.COM copia en `MM.COM`) y
RETURN (`MMRET.DAT`). El 02/09 faltaban casi todos y se recuperaron de la SD de
Flashjacks:

- **`EDITOR = AKID $F`** ← es lo que corre al pulsar **[E]**. Faltaba `AKID.COM` y
  por eso daba error. Recuperado (24.576 B).
- También se añadieron: `PLAYER`, `CHRIS`, `FDSK`, `MGSDRV`, `FROM`, `EVAFJ`,
  `JACKSBOY`, `JPD`, `MBMPLAY`, `MCDRV`, `MGSC`, `MIDIPLAY`, `MMP`, `MP`, `MSA`,
  `MXPV`, `PCMPLAY`, `PI`, `PT3PLAY`, `TT`.
- Faltaban `CGV` y `NV` (visores de gráficos, tecla [V] con Shift) y `UNZIP2`.
  Desde el 17/10 ya no se usan: SHIFT+V abre con `BLS` y los ZIP van con `SUZ`
  (abajo).

## Configuración de Multi Mente (17/10/2026)

Rehecha con lo que hay en la tarjeta. Cómo lee MM 2.07 sus ficheros se sacó
desensamblando `MM.COM`, `MM.EXE` y `CS.COM` y probándolo en openMSX.

### `MMRET.DAT`: qué hace RETURN con cada fichero

- **Solo cuentan las líneas que empiezan por `.` o `:`**, con el patrón en
  MAYÚSCULAS; manda **la primera** que encaje, y `.???` va la última (el visor).
  Entre patrón y orden, un TAB: lo que va tras un espacio llega al programa.
  Una línea sin orden ejecuta la siguiente (le pasaba al `.RAM` de antes).
- **MM lee 16383 bytes** y lo relee en cada RETURN. Ahora mide 9,1 KB.
- **`$T` y `$M` se expanden sobre el propio fichero**: una línea con `$T`
  tiene que estar más lejos del principio que (marcados × línea expandida).
  Por eso las notas van arriba y las líneas con `$T` al final.
- **Las variables (`%MM%`...) se expanden** al ejecutar. `$d` es la unidad de
  `TEMP`, no el arranque.
- Lleva unas notas (en inglés) con lo que necesita cada tipo de fichero.

Lo que cambió:

- **`.VGM`/`.VGZ` → `VGMPLAY $T`** (lo que recomienda Grauw: con varios
  marcados, los toca seguidos). MM buscaba `VGMPLAY` en el PATH y salía el
  **1.2 parcheado de `SOFARUN\`** (comprobado en openMSX). Ahora `musica` va
  delante de `SOFARUN` en el PATH (`contenido.grupos_en_path`, y también en
  `base/AUTOEXEC.BAT`) y sale el **1.4 (dev)**; sin `musica` marcado y con
  SofaRun (lo de un OCM por defecto), sigue el 1.2, que también lee VGZ.
  `UTIL` no se adelanta a `SOFARUN`: cambiaría el AKID (el de SofaRun es
  el 1.02, más nuevo). `UTIL\VGMPLAY.COM`, que era una compilación no oficial
  marcada «1.4», es ahora ese mismo 1.4 (dev). El de SofaRun se queda: SR.COM
  lo llama por su ruta con `/Q`, que el 1.4 no admite.
- **`.ROM` → `SROM`** y **`.DSK` → `SRI`** (como los alias del AUTOEXEC):
  `FROM` y `FDSK` son de Flashjacks. `.DSK` con `$C`: con `$M` y ficheros
  marcados de antes, SRI arrancaría con lo que no es.
- **`.ZIP` → `SUZ L`** (lista; `UNZIP2` no está y el `UNZIP` de UTIL no sabe
  Deflate), **`.LZH` → `PMEXT`** (no hay `LHEXT`).
- **Nuevas**: `.ARC .ARK .ARJ .GIF .BMP .GRA .MIG .SG .EMU .UPD .INI .ASC`,
  las pantallas `.SC5-.SC8 .SCA-.SCC .SR5-.SR8 .SRA .SRB` (antes `.SC?` y
  `.SR?` cogían también `.SRM`, `.SCR`...), y por nombre (al visor):
  `:AUTOEXEC.BAT` (desde MM no tiene `%1`), `:XSYS.BAT`, `:SETALIAS.BAT`,
  `:MBFM.CFG` y `:MBWAVE.CFG` (binarios) y `:EMUDSK.ROM`.
- **Fuera** por falta de programa o de datos: `.BGM` (falta `KINROU5.DRV`),
  `.0??`-`.9??` y `.FD?` (FDSK; además cogían los `MBFM.00x`), `.EVA`
  (`CIRCUIT.SCC`), `.GB?`, `.MDX`/`.PDX` (MXPV solo muestra parámetros),
  `.MIO` (sin MIODRV), `.MIF` (`MV`), `.PAC` (`PACS`), `.RAM`, `.GRP` (BLS no
  lo lee), `.PCK` y `.LDR` (los cargadores de cinta de SofaRun).
- **`.???` → visor** (`$V`) en vez de `AKID`: los binarios desconocidos no se
  abren en el editor. [E] sigue editando.
- **`.MFM` y `.MWM` → `ROBOPLAY $T`** (RoboPlay 2.1, en `musica\roboplay`).
  Las canciones de MoonBlaster FM no las tocaba nada (el editor no las abre
  desde la línea de órdenes). RoboPlay toca en el OPL4 las FM y las Wave en
  modo USER y EDIT, y carga solo el wavekit que nombra la canción (o
  `CANCION.MWK`) de su carpeta; MWMPLAY solo leía USER y había que marcar
  canción y wavekit. `.MWK` sigue con `MWMPLAY $M$K`, para una canción USER
  con un wavekit de otro nombre (los dos marcados, cursor en el `.MWK`).
  Probado en openMSX (NMS 8245 con 512 KB, MoonSound, Nextor 2.1.4 por IDE):
  `.MFM` USER y EDIT guardados con MBFM (UMFDEMO.MBM importado), `.MWM` con
  y sin wavekit, el `.MWK` con MWMPLAY, y el sonido grabado. ESC acaba una
  canción y pasa a la siguiente marcada; CTRL+STOP entre dos da «Terminate
  batch file» y acaba la lista.
- **RoboPlay va en el PATH** (`musica\roboplay`, detrás de `musica`) porque
  busca sus `.PLY`, `WAVES.DAT`, `YRW801.DAT` y `STANDARD.BNK` junto a
  `ROBOPLAY.COM` (por la variable `PROGRAM`) y porque la lista de marcados
  de MM es un batch en lo alto de la TPA: «`ROBOPLAY CANCION.MFM`» y CR LF
  por canción, más unos 66 bytes. RoboPlay usa 0xC000-0xD3FF (búfer de
  lectura y nombres) y su pila: con la TPA en 0xD306 pisa la lista y vuelve
  al DOS sin tocar nada. Medido: MM deja la TPA en 0xD706; 30 canciones
  marcadas (nombres de 7 caracteres) la bajan a 0xD406 y suenan las 30; 39
  la bajan a 0xD306 y fallan. La lista tiene que quedar por debajo de 768
  bytes: con nombres 8.3 enteros (23 bytes por canción) caben 30 por RETURN
  (con `%MM%\..\MUSICA\ROBOPLAY\ROBOPLAY $T`, la primera prueba, fallaban ya
  20). Con 8 particiones la TPA es la misma. La línea del PATH pasa de 89 a
  108 caracteres con todo marcado y en openMSX entra entera (COMMAND2 lee
  hasta 127).
- **Más formatos con `ROBOPLAY $T`**: `.MID`; la música de AdLib de PC
  (`.RAD .DRO .D00 .HSC .AMD .SA2 .SOP .ROL .IMS .IMF .RAW`, y `.WLF` con
  `ROBOPLAY IMF.PLY $T`: RoboPlay elige el `.PLY` por la extensión y no hay
  `WLF.PLY`; `IMF.PLY` toca los `.WLF` a 700 Hz); `.PRO` (Pro-Tracker de
  MSX-MUSIC, pasado al FM del OPL4); y `.SBM` y `.SNG` (SCC Blaffer NT y SCC
  Musixx). Van al final, antes de `.???`.
  - `.MID` suena en el OPL4 con la ROM de ondas YRW801, que el MSXimus tiene
    si `yrw801.bin` está grabada en la flash. MIDIPLAY solo servía con un
    MIDI-PAC. Su línea pasa detrás de la de RoboPlay: sin `musica`,
    `ajustar_mmret` quita la de RoboPlay y manda MIDIPLAY (y sin `UTIL`, el
    visor).
  - `.RAW` es genérico, pero `RAW.PLY` mira la firma `RAWADATA` (Rdos): un
    `.RAW` que no lo es da «Not a valid file» y se vuelve a MM al momento
    (probado). `SNG.PLY` no mira nada (leído en `sng.c`): un `.SNG` que no
    sea de SCC Musixx sonaría a ruido hasta ESC.
  - `.SBM` y `.SNG` necesitan un SCC en un slot: en el MSXimus, Ajustes →
    Slot 1 = 2º SCC (el del cartucho emulado solo está al lanzar una ROM).
    Sin SCC, el SBM solo toca la batería del PSG.
  - Lo que tarda en cargar a 3,58 MHz: un `.ROL` hasta un minuto (busca cada
    instrumento en `STANDARD.BNK`), un `.AMD` empaquetado 26 s, un `.IMS` 16
    s; los demás, de 3 a 7 s. Para los ROL, RoboPlay 2.1 solo lee el
    `STANDARD.BNK` de su carpeta (en `rol.c` la búsqueda del `.BNK` de la
    canción está comentada): las que traen banco propio suenan a medias o
    mudas (JAM-YS2.ROL, que trae varios instrumentos que no están en el
    banco, no suena; JAM-M1.ROL sí). Los IMS usan `CANCION.BNK` y, si no está,
    `STANDARD.BNK`.
  - Probado en openMSX como los MFM (con expansor de slots y SCC para SBM y
    SNG): RETURN desde MM sobre una canción real de cada tipo, el audio
    grabado con `record start -audioonly` y ESC de vuelta a MM. RAD v1, DRO
    v2, D00 (19 subcanciones: izquierda y derecha), HSC, AMD empaquetado,
    SA2 v9, SOP, ROL, IMS con su BNK, IMF tipo 0, WLF (IMF tipo 1), RAW, MID
    (formato 0), PRO, SBM con su kit `.SBK` y SNG. Las canciones salieron de
    una SD de MSXBOOK (carpeta `ROBOMUSI`), de la SD de Flashjacks y (HSC,
    AMD e IMS) de las pruebas de AdPlug; no van en la tarjeta.
  - A mano: un `.MBM` suena en el OPL4 con `ROBOPLAY CANCION.MBM` (unos
    27 s para cargar los samples del `.MBK`). El `.MUS` de FAC SoundTracker
    va ya con RETURN (MUSPLAY, abajo). `ROBOPLAY PRO_ORG.PLY CANCION.PRO`
    toca un PRO en el MSX-MUSIC si es interno (en un FS-A1WSX sí; con un
    FM-PAC en cartucho no sonó).
  - Siguen igual: `.MBM` con MBMPLAY (el MSXimus tiene MSX-AUDIO y
    MSX-MUSIC, los chips de verdad), `.MOD` con MMP, `.PT3` con PT3PLAY (va
    en cualquier MSX; RoboPlay pide OPL4 para el tiempo) y `.VGM` con
    VGMPLAY. Fuera: `.ASC` (en MSX es BASIC en ASCII; el de RoboPlay es de
    ZX Spectrum), `.MDX`, `.TFC` y `.ZSM` (piden un OPM, el SFG-01/05, que el
    MSXimus no tiene), `.ETC`, `.COP` y `.SAA` (SoundStar, SAA1099), `.ADL`
    (`SSY.PLY` es el de Petscii Robots: los `.ADL` de Westwood no los toca) y
    `CSP.PLY` (el Sidplayer de COMPUTE!, sin fuente en el repositorio).
  - La lista de marcados es la de antes: unas 30 canciones por RETURN. Con
    `.WLF` la línea lleva 8 bytes más: unas 22 con nombres 8.3 enteros
    (cuenta hecha con el mismo límite de 768 bytes, no medida).
- **`.MUS` → `MUSPLAY $T$K`** (`musica\MUSPLAY.COM`, nuestro; la fuente,
  `fuentes/musplay/musplay.asm`, se ensambla con pasmo). Dos programas usan
  la extensión: MGS (MGSDRV, de Ain), que es MML en texto y lo compila y toca
  MGSC, y FAC SoundTracker, un volcado binario de 0x8000-0xBFFF que toca
  RoboPlay en el OPL4 con sus samples (`.SM1` y `.SM2`). MM elige solo por
  la extensión, así que RETURN lanza MUSPLAY, que lee los 256 primeros
  bytes: si hay un carácter de control que no sea TAB, LF, FF, CR, ^Z ni ESC
  es binario y ejecuta `ROBOPLAY CANCION.MUS`; si no, `MGSC CANCION.MUS -P
  -N`. Lo que siga al nombre va detrás (`MUSPLAY CANCION.MUS /T 60`).
  - No basta con mirar el `0xFE` de la cabecera de BSAVE: en la SD del
    MSXBOOK hay 802 `.MUS` con ella, pero en su carpeta `ROBOMUSI\MUS` hay
    también 18 FAC de 16.391 o 16.512 bytes con esos 7 bytes a cero (los de
    FAC SoundTracker Pro, como `FSTPRO\WARLOCK.MUS`) o con basura (`80 80
    08...`, `FF 0F...`); RoboPlay se los salta sin mirarlos (`mus.c`) y los
    toca bien. Los 5 binarios que no son de FAC (3 con cabecera `MUSC`, un
    programa y un `MENU.MUS`) van también a RoboPlay, que dice «Unknown
    tracker version» y no suena hasta ESC; MGSC con ellos dice «*** End of
    file». Ninguno de los 868 es texto (43 están vacíos): ahí no hay MML de
    MGS.
  - Un batch no sirve: COMMAND2 no tiene `IF` ni forma de leer el fichero.
    MUSPLAY carga el reproductor como COMMAND2: lo busca en la carpeta
    actual y en las del PATH; pone `PROGRAM` con la ruta completa (RoboPlay
    saca de ahí la carpeta de sus `.PLY`) y `PARAMETERS` igual que lo que va
    en 0x81, espacios del principio incluidos (MGSC lee de ahí la línea de
    órdenes); los dos formatos, medidos con un programa de prueba en
    COMMAND2; y lo lee en 0x100 desde un trozo de código copiado en
    `(0006h)` − 0x200 (encima queda sitio para la pila mientras lee), y le
    salta con la pila en `(0006h)` y 0 encima. Los errores (fichero que no
    está, falta de memoria) los explica COMMAND2 (`_TERM`).
  - `$K` como tenía la línea de MGSC: tras la lista pide una tecla antes de
    volver a MM, y así se ven los errores de MGSC. Con `$T`, varios marcados
    de los dos tipos suenan seguidos; ESC acaba cada uno. La línea de la
    lista («`MUSPLAY CANCION.MUS`») es un carácter más corta que la de
    RoboPlay: caben las mismas, unas 30 por RETURN.
  - La línea `.MUS MGSC $C -P -N$K` pasa detrás, al final: sin `musica`,
    `ajustar_mmret` quita la de MUSPLAY y manda MGSC, como antes; sin `UTIL`
    queda MUSPLAY (los FAC suenan; un MGS da «MGSC.COM not found»); sin los
    dos, el visor (comprobado con `contenido.arbol`).
  - Probado en openMSX (NMS 8245 con 512 KB, MoonSound, Nextor 2.1.4 por
    IDE; desde el DOS también con Nextor 3.0 beta 2), con el sonido grabado:
    `POING.MUS` (FAC de Flying Bytes, con cabecera, de la SD del MSXBOOK),
    `WARLOCK.MUS` (FAC SoundTracker Pro, cabecera a cero) y un `.MUS` de MGS
    escrito para la prueba (tres voces de PSG). Desde el DOS (con ruta y con
    `/T 3`) y con RETURN desde MM, uno a uno y los tres marcados en una
    lista: RoboPlay tarda unos 27 s en cargar los samples y MGSC 2 s en
    compilar. Sin `musica` en la tarjeta, RETURN sobre el MGS va a MGSC.

**Al hacer la tarjeta**, `contenido.ajustar_mmret` quita las líneas cuyo
programa no va (por ejemplo, sin `UTIL` en un OCM o sin `bin\` con MSX-DOS;
sin `musica`, las de RoboPlay y MUSPLAY): esos ficheros caen en el visor y no en «***
Unrecognized command». Busca en las carpetas del PATH, `musica\roboplay`
incluida.

### `MM.CFG` y `MM.COM`

MM **no lee `MM.CFG`**: `CS.COM` copia sus valores en huecos de 32 bytes de
`MM.COM` (desde 0x108, `strcpy`, 31 caracteres como mucho). Se cambiaron los
dos a la vez; pasar `CS MM` por el `MM.CFG` nuevo en openMSX da el mismo
`MM.COM`, byte a byte. 🚨 El bloque de líneas con `!` del final de `MM.CFG` es
la tabla de CS: no tocarlo ni guardarlo en UTF-8.

| Clave | Antes | Ahora |
|---|---|---|
| `UNLHA` ([U] en .LZH) | `LHEXT /D$A $T$K` | `PMEXT $Z $A$J$K` |
| `UNARC` | `UNARC /D$A $Z $J$K` (UNARC no tiene `/D`) | `UNARC $Z $A$J$K` |
| `UNZIP` | `UNZIP2 $Z $A$J$K` | `SUZ X $Z$K` (descomprime en la carpeta del ZIP) |
| `PMA` | `PMARC2 ...` | `PMARC $F/$D $M$K` |
| `CHKPMA` (SHIFT+U) | `PMM $T` | `PMEXT $T$k` |
| `PAGER2` (SHIFT+V) | `CGV $C` | `BLS $C` |
| `SCSAVER` | `manbow` (no está) | vacío: el salvapantallas de MM |
| `S_TOOL` (SHIFT+RET) | `MGSDRV /Z /S5` | `MGSDRV /Z %MM%\MM`: MGSDRV vuelve por BASIC y ejecuta lo que sigue a `/Z` (el `/S5` nunca fue la ranura del SCC). `/Z` instala o, si ya está, quita |
| `C_TOOL` (CTRL+RET) | `FROM $C` | `SROM $C` |

Siguen sin programa: `LHA` (`LHPACK`), `ISH` y `UNISH` (`ISH`). `SC_TOOL`
monta el fichero en `G:` con `MAPDRV`: con 6 particiones o más, `G:` es una.

Para `.MUS` (MGSC), el AUTOEXEC pone `set MGSDRV=%1\UTIL\MGSDRV.COM`.

`MM2.COM` es otra compilación (la japonesa del pack RC5) y no casa con este
`MM.EXE`: en openMSX se cuelga al pulsar F1. `MM` arranca `MM.COM`.
