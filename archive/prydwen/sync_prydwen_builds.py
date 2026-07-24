#!/usr/bin/env python3
"""
sync_prydwen_builds.py
Syncs WW character echo builds from Prydwen.gg.

Strategy (in priority order):
  1. Try Prydwen's Gatsby static page-data JSON endpoint — clean, structured.
  2. Fall back to HTML fetch + regex text extraction if JSON is unavailable.

Run:
  python scripts/sync_prydwen_builds.py
  python scripts/sync_prydwen_builds.py --limit 5   # quick test
  python scripts/sync_prydwen_builds.py --no-json   # force HTML fallback
"""

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, asdict, field
from html import unescape
from pathlib import Path
from typing import Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE        = "https://www.prydwen.gg/wuthering-waves"
INDEX_URL   = f"{BASE}/characters/"
# Gatsby generates a page-data.json for every static page at this path pattern.
GATSBY_URL  = "https://www.prydwen.gg/page-data/wuthering-waves/characters/{slug}/page-data.json"

KNOWN_SETS = {
    "Sierra Gale",
    "Molten Rift",
    "Void Thunder",
    "Freezing Frost",
    "Celestial Light",
    "Sun-sinking Eclipse",
    "Rejuvenating Glow",
    "Moonlit Clouds",
    "Lingering Tunes",
    "Midnight Veil",
    "Empyrean Anthem",
    "Eternal Radiance",
    "Frosty Resolve",
    "Tidebreaking Courage",
    "Gusts of Welkin",
    "Windward Pilgrimage",
    "Flaming Clawprint",
    "Crown of Valor",
    "Dream of the Lost",
    "Flamewing's Shadow",
    "Law of Harmony",
    "Thread of Severed Fate",
    "Halo of Starry Radiance",
    "Pact of Neonlight Leap",
    "Rite of Gilded Revelation",
}


@dataclass
class BuildEntry:
    character_name: str
    character_slug: str
    character_url:  str
    echo_set:       str
    priority:       int
    cost4:          str
    cost3:          str
    cost1:          str
    substats:       str
    source:         str = "Prydwen.gg"


@dataclass
class FailureEntry:
    slug:   str
    reason: str
    fields_empty: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def fetch(url: str, timeout: int = 30) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def fetch_json(url: str, timeout: int = 30) -> Optional[dict]:
    """Return parsed JSON from url, or None on any error."""
    try:
        raw = fetch(url, timeout=timeout)
        return json.loads(raw)
    except (HTTPError, URLError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Gatsby JSON extraction
# ---------------------------------------------------------------------------

def _walk(obj, key: str):
    """Recursively walk a nested dict/list looking for a key."""
    if isinstance(obj, dict):
        if key in obj:
            yield obj[key]
        for v in obj.values():
            yield from _walk(v, key)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item, key)


def extract_from_gatsby(slug: str, data: dict) -> List[BuildEntry]:
    """
    Attempt to pull build data from Gatsby page-data.json.

    Prydwen stores character data inside result.data.  The exact shape varies
    by page version, so we walk the tree looking for recognisable keys.
    Returns an empty list if we can't find anything useful.
    """
    result_node = data.get("result", {})

    # Try to find a node that looks like character build data
    name = slug.replace("-", " ").title()
    for candidate in _walk(result_node, "name"):
        if isinstance(candidate, str) and len(candidate) > 1:
            name = candidate
            break

    # Walk for echo set references
    found_sets: List[str] = []
    for candidate in _walk(result_node, "echoSets"):
        if isinstance(candidate, list):
            for item in candidate:
                if isinstance(item, dict):
                    set_name = item.get("name") or item.get("set") or item.get("title") or ""
                    if set_name in KNOWN_SETS and set_name not in found_sets:
                        found_sets.append(set_name)
            break

    # Fallback: scan all string values for known set names
    if not found_sets:
        for s in KNOWN_SETS:
            for val in _walk(result_node, "name"):
                if val == s and s not in found_sets:
                    found_sets.append(s)

    if not found_sets:
        return []

    # Try to extract stats — these key names are guesses; adjust if Prydwen's
    # schema differs from what we find in practice.
    cost4    = next(_walk(result_node, "cost4"),   None) or next(_walk(result_node, "4cost"),  None) or ""
    cost3    = next(_walk(result_node, "cost3"),   None) or next(_walk(result_node, "3cost"),  None) or ""
    cost1    = next(_walk(result_node, "cost1"),   None) or next(_walk(result_node, "1cost"),  None) or ""
    substats = next(_walk(result_node, "substats"),None) or ""

    # Flatten lists to strings if needed
    if isinstance(cost4, list):    cost4    = " / ".join(cost4)
    if isinstance(cost3, list):    cost3    = " / ".join(cost3)
    if isinstance(cost1, list):    cost1    = " / ".join(cost1)
    if isinstance(substats, list): substats = " > ".join(substats)

    url = f"{BASE}/characters/{slug}"
    return [
        BuildEntry(
            character_name=name,
            character_slug=slug,
            character_url=url,
            echo_set=set_name,
            priority=idx + 1,
            cost4=str(cost4),
            cost3=str(cost3),
            cost1=str(cost1),
            substats=str(substats),
        )
        for idx, set_name in enumerate(found_sets)
    ]


# ---------------------------------------------------------------------------
# HTML / regex extraction (original approach)
# ---------------------------------------------------------------------------

def clean_text(html: str) -> List[str]:
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<style.*?</style>",  " ", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", "\n", html)
    text = unescape(html)
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    return [ln for ln in lines if ln]


def parse_character_links(index_html: str) -> List[str]:
    absolute = re.findall(
        r"https://www\.prydwen\.gg/wuthering-waves/characters/([a-z0-9\-]+)",
        index_html, flags=re.I
    )
    relative = re.findall(
        r"/wuthering-waves/characters/([a-z0-9\-]+)",
        index_html, flags=re.I
    )
    links = sorted(set([s.lower() for s in (absolute + relative)]))
    return [slug for slug in links if slug != "characters"]


def find_section(lines: List[str], start: str, end: Optional[str]) -> List[str]:
    try:
        i = lines.index(start)
    except ValueError:
        return []
    j = len(lines)
    if end:
        for k in range(i + 1, len(lines)):
            if lines[k] == end:
                j = k
                break
    return lines[i:j]


def extract_best_echo_sets(lines: List[str]) -> List[str]:
    section = find_section(lines, "Best Echo Sets", "Best Echo Stats")
    return [ln for ln in section if ln in KNOWN_SETS]


def extract_stat(lines: List[str], label: str) -> str:
    for i, ln in enumerate(lines):
        if ln.lower() == label.lower() and i + 1 < len(lines):
            return lines[i + 1]
    return ""


def extract_substats(lines: List[str]) -> str:
    for i, ln in enumerate(lines):
        if ln.startswith("Substats:"):
            inline = ln.replace("Substats:", "", 1).strip()
            if inline:
                return inline
            if i + 1 < len(lines):
                return lines[i + 1]
    return ""


def extract_character_name(lines: List[str], fallback_slug: str) -> str:
    for ln in lines:
        if "Build and Guide" in ln and "Wuthering Waves" in ln:
            name = ln.replace("Wuthering Waves (WW)", "").replace("Build and Guide", "").strip()
            if name:
                return name
    return fallback_slug.replace("-", " ").title()


def parse_character_page(slug: str, html: str) -> List[BuildEntry]:
    lines     = clean_text(html)
    name      = extract_character_name(lines, slug)
    best_sets = extract_best_echo_sets(lines)
    if not best_sets:
        return []

    stat_section = find_section(lines, "Best Echo Stats", "Best Endgame Stats (Level 90)")
    cost4    = extract_stat(stat_section, "4 cost")
    cost3    = extract_stat(stat_section, "3 cost")
    cost1    = extract_stat(stat_section, "1 cost")
    substats = extract_substats(stat_section)

    url = f"{BASE}/characters/{slug}"
    return [
        BuildEntry(
            character_name=name,
            character_slug=slug,
            character_url=url,
            echo_set=set_name,
            priority=idx + 1,
            cost4=cost4,
            cost3=cost3,
            cost1=cost1,
            substats=substats,
        )
        for idx, set_name in enumerate(best_sets)
    ]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = ["cost4", "cost3", "cost1", "substats"]


def validate_entry(entry: BuildEntry) -> List[str]:
    """Return list of field names that are unexpectedly empty."""
    return [f for f in REQUIRED_FIELDS if not getattr(entry, f, "").strip()]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync WW character echo builds from Prydwen pages."
    )
    parser.add_argument("--output",   default="db/prydwen_character_builds.json",
                        help="Output JSON path")
    parser.add_argument("--log",      default="db/sync_failures.json",
                        help="Failure log JSON path")
    parser.add_argument("--limit",    type=int, default=0,
                        help="Only fetch first N characters (for testing)")
    parser.add_argument("--sleep-ms", type=int, default=250,
                        help="Delay between page fetches (ms)")
    parser.add_argument("--no-json",  action="store_true",
                        help="Skip Gatsby JSON attempt, go straight to HTML scraping")
    args = parser.parse_args()

    root         = Path(__file__).resolve().parents[1]
    output_path  = root / args.output
    log_path     = root / args.log

    # Fetch character index
    print("[info] fetching character index…")
    try:
        index_html = fetch(INDEX_URL)
    except Exception as exc:
        print(f"[error] could not fetch character index: {exc}", file=sys.stderr)
        sys.exit(1)

    slugs = parse_character_links(index_html)
    if args.limit > 0:
        slugs = slugs[:args.limit]
    print(f"[info] found {len(slugs)} character slugs")

    rows:     List[BuildEntry]  = []
    failures: List[FailureEntry] = []
    json_hits = 0
    html_hits = 0

    for slug in slugs:
        entries: List[BuildEntry] = []
        method  = "?"

        # --- Attempt 1: Gatsby static JSON ---
        if not args.no_json:
            gatsby_url  = GATSBY_URL.format(slug=slug)
            gatsby_data = fetch_json(gatsby_url)
            if gatsby_data:
                try:
                    entries = extract_from_gatsby(slug, gatsby_data)
                    if entries:
                        method = "gatsby-json"
                        json_hits += 1
                except Exception as exc:
                    print(f"[warn] gatsby parse failed for {slug}: {exc}")

        # --- Attempt 2: HTML scraping fallback ---
        if not entries:
            try:
                html    = fetch(f"{BASE}/characters/{slug}")
                entries = parse_character_page(slug, html)
                if entries:
                    method = "html"
                    html_hits += 1
            except Exception as exc:
                failures.append(FailureEntry(slug=slug, reason=f"fetch error: {exc}"))
                print(f"[warn] failed {slug}: {exc}")
                time.sleep(max(args.sleep_ms, 0) / 1000.0)
                continue

        if not entries:
            failures.append(FailureEntry(
                slug=slug,
                reason="no echo sets found (page format may have changed)"
            ))
            print(f"[warn] no builds found for {slug} (tried {method})")
        else:
            # Validate fields and warn on incomplete data
            for entry in entries:
                empty = validate_entry(entry)
                if empty:
                    failures.append(FailureEntry(
                        slug=slug,
                        reason=f"incomplete data via {method}",
                        fields_empty=empty
                    ))
                    print(f"[warn] {slug} ({entry.echo_set}): missing {empty}")
            rows.extend(entries)
            print(f"[ok]   {slug} — {len(entries)} set(s) via {method}")

        time.sleep(max(args.sleep_ms, 0) / 1000.0)

    # Write output
    payload: Dict = {
        "source":          "Prydwen.gg",
        "source_url":      BASE,
        "generated_at_epoch": int(time.time()),
        "character_count": len(slugs),
        "build_count":     len(rows),
        "method_summary":  { "gatsby_json": json_hits, "html_scrape": html_hits },
        "builds":          [asdict(r) for r in rows],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\n[done] wrote {output_path} — {len(rows)} builds from {len(slugs)} characters")
    print(f"       gatsby-json: {json_hits}  |  html-scrape: {html_hits}")

    # Write failure log
    if failures:
        log_payload = {
            "total_failures": len(failures),
            "failures": [asdict(f) for f in failures],
        }
        log_path.write_text(json.dumps(log_payload, indent=2), encoding="utf-8")
        print(f"[warn] {len(failures)} issues logged to {log_path}")
    else:
        print("[info] no failures to log")


if __name__ == "__main__":
    main()
