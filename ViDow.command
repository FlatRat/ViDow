#!/bin/bash
# ViDow — Starter für macOS (Natives Desktop-Fenster)
set -e

cd "$(dirname "$0")"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

if [ ! -d ".venv" ]; then
  echo "📦 Erstelle virtuelle Python-Umgebung (.venv)..."
  python3 -m venv .venv
fi

source .venv/bin/activate

if ! python3 -c "import yt_dlp, curl_cffi, webview" >/dev/null 2>&1; then
  echo "⬇️  Installiere yt-dlp, curl-cffi & pywebview..."
  pip install --upgrade pip yt-dlp curl-cffi pywebview
fi

echo "🎬 Starte ViDow im eigenen macOS-Fenster..."
exec python3 app.py "$@"
