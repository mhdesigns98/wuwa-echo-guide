#!/usr/bin/env python3
import argparse
import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Iterable, Tuple


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def upsert_echo_set(cur: sqlite3.Cursor, name: str) -> int:
    slug = name.lower().replace("'", "").replace(".", "").replace(" ", "-")
    cur.execute("INSERT OR IGNORE INTO echo_sets(slug, name) VALUES(?, ?)", (slug, name))
    cur.execute("SELECT id FROM echo_sets WHERE name = ?", (name,))
    return int(cur.fetchone()[0])


def upsert_character(cur: sqlite3.Cursor, slug: str, name: str, source_url: str) -> int:
    cur.execute(
        "INSERT OR IGNORE INTO characters(slug, name, source_url) VALUES(?, ?, ?)",
        (slug, name, source_url),
    )
    cur.execute("SELECT id FROM characters WHERE slug = ?", (slug,))
    return int(cur.fetchone()[0])


def build_rows(payload: Dict) -> Iterable[Tuple]:
    for row in payload.get("builds", []):
        yield (
            row["character_slug"],
            row["character_name"],
            row["character_url"],
            row["echo_set"],
            int(row.get("priority", 1)),
            row.get("substats", ""),
            row.get("cost4", ""),
            row.get("cost3", ""),
            row.get("cost1", ""),
            json.dumps(row, ensure_ascii=True),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SQLite DB from normalized Prydwen sync JSON.")
    parser.add_argument("--input", default="db/prydwen_character_builds.json", help="Input JSON path")
    parser.add_argument("--schema", default="db/schema.sql", help="Schema SQL path")
    parser.add_argument("--db", default="db/wuwa_echoes.sqlite", help="SQLite output path")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    input_path = root / args.input
    schema_path = root / args.schema
    db_path = root / args.db
    db_path.parent.mkdir(parents=True, exist_ok=True)

    payload = load_json(input_path)

    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON;")
    con.executescript(schema_path.read_text(encoding="utf-8"))
    cur = con.cursor()

    cur.execute(
        "INSERT OR REPLACE INTO sources(name, base_url, fetched_at) VALUES(?, ?, ?)",
        ("Prydwen.gg", payload.get("source_url", ""), str(int(time.time()))),
    )

    inserted = 0
    for row in build_rows(payload):
        char_slug, char_name, char_url, set_name, priority, substats, cost4, cost3, cost1, raw_payload = row
        char_id = upsert_character(cur, char_slug, char_name, char_url)
        set_id = upsert_echo_set(cur, set_name)
        cur.execute(
            """
            INSERT OR REPLACE INTO character_echo_builds
            (character_id, echo_set_id, priority, substats, cost4, cost3, cost1, raw_payload)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (char_id, set_id, priority, substats, cost4, cost3, cost1, raw_payload),
        )
        inserted += 1

    con.commit()
    con.close()
    print(f"[ok] upserted {inserted} build rows into {db_path}")


if __name__ == "__main__":
    main()
