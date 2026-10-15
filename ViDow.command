#!/bin/bash
# ViDow — Doppelklick-Starter für macOS
set -e

cd "$(dirname "$0")"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

if [ ! -d ".venv" ]; then
  echo "📦 Erstelle virtuelle Python-Umgebung (.venv)..."
  python3 -m venv .venv
fi

source .venv/bin/activate

if ! python3 -c "import yt_dlp, curl_cffi" >/dev/null 2>&1; then
  echo "⬇️  Installiere yt-dlp & Browser-Impersonation (curl-cffi)..."
  pip install --upgrade pip yt-dlp curl-cffi
fi

echo "🎬 Starte ViDow..."
exec python3 app.py
