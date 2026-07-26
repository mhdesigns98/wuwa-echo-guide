#!/usr/bin/env bash
# Launch the menu-bar app. A 🎙 icon appears in the macOS menu bar.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "!! No virtual environment found. Run ./setup.sh first."
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# Nudge the user if Ollama isn't reachable (summaries would be skipped).
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "Note: Ollama doesn't seem to be running. Transcripts will still be saved,"
  echo "      but summaries will be skipped. Start it with: ollama serve"
fi

exec python -m src.app
