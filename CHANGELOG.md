# Changelog

Alle nennenswerten Änderungen an **ViDow** werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/)
und das Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

---

## [2.0.3] - 2026-11-26

### 🛠️ Behoben & Verbessert
- **Absturzsichere Ordner- & Cookie-Zugriffe (macOS & Windows):** Fängt `PermissionError` / `OSError` bei gesperrten Benutzer-, System- oder Browser-Profilordnern zuverlässig ab und weicht für `settings.json`/Logs bei nicht beschreibbarem Konfigurationspfad automatisch aus.
- **Footer-Farbtokens im Hell-/Dunkel-Modus:** Nutzt im Studio-Footer konsistent die adaptiven Design-Tokens (`--muted` / `--text`) für sauberen Kontrast in Hell- und Studio-Dark-Darstellung.
- **Externe Links & Build-Aufräumung unter Windows:** Öffnet externe Links unter Windows bevorzugt via `os.startfile()` und bereinigt veraltete Setup-/ZIP-Artefakte in `dist/` vor neuen Builds.

---

## [2.0.2] - 2026-11-26

### ✨ Hinzugefügt
- **Fertiges macOS-Download-ZIP (`build_mac_app.py`):** Erzeugt neben `ViDow-2.0.2-macOS.dmg` automatisch das versandfertige Download-Archiv `ViDow-2.0.2-macOS.zip` (mit signierter `ViDow.app`, Kurzanleitung und optionaler Browser-Erweiterung unter Erhalt aller Symlinks & Codesignaturen) – auch direkt in GitHub Actions (`.github/workflows/release.yml`).
- **Nativer Windows-Installer & Download-ZIP (`build_windows_exe.py`):** Kompiliert per Inno Setup 6 automatisch `ViDow-2.0.2-Windows-Setup.exe` sowie das fertige Download-Paket `ViDow-2.0.2-Windows-Setup.zip`.
- **Urheber-Hinweis (`lg-craft`):** Dezente Verlinkung auf [lg-craft](https://lg-craft.com) im Studio-Footer, in der Browser-Erweiterung sowie in den macOS-/Windows-App-Metadaten (inkl. Öffnen im Systembrowser via `/api/open-external`).

### 🛠️ Behoben & Verbessert
- **macOS- & Windows-Fensterintegration:** Synchronisiert die native macOS-Titelleiste (`NSWindow` Aqua/DarkAqua) und Windows-DWM-Titelleiste live mit der gewählten App-Darstellung; Single-Instance-Erkennung holt ein bereits geöffnetes oder minimiertes Fenster auf beiden Systemen zuverlässig in den Vordergrund.
- **Browser-Cookies & Extension-Auto-Discovery:** Cookie-Pfade für Opera/Opera GX und Vivaldi auch unter macOS ergänzt; die Browser-Erweiterung erkennt laufende ViDow-Instanzen automatisch auf den Ports `8765–8767`.
- **WebKit Popover-Darstellung (`v2.0.1`):** Clipping durch `backdrop-filter` und den nativen WebKit-UA-Rahmen am Darstellungs-Popover behoben.

---

## [2.0.0] - 2026-11-25

### ✨ Hinzugefügt (Native Standalone-Auslieferung, Studio-UI & neues Icon)
- **Auslieferbare macOS-App & `.dmg`-Installer (`build_mac_app.py`):** Kompiliert ViDow per PyInstaller zu einem komplett eigenständigen, ad-hoc-signierten `ViDow.app`-Bundle sowie einem versandfertigen `ViDow-2.0.0-macOS.dmg` Disk-Image (inkl. `/Applications`-Symlink und App Transport Security Konfiguration).
- **Auslieferbares Windows-Release-Archiv (`build_windows_exe.py`):** Verpackt den eigenständigen Windows-Build automatisch als `ViDow-2.0.0-Windows-x64.zip` inklusive Browser-Erweiterung.
- **Integriertes Zero-Setup `ffmpeg` (`imageio-ffmpeg`):** Liefert ein eingebettetes statisches `ffmpeg`-Binary direkt im App-Paket mit, falls auf dem Zielgerät kein System-`ffmpeg` installiert ist.
- **Automatisierte GitHub Actions Release-Pipeline (`.github/workflows/release.yml`):** Baut macOS-DMG und Windows-ZIP automatisch in der Cloud und hängt sie bei Versions-Tags (`v*`) an GitHub Releases an.
- **Neues Studio-UI & Farbschema-Steuerung:** Komplett überarbeitetes Desktop-Interface mit kompakter Top-Bar, Spotlight-URL-Eingabe, klickbaren Qualitäts-Chips, Video/Audio-Modus-Umschalter, aufklappbaren Schutz-Sektionen (`<details>`) und System/Hell/Dunkel-Darstellungswahl.
- **Neues Studio-App-Icon (`generate_icons.py`):** Hochauflösender plattformübergreifender 2048px-Supersampling-Generator für `AppIcon.icns`, `icon.ico`, `icon.png`, `icon.svg` und die Browser-Extension-Icons (`16px`, `48px`, `128px`).

### 🛠️ Behoben & Verbessert
- **Vollständige Windows-10/11-Integration:** Native DWM-Titelleiste (automatisch Dunkel/Hell synchron zur App & gerundete Windows-11-Ecken), Per-Monitor-High-DPI-Schärfe, Single-Instance-Fensterfokus, sofortige Win32-Zwischenablage ohne Konsolen-Aufblitzen (`CREATE_NO_WINDOW`), moderner Windows-Explorer-Ordnerdialog, präzise Dateimarkierung per `SHOpenFolderAndSelectItems`, OneDrive-kompatible Systemordner (`SHGetKnownFolderPath`), `MAX_PATH`-sichere Windows-Dateinamen sowie randoptimiertes `.ico`-Icon und Startmenü-/Desktop-Verknüpfungen.
- **OS-konformer Einstellungs- & Log-Pfad:** Speichert `settings.json` und Windowed-Logs nun im nativen Benutzerverzeichnis (`~/Library/Application Support/ViDow` bzw. `%APPDATA%\ViDow`), sodass schreibgeschützte Installationen unter `/Applications` oder `Program Files` fehlerfrei funktionieren.
- **Hochkantvideos & Multi-Qualitäts-Downloads:** Orientierungsunabhängige Qualitätsstufen (`res:<Stufe>` inkl. `540p`/`240p`), KVS-/Iframe-/HTML5-Stream-Fallbacks und auflösungsbasierte Dateinamen.

---

## [1.1.0] - 2026-10-21

### ✨ Hinzugefügt (Windows-Unterstützung & Cross-Platform)
- **Nativer Windows-Support:** ViDow läuft vollständig unter Windows 10/11 im eigenen Desktop-Fenster (Microsoft Edge WebView2 / `pywebview`).
- **Starter & Tools:** `ViDow.bat`, `ViDow-NoConsole.vbs`, `create_windows_shortcut.py` und `build_windows_exe.py`.

---

## [1.0.0] - 2026-10-15

### ✨ Initiale Veröffentlichung (macOS)
- Lokaler Video-Downloader & Stream-Sniffer für macOS (`yt-dlp`, `curl-cffi`, `ffmpeg`, `pywebview`) inkl. Browser-Erweiterung.
