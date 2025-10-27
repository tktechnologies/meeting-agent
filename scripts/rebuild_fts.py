#!/usr/bin/env python3
import os
import sqlite3

try:
    from agent.config import spine_db_path  # type: ignore
    DB = spine_db_path()
except Exception:
    DB = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "parsing-agent", "spine.db"))

SQL_CREATE = """
CREATE VIRTUAL TABLE IF NOT EXISTS fact_fts USING fts5(
  fact_id UNINDEXED, text, title, name, quote, content='', tokenize='porter'
);
"""

SQL_REBUILD = """
WITH ev AS (
  SELECT fact_id, group_concat(quote, ' | ') AS quote
  FROM fact_evidence
  GROUP BY fact_id
)
INSERT INTO fact_fts(fact_id, text, title, name, quote)
SELECT f.fact_id,
       COALESCE(json_extract(f.payload,'$.text'), ''),
       COALESCE(NULLIF(json_extract(f.payload,'$.title'), ''), NULLIF(json_extract(f.payload,'$.name'), ''), ''),
       COALESCE(json_extract(f.payload,'$.name'), ''),
       COALESCE(ev.quote, '')
FROM facts f
LEFT JOIN ev ON ev.fact_id = f.fact_id;
"""

def main():
    print("DB:", DB)
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    # Ensure table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fact_fts'")
    has = cur.fetchone() is not None
    if not has:
        print("Creating fact_fts...")
        cur.executescript(SQL_CREATE)
    # Recreate for contentless FTS5
    print("Dropping existing fact_fts (contentless FTS5 cannot DELETE)...")
    cur.execute("DROP TABLE IF EXISTS fact_fts")
    print("Creating fact_fts...")
    cur.executescript(SQL_CREATE)
    print("Rebuilding fact_fts from facts + fact_evidence...")
    cur.executescript(SQL_REBUILD)
    conn.commit()
    # Quick sanity check
    cnt = cur.execute("SELECT count(*) FROM fact_fts").fetchone()[0]
    print("fact_fts rows:", cnt)

if __name__ == '__main__':
    main()
