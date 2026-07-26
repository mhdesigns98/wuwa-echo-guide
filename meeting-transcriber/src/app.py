"""macOS menu-bar app for recording, transcribing, and outlining meetings.

Built with `rumps`. Runs the transcription/summarization on a background thread
so the menu bar stays responsive. Launch it with `./run.sh` (or `python -m
src.app`); a 🎙 icon appears in the menu bar.

Menu:
    Start Recording / Stop Recording
    Status line (recording time / progress)
    Open Notes Folder
    Choose Input Device ▸  (lists avfoundation devices)
    Quit
"""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

try:
    import rumps
except ModuleNotFoundError:  # pragma: no cover
    raise SystemExit(
        "rumps is not installed (macOS only). Run: pip install rumps"
    )

from .config import load_config
from .devices import list_input_devices
from .notes import make_meeting_dir, write_notes, write_transcript
from .recorder import Recorder, RecorderError
from .summarize import OllamaError, summarize
from .transcribe import transcribe

IDLE_TITLE = "🎙"
REC_TITLE = "🔴"
BUSY_TITLE = "⏳"


class MeetingApp(rumps.App):
    def __init__(self) -> None:
        super().__init__(IDLE_TITLE, quit_button=None)
        self.config = load_config()
        self.recorder = Recorder(self.config)
        self._meeting_dir: Path | None = None
        self._when: datetime | None = None
        self._timer = rumps.Timer(self._tick, 1)

        self.record_item = rumps.MenuItem("Start Recording", callback=self.toggle)
        self.status_item = rumps.MenuItem("Idle")
        self.status_item.set_callback(None)  # non-clickable label

        self.menu = [
            self.record_item,
            self.status_item,
            None,
            rumps.MenuItem("Open Notes Folder", callback=self.open_folder),
            self._build_device_menu(),
            None,
            rumps.MenuItem("Quit", callback=self.quit),
        ]

    # ---- Device selection submenu ----
    def _build_device_menu(self) -> rumps.MenuItem:
        menu = rumps.MenuItem("Input Device")
        try:
            devices = list_input_devices()
        except Exception:
            devices = []
        if not devices:
            menu.add(rumps.MenuItem("(no devices found)", callback=None))
            return menu
        for idx, name in devices:
            item = rumps.MenuItem(f"{name}", callback=self._pick_device)
            item.state = 1 if self._matches_current(idx, name) else 0
            item._device_index = idx  # type: ignore[attr-defined]
            menu.add(item)
        return menu

    def _matches_current(self, idx: int, name: str) -> bool:
        cur = str(self.config.input_device).strip().lower()
        return cur == str(idx) or cur in name.lower()

    def _pick_device(self, sender: rumps.MenuItem) -> None:
        self.config.input_device = str(getattr(sender, "_device_index"))
        # Check the chosen device, uncheck its siblings.
        parent = self.menu["Input Device"]
        for key in parent:
            parent[key].state = 1 if parent[key] is sender else 0
        rumps.notification("Meeting Transcriber", "Input device set", sender.title)

    # ---- Recording control ----
    def toggle(self, _sender) -> None:
        if self.recorder.is_recording:
            self._stop()
        else:
            self._start()

    def _start(self) -> None:
        self._when = datetime.now()
        self._meeting_dir = make_meeting_dir(self.config, when=self._when)
        audio_path = self._meeting_dir / "audio.wav"
        try:
            self.recorder.start(audio_path)
        except RecorderError as exc:
            rumps.alert("Could not start recording", str(exc))
            return
        self.title = REC_TITLE
        self.record_item.title = "Stop Recording"
        self.status_item.title = "Recording 0:00"
        self._timer.start()

    def _stop(self) -> None:
        self._timer.stop()
        try:
            audio_path = self.recorder.stop()
        except RecorderError as exc:
            rumps.alert("Recording error", str(exc))
            self._reset_idle()
            return
        self.title = BUSY_TITLE
        self.record_item.title = "Start Recording"
        self.record_item.set_callback(None)  # disable while processing
        self.status_item.title = "Processing…"
        threading.Thread(target=self._process, args=(audio_path,),
                         daemon=True).start()

    def _process(self, audio_path: Path) -> None:
        """Runs on a background thread: transcribe → summarize → write files."""
        def status(msg: str) -> None:
            self.status_item.title = msg[:40]

        meeting_dir = self._meeting_dir or audio_path.parent
        try:
            transcript = transcribe(audio_path, self.config, progress=status)
            write_transcript(meeting_dir, transcript)

            summary_ok = True
            try:
                status("Summarizing…")
                notes_md = summarize(transcript.text, self.config, progress=status)
                write_notes(meeting_dir, notes_md, transcript, when=self._when)
            except OllamaError as exc:
                summary_ok = False
                rumps.notification(
                    "Transcript saved (no summary)",
                    "Ollama unavailable", str(exc))

            if summary_ok:
                rumps.notification(
                    "Meeting notes ready", meeting_dir.name,
                    "Click 'Open Notes Folder' to view.")
                if self.config.open_notes_when_done:
                    _reveal(meeting_dir / "notes.md")
        except Exception as exc:  # keep the app alive on any failure
            rumps.notification("Processing failed", type(exc).__name__, str(exc))
        finally:
            self._reset_idle()

    def _reset_idle(self) -> None:
        self.title = IDLE_TITLE
        self.record_item.title = "Start Recording"
        self.record_item.set_callback(self.toggle)
        self.status_item.title = "Idle"

    def _tick(self, _timer) -> None:
        secs = int(self.recorder.elapsed_seconds)
        m, s = divmod(secs, 60)
        self.status_item.title = f"Recording {m}:{s:02d}"

    # ---- Misc menu actions ----
    def open_folder(self, _sender) -> None:
        self.config.output_path.mkdir(parents=True, exist_ok=True)
        _reveal(self.config.output_path)

    def quit(self, _sender) -> None:
        if self.recorder.is_recording:
            try:
                self.recorder.stop()
            except RecorderError:
                pass
        rumps.quit_application()


def _reveal(path: Path) -> None:
    import subprocess
    subprocess.run(["open", str(path)], check=False)


def main() -> None:
    MeetingApp().run()


if __name__ == "__main__":
    main()
