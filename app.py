#!/usr/bin/env python3
"""
ViDow — Lokaler Video-Downloader & Stream-Sniffer (Backend)
Unterstützt Qualitäts-/Codec-Auswahl, freie Speicherortwahl (inkl. macOS Finder-Dialog),
automatische Pre-Roll-Werbe-Filterung, SponsorBlock-Zuschnitt und Browser-Extension-Anbindung.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError

# Auf Windows UTF-8 für Konsole erzwingen, um UnicodeEncodeErrors bei Emojis zu verhindern
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
SETTINGS_FILE = BASE_DIR / "settings.json"
DEFAULT_PORT = int(os.environ.get("VIDOW_PORT", "8765"))

# Bekannte Werbe-Domains und URL-Muster für Stream-/Eintragsfilterung
AD_PATTERNS = re.compile(
    r"(doubleclick\.net|googlesyndication\.com|imasdk\.googleapis\.com|"
    r"smartclip\.net|fwmrm\.net|adnxs\.com|spotxchange\.com|teads\.tv|"
    r"pubmatic\.com|rubiconproject\.com|criteo\.com|outbrain\.com|"
    r"taboola\.com|2mdn\.net|innovid\.com|flashtalking\.com|serving-sys\.com|"
    r"[/_.-](vast|vmap|preroll|midroll|adserver|adbreak|advert)[/_.-]?)",
    re.IGNORECASE,
)


def find_ffmpeg() -> str | None:
    """Sucht ffmpeg im PATH sowie in typischen Windows-, macOS- und Linux-Pfaden."""
    # 1. Direkte Suche im PATH
    which_ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if which_ffmpeg and os.path.isfile(which_ffmpeg):
        return which_ffmpeg

    # 2. Projekt-lokaler Ordner (z. B. bin/ffmpeg.exe)
    for cand in [
        BASE_DIR / "bin" / "ffmpeg.exe",
        BASE_DIR / "ffmpeg.exe",
        BASE_DIR / "bin" / "ffmpeg",
        BASE_DIR / "ffmpeg",
    ]:
        if cand.is_file():
            return str(cand)

    # 3. Typische Windows-Installationspfade (WinGet, Scoop, Chocolatey, Standard-Pfade)
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        program_data = os.environ.get("ProgramData", "C:\\ProgramData")
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        home = Path.home()

        if local_app_data:
            winget_dir = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
            if winget_dir.is_dir():
                try:
                    for found in winget_dir.glob("**/ffmpeg.exe"):
                        if found.is_file():
                            return str(found)
                except Exception:
                    pass

        for c in [
            home / "scoop" / "shims" / "ffmpeg.exe",
            home / "scoop" / "apps" / "ffmpeg" / "current" / "bin" / "ffmpeg.exe",
            Path(program_data) / "chocolatey" / "bin" / "ffmpeg.exe",
            Path(program_files) / "ffmpeg" / "bin" / "ffmpeg.exe",
            Path("C:/ffmpeg/bin/ffmpeg.exe"),
        ]:
            if c.is_file():
                return str(c)

    # 4. Typische macOS Homebrew-Pfade
    if sys.platform == "darwin":
        for cand_str in ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
            if os.path.isfile(cand_str) and os.access(cand_str, os.X_OK):
                return cand_str

    # 5. Linux-Pfade
    for cand_str in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
        if os.path.isfile(cand_str) and os.access(cand_str, os.X_OK):
            return cand_str

    return None


FFMPEG_PATH = find_ffmpeg()
DEFAULT_OUTPUT_DIR = str(Path.home() / "Downloads" / "ViDow")


def get_missing_volume_name(path: Path) -> str | None:
    """
    Prüft plattformübergreifend, ob ein Pfad auf ein externes Laufwerk verweist,
    das aktuell nicht angeschlossen/gemountet ist:
    - macOS: /Volumes/<Name> (verhindert PermissionError & Geister-Ordner in /Volumes)
    - Windows: Laufwerksbuchstabe wie D:\\ (wenn das USB-Laufwerk abgesteckt ist)
    """
    parts = path.parts
    if sys.platform == "darwin" and len(parts) >= 3 and parts[0] == "/" and parts[1] == "Volumes":
        volume_name = parts[2]
        volume_root = Path("/Volumes") / volume_name
        try:
            if not volume_root.exists():
                return volume_name
        except OSError:
            return volume_name
    elif sys.platform == "win32" and path.drive:
        drive_root = Path(f"{path.drive}\\")
        try:
            if not drive_root.exists():
                return path.drive
        except OSError:
            return path.drive
    return None


def resolve_usable_output_dir(
    raw_dir: str | None, *, fallback_on_unavailable: bool = True
) -> tuple[str, str | None]:
    """
    Stellt sicher, dass der Zielordner existiert und beschreibbar ist.
    Falls ein externes Laufwerk (z. B. /Volumes/My Passport oder D:\\) abgesteckt ist:
    - Mit fallback_on_unavailable=True wird sauber auf ~/Downloads/ViDow ausgewichen
      (ohne die gespeicherten Favoriten in settings.json zu überschreiben).
    - Mit fallback_on_unavailable=False wird ein verständlicher ValueError geworfen.
    """
    cleaned = (raw_dir or "").strip()
    target = Path(cleaned).expanduser() if cleaned else Path(DEFAULT_OUTPUT_DIR)

    missing_vol = get_missing_volume_name(target)
    if missing_vol:
        msg = (
            f"Das externe Laufwerk „{missing_vol}“ ({target}) ist aktuell nicht angeschlossen."
        )
        if not fallback_on_unavailable:
            raise ValueError(msg)
        fallback = Path(DEFAULT_OUTPUT_DIR)
        try:
            fallback.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return str(fallback), msg

    try:
        target.mkdir(parents=True, exist_ok=True)
        if not os.access(target, os.W_OK):
            raise PermissionError(f"Keine Schreibrechte für {target}")
        return str(target), None
    except OSError as exc:
        msg = f"Zielordner „{target}“ ist nicht verfügbar ({exc})."
        if not fallback_on_unavailable:
            raise ValueError(msg) from exc
        fallback = Path(DEFAULT_OUTPUT_DIR)
        try:
            fallback.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return str(fallback), msg


def load_settings() -> dict[str, Any]:
    default_dir = DEFAULT_OUTPUT_DIR
    video_dir_name = "Videos" if sys.platform == "win32" else "Movies"
    defaults: dict[str, Any] = {
        "output_dir": default_dir,
        "recent_dirs": [
            default_dir,
            str(Path.home() / "Downloads"),
            str(Path.home() / video_dir_name),
        ],
        "quality": "best",
        "codec": "auto",
        "container": "mp4",
        "audio_format": "mp3",
        "skip_preroll_ads": True,
        "min_duration": 45,
        "sponsorblock": False,
        "sponsorblock_cats": ["sponsor", "selfpromo", "intro", "outro"],
        "cookies_browser": "none",
    }
    if SETTINGS_FILE.exists():
        try:
            saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            defaults.update(saved)
        except Exception:
            pass
    return defaults


def save_settings(new_data: dict[str, Any]) -> dict[str, Any]:
    current = load_settings()
    current.update(new_data)
    out_dir = current.get("output_dir", "").strip()
    if out_dir:
        expanded = str(Path(out_dir).expanduser())
        current["output_dir"] = expanded
        recent = [expanded] + [
            d for d in current.get("recent_dirs", []) if d != expanded
        ]
        current["recent_dirs"] = recent[:6]
    try:
        SETTINGS_FILE.write_text(
            json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass
    return current


def format_bytes(num_bytes: float | int | None) -> str:
    if not num_bytes or num_bytes <= 0:
        return "—"
    unit_val = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if unit_val < 1024.0:
            return f"{unit_val:.1f} {unit}"
        unit_val /= 1024.0
    return f"{unit_val:.1f} PB"


def format_seconds(seconds: float | int | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    sec = int(seconds)
    hours, rem = divmod(sec, 3600)
    mins, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours:d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def is_suspected_ad_entry(entry: dict[str, Any], min_duration: int, total_entries: int) -> tuple[bool, str]:
    """Prüft, ob ein gefundener Stream/Playlist-Eintrag sehr wahrscheinlich ein Werbe-Clip ist."""
    url = str(entry.get("url") or entry.get("webpage_url") or "")
    title = str(entry.get("title") or "").lower()
    duration = entry.get("duration")

    if AD_PATTERNS.search(url):
        return True, "Werbe-Server-URL erkannt"

    ad_title_words = ("werbung", "anzeige", "sponsored", "pre-roll", "preroll", "ad break", "commercial")
    if any(w in title for w in ad_title_words):
        return True, "Werbe-Titel erkannt"

    if total_entries > 1 and duration is not None and min_duration > 0 and duration < min_duration:
        return True, f"Clip kürzer als {min_duration}s ({int(duration)}s)"

    return False, ""


class CancelledDownload(Exception):
    pass


JOBS_LOCK = threading.Lock()
JOBS: dict[str, dict[str, Any]] = {}


def get_format_short_edge_and_dims(fmt: dict[str, Any]) -> tuple[int, str, bool]:
    """
    Ermittelt die orientierungsunabhängige Qualitätsstufe (kurze Kante, z. B. 1080 bei
    1920x1080 UND bei 1080x1920 Hochformat), den Anzeige-String und ob Hochformat vorliegt.
    """
    vc = str(fmt.get("vcodec") or "").lower()
    ext = str(fmt.get("ext") or "").lower()
    proto = str(fmt.get("protocol") or "").lower()
    if vc == "none" or ext == "mhtml" or proto == "mhtml":
        return 0, "", False

    w = fmt.get("width")
    h = fmt.get("height")
    if not (isinstance(w, int) and w > 0 and isinstance(h, int) and h > 0):
        res_str = str(fmt.get("resolution") or "")
        m = re.match(r"^(\d+)\s*[x×]\s*(\d+)$", res_str)
        if m:
            w, h = int(m.group(1)), int(m.group(2))

    if isinstance(w, int) and w > 0 and isinstance(h, int) and h > 0:
        return min(w, h), f"{w}×{h}", h > w
    if isinstance(h, int) and h > 0:
        return h, f"{h}p", False
    if isinstance(w, int) and w > 0:
        return w, f"{w}p", False
    return 0, "", False


def build_format_selector(quality: str, codec: str, container: str, audio_format: str) -> str:
    """
    Erzeugt den yt-dlp Format-Selector.
    Die eigentliche Auflösungs- und Codec-Priorisierung erfolgt über `build_format_sort`
    (`res:<Stufe>`), damit sowohl Querformat- (1920x1080) als auch Hochkantvideos (1080x1920)
    in allen Qualitätsstufen zuverlässig geladen werden.
    """
    if quality == "audio":
        return "bestaudio/best"
    if FFMPEG_PATH:
        return "bestvideo*+bestaudio/best"
    return "best/bestvideo+bestaudio"


def build_format_sort(quality: str, codec: str, container: str) -> list[str]:
    """
    Erzeugt die yt-dlp `format_sort`-Kriterien (`-S`).
    `res:<N>` nutzt in yt-dlp `min(width, height)` und funktioniert dadurch identisch
    für 16:9-Querformat, 9:16-/4:5-Hochformat, 1:1-Videos und Streams ohne Breitenangabe.
    """
    if quality == "audio":
        return []

    sort_spec: list[str] = []
    q_clean = str(quality or "best").strip().lower().rstrip("p")
    if q_clean.isdigit() and int(q_clean) > 0:
        sort_spec.append(f"res:{int(q_clean)}")
    else:
        sort_spec.append("res")

    if codec in {"h264", "h265", "vp9", "av1"}:
        sort_spec.append(f"vcodec:{codec}")

    if container == "mp4" and codec in {"auto", "h264", "h265"}:
        sort_spec.append("ext:mp4:m4a")
    elif container == "webm" and codec in {"auto", "vp9", "av1"}:
        sort_spec.append("ext:webm:webm")

    return sort_spec


def apply_impersonate_and_cookies(
    ydl_opts: dict[str, Any],
    cookies_browser: str,
    custom_headers: dict[str, str] | None = None,
) -> None:
    """Aktiviert Chrome-TLS-Impersonation (falls curl_cffi installiert ist) und prüft Browser-Cookies."""
    try:
        from yt_dlp.networking.impersonate import ImpersonateTarget

        ydl_opts["impersonate"] = ImpersonateTarget.from_str("chrome")
    except Exception:
        pass

    if custom_headers:
        ydl_opts["http_headers"] = custom_headers

    if cookies_browser and cookies_browser != "none":
        home = Path.home()
        valid_cookie_store = True
        if sys.platform == "darwin":
            if cookies_browser == "firefox":
                ff_dir = home / "Library/Application Support/Firefox/Profiles"
                valid_cookie_store = ff_dir.exists() and any(ff_dir.glob("*/cookies.sqlite"))
            elif cookies_browser == "chrome":
                ch_dir = home / "Library/Application Support/Google/Chrome"
                valid_cookie_store = ch_dir.exists() and any(ch_dir.glob("*/Cookies"))
            elif cookies_browser == "brave":
                br_dir = home / "Library/Application Support/BraveSoftware/Brave-Browser"
                valid_cookie_store = br_dir.exists() and any(br_dir.glob("*/Cookies"))
            elif cookies_browser == "edge":
                ed_dir = home / "Library/Application Support/Microsoft Edge"
                valid_cookie_store = ed_dir.exists() and any(ed_dir.glob("*/Cookies"))
        elif sys.platform == "win32":
            local_app_data = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData/Local")))
            app_data = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming")))
            if cookies_browser == "firefox":
                ff_dir = app_data / "Mozilla/Firefox/Profiles"
                valid_cookie_store = ff_dir.exists() and any(ff_dir.glob("*/cookies.sqlite"))
            elif cookies_browser == "chrome":
                ch_dir = local_app_data / "Google/Chrome/User Data"
                valid_cookie_store = ch_dir.exists()
            elif cookies_browser == "brave":
                br_dir = local_app_data / "BraveSoftware/Brave-Browser/User Data"
                valid_cookie_store = br_dir.exists()
            elif cookies_browser == "edge":
                ed_dir = local_app_data / "Microsoft/Edge/User Data"
                valid_cookie_store = ed_dir.exists()

        if valid_cookie_store:
            ydl_opts["cookiesfrombrowser"] = (cookies_browser,)


def _decode_kvs_url(video_url: str, license_code: str) -> str:
    """Entschlüsselt verschleierte KVS-URLs ('function/0/https://...') anhand des license_code."""
    if not video_url.startswith("function/0/"):
        return video_url
    if not license_code:
        return video_url[len("function/0/") :]
    try:
        from yt_dlp.extractor.generic import GenericIE

        return GenericIE._kvs_get_real_url(video_url, license_code)
    except Exception:
        return video_url[len("function/0/") :]


def _parse_height_hint(text: str) -> int | None:
    """Extrahiert eine Auflösungs-Höhe (z. B. 1080, 720, 480) aus einem Label oder einer URL."""
    if not text:
        return None
    if re.fullmatch(r"\d{3,4}", text.strip()):
        val = int(text.strip())
        if val in {144, 240, 360, 480, 540, 720, 1080, 1440, 2160, 4320}:
            return val
    if re.search(r"\b(?:4k|2160p?)\b", text, re.IGNORECASE):
        return 2160
    if re.search(r"\b(?:2k|1440p?)\b", text, re.IGNORECASE):
        return 1440
    m = re.search(r"(?:^|[^\d])(2160|1440|1080|720|540|480|360|240|144)[pP]?(?:$|[^\d])", text)
    if m:
        return int(m.group(1))
    return None


def extract_direct_stream_from_html(
    html: str, page_url: str, video_id: str = "direct-stream"
) -> dict[str, Any] | None:
    """
    Sucht direkt im HTML-Code einer Seite (oder einer /embed/-Seite) nach:
    1. PornHub flashvars / mediaDefinitions (inkl. HLS-Master-Playlists & Einzel-Auflösungen)
    2. KVS (Kernel Video Sharing / kt_player) flashvars & verschleierten 'function/0/'-Streams
    3. JSON-LD VideoObject / OpenGraph / Twitter-Stream-Metadaten
    4. HTML5 <video>/<source>-Tags sowie direkten .m3u8/.mp4-Streams
    Greift als Fallback, wenn yt-dlp z.B. mit '[generic] Unable to extract flashvars' oder HTTP 403/410 abbricht.
    """
    if not html:
        return None

    og_title_m = re.search(
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)

    raw_title = (
        (og_title_m.group(1) if og_title_m else "")
        or (re.sub(r"<[^>]+>", "", h1_m.group(1)) if h1_m else "")
        or (title_match.group(1) if title_match else "")
    )
    clean_title = re.sub(r"\s+", " ", raw_title).strip() or "Video-Stream"

    og_thumb_m = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    default_thumb = urllib.parse.urljoin(page_url, og_thumb_m.group(1).strip()) if og_thumb_m else None

    # 1. Prüfe auf PornHub-artige flashvars_<id> / mediaDefinitions
    flashvars_match = re.search(r"(?:var|let|const)?\s*flashvars_\d+\s*=\s*(\{[\s\S]+?\});", html)
    if flashvars_match:
        try:
            fv = json.loads(flashvars_match.group(1))
            clean_title = fv.get("video_title") or clean_title
            thumb = fv.get("image_url") or default_thumb
            duration = fv.get("video_duration")
            media_defs = fv.get("mediaDefinitions") or []
            master_url = ""
            default_url = ""
            quality_urls: dict[int, str] = {}
            heights: set[int] = set()

            for md in media_defs:
                if not isinstance(md, dict):
                    continue
                vurl = md.get("videoUrl")
                q = md.get("quality")
                valid_http = (
                    isinstance(vurl, str)
                    and vurl.startswith("http")
                    and "/video/get_media" not in vurl
                )

                if isinstance(q, list):
                    for item in q:
                        if isinstance(item, (int, str)) and str(item).isdigit():
                            heights.add(int(item))
                    if valid_http and (
                        ".m3u8" in vurl.lower()
                        or ".mpd" in vurl.lower()
                        or str(md.get("format") or "").lower() == "hls"
                    ):
                        master_url = master_url or vurl
                elif isinstance(q, (int, str)) and str(q).isdigit():
                    q_int = int(q)
                    heights.add(q_int)
                    if valid_http:
                        quality_urls[q_int] = vurl

                if valid_http and (md.get("defaultQuality") or not default_url):
                    default_url = vurl

            best_url = master_url or (
                quality_urls[max(quality_urls)] if quality_urls else default_url
            )
            if best_url:
                sorted_heights = sorted(heights, reverse=True)
                formats_list = [
                    {
                        "url": quality_urls.get(h, best_url),
                        "height": h,
                        "format_id": f"{h}p",
                        "http_headers": {"Referer": page_url},
                    }
                    for h in sorted_heights
                ] or [{"url": best_url, "http_headers": {"Referer": page_url}}]
                return {
                    "id": str(fv.get("video_id") or video_id or "direct-stream"),
                    "title": clean_title,
                    "url": best_url,
                    "master_url": master_url,
                    "quality_urls": quality_urls,
                    "webpage_url": page_url,
                    "thumbnail": thumb,
                    "duration": int(duration) if str(duration).isdigit() else None,
                    "extractor_key": "DirectStreamFallback",
                    "http_headers": {"Referer": page_url},
                    "formats": formats_list,
                }
        except Exception:
            pass

    # 2. Prüfe auf KVS (Kernel Video Sharing / kt_player) flashvars (inkl. 'function/0/' Lizenz-Entschlüsselung)
    kvs_url_matches = re.findall(
        r"""['"]?(video_(?:url|alt_url\d*))['"]?\s*:\s*['"]((?:function/0/)?(?:https?:)?//[^'"]+|(?:function/0/)?/[^'"]*get_file/[^'"]+)['"]""",
        html,
    )
    if kvs_url_matches:
        lic_m = re.search(r"""['"]?license_code['"]?\s*:\s*['"]([^'"]+)['"]""", html)
        license_code = lic_m.group(1) if lic_m else ""
        text_labels = dict(
            re.findall(
                r"""['"]?(video_(?:url|alt_url\d*)_text)['"]?\s*:\s*['"]([^'"]+)['"]""",
                html,
            )
        )
        vid_id_m = re.search(r"""['"]?video_id['"]?\s*:\s*['"]?(\d+)['"]?""", html)
        vid_title_m = re.search(r"""['"]?video_title['"]?\s*:\s*['"]([^'"]+)['"]""", html)
        preview_m = re.search(r"""['"]?preview_url['"]?\s*:\s*['"]([^'"]+)['"]""", html)

        if vid_title_m and vid_title_m.group(1).strip():
            clean_title = vid_title_m.group(1).strip()
        thumb = urllib.parse.urljoin(page_url, preview_m.group(1)) if preview_m else default_thumb

        kvs_formats: list[dict[str, Any]] = []
        kvs_quality_urls: dict[int, str] = {}
        seen_urls: set[str] = set()
        for key, raw_val in kvs_url_matches:
            raw_val = raw_val.replace("\\/", "/").strip()
            decoded = _decode_kvs_url(raw_val, license_code)
            full_url = urllib.parse.urljoin(page_url, decoded)
            if not full_url.startswith("http") or full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            label = text_labels.get(f"{key}_text", "")
            height = _parse_height_hint(label) or _parse_height_hint(full_url)
            if height:
                kvs_quality_urls[height] = full_url
            fmt_ext = "m3u8" if ".m3u8" in full_url.lower() else "mp4"
            kvs_formats.append(
                {
                    "format_id": re.sub(r"[^\w-]", "_", label or key),
                    "url": full_url,
                    "ext": fmt_ext,
                    "height": height,
                    "http_headers": {"Referer": page_url},
                }
            )

        if kvs_formats:
            kvs_formats.sort(key=lambda f: f.get("height") or 0)
            best_fmt = kvs_formats[-1]
            return {
                "id": vid_id_m.group(1) if vid_id_m else (video_id or "kvs-stream"),
                "title": clean_title,
                "url": best_fmt["url"],
                "master_url": best_fmt["url"] if best_fmt.get("ext") == "m3u8" else "",
                "quality_urls": kvs_quality_urls,
                "webpage_url": page_url,
                "thumbnail": thumb,
                "extractor_key": "KVSFallback",
                "http_headers": {"Referer": page_url},
                "direct_formats": best_fmt.get("ext") == "mp4",
                "formats": kvs_formats,
            }

    # 3. Prüfe auf JSON-LD (VideoObject contentUrl) und OpenGraph / Twitter-Stream-Tags
    meta_stream_matches = re.findall(
        r"""(?:["']contentUrl["']\s*:\s*["']|<meta[^>]+(?:property|name)=["'](?:og:video(?::(?:url|secure_url))?|twitter:player:stream)["'][^>]+content=["'])(https?://[^"'<>\\\s]+)["']""",
        html,
        re.IGNORECASE,
    )
    for m_url in meta_stream_matches:
        m_url = m_url.replace("\\/", "/")
        if re.search(r"\.(?:mp4|m3u8|webm|mov)(?:\?|$)", m_url, re.IGNORECASE) or "/get_file/" in m_url:
            if not AD_PATTERNS.search(m_url):
                fmt_ext = "m3u8" if ".m3u8" in m_url.lower() else "mp4"
                h = _parse_height_hint(m_url)
                return {
                    "id": video_id or "meta-stream",
                    "title": clean_title,
                    "url": m_url,
                    "master_url": m_url if fmt_ext == "m3u8" else "",
                    "quality_urls": {h: m_url} if h else {},
                    "webpage_url": page_url,
                    "thumbnail": default_thumb,
                    "extractor_key": "MetaStreamFallback",
                    "http_headers": {"Referer": page_url},
                    "direct_formats": fmt_ext == "mp4",
                    "formats": [{"url": m_url, "ext": fmt_ext, "height": h, "http_headers": {"Referer": page_url}}],
                }

    # 4. Prüfe auf HTML5 <video>/<source>-Tags und direkte .m3u8/.mp4/get_file Quellen im HTML/JS
    tag_sources = re.findall(
        r"<(?:video|source)\b[^>]*?\bsrc\s*=\s*[\"']([^\"'<>+\s]+)[\"']([^>]*)",
        html,
        re.IGNORECASE,
    )
    html5_formats: list[dict[str, Any]] = []
    html5_quality_urls: dict[int, str] = {}
    seen_html5: set[str] = set()
    for raw_src, rest_attrs in tag_sources:
        full_src = urllib.parse.urljoin(page_url, raw_src.replace("\\/", "/").replace("&amp;", "&"))
        if not full_src.startswith("http") or AD_PATTERNS.search(full_src) or full_src in seen_html5:
            continue
        if any(full_src.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".vtt", ".srt")):
            continue
        seen_html5.add(full_src)
        h = _parse_height_hint(rest_attrs) or _parse_height_hint(full_src)
        if h:
            html5_quality_urls[h] = full_src
        fmt_ext = "m3u8" if ".m3u8" in full_src.lower() else "mp4"
        html5_formats.append(
            {
                "url": full_src,
                "ext": fmt_ext,
                "height": h,
                "http_headers": {"Referer": page_url},
            }
        )

    stream_matches = re.findall(
        r'["\'](https?:?(?:\\/\\/|//)[^"\'\s<>]+?(?:\.(?:m3u8|mp4)|/get_file/[^"\'\s<>]+)(?:\?[^"\'\s<>]*)?)["\']',
        html,
        re.IGNORECASE,
    )
    for raw_u in stream_matches:
        clean_u = raw_u.replace("\\/", "/").replace("&amp;", "&")
        if clean_u.startswith("//"):
            clean_u = "https:" + clean_u
        if AD_PATTERNS.search(clean_u) or clean_u in seen_html5:
            continue
        # Überspringe winzige Hover-Vorschauclips, sofern andere Streams existieren
        if re.search(r"(?:_preview|preview_|/trailers?/|/thumbs?/)", clean_u, re.IGNORECASE) and html5_formats:
            continue
        seen_html5.add(clean_u)
        h = _parse_height_hint(clean_u)
        if h:
            html5_quality_urls[h] = clean_u
        fmt_ext = "m3u8" if ".m3u8" in clean_u.lower() else "mp4"
        html5_formats.append(
            {
                "url": clean_u,
                "ext": fmt_ext,
                "height": h,
                "http_headers": {"Referer": page_url},
            }
        )

    if html5_formats:
        # Sortiere echte Streams vor etwaige Preview-Clips, bevorzuge .m3u8 Master-Playlists und hohe Auflösungen
        html5_formats.sort(
            key=lambda f: (
                0 if re.search(r"(?:_preview|preview_|/trailers?/)", f["url"], re.IGNORECASE) else 1,
                1 if f.get("ext") == "m3u8" else 0,
                f.get("height") or 0,
            )
        )
        best_fmt = html5_formats[-1]
        best_url = best_fmt["url"]
        return {
            "id": video_id or "direct-html-stream",
            "title": clean_title,
            "url": best_url,
            "master_url": best_url if ".m3u8" in best_url.lower() else "",
            "quality_urls": html5_quality_urls,
            "webpage_url": page_url,
            "thumbnail": default_thumb,
            "extractor_key": "HTML5StreamFallback",
            "http_headers": {"Referer": page_url},
            "direct_formats": best_fmt.get("ext") == "mp4",
            "formats": html5_formats,
        }
    return None


def _extract_embed_candidates(html: str, page_url: str) -> list[str]:
    """Sucht nach eingebetteten Player-Iframes (/embed/...) oder alternativen Embed-URLs einer Videoseite."""
    candidates: list[str] = []
    parsed_page = urllib.parse.urlparse(page_url)
    base_origin = f"{parsed_page.scheme}://{parsed_page.netloc}" if parsed_page.netloc else ""

    # 1. Wenn die URL dem typischen KVS-/Tube-Schema /videos/<id>/ oder /video/<id>/ entspricht -> /embed/<id>
    kvs_path_m = re.search(r"/(?:videos?|v|watch)/(\d+)(?:/|$)", parsed_page.path, re.IGNORECASE)
    if kvs_path_m and base_origin:
        vid_id = kvs_path_m.group(1)
        candidates.append(f"{base_origin}/embed/{vid_id}/")
        candidates.append(f"{base_origin}/embed/{vid_id}")

    if html:
        # 2. <iframe src="..."> im HTML suchen
        for iframe_src in re.findall(r'<iframe\b[^>]+?\bsrc\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE):
            iframe_url = urllib.parse.urljoin(page_url, iframe_src.replace("&amp;", "&").strip())
            if not iframe_url.startswith("http") or AD_PATTERNS.search(iframe_url):
                continue
            if any(
                skip in iframe_url.lower()
                for skip in ("googletagmanager", "google.com/recaptcha", "facebook.com", "twitter.com", "exoclick", "juicyads", "trafficjunky")
            ):
                continue
            candidates.append(iframe_url)

        # 3. video_id aus dem HTML lesen, falls die URL keinen numerischen Pfad hatte
        if not kvs_path_m and base_origin:
            vid_id_m = re.search(r"""['"]?video_id['"]?\s*:\s*['"]?(\d+)['"]?""", html)
            if vid_id_m:
                vid_id = vid_id_m.group(1)
                candidates.append(f"{base_origin}/embed/{vid_id}/")

    return list(dict.fromkeys(c for c in candidates if c != page_url))


def select_fallback_stream_url(fallback_info: dict[str, Any], ydl_opts: dict[str, Any]) -> str:
    """
    Wählt beim Direkt-Stream-Fallback die passende Stream-URL anhand der gewünschten Auflösung:
    1. Falls eine Multi-Qualitäts-Master-Playlist (.m3u8/.mpd) vorliegt, wird diese bevorzugt,
       damit yt-dlp über `format_sort` (`res:<Stufe>`) exakt die gewünschte Hoch-/Querformat-Stufe lädt.
    2. Falls nur einzelne Qualitäts-URLs vorliegen, wird die beste Stufe <= Zielauflösung gewählt.
    """
    master_url = str(fallback_info.get("master_url") or "")
    if master_url:
        return master_url

    quality_urls: dict[int, str] = fallback_info.get("quality_urls") or {}
    if quality_urls:
        target_res: int | None = None
        for item in ydl_opts.get("format_sort") or []:
            if isinstance(item, str) and item.startswith("res:"):
                val = item.split(":", 1)[1].strip()
                if val.isdigit():
                    target_res = int(val)
                    break
        if target_res is not None:
            le_candidates = [q for q in quality_urls if q <= target_res]
            chosen_q = max(le_candidates) if le_candidates else min(quality_urls)
            return quality_urls[chosen_q]
        return quality_urls[max(quality_urls)]

    return str(fallback_info.get("url") or "")


def download_fallback_stream(
    fallback_info: dict[str, Any], clean_opts: dict[str, Any], referer_url: str = ""
) -> dict[str, Any]:
    """Lädt einen per HTML-Fallback gefundenen Stream unter Beibehaltung des echten Titels/ID."""
    fb_opts = dict(clean_opts)
    merged_headers = dict(fb_opts.get("http_headers") or {})
    if referer_url or fallback_info.get("webpage_url"):
        merged_headers.setdefault("Referer", referer_url or str(fallback_info.get("webpage_url")))
    if merged_headers:
        fb_opts["http_headers"] = merged_headers

    stream_url = select_fallback_stream_url(fallback_info, fb_opts)
    raw_outtmpl = fb_opts.get("outtmpl")
    if isinstance(raw_outtmpl, str) and "%(title)" in raw_outtmpl:
        safe_title = yt_dlp.utils.sanitize_filename(
            str(fallback_info.get("title") or "Video"), restricted=False
        )[:150].strip() or "Video"
        safe_id = yt_dlp.utils.sanitize_filename(
            str(fallback_info.get("id") or "stream"), restricted=True
        )[:40] or "stream"
        out_dir = os.path.dirname(raw_outtmpl)
        has_res_token = "%(resolution" in raw_outtmpl
        suffix = "%(resolution& [{}]|)s.%(ext)s" if has_res_token else ".%(ext)s"
        fb_opts["outtmpl"] = os.path.join(out_dir, f"{safe_title} [{safe_id}]{suffix}")

    if fallback_info.get("direct_formats") and fallback_info.get("formats") and not fallback_info.get("master_url"):
        try:
            with yt_dlp.YoutubeDL(fb_opts) as ydl_fb:
                res = ydl_fb.process_ie_result(dict(fallback_info), download=True)
                if isinstance(res, dict):
                    return res
        except Exception:
            pass

    with yt_dlp.YoutubeDL(fb_opts) as ydl_fb:
        res = ydl_fb.extract_info(stream_url, download=True)
        if isinstance(res, dict):
            if fallback_info.get("title"):
                res["title"] = fallback_info["title"]
            if fallback_info.get("thumbnail") and not res.get("thumbnail"):
                res["thumbnail"] = fallback_info["thumbnail"]
        return res


def fetch_url_even_on_error(target_url: str, headers: dict[str, str] | None = None) -> tuple[int, str]:
    import urllib.error
    import urllib.request

    req_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cookie": "age_verified=1; accessAgeDisclaimerPH=1; accessPH=1; platform=pc; kt_rt_popAccess=1; kt_tcookie=1; splash=1",
        "Referer": target_url,
    }
    if headers:
        req_headers.update(headers)

    # 1. Versuche über curl_cffi (Chrome TLS-Impersonation gegen Cloudflare/Bot-Schutz)
    try:
        from curl_cffi import requests as cffi_requests

        resp = cffi_requests.get(
            target_url,
            headers=req_headers,
            impersonate="chrome",
            timeout=12,
            allow_redirects=True,
        )
        if resp.text:
            return resp.status_code, resp.text
    except Exception:
        pass

    # 2. Fallback auf urllib
    req = urllib.request.Request(target_url, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return e.code, body
    except Exception:
        return 0, ""


def extract_info_with_fallback(
    ydl_opts: dict[str, Any],
    url: str,
    download: bool,
    custom_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Versucht regulär über yt-dlp zu extrahieren.
    1. Falls ein ausgewählter Browser keine Cookie-Datenbank hat (z.B. Firefox nicht installiert oder DB gesperrt),
       wird automatisch ohne Browser-Cookies wiederholt.
    2. Falls yt-dlp mit '[generic] Unable to extract flashvars', HTTP 403/410 oder einem anderen Extractor-Fehler
       abbricht, analysiert ViDow den HTML-Code der Seite (sowie etwaige /embed/-Iframes) direkt nach
       KVS-flashvars ('function/0/'), mediaDefinitions, JSON-LD und direkten .m3u8/.mp4-Streams.
    """
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=download)
            if info:
                return info
    except Exception as first_exc:
        first_err = re.sub(r"\x1b\[[0-9;]*m", "", str(first_exc))

        # Automatischer Fallback, falls Browser-Cookies (z.B. Firefox/Chrome) nicht gefunden oder unter Windows gesperrt sind
        if any(
            kw in first_err.lower()
            for kw in ("cookies", "operation not permitted", "permission denied", "could not copy", "dpapi")
        ):
            clean_opts = dict(ydl_opts)
            clean_opts.pop("cookiesfrombrowser", None)
            save_settings({"cookies_browser": "none"})
            try:
                with yt_dlp.YoutubeDL(clean_opts) as ydl_no_cookies:
                    info = ydl_no_cookies.extract_info(url, download=download)
                    if info:
                        return info
            except Exception as second_exc:
                first_exc = second_exc
                first_err = re.sub(r"\x1b\[[0-9;]*m", "", str(second_exc))

        clean_opts = dict(ydl_opts)
        clean_opts.pop("cookiesfrombrowser", None)

        candidates: list[str] = [url]
        ph_match = re.search(
            r"(?:viewkey=|pornhub\.[a-z]+/embed/|\[PornHub\]\s+)(ph[0-9a-f]+|\d+)",
            f"{url} {first_err}",
            re.IGNORECASE,
        )
        ph_video_id = ph_match.group(1) if ph_match else "direct-stream"
        if ph_match:
            candidates.extend(
                [
                    f"https://de.pornhub.org/view_video.php?viewkey={ph_video_id}",
                    f"https://www.pornhub.com/embed/{ph_video_id}",
                ]
            )

        checked_urls: set[str] = set()
        last_html = ""
        last_status = 0

        while candidates:
            candidate_url = candidates.pop(0)
            if candidate_url in checked_urls:
                continue
            checked_urls.add(candidate_url)

            status_code, html = fetch_url_even_on_error(candidate_url, custom_headers)
            if html:
                last_html = html
                last_status = status_code

                fallback_info = extract_direct_stream_from_html(
                    html, candidate_url, video_id=ph_video_id
                )
                if fallback_info:
                    if download:
                        return download_fallback_stream(
                            fallback_info, clean_opts, referer_url=candidate_url
                        )
                    return fallback_info

                # Suche nach eingebetteten /embed/-Playern oder Iframes auf der Seite
                for embed_url in _extract_embed_candidates(html, candidate_url):
                    if embed_url not in checked_urls and embed_url not in candidates:
                        candidates.append(embed_url)

            # Falls es sich um eine entdeckte /embed/-Alternativ-URL handelt, auch regulär über yt-dlp testen
            if candidate_url != url and "/embed/" in candidate_url:
                try:
                    embed_opts = dict(clean_opts)
                    embed_headers = dict(embed_opts.get("http_headers") or {})
                    embed_headers.setdefault("Referer", url)
                    embed_opts["http_headers"] = embed_headers
                    with yt_dlp.YoutubeDL(embed_opts) as ydl_emb:
                        emb_info = ydl_emb.extract_info(candidate_url, download=download)
                        if emb_info:
                            return emb_info
                except Exception:
                    pass

        if last_html:
            if re.search(
                r"(This video is a private video|private video\.\s*You must be friends|requires a password|Bitte einloggen|Login required)",
                last_html,
                re.IGNORECASE,
            ):
                raise ValueError(
                    "Dieses Video ist auf der Webseite als privat oder passwortgeschützt markiert "
                    "(deshalb enthält die Seite keine öffentlichen Player-Daten/'flashvars'). "
                    "Tipp: Falls du im Browser Zugriff hast, wähle in ViDow unter 'Browser-Cookies' deinen Browser aus."
                ) from first_exc

            if last_status == 410 or re.search(
                r"(This video has been disabled|Video has been removed|This video is no longer available|has been flagged|noVideo)",
                last_html,
                re.IGNORECASE,
            ):
                raise ValueError(
                    "Das Video existiert auf dem Server nicht mehr (vom Anbieter gelöscht oder deaktiviert)."
                ) from first_exc

        raise first_exc


def analyze_url(payload: dict[str, Any]) -> dict[str, Any]:
    url = str(payload.get("url") or "").strip()
    if not url:
        raise ValueError("Bitte gib eine gültige Video- oder Webseiten-URL ein.")

    cookies_browser = str(payload.get("cookies_browser") or "none").strip()
    min_duration = int(payload.get("min_duration") or 0)
    custom_headers = payload.get("headers") or {}

    ydl_opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "extract_flat": False,
    }
    if FFMPEG_PATH:
        ydl_opts["ffmpeg_location"] = FFMPEG_PATH
    apply_impersonate_and_cookies(ydl_opts, cookies_browser, custom_headers)

    info = extract_info_with_fallback(ydl_opts, url, download=False, custom_headers=custom_headers)

    if not info:
        raise ValueError("Keine Video-Informationen unter dieser URL gefunden.")

    # Prüfe, ob es mehrere Einträge gibt (z.B. Webseite mit Pre-Roll + Hauptvideo oder Playlist)
    raw_entries = info.get("entries")
    if raw_entries is not None:
        entries_list = [e for e in raw_entries if e]
    else:
        entries_list = [info]

    analyzed_entries: list[dict[str, Any]] = []
    all_heights: set[int] = set()
    all_tier_dims: dict[int, str] = {}
    all_vcodecs: set[str] = set()

    for idx, entry in enumerate(entries_list):
        formats = entry.get("formats") or []
        heights: set[int] = set()
        tier_dims: dict[int, str] = {}
        vcodecs: set[str] = set()
        portrait_count = 0
        landscape_count = 0
        best_filesize = entry.get("filesize") or entry.get("filesize_approx") or 0

        for fmt in formats:
            tier, dims, is_portrait = get_format_short_edge_and_dims(fmt)
            if tier >= 144:
                heights.add(tier)
                all_heights.add(tier)
                if dims and ("×" in dims or tier not in tier_dims):
                    tier_dims[tier] = dims
                if dims and ("×" in dims or tier not in all_tier_dims):
                    all_tier_dims[tier] = dims
                if "×" in dims:
                    if is_portrait:
                        portrait_count += 1
                    else:
                        landscape_count += 1

            vc = str(fmt.get("vcodec") or "")
            if vc and vc != "none":
                if vc.startswith(("avc1", "h264")):
                    vcodecs.add("h264")
                    all_vcodecs.add("h264")
                elif vc.startswith(("hev1", "hvc1", "hevc", "h265")):
                    vcodecs.add("h265")
                    all_vcodecs.add("h265")
                elif vc.startswith(("vp9", "vp09")):
                    vcodecs.add("vp9")
                    all_vcodecs.add("vp9")
                elif vc.startswith("av01"):
                    vcodecs.add("av1")
                    all_vcodecs.add("av1")
            fsize = fmt.get("filesize") or fmt.get("filesize_approx") or 0
            if fsize and fsize > best_filesize:
                best_filesize = fsize

        # Fallback auf Top-Level width/height, falls einzelne Extractors diese nur am Entry setzen
        top_tier, top_dims, top_portrait = get_format_short_edge_and_dims(entry)
        if top_tier >= 144 and not heights:
            heights.add(top_tier)
            all_heights.add(top_tier)
            if top_dims:
                tier_dims[top_tier] = top_dims
                all_tier_dims.setdefault(top_tier, top_dims)
        if portrait_count == 0 and landscape_count == 0 and "×" in top_dims:
            if top_portrait:
                portrait_count = 1
            else:
                landscape_count = 1

        entry_is_vertical = portrait_count > landscape_count
        sorted_entry_heights = sorted(heights, reverse=True)
        entry_tiers = [
            {"quality": q, "resolution": tier_dims.get(q, f"{q}p")}
            for q in sorted_entry_heights
        ]

        suspected_ad, ad_reason = is_suspected_ad_entry(entry, min_duration, len(entries_list))

        analyzed_entries.append(
            {
                "index": idx + 1,
                "id": entry.get("id") or f"stream-{idx+1}",
                "title": entry.get("title") or f"Video-Stream #{idx+1}",
                "url": entry.get("webpage_url") or entry.get("url") or url,
                "direct_url": entry.get("url") or entry.get("webpage_url") or url,
                "thumbnail": entry.get("thumbnail"),
                "duration": entry.get("duration"),
                "duration_ formatted": format_seconds(entry.get("duration")),
                "duration_formatted": format_seconds(entry.get("duration")),
                "uploader": entry.get("uploader") or entry.get("channel") or info.get("extractor_key") or "",
                "extractor": entry.get("extractor_key") or info.get("extractor_key") or "Generic",
                "is_vertical": entry_is_vertical,
                "available_heights": sorted_entry_heights,
                "available_tiers": entry_tiers,
                "available_codecs": sorted(vcodecs),
                "approx_size": format_bytes(best_filesize),
                "is_suspected_ad": suspected_ad,
                "ad_reason": ad_reason,
            }
        )

    # Sortiere so, dass echte Hauptvideos zuerst stehen, falls ein kurzer Pre-Roll-Clip erkannt wurde
    primary = next((e for e in analyzed_entries if not e["is_suspected_ad"]), analyzed_entries[0])
    sorted_all_heights = sorted(all_heights, reverse=True)
    all_tiers = [
        {"quality": q, "resolution": all_tier_dims.get(q, f"{q}p")}
        for q in sorted_all_heights
    ]

    return {
        "title": info.get("title") or primary["title"],
        "extractor": info.get("extractor_key") or primary["extractor"],
        "webpage_url": info.get("webpage_url") or url,
        "thumbnail": info.get("thumbnail") or primary["thumbnail"],
        "duration": info.get("duration") or primary["duration"],
        "duration_formatted": format_seconds(info.get("duration") or primary["duration"]),
        "uploader": info.get("uploader") or primary["uploader"],
        "is_vertical": bool(primary.get("is_vertical")),
        "available_heights": sorted_all_heights,
        "available_tiers": all_tiers,
        "available_codecs": sorted(all_vcodecs),
        "entries": analyzed_entries,
        "ad_filtered_count": sum(1 for e in analyzed_entries if e["is_suspected_ad"]),
    }


def run_download_job(job_id: str, params: dict[str, Any]) -> None:
    url = str(params.get("url") or "").strip()
    raw_output_dir = str(params.get("output_dir") or DEFAULT_OUTPUT_DIR)
    quality = str(params.get("quality") or "best")
    codec = str(params.get("codec") or "auto")
    container = str(params.get("container") or "mp4")
    audio_format = str(params.get("audio_format") or "mp3")
    skip_preroll_ads = bool(params.get("skip_preroll_ads", True))
    min_duration = int(params.get("min_duration") or 0)
    sponsorblock = bool(params.get("sponsorblock", False))
    sponsorblock_cats = params.get("sponsorblock_cats") or ["sponsor", "selfpromo", "intro", "outro"]
    cookies_browser = str(params.get("cookies_browser") or "none")
    custom_headers = params.get("headers") or {}
    custom_title = str(params.get("custom_title") or "").strip()
    recode_if_needed = bool(params.get("recode_if_needed", False))

    def update_job(**kwargs: Any) -> None:
        with JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id].update(kwargs)
                JOBS[job_id]["updated_at"] = time.time()

    try:
        output_dir, _ = resolve_usable_output_dir(
            raw_output_dir, fallback_on_unavailable=False
        )
    except Exception as exc:
        err_msg = str(exc)
        update_job(
            status="error",
            status_text=f"Fehler: {err_msg}",
            error=err_msg,
            speed_formatted="—",
            eta_formatted="—",
        )
        return

    def progress_hook(d: dict[str, Any]) -> None:
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if job and job.get("cancel_requested"):
                raise CancelledDownload("Download vom Nutzer abgebrochen.")

        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            pct = (downloaded / total * 100.0) if total > 0 else 0.0
            # Bei HLS/DASH-Segmenten liefert yt-dlp oft fragment_index / fragment_count
            if total == 0 and d.get("fragment_count"):
                frag_idx = d.get("fragment_index") or 0
                frag_cnt = d.get("fragment_count") or 1
                pct = min(99.0, (frag_idx / frag_cnt) * 100.0)

            speed = d.get("speed")
            eta = d.get("eta")
            filename = d.get("filename") or ""
            info_dict = d.get("info_dict") or {}
            title = info_dict.get("title") or custom_title or JOBS.get(job_id, {}).get("title") or "Video"

            update_job(
                status="downloading",
                status_text="Lädt herunter…",
                title=title,
                progress=round(pct, 1),
                downloaded_formatted=format_bytes(downloaded),
                total_formatted=format_bytes(total) if total else "Stream",
                speed_formatted=f"{format_bytes(speed)}/s" if speed else "—",
                eta_formatted=format_seconds(eta),
                filepath=filename,
            )
        elif status == "finished":
            filename = d.get("filename") or ""
            update_job(
                status="processing",
                status_text="Verarbeite Audio/Video & Container (ffmpeg)…",
                progress=100.0,
                eta_formatted="00:00",
                filepath=filename,
            )

    def postprocessor_hook(d: dict[str, Any]) -> None:
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if job and job.get("cancel_requested"):
                raise CancelledDownload("Download vom Nutzer abgebrochen.")

        pp_status = d.get("status")
        pp_name = d.get("postprocessor") or ""
        info_dict = d.get("info_dict") or {}
        filepath = info_dict.get("filepath") or info_dict.get("_filename")
        if pp_status == "started":
            label = "Finalisiere Video…"
            if "SponsorBlock" in pp_name or "ModifyChapters" in pp_name:
                label = "Schneide Werbe-/Sponsor-Segmente heraus (SponsorBlock)…"
            elif "Merger" in pp_name:
                label = "Füge Video- & Audiospur zusammen (ffmpeg)…"
            elif "ExtractAudio" in pp_name:
                label = f"Konvertiere Audio nach {audio_format.upper()}…"
            elif "VideoConvertor" in pp_name:
                label = f"Konvertiere Codec/Container ({container.upper()})…"
            update_job(status="processing", status_text=label)
        elif pp_status == "finished" and filepath:
            update_job(filepath=filepath)

    format_selector = build_format_selector(quality, codec, container, audio_format)
    format_sort = build_format_sort(quality, codec, container)

    if custom_title:
        safe_custom = yt_dlp.utils.sanitize_filename(custom_title, restricted=False).strip() or "Video"
        target_ext = audio_format if quality == "audio" else container
        existing_same_name = os.path.exists(os.path.join(output_dir, f"{safe_custom}.{target_ext}"))
        if quality != "audio" and existing_same_name:
            out_name = f"{safe_custom}%(resolution& [{{}}]|)s.%(ext)s"
        else:
            out_name = f"{safe_custom}.%(ext)s"
    elif quality == "audio":
        out_name = "%(title).180B [%(id)s].%(ext)s"
    else:
        out_name = "%(title).170B [%(id)s]%(resolution& [{}]|)s.%(ext)s"

    outtmpl = os.path.join(output_dir, out_name)

    postprocessors: list[dict[str, Any]] = []
    postprocessor_args: dict[str, list[str]] = {}

    if quality == "audio":
        postprocessors.append(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_format,
                "preferredquality": "320" if audio_format == "mp3" else "0",
            }
        )
    else:
        # Wenn ein spezifischer Codec erzwungen werden soll (z. B. H.264 für QuickTime)
        if recode_if_needed and codec in {"h264", "h265"}:
            postprocessors.append(
                {
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": container,
                }
            )
            vcodec_ff = "libx264" if codec == "h264" else "libx265"
            postprocessor_args["videoconvertor"] = [
                "-c:v",
                vcodec_ff,
                "-preset",
                "fast",
                "-crf",
                "20",
                "-c:a",
                "aac",
            ]

    if sponsorblock and sponsorblock_cats:
        postprocessors.append(
            {
                "key": "SponsorBlock",
                "categories": sponsorblock_cats,
                "when": "after_filter",
            }
        )
        postprocessors.append(
            {
                "key": "ModifyChapters",
                "remove_sponsor_segments": sponsorblock_cats,
                "force_keyframes": False,
            }
        )

    ydl_opts: dict[str, Any] = {
        "format": format_selector,
        "outtmpl": outtmpl,
        "overwrites": True,
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
        "postprocessors": postprocessors,
        "concurrent_fragment_downloads": 4,
        "quiet": True,
        "no_warnings": True,
    }

    if format_sort:
        ydl_opts["format_sort"] = format_sort

    if quality != "audio":
        ydl_opts["merge_output_format"] = container

    if postprocessor_args:
        ydl_opts["postprocessor_args"] = postprocessor_args

    if FFMPEG_PATH:
        ydl_opts["ffmpeg_location"] = FFMPEG_PATH

    apply_impersonate_and_cookies(ydl_opts, cookies_browser, custom_headers)

    skipped_reasons: list[str] = []

    # Schutz gegen vorgeschaltete Werbe-Clips bei Multi-Stream-Webseiten
    if skip_preroll_ads:
        def ad_match_filter(info_dict: dict[str, Any], *, incomplete: bool = False) -> str | None:
            if incomplete:
                return None
            entry_url = str(info_dict.get("url") or info_dict.get("webpage_url") or "")
            if AD_PATTERNS.search(entry_url):
                reason = "Übersprungen: Werbe-Stream erkannt"
                skipped_reasons.append(reason)
                return reason
            dur = info_dict.get("duration")
            total_entries = int(
                info_dict.get("n_entries") or info_dict.get("playlist_count") or 1
            )
            # Mindestdauer nur bei Multi-Stream-/Playlist-Seiten anwenden, damit kurze
            # Einzelvideos (YouTube Shorts, Reels, TikToks < 45s) nicht übersprungen werden!
            if total_entries > 1 and min_duration > 0 and dur is not None and dur < min_duration:
                reason = (
                    f"Übersprungen: Clip ist kürzer als {min_duration}s "
                    f"({int(dur)}s – vermutlich Pre-Roll-Werbung)"
                )
                skipped_reasons.append(reason)
                return reason
            return None

        ydl_opts["match_filter"] = ad_match_filter

    try:
        update_job(status="downloading", status_text="Verbinde & analysiere Stream…")
        info = extract_info_with_fallback(
            ydl_opts, url, download=True, custom_headers=custom_headers
        )
        final_path = ""
        actual_res = ""
        if info:
            title = info.get("title") or custom_title or "Video"
            thumb = info.get("thumbnail")
            req_dl = (info.get("requested_downloads") or [None])[0]
            if isinstance(req_dl, dict):
                final_path = req_dl.get("filepath") or ""
                _, actual_res, _ = get_format_short_edge_and_dims(req_dl)
            if not actual_res:
                _, actual_res, _ = get_format_short_edge_and_dims(info)
            if not final_path:
                with JOBS_LOCK:
                    final_path = str(JOBS.get(job_id, {}).get("filepath") or "")
            if not final_path:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl_tmp:
                    final_path = ydl_tmp.prepare_filename(info)
                if quality == "audio":
                    final_path = str(Path(final_path).with_suffix(f".{audio_format}"))
                elif container:
                    cand = str(Path(final_path).with_suffix(f".{container}"))
                    if os.path.exists(cand):
                        final_path = cand
            if (not final_path or not os.path.exists(final_path)) and skipped_reasons:
                raise ValueError(skipped_reasons[0])
            update_job(
                status="completed",
                status_text="Abgeschlossen",
                title=title,
                thumbnail=thumb,
                resolution=actual_res,
                progress=100.0,
                eta_formatted="Fertig",
                filepath=final_path,
                filename=os.path.basename(final_path) if final_path else "",
            )
        else:
            if skipped_reasons:
                raise ValueError(skipped_reasons[0])
            update_job(
                status="completed",
                status_text="Abgeschlossen",
                progress=100.0,
            )
    except CancelledDownload:
        update_job(
            status="cancelled",
            status_text="Abgebrochen",
            speed_formatted="—",
            eta_formatted="—",
        )
    except Exception as exc:
        err_msg = str(exc)
        # ANSI-Farbcodes aus yt-dlp Fehlermeldungen entfernen
        err_msg = re.sub(r"\x1b\[[0-9;]*m", "", err_msg)
        update_job(
            status="error",
            status_text=f"Fehler: {err_msg}",
            error=err_msg,
            speed_formatted="—",
            eta_formatted="—",
        )


ACTIVE_WINDOW: Any = None


def pick_folder_dialog(initial_dir: str = "") -> str | None:
    """Öffnet einen nativen Ordnerauswahl-Dialog (pywebview -> OS-spezifischer Fallback)."""
    # 1. Wenn pywebview-Fenster aktiv ist
    if ACTIVE_WINDOW is not None:
        try:
            import webview

            folder_enum = getattr(webview, "FileDialog", None)
            dialog_type = folder_enum.FOLDER if folder_enum else webview.FOLDER_DIALOG
            res = ACTIVE_WINDOW.create_file_dialog(
                dialog_type,
                directory=initial_dir or str(Path.home() / "Downloads"),
            )
            if res and len(res) > 0:
                return str(res[0]).rstrip("/\\")
            return None
        except Exception:
            pass

    # 2. Windows Fallback (Tkinter oder PowerShell)
    if sys.platform == "win32":
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            chosen = filedialog.askdirectory(
                initialdir=initial_dir or str(Path.home() / "Downloads"),
                title="ViDow: Zielordner für Downloads auswählen",
            )
            root.destroy()
            if chosen:
                return str(chosen).rstrip("/\\")
        except Exception:
            pass

        try:
            ps_script = (
                "[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null; "
                "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
                f"$f.SelectedPath = '{initial_dir}'; "
                "$f.Description = 'ViDow: Zielordner auswählen'; "
                "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $f.SelectedPath }"
            )
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip().splitlines()[-1].strip().rstrip("/\\")
        except Exception:
            pass

    # 3. macOS Fallback (osascript / Finder)
    elif sys.platform == "darwin":
        try:
            script = (
                'POSIX path of (choose folder with prompt '
                '"ViDow: Bitte wähle den Zielordner für deine Videos:")'
            )
            proc = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip().rstrip("/")
        except Exception:
            pass

    # 4. Linux Fallback (zenity / kdialog)
    else:
        for cmd in [
            ["zenity", "--file-selection", "--directory", "--title=ViDow: Zielordner"],
            ["kdialog", "--getexistingdirectory"],
        ]:
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if proc.returncode == 0 and proc.stdout.strip():
                    return proc.stdout.strip().rstrip("/")
            except Exception:
                continue

    return None


def get_system_clipboard() -> str:
    """Liest Text aus der System-Zwischenablage (Windows, macOS, Linux)."""
    if sys.platform == "win32":
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if proc.returncode == 0:
                return proc.stdout.strip()
        except Exception:
            pass

        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            text = root.clipboard_get()
            root.destroy()
            return str(text).strip()
        except Exception:
            pass
        return ""

    if sys.platform == "darwin":
        try:
            proc = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=3)
            if proc.returncode == 0:
                return proc.stdout.strip()
        except Exception:
            pass
        return ""

    for tool in [["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]]:
        try:
            proc = subprocess.run(tool, capture_output=True, text=True, timeout=3)
            if proc.returncode == 0:
                return proc.stdout.strip()
        except Exception:
            continue

    return ""


def reveal_in_file_manager(target_path: Path) -> None:
    """Öffnet den Pfad im nativen Dateimanager (Windows Explorer, macOS Finder, Linux)."""
    expanded = target_path.expanduser()
    if not expanded.is_file():
        resolved_dir, _ = resolve_usable_output_dir(
            str(expanded), fallback_on_unavailable=False
        )
        target_path = Path(resolved_dir).resolve()
    else:
        target_path = expanded.resolve()

    if sys.platform == "win32":
        target_str = os.path.normpath(str(target_path))
        if target_path.is_file():
            # Öffnet Windows Explorer und markiert die Datei
            subprocess.Popen(["explorer.exe", f"/select,{target_str}"])
        else:
            os.startfile(target_str)
    elif sys.platform == "darwin":
        if target_path.is_file():
            subprocess.Popen(["open", "-R", str(target_path)])
        else:
            subprocess.Popen(["open", str(target_path)])
    else:
        # Linux
        if target_path.is_file():
            subprocess.Popen(["xdg-open", str(target_path.parent)])
        else:
            subprocess.Popen(["xdg-open", str(target_path)])


def setup_windows_app_id() -> None:
    """Setzt unter Windows die AppUserModelID für sauberes Taskleisten-Icon & Gruppierung."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "FlatRat.ViDow.VideoDownloader.1.0"
            )
        except Exception:
            pass


class ViDowRequestHandler(BaseHTTPRequestHandler):
    server_version = "ViDow/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Schlankes Logging im Terminal
        if "/api/jobs" not in self.path:
            sys.stderr.write(f"[ViDow] {self.address_string()} - {fmt % args}\n")

    def _send_json(self, data: Any, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path

        if route == "/api/status":
            settings = load_settings()
            effective_dir, dir_warning = resolve_usable_output_dir(
                settings.get("output_dir"), fallback_on_unavailable=True
            )
            effective_settings = {**settings, "output_dir": effective_dir}
            self._send_json(
                {
                    "ok": True,
                    "app": "ViDow",
                    "platform": sys.platform,
                    "os_label": (
                        "Windows"
                        if sys.platform == "win32"
                        else "macOS"
                        if sys.platform == "darwin"
                        else "Linux"
                    ),
                    "file_manager_label": "Explorer" if sys.platform == "win32" else "Finder",
                    "yt_dlp_version": yt_dlp.version.__version__,
                    "ffmpeg_available": bool(FFMPEG_PATH),
                    "ffmpeg_path": FFMPEG_PATH,
                    "settings": effective_settings,
                    "output_dir_warning": dir_warning,
                }
            )
            return

        if route == "/api/jobs":
            with JOBS_LOCK:
                jobs_list = sorted(
                    JOBS.values(),
                    key=lambda j: j.get("created_at", 0),
                    reverse=True,
                )
            self._send_json({"ok": True, "jobs": jobs_list})
            return

        # Statische Dateien aus /static ausliefern
        if route == "/" or route == "/index.html":
            file_path = STATIC_DIR / "index.html"
        else:
            rel = route.lstrip("/")
            file_path = (STATIC_DIR / rel).resolve()
            if not str(file_path).startswith(str(STATIC_DIR.resolve())):
                self._send_json({"ok": False, "error": "Ungültiger Pfad"}, HTTPStatus.FORBIDDEN)
                return

        if not file_path.is_file():
            self._send_json({"ok": False, "error": "Nicht gefunden"}, HTTPStatus.NOT_FOUND)
            return

        mime_map = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".ico": "image/x-icon",
            ".json": "application/json; charset=utf-8",
        }
        content_type = mime_map.get(file_path.suffix.lower(), "application/octet-stream")
        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path

        try:
            payload = self._read_json()
        except Exception as exc:
            self._send_json({"ok": False, "error": f"Ungültiges JSON: {exc}"}, HTTPStatus.BAD_REQUEST)
            return

        if route == "/api/settings":
            updated = save_settings(payload)
            self._send_json({"ok": True, "settings": updated})
            return

        if route == "/api/pick-folder":
            try:
                current_dir, _ = resolve_usable_output_dir(
                    load_settings().get("output_dir"), fallback_on_unavailable=True
                )
                chosen = pick_folder_dialog(current_dir)
                if chosen:
                    settings = save_settings({"output_dir": chosen})
                    self._send_json({"ok": True, "path": chosen, "settings": settings})
                else:
                    self._send_json({"ok": False, "cancelled": True})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        if route == "/api/clipboard":
            try:
                clip_text = get_system_clipboard()
                self._send_json({"ok": True, "text": clip_text})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        if route == "/api/open-folder":
            target = str(payload.get("path") or "").strip()
            if not target:
                target, _ = resolve_usable_output_dir(
                    load_settings().get("output_dir"), fallback_on_unavailable=True
                )
            target_path = Path(target)
            try:
                reveal_in_file_manager(target_path)
                self._send_json({"ok": True})
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        if route == "/api/analyze":
            try:
                result = analyze_url(payload)
                self._send_json({"ok": True, "analysis": result})
            except Exception as exc:
                err_msg = re.sub(r"\x1b\[[0-9;]*m", "", str(exc))
                self._send_json({"ok": False, "error": err_msg}, HTTPStatus.BAD_REQUEST)
            return

        if route == "/api/download":
            url = str(payload.get("url") or "").strip()
            if not url:
                self._send_json({"ok": False, "error": "URL fehlt."}, HTTPStatus.BAD_REQUEST)
                return

            requested_dir = str(payload.get("output_dir") or load_settings()["output_dir"]).strip()
            try:
                resolved_output_dir, _ = resolve_usable_output_dir(
                    requested_dir, fallback_on_unavailable=False
                )
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return

            # Speichere aktuelle Präferenzen als Standard
            save_settings(
                {
                    "output_dir": resolved_output_dir,
                    "quality": payload.get("quality") or "best",
                    "codec": payload.get("codec") or "auto",
                    "container": payload.get("container") or "mp4",
                    "audio_format": payload.get("audio_format") or "mp3",
                    "skip_preroll_ads": payload.get("skip_preroll_ads", True),
                    "min_duration": int(payload.get("min_duration") or 0),
                    "sponsorblock": bool(payload.get("sponsorblock", False)),
                    "cookies_browser": payload.get("cookies_browser") or "none",
                }
            )

            job_id = str(uuid.uuid4())[:8]
            job_info: dict[str, Any] = {
                "id": job_id,
                "url": url,
                "title": payload.get("title") or payload.get("custom_title") or url,
                "thumbnail": payload.get("thumbnail"),
                "quality": payload.get("quality") or "best",
                "codec": payload.get("codec") or "auto",
                "container": (
                    payload.get("audio_format")
                    if payload.get("quality") == "audio"
                    else payload.get("container") or "mp4"
                ),
                "output_dir": resolved_output_dir,
                "status": "queued",
                "status_text": "In Warteschlange…",
                "progress": 0.0,
                "downloaded_formatted": "0 B",
                "total_formatted": "—",
                "speed_formatted": "—",
                "eta_formatted": "—",
                "filepath": "",
                "filename": "",
                "created_at": time.time(),
                "updated_at": time.time(),
                "cancel_requested": False,
            }
            with JOBS_LOCK:
                JOBS[job_id] = job_info

            thread = threading.Thread(
                target=run_download_job, args=(job_id, payload), daemon=True
            )
            thread.start()
            self._send_json({"ok": True, "job": job_info})
            return

        if route == "/api/jobs/cancel":
            job_id = str(payload.get("id") or "")
            with JOBS_LOCK:
                if job_id in JOBS:
                    JOBS[job_id]["cancel_requested"] = True
                    JOBS[job_id]["status_text"] = "Breche ab…"
            self._send_json({"ok": True})
            return

        if route == "/api/jobs/clear":
            with JOBS_LOCK:
                to_keep = {
                    k: v
                    for k, v in JOBS.items()
                    if v.get("status") in {"queued", "downloading", "processing"}
                }
                JOBS.clear()
                JOBS.update(to_keep)
            self._send_json({"ok": True})
            return

        self._send_json({"ok": False, "error": "Unbekannter Endpunkt"}, HTTPStatus.NOT_FOUND)


def start_http_server() -> tuple[ThreadingHTTPServer | None, int]:
    """Startet den lokalen ViDow-HTTP-Server auf Port 8765 (oder einem freien Ausweichport)."""
    for candidate_port in (DEFAULT_PORT, 8766, 8767, 0):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", candidate_port), ViDowRequestHandler)
            actual_port = srv.server_address[1]
            return srv, actual_port
        except OSError:
            continue
    return None, DEFAULT_PORT


def apply_macos_dock_icon() -> None:
    """Setzt das ViDow-Icon zur Laufzeit im macOS-Dock und im Cmd+Tab-Switcher."""
    if sys.platform != "darwin":
        return
    icon_file = STATIC_DIR / "icon.png"
    if not icon_file.is_file():
        return
    try:
        import AppKit

        app = AppKit.NSApplication.sharedApplication()
        img = AppKit.NSImage.alloc().initWithContentsOfFile_(str(icon_file))
        if img:
            app.setApplicationIconImage_(img)
    except Exception:
        pass


def main() -> None:
    global ACTIVE_WINDOW
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    setup_windows_app_id()
    settings = load_settings()
    effective_output_dir, output_dir_warning = resolve_usable_output_dir(
        settings.get("output_dir"), fallback_on_unavailable=True
    )

    server, port = start_http_server()
    url = f"http://127.0.0.1:{port}"

    ffmpeg_status = FFMPEG_PATH
    if not ffmpeg_status:
        if sys.platform == "win32":
            ffmpeg_status = "Nicht gefunden (Tipp: 'winget install Gyan.FFmpeg' im Terminal ausführen)"
        else:
            ffmpeg_status = "Nicht gefunden (bitte 'brew install ffmpeg' ausführen)"

    print("=" * 60)
    print(f"🎬 ViDow läuft auf: {url}")
    print(f"📂 Standard-Speicherort: {effective_output_dir}")
    if output_dir_warning:
        print(f"⚠️  {output_dir_warning}")
    print(f"🔧 yt-dlp Version: {yt_dlp.version.__version__}")
    print(f"🎞️  ffmpeg: {ffmpeg_status}")
    print("=" * 60)

    use_browser_only = "--browser" in sys.argv or os.environ.get("VIDOW_BROWSER_ONLY") == "1"

    if not use_browser_only:
        try:
            import webview

            if server is not None:
                srv_thread = threading.Thread(target=server.serve_forever, daemon=True)
                srv_thread.start()

            if sys.platform == "darwin":
                apply_macos_dock_icon()

            icon_ico = STATIC_DIR / "icon.ico"
            icon_png = STATIC_DIR / "icon.png"
            chosen_icon = str(icon_ico if (sys.platform == "win32" and icon_ico.is_file()) else icon_png)
            if not os.path.isfile(chosen_icon):
                chosen_icon = None

            ACTIVE_WINDOW = webview.create_window(
                "ViDow — Video Downloader",
                url,
                width=1260,
                height=860,
                min_size=(920, 640),
            )

            start_kwargs: dict[str, Any] = {}
            if sys.platform == "darwin":
                start_kwargs["func"] = apply_macos_dock_icon
            if chosen_icon:
                start_kwargs["icon"] = chosen_icon

            webview.start(**start_kwargs)
            if server is not None:
                server.shutdown()
                server.server_close()
            return
        except Exception as exc:
            print(f"[ViDow] Hinweis: Konnte natives Desktop-Fenster nicht starten ({exc}), öffne im Browser…")

    if os.environ.get("VIDOW_NO_BROWSER") != "1":
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    if server is not None:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n[ViDow] Server wird beendet…")
            server.server_close()


if __name__ == "__main__":
    main()
