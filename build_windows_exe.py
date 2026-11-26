#!/usr/bin/env python3
"""
ViDow 2.0 — Native Windows App-, Setup-Installer- & Download-ZIP-Builder
1. Kompiliert ViDow mit PyInstaller zu einer eigenständigen Windows-Anwendung ('dist/ViDow/ViDow.exe')
   inklusive Windows-Versionsmetadaten, integriertem ffmpeg (imageio-ffmpeg) & Studio-Icons (.ico).
2. Erzeugt mit Inno Setup 6 einen vollwertigen Windows-10/11-Installer
   ('dist/ViDow-2.0.2-Windows-Setup.exe') mit Startmenü-/Desktop-Verknüpfung & Deinstallationsroutine.
3. Schnürt daraus das fertige Download-Paket ('dist/ViDow-2.0.2-Windows-Setup.zip') inklusive
   Setup-Installer, Kurzanleitung und optionaler Browser-Erweiterung.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

APP_VERSION = "2.0.2"
VERSION_TUPLE = (2, 0, 2, 0)
INNO_APP_ID = "{{8F4E2D91-7C3A-4B6E-9D12-5A8C3E7F1020}"

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
BUILD_DIR = BASE_DIR / "build"
DIST_DIR = BASE_DIR / "dist"
ICON_FILE = STATIC_DIR / "icon.ico"

os.environ["PYTHONNOUSERSITE"] = "1"
os.environ["PYTHONUTF8"] = "1"

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def find_iscc() -> Path | None:
    """Sucht den Inno Setup 6 Compiler (ISCC.exe) in PATH und typischen Windows-Pfaden."""
    which_iscc = shutil.which("ISCC") or shutil.which("iscc.exe")
    if which_iscc and Path(which_iscc).is_file():
        return Path(which_iscc)

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    prog_data = os.environ.get("ProgramData", r"C:\ProgramData")
    home = Path.home()

    candidates = [
        Path(local_app_data) / "Programs" / "Inno Setup 6" / "ISCC.exe" if local_app_data else None,
        Path(prog_files_x86) / "Inno Setup 6" / "ISCC.exe",
        Path(prog_files) / "Inno Setup 6" / "ISCC.exe",
        home / "scoop" / "apps" / "innosetup" / "current" / "ISCC.exe",
        Path(prog_data) / "chocolatey" / "bin" / "ISCC.exe",
    ]
    for cand in candidates:
        if cand is not None and cand.is_file():
            return cand
    return None


def write_windows_version_file(target_file: Path) -> Path:
    """Erzeugt eine PyInstaller-Versionsressource für den Windows-Explorer & Task-Manager."""
    target_file.parent.mkdir(parents=True, exist_ok=True)
    v_str = ".".join(str(x) for x in VERSION_TUPLE)
    content = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={VERSION_TUPLE},
    prodvers={VERSION_TUPLE},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040704B0',
          [
            StringStruct('CompanyName', 'lg-craft'),
            StringStruct('FileDescription', 'ViDow — Studio Video & Audio Downloader'),
            StringStruct('FileVersion', '{v_str}'),
            StringStruct('InternalName', 'ViDow'),
            StringStruct('LegalCopyright', 'Copyright (c) lg-craft (https://lg-craft.com)'),
            StringStruct('OriginalFilename', 'ViDow.exe'),
            StringStruct('ProductName', 'ViDow Studio'),
            StringStruct('ProductVersion', '{APP_VERSION}')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1031, 1200])])
  ]
)
"""
    target_file.write_text(content, encoding="utf-8")
    return target_file


def write_inno_setup_script(
    iss_path: Path,
    app_folder: Path,
    setup_stem: str,
    iscc_exe: Path,
) -> Path:
    """Erzeugt das Inno-Setup-Skript (.iss) für den nativen Windows-10/11-Installer."""
    iss_path.parent.mkdir(parents=True, exist_ok=True)
    has_german = (iscc_exe.parent / "Languages" / "German.isl").is_file()
    ext_dir = BASE_DIR / "extension"

    languages_block = (
        'Name: "german"; MessagesFile: "compiler:Languages\\German.isl"\n'
        'Name: "english"; MessagesFile: "compiler:Default.isl"'
        if has_german
        else 'Name: "default"; MessagesFile: "compiler:Default.isl"'
    )

    ext_files_line = (
        f'Source: "{ext_dir}\\*"; DestDir: "{{app}}\\extension"; '
        "Flags: ignoreversion recursesubdirs createallsubdirs"
        if ext_dir.is_dir()
        else ""
    )

    icon_setup_line = f"SetupIconFile={ICON_FILE}" if ICON_FILE.is_file() else ""

    iss_content = f"""; ViDow Studio v{APP_VERSION} — Inno Setup 6 Installer Script
[Setup]
AppId={INNO_APP_ID}
AppName=ViDow Studio
AppVersion={APP_VERSION}
AppVerName=ViDow Studio {APP_VERSION}
AppPublisher=lg-craft
AppPublisherURL=https://lg-craft.com
AppSupportURL=https://lg-craft.com
DefaultDirName={{autopf}}\\ViDow
DefaultGroupName=ViDow Studio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={DIST_DIR}
OutputBaseFilename={setup_stem}
{icon_setup_line}
UninstallDisplayIcon={{app}}\\ViDow.exe
UninstallDisplayName=ViDow Studio
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
#if VER >= EncodeVer(6,3,0)
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
#else
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
#endif

[Languages]
{languages_block}

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"

[InstallDelete]
Type: filesandordirs; Name: "{{app}}\\_internal"

[Files]
Source: "{app_folder}\\*"; DestDir: "{{app}}"; Excludes: "*.bat"; Flags: ignoreversion recursesubdirs createallsubdirs
{ext_files_line}

[Icons]
Name: "{{autoprograms}}\\ViDow Studio"; Filename: "{{app}}\\ViDow.exe"; WorkingDir: "{{app}}"; AppUserModelID: "FlatRat.ViDow.Studio.2.0"
Name: "{{autodesktop}}\\ViDow Studio"; Filename: "{{app}}\\ViDow.exe"; WorkingDir: "{{app}}"; Tasks: desktopicon; AppUserModelID: "FlatRat.ViDow.Studio.2.0"

[Run]
Filename: "{{app}}\\ViDow.exe"; Description: "{{cm:LaunchProgram,ViDow Studio}}"; Flags: nowait postinstall skipifsilent
"""
    # UTF-8 mit BOM schreiben, damit Inno Setup Umlaute (z. B. —) zuverlässig liest
    iss_path.write_text(iss_content, encoding="utf-8-sig")
    return iss_path


def package_setup_download_zip(setup_exe: Path, zip_path: Path) -> None:
    """
    Verpackt die fertige Setup.exe + Kurzanleitung + optionale Browser-Erweiterung
    in ein sauberes Download-ZIP-Archiv.
    """
    if zip_path.exists():
        zip_path.unlink()

    readme_txt = (
        f"ViDow Studio v{APP_VERSION} für Windows 10 & Windows 11 (64-Bit)\r\n"
        "================================================================\r\n\r\n"
        "Ein Projekt von lg-craft (https://lg-craft.com)\r\n\r\n"
        "INSTALLATION (1 KLICK):\r\n"
        f"1. Doppelklicke auf '{setup_exe.name}'.\r\n"
        "   (Hinweis: Falls Windows SmartScreen beim ersten Start fragt,\r\n"
        "    klicke auf 'Weitere Informationen' -> 'Trotzdem ausführen'.)\r\n"
        "2. Folge kurz dem Installations-Assistenten.\r\n"
        "   - Python oder ffmpeg müssen NICHT separat installiert werden (alles integriert).\r\n"
        "   - ViDow wird sauber ins Windows-Startmenü (und optional auf den Desktop) gelegt\r\n"
        "     und lässt sich jederzeit über 'Windows-Einstellungen -> Installierte Apps' entfernen.\r\n\r\n"
        "OPTIONALE BROWSER-ERWEITERUNG (Chrome / Edge / Brave):\r\n"
        "1. Entpacke den Ordner 'extension' an einen festen Ort (oder nutze nach der\r\n"
        "   Installation direkt den Ordner '%LOCALAPPDATA%\\Programs\\ViDow\\extension').\r\n"
        "2. Öffne 'edge://extensions' bzw. 'chrome://extensions', aktiviere oben rechts\r\n"
        "   den 'Entwicklermodus' und wähle 'Entpackte Erweiterung laden' -> Ordner 'extension'.\r\n"
    )

    # Da die Setup.exe bereits per LZMA2 hochkomprimiert ist, speichern wir sie ohne
    # doppelte Re-Kompression schnell im ZIP und komprimieren Text-/Extension-Dateien per Deflate.
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.write(setup_exe, arcname=setup_exe.name, compress_type=zipfile.ZIP_STORED)
        zf.writestr("LIESMICH - Installation.txt", readme_txt.encode("utf-8"))

        ext_dir = BASE_DIR / "extension"
        if ext_dir.is_dir():
            for ext_file in ext_dir.rglob("*"):
                if ext_file.is_file():
                    arcname = Path("extension") / ext_file.relative_to(ext_dir)
                    zf.write(ext_file, arcname)


def package_portable_fallback_zip(app_folder: Path, zip_path: Path) -> None:
    """Fallback, falls auf einem Build-System kein Inno Setup installiert ist."""
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


def build(installer_only: bool = False) -> None:
    if sys.platform != "win32":
        print("Dieses Build-Skript ist für Windows gedacht.")
        sys.exit(1)

    print("=" * 68)
    print(f"🎬 ViDow v{APP_VERSION} — Native Windows Setup & Download-ZIP Build")
    print("=" * 68)

    app_folder = DIST_DIR / "ViDow"
    exe_path = app_folder / "ViDow.exe"

    if not (installer_only and exe_path.is_file()):
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

        for folder in (app_folder, BUILD_DIR):
            if folder.exists():
                shutil.rmtree(folder, ignore_errors=True)

        version_file = write_windows_version_file(BUILD_DIR / "windows_version_info.txt")

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
            "--version-file",
            str(version_file),
            "--add-data",
            f"{STATIC_DIR};static",
            "--collect-all",
            "yt_dlp",
            "--collect-all",
            "curl_cffi",
            "--collect-all",
            "webview",
            "--collect-all",
            "pythonnet",
            "--collect-all",
            "clr_loader",
            "--collect-all",
            "imageio_ffmpeg",
            "--collect-data",
            "certifi",
            "--hidden-import",
            "tkinter",
            "--hidden-import",
            "tkinter.filedialog",
        ]
        if ICON_FILE.is_file():
            cmd.extend(["--icon", str(ICON_FILE)])
        cmd.append(str(BASE_DIR / "app.py"))

        print("\n📦 [1/3] Erzeuge eigenständiges Windows-Programm in 'dist/ViDow/'...")
        res = subprocess.run(cmd)
        if res.returncode != 0:
            print("\n❌ PyInstaller-Build fehlgeschlagen.")
            sys.exit(res.returncode)
    else:
        print(f"ℹ️ Nutze bereits gebautes Programmverzeichnis: {app_folder}")

    # Alte Portable-ZIP entfernen, damit keine Verwechslung im dist-Ordner entsteht
    legacy_portable_zip = DIST_DIR / f"ViDow-{APP_VERSION}-Windows-x64.zip"
    if legacy_portable_zip.exists():
        legacy_portable_zip.unlink()

    iscc_exe = find_iscc()
    setup_stem = f"ViDow-{APP_VERSION}-Windows-Setup"
    setup_exe = DIST_DIR / f"{setup_stem}.exe"
    setup_zip = DIST_DIR / f"{setup_stem}.zip"

    if iscc_exe is not None:
        print(f"\n💿 [2/3] Kompiliere Windows-Installer mit Inno Setup ({iscc_exe})...")
        iss_file = write_inno_setup_script(
            BUILD_DIR / "vidow_setup.iss", app_folder, setup_stem, iscc_exe
        )
        res_inno = subprocess.run([str(iscc_exe), str(iss_file)])
        if res_inno.returncode != 0 or not setup_exe.is_file():
            print("\n❌ Inno-Setup-Kompilierung fehlgeschlagen.")
            sys.exit(res_inno.returncode or 1)

        print(f"\n🗜️ [3/3] Schnüre fertiges Download-ZIP: {setup_zip.name}...")
        package_setup_download_zip(setup_exe, setup_zip)

        setup_mb = setup_exe.stat().st_size / (1024 * 1024)
        zip_mb = setup_zip.stat().st_size / (1024 * 1024)
        print("\n" + "=" * 68)
        print("✅ Windows-Setup & Download-ZIP erfolgreich erstellt!")
        print(f"💿 Windows-Setup:   {setup_exe} ({setup_mb:.1f} MB)")
        print(f"📦 Download-ZIP:    {setup_zip} ({zip_mb:.1f} MB)")
        print("=" * 68)
    else:
        print("\n⚠️ Inno Setup 6 (ISCC.exe) nicht gefunden – erzeuge portables Fallback-ZIP...")
        print("   (Tipp: 'winget install JRSoftware.InnoSetup' installiert den Setup-Compiler.)")
        package_portable_fallback_zip(app_folder, legacy_portable_zip)
        zip_mb = legacy_portable_zip.stat().st_size / (1024 * 1024)
        print(f"📦 Portables ZIP:   {legacy_portable_zip} ({zip_mb:.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description="ViDow Windows App & Setup Builder")
    parser.add_argument(
        "--installer-only",
        action="store_true",
        help="Erzeugt direkt Setup.exe + Download-ZIP aus einem vorhandenen dist/ViDow-Build.",
    )
    args = parser.parse_args()
    build(installer_only=args.installer_only)


if __name__ == "__main__":
    main()
