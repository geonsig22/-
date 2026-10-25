@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 goto error
.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller==6.16.0
if errorlevel 1 goto error
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onefile --collect-all rawpy --icon assets/photobatch.ico --add-data "assets;assets" --name PhotoBatch app.py
if errorlevel 1 goto error
echo Ready: dist\PhotoBatch.exe
pause
exit /b 0
:error
echo Build failed. Check the error above.
pause
exit /b 1
