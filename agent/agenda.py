import json
from typing import Any, Dict, Optional, Sequence

from . import retrieval
from .legacy import planner
from .legacy import planner_v3
from .legacy import intent as intent_module
from . import db_router as db
from .config import DEFAULT_ORG_ID, MACRO_DEFAULT_MODE, USE_MACRO_PLAN, USE_PLANNER_V3, PLANNER_V3_ORGS
from .nl_parser import parse_nl


DEFAULT_FACT_TYPES: Sequence[str] = planner.DEFAULT_FACT_TYPES


def _should_use_planner_v3(org_id: str) -> bool:
    """Check if planner v3 should be used for this org."""
    if not USE_PLANNER_V3:
        return False
    
    # Check for org-specific rollout
    if PLANNER_V3_ORGS:
        allowed_orgs = [o.strip() for o in PLANNER_V3_ORGS.split(",")]
        return org_id in allowed_orgs
    
    # Default: use v3 for all orgs
    return True


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
    macro_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Plan agenda with optional macro-context layer.
    
    Args:
        macro_mode: "auto" | "strict" | "off"
            - auto (default): try macro path; fallback to micro if no workstreams
            - strict: MUST use workstreams; return nudge if none exist
            - off: bypass macro path entirely (legacy behavior)
    """
    org_id = retrieval.resolve_org_id(org)
    req_subject = subject
    minutes = duration_minutes or 30
    lang = language or "pt-BR"
    
    # Parse NL prompt if provided
    if prompt:
        parsed = parse_nl(prompt, {})
        req_subject = req_subject or parsed.subject
        minutes = duration_minutes or parsed.target_duration_minutes
        lang = language or parsed.language
    
    req_subject = (req_subject or "").strip() or None
    types = list(fact_types or DEFAULT_FACT_TYPES)
    
    # Determine macro mode
    mode = macro_mode or MACRO_DEFAULT_MODE
    if not USE_MACRO_PLAN:
        mode = "off"
    
    # Macro planning path
    if mode in ("auto", "strict"):
        # Select workstreams
        workstreams = retrieval.select_workstreams(org_id, req_subject, k=3)
        
        if workstreams:
            # Check if we should use planner v3
            use_v3 = _should_use_planner_v3(org_id)
            
            if use_v3:
                # Use new intent-driven planner
                # Detect intent
                detected_intent = intent_module.MeetingIntent.detect_intent(
                    req_subject, workstreams, [], lang
                )
                
                # Enrich subject if needed
                enriched_subject = intent_module.MeetingIntent.enrich_subject(
                    req_subject, detected_intent, workstreams, lang
                )
                
                # Get actionable facts
                actionable_facts = retrieval.select_actionable_facts(
                    org_id, enriched_subject, detected_intent, workstreams, lang, limit=40
                )
                
                # If no actionable facts found, try broader subject-based search
                if not actionable_facts and enriched_subject:
                    subject_facts = retrieval.retrieve_facts_for_subject(
                        org_id, enriched_subject, limit=30, language=lang
                    )
                    # Use top facts as actionable with lower urgency
                    actionable_facts = subject_facts[:20]
                
                # Plan with v3
                proposal = planner_v3.plan_agenda_v3(
                    org_id, enriched_subject, detected_intent, workstreams,
                    actionable_facts, minutes, lang
                )
                
                return {"org_id": org_id, "subject": enriched_subject, "proposal": proposal}
            
            # Legacy path: use old planner
            # Get facts for workstreams
            facts = retrieval.facts_for_workstreams(org_id, workstreams, per_ws=20)
            
            # If subject-specific and no facts, optionally include draft/proposed for that subject
            if req_subject and not facts:
                # Try micro search with subject including draft/proposed
                subject_facts = retrieval.retrieve_facts_for_subject(
                    org_id, req_subject, limit=40, language=lang
                )
                # Mark these as subject-specific in metadata
                for f in subject_facts:
                    if f.get("status") in ("draft", "proposed"):
                        f["_subject_fallback"] = True
                facts = subject_facts
            
            # Plan from workstreams
            proposal = planner.plan_agenda_from_workstreams(
                org_id, workstreams, facts, minutes, lang
            )
            
            # Add subject to proposal if provided
            if req_subject:
                proposal["subject"]["query"] = req_subject
            
            return {"org_id": org_id, "subject": req_subject, "proposal": proposal}
        
        # No workstreams found
        if mode == "strict":
            # Return empty structure with nudge
            return {
                "org_id": org_id,
                "subject": req_subject,
                "proposal": {
                    "agenda": {
                        "title": "Criar contexto macro" if lang == "pt-BR" else "Create macro context",
                        "minutes": minutes,
                        "sections": [],
                        "_metadata": {
                            "agenda_v": "2.0",
                            "nudge": "macro_context_missing",
                            "workstreams": [],
                            "refs": [],
                        },
                    },
                    "choice": "macro-strict-empty",
                    "reason": "No workstreams available; macro=strict requires workstreams",
                    "subject": {"query": req_subject, "coverage": 0.0, "facts": 0},
                    "supporting_fact_ids": [],
                },
            }
        
        # mode == "auto": fall through to legacy path
    
    # Legacy micro-only path (mode == "off" or auto fallback)
    # Infer subject if missing or generic
    if not req_subject or retrieval.looks_generic_subject(req_subject, lang):
        inferred = retrieval.infer_best_subject(org_id, language=lang)
        if inferred:
            req_subject = inferred
    
    # Fetch candidates
    candidates = retrieval.find_candidates_for_agenda(org_id, req_subject, types, limit=80)
    
    # Get company context if not provided
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
    
    # Add nudge if using legacy fallback but macro is available
    if mode == "auto" and USE_MACRO_PLAN:
        if "_metadata" not in proposal.get("agenda", {}):
            proposal.setdefault("agenda", {})["_metadata"] = {}
        proposal["agenda"]["_metadata"]["nudge"] = "macro_context_missing"
    
    return {"org_id": org_id, "subject": req_subject, "proposal": proposal}
