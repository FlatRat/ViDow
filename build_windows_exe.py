#!/usr/bin/env python3
"""
ViDow — Build-Skript für Windows
Kompiliert ViDow mit PyInstaller zu einer eigenständigen Windows-Anwendung (ViDow.exe)
inklusive Icon und statischen Web-Assets.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
ICON_FILE = STATIC_DIR / "icon.ico"

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def build() -> None:
    if sys.platform != "win32":
        print("Dieses Build-Skript ist für Windows gedacht.")
        return

    # UTF-8 Konsole
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("=" * 60)
    print("🎬 ViDow — Windows Build (PyInstaller)")
    print("=" * 60)

    # 1. Sicherstellen, dass icon.ico existiert
    if not ICON_FILE.is_file():
        print("Erzeuge static/icon.ico...")
        try:
            from PIL import Image

            img = Image.open(STATIC_DIR / "icon.png")
            img.save(
                ICON_FILE,
                format="ICO",
                sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
            )
        except Exception as exc:
            print(f"Konnte icon.ico nicht erzeugen ({exc}), fahre fort...")

    # 2. PyInstaller prüfen
    try:
        import PyInstaller
    except ImportError:
        print("⬇️ Installiere PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    # 3. PyInstaller Befehl zusammenstellen
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name",
        "ViDow",
        "--add-data",
        f"{STATIC_DIR};static",
        "--collect-all",
        "yt_dlp",
        "--collect-all",
        "curl_cffi",
        "--collect-all",
        "webview",
    ]

    if ICON_FILE.is_file():
        cmd.extend(["--icon", str(ICON_FILE)])

    cmd.append(str(BASE_DIR / "app.py"))

    print("\n📦 Erzeuge Windows-Bundle in 'dist/ViDow/'...")
    res = subprocess.run(cmd)

    if res.returncode == 0:
        exe_path = BASE_DIR / "dist" / "ViDow" / "ViDow.exe"
        print("\n" + "=" * 60)
        print(f"✅ ViDow erfolgreich gebaut!")
        print(f"📁 Programm-Ordner: {BASE_DIR / 'dist' / 'ViDow'}")
        if exe_path.is_file():
            print(f"🚀 Startdatei: {exe_path}")
        print("=" * 60)
    else:
        print("\n❌ Build fehlgeschlagen. Siehe Fehlermeldungen oben.")


if __name__ == "__main__":
    build()
