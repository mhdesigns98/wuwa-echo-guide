# Audio Setup — Capturing Mic + Meeting Audio (macOS)

To record **both** your voice and the other participants, macOS needs two
virtual devices, created once in **Audio MIDI Setup**. `setup.sh` already
installed the **BlackHole 2ch** driver; this guide wires it up.

The idea:

- An **Aggregate Device** = your microphone **+** BlackHole. The app records
  from this, so it hears *you* (mic) and *the meeting* (routed into BlackHole).
- A **Multi-Output Device** = your speakers/headphones **+** BlackHole. You set
  this as system output so the meeting audio goes into BlackHole (for recording)
  **and** to your ears (so you can still hear the call).

```
 Meeting app ──▶ Multi-Output ──┬──▶ Speakers/Headphones (you hear it)
                                └──▶ BlackHole ──┐
 Your mic ──────────────────────────────────────┤
                                                 ▼
                                          Aggregate Device ──▶ this app records
```

---

## Step 1 — Open Audio MIDI Setup
Press **⌘ + Space**, type **Audio MIDI Setup**, open it. You'll see a list of
audio devices on the left. (You should see **BlackHole 2ch** in the list. If not,
re-run `brew install --cask blackhole-2ch` and reboot.)

## Step 2 — Create the Aggregate Device (what the app records)
1. Click the **+** at the bottom-left → **Create Aggregate Device**.
2. Rename it to **Aggregate Device** (double-click its name). *If you pick a
   different name, set `input_device` in `config.toml` to match.*
3. In the right-hand list, tick the **Use** checkbox for:
   - your **microphone** (e.g. "MacBook Pro Microphone" or your USB mic), and
   - **BlackHole 2ch**.
4. Set your microphone as the **Clock Source** (dropdown, top-right) and enable
   **Drift Correction** on BlackHole.

## Step 3 — Create the Multi-Output Device (so you still hear the meeting)
1. Click **+** again → **Create Multi-Output Device**.
2. Tick **Use** for:
   - your **speakers/headphones** (e.g. "MacBook Pro Speakers"), and
   - **BlackHole 2ch**.
3. Put your **speakers/headphones first** (top) and enable **Drift Correction**
   on BlackHole.

## Step 4 — Route system sound through the Multi-Output
When you're about to record a meeting:
- Open **System Settings ▸ Sound ▸ Output** and choose your **Multi-Output
  Device**. (Or ⌥-click the menu-bar volume icon to switch quickly.)
- Leave the meeting app's own speaker set to "System Default".

> Volume note: a Multi-Output Device ignores the volume keys. Set a comfortable
> level **before** switching to it, or control volume inside the meeting app.

## Step 5 — Point the transcriber at the Aggregate Device
- Run `python -m src.devices` to list devices and confirm the name/index.
- Ensure `config.toml` has `input_device = "Aggregate Device"` (the default), or
  pick it live from the app's **Input Device** submenu.

---

## Quick test
1. Set **Output** to the Multi-Output Device.
2. `./run.sh` → **Start Recording**.
3. Say a sentence, then play ~15s of a YouTube video (simulating a participant).
4. **Stop Recording**. Open the notes folder — the transcript should contain both
   your sentence and the video's speech.

## Troubleshooting
- **Only your voice is captured** → System Output isn't set to the Multi-Output
  Device, or BlackHole isn't ticked in the Aggregate Device.
- **You can't hear the meeting** → your speakers aren't ticked (or not first) in
  the Multi-Output Device.
- **ffmpeg error on start / echo** → wrong `input_device`; run
  `python -m src.devices` and set the exact name or index.
- **Simplest fallback** → set `input_device` to just your microphone. You'll only
  capture your side (fine for in-person meetings or dictation).
