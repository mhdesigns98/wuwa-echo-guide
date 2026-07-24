PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  base_url TEXT NOT NULL,
  fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS echo_sets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS characters (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL UNIQUE,
  element TEXT,
  rarity INTEGER,
  source_url TEXT
);

CREATE TABLE IF NOT EXISTS character_echo_builds (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  echo_set_id INTEGER NOT NULL REFERENCES echo_sets(id) ON DELETE CASCADE,
  priority INTEGER NOT NULL DEFAULT 1,
  substats TEXT,
  cost4 TEXT,
  cost3 TEXT,
  cost1 TEXT,
  raw_payload TEXT,
  UNIQUE(character_id, echo_set_id)
);

CREATE INDEX IF NOT EXISTS idx_builds_character ON character_echo_builds(character_id);
CREATE INDEX IF NOT EXISTS idx_builds_echo_set ON character_echo_builds(echo_set_id);
