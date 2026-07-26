"""Local transcription using faster-whisper.

Runs entirely offline once the model is downloaded (cached under
~/.cache/huggingface). Exposes both a library function and a small CLI so the
pipeline can be exercised without the menu bar:

    python -m src.transcribe audio.wav --model base
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .config import Config, load_config


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class Transcript:
    text: str
    segments: List[Segment]
    language: Optional[str] = None

    def as_timestamped(self) -> str:
        """Human-readable transcript with [mm:ss] markers per segment."""
        lines = []
        for seg in self.segments:
            lines.append(f"[{_fmt_ts(seg.start)}] {seg.text.strip()}")
        return "\n".join(lines)


def _fmt_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"


def transcribe(audio_path: Path | str, config: Optional[Config] = None,
               progress=None) -> Transcript:
    """Transcribe an audio file locally. `progress` is an optional callback(str)."""
    config = config or load_config()
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    try:
        from faster_whisper import WhisperModel
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "faster-whisper is not installed. Run: pip install faster-whisper"
        ) from exc

    if progress:
        progress(f"Loading Whisper model '{config.whisper_model}'…")
    model = WhisperModel(
        config.whisper_model,
        device=config.whisper_device,
        compute_type=config.whisper_compute_type,
    )

    if progress:
        progress("Transcribing…")
    segments_iter, info = model.transcribe(
        str(audio_path),
        language=config.language,
        vad_filter=True,  # skip long silences → faster, cleaner transcript
    )

    segments: List[Segment] = []
    for seg in segments_iter:
        segments.append(Segment(start=seg.start, end=seg.end, text=seg.text))
        if progress:
            progress(f"  [{_fmt_ts(seg.end)}] transcribed…")

    full_text = " ".join(s.text.strip() for s in segments).strip()
    return Transcript(text=full_text, segments=segments,
                      language=getattr(info, "language", None))


def _main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe an audio file locally.")
    parser.add_argument("audio", help="Path to an audio file (wav/m4a/mp3…)")
    parser.add_argument("--model", help="Whisper model size override")
    parser.add_argument("--language", help="Force a language code (e.g. en)")
    parser.add_argument("--timestamps", action="store_true",
                        help="Print timestamped segments instead of plain text")
    args = parser.parse_args()

    config = load_config()
    if args.model:
        config.whisper_model = args.model
    if args.language:
        config.language = args.language

    transcript = transcribe(args.audio, config, progress=lambda m: print(m))
    print("\n--- Transcript ---\n")
    print(transcript.as_timestamped() if args.timestamps else transcript.text)


if __name__ == "__main__":
    _main()
