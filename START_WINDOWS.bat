@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0BOOTSTRAP_WINDOWS.bat"
if errorlevel 1 goto ERROR

echo [Impozycjoner] Instalacja wymaganych bibliotek ...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto ERROR

echo [Impozycjoner] Uruchamianie aplikacji ...
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto ERROR
exit /b 0

:ERROR
echo.
echo Nie mozna uruchomic programu. Skopiuj powyzszy blad do ChatGPT.
pause
exit /b 1
