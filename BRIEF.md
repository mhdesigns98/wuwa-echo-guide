# WuWa Echo Guide — Update Workflow — Brief
*Written: 2026-07-10*

## Problem / Why
The guide falls behind because refreshing it is unreliable and tedious. The Prydwen
scraper fails silently when page formats change or new characters land — right now
7 characters are stuck (`db/sync_failures.json`: aemeath, cartethyia, denia, hiyuki,
lucilla, rover-havoc, sigrika) — and even when data is available, editing and
verifying `data.json` by hand is enough friction to make updates get put off. The
goal is a workflow that makes a refresh a quick, confident, one-command act when a
new echo set or character drops.

## Audience
Primary: Mark (maintainer). Secondary: site visitors at the public guide who benefit
from it being current. This pass serves the maintainer — reducing the cost and risk
of keeping the guide fresh.

## What done looks like
- **One command** (e.g. `python3 scripts/refresh.py`) runs the whole refresh: scrape
  → merge overrides → diff → report. No always-on infra, run on demand.
- **Fails loudly, not silently.** The run ends with a clear summary: new characters
  detected since last run, characters that failed to scrape, and fields left empty —
  surfaced in the terminal, not buried in a JSON file I have to remember to open.
- **Hybrid source of truth works**: a curated override file (sheet/CSV/JSON) takes
  precedence over scraped values, so I can hand-fix a character without touching or
  waiting on the scraper. The 7 currently-stuck characters are resolvable this way.
- **Review before write/deploy**: the command shows a human-readable diff of proposed
  `data.json` changes and does not deploy. Publishing stays a separate, deliberate step.
- **Proof it works**: after one run, the 7 failing characters are either scraped
  correctly or filled from overrides, and `data.json` validates against the app's
  expected shape (valid elements, cost tiers, substat lists).

## Out of scope (v1)
- **No app redesign** — `index.html` UI/UX is untouched; this is purely the update pipeline.
- **No auto-publishing** — nothing deploys to the live site without explicit review.
- **No new data sources** — Prydwen stays the single scrape source; no Hakush/other wikis this pass.
- **No new data categories** — echo sets + main/substats only; no weapons, teams, or full builds.

## Deploy target & constraints
The app itself is a static single-page HTML + React (CDN), hosted on GitHub Pages and
Vercel, fetching `data.json` at runtime. The workflow tooling is local Python scripts
(`scripts/`) run on Mark's machine — no build step, no server, no scheduled infra.
Output must remain the existing `data.json` shape so the live app keeps working unchanged.

## Content source & maintenance
Hybrid: `sync_prydwen_builds.py` scrapes Prydwen.gg to produce a draft; a curated
override layer (leaning on the existing 2026 Builds sheet/CSV + `import_sheet.py`) is
authoritative and merged on top. Mark curates overrides and runs the refresh; the
merge + diff + validation is automated. Publishing to the live site remains manual.

## Deadline / trigger
None fixed. Natural trigger is each WuWa patch / new echo set or character release —
the workflow should make that moment cheap to act on.

## Open questions
- Override file format: reuse the existing Google Sheet/CSV (`import_sheet.py`) as the
  override layer, or a dedicated `overrides.json`? Which is less friction to curate?
- How should "new character since last run" be detected — diff against current
  `data.json` roster, or maintain a known-roster manifest the scraper checks against?
- Should the refresh command auto-open the diff for review (e.g. write a proposed
  `data.next.json` and print the diff), or edit `data.json` in place behind a `--apply` flag?
- Is the `db/` SQLite step still pulling its weight in a hybrid model, or can the
  pipeline collapse to scrape → merge → export?

## Resolved (2026-07-19)

**Source pivot:** Prydwen scraping is abandoned — `page-data.json` now returns
`410 Gone` and direct page scraping is Cloudflare-blocked, both unfixable on our
side. Game data (sonata set bonuses, roster for new-character detection) now comes
from `https://static.nanoka.cc` (a hakush.in revival, primary source), with
`https://api.encore.moe` as fallback. Build recommendations stay sheet-curated —
no change there.

- **Override file format:** the existing Google Sheet, via `scripts/import_sheet.py`,
  stays the override/authoritative layer for character builds. No new
  `overrides.json` — the sheet already does this job and adding a second file would
  just be a second thing to keep in sync.
- **New-character detection:** compare the character list from the new source
  (nanoka.cc/encore.moe) against the rosters already present in `data.json`, cross-
  checked with `CHARACTER_ELEMENT_MAP`. Anything in the source list that isn't in
  `data.json` (or doesn't map to a known element) is flagged as new/unknown in the
  refresh report.
- **Diff flow:** in-memory terminal diff, no `data.next.json` staging file. `refresh.py`
  computes proposed changes, prints them, and exits 0/1/2 depending on whether
  there's anything to review. `--apply` is required to actually write `data.json`.
- **`db`/SQLite:** archived, not carried forward. With Prydwen scraping gone there's
  no multi-stage extract-then-load need it was serving. The pipeline collapses to
  a single flow: **fetch → match → diff → apply**, implemented in `scripts/refresh.py`.
  The retired scripts and SQLite artifacts live in `archive/prydwen/`.
