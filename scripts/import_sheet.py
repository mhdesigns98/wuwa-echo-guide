#!/usr/bin/env python3
"""
import_sheet.py
Merges the Google Sheets character build data into data.json.

Usage:
  # Pull directly from the published Google Sheet (recommended):
  python3 scripts/import_sheet.py

  # Use a locally downloaded CSV instead:
  python3 scripts/import_sheet.py path/to/file.csv

  # Preview changes without writing anything:
  python3 scripts/import_sheet.py --dry-run
  python3 scripts/import_sheet.py path/to/file.csv --dry-run

What it does:
  - Sets in the CSV → characters list is replaced with fresh CSV data
  - Sets in data.json but NOT in CSV → kept as-is (nothing deleted)
  - Sets in CSV but NOT in data.json → new entry created with placeholder metadata
  - Set metadata (setBonus, mainEcho, element) → always preserved from data.json

CSV columns expected:
  Character, Best Echo Set, 4-Cost Main, 3-Cost Main, 1-Cost Main,
  Substat Priority, Target ER
"""

import argparse
import csv
import io
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from urllib.request import Request, urlopen

ROOT      = Path(__file__).resolve().parents[1]
DATA_JSON = ROOT / "data.json"

# Published Google Sheet CSV URL — update this if the sheet changes
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRFgZwdLizUu1Ztiw-CkNLktl7UQqatiAMeNbXHMWOdhqa_s6b1cCm_D2qJbT5FSgcOfwifU2Q3aeGJ/pub?output=csv"

# ---------------------------------------------------------------------------
# Name normalisation maps — add entries here when the sheet uses a slightly
# different spelling than what's in data.json / the game.
# ---------------------------------------------------------------------------

SET_NAME_MAP: Dict[str, str] = {
    "Pact of Neonlight":           "Pact of Neonlight Leap",
    "Rite of Guilded Revelations": "Rite of Gilded Revelation",
    "Rite of Gilded Revelations":  "Rite of Gilded Revelation",
    "Halo of Radiance":            "Halo of Starry Radiance",
    "Flaming Clawprint":           "Flaming Clawprint",
    "Thread of Severed Fate":      "Thread of Severed Fate",
}

# Element to assign when a set is brand new (not yet in data.json).
# Update this list as new sets are added to the game.
NEW_SET_ELEMENT_MAP: Dict[str, str] = {
    "Trailblazing Star":      "Fusion",
    "Tidebreaking Courage":   "Fusion",
    "Moonlit Clouds":         "Support",
    "Celestial Light":        "Spectro",
    "Freezing Frost":         "Glacio",
    "Sound of True Name":     "Aero",
    "Halo of Starry Radiance":"Universal",
}

# Character elements — used when building character objects.
# Add new characters here as they're released.
CHARACTER_ELEMENT_MAP: Dict[str, str] = {
    "Aemeath":      "Fusion",
    "Augusta":      "Electro",
    "Baizhi":       "Glacio",
    "Brant":        "Fusion",
    "Buling":       "Electro",
    "Camellya":     "Havoc",
    "Cantarella":   "Havoc",
    "Carlotta":     "Glacio",
    "Calcharo":     "Electro",
    "Cartethyia":   "Aero",
    "Changli":      "Fusion",
    "Chisa":        "Havoc",
    "Ciaccona":     "Aero",
    "Danjin":       "Havoc",
    "Galbrena":     "Fusion",
    "Iuno":         "Universal",
    "Jianxin":      "Aero",
    "Jinhsi":       "Spectro",
    "Jiyan":        "Aero",
    "Lumi":         "Electro",
    "Lupa":         "Fusion",
    "Luuk Herssen": "Spectro",
    "Lynae":        "Spectro",
    "Mornye":       "Universal",
    "Phoebe":       "Spectro",
    "Phrolova":     "Havoc",
    "Qiuyuan":      "Aero",
    "Roccia":       "Havoc",
    "Shorekeeper":  "Spectro",
    "Sigrika":      "Aero",
    "Verina":       "Spectro",
    "Xiangli Yao":  "Electro",
    "Yinlin":       "Electro",
    "Zani":         "Spectro",
    "Zhezhi":       "Glacio",
}

# Roles inferred from 4-cost main stat or set type.
# Most characters default to "Main DPS" — override here for supports/healers.
CHARACTER_ROLE_MAP: Dict[str, str] = {
    "Baizhi":       "Healer",
    "Cantarella":   "Healer / Buffer",
    "Chisa":        "Sustain / Support",
    "Jianxin":      "Support / Sub-DPS",
    "Mornye":       "Support / DEF",
    "Shorekeeper":  "Healer / Buffer",
    "Verina":       "Healer / Buffer",
    "Zhezhi":       "Sub-DPS / Buffer",
}


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def normalize_set_name(name: str) -> str:
    name = name.strip()
    return SET_NAME_MAP.get(name, name)


def parse_costs(raw: str) -> List[str]:
    """
    'Crit Rate/DMG' → ['Crit DMG', 'Crit Rate']   (priority order: DMG first)
    'Healing Bonus' → ['Healing Bonus']
    'Crit Rate (ER)'→ ['Crit Rate']                (strip the note)
    """
    raw = raw.strip()
    if not raw:
        return []
    # Strip parenthetical notes like "(ER)"
    raw = re.sub(r"\(.*?\)", "", raw).strip()
    if "/" in raw:
        parts = [p.strip() for p in raw.split("/")]
        # Put DMG variant first as primary recommendation
        parts.sort(key=lambda x: (0 if "DMG" in x else 1))
        return parts
    return [raw]


def parse_substats(raw: str) -> List[str]:
    if not raw.strip():
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def infer_role(name: str, cost4: List[str]) -> str:
    if name in CHARACTER_ROLE_MAP:
        return CHARACTER_ROLE_MAP[name]
    if cost4 and "Healing" in cost4[0]:
        return "Healer"
    if cost4 and "Defence" in cost4[0]:
        return "Main DPS (DEF)"
    return "Main DPS"


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def fetch_sheet_csv() -> str:
    """Fetch the published Google Sheet as raw CSV text."""
    print(f"[info] fetching sheet from Google…")
    req = Request(SHEET_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8-sig", errors="ignore")


def csv_to_builds(source) -> Dict[str, List[dict]]:
    """
    Parse CSV → {canonical_set_name: [character_dict, ...]}
    source can be a Path (local file) or a string of raw CSV text.
    """
    builds: Dict[str, List[dict]] = {}

    if isinstance(source, Path):
        f = open(source, newline="", encoding="utf-8-sig")
    else:
        f = io.StringIO(source)

    with f:
        reader = csv.DictReader(f)
        for row in reader:
            name      = row.get("Character", "").strip()
            set_raw   = row.get("Best Echo Set", "").strip()
            set_name  = normalize_set_name(set_raw)
            cost4     = parse_costs(row.get("4-Cost Main", ""))
            cost3     = parse_costs(row.get("3-Cost Main", ""))
            cost1     = parse_costs(row.get("1-Cost Main", ""))
            substats  = parse_substats(row.get("Substat Priority", ""))
            target_er = row.get("Target ER", "").strip()

            if not name or not set_name:
                continue

            if set_raw != set_name:
                print(f"[norm] '{set_raw}' → '{set_name}' for {name}")

            char: dict = {
                "name":     name,
                "element":  CHARACTER_ELEMENT_MAP.get(name, "Universal"),
                "role":     infer_role(name, cost4),
                "costs":    {"4": cost4, "3": cost3, "1": cost1},
                "substats": substats,
            }
            if target_er:
                char["targetER"] = target_er

            builds.setdefault(set_name, []).append(char)

    return builds


def merge(data: dict, builds: Dict[str, List[dict]]) -> tuple[dict, list]:
    """
    Merge builds into data, return (updated_data, change_log).

    After merging, any character whose name doesn't appear anywhere in the
    CSV is removed from data.json. Sets that end up empty are also removed.
    The Google Sheet is treated as the single source of truth for who exists.
    """
    sets    = data.get("sets", [])
    by_name: Dict[str, dict] = {s["name"]: s for s in sets}
    log: list = []

    # Build the canonical name list from the CSV — used for purging below
    csv_names: set = {c["name"] for chars in builds.values() for c in chars}

    # --- Step 1: update / create sets from CSV ---
    for set_name, chars in sorted(builds.items()):
        if set_name in by_name:
            old_chars = [c["name"] for c in by_name[set_name].get("characters", [])]
            new_chars = [c["name"] for c in chars]
            added     = [n for n in new_chars if n not in old_chars]
            removed   = [n for n in old_chars if n not in new_chars]
            by_name[set_name]["characters"] = chars
            log.append(f"[upd]  {set_name}: {len(chars)} chars"
                       + (f" | +{added}" if added else "")
                       + (f" | -{removed}" if removed else ""))
        else:
            element = NEW_SET_ELEMENT_MAP.get(set_name, "Universal")
            slug    = re.sub(r"[^a-z0-9]+", "-", set_name.lower()).strip("-")
            new_set = {
                "id":         slug,
                "name":       set_name,
                "element":    element,
                "setBonus":   f"2pc: {element} DMG +10% | 5pc: See Prydwen.gg for 5pc bonus",
                "mainEcho":   "TBD — fill in manually",
                "characters": chars,
            }
            sets.append(new_set)
            by_name[set_name] = new_set
            log.append(f"[NEW]  {set_name} ({element}) — {len(chars)} chars (fill in setBonus + mainEcho)")

    # --- Step 2: purge characters not in the sheet from ALL sets ---
    for s in sets:
        before = [c["name"] for c in s.get("characters", [])]
        kept   = [c for c in s.get("characters", []) if c["name"] in csv_names]
        purged = [n for n in before if n not in csv_names]
        if purged:
            s["characters"] = kept
            log.append(f"[purge] {s['name']}: removed {purged} (not in sheet)")

    # --- Step 3: remove sets that are now empty ---
    before_count = len(sets)
    sets = [s for s in sets if s.get("characters")]
    removed_sets = before_count - len(sets)
    if removed_sets:
        log.append(f"[clean] removed {removed_sets} empty set(s)")

    data["sets"] = sets
    return data, log


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge Google Sheets data into data.json"
    )
    parser.add_argument("csv", nargs="?", default=None,
                        help="Path to a local CSV file (omit to fetch from Google Sheets)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing anything")
    args = parser.parse_args()

    if args.csv:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            print(f"[error] file not found: {csv_path}")
            return
        print(f"[info] reading {csv_path.name}…")
        builds = csv_to_builds(csv_path)
    else:
        raw_csv = fetch_sheet_csv()
        builds  = csv_to_builds(raw_csv)
    total_chars = sum(len(v) for v in builds.values())
    print(f"[info] {total_chars} characters across {len(builds)} sets")

    print(f"[info] loading {DATA_JSON}…")
    data = json.loads(DATA_JSON.read_text(encoding="utf-8"))

    data, log = merge(data, builds)

    print()
    for line in log:
        print(line)

    if args.dry_run:
        print("\n[dry-run] no files written")
    else:
        DATA_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"\n[done] {DATA_JSON} updated")
        print("       Remember to fill in setBonus + mainEcho for any [NEW] sets above.")


if __name__ == "__main__":
    main()
