# Multi Mente con nombres largos

`sd/base/MM/MM.COM` lleva este parche (versión 2). Enseña los nombres largos (VFAT), los
que se ven en Windows, en vez de los 8.3:

- **En la lista**, cada hueco enseña los 12 primeros caracteres del nombre largo. Si el
  nombre sigue, en la posición 13 sale `>` (en las carpetas sigue saliendo la `\`).
- **En File info**, el campo **Name:** enseña el nombre largo del fichero o carpeta del
  cursor (`Metal Gear 2 - Solid Snake (1990)(Konami).rom` en vez de `METALG~1.ROM`).

Multi Mente 2.07 (MOGU) solo se publicó en binario: el parche está hecho a mano sobre el
desensamblado. `mmlfn.asm` es el código nuevo y `parchear.py` lo ensambla con
[pasmo](http://pasmo.speccy.org/) y lo aplica al MM.COM original:

```bash
git show bd3beb9:sd/base/MM/MM.COM > MM.COM.original
python parchear.py MM.COM.original MM.COM
```

El original tiene 23.539 bytes (sha1 `db7316e2…`); el parcheado, 25.673 (sha1 `479dade9…`).

## Cómo se ve

```
antes:    ALESTE~1.ROM    FRAY2-~5.ROM    GOLVEL~5.ROM    KING'S~9.ROM    METALG~5.ROM
ahora:    Aleste 1 - E>   Fray 2 - Ver>   Golvellius 3>   King's Valle>   Metal Gear 3>
```

- En la lista, en todas las vistas (1, 2, 3 y 5 columnas; en las de 1-3, el tamaño y la
  fecha siguen en su sitio). Los que no tienen nombre largo salen en 8.3, como siempre.
- En File info, si el nombre cabe en el campo (12 caracteres), se pinta en su sitio. Si es
  más largo, ocupa toda la fila hasta el recuadro de `Wild:` (31 caracteres) y tapa la
  fecha de ese fichero; `Size:` y `Time:` siguen en la fila de abajo. Si pasa de 31: los
  20 primeros, `...` y los 8 últimos (para que se vea la extensión):
  `Nombre_muy_largo_de_...s_xx.dsk`.

## Limitaciones

- **Solo para ver.** Copiar, mover, renombrar y borrar siguen igual: Multi Mente trabaja con
  el 8.3 y lo que copia o crea no lleva nombre largo. Si se renombra un fichero, sus
  entradas LFN viejas se quedan en el disco; el parche comprueba el checksum y no las enseña
  (sale el 8.3 nuevo).
- **Lo que se ve en la lista es el principio del nombre.** La extensión casi nunca llega a
  verse, y en las colecciones muchos nombres comparten los 12 primeros caracteres (lo que
  cambia es el final: `(JP)`, `[a]`...); File info enseña el nombre entero. El color por
  extensión sigue saliendo del 8.3, y **ordenar ordena por el 8.3** (los `~1`, `~2` no
  siguen el orden de los nombres largos). Sin ordenar se ve el orden del directorio: el
  alfabético de los nombres largos en las tarjetas de MSX SD Maker; en una copia hecha desde
  Windows, el orden en que se copió.
- **Caracteres:** ASCII. Las letras latinas acentuadas salen sin acento (`Música española ñ`
  → `Musica espanola n`), porque la fuente de MM es la de la BIOS (japonesa en muchas
  máquinas). Lo demás (japonés, símbolos) sale como `?`. Lo que busca por nombre sigue
  usando el 8.3.
- **Necesita Nextor 2.1 o 3.0** (usa `_RDDRV`, `_GETCLUS` y lo que guarda el FIB de
  Nextor). Con otro DOS, o si algo falla, se ve el 8.3. Solo FAT16 y FAT12: Nextor no lee
  FAT32.
- **Necesita un segmento del mapper** para la tabla de nombres: se queda el último de los
  que MM reserva para copiar (hasta 64). Si MM consigue menos de dos (un mapper de 128 KB),
  se le deja el suyo y la lista sigue en 8.3; File info lee entonces el nombre del disco en
  cada movimiento del cursor, como en la versión 1.
- **Y sitio en la página 3:** el código va en `CB92h-D0EAh` (MM usa hasta `CB91h` y deja el
  resto para la pila). Si la cima del TPA está por debajo de `D3EBh`, el parche se queda
  como en la versión 1: nombre largo solo en File info. Con Nextor 2.1.4 la cima es `D806h`
  y con Nextor 3.0 `D706h` (NMS 8245 en openMSX).
- **Más de 256 ficheros:** MM se queda como mucho con 257 entradas y la tabla tiene sitio
  para 256: la última sale en 8.3.
- **Algo más lento al entrar en una carpeta:** cada vez que MM la lista (al entrar, al
  volver de un programa, después de copiar o borrar...) se lee entero su directorio. En
  openMSX (Sunrise IDE, Nextor 2.1.4), una carpeta de 200 ficheros con nombres de 32 a 53
  caracteres (912 entradas) tarda **0,86 s más** (listar 3,2 s y pintar 1,6 s: +18 %): 0,25 s
  leyendo de 8 en 8 sectores, 0,1 s de interrupciones y el resto juntando y convirtiendo los
  9.230 caracteres; con Nextor 3.0, 0,9 s. Una de 17 ficheros, 0,1 s más; la raíz, 0,05 s.
  A cambio, mover el cursor no lee el disco.
- Cada `_RDDRV` hace que Nextor vacíe e invalide sus búferes de esa unidad (es como está
  hecho Nextor); no se pierde nada, solo que el siguiente acceso al disco los vuelve a leer.
- Si el disco da un error mientras se leen los nombres, se ignora y la lista sigue en 8.3
  (el error de verdad ya lo habría dado MM al listar). Si Nextor lo reintenta y se repite,
  sale el diálogo de MM; con Abort se deja todo como estaba y sigue lo de MM, como si el
  error hubiera salido al listar. Sin tabla, File info lee el disco
  como en la versión 1: si el medio falla, el diálogo de error de MM puede salir al mover el
  cursor. Con Abort se vuelve bien; con Retry, el nombre puede salir con el color del
  diálogo hasta el siguiente movimiento.

## Cómo funciona

Al listar un directorio, MM guarda cada entrada en un registro de 32 bytes con el mismo
formato que una entrada FAT (`5FFFh + 32·n`, en el orden del directorio), y no usa los
bytes 12-21 (comprobado con puntos de vigilancia en openMSX al listar, ordenar, marcar,
árbol, copiar y borrar).

1. **Al arrancar** (`0100h`): el código de la página 3 va en MM.COM detrás de lo de la
   versión 1. Al cargar cae en `5FBFh+`, donde MM pone luego sus marcas y sus registros; el
   arranque lo copia a `CB92h` antes de saltar a MM. Si no cabe, deja como en la versión 1
   los sitios que llaman a la página 3.
2. **El segmento** (`586Fh`): cuando MM acaba la lista de segmentos que se queda para copiar
   (`C831h`, acabada en `FFh`), se le quita el último. Pedirlo antes no vale: MM hace
   `_FORK` al empezar (`5783h`) y lo pedido antes de eso no se libera con el `_JOIN` de la
   vuelta de un programa (se perdía un segmento en cada vuelta). Ahí mismo se hace en el
   segmento la tabla para convertir los caracteres.
3. **Al listar:** `3E4Ah` marca la tabla como no válida; `3E88h` (de la versión 1) guarda en
   cada registro la marca `A5h` y la posición de la entrada que da el FIB de Nextor.
4. **Al acabar el listado** (`3E82h`), la pasada por el directorio, con el segmento en la
   página 2. Solo en el listado de siempre (el que se llama desde `07ABh`, al entrar en una
   carpeta y al volver a ella): ahí se sabe qué rutina de abort tiene puesta MM. Los otros
   (como `1AFFh`) vuelven a listar luego por `07ABh`. La pasada saca primero con
   `_GETCLUS` la cadena de clusters (tras cada `_RDDRV` Nextor vuelve a leer la FAT: así se
   lee una vez) y lee el directorio con `_RDDRV` de 8 en 8 sectores, sin pasar de un
   cluster. El primer cluster de una carpeta es el del registro de
   `.`; si el patrón del listado lo ha dejado fuera, el de `_FFIRST "."`; la raíz, con el
   `_DPARM` que hace MM. Junta las entradas LFN de cada 8.3 (comprobando orden y checksum) y
   la casa por el nombre con el registro que toca, porque los dos van en el mismo orden; si
   no es ese, mira los 4 siguientes (los que se salta se quedan sin nombre largo). Para cada
   registro, la tabla guarda el checksum de su 8.3 y el nombre ya como se pinta (hasta 31
   caracteres).
5. **La entrada de la tabla va en el propio registro** (byte 18, y la marca `A5h` en el 19):
   MM mueve los registros enteros al ordenar (las carpetas primero), y al borrar no vuelve
   a listar; la entrada se mueve con el registro.
6. **Al pintar** un elemento de la lista (`33BFh`, la llamada a `1376h`) y en File info
   (`34D5h`) se copia la entrada del segmento (se pone en la página 2 solo para eso). Si el
   checksum no es el del 8.3 del registro (cambiado sin volver a listar), la lista pinta el
   8.3 y File info lee el disco como en la versión 1: ese sector y el anterior, juntando las
   entradas LFN que preceden a la 8.3, o recorriendo el directorio.

Durante la pasada hay una rutina propia de errores de disco (`_DEFER`) y otra de abort
(`_DEFAB`). El primer error se ignora y la pasada se abandona; si Nextor lo reintenta, sale
el diálogo de MM con la página 2 del TPA, y con Retry se vuelve a leer al segmento. Si se
aborta (Abort en el diálogo; CTRL+STOP no corta `_RDDRV` ni `_GETCLUS`), se reponen la
página 2, las dos rutinas de MM y el DTA, y se sigue con la de abort de MM (`056Ah`). Con
la pila en la página 2 (alguna rutina de MM la pone ahí) no se cambia el segmento.

| Zona | Qué era | Qué va |
| --- | --- | --- |
| `3D07h-3D2Ah`, `3D60h-3DDDh`, `3DDFh-3E01h` | el lector de directorios por sectores de MM (solo FAT12), muerto: `3D5Dh` lo salta con un `JP 3E4Ah` | de la versión 1: el gancho del listado, tablas, rutinas pequeñas y las variables de un byte |
| `5CF4h-5FAEh` (+ variables hasta `5FBCh`) | detrás del final de MM.COM, sin usar | File info (versión 1); se añade al fichero |
| `5FBFh-600Fh` del fichero | lo pisan luego las marcas y los registros de MM | el arranque |
| `CB92h-D0EAh` | la pila de MM, que no baja de `D3xxh` | la pasada, la lista y la tabla (se copia del fichero) |
| un segmento del mapper | el último de los que MM se queda para copiar | la tabla (`8000h`, 256 × 32), el nombre que se junta, la conversión de caracteres, los clusters de la carpeta y 8 sectores |

No se tocan `3DDEh` ni `3E3Eh` (MM y MM.EXE los reescriben) ni `3D2Bh`-`3D5Fh` y
`3E03h`-`3E49h` (los llaman overlays de MM.EXE). Los sitios desviados:

| Dirección | Antes | Ahora |
| --- | --- | --- |
| `0100h` | `JP 5CC4h` | `JP start` |
| `586Fh` | `LD (HL),FFh` / `LD A,(F24Fh)` | `CALL takeseg` / `NOP` / `NOP` |
| `3E4Ah` | `LD HL,5FFFh` | `CALL lstart` |
| `3E88h` | `LD DE,C935h` | `JP hookfib` |
| `3E82h` | `LD HL,(3E8Ch)` | `JP pass` |
| `33BFh` | `CALL 1376h` | `CALL lstname` |
| `34C3h` | `CALL 36C4h` | `CALL prep` |
| `34D5h` | `CALL 13BAh` | `CALL tname` |
| `3547h` | `CALL 35C3h` | `CALL mydate` |

## Pruebas (openMSX, Philips NMS 8245 con 4 MB y Sunrise IDE)

Con Nextor 2.1.4 y con Nextor 3.0.0-beta2 (núcleo base de Konamiman con su driver Sunrise
IDE para Nextor 3, montado con N80 y mknexrom), en imágenes hechas con `MSXsdmaker.py
imagen` (FAT16 de 256 MB, clusters de 4 KB):

- una carpeta de 200 nombres de 32-53 caracteres, otra de 300 (MM se queda 257), la raíz
  (con la etiqueta de volumen) y una de casos raros: nombres de 7, 12, 13, 31, 32, 204 y 255
  caracteres, con acentos, japonés, `a.txt` en minúsculas (8.3 con los bits de NT, sin
  nombre largo), `Telnet.com`, carpetas con y sin nombre largo;
- las vistas de 1, 2, 3 y 5 columnas, File info en cada elemento, marcar, ordenar (las
  carpetas primero: MM mueve los registros), renombrar, borrar (MM no vuelve a listar),
  copiar, un listado con un patrón (`*.TXT`, puesto en memoria), entrar y salir de
  carpetas y volver de un programa cuatro veces seguidas (el segmento se libera y se vuelve
  a coger el mismo);
- un mapper de 128 KB (la lista sigue en 8.3 y File info lee el disco) y el arranque sin
  sitio en la página 3 (forzado: se queda como la versión 1);
- un error de disco en la pasada (un sector fuera del disco, el segundo error, Abort en el
  diálogo de MM: MM se recupera, vuelve a listar y sigue con su segmento) y CTRL+STOP
  pulsado durante la pasada;
- con puntos de vigilancia en `CB92h-D0EAh`: no escribe nadie más que el parche (y Nextor
  en el búfer de `_GETCLUS`); la pila no baja de `D3EAh` (Nextor 3, File info leyendo
  el disco) ni, con la tabla, de `D6E5h` (Nextor 3) y `D7D8h` (Nextor 2.1.4).
