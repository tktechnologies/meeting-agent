#!/usr/bin/env python3
import argparse
import os
import sqlite3
import sys
from pathlib import Path


def resolve_db_path() -> str:
    # First: env var used by the agent
    env_db = os.getenv("SPINE_DB_PATH")
    if env_db and env_db.strip():
        return os.path.abspath(env_db)
    # Second: try importing agent.config regardless of CWD by adding parent dir
    this_dir = Path(__file__).resolve().parent
    meeting_agent_root = this_dir.parent
    sys.path.insert(0, str(meeting_agent_root))
    try:
        from agent.config import spine_db_path  # type: ignore
        return spine_db_path()
    except Exception:
        pass
    # Fallback: default dev DB at meeting-agent root
    return str(meeting_agent_root / "spine_dev.sqlite3")


def q(cur: sqlite3.Cursor, sql: str, *args):
    try:
        cur.execute(sql, args)
        return cur.fetchall()
    except Exception as e:
        print("ERR", type(e).__name__, e, "SQL=", sql)
        return []


def main():
    parser = argparse.ArgumentParser(description="Inspect Spine SQLite DB contents")
    parser.add_argument("--org", default=None, help="Filter stats to a specific org id")
    parser.add_argument("--limit", type=int, default=10, help="Sample size for fact listings (default 10)")
    args = parser.parse_args()

    db_path = resolve_db_path()
    print("DB path:", db_path)
    if not os.path.exists(db_path):
        print("DB file not found")
        return
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("\n== tables ==")
    for r in q(cur, "select name from sqlite_master where type in ('table','view') order by name"):
        print("-", r["name"])

    orgs = q(cur, "select org_id, name from orgs order by name")
    print("\n== orgs ==", len(orgs))
    for r in orgs[:10]:
        print("-", r["name"], r["org_id"])

    cnt_rows = q(cur, "select count(*) as c from facts")
    cnt = cnt_rows[0]["c"] if cnt_rows else 0
    print("\n== facts count ==", cnt)
    recent60 = q(cur, "select count(*) as c from facts where created_at >= datetime('now','-60 days')")
    print("recent (60d):", (recent60[0]["c"] if recent60 else 0))

    if args.org:
        print(f"\n== fact types for org '{args.org}' ==")
        for r in q(cur, "select fact_type, count(*) as c from facts where org_id=? group by fact_type order by c desc", args.org):
            print("-", r["fact_type"], r["c"])
    else:
        print("\n== fact types ==")
        for r in q(cur, "select fact_type, count(*) as c from facts group by fact_type order by c desc"):
            print("-", r["fact_type"], r["c"])

    fts = q(cur, "select name from sqlite_master where name='fact_fts'")
    print("\n== fts table ==", bool(fts))
    if fts:
        org_for_test = args.org
        if not org_for_test and orgs:
            org_for_test = orgs[0]["org_id"]
        print("org for filtered tests:", org_for_test)
        for token in ["SSO", "proposta", "orçamento", "contrato", "onboarding", "parceria"]:
            rows = q(cur, "SELECT count(*) as c FROM fact_fts WHERE fact_fts MATCH ?", token)
            c_all = rows[0]["c"] if rows else "ERR"
            print(f"fts(match any) '{token}':", c_all, end="")
            if org_for_test:
                rows2 = q(
                    cur,
                    "SELECT count(*) as c FROM facts f JOIN fact_fts ON fact_fts.fact_id=f.fact_id "
                    "WHERE f.org_id=? AND fact_fts MATCH ? AND f.created_at >= datetime('now','-60 days')",
                    org_for_test,
                    token,
                )
                c_filt = rows2[0]["c"] if rows2 else "ERR"
                print(" | filtered(60d, org):", c_filt)
            else:
                print()

    print("\n== sample facts ==")
    if args.org:
        rows = q(cur, "SELECT fact_id, fact_type, substr(payload,1,160) as p FROM facts WHERE org_id=? order by created_at desc limit ?", args.org, args.limit)
    else:
        rows = q(cur, "SELECT fact_id, fact_type, substr(payload,1,160) as p FROM facts order by created_at desc limit ?", args.limit)
    for r in rows:
        print(r["fact_id"], r["fact_type"], r["p"])


if __name__ == "__main__":
    main()
