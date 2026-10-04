# SD_Maker — SD cards for the FPGA MSX machines

*[Castellano](LEEME.md)*

**MSX SD Maker** is a Windows program that gets an SD card ready for the FPGA MSX machines: an **MSXimus** (Tang Console 60K, Tang Mega 138K or Zynq), an **MSXnano** or a **Goa'uld** — and also for an **MSX Pico** and the **MSXBOOK / OneChipBook / 1chipMSX** (OCM-PLD):

- partitions it like Nextor's `FDISK`: FAT16 of 2 or 4 GB (up to 8), or one FAT32;
- copies the system: Nextor 2.1.4, Nextor 3.0 beta 2 or MSX-DOS;
- copies the programs: SofaRun, Multi Mente, utilities, UNAPI networking, music…, and the FPGA tools (`MXUPDATE`, which updates the MSXimus and MSXnano core from MSX-DOS), and writes the `AUTOEXEC.BAT`;
- reads everything back and checks it by CRC. It can also write a card image instead of a card;
- for the MSXBOOK, OneChipBook and 1chipMSX it builds the `OCM-BIOS.DAT` BIOS images from KdL's OCM-SDBIOS Pack, with
  the same options as his `make-sdb.cmd`. The pack is not included (its BIOS images hold third-party system ROMs): the
  user drops it, as downloaded, in the `OCM-SDBIOS` folder next to the program.

**Download** `MSX_SD_Maker_<version>.zip` from the [latest release](https://github.com/Papipapito/SD_Maker/releases/latest), unzip it and run `MSXsdmaker.exe`. How to use it: [paquete/README.md](paquete/README.md) (English) · [paquete/LEEME.md](paquete/LEEME.md) (castellano). The program itself is in Spanish.

## Contents

| | |
|---|---|
| `MSXsdmaker.py`, `sdmaker/` | The program (Python 3 + tkinter) |
| `sd/` | What goes to the card ([sd/LEEME.md](sd/LEEME.md)) |
| `paquete/` | The guide, licences and screenshots that go with the `.exe` |
| `pruebas/` | Image tests with tools that are not ours (`sfdisk`, `fsck.fat`, `mtools`) |
| `construir_exe.bat` | Builds `dist\MSXsdmaker.exe` with PyInstaller, with `sd/` inside |
| `hacer_zip.py` | Builds the release ZIP: the `.exe` with the guide, the licences and the screenshots |
| `publicar_paquete.py` | Copies the `.exe` and the guide to the `MSXsdmaker/` folder of each machine's repository |

## Build and test

```bat
construir_exe.bat
python hacer_zip.py
```

```bash
python MSXsdmaker.py imagen test.img --tamano 1800M --sistema nextor3
bash pruebas/probar_imagenes.sh
python pruebas/probar_ocm.py "PATH TO KdL's PACK"
```

## Licences

MSX SD Maker is by Albert (Papipapito), under the GPL v3 ([LICENSE](LICENSE)).

Most of `sd/` is third-party MSX software (Nextor, MSX-DOS, SofaRun, Multi Mente, the UNAPI tools…). Each file belongs to its author and is included under the responsibility of this project's author. Authors and licences, including the Nextor licence, are in [paquete/LICENCIAS.md](paquete/LICENCIAS.md). If you are the author of any of these files and would rather it were not included, open an issue and it will be removed.

## Coming next: Linux and macOS

Today MSX SD Maker is a Windows program. Only the part that talks to the card reader is Windows-specific (listing the
cards, writing the whole disk and asking for administrator rights, in `sdmaker/dispositivos.py`); partitioning,
formatting, copying, the `AUTOEXEC.BAT` and the card images already work on Linux (the tests run there). The plan:

1. **The window and "Save as image" on Linux and macOS**, with the image then written with balenaEtcher or `dd`. A ZIP for
   each system (`windows`, `linux`, `macos`), built by GitHub Actions on every release: unzip and run.
2. **Writing the card directly**: on Linux, the SD and USB card readers from `lsblk`, unmounting them and writing
   `/dev/sdX` with `sudo`; on macOS, `diskutil` for the external disks, `unmountDisk` and `/dev/rdiskN` with
   administrator rights. It wipes whole disks, so it ships only after being tried with real cards on each system.
