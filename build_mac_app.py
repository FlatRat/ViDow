#!/usr/bin/env python3
"""
ViDow 2.0 — Standalone macOS App-, DMG- & Download-ZIP-Builder
Erzeugt ein komplett eigenständiges, auslieferbares macOS-App-Bundle ('ViDow.app')
inklusive eingebetteter Python-Laufzeit, pywebview, yt-dlp, curl_cffi, integriertem
ffmpeg (imageio-ffmpeg), Studio-Icons (.icns), Ad-hoc-Codesigning sowie:
1. einem versandfertigen 'ViDow-<version>-macOS.dmg' Disk-Image (mit Applications-Symlink)
2. einem fertigen Download-ZIP 'ViDow-<version>-macOS.zip' (inkl. ViDow.app, Anleitung & Extension)
"""

from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from generate_icons import generate_all_icons

APP_VERSION = "2.0.3"
BUNDLE_ID = "de.lucasgoedel.vidow"

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"
ROOT_APP_BUNDLE = BASE_DIR / "ViDow.app"


def _patch_info_plist(app_bundle: Path) -> None:
    """Ergänzt wichtige macOS-Metadaten und ATS-Freigaben in Contents/Info.plist."""
    plist_path = app_bundle / "Contents" / "Info.plist"
    data: dict = {}
    if plist_path.is_file():
        with open(plist_path, "rb") as fp:
            data = plistlib.load(fp)

    data.update(
        {
            "CFBundleName": "ViDow",
            "CFBundleDisplayName": "ViDow",
            "CFBundleIdentifier": BUNDLE_ID,
            "CFBundleVersion": APP_VERSION,
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundlePackageType": "APPL",
            "CFBundleIconFile": "AppIcon.icns",
            "LSMinimumSystemVersion": "11.0",
            "LSApplicationCategoryType": "public.app-category.video",
            "NSHumanReadableCopyright": "© lg-craft (https://lg-craft.com)",
            "NSHighResolutionCapable": True,
            "NSSupportsAutomaticGraphicsSwitching": True,
            # Erlaubt WebKit den Zugriff auf den lokalen ViDow-HTTP-Server (127.0.0.1)
            # sowie Vorschaubilder externer Video-Plattformen
            "NSAppTransportSecurity": {
                "NSAllowsArbitraryLoads": True,
                "NSAllowsLocalNetworking": True,
            },
        }
    )
    with open(plist_path, "wb") as fp:
        plistlib.dump(data, fp)


def _apply_finder_icon(target_path: Path, icon_png: Path) -> None:
    """Setzt das Icon zusätzlich im macOS Finder-Cache (falls AppKit verfügbar ist)."""
    try:
        import AppKit

        ws = AppKit.NSWorkspace.sharedWorkspace()
        ns_img = AppKit.NSImage.alloc().initWithContentsOfFile_(str(icon_png))
        if ns_img and target_path.exists():
            ws.setIcon_forFile_options_(ns_img, str(target_path), 0)
    except Exception:
        pass


def create_dmg(app_bundle: Path, dmg_path: Path) -> None:
    """Erzeugt ein komprimiertes, auslieferbares macOS .dmg mit ViDow.app & /Applications-Link."""
    if dmg_path.exists():
        dmg_path.unlink()
    dmg_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="vidow_dmg_") as staging_str:
        staging = Path(staging_str)
        staged_app = staging / "ViDow.app"
        subprocess.run(
            ["ditto", "--norsrc", "--noextattr", str(app_bundle), str(staged_app)],
            check=True,
        )
        os.symlink("/Applications", staging / "Applications")

        subprocess.run(
            [
                "hdiutil",
                "create",
                "-volname",
                "ViDow",
                "-srcfolder",
                str(staging),
                "-ov",
                "-format",
                "UDZO",
                str(dmg_path),
            ],
            check=True,
        )


def create_download_zip(app_bundle: Path, zip_path: Path) -> None:
    """
    Verpackt die signierte ViDow.app + Kurzanleitung + optionale Browser-Erweiterung
    per macOS 'ditto' in ein fertiges Download-ZIP (erhält Symlinks, Rechte & Codesignatur).
    """
    if zip_path.exists():
        zip_path.unlink()
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    readme_txt = (
        f"ViDow Studio v{APP_VERSION} für macOS (ab macOS 11)\n"
        "====================================================\n\n"
        "Ein Projekt von lg-craft (https://lg-craft.com)\n\n"
        "INSTALLATION (1 KLICK):\n"
        "1. Ziehe 'ViDow.app' in deinen Ordner 'Programme' (/Applications).\n"
        "2. Öffne 'ViDow' aus dem Programme-Ordner.\n"
        "   - Python oder ffmpeg müssen NICHT separat installiert werden (alles integriert).\n"
        "   - Hinweis beim allerersten Start (macOS Gatekeeper):\n"
        "     Falls macOS meldet, dass die App nicht verifiziert werden kann, klicke mit\n"
        "     Rechtsklick (Ctrl-Klick) auf 'ViDow.app' -> 'Öffnen' (oder bestätige sie\n"
        "     unter 'Systemeinstellungen -> Datenschutz & Sicherheit -> Dennoch öffnen').\n\n"
        "OPTIONALE BROWSER-ERWEITERUNG (Chrome / Brave / Edge):\n"
        "1. Lege den mitgelieferten Ordner 'extension' an einen festen Ort (z. B. Dokumente).\n"
        "2. Öffne 'chrome://extensions' (bzw. 'brave://extensions' oder 'edge://extensions'),\n"
        "   aktiviere oben rechts den 'Entwicklermodus' und wähle\n"
        "   'Entpackte Erweiterung laden' -> Ordner 'extension'.\n"
    )

    folder_name = f"ViDow-{APP_VERSION}-macOS"
    with tempfile.TemporaryDirectory(prefix="vidow_zip_") as staging_str:
        staging_root = Path(staging_str) / folder_name
        staging_root.mkdir(parents=True, exist_ok=True)

        staged_app = staging_root / "ViDow.app"
        subprocess.run(
            ["ditto", "--norsrc", "--noextattr", str(app_bundle), str(staged_app)],
            check=True,
        )
        (staging_root / "LIESMICH - Installation.txt").write_text(readme_txt, encoding="utf-8")

        ext_dir = BASE_DIR / "extension"
        if ext_dir.is_dir():
            staged_ext = staging_root / "extension"
            shutil.copytree(
                ext_dir,
                staged_ext,
                ignore=shutil.ignore_patterns(".DS_Store", "__pycache__", ".*"),
            )

        subprocess.run(["xattr", "-cr", str(staging_root)], check=False)
        subprocess.run(
            [
                "ditto",
                "-c",
                "-k",
                "--norsrc",
                "--noextattr",
                "--keepParent",
                str(staging_root),
                str(zip_path),
            ],
            check=True,
        )


def build_dev_wrapper(icns_path: Path) -> None:
    """Schneller lokaler Entwicklungs-Wrapper (nutzt .venv direkt im Projektordner)."""
    contents_dir = ROOT_APP_BUNDLE / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"

    if ROOT_APP_BUNDLE.exists():
        shutil.rmtree(ROOT_APP_BUNDLE)

    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(icns_path, resources_dir / "AppIcon.icns")

    _patch_info_plist(ROOT_APP_BUNDLE)
    plist_path = contents_dir / "Info.plist"
    with open(plist_path, "rb") as fp:
        pl = plistlib.load(fp)
    pl["CFBundleExecutable"] = "ViDow"
    with open(plist_path, "wb") as fp:
        plistlib.dump(pl, fp)

    launcher_script = f"""#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
PROJECT_DIR="{BASE_DIR}"
cd "$PROJECT_DIR"
exec "$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/app.py" >> /tmp/vidow.log 2>&1
"""
    executable_path = macos_dir / "ViDow"
    executable_path.write_text(launcher_script, encoding="utf-8")
    executable_path.chmod(
        executable_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    _apply_finder_icon(ROOT_APP_BUNDLE, STATIC_DIR / "icon.png")
    print(f"✅ Lokaler Dev-Wrapper erstellt: {ROOT_APP_BUNDLE}")


def build_standalone(skip_dmg: bool = False) -> None:
    """Baut die eigenständige, auslieferbare ViDow.app + ViDow-<version>-macOS.dmg."""
    if sys.platform != "darwin":
        print("Dieses Build-Skript ist für macOS gedacht.")
        sys.exit(1)

    print("=" * 64)
    print(f"🎬 ViDow v{APP_VERSION} — Native macOS Standalone-App & DMG Build")
    print("=" * 64)

    # 1. Alle Icons frisch rendern
    icns_path = generate_all_icons()
    print(f"🎨 Icons generiert: {icns_path}")

    # 2. PyInstaller prüfen
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("⬇️ Installiere PyInstaller & Build-Abhängigkeiten...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyinstaller", "pillow", "imageio-ffmpeg"],
            check=True,
        )

    # 3. Alte Artefakte bereinigen
    dist_app = DIST_DIR / "ViDow.app"
    for p in (dist_app, DIST_DIR / "ViDow", BUILD_DIR):
        if p.exists():
            shutil.rmtree(p)

    # 4. PyInstaller ausführen
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
        "--osx-bundle-identifier",
        BUNDLE_ID,
        "--icon",
        str(icns_path),
        "--add-data",
        f"{STATIC_DIR}:static",
        "--collect-all",
        "yt_dlp",
        "--collect-all",
        "curl_cffi",
        "--collect-all",
        "webview",
        "--collect-all",
        "imageio_ffmpeg",
        "--hidden-import",
        "PyObjCTools.AppHelper",
        str(BASE_DIR / "app.py"),
    ]
    print("\n📦 Kompiliere eigenständiges macOS App-Bundle (PyInstaller)...")
    subprocess.run(cmd, check=True)

    if not dist_app.is_dir():
        raise RuntimeError(f"Erwartetes App-Bundle wurde nicht erzeugt: {dist_app}")

    # Sicherstellen, dass AppIcon.icns unter Contents/Resources/AppIcon.icns liegt
    res_icns = dist_app / "Contents" / "Resources" / "AppIcon.icns"
    shutil.copy2(icns_path, res_icns)
    _patch_info_plist(dist_app)

    # 5. Finder-Metadaten/Resource-Forks entfernen & Ad-hoc Codesigning (--strict kompatibel!)
    print("🔏 Bereinige Extended Attributes & signiere ViDow.app (ad-hoc codesign)...")
    subprocess.run(["xattr", "-cr", str(dist_app)], check=False)
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(dist_app)],
        check=True,
    )
    subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", str(dist_app)],
        check=True,
    )

    # 6. Auch ./ViDow.app im Projektstamm aktualisieren (per ditto --norsrc --noextattr)
    if ROOT_APP_BUNDLE.exists():
        shutil.rmtree(ROOT_APP_BUNDLE)
    subprocess.run(
        ["ditto", "--norsrc", "--noextattr", str(dist_app), str(ROOT_APP_BUNDLE)],
        check=True,
    )

    cmd_file = BASE_DIR / "ViDow.command"
    if cmd_file.exists():
        _apply_finder_icon(cmd_file, STATIC_DIR / "icon.png")

    # Alte DMG-/ZIP-Versionen im dist-Ordner aufräumen
    if DIST_DIR.is_dir():
        for old_pkg in list(DIST_DIR.glob("ViDow-*-macOS.dmg")) + list(DIST_DIR.glob("ViDow-*-macOS.zip")):
            old_pkg.unlink(missing_ok=True)

    # 7. Auslieferbares .dmg Installer-Image & Download-.zip bauen
    dmg_path = DIST_DIR / f"ViDow-{APP_VERSION}-macOS.dmg"
    zip_path = DIST_DIR / f"ViDow-{APP_VERSION}-macOS.zip"
    if not skip_dmg:
        print(f"💿 Erzeuge auslieferbares Disk-Image: {dmg_path.name}...")
        create_dmg(dist_app, dmg_path)

    print(f"🗜️ Schnüre fertiges Download-ZIP: {zip_path.name}...")
    create_download_zip(dist_app, zip_path)

    print("\n" + "=" * 64)
    print("✅ Native macOS-App & Download-Pakete erfolgreich gebaut!")
    print(f"🍏 Standalone App:  {dist_app}")
    print(f"🍏 Projekt-Kopie:   {ROOT_APP_BUNDLE}")
    if not skip_dmg and dmg_path.is_file():
        dmg_mb = dmg_path.stat().st_size / (1024 * 1024)
        print(f"💿 Installer-DMG:   {dmg_path} ({dmg_mb:.1f} MB)")
    if zip_path.is_file():
        zip_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"📦 Download-ZIP:    {zip_path} ({zip_mb:.1f} MB)")
    print("=" * 64)


def main() -> None:
    parser = argparse.ArgumentParser(description="ViDow macOS App, DMG & Download-ZIP Builder")
    parser.add_argument(
        "--dev-wrapper",
        action="store_true",
        help="Erzeugt nur einen schlanken .venv-Starter statt eines eigenständigen Bundles.",
    )
    parser.add_argument(
        "--no-dmg",
        action="store_true",
        help="Überspringt die Erstellung der .dmg-Datei.",
    )
    parser.add_argument(
        "--zip-only",
        action="store_true",
        help=" Schnürt direkt das fertige Download-ZIP aus einem vorhandenen dist/ViDow.app-Build.",
    )
    args = parser.parse_args()

    if args.dev_wrapper:
        icns = generate_all_icons()
        build_dev_wrapper(icns)
    elif args.zip_only:
        dist_app = DIST_DIR / "ViDow.app"
        if not dist_app.is_dir():
            raise SystemExit(f"Kein vorhandenes App-Bundle unter {dist_app} gefunden.")
        zip_path = DIST_DIR / f"ViDow-{APP_VERSION}-macOS.zip"
        create_download_zip(dist_app, zip_path)
        zip_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"📦 Download-ZIP erstellt: {zip_path} ({zip_mb:.1f} MB)")
    else:
        build_standalone(skip_dmg=args.no_dmg)


if __name__ == "__main__":
    main()
