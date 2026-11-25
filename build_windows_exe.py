#!/usr/bin/env python3
"""
ViDow 2.0 — Standalone Windows App- & Release-ZIP-Builder
Kompiliert ViDow mit PyInstaller zu einer komplett eigenständigen Windows-Anwendung
('dist/ViDow/ViDow.exe') inklusive integriertem ffmpeg (imageio-ffmpeg), neuen
Studio-Icons (.ico) und schnürt ein versandfertiges Release-Archiv ('dist/ViDow-2.0.0-Windows-x64.zip').
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

APP_VERSION = "2.0.0"

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DIST_DIR = BASE_DIR / "dist"
ICON_FILE = STATIC_DIR / "icon.ico"

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def package_windows_zip(app_folder: Path, zip_path: Path) -> None:
    """Verpackt dist/ViDow sowie den optionalen Browser-Helper in ein auslieferbares ZIP-Archiv."""
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file_path in app_folder.rglob("*"):
            if file_path.is_file():
                arcname = Path("ViDow") / file_path.relative_to(app_folder)
                zf.write(file_path, arcname)

        ext_dir = BASE_DIR / "extension"
        if ext_dir.is_dir():
            for ext_file in ext_dir.rglob("*"):
                if ext_file.is_file():
                    arcname = Path("ViDow") / "extension" / ext_file.relative_to(ext_dir)
                    zf.write(ext_file, arcname)


def build() -> None:
    if sys.platform != "win32":
        print("Dieses Build-Skript ist für Windows gedacht.")
        sys.exit(1)

    print("=" * 64)
    print(f"🎬 ViDow v{APP_VERSION} — Native Windows Standalone Build")
    print("=" * 64)

    # 1. Abhängigkeiten & Icons sicherstellen
    for pkg, mod in [
        ("pillow", "PIL"),
        ("imageio-ffmpeg", "imageio_ffmpeg"),
        ("pyinstaller", "PyInstaller"),
    ]:
        try:
            __import__(mod)
        except ImportError:
            print(f"⬇️ Installiere {pkg}...")
            subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)

    from generate_icons import generate_all_icons

    generate_all_icons()

    # 2. PyInstaller Befehl zusammenstellen
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
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
        "--collect-all",
        "imageio_ffmpeg",
    ]

    if ICON_FILE.is_file():
        cmd.extend(["--icon", str(ICON_FILE)])

    cmd.append(str(BASE_DIR / "app.py"))

    print("\n📦 Erzeuge eigenständiges Windows-Programm in 'dist/ViDow/'...")
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print("\n❌ Build fehlgeschlagen. Siehe Fehlermeldungen oben.")
        sys.exit(res.returncode)

    app_folder = DIST_DIR / "ViDow"
    exe_path = app_folder / "ViDow.exe"
    zip_path = DIST_DIR / f"ViDow-{APP_VERSION}-Windows-x64.zip"

    print(f"🗜️ Erzeuge auslieferbares Archiv: {zip_path.name}...")
    package_windows_zip(app_folder, zip_path)

    print("\n" + "=" * 64)
    print("✅ Native Windows-App erfolgreich gebaut!")
    print(f"📁 Programm-Ordner: {app_folder}")
    if exe_path.is_file():
        print(f"🚀 Startdatei:      {exe_path}")
    if zip_path.is_file():
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"📦 Release-ZIP:     {zip_path} ({size_mb:.1f} MB)")
    print("=" * 64)


if __name__ == "__main__":
    build()
