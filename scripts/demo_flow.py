from __future__ import annotations

import json
from pprint import pprint

from agent import agenda, db
from agent.config import DEFAULT_ORG_ID
from .seed import run as seed_run


def main() -> None:
    db.init_db()
    seed_result = seed_run(DEFAULT_ORG_ID)
    print(f"Seed complete: {len(seed_result['facts'])} facts for org {seed_result['org_id']}")

    proposal = agenda.propose_agenda(
        org=seed_result['org_id'],
        subject="Q4 kickoff planning",
        meeting_id="demo-flow-meeting",
        transcript_id=seed_result['transcript_id'],
    )
    print("\nAgenda proposal persisted:")
    pprint(proposal['proposal_preview'])

    listing = agenda.list_agenda_proposals(seed_result['org_id'], limit=5)
    print("\nRecent agenda proposals:")
    print(json.dumps(listing, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
