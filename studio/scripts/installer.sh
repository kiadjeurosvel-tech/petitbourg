#!/usr/bin/env bash
# Installation du studio (Linux / macOS). Usage : bash scripts/installer.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
$PY -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ requis"'
[ -d .venv ] || $PY -m venv .venv
. .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt || pip install -q fastapi uvicorn numpy pillow
echo
command -v ffmpeg >/dev/null && echo "✓ FFmpeg" || echo "✗ FFmpeg ABSENT — obligatoire (Linux : sudo apt install ffmpeg · macOS : brew install ffmpeg)"
command -v blender >/dev/null || [ -x /Applications/Blender.app/Contents/MacOS/Blender ] && echo "✓ Blender" || echo "! Blender absent — aperçu 2D en attendant (https://www.blender.org/download/)"
command -v espeak-ng >/dev/null && echo "✓ espeak-ng" || echo "! espeak-ng absent (voix de secours) — sudo apt install espeak-ng / brew install espeak-ng"
if [ "$(uname)" = Linux ] && [ -z "${DISPLAY:-}" ] && ! command -v xvfb-run >/dev/null; then
  echo "! Serveur sans écran : installez xvfb pour le rendu EEVEE (sudo apt install xvfb)"
fi
echo
echo "Voix naturelles (Piper) : python scripts/telecharger_voix.py"
echo "Démarrer               : bash scripts/demarrer.sh"
