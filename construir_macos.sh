#!/bin/bash
# Construye MSXsdmaker.app y el ZIP de macOS. Usa un Python con tkinter, PyInstaller y py7zr instalados.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -c 'import tkinter, PyInstaller, py7zr'
rm -rf build/macos dist/MSXsdmaker.app
"$PYTHON_BIN" -m PyInstaller --noconfirm --clean --windowed --name MSXsdmaker \
  --osx-bundle-identifier com.papipapito.msx-sd-maker \
  --add-data "$PWD/sd:sd" --hidden-import py7zr \
  --workpath build/macos --specpath build/macos MSXsdmaker.py

PLIST="dist/MSXsdmaker.app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName MSX SD Maker" "$PLIST"
/usr/bin/codesign --force --deep --sign - dist/MSXsdmaker.app
"$PYTHON_BIN" hacer_zip_macos.py
