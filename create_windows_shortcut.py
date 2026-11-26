#!/usr/bin/env python3
"""
Erstellt unter Windows Verknüpfungen ('ViDow.lnk') auf dem Desktop und im Startmenü
inklusive offiziellem App-Icon und Unterstützung für OneDrive-Ordnerumleitungen.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ICON_FILE = BASE_DIR / "static" / "icon.ico"
STANDALONE_EXE = BASE_DIR / "dist" / "ViDow" / "ViDow.exe"
VBS_LAUNCHER = BASE_DIR / "ViDow-NoConsole.vbs"
PYTHONW = BASE_DIR / ".venv" / "Scripts" / "pythonw.exe"
TARGET_SCRIPT = BASE_DIR / "app.py"
WIN_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _get_special_folder(name: str) -> Path | None:
    """Liest echte Windows-Systemordner (z. B. Desktop inkl. OneDrive, Programs für Startmenü)."""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"[Environment]::GetFolderPath('{name}')"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=WIN_NO_WINDOW,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            p = Path(proc.stdout.strip())
            if p.is_dir():
                return p
    except Exception:
        pass
    return None


def _write_lnk(shortcut_path: Path, target: str, arguments: str, working_dir: str, icon_loc: str) -> bool:
    env = os.environ.copy()
    env["VIDOW_LNK_PATH"] = str(shortcut_path)
    env["VIDOW_LNK_TARGET"] = target
    env["VIDOW_LNK_ARGS"] = arguments
    env["VIDOW_LNK_CWD"] = working_dir
    env["VIDOW_LNK_ICON"] = icon_loc

    ps_code = (
        "$WshShell = New-Object -ComObject WScript.Shell; "
        "$Shortcut = $WshShell.CreateShortcut($env:VIDOW_LNK_PATH); "
        "$Shortcut.TargetPath = $env:VIDOW_LNK_TARGET; "
        "$Shortcut.Arguments = $env:VIDOW_LNK_ARGS; "
        "$Shortcut.WorkingDirectory = $env:VIDOW_LNK_CWD; "
        "$Shortcut.Description = 'ViDow Studio — Video & Audio Downloader'; "
        "if ($env:VIDOW_LNK_ICON -ne '') { $Shortcut.IconLocation = $env:VIDOW_LNK_ICON }; "
        "$Shortcut.Save()"
    )
    res = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_code],
        env=env,
        capture_output=True,
        text=True,
        creationflags=WIN_NO_WINDOW,
    )
    return res.returncode == 0 and shortcut_path.is_file()


def create_shortcut() -> None:
    if sys.platform != "win32":
        print("Dieses Skript ist für Windows gedacht.")
        return

    if not ICON_FILE.is_file():
        try:
            from generate_icons import generate_all_icons

            generate_all_icons()
        except Exception:
            pass

    if STANDALONE_EXE.is_file():
        target = str(STANDALONE_EXE)
        arguments = ""
        working_dir = str(STANDALONE_EXE.parent)
    elif VBS_LAUNCHER.is_file():
        wscript = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "wscript.exe"
        target = str(wscript if wscript.is_file() else VBS_LAUNCHER)
        arguments = f'"{VBS_LAUNCHER}"' if wscript.is_file() else ""
        working_dir = str(BASE_DIR)
    elif PYTHONW.is_file():
        target = str(PYTHONW)
        arguments = f'"{TARGET_SCRIPT}"'
        working_dir = str(BASE_DIR)
    else:
        target = str(BASE_DIR / "ViDow.bat")
        arguments = ""
        working_dir = str(BASE_DIR)

    icon_loc = str(ICON_FILE) if ICON_FILE.is_file() else ""

    desktop = _get_special_folder("Desktop") or (Path(os.environ.get("USERPROFILE", "")) / "Desktop")
    start_menu = _get_special_folder("Programs") or (
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    )

    created: list[Path] = []
    for folder, label in [(desktop, "Desktop"), (start_menu, "Startmenü")]:
        if folder and folder.is_dir():
            lnk = folder / "ViDow.lnk"
            if _write_lnk(lnk, target, arguments, working_dir, icon_loc):
                created.append(lnk)
                print(f"✅ {label}-Verknüpfung erstellt: {lnk}")

    if not created:
        print("❌ Konnte keine Windows-Verknüpfung erstellen.")


if __name__ == "__main__":
    create_shortcut()
