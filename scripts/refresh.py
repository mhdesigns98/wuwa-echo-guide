#!/usr/bin/env python3
"""
refresh.py
Pulls live Wuthering Waves game data (sonata/echo-set data) and syncs the
"setBonus" text on data.json's sets, plus a handful of advisory sanity checks.

This script NEVER touches characters, mainEcho, element, id, or meta — those
stay under manual/sheet control (see import_sheet.py). By default nothing is
written; pass --apply to actually update data.json.

Usage:
  python3 scripts/refresh.py                 # fetch (cache-aware), print diff report, write nothing
  python3 scripts/refresh.py --apply         # same, then write data.json in place
  python3 scripts/refresh.py --offline       # cache only, no network
  python3 scripts/refresh.py --force-fetch   # ignore cache freshness, refetch everything
  python3 scripts/refresh.py --source encore # force the encore.moe fallback source

Sources:
  PRIMARY  nanoka (hakush.in revival)  https://static.nanoka.cc
           Requires a browser-like User-Agent or Cloudflare returns 403.
  FALLBACK encore                      https://api.encore.moe
           Used automatically if nanoka fails, or forced with --source encore.

Exit codes:
  0 = no changes and no findings
  1 = changes pending / new sets / new characters / name misses
  2 = fetch error or ambiguous match
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT      = Path(__file__).resolve().parents[1]
DATA_JSON = ROOT / "data.json"
CACHE_DIR = ROOT / "cache"

# Reuse the character->element map maintained by import_sheet.py instead of
# duplicating it here.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_sheet import CHARACTER_ELEMENT_MAP  # noqa: E402

NANOKA_BASE = "https://static.nanoka.cc"
ENCORE_BASE = "https://api.encore.moe/en"

# Cloudflare in front of static.nanoka.cc 403s on the default urllib UA.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Name reconciliation between source sonata names and data.json set names.
# Key = source (nanoka/encore) name, value = the corresponding data.json name.
# ---------------------------------------------------------------------------
NAME_ALIASES = {
    "Havoc Eclipse": "Sun-sinking Eclipse",
}

# data.json sets that are intentionally not 1:1 with a single game sonata
# (they represent partial/mixed-set builds) — never matched, never reported
# as stale/unmatched.
SKIP_SETS = {
    "Dream of the Lost + 2pc Havoc",
    "Law of Harmony + 2pc Aero",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    """casefold, strip, drop colons, collapse whitespace — for pass 3 matching
    and for the mainEcho advisory check."""
    name = name.strip().casefold().replace(":", "")
    name = re.sub(r"\s+", " ", name)
    return name


def collapse_whitespace(s: str) -> str:
    s = s.replace("\n", " ")
    return re.sub(r"\s+", " ", s).strip()


def version_key(v: str):
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def http_get_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Interpolation / rendering
# ---------------------------------------------------------------------------

def interpolate(desc: str, params: list) -> str:
    """Replace {i} with params[i] ONLY if '{' appears in desc — older sets
    (ids 1-7, 9) ship pre-interpolated text whose param values can disagree
    with the text, so those are left completely alone."""
    if "{" not in desc:
        return collapse_whitespace(desc)

    def repl(m):
        idx = int(m.group(1))
        if idx < len(params):
            return str(params[idx])
        print(f"[warn] param index {{{idx}}} out of range "
              f"(have {len(params)}) in desc: {desc!r}")
        return m.group(0)

    result = re.sub(r"\{(\d+)\}", repl, desc)
    return collapse_whitespace(result)


def render_set_bonus(nanoka_set: dict) -> str:
    """nanoka_set: {"set": {"<pieceCount>": {"en": {desc, param}, ...}, ...}}
    Generic over any combination of piece counts (2/5, 3, 1, ...)."""
    pieces = sorted(nanoka_set["set"].keys(), key=lambda x: int(x))
    parts = []
    for p in pieces:
        entry = nanoka_set["set"][p]["en"]
        text = interpolate(entry["desc"], entry.get("param", []))
        parts.append(f"{p}pc: {text}")
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def cache_file(ver: str, name: str) -> Path:
    return CACHE_DIR / ver / f"{name}.json"


def cache_read(ver: str, name: str):
    p = cache_file(ver, name)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def cache_write(ver: str, name: str, data) -> None:
    p = cache_file(ver, name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def cached_versions() -> list:
    if not CACHE_DIR.exists():
        return []
    return sorted(
        (d.name for d in CACHE_DIR.iterdir() if d.is_dir() and d.name != "encore"),
        key=version_key,
        reverse=True,
    )


# ---------------------------------------------------------------------------
# nanoka source
# ---------------------------------------------------------------------------

def fetch_nanoka(offline: bool, force_fetch: bool):
    """Returns (ver, sonata, echo, character, status_lines) or raises on
    unrecoverable fetch error."""
    status = []

    if offline:
        versions = cached_versions()
        if not versions:
            raise RuntimeError("no cached nanoka version available for --offline")
        for ver in versions:
            sonata = cache_read(ver, "sonata")
            echo = cache_read(ver, "echo")
            character = cache_read(ver, "character")
            if sonata and echo and character:
                status.append(f"[info] offline: using cached version {ver}")
                return ver, sonata, echo, character, status
        raise RuntimeError("cached version dirs exist but are missing sonata/echo/character.json")

    # Need the manifest to know the live version.
    manifest = http_get_json(f"{NANOKA_BASE}/manifest.json")
    ver = manifest["ww"]["live"]
    cache_write(ver, "manifest", manifest)

    have_full_cache = (
        not force_fetch
        and cache_file(ver, "sonata").exists()
        and cache_file(ver, "echo").exists()
        and cache_file(ver, "character").exists()
    )

    if have_full_cache:
        status.append(f"[info] live version {ver} — reusing cache/{ver}/")
        sonata = cache_read(ver, "sonata")
        echo = cache_read(ver, "echo")
        character = cache_read(ver, "character")
        return ver, sonata, echo, character, status

    status.append(f"[info] live version {ver} — fetching fresh data" +
                   (" (--force-fetch)" if force_fetch else " (no usable cache)"))
    sonata = http_get_json(f"{NANOKA_BASE}/ww/{ver}/sonata.json")
    echo = http_get_json(f"{NANOKA_BASE}/ww/{ver}/echo.json")
    character = http_get_json(f"{NANOKA_BASE}/ww/{ver}/character.json")
    cache_write(ver, "sonata", sonata)
    cache_write(ver, "echo", echo)
    cache_write(ver, "character", character)
    return ver, sonata, echo, character, status


def nanoka_sonatas(sonata_data: dict) -> dict:
    """{source_name: {"set": {...}}} — keeps the shape render_set_bonus wants."""
    return {v["name"]["en"]: {"set": v["set"]} for v in sonata_data.values()}


def nanoka_echo_names(echo_data: dict) -> set:
    return {v["en"] for v in echo_data.values() if v.get("en")}


def nanoka_character_names(character_data: dict) -> set:
    return {v["en"] for v in character_data.values() if v.get("en")}


# ---------------------------------------------------------------------------
# encore fallback source
# ---------------------------------------------------------------------------

def fetch_encore(offline: bool, force_fetch: bool):
    status = []
    ver = "encore"

    if offline:
        echo = cache_read(ver, "echo")
        character = cache_read(ver, "character")
        if not (echo and character):
            raise RuntimeError("no cached encore data available for --offline")
        status.append("[info] offline: using cached encore data")
        return ver, echo, character, status

    have_cache = (
        not force_fetch
        and cache_file(ver, "echo").exists()
        and cache_file(ver, "character").exists()
    )
    if have_cache:
        status.append("[info] encore — reusing cache/encore/")
        return ver, cache_read(ver, "echo"), cache_read(ver, "character"), status

    status.append("[info] encore — fetching fresh data" +
                   (" (--force-fetch)" if force_fetch else " (no usable cache)"))
    echo = http_get_json(f"{ENCORE_BASE}/echo")
    character = http_get_json(f"{ENCORE_BASE}/character")
    cache_write(ver, "echo", echo)
    cache_write(ver, "character", character)
    return ver, echo, character, status


def encore_sonatas(echo_data: dict) -> dict:
    """Builds the same {source_name: {"set": {piece: {"en": {desc, param}}}}}
    shape from encore's FetterGroups. encore's EffectDescription text is
    already fully joined/English — no param interpolation needed or possible,
    so param is always left empty (interpolate() is a no-op without '{')."""
    sonatas: dict = {}
    for e in echo_data.get("Echo", []):
        for group in e.get("FetterGroups", []):
            name = group.get("Name")
            if not name:
                continue
            bucket = sonatas.setdefault(name, {"set": {}})
            for fetter in group.get("Fetters", []):
                key = str(fetter.get("Key"))
                desc = fetter.get("EffectDescription", "")
                if key not in bucket["set"]:
                    bucket["set"][key] = {"en": {"desc": desc, "param": []}}
    return sonatas


def encore_echo_names(echo_data: dict) -> set:
    return {e["Name"] for e in echo_data.get("Echo", []) if e.get("Name")}


def encore_character_names(character_data: dict) -> set:
    return {r["Name"] for r in character_data.get("roleList", []) if r.get("Name")}


def encore_text_is_usable(sonatas: dict) -> bool:
    """encore's EffectDescription is supposed to ship fully pre-joined
    English text (no param array to interpolate against), but in practice a
    large share of entries still contain unresolved '{n}' placeholders with
    nothing to fill them. Rendering those would silently write garbled
    "DMG + {0}" text into data.json, so bonus-text sync is only offered from
    encore when none of its descriptions have leftover braces."""
    for bonus in sonatas.values():
        for piece in bonus["set"].values():
            if "{" in piece["en"]["desc"]:
                return False
    return True


# ---------------------------------------------------------------------------
# Matching data.json sets <-> source sonatas
# ---------------------------------------------------------------------------

class AmbiguousMatch(Exception):
    pass


def find_source_for_data_set(data_name: str, sonatas: dict):
    """Returns the source sonata name matching data_name, or None if no
    match was found. Raises AmbiguousMatch if normalization collapses more
    than one source name onto this data_name."""
    # Pass 1: exact English name
    if data_name in sonatas:
        return data_name

    # Pass 2: NAME_ALIASES (source name -> data.json name)
    for src_name, target in NAME_ALIASES.items():
        if target == data_name and src_name in sonatas:
            return src_name

    # Pass 3: normalized equality (casefold, strip, drop ':', collapse spaces)
    norm_target = normalize_name(data_name)
    candidates = [s for s in sonatas if normalize_name(s) == norm_target]
    if len(candidates) > 1:
        raise AmbiguousMatch(
            f"data set '{data_name}' normalizes to match multiple source "
            f"sonatas: {candidates}"
        )
    if len(candidates) == 1:
        return candidates[0]

    return None


# ---------------------------------------------------------------------------
# Advisory checks
# ---------------------------------------------------------------------------

def check_main_echoes(data: dict, echo_names: set) -> list:
    norm_echo_names = {normalize_name(n) for n in echo_names}
    warnings = []
    for s in data.get("sets", []):
        if s["name"] in SKIP_SETS:
            continue
        main_echo = s.get("mainEcho", "") or ""
        if not main_echo or "tbd" in main_echo.lower() or "placeholder" in main_echo.lower():
            continue
        for raw_part in main_echo.split("/"):
            part = raw_part.strip()
            if not part:
                continue
            if "tbd" in part.lower() or "placeholder" in part.lower():
                continue
            if normalize_name(part) not in norm_echo_names:
                warnings.append(
                    f"[warn] mainEcho '{part}' (set: {s['name']}) not found "
                    f"in source echo names"
                )
    return warnings


def check_new_characters(data: dict, source_char_names: set) -> list:
    known = set(CHARACTER_ELEMENT_MAP.keys())
    for s in data.get("sets", []):
        for c in s.get("characters", []):
            if c.get("name"):
                known.add(c["name"])

    new_chars = sorted(n for n in source_char_names if n not in known)
    return [f"[new-char] {n} — add to the Google Sheet" for n in new_chars]


# ---------------------------------------------------------------------------
# Report / main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync sonata set-bonus text from live game data into data.json"
    )
    parser.add_argument("--apply", action="store_true",
                        help="Write data.json in place (default: dry-run / report only)")
    parser.add_argument("--offline", action="store_true",
                        help="Use cached data only, no network calls")
    parser.add_argument("--force-fetch", action="store_true",
                        help="Ignore cache freshness and refetch everything")
    parser.add_argument("--source", choices=["auto", "nanoka", "encore"], default="auto",
                        help="Force a specific data source (default: auto, "
                             "tries nanoka then falls back to encore)")
    args = parser.parse_args()

    if args.offline and args.force_fetch:
        print("[error] --offline and --force-fetch are mutually exclusive")
        return 2

    # -----------------------------------------------------------------
    # Fetch source data
    # -----------------------------------------------------------------
    source_origin = None
    status_lines: list = []
    ver = None
    sonatas = {}
    echo_names: set = set()
    char_names: set = set()
    bonus_sync_supported = True

    def load_encore():
        nonlocal source_origin, ver
        e_ver, echo_data, character_data, e_status = fetch_encore(args.offline, args.force_fetch)
        status_lines.extend(e_status)
        source_origin = "encore (api.encore.moe)"
        ver = e_ver
        return (encore_sonatas(echo_data),
                encore_echo_names(echo_data),
                encore_character_names(character_data))

    try:
        if args.source == "encore":
            sonatas, echo_names, char_names = load_encore()
            bonus_sync_supported = encore_text_is_usable(sonatas)
        else:
            try:
                n_ver, sonata_data, echo_data, character_data, n_status = fetch_nanoka(
                    args.offline, args.force_fetch
                )
                status_lines.extend(n_status)
                source_origin = "nanoka (static.nanoka.cc)"
                ver = n_ver
                sonatas = nanoka_sonatas(sonata_data)
                echo_names = nanoka_echo_names(echo_data)
                char_names = nanoka_character_names(character_data)
            except (HTTPError, URLError, RuntimeError, KeyError) as exc:
                if args.source == "nanoka":
                    print(f"[error] nanoka fetch failed: {exc}")
                    return 2
                print(f"[warn] nanoka fetch failed ({exc}); falling back to encore")
                sonatas, echo_names, char_names = load_encore()
                bonus_sync_supported = encore_text_is_usable(sonatas)
    except (HTTPError, URLError, RuntimeError) as exc:
        print(f"[error] fetch failed: {exc}")
        return 2

    if not bonus_sync_supported:
        status_lines.append(
            "[warn] encore EffectDescription text contains unresolved {n} "
            "placeholders with no param data to fill them — setBonus sync "
            "is disabled for this run. Advisory checks (mainEcho / new "
            "characters) and NEW/MISS set detection still run. Use the "
            "default nanoka source to sync setBonus text."
        )

    # -----------------------------------------------------------------
    # Load data.json (read-only unless --apply)
    # -----------------------------------------------------------------
    data = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    sets = data.get("sets", [])

    # -----------------------------------------------------------------
    # Match data.json sets <-> source sonatas
    # -----------------------------------------------------------------
    matchable_sets = [s for s in sets if s["name"] not in SKIP_SETS]

    matched_source_names: set = set()
    diffs = []       # (data_name, old_bonus, new_bonus)
    unmatched = []   # data.json sets with no source counterpart

    try:
        for s in matchable_sets:
            src_name = find_source_for_data_set(s["name"], sonatas)
            if src_name is None:
                unmatched.append(s["name"])
                continue
            matched_source_names.add(src_name)
            if not bonus_sync_supported:
                continue
            new_bonus = render_set_bonus(sonatas[src_name])
            old_bonus = s.get("setBonus", "")
            if new_bonus != old_bonus:
                diffs.append((s["name"], old_bonus, new_bonus))
                if args.apply:
                    s["setBonus"] = new_bonus
    except AmbiguousMatch as exc:
        print(f"[error] ambiguous match: {exc}")
        return 2

    new_sonatas = sorted(name for name in sonatas if name not in matched_source_names)

    # -----------------------------------------------------------------
    # Advisory checks
    # -----------------------------------------------------------------
    main_echo_warnings = check_main_echoes(data, echo_names)
    new_char_lines = check_new_characters(data, char_names)

    # -----------------------------------------------------------------
    # Report
    # -----------------------------------------------------------------
    print("=" * 70)
    print(f"refresh.py — Wuthering Waves data sync ({ver})")
    print(f"source: {source_origin}")
    for line in status_lines:
        print(line)
    print("=" * 70)

    if not bonus_sync_supported:
        print("\n-- setBonus diffs — DISABLED (encore text has unresolved placeholders) --")
        print("(re-run with the default nanoka source to sync setBonus text)")
    else:
        print(f"\n-- setBonus diffs ({len(diffs)} changed) --")
        if diffs:
            for name, old, new in diffs:
                print(f"[diff] {name}")
                print(f"  old: {old}")
                print(f"  new: {new}")
        else:
            print("(none)")

    print(f"\n-- NEW sets in source, not in data.json ({len(new_sonatas)}) --")
    if new_sonatas:
        for name in new_sonatas:
            print(f"[NEW]  {name}")
    else:
        print("(none)")

    print(f"\n-- Unmatched data.json sets ({len(unmatched)}) --")
    if unmatched:
        for name in unmatched:
            print(f"[MISS] {name} — no source match. Add a NAME_ALIASES / "
                  f"SKIP_SETS entry, or fix the name in data.json.")
    else:
        print("(none)")

    print(f"\n-- mainEcho advisory warnings ({len(main_echo_warnings)}) --")
    if main_echo_warnings:
        for line in main_echo_warnings:
            print(line)
    else:
        print("(none)")

    print(f"\n-- New characters in source, not in data.json/sheet ({len(new_char_lines)}) --")
    if new_char_lines:
        for line in new_char_lines:
            print(line)
    else:
        print("(none)")

    print("\n-- Summary --")
    print(f"  setBonus changes:  {len(diffs)}")
    print(f"  new sets:          {len(new_sonatas)}")
    print(f"  unmatched sets:    {len(unmatched)}")
    print(f"  mainEcho warnings: {len(main_echo_warnings)}")
    print(f"  new characters:    {len(new_char_lines)}")

    has_findings = bool(diffs or new_sonatas or unmatched or new_char_lines)
    exit_code = 1 if has_findings else 0

    if args.apply:
        data["sets"] = sets
        DATA_JSON.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"\n[done] {DATA_JSON} updated ({len(diffs)} set(s) changed). "
              f"Exit code {exit_code} "
              f"(0 = nothing pending, 1 = findings existed, 2 = fetch/match error).")
    else:
        print(f"\n[dry-run] no files written. Exit code {exit_code} "
              f"(0 = nothing pending, 1 = findings to review, 2 = fetch/match error). "
              f"Re-run with --apply to write these changes.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
