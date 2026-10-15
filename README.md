# 🎬 ViDow — Lokaler Video-Downloader & Stream-Filter

**ViDow** ist dein persönliches Video-Download-Tool für macOS. Es kombiniert eine lokale Web-App (auf Basis von `yt-dlp` und `ffmpeg`) mit einer optionalen Browser-Erweiterung für Chrome/Brave/Edge.

---

## ✨ Features

1. **Qualität, Codec & Container frei wählbar**
   - **Auflösungen:** Beste verfügbar (Auto), 4K (`2160p`), 2K (`1440p`), Full HD (`1080p`), HD (`720p`), SD (`480p`), `360p` oder **Nur Audio** (`MP3`, `M4A`, `FLAC`, `WAV`, `Opus`).
   - **Video-Codecs:** `Automatisch (Original)`, `H.264 / AVC` (perfekt für QuickTime, iPhone & iPad), `H.265 / HEVC`, `VP9`, `AV1`.
   - **Optionales Auto-Transcoding:** Falls der gewünschte Codec (z. B. `H.264`) auf der Webseite nicht nativ angeboten wird, wandelt `ffmpeg` das Video auf Wunsch automatisch um.
   - **Container:** `MP4`, `MKV`, `WebM`, `MOV`.

2. **Freie Speicherort-Auswahl (inkl. macOS Finder-Dialog)**
   - Klicke im Dashboard auf **„📂 Ordner wählen…“**, um über den echten **macOS Finder-Dialog** deinen Zielordner auszuwählen.
   - Zuletzt genutzte Ordner werden als Schnellauswahl-Chips gespeichert.
   - Fertige Downloads lassen sich per Klick direkt im Finder markieren (**„Im Finder zeigen“**).

3. **4-Stufen-Schutz gegen Werbung („Wenn Werbung vor einem Video kommt“)**
   - **Stufe 1 – Direkter Manifest-Abgriff (Pre-Roll-Bypass):** Klassische Werbung vor Videos (YouTube, Mediatheken, Vimeo, Nachrichtenportale) wird im Browser vom Player über externe Ad-Server eingespielt. Da ViDow den Stream direkt von der Quelle lädt, fällt diese Pre-Roll-Werbung **automatisch weg**.
   - **Stufe 2 – Multi-Stream- & Mindestdauer-Filter:** Bündelt eine Webseite auf einer URL erst einen kurzen Werbe-Clip (z. B. 20 Sek.) und danach das Hauptvideo, erkennt ViDow bekannte Ad-Domains sowie Clips unter deiner eingestellten Mindestdauer (Standard: `45 Sek.`) und wählt diese automatisch ab.
   - **Stufe 3 – SponsorBlock-Integration:** Schneidet auf Wunsch sogar **im Video eingesprochene Sponsoren-Segmente, Eigenwerbung und Intros** beim Download per `ffmpeg` heraus.
   - **Stufe 4 – ViDow Browser-Helper (`extension/`):** Für exotische Webseiten, die den Hauptstream (`.m3u8` / `.mp4`) erst im Netzwerk laden, *nachdem* der Werbespot im Browser abgelaufen ist:
     - Besitzt einen Button **„⚡ Laufende Pre-Roll-Werbung im Tab überspringen“**, der das Werbevideo im Tab mit 16-facher Geschwindigkeit ans Ende springen lässt.
     - Fängt echte `.m3u8`-, `.mpd`- und `.mp4`-Streams im Hintergrund ab (Ad-Server werden herausgefiltert) und schickt sie per Klick an ViDow.

---

## 🚀 Starten

Im Terminal oder per Doppelklick im Finder:

```bash
cd /Users/lucasgoedel/Projekte/ViDow
chmod +x ViDow.command
./ViDow.command
```

Beim ersten Start legt `ViDow.command` automatisch eine lokale Python-Umgebung (`.venv`) an, installiert `yt-dlp` und öffnet das Dashboard unter **[http://127.0.0.1:8765](http://127.0.0.1:8765)**.
*(Hinweis: `ffmpeg` ist auf deinem Mac bereits unter `/opt/homebrew/bin/ffmpeg` installiert und wird automatisch erkannt).*

---

## 🧩 Optionale Browser-Erweiterung installieren (Chrome / Brave / Edge)

1. Öffne im Browser `chrome://extensions/`
2. Aktiviere oben rechts den **Entwicklermodus** (Developer mode).
3. Klicke auf **„Entpackte Erweiterung laden“** (Load unpacked).
4. Wähle den Ordner `/Users/lucasgoedel/Projekte/ViDow/extension` aus.
