# 🎬 ViDow — Nativer macOS Video-Downloader & Stream-Filter

**ViDow** ist dein persönliches Video-Download-Tool für macOS. Es läuft in einem **eigenen, vom Browser entkoppelten macOS-Programmfenster** (über natives macOS WebKit / `pywebview`) auf Basis von `yt-dlp`, `curl-cffi` und `ffmpeg` – plus optionaler Browser-Erweiterung für Chrome/Brave/Edge.

---

## ✨ Features

1. **Eigenständiges macOS-Fenster & `ViDow.app`**
   - Startet als **eigenständige Mac-App (`ViDow.app`)** mit eigenem App-Icon im Finder/Dock – komplett **ohne Browser-Tab und ohne offenes Terminal-Fenster**.
   - Schließt du das ViDow-Fenster, beendet sich auch der Hintergrundprozess sauber.

2. **Qualität, Codec & Container frei wählbar**
   - **Auflösungen:** Beste verfügbar (Auto), 4K (`2160p`), 2K (`1440p`), Full HD (`1080p`), HD (`720p`), SD (`480p`), `360p` oder **Nur Audio** (`MP3`, `M4A`, `FLAC`, `WAV`, `Opus`).
   - **Video-Codecs:** `Automatisch (Original)`, `H.264 / AVC` (perfekt für QuickTime, iPhone & iPad), `H.265 / HEVC`, `VP9`, `AV1`.
   - **Optionales Auto-Transcoding:** Falls der gewünschte Codec (z. B. `H.264`) auf der Webseite nicht nativ angeboten wird, wandelt `ffmpeg` das Video auf Wunsch automatisch um.
   - **Container:** `MP4`, `MKV`, `WebM`, `MOV`.

3. **Freie Speicherort-Auswahl (inkl. macOS Ordner-Dialog)**
   - Klicke auf **„📂 Ordner wählen…“**, um direkt im nativen **macOS Ordnerdialog** deinen Zielordner auszuwählen.
   - Zuletzt genutzte Ordner werden als Schnellauswahl-Chips gespeichert.
   - Fertige Downloads lassen sich per Klick direkt im Finder markieren (**„Im Finder zeigen“**).

4. **4-Stufen-Schutz gegen Werbung („Wenn Werbung vor einem Video kommt“)**
   - **Stufe 1 – Direkter Manifest-Abgriff (Pre-Roll-Bypass):** Klassische Werbung vor Videos (YouTube, Mediatheken, Vimeo, Nachrichtenportale) wird im Browser vom Player über externe Ad-Server eingespielt. Da ViDow den Stream direkt von der Quelle lädt, fällt diese Pre-Roll-Werbung **automatisch weg**.
   - **Stufe 2 – Multi-Stream- & Mindestdauer-Filter:** Bündelt eine Webseite auf einer URL erst einen kurzen Werbe-Clip (z. B. 20 Sek.) und danach das Hauptvideo, erkennt ViDow bekannte Ad-Domains sowie Clips unter deiner eingestellten Mindestdauer (Standard: `45 Sek.`) und wählt diese automatisch ab.
   - **Stufe 3 – SponsorBlock-Integration:** Schneidet auf Wunsch sogar **im Video eingesprochene Sponsoren-Segmente, Eigenwerbung und Intros** beim Download per `ffmpeg` heraus.
   - **Stufe 4 – ViDow Browser-Helper (`extension/`):** Für exotische Webseiten, die den Hauptstream (`.m3u8` / `.mp4`) erst im Netzwerk laden, *nachdem* der Werbespot im Browser abgelaufen ist.

---

## 🚀 Starten

### Variante A: Als echte Mac-App (`ViDow.app` – ohne Terminal & ohne Browser)
Im Projektordner liegt direkt **`ViDow.app`**. Du kannst sie im Finder einfach **doppelklicken** oder in dein **macOS-Dock** ziehen!

*(Um `ViDow.app` nach einem frischen `git clone` neu zu erzeugen:)*
```bash
python3 build_mac_app.py
```

### Variante B: Über `ViDow.command`
```bash
./ViDow.command
```
*(Falls du ViDow ausnahmsweise im Webbrowser statt im eigenen Fenster öffnen möchtest: `./ViDow.command --browser`)*

---

## 🧩 Optionale Browser-Erweiterung installieren (Chrome / Brave / Edge)

1. Öffne im Browser `chrome://extensions/`
2. Aktiviere oben rechts den **Entwicklermodus** (Developer mode).
3. Klicke auf **„Entpackte Erweiterung laden“** (Load unpacked).
4. Wähle den Ordner `/Users/lucasgoedel/Projekte/ViDow/extension` aus.
