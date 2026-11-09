#!/usr/bin/env bash
# Démarre le studio. Options : --hote 0.0.0.0 (réseau local), --port 8765
cd "$(dirname "$0")/.."
[ -f .venv/bin/activate ] && . .venv/bin/activate
exec python -m serveur "$@"
