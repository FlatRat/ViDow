@echo off
setlocal
chcp 65001 >nul
title ViDow - Video Downloader

cd /d "%~dp0."

echo ============================================================
echo   ViDow - Video Downloader ^& Stream-Filter (Windows)
echo ============================================================
echo.

set "VENV_DIR=%~dp0.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

REM 1. Falls .venv noch nicht existiert, erstelle sie
if not exist "%VENV_PY%" (
    echo [1/3] Virtuelle Python-Umgebung wird erstellt...
    where py.exe >nul 2>&1
    if not errorlevel 1 (
        py -m venv "%VENV_DIR%"
    ) else (
        where python.exe >nul 2>&1
        if not errorlevel 1 (
            python -m venv "%VENV_DIR%"
        ) else (
            echo [FEHLER] Python wurde nicht im PATH gefunden!
            echo Bitte installiere Python und fuege es zum PATH hinzu.
            pause
            exit /b 1
        )
    )
)

REM 2. Abhaengigkeiten pruefen
"%VENV_PY%" -c "import yt_dlp, curl_cffi, webview" >nul 2>&1
if errorlevel 1 (
    echo [2/3] Installiere Abhaengigkeiten...
    "%VENV_PY%" -m pip install --upgrade pip
    "%VENV_PY%" -m pip install -r requirements.txt
)

REM 3. Icon pruefen
if not exist "static\icon.ico" (
    "%VENV_PY%" -c "from PIL import Image; img=Image.open('static/icon.png'); img.save('static/icon.ico', format='ICO', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])" >nul 2>&1
)

REM 4. ViDow starten
echo [3/3] Starte ViDow Desktop-App...
echo.
"%VENV_PY%" app.py %*

if errorlevel 1 (
    echo.
    echo [HINWEIS] ViDow wurde mit einem Fehler beendet.
    pause
)
