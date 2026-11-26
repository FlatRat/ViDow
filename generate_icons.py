#!/usr/bin/env python3
"""
ViDow — Studio-Icon-Generator (Gefaltetes V-Ribbon-Monogramm in Korall-Rot bis Violett)
Erzeugt per analytischem Signed-Distance-Field (SDF) ein gestochen scharfes, perfekt
symmetrisches Apple-HIG-Squircle-Icon für macOS (.icns), Windows (.ico), die Desktop-UI
(static/icon.png & static/icon.svg) sowie die Browser-Erweiterung (extension/icons/*).
"""

from __future__ import annotations

import math
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
EXT_ICONS_DIR = BASE_DIR / "extension" / "icons"


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else (hi if x > hi else x)


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    t = _clamp((x - edge0) / (edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)


def _lerp_rgb(
    c1: tuple[float, float, float], c2: tuple[float, float, float], t: float
) -> tuple[float, float, float]:
    return (
        c1[0] + (c2[0] - c1[0]) * t,
        c1[1] + (c2[1] - c1[1]) * t,
        c1[2] + (c2[2] - c1[2]) * t,
    )


def _sdf_capsule(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
    radius: float,
) -> float:
    pax, pay = px - ax, py - ay
    bax, bay = bx - ax, by - ay
    denom = bax * bax + bay * bay
    h = _clamp((pax * bax + pay * bay) / denom) if denom > 1e-9 else 0.0
    return math.hypot(pax - bax * h, pay - bay * h) - radius


def _sdf_polygon(px: float, py: float, verts: list[tuple[float, float]]) -> float:
    """Exaktes 2D-Polygon-SDF (negativ im Inneren, positiv außerhalb)."""
    d = (px - verts[0][0]) ** 2 + (py - verts[0][1]) ** 2
    s = 1.0
    n = len(verts)
    j = n - 1
    for i in range(n):
        vx, vy = verts[i]
        wx, wy = verts[j]
        ex, ey = wx - vx, wy - vy
        dx, dy = px - vx, py - vy
        denom = ex * ex + ey * ey
        h = _clamp((dx * ex + dy * ey) / denom) if denom > 1e-9 else 0.0
        bx, by = dx - ex * h, dy - ey * h
        sq = bx * bx + by * by
        if sq < d:
            d = sq
        c1 = py >= vy
        c2 = py < wy
        c3 = ex * dy > ey * dx
        if (c1 and c2 and c3) or (not c1 and not c2 and not c3):
            s = -s
        j = i
    return s * math.sqrt(d)


def _inset_convex_polygon(
    verts: list[tuple[float, float]], inset: float
) -> list[tuple[float, float]]:
    """Verschiebt die Kanten eines konvexen Polygons um `inset` nach innen (für exakte Eckenradien)."""
    cx = sum(v[0] for v in verts) / len(verts)
    cy = sum(v[1] for v in verts) / len(verts)
    n = len(verts)
    lines: list[tuple[float, float, float]] = []
    for i in range(n):
        x1, y1 = verts[i]
        x2, y2 = verts[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        nx, ny = -dy / length, dx / length
        # Prüfe Orientierung Richtung Schwerpunkt (innen)
        if nx * (cx - x1) + ny * (cy - y1) < 0:
            nx, ny = -nx, -ny
        c = nx * x1 + ny * y1 + inset
        lines.append((nx, ny, c))

    out: list[tuple[float, float]] = []
    for i in range(n):
        n1x, n1y, c1 = lines[i - 1]
        n2x, n2y, c2 = lines[i]
        det = n1x * n2y - n1y * n2x
        ix = (c1 * n2y - n1y * c2) / det
        iy = (n1x * c2 - c1 * n2x) / det
        out.append((ix, iy))
    return out


def _sdf_squircle(
    px: float, py: float, half_box: float, corner_r: float, exp_k: float = 2.35
) -> float:
    """Kontinuierliche Apple-Superellipse (gerade Kanten + sanfte Lp-Kurvenecken)."""
    inner = half_box - corner_r
    dx = abs(px - 0.5) - inner
    dy = abs(py - 0.5) - inner
    qx = dx if dx > 0.0 else 0.0
    qy = dy if dy > 0.0 else 0.0
    d_out = (qx**exp_k + qy**exp_k) ** (1.0 / exp_k)
    d_in = min(max(dx, dy), 0.0)
    return d_out + d_in - corner_r


def render_master_icon(size: int = 1024) -> Image.Image:
    """
    Rendert ein reduziertes, zeitloses gefaltetes 'V'-Ribbon-Monogramm über einer
    satinierten Download-Basis auf einem warmen Korall-Rot -> Rubin -> Violett Squircle.
    """
    render_sz = 1024
    aa = 1.05 / render_sz
    inv_sz = 1.0 / render_sz

    # Apple macOS HIG Squircle (824px innerhalb 1024px)
    half_box = 0.402
    corner_r = 0.182

    # Typografisches, gefaltetes V-Ribbon (exakt 60°-Geometrie mit sanft gerundeten Kanten)
    r_ribbon = 0.020
    left_raw = [
        (0.252, 0.258),
        (0.410, 0.258),
        (0.5785, 0.547),
        (0.500, 0.682),
    ]
    right_raw = [
        (0.590, 0.258),
        (0.748, 0.258),
        (0.500, 0.682),
        (0.4215, 0.547),
    ]
    left_inset = _inset_convex_polygon(left_raw, r_ribbon)
    right_inset = _inset_convex_polygon(right_raw, r_ribbon)

    # Dezente, elegante Download-Basis-Linie unter der V-Spitze
    bx0, bx1, by_bar = 0.352, 0.648, 0.778
    w_bar = 0.026

    # Farbwelt: Warmes Korall-Rot -> Cinema-Rubin -> Tiefes Royal-Violett
    c_coral = (255.0, 94.0, 62.0)     # #FF5E3E
    c_crimson = (225.0, 29.0, 88.0)   # #E11D58
    c_violet = (76.0, 20.0, 148.0)    # #4C1494
    c_glow = (255.0, 174.0, 128.0)    # Warmer Lichtschein oben links

    # 1. Weicher äußerer Squircle-Schlagschatten
    s_bytes = bytearray(render_sz * render_sz * 4)
    for iy in range(render_sz):
        py = (iy + 0.5) * inv_sz - 0.020
        row_off = iy * render_sz * 4
        for ix in range(render_sz):
            px = (ix + 0.5) * inv_sz
            d_sq = _sdf_squircle(px, py, half_box - 0.006, corner_r)
            if d_sq < aa:
                cov = _clamp(0.5 - d_sq / aa)
                idx = row_off + ix * 4
                s_bytes[idx] = 32
                s_bytes[idx + 1] = 8
                s_bytes[idx + 2] = 52
                s_bytes[idx + 3] = int(125 * cov)
    shadow_layer = Image.frombytes("RGBA", (render_sz, render_sz), bytes(s_bytes))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=render_sz * 0.024))

    # 2. Squircle + gefaltetes V-Monogramm
    fg_bytes = bytearray(render_sz * render_sz * 4)

    # Normalenvektor der linken Innenkante (für sanften Falt-Schatten auf dem rechten Band)
    # Kante von (0.410, 0.258) nach (0.5785, 0.547) -> Richtungsvektor (0.1685, 0.289)
    fold_len = math.hypot(0.1685, 0.289)
    fnx, fny = 0.289 / fold_len, -0.1685 / fold_len  # zeigt nach rechts oben auf den rechten Flügel

    for iy in range(render_sz):
        py = (iy + 0.5) * inv_sz
        row_off = iy * render_sz * 4
        for ix in range(render_sz):
            px = (ix + 0.5) * inv_sz
            d_sq = _sdf_squircle(px, py, half_box, corner_r)
            if d_sq >= aa:
                continue

            sq_alpha = _clamp(0.5 - d_sq / aa)

            nx = (px - 0.098) / 0.804
            ny = (py - 0.098) / 0.804
            t_diag = _clamp(nx * 0.45 + ny * 0.55)
            if t_diag < 0.48:
                u = _smoothstep(0.0, 0.48, t_diag)
                r, g, b = _lerp_rgb(c_coral, c_crimson, u)
            else:
                u = _smoothstep(0.48, 1.0, t_diag)
                r, g, b = _lerp_rgb(c_crimson, c_violet, u)

            dist_glow = math.hypot(px - 0.28, py - 0.18) / 0.58
            if dist_glow < 1.0:
                g_w = ((1.0 - dist_glow * dist_glow) ** 2) * 0.34
                r, g, b = _lerp_rgb((r, g, b), c_glow, g_w)

            dist_deep = math.hypot(px - 0.80, py - 0.86) / 0.62
            if dist_deep < 1.0:
                d_w = ((1.0 - dist_deep) ** 2) * 0.22
                r, g, b = _lerp_rgb((r, g, b), (36.0, 8.0, 76.0), d_w)

            # Dezente innere Glaskante am Squircle-Rand (nur als hauchfeiner Lichtsaum ohne dunklen Graben)
            if -0.008 < d_sq < 0.0:
                rim_t = 1.0 + d_sq / 0.008
                rim_light = (rim_t * rim_t) * _clamp(1.1 - (nx * 0.45 + ny * 0.9))
                if rim_light > 0.0:
                    r, g, b = _lerp_rgb((r, g, b), (255.0, 236.0, 228.0), rim_light * 0.34)

            # Monogramm-Bereich prüfen (Bounding Box für Performance)
            if 0.20 < px < 0.80 and 0.21 < py < 0.86:
                # Weicher Schatten unter dem Monogramm
                spy = py - 0.017
                sd_l = _sdf_polygon(px, spy, left_inset) - r_ribbon
                sd_r = _sdf_polygon(px, spy, right_inset) - r_ribbon
                sd_b = _sdf_capsule(px, spy, bx0, by_bar, bx1, by_bar, w_bar)
                sd_min = min(sd_l, sd_r, sd_b)
                if sd_min < 0.034:
                    sh_t = _clamp(1.0 - max(0.0, sd_min + 0.004) / 0.038)
                    r, g, b = _lerp_rgb((r, g, b), (26.0, 5.0, 54.0), (sh_t * sh_t) * 0.28)

                # Exakte SDFs für linken Flügel, rechten Flügel und Download-Tray
                d_left = _sdf_polygon(px, py, left_inset) - r_ribbon
                d_right = _sdf_polygon(px, py, right_inset) - r_ribbon
                d_bar = _sdf_capsule(px, py, bx0, by_bar, bx1, by_bar, w_bar)

                # 1. Zuerst satinierte Download-Basis-Pille (82 % Deckkraft = edler Milchglas-Effekt)
                if d_bar < aa:
                    bar_cov = _clamp(0.5 - d_bar / aa) * 0.82
                    r, g, b = _lerp_rgb((r, g, b), (255.0, 244.0, 250.0), bar_cov)

                # 2. Rechter V-Flügel (mit seidigem Rosé-Lavendel-Falzschatten nahe der Überlappungskante)
                if d_right < aa:
                    right_cov = _clamp(0.5 - d_right / aa)
                    # Abstand senkrecht zur Faltkante des linken Flügels
                    dist_from_fold = (px - 0.410) * fnx + (py - 0.258) * fny
                    fold_shade = (1.0 - _smoothstep(0.0, 0.16, max(0.0, dist_from_fold))) * 0.19
                    rr = 255.0 - fold_shade * 22.0
                    rg = 255.0 - fold_shade * 96.0
                    rb = 255.0 - fold_shade * 48.0
                    r, g, b = _lerp_rgb((r, g, b), (rr, rg, rb), right_cov)

                # 3. Linker V-Flügel liegt klar und reinweiß darüber (bildet die ikonische V-Faltung)
                if d_left < aa:
                    left_cov = _clamp(0.5 - d_left / aa)
                    r, g, b = _lerp_rgb((r, g, b), (255.0, 255.0, 255.0), left_cov)

            idx = row_off + ix * 4
            fg_bytes[idx] = int(round(_clamp(r, 0.0, 255.0)))
            fg_bytes[idx + 1] = int(round(_clamp(g, 0.0, 255.0)))
            fg_bytes[idx + 2] = int(round(_clamp(b, 0.0, 255.0)))
            fg_bytes[idx + 3] = int(round(sq_alpha * 255.0))

    fg_layer = Image.frombytes("RGBA", (render_sz, render_sz), bytes(fg_bytes))
    composed = Image.alpha_composite(shadow_layer, fg_layer)

    if size != render_sz:
        return composed.resize((size, size), Image.Resampling.LANCZOS)
    return composed


SVG_ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" fill="none">
  <defs>
    <linearGradient id="vidow-bg" x1="14" y1="12" x2="114" y2="116" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#FF5E3E"/>
      <stop offset="48%" stop-color="#E11D58"/>
      <stop offset="100%" stop-color="#4C1494"/>
    </linearGradient>
    <radialGradient id="vidow-warm" cx="0.28" cy="0.18" r="0.58">
      <stop offset="0%" stop-color="#FFAE80" stop-opacity="0.36"/>
      <stop offset="100%" stop-color="#FF5E3E" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="vidow-rwing" x1="60" y1="74" x2="92" y2="34" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#F6C8DC"/>
      <stop offset="68%" stop-color="#FFFFFF"/>
    </linearGradient>
    <filter id="vidow-shadow" x="14%" y="16%" width="72%" height="76%">
      <feDropShadow dx="0" dy="2.2" stdDeviation="2.4" flood-color="#1A0536" flood-opacity="0.26"/>
    </filter>
  </defs>
  <rect x="10" y="10" width="108" height="108" rx="25" fill="url(#vidow-bg)"/>
  <rect x="10" y="10" width="108" height="108" rx="25" fill="url(#vidow-warm)"/>
  <rect x="10.75" y="10.75" width="106.5" height="106.5" rx="24.25" stroke="#FFECE4" stroke-opacity="0.28" stroke-width="1.5"/>
  <g filter="url(#vidow-shadow)">
    <!-- Satinierte Download-Basis -->
    <rect x="42" y="96.2" width="44" height="6.6" rx="3.3" fill="#FFF4FA" fill-opacity="0.82"/>
    <!-- Rechter V-Ribbon-Flügel mit sanftem Falzverlauf -->
    <path d="M76.5 33H94.2C95.6 33 96.5 34.5 95.8 35.7L65.6 87.3C64.9 88.5 63.1 88.5 62.4 87.3L54.8 74.3L74.9 34.0C75.2 33.4 75.8 33 76.5 33Z" fill="url(#vidow-rwing)"/>
    <!-- Linker V-Ribbon-Flügel reinweiß darüber gefaltet -->
    <path d="M33.8 33H51.5C52.2 33 52.8 33.4 53.1 34.0L73.2 70.0L65.6 87.3C64.9 88.5 63.1 88.5 62.4 87.3L32.2 35.7C31.5 34.5 32.4 33 33.8 33Z" fill="#FFFFFF"/>
  </g>
</svg>
"""


def _safe_save_img(img: Image.Image, path: Path, **kwargs: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    img.save(path, **kwargs)


def generate_all_icons(extra_icns_path: Path | None = None) -> Path:
    """Erzeugt alle Icon-Dateien im Projekt und gibt den Pfad zu AppIcon.icns zurück."""
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    EXT_ICONS_DIR.mkdir(parents=True, exist_ok=True)

    master_1024 = render_master_icon(1024)

    # 1. PNG & SVG für Desktop-UI und Laufzeit-Dock
    icon_512 = master_1024.resize((512, 512), Image.Resampling.LANCZOS)
    _safe_save_img(icon_512, STATIC_DIR / "icon.png", format="PNG")
    svg_path = STATIC_DIR / "icon.svg"
    if svg_path.exists():
        svg_path.unlink()
    svg_path.write_text(SVG_ICON, encoding="utf-8")

    # 2. Windows Multi-Size .ico (reduzierter Außenrand gegenüber macOS HIG,
    #    damit das Icon in Windows-Taskleiste, Titelleiste & Explorer in voller Fluent-Größe erscheint)
    win_crop_margin = int(round(1024 * 0.066))  # 68px -> ~93% Canvas-Füllung inkl. sanftem Schatten
    win_master = master_1024.crop(
        (win_crop_margin, win_crop_margin, 1024 - win_crop_margin, 1024 - win_crop_margin)
    ).resize((1024, 1024), Image.Resampling.LANCZOS)
    ico_path = STATIC_DIR / "icon.ico"
    _safe_save_img(
        win_master,
        ico_path,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    # 3. Chrome / Brave / Edge Extension Icons (exakte Pixelgrößen, ebenfalls randoptimiert)
    for ext_sz in (16, 48, 128):
        resized = win_master.resize((ext_sz, ext_sz), Image.Resampling.LANCZOS)
        _safe_save_img(resized, EXT_ICONS_DIR / f"icon-{ext_sz}.png", format="PNG")

    # 4. macOS AppIcon.icns (falls auf macOS und iconutil verfügbar)
    icns_target = STATIC_DIR / "AppIcon.icns"
    if sys.platform == "darwin":
        with tempfile.TemporaryDirectory() as tmp:
            iconset = Path(tmp) / "AppIcon.iconset"
            iconset.mkdir()
            for s in (16, 32, 128, 256, 512):
                img_1x = master_1024.resize((s, s), Image.Resampling.LANCZOS)
                img_2x = master_1024.resize((s * 2, s * 2), Image.Resampling.LANCZOS)
                img_1x.save(iconset / f"icon_{s}x{s}.png", format="PNG")
                img_2x.save(iconset / f"icon_{s}x{s}@2x.png", format="PNG")

            if icns_target.exists():
                icns_target.unlink()
            subprocess.run(
                ["iconutil", "-c", "icns", str(iconset), "-o", str(icns_target)],
                check=True,
            )
            if extra_icns_path is not None:
                extra_icns_path.parent.mkdir(parents=True, exist_ok=True)
                if extra_icns_path.exists():
                    extra_icns_path.unlink()
                subprocess.run(
                    ["iconutil", "-c", "icns", str(iconset), "-o", str(extra_icns_path)],
                    check=True,
                )

    return icns_target


if __name__ == "__main__":
    out = generate_all_icons()
    print(f"✅ Gefaltetes V-Ribbon-Icon erfolgreich generiert ({STATIC_DIR / 'icon.png'}, {STATIC_DIR / 'icon.ico'}, {out})")
