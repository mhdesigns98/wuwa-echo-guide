# Archived: Prydwen Scraper Pipeline

**Archived 2026-07-19.**

This directory holds the original Prydwen-based data pipeline, retired because
Prydwen.gg is no longer scrapable:

- `page-data.json` (the endpoint the scraper relied on) now returns **HTTP 410 Gone**.
- Direct page scraping is blocked by **Cloudflare** bot protection.

Both failure modes are on Prydwen's side and outside this project's control, so the
pipeline was archived rather than patched further.

## What's here

- `sync_prydwen_builds.py` — scraped character pages from Prydwen and extracted echo
  sets, main stats, and substats.
- `build_sqlite.py` — loaded the synced JSON into a SQLite database.
- `export_app_data.py` — converted synced data into the app's `data.json` shape.
- `db/` — the SQLite database, schema, and synced JSON this pipeline produced
  (`wuwa_echoes.sqlite`, `schema.sql`, `prydwen_character_builds.json`,
  `sync_failures.json`).
- `data.prydwen.json` — the last successful export from this pipeline.

## What replaced it

- **`scripts/refresh.py`** — pulls game data (sonata set bonuses, new-set/new-character
  detection) from `https://static.nanoka.cc` (hakush.in revival, primary), with
  `https://api.encore.moe` as fallback. Produces a terminal diff report; writes
  `data.json` only with `--apply`.
- **`scripts/import_sheet.py`** — unchanged; still merges curated character build
  recommendations from the Google Sheet on top of the set data `refresh.py` produces.

See the root `README.md` ("Updating the Data") for the current workflow, and
`BRIEF.md` ("Resolved (2026-07-19)") for the reasoning behind the pivot.

This directory is kept for reference only — nothing here is run as part of the
current workflow.
