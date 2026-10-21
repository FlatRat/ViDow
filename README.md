# 🎬 ViDow — Nativer Video-Downloader & Stream-Filter (Windows & macOS)

**ViDow** ist dein persönliches Video-Download-Tool für **Windows** und **macOS**. Es läuft in einem **eigenen, vom Browser entkoppelten Desktop-Programmfenster** (über natives WebView2 auf Windows bzw. WebKit auf macOS via `pywebview`) auf Basis von `yt-dlp`, `curl-cffi` und `ffmpeg` – plus optionaler Browser-Erweiterung für Chrome, Brave und Edge.

---

## ✨ Features

1. **Eigenständiges Desktop-Fenster & Taskleisten-/Dock-Integration**
   - Startet als **echte Desktop-App mit eigenem Logo** in der Taskleiste (Windows) bzw. im Dock/Finder (macOS).
   - Komplett **ohne Browser-Tab und auf Wunsch ohne offenes Terminal-Fenster** (z. B. via `ViDow-NoConsole.vbs` auf Windows).
   - Schließt du das ViDow-Fenster, beendet sich auch der Hintergrundprozess sauber.

2. **Qualität, Codec & Container frei wählbar**
   - **Auflösungen:** Beste verfügbar (Auto), 4K (`2160p`), 2K (`1440p`), Full HD (`1080p`), HD (`720p`), SD (`480p`), `360p` oder **Nur Audio** (`MP3`, `M4A`, `FLAC`, `WAV`, `Opus`).
   - **Video-Codecs:** `Automatisch (Original)`, `H.264 / AVC` (maximale Kompatibilität für PC, TV, Handy & Co.), `H.265 / HEVC`, `VP9`, `AV1`.
   - **Optionales Auto-Transcoding:** Falls der gewünschte Codec (z. B. `H.264`) auf der Webseite nicht nativ angeboten wird, wandelt `ffmpeg` das Video auf Wunsch automatisch um.
   - **Container:** `MP4`, `MKV`, `WebM`, `MOV`.

3. **Freie Speicherort-Auswahl (inkl. nativer Ordner-Dialog)**
   - Klicke auf **„📂 Ordner wählen…“**, um direkt im nativen Ordnerdialog (Windows Explorer bzw. macOS Finder) deinen Zielordner auszuwählen.
   - Zuletzt genutzte Ordner werden als Schnellauswahl-Chips gespeichert.
   - Fertige Downloads lassen sich per Klick direkt im Dateimanager markieren (**„Im Explorer zeigen“** auf Windows / **„Im Finder zeigen“** auf Mac).

4. **4-Stufen-Schutz gegen Werbung („Wenn Werbung vor einem Video kommt“)**
   - **Stufe 1 – Direkter Manifest-Abgriff (Pre-Roll-Bypass):** Klassische Werbung vor Videos (YouTube, Mediatheken, Vimeo, Nachrichtenportale) wird im Browser vom Player über externe Ad-Server eingespielt. Da ViDow den Stream direkt von der Quelle lädt, fällt diese Pre-Roll-Werbung **automatisch weg**.
   - **Stufe 2 – Multi-Stream- & Mindestdauer-Filter:** Bündelt eine Webseite auf einer URL erst einen kurzen Werbe-Clip (z. B. 20 Sek.) und danach das Hauptvideo, erkennt ViDow bekannte Ad-Domains sowie Clips unter deiner eingestellten Mindestdauer (Standard: `45 Sek.`) und wählt diese automatisch ab.
   - **Stufe 3 – SponsorBlock-Integration:** Schneidet auf Wunsch sogar **im Video eingesprochene Sponsoren-Segmente, Eigenwerbung und Intros** beim Download per `ffmpeg` heraus.
   - **Stufe 4 – ViDow Browser-Helper (`extension/`):** Für exotische Webseiten, die den Hauptstream (`.m3u8` / `.mp4`) erst im Netzwerk laden, *nachdem* der Werbespot im Browser abgelaufen ist.

---

## 🚀 Starten auf Windows

### Variante 1: Einfacher Doppelklick (`ViDow.bat`)
Macht alles automatisch (prüft Python, richtet die `.venv` ein, installiert Pakete und startet ViDow):
- Doppelklick auf **`ViDow.bat`** im Projektordner.

### Variante 2: Lautlos ohne schwarzes Konsolenfenster (`ViDow-NoConsole.vbs`)
Startet ViDow direkt im sauberen Desktop-Fenster ohne Hintergrund-Eingabeaufforderung:
- Doppelklick auf **`ViDow-NoConsole.vbs`**.

### Variante 3: Desktop-Verknüpfung mit App-Icon anlegen
Erzeugt eine bequeme Desktop-Verknüpfung (`ViDow.lnk`) auf deinem Windows-Desktop:
```powershell
python create_windows_shortcut.py
```

### Variante 4: Als eigenständiges Windows-Programm (`ViDow.exe`) kompilieren
Möchtest du ein komplett eigenständiges Programm erzeugen:
```powershell
python build_windows_exe.py
```
Das fertige Programm liegt anschließend unter `dist/ViDow/ViDow.exe`.

### 🎞️ FFmpeg unter Windows installieren (falls noch nicht vorhanden)
Falls FFmpeg noch nicht auf deinem PC installiert ist, öffne PowerShell und tippe:
```powershell
winget install Gyan.FFmpeg
```
*(ViDow erkennt FFmpeg automatisch im Windows-PATH, in WinGet-, Scoop- und Chocolatey-Verzeichnissen).*

---

## 🍏 Starten auf macOS

### Variante A: Als native Mac-App (`ViDow.app` – ohne Terminal & ohne Browser)
Im Finder einfach **`ViDow.app`** doppelklicken oder in dein **macOS-Dock** ziehen!

*(Um `ViDow.app` nach einem frischen `git clone` neu zu erzeugen:)*
```bash
python3 build_mac_app.py
```

### Variante B: Über `ViDow.command`
```bash
./ViDow.command
```
*(Falls du ViDow ausnahmsweise im Webbrowser statt im eigenen Fenster öffnen möchtest: `./ViDow.command --browser`)*

### 🎞️ FFmpeg unter macOS installieren
```bash
brew install ffmpeg
```

---

## 🧩 Optionale Browser-Erweiterung installieren (Chrome / Brave / Edge)

1. Öffne im Browser `chrome://extensions/` (bzw. `edge://extensions/` oder `brave://extensions/`).
2. Aktiviere oben rechts den **Entwicklermodus** (Developer mode).
3. Klicke auf **„Entpackte Erweiterung laden“** (Load unpacked).
4. Wähle den Unterordner **`extension`** aus deinem ViDow-Projektverzeichnis aus.
