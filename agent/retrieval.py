import json
from typing import Any, Dict, List, Optional, Sequence, Tuple
import re

from .config import DEFAULT_ORG_ID
from . import db


Candidate = Dict[str, Any]


def _row_to_dict(row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def _parse_payload(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def resolve_org_id(text_or_id: Optional[str]) -> str:
    candidate = (text_or_id or "").strip()
    if candidate:
        row = db.get_org(candidate)
        if row:
            return row["org_id"]
        row = db.find_org_by_text(candidate)
        if row:
            return row["org_id"]
        db.ensure_org(candidate, candidate)
        return candidate
    db.ensure_org(DEFAULT_ORG_ID, DEFAULT_ORG_ID)
    return DEFAULT_ORG_ID


def _hydrate_related(fact_ids: Sequence[str]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    evidence_map = db.get_evidence_for_fact_ids(fact_ids)
    entities_map = db.get_entities_for_fact_ids(fact_ids)
    evidence_payload = {fid: [_row_to_dict(r) for r in rows] for fid, rows in evidence_map.items()}
    entities_payload = {
        fid: [{k: row[k] for k in row.keys() if k != "fact_id"} for row in rows]
        for fid, rows in entities_map.items()
    }
    return {"evidence": evidence_payload, "entities": entities_payload}


def find_candidates_for_agenda(
    org_id: str,
    subject: Optional[str],
    types: Sequence[str],
    limit: int = 60,
) -> List[Candidate]:
    org_id = org_id or DEFAULT_ORG_ID
    # Primary: subject search (FTS/LIKE)
    rows = db.search_facts(org_id, subject or "", types, limit) if subject else None
    # Fallback 1: tokenized FTS OR search
    if subject and not rows:
        # keep tokens with >=3 chars, alnum
        tokens = [t for t in re.findall(r"\w+", subject.lower()) if len(t) >= 3]
        # de-dup while preserving order
        seen = set()
        toks = []
        for t in tokens:
            if t not in seen:
                seen.add(t)
                toks.append(t)
        if toks:
            or_query = " OR ".join(toks)
            rows = db.search_facts(org_id, or_query, types, limit)
    # Fallback 2: recent facts
    if not rows:
        rows = db.get_recent_facts(org_id, types, limit)
    # Diversify: ensure we have some of each core category to help build sections
    if rows:
        got = {r["fact_type"].lower() for r in rows if r["fact_type"]}
        core_needs = [
            ("decision", 4), ("question", 6), ("risk", 4), ("process_step", 6), ("action_item", 6), ("metric", 4)
        ]
        augmented: List[Any] = list(rows)
        for t, extra in core_needs:
            if t not in got:
                extra_rows = db.get_recent_facts(org_id, [t], extra)
                augmented.extend(extra_rows)
        # De-duplicate by fact_id preserving order
        seen = set()
        uniq: List[Any] = []
        for r in augmented:
            fid = r["fact_id"]
            if fid not in seen:
                seen.add(fid)
                uniq.append(r)
        rows = uniq[: limit]
    if not rows:
        return []
    fact_ids = [row["fact_id"] for row in rows]
    related = _hydrate_related(fact_ids)
    evidence_map = related["evidence"]
    entities_map = related["entities"]
    candidates: List[Candidate] = []
    for row in rows:
        row_dict = _row_to_dict(row)
        payload = _parse_payload(row_dict.get("payload"))
        fid = row_dict["fact_id"]
        data: Candidate = {
            "fact_id": fid,
            "org_id": row_dict["org_id"],
            "meeting_id": row_dict.get("meeting_id"),
            "transcript_id": row_dict.get("transcript_id"),
            "fact_type": row_dict["fact_type"],
            "status": row_dict["status"],
            "confidence": row_dict.get("confidence"),
            "payload": payload,
            "due_iso": row_dict.get("due_iso"),
            "due_at": row_dict.get("due_at"),
            "created_at": row_dict.get("created_at"),
            "updated_at": row_dict.get("updated_at"),
            "evidence": evidence_map.get(fid, []),
            "entities": entities_map.get(fid, []),
        }
        if "fts_score" in row_dict:
            data["fts_score"] = row_dict["fts_score"]
        candidates.append(data)
    return candidates


# --- Subject inference for next-meeting planning ---

def _extract_subject_text(payload: Dict[str, Any], evidence: List[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(payload, dict):
        payload = {}
    for k in ("subject", "title", "name", "headline", "summary", "text"):
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            s = v.strip()
            # Trim to a reasonable length
            return (s if len(s) <= 160 else (s[:159] + "…"))
    if evidence:
        q = evidence[0].get("quote")
        if isinstance(q, str) and q.strip():
            s = q.strip()
            return (s if len(s) <= 160 else (s[:159] + "…"))
    return None


def _normalize_key(s: str) -> str:
    return (s or "").strip().lower().rstrip(".:;?!")


def infer_candidate_subjects(
    org_id: str,
    *,
    types: Optional[Sequence[str]] = None,
    limit: int = 120,
) -> List[Tuple[str, float]]:
    """Return candidate subjects with scores from recent facts.

    Score combines type weight and simple recency rank. Output is list of (text, score).
    """
    # Prefer forward-looking relevant types first but keep broad
    type_order = [
        "topic", "insight", "requirement", "decision", "question",
        "process_step", "dependency", "metric", "reference", "action_item", "milestone",
    ]
    types = list(types or type_order)
    rows = db.get_recent_facts(org_id or DEFAULT_ORG_ID, types, limit)
    if not rows:
        return []
    fact_ids = [r["fact_id"] for r in rows]
    related = _hydrate_related(fact_ids)
    ev_map = related["evidence"]
    # Weights by type
    w = {
        "topic": 3.0,
        "insight": 2.5,
        "requirement": 2.0,
        "decision": 2.0,
        "question": 1.8,
        "process_step": 1.6,
        "dependency": 1.6,
        "action_item": 1.7,
        "milestone": 1.7,
        "metric": 1.5,
        "reference": 1.2,
    }
    scores: Dict[str, float] = {}
    texts: Dict[str, str] = {}
    N = max(1, len(rows))
    for idx, r in enumerate(rows):  # rows assumed newest first
        ftype = (r["fact_type"] or "").lower()
        payload = _parse_payload(r["payload"])
        fid = r["fact_id"]
        ev = ev_map.get(fid, [])
        text = _extract_subject_text(payload, ev)
        if not text:
            continue
        key = _normalize_key(text)
        if not key or len(key) < 6 or len(key.split()) < 2:
            continue
        base = w.get(ftype, 1.0)
        recency = (N - idx) / N  # 0..1
        score = base + 0.8 * recency
        scores[key] = scores.get(key, 0.0) + score
        texts.setdefault(key, text)
    # Sort candidates
    items = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [(texts[k], s) for k, s in items]


def looks_generic_subject(subject: Optional[str], language: str = "en-US") -> bool:
    s = (subject or "").strip().lower()
    if not s:
        return True
    pats_pt = [
        r"^fa[cç]a a pauta", r"^crie a pauta", r"^fazer a pauta", r"^montar a pauta", r"pr[óo]xima reuni[ãa]o",
    ]
    pats_en = [
        r"^make the agenda", r"^create the agenda", r"^build the agenda", r"next meeting",
    ]
    pats = pats_pt if language == "pt-BR" else pats_en
    return any(re.search(p, s) for p in pats)


def infer_best_subject(org_id: str, *, language: str = "en-US") -> Optional[str]:
    """Pick and synthesize a subject from recent facts for the next meeting."""
    cands = infer_candidate_subjects(org_id)
    if not cands:
        return None
    top_texts = [t for (t, _s) in cands[:5] if isinstance(t, str) and t.strip()]
    subject = synthesize_subject_from_texts(top_texts, language=language)
    if subject and not looks_generic_subject(subject, language):
        return subject
    # Fallbacks: return refined top candidate
    for text in top_texts:
        refined = refine_subject_text(text, language)
        if refined and not looks_generic_subject(refined, language):
            return refined
    return refine_subject_text(cands[0][0], language)


# --- Subject synthesis utilities ---

_PT_FILLERS = [
    r"^temos\s+um[au]?\s+",
    r"^tem\s+um[au]?\s+",
    r"^estamos\s+",
    r"^a\s+gente\s+",
    r"^vamos\s+",
    r"^que\s+fala\s+s[oó]\s+de\s+",
]
_PT_TAILS = [
    r"\b(a|à)\s+medida\s+em?\s+que\b.*$",
    r"\bquando\b.*$",
    r"\bse\b.*$",
]
_EN_FILLERS = [
    r"^we\s+have\s+",
    r"^there\s+is\s+",
    r"^we're\s+",
    r"^we\s+are\s+",
]
_EN_TAILS = [
    r"\bwhen\b.*$",
    r"\bif\b.*$",
]


def refine_subject_text(text: str, language: str = "en-US") -> str:
    s = (text or "").strip()
    if not s:
        return ""
    import re
    fillers = _PT_FILLERS if language == "pt-BR" else _EN_FILLERS
    tails = _PT_TAILS if language == "pt-BR" else _EN_TAILS
    for p in fillers:
        s = re.sub(p, "", s, flags=re.IGNORECASE)
    for p in tails:
        s = re.sub(p, "", s, flags=re.IGNORECASE)
    s = s.strip().strip("…").strip(" .,:-;")
    # Shorten to a concise phrase
    if len(s) > 72:
        # Prefer cutting at a comma or ' e ' / ' and '
        cut_points = []
        for token in ([",", " e "] if language == "pt-BR" else [",", " and "]):
            idx = s.lower().find(token)
            if 0 < idx < 72:
                cut_points.append(idx)
        if cut_points:
            s = s[: max(cut_points)]
        else:
            s = s[:72].rstrip()
    # Capitalize first letter
    if s:
        s = s[0].upper() + s[1:]
    return s


def synthesize_subject_from_texts(texts: Sequence[str], *, language: str = "en-US") -> Optional[str]:
    import re
    toks: List[str] = []
    for t in texts:
        t = refine_subject_text(t, language)
        # Tokenize words
        for w in re.findall(r"[\wÀ-ÿ]+", t, flags=re.IGNORECASE):
            if len(w) >= 3:
                toks.append(w.lower())
    if not toks:
        return None
    # Stopwords
    stop_pt = {"de","da","do","das","dos","e","em","para","por","que","uma","um","uns","umas","na","no","nas","nos","com","sobre","ao","a","o","as","os"}
    stop_en = {"the","and","for","with","a","an","of","in","on","to","by","about","from","as","at","is","are"}
    stop = stop_pt if language == "pt-BR" else stop_en
    # Count frequencies
    from collections import Counter
    freq = Counter([w for w in toks if w not in stop])
    if not freq:
        return None
    # Pick top 3-6 content words
    top_words = [w for (w, _c) in freq.most_common(6)]
    if language == "pt-BR":
        # Build a concise noun-phrase-like subject
        phrase = " ".join(top_words[:3])
        return phrase.capitalize()
    else:
        phrase = " ".join(top_words[:3])
        return phrase.title()
