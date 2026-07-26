"""Assemble the final notes.md file and manage the per-meeting output folder."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import Config
from .transcribe import Transcript


def make_meeting_dir(config: Config, when: Optional[datetime] = None,
                     title: Optional[str] = None) -> Path:
    """Create and return a fresh timestamped folder for one meeting."""
    when = when or datetime.now()
    stamp = when.strftime("%Y-%m-%d_%H-%M-%S")
    name = f"{stamp}_{_slug(title)}" if title else stamp
    path = config.output_path / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _slug(text: str) -> str:
    keep = "".join(c if c.isalnum() or c in " -_" else "" for c in text)
    return "-".join(keep.split()).lower()[:60]


def write_transcript(meeting_dir: Path, transcript: Transcript) -> Path:
    path = meeting_dir / "transcript.txt"
    path.write_text(transcript.as_timestamped() + "\n", encoding="utf-8")
    return path


def write_notes(meeting_dir: Path, notes_markdown: str,
                transcript: Transcript, when: Optional[datetime] = None,
                title: Optional[str] = None) -> Path:
    """Write notes.md combining a header, the model's outline, and metadata."""
    when = when or datetime.now()
    duration = transcript.segments[-1].end if transcript.segments else 0
    header = [
        f"# Meeting Notes — {title or when.strftime('%A, %B %d, %Y')}",
        "",
        f"- **Date:** {when.strftime('%Y-%m-%d %H:%M')}",
        f"- **Duration:** {_fmt_duration(duration)}",
        f"- **Language:** {transcript.language or 'unknown'}",
        f"- **Words:** {len(transcript.text.split())}",
        "",
        "---",
        "",
    ]
    body = notes_markdown.strip()
    footer = [
        "",
        "---",
        "",
        "*Generated locally with Whisper + Ollama. Full transcript in "
        "`transcript.txt`.*",
        "",
    ]
    path = meeting_dir / "notes.md"
    path.write_text("\n".join(header) + body + "\n" + "\n".join(footer),
                    encoding="utf-8")
    return path


def _fmt_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"
