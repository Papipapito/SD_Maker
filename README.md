# SD_Maker — SD cards for the FPGA MSX machines

*[Castellano](LEEME.md)*

**MSX SD Maker** is a Windows and macOS app that gets an SD card ready for the FPGA MSX machines: an **MSXimus** (Tang Console 60K, Tang Mega 138K or Zynq), an **MSXnano** or a **Goa'uld** — and also for an **MSX Pico** and the **MSXBOOK / OneChipBook / 1chipMSX** (OCM-PLD):

- partitions it like Nextor's `FDISK`: FAT16 of 2 or 4 GB (up to 8), or one FAT32;
- copies the system: Nextor 2.1.4, Nextor 3.0 beta 2 or MSX-DOS;
- copies the programs: SofaRun, Multi Mente, utilities, UNAPI networking, music (the MoonBlaster Wave and MoonBlaster FM editors for the OPL4, RoboPlay and the MWM and VGM players)…, and the FPGA tools (`MXUPDATE`, which updates the MSXimus and MSXnano core from MSX-DOS, and `MTVOL`, which sets the OPL4 FM and Wave volume), and writes the `AUTOEXEC.BAT`;
- reads everything back and checks it by CRC. It can also write a card image instead of a card;
- (1.5) sets up Multi Mente so that RETURN opens each file with its program (VGM/VGZ with VGMPlay 1.4; MFM, MWM, MID and the AdLib formats with RoboPlay; ROM, DSK and ZIP with SofaRun…) and shows long file names (patched `MM.COM`, in `parches/mm-nombres-largos/`);
- for the MSXBOOK, OneChipBook and 1chipMSX it builds the `OCM-BIOS.DAT` BIOS images from KdL's OCM-SDBIOS Pack, with
  the same options as his `make-sdb.cmd`. The pack is not included (its BIOS images hold third-party system ROMs): the
  user drops it, as downloaded, in the `OCM-SDBIOS` folder next to the program.

**Download** the ZIP for your system from the [latest release](https://github.com/Papipapito/SD_Maker/releases/latest), unzip it and run `MSXsdmaker.exe` on Windows or `MSXsdmaker.app` on macOS. How to use it: [paquete/README.md](paquete/README.md) (English) · [paquete/LEEME.md](paquete/LEEME.md) (castellano). The program itself is in Spanish.

## Contents

| | |
|---|---|
| `MSXsdmaker.py`, `sdmaker/` | The program (Python 3 + tkinter) |
| `sd/` | What goes to the card ([sd/LEEME.md](sd/LEEME.md)) |
| `paquete/` | The guide, licences and screenshots that go with the `.exe` |
| `pruebas/` | Image tests with tools that are not ours (`sfdisk`, `fsck.fat`, `mtools`) |
| `construir_exe.bat` | Builds `dist\MSXsdmaker.exe` with PyInstaller, with `sd/` inside |
| `construir_macos.sh` | Builds the native `dist/MSXsdmaker.app` bundle and the macOS ZIP |
| `hacer_zip.py`, `hacer_zip_macos.py` | Build the Windows and macOS release ZIPs |
| `publicar_paquete.py` | Copies the `.exe` and the guide to the `MSXsdmaker/` folder of each machine's repository |

## Build and test

```bat
construir_exe.bat
python hacer_zip.py
```

```bash
PYTHON_BIN=.venv-macos/bin/python ./construir_macos.sh
```

```bash
python MSXsdmaker.py imagen test.img --tamano 1800M --sistema nextor3
bash pruebas/probar_imagenes.sh
python pruebas/probar_ocm.py "PATH TO KdL's PACK"
```

## Licences

MSX SD Maker is by Albert (Papipapito), under the GPL v3 ([LICENSE](LICENSE)).

Most of `sd/` is third-party MSX software (Nextor, MSX-DOS, SofaRun, Multi Mente, the UNAPI tools…). Each file belongs to its author and is included under the responsibility of this project's author. Authors and licences, including the Nextor licence, are in [paquete/LICENCIAS.md](paquete/LICENCIAS.md). If you are the author of any of these files and would rather it were not included, open an issue and it will be removed.

## macOS safety

The macOS app lists physical, external, removable media through `diskutil`, explicitly excludes every physical store
used by the macOS root volume, and accepts only 512-byte-sector devices. Just before writing it validates the selected
device again, unmounts it, asks for administrator rights and writes through `/dev/rdiskN`; the GUI itself never runs as
root. The Windows code path is unchanged. Linux still supports card images but not direct card writing.
