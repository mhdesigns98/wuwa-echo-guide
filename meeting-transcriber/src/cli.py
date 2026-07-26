"""Headless pipeline: turn an existing audio file into transcript + notes.

    python -m src.cli path/to/meeting.m4a
    python -m src.cli meeting.wav --title "Weekly Sync" --no-summary

Useful for processing recordings you already have, and for verifying the
transcribe→summarize pipeline without the menu bar or live audio capture.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from .config import load_config
from .notes import make_meeting_dir, write_notes, write_transcript
from .summarize import OllamaError, summarize
from .transcribe import transcribe


def process_file(audio_path: str, title: str | None = None,
                 do_summary: bool = True, config=None) -> Path:
    config = config or load_config()

    def log(msg: str) -> None:
        print(msg, flush=True)

    when = datetime.now()
    meeting_dir = make_meeting_dir(config, when=when, title=title)
    log(f"Output folder: {meeting_dir}")

    transcript = transcribe(audio_path, config, progress=log)
    tpath = write_transcript(meeting_dir, transcript)
    log(f"Wrote {tpath}")

    if do_summary:
        try:
            notes_md = summarize(transcript.text, config, progress=log)
            npath = write_notes(meeting_dir, notes_md, transcript,
                                when=when, title=title)
            log(f"Wrote {npath}")
        except OllamaError as exc:
            log(f"\n[!] Skipping summary: {exc}")
            log("    The transcript was still saved.")

    return meeting_dir


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Transcribe an audio file and generate meeting notes locally.")
    parser.add_argument("audio", help="Path to an audio file (wav/m4a/mp3…)")
    parser.add_argument("--title", help="Optional meeting title")
    parser.add_argument("--no-summary", action="store_true",
                        help="Only transcribe; skip the Ollama outline")
    parser.add_argument("--model", help="Whisper model size override")
    args = parser.parse_args()

    config = load_config()
    if args.model:
        config.whisper_model = args.model

    meeting_dir = process_file(
        args.audio, title=args.title,
        do_summary=not args.no_summary, config=config,
    )
    print(f"\nDone. See: {meeting_dir}")


if __name__ == "__main__":
    _main()
