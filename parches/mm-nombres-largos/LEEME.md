# Multi Mente con nombres largos en «File info»

`sd/base/MM/MM.COM` lleva este parche: en el recuadro **File info**, el campo **Name:**
enseña el nombre largo (VFAT) del fichero o carpeta que está bajo el cursor, el que se ve
en Windows, en vez del 8.3 (`Metal Gear 2 - Solid Snake (1990)(Konami).rom` en vez de
`METALG~1.ROM`). La lista de ficheros sigue con los nombres 8.3.

Multi Mente 2.07 (MOGU) solo se publicó en binario: el parche está hecho a mano sobre el
desensamblado. `mmlfn.asm` es el código nuevo y `parchear.py` lo ensambla con
[pasmo](http://pasmo.speccy.org/) y lo aplica al MM.COM original:

```bash
git show bd3beb9:sd/base/MM/MM.COM > MM.COM.original
python parchear.py MM.COM.original MM.COM
```

El original tiene 23.539 bytes (sha1 `db7316e2…`); el parcheado, 24.221 (sha1 `f5842063…`).

## Cómo se ve

- Si el nombre largo cabe en el campo (12 caracteres), se pinta en su sitio.
- Si es más largo, ocupa toda la fila hasta el recuadro de `Wild:` (31 caracteres) y tapa
  la fecha de ese fichero; `Size:` y `Time:` siguen en la fila de abajo. Al pasar a un
  fichero de nombre corto vuelve a salir `Date:`.
- Si pasa de 31: los 20 primeros, `...` y los 8 últimos (para que se vea la extensión):
  `Nombre_muy_largo_de_...s_xx.dsk`.
- Si el fichero no tiene nombre largo (o su nombre largo no cuadra), se ve el 8.3 de siempre.

## Limitaciones

- **Solo para ver.** Copiar, mover, renombrar y borrar siguen igual: Multi Mente trabaja con
  el 8.3 y lo que copia o crea no lleva nombre largo. Si se renombra un fichero desde
  MSX-DOS, sus entradas LFN viejas se quedan en el disco; el parche comprueba el checksum
  y no las enseña (sale el 8.3 nuevo).
- **Caracteres:** ASCII. Las letras latinas acentuadas salen sin acento (`Música española ñ`
  → `Musica espanola n`), porque la fuente de MM es la de la BIOS (japonesa en muchas
  máquinas). Lo demás (japonés, símbolos) sale como `?`.
- **Necesita Nextor 2.1 o 3.0** (usa `_RDDRV`, `_GETCLUS` y lo que guarda el FIB de
  Nextor). Con otro DOS, o si algo falla, se ve el 8.3. Solo FAT16 y FAT12: Nextor no lee
  FAT32.
- **Algo más lento:** cada vez que se mueve el cursor se leen uno o dos sectores del
  directorio. En openMSX (Sunrise IDE) pintar el nombre pasa de ~13 ms a 35-65 ms: unos
  20 ms son las lecturas y el resto pintar más letras. Si la cadena LFN del fichero empieza
  en el cluster anterior se recorre el directorio desde el principio (0,1-0,5 s en un
  directorio de 120 nombres largos con clusters de 2 KB; con los de 32 KB de las FAT16 de
  2 GB pasa muy poco).
- Cada `_RDDRV` hace que Nextor vacíe e invalide sus búferes de esa unidad (es como está
  hecho Nextor); no se pierde nada, solo que el siguiente acceso al disco los vuelve a leer.

## Cómo funciona

Al listar un directorio, MM guarda cada entrada en un registro de 32 bytes con el mismo
formato que una entrada FAT (5FFFh + 32·n), pero no usa los bytes 12-21 (comprobado con
puntos de vigilancia en openMSX al listar, ordenar, marcar, árbol, copiar y borrar).

1. **Al listar** (`3E88h`, la rutina que pasa el FIB al registro): se guarda en el registro
   la marca `A5h` y la posición de la entrada que da el FIB de Nextor (FIB+45..49: entradas
   y sectores que quedan, y el sector de 24 bits; mismo formato en Nextor 2.1.4 y 3.0.0).
2. **Al pintar File info** (`34D5h`): con `_RDDRV` se leen ese sector y el anterior (si está
   en el mismo cluster), se busca la entrada 8.3 y se juntan las entradas LFN que la
   preceden si su checksum es el del 8.3. Si la cadena empieza antes, se recorre el
   directorio: `_FFIRST` de `.` da su cluster y `_GETCLUS` la cadena; la raíz, con el
   `_DPARM` que hace MM al leer el directorio.
3. El sector (512 bytes) y el nombre (261) van en la pila, que en MM tiene sitio entre
   CB92h (el final de sus datos) y la cima del TPA; si no hay 773 bytes libres por encima
   de CC00h, se pinta el 8.3.

El código va en memoria que MM no usa:

| Zona | Qué era | Qué va |
| --- | --- | --- |
| `5CF4h-5F9Ch` (+ variables hasta `5FB1h`) | detrás del final de MM.COM, sin usar (5FBFh son las marcas) | casi todo; se añade al fichero |
| `3D07h-3D1Fh`, `3D60h-3DD7h`, `3DDFh-3E02h` | el lector de directorios por sectores de MM (solo FAT12), muerto: `3D5Dh` lo salta con un `JP 3E4Ah` | el gancho del listado, tablas y rutinas pequeñas |

No se tocan `3DDEh` ni `3E3Eh` (MM y MM.EXE los reescriben) ni `3D2Bh`-`3D5Fh` y
`3E03h`-`3E49h` (los llaman overlays de MM.EXE). Los cuatro sitios desviados:

| Dirección | Antes | Ahora |
| --- | --- | --- |
| `3E88h` | `LD DE,C935h` | `JP hookfib` |
| `34C3h` | `CALL 36C4h` | `CALL prep` |
| `34D5h` | `CALL 13BAh` | `CALL name` |
| `3547h` | `CALL 35C3h` | `CALL mydate` |

## Pruebas (openMSX, Philips NMS 8245 con 4 MB y Sunrise IDE)

Con Nextor 2.1.4 y con Nextor 3.0.0-beta2 (núcleo base de Konamiman con su driver Sunrise
IDE para Nextor 3, montado con N80 y mknexrom), en imágenes hechas con `MSXsdmaker.py
imagen`:

- nombres de 1 a 64 caracteres, con acentos, con mayúsculas y minúsculas, carpetas, la
  raíz y una carpeta de 120 nombres largos en 10 clusters, todo más allá del sector 65535;
- F1 y sus páginas de ayuda, RETURN (`.TXT` → AKID), `$T` con dos ficheros marcados,
  ordenar, árbol, copiar y borrar, y la vuelta a MM tras ejecutar un programa;
- un fichero renombrado con `REN` desde MSX-DOS (sale el 8.3 nuevo) y `fsck.fat` de la
  partición después de copiar con MM: sin errores.
