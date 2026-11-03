# Multi Mente con nombres largos

`sd/base/MM/` lleva **Multi Mente 2.07A+ RC5** (la de la comunidad, con los arreglos de FAT16 y del año 2000)
con el parche de nombres largos: la lista enseña los 12 primeros caracteres del nombre largo de cada
fichero y **File info** el nombre largo entero.

El parche, su código, los aplicadores (`aplicar.py`, `aplicar.html`, `MM_LFN_RC5.ips`), las limitaciones y el
banco de pruebas en openMSX viven en su propio repositorio, **[MultiMente_LFN](https://github.com/Papipapito/MultiMente_LFN)** (GPL v3). Multi Mente es de
MOGU; el parche no es suyo ni cuenta con su aval.

Para parchear tu propio `MM.COM` (2.07_A o RC5) sin instalar nada: [aplicador en línea](https://papipapito.github.io/MultiMente_LFN/aplicar.html).

Lo que hay en la tarjeta:

| Fichero | Qué es |
|---|---|
| `MM.COM` | El de la RC5 (23.552 bytes, sha1 `09c4a6b4…`) + `MM_LFN_RC5.ips` (25.673 bytes, sha1 `5b97f818…`), y encima los huecos de herramientas de este proyecto (`0x108-0x367`, lo que `CS.COM` copia desde `MM.CFG`): 25.673 bytes, sha1 `7d7a962a…` |
| `MM.EXE` | El de la RC5 (11.648 bytes): va con su `MM.COM` |
| `CS.COM` | CS 3.12, el que acompaña a la RC5 |
| `MM.CFG`, `MMRET.DAT`, `MMMCR.DAT`… | Los de este proyecto (ver `sd/LEEME.md`) |

Para rehacer `MM.COM`: aplicar `MM_LFN_RC5.ips` (de [MultiMente_LFN](https://github.com/Papipapito/MultiMente_LFN)) al `MM.COM` de la RC5 y copiar encima los
bytes `0x108-0x367` del `MM.COM` actual (o pasar `CS MM` en el MSX con el `MM.CFG` de la tarjeta).

Probado en openMSX con el banco de MultiMente_LFN (Nextor 2.1.4): lista y File info, ordenar, marcar,
carpetas, volver de [X]ecom, borrar, copiar y `CS MM`. Con Nextor 3 la RC5 no se ha probado.

---

# Multi Mente with long file names

`sd/base/MM/` carries **Multi Mente 2.07A+ RC5** (the community release, with the FAT16 and year 2000 fixes)
with the long-file-name patch: the list shows the first 12 characters of each file's long name and
**File info** the whole long name.

The patch, its source, the appliers (`aplicar.py`, `aplicar.html`, `MM_LFN_RC5.ips`), its limitations and the
openMSX test bench live in their own repository, **[MultiMente_LFN](https://github.com/Papipapito/MultiMente_LFN)** (GPL v3). Multi Mente is by MOGU; the
patch is not his and is not endorsed by him.

To patch your own `MM.COM` (2.07_A or RC5) without installing anything: [online applier](https://papipapito.github.io/MultiMente_LFN/aplicar.html).

`MM.COM` = RC5 `MM.COM` + `MM_LFN_RC5.ips`, with this project's tool slots (`0x108-0x367`, what `CS.COM`
copies from `MM.CFG`) on top. `MM.EXE` is the RC5 one (it goes with its `MM.COM`) and `CS.COM` is CS 3.12.
Tested in openMSX with Nextor 2.1.4; not tested with Nextor 3.
