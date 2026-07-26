"""List and resolve macOS avfoundation audio input devices via ffmpeg.

`ffmpeg -f avfoundation -list_devices true -i ""` prints devices to stderr in a
block like::

    [AVFoundation indev @ 0x...] AVFoundation audio devices:
    [AVFoundation indev @ 0x...] [0] MacBook Pro Microphone
    [AVFoundation indev @ 0x...] [1] BlackHole 2ch
    [AVFoundation indev @ 0x...] [2] Aggregate Device

We parse the audio section into (index, name) pairs.
"""

from __future__ import annotations

import re
import subprocess
from typing import List, Tuple

_AUDIO_HEADER = "AVFoundation audio devices:"
_DEVICE_RE = re.compile(r"\[(\d+)\]\s+(.*)$")


def list_input_devices() -> List[Tuple[int, str]]:
    """Return a list of (index, name) audio input devices. macOS only."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-f", "avfoundation",
         "-list_devices", "true", "-i", ""],
        capture_output=True,
        text=True,
    )
    # ffmpeg exits non-zero because no real input was opened; output is on stderr.
    lines = proc.stderr.splitlines()

    devices: List[Tuple[int, str]] = []
    in_audio = False
    for line in lines:
        if _AUDIO_HEADER in line:
            in_audio = True
            continue
        if in_audio and "devices:" in line and _AUDIO_HEADER not in line:
            # Reached the next section (e.g. video), stop.
            break
        if in_audio:
            m = _DEVICE_RE.search(line)
            if m:
                devices.append((int(m.group(1)), m.group(2).strip()))
    return devices


def resolve_device_index(device: str) -> int:
    """Resolve a device spec (numeric index or name substring) to an index.

    Raises ValueError if it cannot be resolved.
    """
    device = str(device).strip()
    if device.isdigit():
        return int(device)

    devices = list_input_devices()
    # Exact (case-insensitive) match first, then substring.
    for idx, name in devices:
        if name.lower() == device.lower():
            return idx
    for idx, name in devices:
        if device.lower() in name.lower():
            return idx

    available = ", ".join(f"[{i}] {n}" for i, n in devices) or "(none found)"
    raise ValueError(
        f"Could not find audio input device matching '{device}'. "
        f"Available: {available}"
    )


def _main() -> None:
    try:
        devices = list_input_devices()
    except FileNotFoundError:
        raise SystemExit("ffmpeg not found. Install it with: brew install ffmpeg")
    if not devices:
        print("No audio input devices found (this only works on macOS).")
        return
    print("Audio input devices:")
    for idx, name in devices:
        print(f"  [{idx}] {name}")


if __name__ == "__main__":
    _main()
