# SofaRun con nombres largos

`sd/extras/SOFARUN/SR.COM` lleva el parche de nombres largos de SofaRun 8.1: la lista de ficheros pasa a una sola
columna con el nombre largo (VFAT) de cada fichero, hasta 63 caracteres (los más largos se ven como los 44 primeros,
`...` y los 16 últimos), y el tamaño a la derecha.

El parche, su código, los aplicadores (`aplicar.py`, `aplicar.html`, `SR_LFN.ips`, `SR_LFN_2025-11.ips`), las
limitaciones y el banco de pruebas en openMSX viven en su propio repositorio,
**[SofaRun_LFN](https://github.com/Papipapito/SofaRun_LFN)** (GPL v3). SofaRun es de Louthrax; el parche no es de
Louthrax ni cuenta con su aval.

Para parchear tu propio `SR.COM` sin instalar nada: [aplicador en línea](https://papipapito.github.io/SofaRun_LFN/aplicar.html).

| Fichero | Qué es |
|---|---|
| `SR.COM` | El de SofaRun 8.1 que llevaba la tarjeta (34.929 bytes, sha1 `2f13bb73…`) + `SR_LFN.ips` de SofaRun_LFN `c0d3f0d`: 36.242 bytes, sha1 `c2f56896…` |
| El resto de `SOFARUN\` | Sin cambios |

Hay que saber:

- Hace falta Nextor 2.1 o 3.0, una partición FAT16 o FAT12 y la pantalla de 80 columnas. En 40 columnas la lista
  sigue como antes (8.3).
- Los nombres largos son solo para ver: al lanzar un fichero y en los ajustes se usa el nombre 8.3.
- Caben unos 180-200 ficheros con nombre largo por carpeta.
- El título del menú de juego sigue siendo el nombre 8.3.
- Probado solo en openMSX (Nextor 2.1.4, FAT16) con el banco de SofaRun_LFN.

---

# SofaRun with long file names

`sd/extras/SOFARUN/SR.COM` carries the SofaRun 8.1 long-file-name patch: the file list becomes a single column with
each file's long (VFAT) name, up to 63 characters (longer ones show the first 44, `...` and the last 16), and the
size on the right.

The patch, its source, the appliers (`aplicar.py`, `aplicar.html`, `SR_LFN.ips`, `SR_LFN_2025-11.ips`), its
limitations and the openMSX test bench live in their own repository,
**[SofaRun_LFN](https://github.com/Papipapito/SofaRun_LFN)** (GPL v3). SofaRun is by Louthrax; the patch is not
Louthrax's work and is not endorsed by Louthrax.

To patch your own `SR.COM` without installing anything: [online applier](https://papipapito.github.io/SofaRun_LFN/aplicar.html).

`SR.COM` = the SofaRun 8.1 `SR.COM` the card already carried (34,929 bytes, sha1 `2f13bb73…`) + `SR_LFN.ips`:
36,242 bytes, sha1 `c2f56896…`. The rest of `SOFARUN\` is unchanged.

Needs Nextor 2.1 or 3.0, a FAT16 or FAT12 partition and the 80-column screen (in 40 columns the list is unchanged,
8.3). Long names are display only: launching and settings use the 8.3 name. About 180-200 long-named files fit per
folder. The game menu title stays 8.3. Tested only in openMSX (Nextor 2.1.4, FAT16).
