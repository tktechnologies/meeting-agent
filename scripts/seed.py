from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from agent import db_router as db
from agent.config import DEFAULT_ORG_ID


def _ensure_transcript(org_id: str) -> str:
    payload = {
        "transcript_id": "seed-transcript",
        "org_id": org_id,
        "meeting_id": "meeting-seed",
        "source": "seed-demo",
        "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return db.record_transcript(payload)


def run(org_id: str | None = None) -> Dict[str, Any]:
    target_org = (org_id or DEFAULT_ORG_ID).strip() or DEFAULT_ORG_ID
    db.init_db()
    db.ensure_org(target_org, "Demo Org")
    transcript_id = _ensure_transcript(target_org)

    now = datetime.utcnow()
    due_soon = (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    facts: List[Dict[str, Any]] = [
        {
            "meeting_id": "meeting-seed",
            "transcript_id": transcript_id,
            "fact_type": "decision",
            "status": "validated",
            "confidence": 0.85,
            "payload": {
                "title": "Adopt usage-based pricing for Q4",
                "summary": "Leadership approved adding a usage-based tier for enterprise customers.",
                "owner": "Revenue Ops",
                "subject": "Pricing strategy",
            },
            "idempotency_key": "seed::decision::usage-pricing",
            "evidence": [
                {
                    "quote": "Let's proceed with usage-based pricing next quarter for the enterprise plans.",
                    "who_said_label": "CEO",
                    "ts_start_ms": 128000,
                }
            ],
            "entities": [
                {"type": "person", "display_name": "Laura CEO"},
                {"type": "team", "display_name": "Revenue Ops"},
            ],
        },
        {
            "meeting_id": "meeting-seed",
            "transcript_id": transcript_id,
            "fact_type": "action_item",
            "status": "proposed",
            "confidence": 0.9,
            "payload": {
                "title": "Prepare Q4 kickoff deck",
                "summary": "Draft slides highlighting roadmap, pricing changes, and onboarding metrics.",
                "owner": "Lina PM",
            },
            "due_iso": due_soon,
            "idempotency_key": "seed::action_item::kickoff-deck",
            "evidence": [
                {
                    "quote": "Lina, can you pull together the Q4 kickoff deck with the pricing updates?",
                    "who_said_label": "COO",
                    "ts_start_ms": 185000,
                }
            ],
            "entities": [
                {"type": "person", "display_name": "Lina PM"},
                {"type": "team", "display_name": "Product"},
            ],
        },
        {
            "meeting_id": "meeting-seed",
            "transcript_id": transcript_id,
            "fact_type": "risk",
            "status": "draft",
            "confidence": 0.6,
            "payload": {
                "title": "Onboarding backlog is growing",
                "text": "Customer onboarding backlog exceeds SLA by 4 days; may impact renewals.",
            },
            "idempotency_key": "seed::risk::onboarding-backlog",
            "evidence": [
                {
                    "quote": "We're now four days behind on onboarding tasks for enterprise customers.",
                    "who_said_label": "CX Lead",
                    "ts_start_ms": 223000,
                }
            ],
            "entities": [
                {"type": "team", "display_name": "Customer Experience"},
            ],
        },
        {
            "meeting_id": "meeting-seed",
            "transcript_id": transcript_id,
            "fact_type": "question",
            "status": "proposed",
            "confidence": 0.7,
            "payload": {
                "title": "Do we need legal sign-off for the new pricing?",
                "text": "Legal impact needs confirmation before launch.",
            },
            "idempotency_key": "seed::question::legal-signoff",
            "evidence": [
                {
                    "quote": "Double-check with legal if the usage-based pricing needs a contract addendum.",
                    "who_said_label": "Sales Director",
                    "ts_start_ms": 241000,
                }
            ],
            "entities": [
                {"type": "team", "display_name": "Legal"},
            ],
        },
        {
            "meeting_id": "meeting-seed",
            "transcript_id": transcript_id,
            "fact_type": "topic",
            "status": "published",
            "confidence": 0.75,
            "payload": {
                "title": "Customer health metrics",
                "text": "Review churn, NPS, and onboarding velocity for top accounts.",
            },
            "idempotency_key": "seed::topic::customer-health",
            "evidence": [
                {
                    "quote": "Let's review churn, NPS, and onboarding velocity so we know where to focus.",
                    "who_said_label": "CEO",
                    "ts_start_ms": 99000,
                }
            ],
            "entities": [
                {"type": "team", "display_name": "Customer Success"},
            ],
        },
    ]

    created = []
    for entry in facts:
        evidence = entry.pop("evidence", [])
        entities = entry.pop("entities", [])
        entry["org_id"] = target_org
        fact_id = db.insert_or_update_fact(entry)
        if evidence:
            db.add_evidence(fact_id, evidence)
        if entities:
            db.link_entities(fact_id, entities)
        created.append({"fact_id": fact_id, "fact_type": entry["fact_type"]})
    return {"org_id": target_org, "facts": created, "transcript_id": transcript_id}


if __name__ == "__main__":
    result = run()
    print(
        f"Seeded {len(result['facts'])} facts for org {result['org_id']} "
        f"(transcript {result['transcript_id']})."
    )
