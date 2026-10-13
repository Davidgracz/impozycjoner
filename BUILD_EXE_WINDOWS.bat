@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0BOOTSTRAP_WINDOWS.bat"
if errorlevel 1 goto ERROR

echo [Impozycjoner] Instalacja bibliotek i PyInstaller ...
".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto ERROR

".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --onedir --name "Impozycjoner-Studio" --collect-all pymupdf --hidden-import sheet_editor --add-data "assets;assets" app.py
if errorlevel 1 goto ERROR

echo.
echo EXE: dist\Impozycjoner-Studio\Impozycjoner-Studio.exe
pause
exit /b 0

:ERROR
echo.
echo Blad budowania EXE. Skopiuj powyzszy blad do ChatGPT.
pause
exit /b 1
