@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo [Impozycjoner] Publikowanie projektu na GitHub...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\publish-github.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo Nie udalo sie opublikowac projektu. Przeslij komunikat bledu.
)
echo.
pause
exit /b %EXIT_CODE%
