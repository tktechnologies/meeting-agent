from __future__ import annotations

import argparse
import json
import secrets
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# Ensure the meeting-agent root is on sys.path so 'agent' imports work regardless of CWD
MEETING_AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(MEETING_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(MEETING_AGENT_ROOT))

from agent import db
from agent.config import DEFAULT_ORG_ID


def _load_bundle(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Bundle file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Bundle JSON must be an object")
    for key in ("org_id", "meeting", "facts"):
        if key not in data:
            raise ValueError(f"Bundle missing required key '{key}'")
    if not isinstance(data["facts"], list):
        raise ValueError("Bundle 'facts' must be an array")
    return data


def _timecode_to_ms(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    parts = raw.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours = "0"
        minutes, seconds = parts
    else:
        return None
    try:
        h = int(hours)
        m = int(minutes)
        s = int(seconds)
    except ValueError:
        return None
    total_ms = ((h * 60 + m) * 60 + s) * 1000
    return total_ms


def _collect_transcript_ids(facts: Iterable[Dict[str, Any]]) -> List[str]:
    seen: Dict[str, None] = {}
    for fact in facts:
        evidence = fact.get("evidence") or {}
        transcript_id = evidence.get("transcript_id")
        if transcript_id and transcript_id not in seen:
            seen[transcript_id] = None
    return list(seen.keys())


def _ensure_participants(org_id: str, participants: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    entries = list(participants or [])
    if not entries:
        return mapping
    with db.tx() as conn:
        for participant in entries:
            pid = (participant.get("id") or "").strip()
            if not pid:
                continue
            display = (participant.get("display_name") or pid).strip() or pid
            mapping[pid] = display
            conn.execute(
                """
                INSERT INTO entities(entity_id, org_id, type, display_name, external_ids, is_active)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity_id) DO UPDATE SET
                    org_id=excluded.org_id,
                    type=excluded.type,
                    display_name=excluded.display_name,
                    is_active=excluded.is_active
                """,
                (pid, org_id, "person", display, None, 1),
            )
    return mapping


def _make_fact_payload(fact: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "label": fact.get("label"),
        "text": fact.get("text"),
        "attributes": fact.get("attributes"),
        "provenance": fact.get("provenance"),
        "derived_from": fact.get("derived_from"),
    }
    for key in list(payload.keys()):
        if payload[key] is None:
            payload.pop(key)
    payload["bundle_fact_id"] = fact.get("id")
    return payload


def _build_evidence_items(
    fact: Dict[str, Any],
    speaker_id: Optional[str],
    speaker_label: Optional[str],
) -> List[Dict[str, Any]]:
    evidence = fact.get("evidence") or {}
    if not evidence:
        return []
    evidence_id = evidence.get("card_id") or f"{fact.get('id')}:primary"
    char_span = evidence.get("char_span")
    utids = evidence.get("utterance_ids")
    ts_ms = _timecode_to_ms((fact.get("provenance") or {}).get("when_said"))
    return [
        {
            "evidence_id": evidence_id,
            "quote": evidence.get("quote"),
            "who_said_id": speaker_id,
            "who_said_label": speaker_label,
            "ts_start_ms": ts_ms,
            "utterance_ids": utids,
            "char_span": json.dumps(char_span) if isinstance(char_span, (list, tuple)) else None,
            "card_id": evidence.get("card_id"),
        }
    ]


def _link_speaker_entity(
    fact_id: str,
    speaker_id: Optional[str],
    speaker_label: Optional[str],
    org_id: str,
) -> None:
    if not speaker_id:
        return
    db.link_entities(
        fact_id,
        [
            {
                "entity_id": speaker_id,
                "org_id": org_id,
                "type": "person",
                "display_name": speaker_label or speaker_id,
                "role": "speaker",
            }
        ],
    )


def ingest_bundle(
    bundle_path: Path,
    *,
    default_status: str,
    org_name: Optional[str],
    transcript_source: Optional[str],
) -> Dict[str, Any]:
    bundle = _load_bundle(bundle_path)
    org_id = bundle.get("org_id") or DEFAULT_ORG_ID
    meeting = bundle.get("meeting") or {}
    meeting_id = meeting.get("meeting_id")
    meeting_started_at = meeting.get("meeting_started_at")
    participants = meeting.get("participants") or []

    db.init_db()
    # Resolve org conflicts: if a row with the same display name exists under a different org_id,
    # reuse that org_id to avoid FK failures and name UNIQUE conflicts.
    preferred_name = org_name or org_id
    existing = db.get_org(org_id) or db.find_org_by_text(preferred_name)
    if existing:
        existing_id = existing["org_id"]
        if existing_id != org_id:
            org_id = existing_id
    db.ensure_org(org_id, preferred_name)

    participant_lookup = _ensure_participants(org_id, participants)

    transcript_ids = _collect_transcript_ids(bundle.get("facts", []))
    for transcript_id in transcript_ids:
        if not transcript_id:
            continue
        db.record_transcript(
            {
                "transcript_id": transcript_id,
                "org_id": org_id,
                "meeting_id": meeting_id,
                "source": transcript_source or str(bundle_path),
                "created_at": meeting_started_at,
            }
        )

    inserted = 0
    updated = 0

    for fact in bundle.get("facts", []):
        fact_id = fact.get("id") or secrets.token_hex(16)
        fact_type = fact.get("type") or "insight"
        evidence = fact.get("evidence") or {}
        transcript_id = evidence.get("transcript_id")
        speaker_id = (fact.get("provenance") or {}).get("who_said")
        speaker_label = participant_lookup.get(speaker_id, speaker_id)

        existing_rows = db.get_fact_rows([fact_id])
        status = existing_rows[0]["status"] if existing_rows else default_status

        record = {
            "fact_id": fact_id,
            "org_id": org_id,
            "meeting_id": fact.get("meeting_id") or meeting_id,
            "transcript_id": transcript_id,
            "fact_type": fact_type,
            "status": status,
            "confidence": fact.get("confidence"),
            "payload": _make_fact_payload(fact),
            "due_iso": (fact.get("attributes") or {}).get("due_date_iso"),
            "idempotency_key": fact_id,
        }

        db.insert_or_update_fact(record)
        if existing_rows:
            updated += 1
        else:
            inserted += 1

        evidence_items = _build_evidence_items(fact, speaker_id, speaker_label)
        if evidence_items:
            db.add_evidence(fact_id, evidence_items)
        if speaker_id:
            _link_speaker_entity(fact_id, speaker_id, speaker_label, org_id)

    return {
        "org_id": org_id,
        "meeting_id": meeting_id,
        "facts_total": len(bundle.get("facts", [])),
        "inserted": inserted,
        "updated": updated,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest a Spine bundle into the local Spine DB")
    parser.add_argument("bundle", help="Path to spine_bundle.json")
    parser.add_argument(
        "--status",
        default="draft",
        choices=sorted(db.ALLOWED_FACT_STATUSES),
        help="Default status for ingested facts (default: draft)",
    )
    parser.add_argument("--org-name", default=None, help="Optional org display name override")
    parser.add_argument(
        "--transcript-source",
        default=None,
        help="Optional source label stored with transcript rows",
    )
    return parser


def main(argv: Optional[Iterable[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    bundle_path = Path(args.bundle)
    result = ingest_bundle(
        bundle_path,
        default_status=args.status,
        org_name=args.org_name,
        transcript_source=args.transcript_source,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
