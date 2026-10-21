# Changelog

Alle nennenswerten Änderungen an **ViDow** werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/)
und das Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

---

## [1.1.0] - 2026-10-21

### ✨ Hinzugefügt (Windows-Unterstützung & Cross-Platform)
- **Nativer Windows-Support:** ViDow läuft ab sofort vollständig und nativ unter Windows 10/11 im eigenen Desktop-Fenster (via Microsoft Edge WebView2 / `pywebview`).
- **Doppelklick-Starter [`ViDow.bat`](ViDow.bat):** Richtet beim ersten Aufruf automatisch die virtuelle Python-Umgebung (`.venv`) ein, prüft Abhängigkeiten und startet die App.
- **Lautloser Starter [`ViDow-NoConsole.vbs`](ViDow-NoConsole.vbs):** Ermöglicht den Start direkt als Desktop-App ohne offenes schwarzes Terminalfenster.
- **Desktop-Verknüpfung [`create_windows_shortcut.py`](create_windows_shortcut.py):** Erstellt per Befehl eine Windows-Desktop-Verknüpfung mit offiziellem App-Icon.
- **Standalone Build [`build_windows_exe.py`](build_windows_exe.py):** Kompiliert ViDow mit PyInstaller zu einer eigenständigen Windows-Anwendung unter `dist/ViDow/ViDow.exe`.
- **Automatische FFmpeg-Erkennung unter Windows:** Sucht `ffmpeg` im System-`PATH` sowie in WinGet (`Gyan.FFmpeg`), Scoop, Chocolatey und lokalen Verzeichnissen.
- **Dateimanager-Integration:** Downloads lassen sich per Klick direkt im Windows Explorer markieren und öffnen (`explorer.exe /select,...`).
- **Nativer Ordnerauswahl-Dialog:** Windows-spezifischer Fallback für den nativen Ordner-Dialog via `FolderBrowserDialog` und `tkinter`.
- **System-Zwischenablage für Windows:** URL-Einfügen aus der Zwischenablage funktioniert nun auch unter Windows zuverlässig.
- **Browser-Cookies unter Windows:** Cookie-Pfade für Google Chrome, Microsoft Edge, Brave und Mozilla Firefox unter `%LOCALAPPDATA%` und `%APPDATA%` integriert.
- **Windows Taskleiste & Icon:** Eindeutige App-Identifikation via `AppUserModelID` (`FlatRat.ViDow.App.1.0`) und Multi-Resolution-Icon [`static/icon.ico`](static/icon.ico).

### 🛠️ Behoben & Verbessert
- **Konsolen-Encoding:** UTF-8 wird auf Windows-Konsolen erzwungen, wodurch `UnicodeEncodeError` bei Emojis und Sonderzeichen auf Standard-Windows-Konsolen (CP1252) verhindert werden.
- **Dynamische UI-Labels:** Buttons und Hinweistexte passen sich automatisch dem Betriebssystem an („Im Explorer zeigen“ auf Windows, „Im Finder zeigen“ auf macOS).
- **Dokumentation:** Ausführliche Anleitung für Windows und macOS in der [`README.md`](README.md) ergänzt.

---

## [1.0.0] - 2026-10-15

### ✨ Initiale Veröffentlichung (macOS)
- Lokaler Video-Downloader & Stream-Sniffer für macOS (via `yt-dlp`, `curl-cffi`, `ffmpeg`).
- Eigenständiges macOS-Programmfenster über natives WebKit (`pywebview`).
- Generierung des macOS-App-Bundles `ViDow.app` via `build_mac_app.py`.
- Freie Auswahl von Auflösung (bis 4K), Video-Codec (H.264, HEVC, VP9, AV1) und Container (MP4, MKV, WebM, MOV) bzw. Audio-Extraktion.
- 4-Stufen-Schutz gegen vorgeschaltete Pre-Roll-Werbung.
- Optionale SponsorBlock-Integration zum Herausschneiden von Sponsorensegmenten.
- Browser-Erweiterung für Chrome, Brave und Edge im Ordner `extension/`.
