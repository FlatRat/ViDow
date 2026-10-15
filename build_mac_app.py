#!/usr/bin/env python3
"""
Erzeugt das native macOS App-Bundle 'ViDow.app' inklusive hochauflösendem
Vektor-Icon (exakt passend zum ViDow-Logo aus dem Dashboard) und setzt das Icon
direkt für Finder (ViDow.app & ViDow.command), Dock und Browser-Extension.
"""

from __future__ import annotations

import plistlib
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

import AppKit
import Foundation

BASE_DIR = Path(__file__).resolve().parent
APP_BUNDLE = BASE_DIR / "ViDow.app"
STATIC_DIR = BASE_DIR / "static"
EXT_ICONS_DIR = BASE_DIR / "extension" / "icons"


def render_vidow_icon_nsimage(size: int = 1024) -> AppKit.NSImage:
    """
    Zeichnet das ViDow-Logo (blauer macOS-Squircle mit weißem Play-Dreieck und
    Download-Pfeil rechts unten – exakt wie das SVG im Header) als Vektorgrafik.
    """
    img = AppKit.NSImage.alloc().initWithSize_(Foundation.NSMakeSize(size, size))
    img.lockFocus()

    ctx = AppKit.NSGraphicsContext.currentContext()
    ctx.setShouldAntialias_(True)
    ctx.setImageInterpolation_(AppKit.NSImageInterpolationHigh)

    pad = size * 0.08
    box_size = size - 2 * pad
    radius = box_size * 0.225
    rect = Foundation.NSMakeRect(pad, pad, box_size, box_size)

    # Hintergrund-Squircle mit Farbverlauf (#3B82F6 oben -> #1D4ED8 unten)
    bg_path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        rect, radius, radius
    )
    top_color = AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(
        0.22, 0.48, 0.96, 1.0
    )
    bottom_color = AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(
        0.11, 0.28, 0.82, 1.0
    )
    gradient = AppKit.NSGradient.alloc().initWithStartingColor_endingColor_(
        bottom_color, top_color
    )
    gradient.drawInBezierPath_angle_(bg_path, 90.0)

    # Dezenter heller Innenrahmen
    AppKit.NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.18).setStroke()
    bg_path.setLineWidth_(size * 0.012)
    bg_path.stroke()

    # Koordinaten-Helfer: rechnet die 24x24 SVG-ViewBox (y von oben nach unten)
    # in das macOS-Koordinatensystem (y von unten nach oben) innerhalb des Icons um.
    inner_pad = size * 0.23
    inner_span = size - 2 * inner_pad

    def pt(svg_x: float, svg_y: float) -> Foundation.NSPoint:
        nx = (svg_x - 3.0) / 19.0
        ny = 1.0 - ((svg_y - 3.0) / 18.0)
        return Foundation.NSMakePoint(
            inner_pad + nx * inner_span,
            inner_pad + ny * inner_span,
        )

    AppKit.NSColor.whiteColor().setStroke()
    stroke_w = size * 0.058

    # 1. Play-Dreieck: polygon points="5 3, 19 12, 5 21"
    play_path = AppKit.NSBezierPath.bezierPath()
    play_path.setLineWidth_(stroke_w)
    play_path.setLineCapStyle_(AppKit.NSLineCapStyleRound)
    play_path.setLineJoinStyle_(AppKit.NSLineJoinStyleRound)
    play_path.moveToPoint_(pt(5, 3))
    play_path.lineToPoint_(pt(18.5, 11.5))
    play_path.lineToPoint_(pt(5, 20))
    play_path.closePath()
    play_path.stroke()

    # Kleiner blauer Freiraum rechts unten für den Download-Pfeil, damit er sich klar abhebt
    badge_center = pt(19, 18)
    badge_r = size * 0.145
    badge_rect = Foundation.NSMakeRect(
        badge_center.x - badge_r,
        badge_center.y - badge_r,
        badge_r * 2,
        badge_r * 2,
    )
    badge_bg = AppKit.NSBezierPath.bezierPathWithOvalInRect_(badge_rect)
    bottom_color.setFill()
    badge_bg.fill()

    # 2. Download-Pfeil: line (19,14)->(19,21) + polyline (15.5,17.8)->(19,21.2)->(22.5,17.8)
    AppKit.NSColor.whiteColor().setStroke()
    arrow_path = AppKit.NSBezierPath.bezierPath()
    arrow_path.setLineWidth_(stroke_w * 0.92)
    arrow_path.setLineCapStyle_(AppKit.NSLineCapStyleRound)
    arrow_path.setLineJoinStyle_(AppKit.NSLineJoinStyleRound)
    arrow_path.moveToPoint_(pt(19, 13.8))
    arrow_path.lineToPoint_(pt(19, 21.0))
    arrow_path.moveToPoint_(pt(15.6, 17.8))
    arrow_path.lineToPoint_(pt(19, 21.2))
    arrow_path.lineToPoint_(pt(22.4, 17.8))
    arrow_path.stroke()

    img.unlockFocus()
    return img


def save_nsimage_as_png(img: AppKit.NSImage, out_path: Path, pixel_size: int) -> None:
    rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None,
        pixel_size,
        pixel_size,
        8,
        4,
        True,
        False,
        AppKit.NSCalibratedRGBColorSpace,
        0,
        0,
    )
    rep.setSize_(Foundation.NSMakeSize(pixel_size, pixel_size))

    AppKit.NSGraphicsContext.saveGraphicsState()
    ctx = AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    AppKit.NSGraphicsContext.setCurrentContext_(ctx)
    ctx.setShouldAntialias_(True)
    ctx.setImageInterpolation_(AppKit.NSImageInterpolationHigh)
    img.drawInRect_fromRect_operation_fraction_(
        Foundation.NSMakeRect(0, 0, pixel_size, pixel_size),
        Foundation.NSZeroRect,
        AppKit.NSCompositingOperationSourceOver,
        1.0,
    )
    AppKit.NSGraphicsContext.restoreGraphicsState()

    png_data = rep.representationUsingType_properties_(
        AppKit.NSBitmapImageFileTypePNG, {}
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    png_data.writeToFile_atomically_(str(out_path), True)


def create_icns_and_assets(resources_dir: Path) -> AppKit.NSImage:
    ns_img = render_vidow_icon_nsimage(1024)

    # Speichere hochauflösendes PNG auch unter static/icon.png (für das Laufzeit-Dock-Icon)
    save_nsimage_as_png(ns_img, STATIC_DIR / "icon.png", 512)

    # Speichere echte PNG-Größen für die Browser-Erweiterung
    EXT_ICONS_DIR.mkdir(parents=True, exist_ok=True)
    for ext_sz in (16, 48, 128):
        save_nsimage_as_png(ns_img, EXT_ICONS_DIR / f"icon-{ext_sz}.png", ext_sz)

    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "AppIcon.iconset"
        iconset.mkdir()

        for s in (16, 32, 128, 256, 512):
            save_nsimage_as_png(ns_img, iconset / f"icon_{s}x{s}.png", s)
            save_nsimage_as_png(ns_img, iconset / f"icon_{s}x{s}@2x.png", s * 2)

        icns_out = resources_dir / "AppIcon.icns"
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(icns_out)],
            check=True,
        )

    return ns_img


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
        "CFBundleIconFile": "AppIcon.icns",
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
    executable_path.chmod(
        executable_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )

    ns_img = create_icns_and_assets(resources_dir)

    # Setze das Icon direkt im macOS Finder (NSWorkspace) für ViDow.app & ViDow.command,
    # damit der Finder das Icon sofort ohne Cache-Verzögerung anzeigt!
    ws = AppKit.NSWorkspace.sharedWorkspace()
    ws.setIcon_forFile_options_(ns_img, str(APP_BUNDLE), 0)
    cmd_file = BASE_DIR / "ViDow.command"
    if cmd_file.exists():
        ws.setIcon_forFile_options_(ns_img, str(cmd_file), 0)

    subprocess.run(["touch", str(APP_BUNDLE)], check=False)
    print(f"✅ ViDow.app & Icons erfolgreich erstellt: {APP_BUNDLE}")


if __name__ == "__main__":
    build_app()
