from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Optional

from agent import db_router as db
from agent.config import DB_PATH
from .ingest_bundle import ingest_bundle


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Create/upgrade Spine DB and store items from a Spine bundle."
    )
    p.add_argument(
        "bundle",
        help="Path to spine_bundle.json (produced by parsing-agent)",
    )
    p.add_argument(
        "--status",
        default="draft",
        choices=sorted(db.ALLOWED_FACT_STATUSES),
        help="Default status for ingested facts (default: draft)",
    )
    p.add_argument(
        "--org-name",
        default=None,
        help="Optional org display name override",
    )
    p.add_argument(
        "--transcript-source",
        default=None,
        help="Optional source label stored with transcript rows",
    )
    return p


def main(argv: Optional[Iterable[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Ensure database exists and is up to date
    db.init_db()

    result = ingest_bundle(
        Path(args.bundle),
        default_status=args.status,
        org_name=args.org_name,
        transcript_source=args.transcript_source,
    )

    summary = {
        "db_path": DB_PATH,
        **result,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
