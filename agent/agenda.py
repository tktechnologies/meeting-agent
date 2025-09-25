import json
from typing import Any, Dict, Optional, Sequence

from . import db, planner, retrieval
from .config import DEFAULT_ORG_ID
from .nl_parser import parse_nl


DEFAULT_FACT_TYPES: Sequence[str] = planner.DEFAULT_FACT_TYPES


def _load_fact_snapshot(fact_id: str) -> Optional[Dict[str, Any]]:
    rows = db.get_fact_rows([fact_id])
    if not rows:
        return None
    row = rows[0]
    payload = row["payload"]
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    snapshot = {
        "fact_id": row["fact_id"],
        "org_id": row["org_id"],
        "meeting_id": row["meeting_id"],
        "transcript_id": row["transcript_id"],
        "status": row["status"],
        "confidence": row["confidence"],
        "payload": payload,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    return snapshot


def propose_agenda(
    *,
    org: Optional[str] = None,
    subject: Optional[str] = None,
    prompt: Optional[str] = None,
    meeting_id: Optional[str] = None,
    transcript_id: Optional[str] = None,
    duration_minutes: Optional[int] = None,
    language: Optional[str] = None,
    fact_types: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    org_id = retrieval.resolve_org_id(org)
    req_subject = subject
    minutes = duration_minutes or 30
    lang = language or "pt-BR"
    if prompt:
        parsed = parse_nl(prompt, {})
        req_subject = req_subject or parsed.subject
        minutes = duration_minutes or parsed.target_duration_minutes
        lang = language or parsed.language
    req_subject = (req_subject or "").strip() or None
    types = list(fact_types or DEFAULT_FACT_TYPES)
    candidates = retrieval.find_candidates_for_agenda(org_id, req_subject, types, limit=60)
    proposal = planner.plan_agenda(org_id, req_subject, candidates, duration_minutes=minutes, language=lang)
    fact_id = planner.persist_agenda_proposal(org_id, proposal, meeting_id=meeting_id, transcript_id=transcript_id)
    snapshot = _load_fact_snapshot(fact_id)
    proposal_preview = {
        "agenda": proposal.get("agenda"),
        "choice": proposal.get("choice"),
        "reason": proposal.get("reason"),
        "subject": proposal.get("subject"),
        "fact_id": fact_id,
        "org_id": org_id,
    }
    if snapshot:
        proposal_preview["status"] = snapshot.get("status")
        proposal_preview["created_at"] = snapshot.get("created_at")
        proposal_preview["updated_at"] = snapshot.get("updated_at")
    return {
        "fact_id": fact_id,
        "proposal_preview": proposal_preview,
        "snapshot": snapshot,
    }


def plan_agenda_only(
    *,
    org: Optional[str] = None,
    subject: Optional[str] = None,
    prompt: Optional[str] = None,
    duration_minutes: Optional[int] = None,
    language: Optional[str] = None,
    fact_types: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Plan an agenda using recent facts without persisting anything.

    Returns a proposal object with agenda sections and metadata.
    """
    org_id = retrieval.resolve_org_id(org)
    req_subject = subject
    minutes = duration_minutes or 30
    lang = language or "pt-BR"
    if prompt:
        parsed = parse_nl(prompt, {})
        req_subject = req_subject or parsed.subject
        minutes = duration_minutes or parsed.target_duration_minutes
        lang = language or parsed.language
    req_subject = (req_subject or "").strip() or None
    types = list(fact_types or DEFAULT_FACT_TYPES)
    candidates = retrieval.find_candidates_for_agenda(org_id, req_subject, types, limit=60)
    proposal = planner.plan_agenda(org_id, req_subject, candidates, duration_minutes=minutes, language=lang)
    return {
        "org_id": org_id,
        "subject": req_subject,
        "proposal": proposal,
    }


def list_agenda_proposals(org: Optional[str], limit: int = 20) -> Dict[str, Any]:
    org_id = retrieval.resolve_org_id(org)
    rows = db.get_agenda_proposals(org_id, limit)
    items = []
    for row in rows:
        payload = row["payload"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
        items.append({
            "fact_id": row["fact_id"],
            "status": row["status"],
            "payload": payload,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        })
    return {"org_id": org_id, "items": items}


def plan_agenda_next_only(
    *,
    org: Optional[str] = None,
    subject: Optional[str] = None,
    prompt: Optional[str] = None,
    company_context: Optional[str] = None,
    duration_minutes: Optional[int] = None,
    language: Optional[str] = None,
    fact_types: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    org_id = retrieval.resolve_org_id(org)
    req_subject = subject
    minutes = duration_minutes or 30
    lang = language or "pt-BR"
    # Optional natural language prompt parsing (consistent with propose/only variants)
    if prompt:
        parsed = parse_nl(prompt, {})
        req_subject = req_subject or parsed.subject
        minutes = duration_minutes or parsed.target_duration_minutes
        lang = language or parsed.language
    req_subject = (req_subject or "").strip() or None
    types = list(fact_types or DEFAULT_FACT_TYPES)
    # If no specific subject or a generic one is provided, infer a likely next subject
    if not req_subject or retrieval.looks_generic_subject(req_subject, lang):
        inferred = retrieval.infer_best_subject(org_id, language=lang)
        if inferred:
            req_subject = inferred
    # Fetch candidates centered around the subject (inferred or explicit), with fallbacks inside
    candidates = retrieval.find_candidates_for_agenda(org_id, req_subject, types, limit=80)
    if not company_context:
        gctx = db.get_global_context("default")
        if gctx and isinstance(gctx["context_text"], str) and gctx["context_text"].strip():
            company_context = gctx["context_text"]
        else:
            ctx_row = db.get_org_context(org_id)
            if ctx_row and isinstance(ctx_row["context_text"], str) and ctx_row["context_text"].strip():
                company_context = ctx_row["context_text"]
    proposal = planner.plan_agenda_next(
        org_id,
        req_subject,
        candidates,
        company_context=company_context,
        duration_minutes=minutes,
        language=lang,
    )
    return {"org_id": org_id, "subject": req_subject, "proposal": proposal}
