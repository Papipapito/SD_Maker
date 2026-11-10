#!/bin/bash
# Construye MSXimusZboot.app (la tarjeta de arranque de la MSXimus Z) y su ZIP. Un Python con tkinter, PyInstaller y certifi.
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -c 'import tkinter, PyInstaller, certifi'
rm -rf build/zboot-macos dist/MSXimusZboot.app
"$PYTHON_BIN" -m PyInstaller --noconfirm --clean --windowed --name MSXimusZboot \
  --osx-bundle-identifier com.papipapito.msximusz-boot \
  --add-data "$PWD/zynq:zynq" --hidden-import certifi --collect-data certifi \
  --workpath build/zboot-macos --specpath build/zboot-macos MSXimusZboot.py
PLIST="dist/MSXimusZboot.app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName MSXimus Z Boot" "$PLIST"
/usr/bin/codesign --force --deep --sign - dist/MSXimusZboot.app
( cd dist && ditto -c -k --keepParent MSXimusZboot.app MSXimusZboot_macOS_arm64.zip )