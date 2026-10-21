#!/usr/bin/env python3
"""
Erstellt eine Windows-Desktop-Verknüpfung ('ViDow.lnk') inklusive offiziellem App-Icon.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ICON_FILE = BASE_DIR / "static" / "icon.ico"
PYTHONW = BASE_DIR / ".venv" / "Scripts" / "pythonw.exe"
TARGET_SCRIPT = BASE_DIR / "app.py"

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def create_shortcut() -> None:
    if sys.platform != "win32":
        print("Dieses Skript ist für Windows gedacht.")
        return

    desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
    if not desktop.is_dir():
        print("Desktop-Ordner wurde nicht gefunden.")
        return

    shortcut_path = desktop / "ViDow.lnk"

    target = str(PYTHONW if PYTHONW.is_file() else (BASE_DIR / "ViDow.bat"))
    arguments = f'"{TARGET_SCRIPT}"' if PYTHONW.is_file() else ""
    working_dir = str(BASE_DIR)
    icon_loc = str(ICON_FILE) if ICON_FILE.is_file() else ""

    ps_code = f"""
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut('{shortcut_path}')
    $Shortcut.TargetPath = '{target}'
    $Shortcut.Arguments = '{arguments}'
    $Shortcut.WorkingDirectory = '{working_dir}'
    $Shortcut.Description = 'ViDow — Video Downloader & Stream-Filter'
    if ('{icon_loc}' -ne '') {{
        $Shortcut.IconLocation = '{icon_loc}'
    }}
    $Shortcut.Save()
    """

    res = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_code],
        capture_output=True,
        text=True,
    )
    if res.returncode == 0 and shortcut_path.is_file():
        print(f"✅ Desktop-Verknüpfung erfolgreich erstellt: {shortcut_path}")
    else:
        print(f"Fehler beim Erstellen der Verknüpfung: {res.stderr.strip() or res.stdout.strip()}")


if __name__ == "__main__":
    create_shortcut()
