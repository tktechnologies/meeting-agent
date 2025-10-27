from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence
import json
import re

from . import db_router as db
from .legacy import planner


def _parse_payload(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def _token_set(text: Optional[str]) -> set[str]:
    if not text:
        return set()
    toks = [t for t in re.findall(r"\w+", text.lower()) if len(t) >= 3]
    return set(toks)


def _context_relevance_score(text: str, context_texts: List[str]) -> float:
    if not text or not context_texts:
        return 0.0
    tset = _token_set(text)
    if not tset:
        return 0.0
    cset: set[str] = set()
    for c in context_texts:
        cset |= _token_set(c)
    if not cset:
        return 0.0
    overlap = len(tset & cset)
    return 0.0 if not tset else round(overlap / len(tset), 3)


def _language_for_org(org_id: str) -> str:
    row = db.get_org_context(org_id)
    if row and isinstance(row["language"], str) and row["language"].strip():
        return row["language"].strip()
    return "en-US"


def validate_org_if_needed(
    org_id: str,
    types: Optional[Sequence[str]] = None,
    *,
    max_to_validate: int = 120,
) -> Dict[str, Any]:
    """Auto-validate draft/proposed facts if any exist for the org.

    Heuristic: requires evidence quote present and text quality >= 0.60.
    Uses org/global context for a simple relevance score to avoid irrelevant items.
    """
    db.init_db()
    lang = _language_for_org(org_id)
    # Pull a recent window; we'll filter to draft/proposed
    rows = db.get_recent_facts(org_id, types, limit=max_to_validate)
    if not rows:
        return {"checked": 0, "validated": 0}
    # Filter to candidates needing validation
    need = [r for r in rows if str(r["status"] or "").lower() in {"draft", "proposed"}]
    if not need:
        return {"checked": 0, "validated": 0}
    # Hydrate evidence
    fact_ids = [r["fact_id"] for r in need]
    evidence_map = db.get_evidence_for_fact_ids(fact_ids)
    # Build context corpus
    ctx_row = db.get_org_context(org_id)
    gctx = db.get_global_context("default")
    ctx_texts: List[str] = []
    if ctx_row and isinstance(ctx_row["context_text"], str):
        ctx_texts.append(ctx_row["context_text"])
    if gctx and isinstance(gctx["context_text"], str):
        ctx_texts.append(gctx["context_text"])

    validated = 0
    checked = 0
    CORE = {"decision", "open_question", "question", "risk", "action_item", "milestone"}
    for r in need:
        if validated >= max_to_validate:
            break
        fid = r["fact_id"]
        ftype = (r["fact_type"] or "").lower()
        payload = _parse_payload(r["payload"])
        # Compose a minimal fact dict for planner utilities
        fact_like = {"payload": payload, "fact_id": fid}
        text = planner._abstract_text_from_fact(fact_like, language=lang) or payload.get("text") or ""
        if not text:
            continue
        # Quality gate
        if planner._quality_score(text, lang) < 0.60:
            continue
        # Evidence presence gate
        evs = evidence_map.get(fid, [])
        if not evs or not any((isinstance(ev["quote"], str) and ev["quote"].strip()) for ev in evs):
            continue
        # Context relevance (soft gate): allow core types even with low overlap
        rel = _context_relevance_score(text, ctx_texts)
        if rel < 0.08 and ftype not in CORE:
            continue
        # Promote to validated
        try:
            db.update_fact_status(fid, "validated")
            validated += 1
        except Exception:
            # if concurrent update or invalid id, skip
            continue
        finally:
            checked += 1
    return {"checked": checked, "validated": validated}
