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

## Two Ways to Browse

- **By set** (`index.html`) — click any set tab to see every character that uses it.
- **My Roster** (`roster.html`) — select the characters you own and instantly see
  which echo sets are worth keeping and which are safe to discard. Your selection is
  saved in the browser. The two pages cross-link in the header.

## How to Use

Just open the site — no account, no login, no install.

👉 **[View the site](https://wuwa-echo-guide.mikehayesdesign.workers.dev/)**

## Updating the Data

All character and set data lives in **`data.json`**. The app fetches it at runtime, so you never need to touch `index.html` or `roster.html` to update builds.

**The easy loop:** edit the Google Sheet → run the two scripts below → `git push`.
Cloudflare auto-deploys within ~10 seconds. The Google Sheet is the source of truth for
build recommendations — edit it from any browser; the local CSV is only a fallback.

> ⚠️ **The sheet is authoritative and destructive.** On merge, any character in
> `data.json` that is *not* in the sheet gets **purged**. Keep the sheet as your full
> roster, not just a diff.

The Prydwen scraper pipeline is retired — Prydwen now returns `410 Gone` on
`page-data.json` and Cloudflare blocks direct page scraping. The pipeline has been
archived to `archive/prydwen/` (see that folder's `README.md` for details).

**Scheduled run:** a launchd agent (`com.mhayes.wuwa-refresh`, plist kept at
`scripts/com.mhayes.wuwa-refresh.plist` and installed to `~/Library/LaunchAgents/`)
runs `refresh.py --apply` every **Monday at 9:12am**, appending each dated report to
`logs/refresh-cron.log`. Check that log for new sets/characters to add to the sheet.
Manage it with `launchctl kickstart|bootout gui/$UID/com.mhayes.wuwa-refresh`.
Note: this only updates the local `data.json` — publishing is a separate step
(`git push`, which Cloudflare then auto-deploys).

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

### Alternate sets

A character can be viable in a second echo set. Add it in the **`Secondary Echo Set`**
column (one row per character — no extra rows needed). On import:

- the **primary** entry gets `alts: [{ set, label }]`,
- the **secondary** set gets an `alt`-tagged copy of the build (`alt: true`,
  `build: "Alt"`, `primarySet: "<name>"`) so the character also appears under it.
- a **bare element** in that column (e.g. `Aero`) is treated as a 2pc filler and shown
  as an *"also viable: 2pc Aero"* note rather than a real set.

Element is auto-detected from the `3-Cost Main` column (the element for DPS), falling
back to `CHARACTER_ELEMENT_MAP` then `Universal` — so new characters usually need no
code change.

On the **My Roster** page, only the **primary** set counts toward what you keep/farm
(so the checklist stays lean); alternates show up as an *"Also viable"* note and, on a
set that's someone else's primary, as an `ALT`-tagged character chip. On **Browse by
Set**, alternate appearances carry an `ALT · <label>` badge and a `Primary set:` line.

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

### Publishing changes

The repo is Git-connected to Cloudflare, so publishing is just:

```bash
git add -A
git commit -m "Update builds"
git push
```

Cloudflare rebuilds and deploys automatically within ~10 seconds. No build step to
configure. (You can also edit `data.json` directly on GitHub via the pencil icon and
commit — the same auto-deploy fires — but the scripted sheet workflow above is the
maintained path.)

## Tech

- Plain HTML + React (loaded via CDN) — no build tools, no dependencies to install
- `index.html` (browse by set) + `roster.html` (keep/discard by owned characters)
- `data.json` is fetched at runtime, keeping data separate from the app
- Custom headers via Cloudflare `_headers` (security headers + `data.json` caching)
- Hosted on **Cloudflare** (Git-connected, auto-deploy on push) at
  <https://wuwa-echo-guide.mikehayesdesign.workers.dev/>

## Data Source

- **Game data** (echo sets, set bonuses, character roster): [static.nanoka.cc](https://static.nanoka.cc) (hakush.in revival), with [api.encore.moe](https://api.encore.moe) as fallback, via `scripts/refresh.py`.
- **Build recommendations** (main stats, substats, roles): curated in the Google Sheet and merged via `scripts/import_sheet.py`. Always verify against the latest guides as the meta shifts with new patches.
- **Echo set emblem images** (`assets/sets/*.webp`, shown on the My Roster page): the
  per-set icons from the [Wuthering Waves Fandom wiki](https://wutheringwaves.fandom.com/wiki/Sonata)
  (content under CC BY-SA), self-hosted so there's no runtime dependency on Fandom.
  Re-fetch or add new-set images with `python3 scripts/fetch_set_images.py` (idempotent;
  falls back to a CSS element emblem for any set without an image).
- **Prydwen.gg** — *historical.* The original data source; its scraper pipeline is archived in `archive/prydwen/` and is no longer run (endpoint returns `410`, scraping is Cloudflare-blocked).
