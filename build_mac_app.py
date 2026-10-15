#!/usr/bin/env python3
"""
Erzeugt das native macOS App-Bundle 'ViDow.app' im Projektordner.
Damit lässt sich ViDow wie ein normales Mac-Programm (im Dock oder Finder)
komplett ohne Terminal-Fenster und ohne Webbrowser starten.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import stat
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
APP_BUNDLE = BASE_DIR / "ViDow.app"


def make_icon_png(path: Path, size: int = 512) -> None:
    """Erzeugt ein modernes blaues App-Icon (Abgerundetes Quadrat + Play/Download-Symbol) als PNG."""
    rows: list[bytes] = []
    radius = size * 0.22
    pad = size * 0.06

    for y in range(size):
        row = bytearray([0])  # PNG Filter-Byte 0
        for x in range(size):
            # Prüfe ob innerhalb des abgerundeten Quadrats
            in_box = False
            if pad <= x < size - pad and pad <= y < size - pad:
                in_box = True
                # Ecken abrunden
                cx = pad + radius if x < pad + radius else (size - pad - radius if x > size - pad - radius else x)
                cy = pad + radius if y < pad + radius else (size - pad - radius if y > size - pad - radius else y)
                if (x - cx) ** 2 + (y - cy) ** 2 > radius ** 2:
                    in_box = False

            if not in_box:
                row.extend((0, 0, 0, 0))
                continue

            # Farbverlauf Blau (#2563EB -> #1D4ED8)
            t = y / size
            r = int(37 * (1 - t) + 25 * t)
            g = int(99 * (1 - t) + 65 * t)
            b = int(235 * (1 - t) + 205 * t)

            # Weißes Play-Dreieck in der Mitte
            nx = (x - size * 0.5) / (size * 0.5)
            ny = (y - size * 0.5) / (size * 0.5)

            is_symbol = False
            # Play-Dreieck links-mittig
            if -0.28 <= nx <= 0.22 and abs(ny) <= (0.22 - nx) * 0.68:
                is_symbol = True
            # Kleiner Download-Pfeil rechts unten
            if 0.14 <= nx <= 0.26 and 0.02 <= ny <= 0.30:
                is_symbol = True
            if 0.04 <= nx <= 0.36 and 0.22 <= ny <= 0.38 and (ny - 0.22) >= abs(nx - 0.20) - 0.02 and (ny - 0.22) <= 0.16:
                is_symbol = True

            if is_symbol:
                row.extend((255, 255, 255, 255))
            else:
                row.extend((r, g, b, 255))
        rows.append(bytes(row))

    raw = b"".join(rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack("!I", len(data))
            + tag
            + data
            + struct.pack("!I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack("!IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def create_icns(resources_dir: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        master_png = tmp_path / "master.png"
        make_icon_png(master_png, 512)

        iconset = tmp_path / "AppIcon.iconset"
        iconset.mkdir()

        sizes = [16, 32, 128, 256, 512]
        for s in sizes:
            subprocess.run(
                ["sips", "-z", str(s), str(s), str(master_png), "--out", str(iconset / f"icon_{s}x{s}.png")],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            subprocess.run(
                ["sips", "-z", str(s * 2), str(s * 2), str(master_png), "--out", str(iconset / f"icon_{s}x{s}@2x.png")],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

        icns_out = resources_dir / "AppIcon.icns"
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(icns_out)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def build_app() -> None:
    contents_dir = APP_BUNDLE / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"

    if APP_BUNDLE.exists():
        shutil.rmtree(APP_BUNDLE)

    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    info_plist = {
        "CFBundleName": "ViDow",
        "CFBundleDisplayName": "ViDow",
        "CFBundleIdentifier": "de.lucasgoedel.vidow",
        "CFBundleVersion": "1.1.0",
        "CFBundleShortVersionString": "1.1.0",
        "CFBundlePackageType": "APPL",
        "CFBundleExecutable": "ViDow",
        "CFBundleIconFile": "AppIcon",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
    }
    with open(contents_dir / "Info.plist", "wb") as fp:
        plistlib.dump(info_plist, fp)

    launcher_script = f"""#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
PROJECT_DIR="{BASE_DIR}"
cd "$PROJECT_DIR"
exec "$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/app.py" >> /tmp/vidow.log 2>&1
"""
    executable_path = macos_dir / "ViDow"
    executable_path.write_text(launcher_script, encoding="utf-8")
    executable_path.chmod(executable_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    create_icns(resources_dir)
    print(f"✅ macOS App-Bundle erstellt: {APP_BUNDLE}")


if __name__ == "__main__":
    build_app()
