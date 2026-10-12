@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Prefer the Windows Python launcher, fall back to python on PATH.
set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m venv --help >nul 2>nul
    if not errorlevel 1 set "PY_CMD=py -3"
)
if not defined PY_CMD (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -m venv --help >nul 2>nul
        if not errorlevel 1 set "PY_CMD=python"
    )
)
if not defined PY_CMD goto NO_PYTHON

if not exist ".venv\Scripts\python.exe" (
    echo [Impozycjoner] Tworzenie srodowiska .venv ...
    %PY_CMD% -m venv ".venv"
    if errorlevel 1 goto ENV_ERROR
)

rem venv can exist without pip (broken/incomplete Python installation).
".venv\Scripts\python.exe" -m pip --version >nul 2>nul
if not errorlevel 1 goto READY

echo [Impozycjoner] Brak pip - proba automatycznej naprawy ...
".venv\Scripts\python.exe" -m ensurepip --upgrade
".venv\Scripts\python.exe" -m pip --version >nul 2>nul
if not errorlevel 1 goto READY

rem A failed ensurepip sometimes means the environment was partly created.
echo [Impozycjoner] Ponowne tworzenie uszkodzonego .venv ...
%PY_CMD% -m venv --clear ".venv"
if errorlevel 1 goto ENV_ERROR
".venv\Scripts\python.exe" -m ensurepip --upgrade
".venv\Scripts\python.exe" -m pip --version >nul 2>nul
if errorlevel 1 goto PIP_ERROR

:READY
exit /b 0

:NO_PYTHON
echo.
echo BLAD: Nie znaleziono prawidlowego Pythona.
echo Zainstaluj Python 3.11+ z https://www.python.org/downloads/windows/
echo Podczas instalacji zaznacz Add python.exe to PATH oraz pip.
exit /b 1

:ENV_ERROR
echo.
echo BLAD: Nie udalo sie utworzyc .venv.
echo Sprawdz, czy Python ma moduly venv i ensurepip.
exit /b 1

:PIP_ERROR
echo.
echo BLAD: Python nie zawiera pip lub ensurepip.
echo Zainstaluj pelna wersje Pythona z https://www.python.org/downloads/windows/
echo W instalatorze wybierz Modify i wlacz pip.
exit /b 1
