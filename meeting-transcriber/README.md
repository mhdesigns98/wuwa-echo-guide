# Meeting Transcriber 🎙

A **fully local** macOS menu-bar app that records your meetings, transcribes
them with Whisper, and generates outlined notes with a local LLM (via Ollama).
**Nothing leaves your machine** — no cloud, no API keys, no accounts.

- **Record** mic **+** meeting audio (Zoom/Meet/Teams participants) together
- **Transcribe** locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- **Outline** into Summary / Key Points / Decisions / Action Items / Open
  Questions with a local model through [Ollama](https://ollama.com)
- **Save** each meeting to `~/MeetingNotes/<timestamp>/` as `audio.wav`,
  `transcript.txt`, and `notes.md`

---

## Requirements
- macOS (Apple Silicon or Intel), macOS 12+
- [Homebrew](https://brew.sh)
- ~2–5 GB free for the Whisper + Ollama models

## Quick start
```bash
cd meeting-transcriber
./setup.sh                     # installs ffmpeg, BlackHole, Ollama, Python deps, models
open docs/AUDIO_SETUP.md       # one-time audio routing (≈3 min) — see below
./run.sh                       # 🎙 appears in the menu bar
```
Then: **Start Recording** → have your meeting → **Stop Recording**. A minute or
two later a notification says your notes are ready, and `notes.md` opens.

## The one manual step: audio routing
Capturing *both* your mic and the other participants requires two virtual audio
devices you create once in **Audio MIDI Setup**. It takes about three minutes and
is walked through step-by-step in **[docs/AUDIO_SETUP.md](docs/AUDIO_SETUP.md)**.

> Don't want to bother? Set `input_device` in `config.toml` to just your
> microphone. You'll capture your side only — perfect for in-person meetings or
> dictation.

## Try it without recording
Already have a recording (or want to verify the pipeline)? Process any audio file
headlessly — this also works for confirming transcription/summarization outside
the menu bar:
```bash
source .venv/bin/activate
python -m src.cli /path/to/recording.m4a --title "Weekly Sync"
python -m src.cli recording.wav --no-summary      # transcript only
```

## Configuration
Copy `config.example.toml` → `config.toml` (setup.sh does this) and edit. Common
knobs:

| Setting | Default | Notes |
|---|---|---|
| `whisper_model` | `base` | `tiny`/`base`/`small`/`medium`/`large-v3` — bigger = more accurate, slower |
| `input_device` | `Aggregate Device` | name substring or numeric index; `python -m src.devices` to list |
| `ollama_model` | `llama3.1` | any model you've `ollama pull`ed |
| `output_dir` | `~/MeetingNotes` | where meetings are saved |

## How it works
```
menu bar (rumps)
   │  Start ──▶ ffmpeg records the Aggregate Device ──▶ audio.wav
   │  Stop  ──▶ faster-whisper ──▶ transcript.txt
   │           ──▶ Ollama (map-reduce for long calls) ──▶ notes.md
   ▼
~/MeetingNotes/2026-07-26_14-30-00/
```
Source modules: `recorder.py` (capture), `transcribe.py` (Whisper),
`summarize.py` (Ollama), `notes.py` (file assembly), `app.py` (menu bar),
`cli.py` (headless pipeline), `devices.py` (device listing), `config.py`.

## Troubleshooting
- **"Ollama unavailable" / no summary** — start it: `ollama serve` (the
  transcript is still saved either way).
- **ffmpeg error when recording starts** — wrong device; run
  `python -m src.devices` and set `input_device` to the exact name/index.
- **Only my voice was captured** — system output isn't set to the Multi-Output
  Device; see the audio guide.
- **Slow transcription** — use a smaller `whisper_model`, or on Apple Silicon
  swap in `mlx-whisper` (see below).

## Notes on models
- **faster-whisper** runs on CPU by default (`int8`), which is fine for most
  laptops. On Apple Silicon you can get a big speedup with
  [`mlx-whisper`](https://github.com/ml-explore/mlx-examples/tree/main/whisper) —
  swap the engine inside `transcribe.py`.
- Any Ollama chat model works. `llama3.1` (8B) is a good balance; try
  `qwen2.5:7b` or a larger model if you have the RAM.

## Not included (v1) / ideas for later
- **Speaker labels** (who said what) — needs diarization (pyannote + a Hugging
  Face token) on a separately-recorded track; deliberately left out to keep this
  simple and 100% offline.
- Auto-start when a meeting is detected; in-app note editing; bundling into a
  double-clickable `.app` via [py2app](https://py2app.readthedocs.io).

## Privacy
Audio, transcripts, and notes stay in `~/MeetingNotes` on your Mac. The only
network calls are to `localhost:11434` (your own Ollama) and a one-time model
download during setup. **Recording others may require their consent — check your
local laws and tell participants.**
