#!/usr/bin/env bash
# One-time setup for the local meeting transcriber (macOS).
# Installs system + Python dependencies and pulls the AI models.
set -euo pipefail

cd "$(dirname "$0")"
echo "==> Meeting Transcriber setup"

# --- 1. Homebrew ---
if ! command -v brew >/dev/null 2>&1; then
  echo "!! Homebrew is required. Install it from https://brew.sh and re-run."
  exit 1
fi

# --- 2. System dependencies ---
echo "==> Installing ffmpeg, BlackHole, and Ollama via Homebrew…"
brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg
brew list blackhole-2ch >/dev/null 2>&1 || brew install --cask blackhole-2ch
brew list ollama >/dev/null 2>&1 || brew install ollama

# --- 3. Python virtualenv ---
echo "==> Creating Python virtual environment (.venv)…"
PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
  echo "!! python3 not found. Install it (brew install python) and re-run."
  exit 1
fi
"$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
echo "==> Installing Python dependencies…"
pip install --quiet -r requirements.txt

# --- 4. Config ---
if [ ! -f config.toml ]; then
  cp config.example.toml config.toml
  echo "==> Created config.toml (edit it to taste)."
fi

# --- 5. Models ---
echo "==> Starting Ollama and pulling the summary model…"
# Start a background server if one isn't already running.
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
  ollama serve >/tmp/ollama.log 2>&1 &
  sleep 3
fi
OLLAMA_MODEL="$(grep -E '^ollama_model' config.toml | sed -E 's/.*"(.*)".*/\1/' || echo llama3.1)"
ollama pull "${OLLAMA_MODEL:-llama3.1}"

echo "==> Warming up the Whisper model (downloads on first use)…"
python - <<'PY'
from src.config import load_config
try:
    from faster_whisper import WhisperModel
    cfg = load_config()
    WhisperModel(cfg.whisper_model, device=cfg.whisper_device,
                 compute_type=cfg.whisper_compute_type)
    print(f"Whisper model '{cfg.whisper_model}' ready.")
except Exception as e:
    print(f"(Whisper will download on first run) {e}")
PY

cat <<'EOF'

==> Setup complete.

Next steps:
  1. Create the Aggregate + Multi-Output audio devices — see docs/AUDIO_SETUP.md
     (one-time, ~3 minutes). This is what lets you capture BOTH your mic and the
     meeting audio while still hearing the call.
  2. Make sure Ollama is running:   ollama serve   (or the menu-bar Ollama app)
  3. Launch the app:                ./run.sh

Tip: verify the core pipeline on any existing recording first:
     source .venv/bin/activate
     python -m src.cli /path/to/some-recording.m4a
EOF
