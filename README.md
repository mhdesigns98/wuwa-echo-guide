# WuWa Echo Set Guide

A lightweight, single-page reference tool for Wuthering Waves echo farming. Select an echo set and instantly see every character that uses it, their recommended main stats for each echo cost tier, and substat priorities — so you always know what to keep or discard.

## What It Shows

For each echo set you get:

- **Set bonus** summary and the recommended **main echo** to slot
- Every character that uses the set, with:
  - **4-cost, 3-cost, and 1-cost main stat** recommendations (with alternates where applicable)
  - **Priority substats** in order, including Energy Regen targets where relevant
  - Character element and role (Main DPS, Sub-DPS, Support, Healer, etc.)

## Sets Included

| # | Set | Element |
|---|-----|---------|
| 1 | Freezing Frost | Glacio |
| 2 | Molten Rift | Fusion |
| 3 | Void Thunder | Electro |
| 4 | Sierra Gale | Aero |
| 5 | Celestial Light | Spectro |
| 6 | Sun-sinking Eclipse | Havoc |
| 7 | Rejuvenating Glow | Support |
| 8 | Moonlit Clouds | Support |
| 9 | Lingering Tunes | Universal |
| 10 | Midnight Veil | Havoc |
| 11 | Empyrean Anthem | Universal |
| 12 | Eternal Radiance | Spectro |
| 13 | Frosty Resolve | Glacio |
| 14 | Tidebreaking Courage | Universal |
| 15 | Gusts of Welkin | Aero |
| 16 | Windward Pilgrimage | Aero |
| 17 | Flaming Clawprint | Fusion |
| 18 | Crown of Valor | Universal |
| 19 | Dream of the Lost | Havoc |
| 20 | Flamewing's Shadow | Fusion |
| 21 | Law of Harmony | Aero |
| 22 | Thread of Severed Fate | Havoc |
| 23 | Halo of Starry Radiance | Support |
| 24 | Pact of Neonlight Leap | Spectro |
| 25 | Rite of Gilded Revelation | Spectro |

## How to Use

Just open the site and click any set tab. No account, no login, no install.

👉 **[View the site](https://mhdesigns98.github.io/wuwa-echo-guide/)**

## Updating the Data

All character and set data lives in **`data.json`**. The app fetches it at runtime, so you never need to touch `index.html` to update builds.

## Database Pipeline (Prydwen Source)

If you want to build this out as a real database (instead of only a front-end JSON file), there is now a starter pipeline:

- `db/schema.sql` - normalized SQLite schema for echo sets, characters, and character/set build links.
- `scripts/sync_prydwen_builds.py` - pulls character pages from Prydwen and extracts:
  - best echo sets
  - recommended 4/3/1-cost stats
  - recommended substats
- `scripts/build_sqlite.py` - loads the synced JSON into SQLite.
- `scripts/export_app_data.py` - converts synced data into the current app `data.json` structure.

### Run it

From `wuwa-echo-guide`:

```bash
python3 scripts/sync_prydwen_builds.py
python3 scripts/build_sqlite.py
python3 scripts/export_app_data.py
```

This writes:

- `db/prydwen_character_builds.json`
- `db/wuwa_echoes.sqlite`
- `data.prydwen.json`

### Quick test run

To test on only a few characters first:

```bash
python3 scripts/sync_prydwen_builds.py --limit 5
python3 scripts/build_sqlite.py
```

### Notes

- The extractor is intentionally conservative and targets the core data you asked for (echo sets, best-with characters, and substats).
- Prydwen page structure can change over time, so validate a few records after each patch cycle.
- Respect Prydwen's terms of use when pulling data.

### Adding or editing a character

Open `data.json` and find the set you want to update. Each character follows this structure:

```json
{
  "name": "Jiyan",
  "element": "Aero",
  "role": "Main DPS",
  "costs": {
    "4": ["Crit DMG", "Crit Rate"],
    "3": ["Aero DMG%"],
    "1": ["ATK%"]
  },
  "substats": ["Energy Regen (25%)", "Crit Rate/DMG", "ATK%", "Heavy ATK Bonus"]
}
```

- `costs` — list stats in priority order. First entry is the primary recommendation, additional entries appear as "or" alternatives.
- `substats` — list in priority order. The first entry is highlighted as the top priority.

### Adding a new set

Copy an existing set block and update the fields:

```json
{
  "id": "my-new-set",
  "name": "My New Set",
  "element": "Fusion",
  "setBonus": "2pc: Fusion DMG +10%  |  5pc: ...",
  "mainEcho": "Echo Name",
  "characters": []
}
```

Valid `element` values: `Electro`, `Aero`, `Spectro`, `Fusion`, `Glacio`, `Havoc`, `Support`, `Universal`

### Quickest way to update on GitHub

1. Open `data.json` in the repo
2. Click the **pencil icon** to edit
3. Make your changes
4. Click **Commit changes**

The site updates within ~30 seconds. No build step, no terminal needed.

## Tech

- Plain HTML + React (loaded via CDN) — no build tools, no dependencies to install
- `data.json` is fetched at runtime, keeping data separate from the app
- Hosted for free on GitHub Pages

## Data Source

Build recommendations sourced from [Prydwen.gg](https://www.prydwen.gg/wuthering-waves). Always verify against the latest guides as the meta shifts with new patches.
