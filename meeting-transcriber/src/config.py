"""Configuration loading with sensible defaults.

Reads ``config.toml`` from the project root if present, otherwise falls back to
the defaults below. Everything is local-only; no keys or remote endpoints beyond
a locally-running Ollama server.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

# tomllib is stdlib on 3.11+; tomli is the backport for older versions.
try:  # pragma: no cover - trivial import shim
    import tomllib  # type: ignore[import-not-found]

    def _load_toml(fh) -> Dict[str, Any]:
        return tomllib.load(fh)
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli  # type: ignore[import-not-found]

        def _load_toml(fh) -> Dict[str, Any]:
            return tomli.load(fh)
    except ModuleNotFoundError:  # pragma: no cover
        def _load_toml(fh) -> Dict[str, Any]:
            raise RuntimeError(
                "No TOML parser available. Use Python 3.11+ or `pip install tomli`."
            )


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.toml"


@dataclass
class Config:
    # --- Audio capture ---
    # macOS avfoundation input device. Can be an index ("2") or a name substring
    # ("Aggregate"). devices.py helps you find this. The recorder resolves names
    # to indices automatically.
    input_device: str = "Aggregate Device"
    sample_rate: int = 16000  # 16 kHz is ideal for Whisper
    channels: int = 1  # mixed down to mono for transcription

    # --- Transcription (faster-whisper) ---
    whisper_model: str = "base"  # tiny/base/small/medium/large-v3
    whisper_compute_type: str = "int8"  # int8 (CPU-friendly) / float16 / auto
    whisper_device: str = "auto"  # auto/cpu/cuda
    language: str | None = None  # None = autodetect; or e.g. "en"

    # --- Summarization (Ollama) ---
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ollama_num_ctx: int = 8192
    # Approx characters per chunk when a transcript is too long for one pass.
    chunk_char_size: int = 9000

    # --- Output ---
    output_dir: str = "~/MeetingNotes"
    open_notes_when_done: bool = True

    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def output_path(self) -> Path:
        return Path(os.path.expanduser(self.output_dir))


def load_config(path: Path | str | None = None) -> Config:
    """Load configuration, layering a TOML file over the defaults."""
    cfg = Config()
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    if not p.exists():
        return cfg

    with p.open("rb") as fh:
        data = _load_toml(fh)

    known = {f for f in cfg.__dataclass_fields__ if f != "extra"}
    for key, value in data.items():
        if key in known:
            setattr(cfg, key, value)
        else:
            cfg.extra[key] = value
    return cfg
