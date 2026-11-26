@echo off
setlocal
chcp 65001 >nul
title ViDow Studio - Video Downloader (Windows)

cd /d "%~dp0."
set "PYTHONNOUSERSITE=1"
set "PYTHONUTF8=1"

REM Falls bereits eine kompilierte Standalone-EXE existiert und kein --dev/--setup-only Flag gesetzt ist
if /I not "%~1"=="--dev" if /I not "%~1"=="--setup-only" (
    if exist "%~dp0dist\ViDow\ViDow.exe" (
        if not exist "%~dp0.venv\Scripts\python.exe" (
            start "" "%~dp0dist\ViDow\ViDow.exe" %*
            exit /b 0
        )
    )
)

echo ============================================================
echo   ViDow Studio - Video Downloader ^& Stream-Filter (Windows)
echo ============================================================
echo.

set "VENV_DIR=%~dp0.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "VENV_PYW=%VENV_DIR%\Scripts\pythonw.exe"
set "DEPS_MARKER=%VENV_DIR%\.vidow_deps_v2_ok"

REM 1. Falls .venv noch nicht existiert, erstelle sie
if not exist "%VENV_PY%" (
    echo [1/3] Virtuelle Python-Umgebung wird erstellt...
    where py.exe >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv "%VENV_DIR%"
    ) else (
        where python.exe >nul 2>&1
        if not errorlevel 1 (
            python -m venv "%VENV_DIR%"
        ) else (
            echo [FEHLER] Python 3 wurde nicht im PATH gefunden!
            echo Bitte installiere Python 3.10+ von https://www.python.org/downloads/
            echo ^(Haken bei "Add python.exe to PATH" setzen^).
            pause
            exit /b 1
        )
    )
)

REM 2. Abhaengigkeiten vollstaendig pruefen (inkl. Pillow & imageio-ffmpeg)
"%VENV_PY%" -c "import yt_dlp, curl_cffi, webview, PIL, imageio_ffmpeg" >nul 2>&1
if errorlevel 1 (
    if exist "%DEPS_MARKER%" del /q "%DEPS_MARKER%" >nul 2>&1
    echo [2/3] Installiere / aktualisiere Windows-Abhaengigkeiten...
    "%VENV_PY%" -m pip install --upgrade pip
    "%VENV_PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [FEHLER] Paketinstallation fehlgeschlagen. Bitte Internetverbindung pruefen.
        pause
        exit /b 1
    )
)
echo ok > "%DEPS_MARKER%"

REM 3. Windows-Icon (.ico) sicherstellen
if not exist "static\icon.ico" (
    "%VENV_PY%" generate_icons.py >nul 2>&1
)

if /I "%~1"=="--setup-only" (
    echo [OK] ViDow-Umgebung ist eingerichtet.
    exit /b 0
)

REM 4. ViDow starten
echo [3/3] Starte ViDow Studio...
echo.
"%VENV_PY%" app.py %*

if errorlevel 1 (
    echo.
    echo [HINWEIS] ViDow wurde mit einem Fehler beendet.
    pause
)
