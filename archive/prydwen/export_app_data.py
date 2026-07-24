#!/usr/bin/env python3
import argparse
import json
from collections import defaultdict
from pathlib import Path


def slugify(text: str) -> str:
    return text.lower().replace("'", "").replace(".", "").replace(" ", "-")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export app-friendly data.json from prydwen sync output.")
    parser.add_argument("--input", default="db/prydwen_character_builds.json", help="Input sync JSON")
    parser.add_argument("--output", default="data.prydwen.json", help="Output file in app format")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / args.input).read_text(encoding="utf-8"))
    builds = payload.get("builds", [])

    grouped = defaultdict(list)
    for b in sorted(builds, key=lambda x: (x.get("echo_set", ""), int(x.get("priority", 1)))):
        grouped[b["echo_set"]].append(
            {
                "name": b["character_name"],
                "element": "Unknown",
                "role": "TBD",
                "costs": {
                    "4": [b.get("cost4", "")] if b.get("cost4", "") else [],
                    "3": [b.get("cost3", "")] if b.get("cost3", "") else [],
                    "1": [b.get("cost1", "")] if b.get("cost1", "") else [],
                },
                "substats": [b.get("substats", "")] if b.get("substats", "") else [],
            }
        )

    sets = []
    for set_name, chars in grouped.items():
        sets.append(
            {
                "id": slugify(set_name),
                "name": set_name,
                "element": "Universal",
                "setBonus": "Sourced from Prydwen.gg",
                "mainEcho": "",
                "characters": chars,
            }
        )

    sets = sorted(sets, key=lambda x: x["name"])
    out = root / args.output
    out.write_text(json.dumps(sets, indent=2), encoding="utf-8")
    print(f"[ok] wrote {out} with {len(sets)} sets")


if __name__ == "__main__":
    main()
