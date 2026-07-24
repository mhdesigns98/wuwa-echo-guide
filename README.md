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
| 1 | Void Thunder | Electro |
| 2 | Gusts of Welkin | Aero |
| 3 | Sierra Gale | Aero |
| 4 | Sound of True Name | Aero |
| 5 | Windward Pilgrimage | Aero |
| 6 | Celestial Light | Spectro |
| 7 | Eternal Radiance | Spectro |
| 8 | Pact of Neonlight Leap | Spectro |
| 9 | Rite of Gilded Revelation | Spectro |
| 10 | Flamewing's Shadow | Fusion |
| 11 | Flaming Clawprint | Fusion |
| 12 | Molten Rift | Fusion |
| 13 | Tidebreaking Courage | Fusion |
| 14 | Trailblazing Star | Fusion |
| 15 | Frosty Resolve | Glacio |
| 16 | Dream of the Lost | Havoc |
| 17 | Midnight Veil | Havoc |
| 18 | Thread of Severed Fate | Havoc |
| 19 | Moonlit Clouds | Support |
| 20 | Rejuvenating Glow | Support |
| 21 | Crown of Valor | Universal |
| 22 | Dream of the Lost + 2pc Havoc | Universal |
| 23 | Emperian Anthem | Universal |
| 24 | Empyrean Anthem | Universal |
| 25 | Halo of Starry Radiance | Support |
| 26 | Law of Harmony + 2pc Aero | Universal |

*(Kept in sync with `data.json` — verify against it if this list looks stale.)*

## How to Use

Just open the site and click any set tab. No account, no login, no install.

👉 **[View the site](https://mhdesigns98.github.io/wuwa-echo-guide/)**

## Updating the Data

All character and set data lives in **`data.json`**. The app fetches it at runtime, so you never need to touch `index.html` to update builds.

The Prydwen scraper pipeline is retired — Prydwen now returns `410 Gone` on
`page-data.json` and Cloudflare blocks direct page scraping. The pipeline has been
archived to `archive/prydwen/` (see that folder's `README.md` for details).

**Scheduled run:** a launchd agent (`com.mhayes.wuwa-refresh`, plist kept at
`scripts/com.mhayes.wuwa-refresh.plist` and installed to `~/Library/LaunchAgents/`)
runs `refresh.py --apply` every **Monday at 9:12am**, appending each dated report to
`logs/refresh-cron.log`. Check that log for new sets/characters to add to the sheet.
Manage it with `launchctl kickstart|bootout gui/$UID/com.mhayes.wuwa-refresh`.
Note: this only updates the local `data.json` — publishing to GitHub Pages/Vercel
is still a manual step.

Refreshing the guide is now a **two-command workflow**, run in order:

### 1. `python3 scripts/refresh.py` — game data (set bonuses, roster)

Pulls sonata set bonuses and detects new sets/characters from
[static.nanoka.cc](https://static.nanoka.cc) (a hakush.in revival, primary source),
falling back to [api.encore.moe](https://api.encore.moe) if nanoka is unreachable.

By default it runs in **report-only mode**: it prints a diff of proposed `setBonus`
changes, plus warnings for new sets, new characters, and missing `mainEcho` values.
Nothing is written to disk unless you pass `--apply`.

```bash
python3 scripts/refresh.py              # dry run: print the diff/report only
python3 scripts/refresh.py --apply      # write approved changes to data.json
python3 scripts/refresh.py --offline    # use cached data, skip network calls
python3 scripts/refresh.py --force-fetch  # ignore cache, re-fetch everything
python3 scripts/refresh.py --source encore  # force the encore.moe fallback
```

Exit codes: `0` clean (no findings), `1` findings pending review, `2` error.

Fetched data is cached under `cache/{version}/`. The cache is disposable — delete it
any time to force a clean re-fetch.

### 2. `python3 scripts/import_sheet.py` — character build recommendations

Merges the curated Google Sheet (the authoritative source for character build
recommendations — main stats, substats, roles) into `data.json`. Supports
`--dry-run` to preview changes before writing.

```bash
python3 scripts/import_sheet.py --dry-run
python3 scripts/import_sheet.py
```

### Why this order

Run `refresh.py` first so any new sonata sets exist in `data.json` before
`import_sheet.py` tries to attach characters to them. **A new set only shows up in
the app once a character in the sheet is assigned to use it** — `refresh.py` alone
will report a new set's existence, but won't make it visible in the UI until
`import_sheet.py` links a character to it.

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

- **Game data** (echo sets, set bonuses, character roster): [static.nanoka.cc](https://static.nanoka.cc) (hakush.in revival), with [api.encore.moe](https://api.encore.moe) as fallback, via `scripts/refresh.py`.
- **Build recommendations** (main stats, substats, roles): curated in the Google Sheet and merged via `scripts/import_sheet.py`. Always verify against the latest guides as the meta shifts with new patches.
- **Prydwen.gg** — *historical.* The original data source; its scraper pipeline is archived in `archive/prydwen/` and is no longer run (endpoint returns `410`, scraping is Cloudflare-blocked).
