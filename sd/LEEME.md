# Ficheros para la tarjeta SD

Se copia a la raíz de la SD: **el contenido de `base/`** + **el
contenido de la carpeta de la versión de Nextor que lleve el pack flasheado**.

```
sd/
├── base/     ← común a todo (va siempre)
│   ├── AUTOEXEC.BAT         monta C:/D:/E: con MAPDRV y arma el PATH
│   ├── UTIL/                135 utilidades (está en el PATH)
│   ├── WIFI/                cliente WiFi/UNAPI (está en el PATH)
│   ├── FHUNT/   ← 🚨 VACÍA A PROPÓSITO: NO BORRAR
│   └── TMP/     ← 🚨 VACÍA A PROPÓSITO: NO BORRAR
├── nextor-2.1.4/            NEXTOR.SYS + COMMAND2.COM + MSXDOS2.SYS…
└── nextor-3.0.0-beta1/      NEXTOR.SYS + COMMAND3.COM + tools/
```

## 🚨 FHUNT y TMP tienen que existir aunque estén vacías

El menú **ya no puede crear carpetas**: se le quitó esa capacidad el 01/09/2026
porque crear entradas de directorio y asignar clústeres era lo que corrompía
tarjetas. Si `FHUNT` no existe, las descargas del File-Hunter fallan. Se crea
desde DOS con `MKDIR`, o dejándola aquí.

## Por qué las herramientas de Nextor están "duplicadas" (y no lo están)

`UTIL/` lleva **20 herramientas de Nextor en la versión de la era Nextor 2**, que
es la que corresponde al `nextor-2.1.4` que arranca hoy. `nextor-3.0.0-beta1/tools/`
lleva las **oficiales v1.1, más nuevas y conscientes de Nextor 3**.

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

1. Copiar `base/` + `nextor-3.0.0-beta1/` a la raíz de la SD.
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
`nextor-2.1.4/tools/`. Las de `nextor-3.0.0-beta1/tools/` son las oficiales v1.1,
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

`MM.CFG` asocia teclas y extensiones a programas externos. El 02/09 faltaban casi
todos y se recuperaron de la SD de Flashjacks:

- **`EDITOR = AKID $F`** ← es lo que corre al pulsar **[E]**. Faltaba `AKID.COM` y
  por eso daba error. Recuperado (24.576 B).
- También se añadieron: `PLAYER`, `CHRIS`, `FDSK`, `MGSDRV`, `FROM`, `EVAFJ`,
  `JACKSBOY`, `JPD`, `MBMPLAY`, `MCDRV`, `MGSC`, `MIDIPLAY`, `MMP`, `MP`, `MSA`,
  `MXPV`, `PCMPLAY`, `PI`, `PT3PLAY`, `TT`.
- **Siguen faltando** (no están ni en Flashjacks): `CGV` y `NV` (visores de
  gráficos, tecla [V] con Shift) y `UNZIP2`.
