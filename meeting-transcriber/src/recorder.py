"""Audio capture via an ffmpeg subprocess reading a macOS avfoundation device.

Usage::

    rec = Recorder(config)
    rec.start(Path("audio.wav"))
    ...
    rec.stop()

The recorder writes a 16 kHz mono WAV, which is exactly what Whisper wants.
Start/stop is done by launching ffmpeg and later sending it 'q' on stdin so it
finalizes the file cleanly (a hard kill can truncate the WAV header).
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from .config import Config
from .devices import resolve_device_index


class RecorderError(RuntimeError):
    pass


class Recorder:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._proc: subprocess.Popen | None = None
        self._output: Path | None = None
        self._started_at: float | None = None

    @property
    def is_recording(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    @property
    def elapsed_seconds(self) -> float:
        if self._started_at is None:
            return 0.0
        return time.monotonic() - self._started_at

    def start(self, output: Path) -> None:
        if self.is_recording:
            raise RecorderError("Already recording.")

        index = resolve_device_index(self.config.input_device)
        output.parent.mkdir(parents=True, exist_ok=True)

        # ":<index>" means "no video input, audio input <index>".
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-f", "avfoundation",
            "-i", f":{index}",
            "-ac", str(self.config.channels),
            "-ar", str(self.config.sample_rate),
            "-y",
            str(output),
        ]
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as exc:  # ffmpeg missing
            raise RecorderError(
                "ffmpeg not found. Install it with: brew install ffmpeg"
            ) from exc

        # Give ffmpeg a moment; if it dies immediately the device is wrong or busy.
        time.sleep(0.4)
        if self._proc.poll() is not None:
            err = (self._proc.stderr.read().decode(errors="replace")
                   if self._proc.stderr else "")
            self._proc = None
            raise RecorderError(f"ffmpeg failed to start recording:\n{err.strip()}")

        self._output = output
        self._started_at = time.monotonic()

    def stop(self, timeout: float = 10.0) -> Path:
        """Stop recording and return the finalized output path."""
        if self._proc is None:
            raise RecorderError("Not recording.")

        proc, output = self._proc, self._output
        try:
            # Ask ffmpeg to quit gracefully so the WAV is finalized.
            if proc.poll() is None and proc.stdin:
                try:
                    proc.stdin.write(b"q")
                    proc.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
        finally:
            self._proc = None
            self._started_at = None
            self._output = None

        if output is None or not output.exists():
            raise RecorderError("Recording stopped but no output file was produced.")
        return output
