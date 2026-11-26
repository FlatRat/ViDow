# 🎬 ViDow Studio — Nativer Video- & Audio-Downloader (macOS & Windows)

**ViDow** ist eine eigenständige, auslieferbare Desktop-App für **macOS** (`.app` / `.dmg` über WebKit) und **Windows** (`.exe` / `.zip` über WebView2) auf Basis von `yt-dlp`, `curl-cffi` und integriertem `ffmpeg` – inklusive optionaler Browser-Erweiterung für Chrome, Brave und Edge. Ein Projekt von **[lg-craft](https://lg-craft.com)**.

---

## ✨ Highlights in Version 2.0

1. **100 % eigenständige & auslieferbare Desktop-App**
   - Läuft als echte native App ohne Python-, Homebrew- oder Terminal-Pflicht auf Zielgeräten.
   - **Integriertes `ffmpeg` out-of-the-box:** Dank gebündeltem `imageio-ffmpeg` funktionieren 4K-Merging, MP3-Extraktion, SponsorBlock und H.264-Konvertierung sofort auf jedem Mac und Windows-PC.
   - **OS-konforme Datenhaltung:** Nutzereinstellungen liegen sauber unter `~/Library/Application Support/ViDow` (macOS) bzw. `%APPDATA%\ViDow` (Windows), sodass das App-Bundle schreibgeschützt unter `/Applications` oder `Program Files` liegen kann.

2. **Neues Studio-Design & App-Icon**
   - Überarbeitetes **Studio-Interface** mit adaptivem Hell-/Dunkel-Modus (System, Hell, Studio Dark), Spotlight-artiger URL-Leiste, klickbaren Qualitäts-Chips und Live-Warteschlange.
   - Neues hochauflösendes **Squircle-Studio-Icon** (`AppIcon.icns`, `icon.ico`, `icon.png`, `icon.svg` sowie Extension-Icons).

3. **Quer- & Hochkantvideos in jeder Qualitätsstufe**
   - Orientierungsunabhängige Qualitätsauswahl (`best`, `2160p`, `1440p`, `1080p`, `720p`, `540p`, `480p`, `360p`, `240p` oder **Nur Audio** in `MP3`, `M4A`, `FLAC`, `WAV`, `Opus`) – ideal für klassische 16:9-Videos ebenso wie für 9:16-Shorts, Reels und TikToks.
   - **Codecs & Container:** `Auto`, `H.264`, `H.265 / HEVC`, `VP9`, `AV1` in `MP4`, `MKV`, `WebM` oder `MOV`.

4. **4-Stufen-Schutz gegen Werbung & geschützte Player**
   - **Stufe 1 – Direkter Manifest-Abgriff:** Pre-Roll-Werbespots externer Ad-Server entfallen automatisch.
   - **Stufe 2 – Multi-Clip-Filter:** Erkennt kurze Werbe-Clips auf Multi-Stream-Seiten, ohne kurze Einzel-Shorts zu überspringen.
   - **Stufe 3 – KVS- & Embed-Tiefensuche + SponsorBlock:** Entschlüsselt eingebettete Player/Master-Playlists und schneidet auf Wunsch Sponsoren-Segmente per `ffmpeg` heraus.
   - **Stufe 4 – ViDow Studio Browser-Helper (`extension/`):** Überspringt Pre-Roll-Werbung im Browser-Tab und übergibt `.m3u8`/`.mp4`-Streams mit 1 Klick an ViDow.

---

## 📦 Auslieferbare Pakete bauen (macOS & Windows)

### 🍏 macOS: Eigenständige `ViDow.app`, Installer-`.dmg` & Download-`.zip` erzeugen
```bash
python3 -m pip install -r requirements.txt pyinstaller
python3 build_mac_app.py
```
Erzeugt:
- `dist/ViDow.app` (signiertes Standalone-App-Bundle, auch nach `./ViDow.app` synchronisiert)
- `dist/ViDow-2.0.2-macOS.dmg` (versandfertiges Disk-Image mit `/Applications`-Verknüpfung)
- `dist/ViDow-2.0.2-macOS.zip` (fertiges Download-Paket mit `ViDow.app`, Kurzanleitung & Browser-Helper)

### 🪟 Windows: Nativen `Setup.exe`-Installer & Download-`.zip` erzeugen
```powershell
winget install JRSoftware.InnoSetup
python -m pip install -r requirements.txt pyinstaller
python build_windows_exe.py
```
Erzeugt:
- `dist/ViDow-2.0.2-Windows-Setup.exe` (nativer Windows-10/11-Installer mit Startmenü-/Desktop-Eintrag, Deinstallationsroutine & integriertem `ffmpeg` – funktioniert ohne Admin-Zwang)
- `dist/ViDow-2.0.2-Windows-Setup.zip` (fertiges Download-Paket mit `Setup.exe`, Kurzanleitung & Browser-Helper)

### ☁️ Automatische GitHub-Releases (CI/CD)
Über [`.github/workflows/release.yml`](.github/workflows/release.yml) baut GitHub Actions automatisch sowohl die **macOS-Pakete (`.dmg` & `.zip`)** als auch die **Windows-Pakete (`Setup.exe` & `.zip`)** – entweder manuell per *Workflow Dispatch* oder automatisch beim Pushen eines Versions-Tags (z. B. `git tag v2.0.2 && git push origin v2.0.2`).

---

## 🛠️ Lokaler Start (ohne Kompilierung)

- **Windows:**
  - Doppelklick auf `ViDow-NoConsole.vbs` (startet lautlos im nativen Desktop-Fenster und richtet `.venv` beim ersten Start automatisch ein) oder `ViDow.bat`
  - Optional Desktop- & Startmenü-Verknüpfung anlegen: `python create_windows_shortcut.py`
- **macOS:** `./ViDow.command` (oder `python3 build_mac_app.py --dev-wrapper`)

---

## 🧩 Optionale Browser-Erweiterung installieren (Chrome / Brave / Edge)

1. Öffne `chrome://extensions/` (bzw. `edge://extensions/` oder `brave://extensions/`).
2. Aktiviere oben rechts den **Entwicklermodus**.
3. Klicke auf **„Entpackte Erweiterung laden“** und wähle den Ordner **`extension`** aus.
