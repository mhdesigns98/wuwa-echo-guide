#!/usr/bin/env python3
import argparse
import json
import re
import time
from dataclasses import dataclass, asdict
from html import unescape
from pathlib import Path
from typing import Dict, List, Optional
from urllib.request import Request, urlopen

BASE = "https://www.prydwen.gg/wuthering-waves"
INDEX_URL = f"{BASE}/characters/"

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
    character_url: str
    echo_set: str
    priority: int
    cost4: str
    cost3: str
    cost1: str
    substats: str
    source: str = "Prydwen.gg"


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def clean_text(html: str) -> List[str]:
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", "\n", html)
    text = unescape(html)
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    return [ln for ln in lines if ln]


def parse_character_links(index_html: str) -> List[str]:
    absolute = re.findall(r"https://www\.prydwen\.gg/wuthering-waves/characters/([a-z0-9\-]+)", index_html, flags=re.I)
    relative = re.findall(r"/wuthering-waves/characters/([a-z0-9\-]+)", index_html, flags=re.I)
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
    out: List[str] = []
    for ln in section:
        if ln in KNOWN_SETS:
            out.append(ln)
    return out


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
    lines = clean_text(html)
    name = extract_character_name(lines, slug)
    best_sets = extract_best_echo_sets(lines)
    if not best_sets:
        return []

    stat_section = find_section(lines, "Best Echo Stats", "Best Endgame Stats (Level 90)")
    cost4 = extract_stat(stat_section, "4 cost")
    cost3 = extract_stat(stat_section, "3 cost")
    cost1 = extract_stat(stat_section, "1 cost")
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync WW character echo builds from Prydwen pages.")
    parser.add_argument("--output", default="db/prydwen_character_builds.json", help="Output JSON path")
    parser.add_argument("--limit", type=int, default=0, help="Only fetch first N characters for testing")
    parser.add_argument("--sleep-ms", type=int, default=250, help="Delay between page fetches")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output_path = root / args.output

    index_html = fetch(INDEX_URL)
    slugs = parse_character_links(index_html)
    if args.limit > 0:
        slugs = slugs[: args.limit]

    rows: List[BuildEntry] = []
    for slug in slugs:
        try:
            html = fetch(f"{BASE}/characters/{slug}")
            rows.extend(parse_character_page(slug, html))
        except Exception as exc:
            print(f"[warn] failed {slug}: {exc}")
        time.sleep(max(args.sleep_ms, 0) / 1000.0)

    payload: Dict[str, object] = {
        "source": "Prydwen.gg",
        "source_url": BASE,
        "generated_at_epoch": int(time.time()),
        "character_count": len(slugs),
        "build_count": len(rows),
        "builds": [asdict(r) for r in rows],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[ok] wrote {output_path} with {len(rows)} builds")


if __name__ == "__main__":
    main()
