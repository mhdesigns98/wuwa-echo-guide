#!/usr/bin/env python3
"""
Download per-set echo (sonata) emblem images for the guide.

Source: the Wuthering Waves Fandom wiki. Each sonata set has a `File:Icon_<Set Name>.png`
that the MediaWiki API resolves to a static.wikia.nocookie.net URL (usually served as
webp). We self-host these under assets/sets/ so the app has no runtime dependency on
Fandom and they ride Cloudflare's CDN.

Usage:
    python3 scripts/fetch_set_images.py            # download missing images
    python3 scripts/fetch_set_images.py --force    # re-download everything

Idempotent: skips a set if any assets/sets/<id>.<ext> already exists (unless --force).
Prints a summary of downloaded / skipped / missing sets at the end.

Naming: files are saved as assets/sets/<set.id>.<ext>, where <ext> matches the actual
returned content-type (.webp for most, .png/.jpg otherwise). The app (roster.html)
tries .webp then .png, then falls back to a CSS element emblem, so mixed extensions and
missing images both degrade gracefully.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data.json")
OUT_DIR = os.path.join(ROOT, "assets", "sets")
API = "https://wutheringwaves.fandom.com/api.php"
UA = "wuwa-echo-guide/1.0 (personal static site; set-icon fetch)"

# Sets whose data.json name doesn't map cleanly to a Fandom file title.
# Composite variants ("X + 2pc Y") use their base set's icon; "Emperian" is a typo of
# the in-game "Empyrean".
NAME_OVERRIDES = {
    "Emperian Anthem": "Empyrean Anthem",
    "Dream of the Lost + 2pc Havoc": "Dream of the Lost",
    "Law of Harmony + 2pc Aero": "Law of Harmony",
}

EXT_BY_TYPE = {"image/webp": ".webp", "image/png": ".png", "image/jpeg": ".jpg"}

# Sets referenced by curators/reference sheets but not yet in data.json. Pre-staging
# their emblems means they display the moment a character is assigned to them in the
# sheet. Slug MUST match import_sheet.py's rule (see slugify) so the ids line up.
EXTRA_SETS = [
    "Freezing Frost", "Chromatic Foam", "Havoc Eclipse", "Sun-sinking Eclipse",
    "Wishes of Quiet Snowfall", "Lingering Tunes", "Law of Harmony",
    "Song of Feathered Trace", "Heart of Evil's Purge", "Lamp of Nether Road",
    "Reel of Spliced Memories", "Shadow of Shattered Dreams",
]


def slugify(name):
    """Mirror import_sheet.py's set-id slug so pre-staged image filenames align."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def file_title(set_name):
    """data.json set name -> Fandom 'File:Icon_...png' title."""
    base = NAME_OVERRIDES.get(set_name, set_name)
    if " + " in base:  # any un-overridden composite -> base set
        base = base.split(" + ")[0]
    return "File:Icon_" + base.replace(" ", "_") + ".png"


def api_get(params):
    params = {**params, "format": "json", "formatversion": "2"}
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def resolve_urls(titles):
    """Batch-resolve a list of File: titles -> {title: direct_url}. API caps ~50/call."""
    out = {}
    for i in range(0, len(titles), 40):
        batch = titles[i:i + 40]
        data = api_get({
            "action": "query",
            "titles": "|".join(batch),
            "prop": "imageinfo",
            "iiprop": "url",
        })
        # normalized maps API-cleaned titles back to what we asked for
        norm = {n["from"]: n["to"] for n in data.get("query", {}).get("normalized", [])}
        asked_for = {}  # api title -> original asked title
        for t in batch:
            asked_for[norm.get(t, t)] = t
        for page in data.get("query", {}).get("pages", []):
            ii = page.get("imageinfo")
            if ii:
                orig = asked_for.get(page["title"], page["title"])
                out[orig] = ii[0]["url"]
        time.sleep(0.3)  # be polite to the API
    return out


def existing_file(set_id):
    for ext in (".webp", ".png", ".jpg"):
        p = os.path.join(OUT_DIR, set_id + ext)
        if os.path.exists(p):
            return p
    return None


def download(url, set_id):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        ctype = r.headers.get("Content-Type", "").split(";")[0].strip()
        data = r.read()
    ext = EXT_BY_TYPE.get(ctype, ".png")
    path = os.path.join(OUT_DIR, set_id + ext)
    with open(path, "wb") as f:
        f.write(data)
    return os.path.basename(path), len(data)


def main():
    force = "--force" in sys.argv
    os.makedirs(OUT_DIR, exist_ok=True)

    doc = json.load(open(DATA))
    sets = doc["sets"] if isinstance(doc, dict) else doc

    # Append pre-staged sets not yet present in data.json (by slug id).
    existing_ids = {s["id"] for s in sets}
    for name in EXTRA_SETS:
        sid = slugify(name)
        if sid not in existing_ids:
            sets.append({"id": sid, "name": name})
            existing_ids.add(sid)

    todo = []          # sets needing download: (set_id, set_name, file_title)
    skipped = []
    for s in sets:
        if not force and existing_file(s["id"]):
            skipped.append(s["id"])
            continue
        todo.append((s["id"], s["name"], file_title(s["name"])))

    downloaded, missing = [], []
    if todo:
        titles = sorted({t[2] for t in todo})
        print(f"Resolving {len(titles)} file titles via Fandom API…")
        url_map = resolve_urls(titles)
        for set_id, set_name, title in todo:
            url = url_map.get(title)
            if not url:
                missing.append((set_id, set_name, title))
                continue
            try:
                fname, size = download(url, set_id)
                downloaded.append(fname)
                print(f"  ✓ {set_name:32s} -> {fname} ({size} B)")
                time.sleep(0.2)
            except Exception as e:  # noqa: BLE001
                missing.append((set_id, set_name, f"{title} [{e}]"))

    print("\n--- summary ---")
    print(f"downloaded: {len(downloaded)}")
    print(f"skipped (already present): {len(skipped)}")
    if missing:
        print(f"MISSING ({len(missing)}) — no image found, will fall back to element emblem:")
        for set_id, set_name, why in missing:
            print(f"  ✗ {set_name} ({set_id}) — {why}")
    else:
        print("missing: 0")


if __name__ == "__main__":
    main()
