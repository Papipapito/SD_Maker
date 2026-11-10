@echo off
rem construir_zboot.bat - MSXimusZboot.exe (un solo fichero, pide administrador al abrirse) con PyInstaller: el programa
rem de la tarjeta de ARRANQUE (TF1) de la MSXimus Z. Lleva dentro zynq\ (la foto de la ranura TF1 y, si estan, las fotos
rem de SW1 sw1_sd.png / sw1_qspi.png) y certifi (los certificados para https://msx.barcelona). Resultado: dist\MSXimusZboot.exe
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin --name MSXimusZboot ^
  --add-data "%~dp0zynq;zynq" --hidden-import certifi --collect-data certifi ^
  --workpath build\zboot --specpath build\zboot MSXimusZboot.py