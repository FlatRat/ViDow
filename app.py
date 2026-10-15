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
    """Sucht ffmpeg auch in typischen macOS Homebrew-Pfaden."""
    for candidate in [
        shutil.which("ffmpeg"),
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ]:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


FFMPEG_PATH = find_ffmpeg()


def load_settings() -> dict[str, Any]:
    default_dir = str(Path.home() / "Downloads" / "ViDow")
    defaults: dict[str, Any] = {
        "output_dir": default_dir,
        "recent_dirs": [
            default_dir,
            str(Path.home() / "Downloads"),
            str(Path.home() / "Movies"),
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


def build_format_selector(quality: str, codec: str, container: str, audio_format: str) -> str:
    """
    Erzeugt den optimalen yt-dlp Format-Selector anhand der gewünschten Auflösung und des Codecs.
    Fällt sauber auf das nächstbeste Format zurück, falls ein exakter Codec auf der Quellseite
    nicht nativ vorliegt (ffmpeg übernimmt dann bei Bedarf das Remuxing/Transcoding).
    """
    if quality == "audio":
        return "bestaudio/best"

    height_filter = ""
    if quality in {"2160", "1440", "1080", "720", "480", "360"}:
        height_filter = f"[height<={quality}]"

    codec_map = {
        "h264": "^(avc1|h264)",
        "h265": "^(hev1|hvc1|hevc|h265)",
        "vp9": "^vp0?9",
        "av1": "^av01",
    }

    if codec in codec_map:
        vc = codec_map[codec]
        # 1. Versuche gewünschten Video-Codec + gewünschte Höhe
        # 2. Fallback auf beliebigen Video-Codec mit gewünschter Höhe (wird ggf. konvertiert)
        return (
            f"bestvideo{height_filter}[vcodec~='{vc}']+bestaudio/"
            f"best{height_filter}[vcodec~='{vc}']/"
            f"bestvideo{height_filter}+bestaudio/"
            f"best{height_filter}/best"
        )

    # Codec == "auto"
    if container == "mp4":
        return (
            f"bestvideo{height_filter}[ext=mp4]+bestaudio[ext=m4a]/"
            f"bestvideo{height_filter}+bestaudio/"
            f"best{height_filter}/best"
        )
    return f"bestvideo{height_filter}+bestaudio/best{height_filter}/best"


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

        if valid_cookie_store:
            ydl_opts["cookiesfrombrowser"] = (cookies_browser,)


def extract_direct_stream_from_html(html: str, page_url: str) -> dict[str, Any] | None:
    """
    Sucht direkt im HTML-Code einer Seite (oder einer /embed/-Seite) nach
    flashvars / mediaDefinitions oder direkten .m3u8/.mp4-Streams, falls der
    reguläre yt-dlp-Extractor mit HTTP 410/403 abbricht.
    """
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    clean_title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else "Video-Stream"

    # 1. Prüfe auf flashvars / mediaDefinitions (einzeiliges JSON-Objekt)
    flashvars_match = re.search(r"var\s+flashvars_\d+\s*=\s*(\{.+?\});\s*\r?\n", html)
    if flashvars_match:
        try:
            fv = json.loads(flashvars_match.group(1))
            clean_title = fv.get("video_title") or clean_title
            thumb = fv.get("image_url")
            duration = fv.get("video_duration")
            media_defs = fv.get("mediaDefinitions") or []
            best_url = ""
            heights: list[int] = []
            for md in media_defs:
                if not isinstance(md, dict):
                    continue
                vurl = md.get("videoUrl")
                q = md.get("quality")
                if isinstance(q, (int, str)) and str(q).isdigit():
                    heights.append(int(q))
                if vurl and isinstance(vurl, str) and vurl.startswith("http"):
                    if md.get("defaultQuality") or not best_url:
                        best_url = vurl
            if best_url:
                return {
                    "id": "direct-stream",
                    "title": clean_title,
                    "url": best_url,
                    "webpage_url": page_url,
                    "thumbnail": thumb,
                    "duration": int(duration) if str(duration).isdigit() else None,
                    "extractor_key": "DirectStreamFallback",
                    "formats": [{"url": best_url, "height": h} for h in heights] or [{"url": best_url}],
                }
        except Exception:
            pass

    # 2. Prüfe auf direkte .m3u8 oder .mp4 Quellen im HTML
    stream_matches = re.findall(
        r'["\'](https?://[^"\'\s<>]+?\.(?:m3u8|mp4)(?:\?[^"\'\s<>]*)?)["\']',
        html,
        re.IGNORECASE,
    )
    filtered = [u.replace("\\/", "/") for u in stream_matches if not AD_PATTERNS.search(u)]
    if filtered:
        best_url = filtered[0]
        return {
            "id": "direct-html-stream",
            "title": clean_title,
            "url": best_url,
            "webpage_url": page_url,
            "extractor_key": "HTML5StreamFallback",
            "formats": [{"url": best_url}],
        }
    return None


def fetch_url_even_on_error(target_url: str, headers: dict[str, str] | None = None) -> tuple[int, str]:
    import urllib.error
    import urllib.request

    req_headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cookie": "age_verified=1; accessAgeDisclaimerPH=1; accessPH=1; platform=pc",
    }
    if headers:
        req_headers.update(headers)

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
    1. Falls ein ausgewählter Browser keine Cookie-Datenbank hat (z.B. Firefox nicht installiert),
       wird automatisch ohne Browser-Cookies wiederholt.
    2. Falls ein HTTP Error 410 (Gone) oder 403 auftritt, wird die Original-Domain (z. B. de.pornhub.org)
       direkt abgefragt und die Stream-URL aus flashvars extrahiert.
    """
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=download)
            if info:
                return info
    except Exception as first_exc:
        first_err = re.sub(r"\x1b\[[0-9;]*m", "", str(first_exc))

        # Automatischer Fallback, falls Browser-Cookies (z.B. Firefox) nicht gefunden oder gesperrt sind
        if "cookies" in first_err.lower() or "operation not permitted" in first_err.lower():
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

        ph_match = re.search(
            r"(?:viewkey=|/embed/|\[PornHub\]\s+)(ph[0-9a-f]+|\d+)",
            f"{url} {first_err}",
            re.IGNORECASE,
        )
        if ph_match:
            video_id = ph_match.group(1)
            candidates = [
                url,
                f"https://de.pornhub.org/view_video.php?viewkey={video_id}",
                f"https://www.pornhub.com/embed/{video_id}",
            ]
            for candidate_url in dict.fromkeys(candidates):
                status_code, html = fetch_url_even_on_error(candidate_url, custom_headers)
                if html:
                    fallback_info = extract_direct_stream_from_html(html, url)
                    if fallback_info:
                        if download:
                            with yt_dlp.YoutubeDL(clean_opts) as ydl_fb:
                                return ydl_fb.extract_info(fallback_info["url"], download=True)
                        return fallback_info

                    if status_code == 410 or re.search(
                        r"(This video has been disabled|Video has been removed|has been flagged|noVideo)",
                        html,
                        re.IGNORECASE,
                    ):
                        if "pornhub." not in url.lower():
                            _, main_html = fetch_url_even_on_error(url, custom_headers)
                            main_fallback = extract_direct_stream_from_html(main_html, url)
                            if main_fallback:
                                if download:
                                    with yt_dlp.YoutubeDL(clean_opts) as ydl_fb:
                                        return ydl_fb.extract_info(main_fallback["url"], download=True)
                                return main_fallback

                        raise ValueError(
                            f"Das Video ({video_id}) existiert auf dem Server nicht mehr (HTTP 410: Gone – "
                            "vom Anbieter gelöscht oder deaktiviert)."
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
    all_vcodecs: set[str] = set()

    for idx, entry in enumerate(entries_list):
        formats = entry.get("formats") or []
        heights: set[int] = set()
        vcodecs: set[str] = set()
        best_filesize = entry.get("filesize") or entry.get("filesize_approx") or 0

        for fmt in formats:
            h = fmt.get("height")
            if isinstance(h, int) and h >= 144:
                heights.add(h)
                all_heights.add(h)
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
                "available_heights": sorted(heights, reverse=True),
                "available_codecs": sorted(vcodecs),
                "approx_size": format_bytes(best_filesize),
                "is_suspected_ad": suspected_ad,
                "ad_reason": ad_reason,
            }
        )

    # Sortiere so, dass echte Hauptvideos zuerst stehen, falls ein kurzer Pre-Roll-Clip erkannt wurde
    primary = next((e for e in analyzed_entries if not e["is_suspected_ad"]), analyzed_entries[0])

    return {
        "title": info.get("title") or primary["title"],
        "extractor": info.get("extractor_key") or primary["extractor"],
        "webpage_url": info.get("webpage_url") or url,
        "thumbnail": info.get("thumbnail") or primary["thumbnail"],
        "duration": info.get("duration") or primary["duration"],
        "duration_formatted": format_seconds(info.get("duration") or primary["duration"]),
        "uploader": info.get("uploader") or primary["uploader"],
        "available_heights": sorted(all_heights, reverse=True),
        "available_codecs": sorted(all_vcodecs),
        "entries": analyzed_entries,
        "ad_filtered_count": sum(1 for e in analyzed_entries if e["is_suspected_ad"]),
    }


def run_download_job(job_id: str, params: dict[str, Any]) -> None:
    url = str(params.get("url") or "").strip()
    output_dir = str(Path(str(params.get("output_dir") or "~/Downloads/ViDow")).expanduser())
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

    os.makedirs(output_dir, exist_ok=True)

    def update_job(**kwargs: Any) -> None:
        with JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id].update(kwargs)
                JOBS[job_id]["updated_at"] = time.time()

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

    outtmpl = os.path.join(
        output_dir,
        f"{custom_title}.%(ext)s" if custom_title else "%(title).180B [%(id)s].%(ext)s",
    )

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
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
        "postprocessors": postprocessors,
        "concurrent_fragment_downloads": 4,
        "quiet": True,
        "no_warnings": True,
    }

    if quality != "audio":
        ydl_opts["merge_output_format"] = container

    if postprocessor_args:
        ydl_opts["postprocessor_args"] = postprocessor_args

    if FFMPEG_PATH:
        ydl_opts["ffmpeg_location"] = FFMPEG_PATH

    apply_impersonate_and_cookies(ydl_opts, cookies_browser, custom_headers)

    # Schutz gegen vorgeschaltete Werbe-Clips bei Multi-Stream-Webseiten
    if skip_preroll_ads:
        def ad_match_filter(info_dict: dict[str, Any], *, incomplete: bool = False) -> str | None:
            if incomplete:
                return None
            entry_url = str(info_dict.get("url") or info_dict.get("webpage_url") or "")
            if AD_PATTERNS.search(entry_url):
                return "Übersprungen: Werbe-Stream erkannt"
            dur = info_dict.get("duration")
            # Nur filtern, wenn die Dauer bekannt ist und unter dem Schwellenwert liegt
            if min_duration > 0 and dur is not None and dur < min_duration:
                return f"Übersprungen: Clip ist kürzer als {min_duration}s ({int(dur)}s – vermutlich Pre-Roll-Werbung)"
            return None

        ydl_opts["match_filter"] = ad_match_filter

    try:
        update_job(status="downloading", status_text="Verbinde & analysiere Stream…")
        info = extract_info_with_fallback(
            ydl_opts, url, download=True, custom_headers=custom_headers
        )
        final_path = ""
        if info:
            title = info.get("title") or custom_title or "Video"
            thumb = info.get("thumbnail")
            if "requested_downloads" in info and info["requested_downloads"]:
                final_path = info["requested_downloads"][0].get("filepath") or ""
            if not final_path:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl_tmp:
                    final_path = ydl_tmp.prepare_filename(info)
                if quality == "audio":
                    final_path = str(Path(final_path).with_suffix(f".{audio_format}"))
                elif container:
                    cand = str(Path(final_path).with_suffix(f".{container}"))
                    if os.path.exists(cand):
                        final_path = cand
            update_job(
                status="completed",
                status_text="Abgeschlossen",
                title=title,
                thumbnail=thumb,
                progress=100.0,
                eta_formatted="Fertig",
                filepath=final_path,
                filename=os.path.basename(final_path) if final_path else "",
            )
        else:
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
            self._send_json(
                {
                    "ok": True,
                    "app": "ViDow",
                    "yt_dlp_version": yt_dlp.version.__version__,
                    "ffmpeg_available": bool(FFMPEG_PATH),
                    "ffmpeg_path": FFMPEG_PATH,
                    "settings": settings,
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
            # Öffnet den nativen macOS Ordnerdialog (direkt im ViDow-Fenster oder via Finder/AppleScript)
            try:
                chosen = ""
                if ACTIVE_WINDOW is not None:
                    try:
                        import webview

                        folder_Enum = getattr(webview, "FileDialog", None)
                        dialog_type = folder_Enum.FOLDER if folder_Enum else webview.FOLDER_DIALOG
                        res = ACTIVE_WINDOW.create_file_dialog(
                            dialog_type,
                            directory=load_settings().get("output_dir", str(Path.home() / "Downloads")),
                        )
                        if res and len(res) > 0:
                            chosen = str(res[0]).rstrip("/")
                        else:
                            self._send_json({"ok": False, "cancelled": True})
                            return
                    except Exception:
                        chosen = ""

                if not chosen:
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
                        chosen = proc.stdout.strip().rstrip("/")

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
                proc = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=3)
                self._send_json({"ok": True, "text": proc.stdout.strip()})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        if route == "/api/open-folder":
            target = str(payload.get("path") or "").strip()
            if not target:
                target = load_settings().get("output_dir", "")
            target_path = Path(target).expanduser()
            try:
                if target_path.is_file():
                    subprocess.Popen(["open", "-R", str(target_path)])
                else:
                    target_path.mkdir(parents=True, exist_ok=True)
                    subprocess.Popen(["open", str(target_path)])
                self._send_json({"ok": True})
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

            # Speichere aktuelle Präferenzen als Standard
            save_settings(
                {
                    "output_dir": payload.get("output_dir") or load_settings()["output_dir"],
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
                "output_dir": str(Path(str(payload.get("output_dir") or load_settings()["output_dir"])).expanduser()),
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


ACTIVE_WINDOW: Any = None


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


def main() -> None:
    global ACTIVE_WINDOW
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    settings = load_settings()
    Path(settings["output_dir"]).expanduser().mkdir(parents=True, exist_ok=True)

    server, port = start_http_server()
    url = f"http://127.0.0.1:{port}"
    print("=" * 60)
    print(f"🎬 ViDow läuft auf: {url}")
    print(f"📂 Standard-Speicherort: {settings['output_dir']}")
    print(f"🔧 yt-dlp Version: {yt_dlp.version.__version__}")
    print(f"🎞️  ffmpeg: {FFMPEG_PATH or 'Nicht gefunden (bitte brew install ffmpeg)'}")
    print("=" * 60)

    use_browser_only = "--browser" in sys.argv or os.environ.get("VIDOW_BROWSER_ONLY") == "1"

    if not use_browser_only:
        try:
            import webview

            if server is not None:
                srv_thread = threading.Thread(target=server.serve_forever, daemon=True)
                srv_thread.start()

            ACTIVE_WINDOW = webview.create_window(
                "ViDow — Video Downloader",
                url,
                width=1260,
                height=860,
                min_size=(920, 640),
            )
            webview.start()
            if server is not None:
                server.shutdown()
                server.server_close()
            return
        except Exception as exc:
            print(f"[ViDow] Hinweis: Konnte natives Fenster nicht starten ({exc}), öffne im Browser…")

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
