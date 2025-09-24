import json
from typing import Any, Dict, List, Optional, Sequence, Tuple
import re

from .config import DEFAULT_ORG_ID
from . import db
from . import auto_validate


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
    # Opportunistic auto-validation pass: if there are draft/proposed facts, try to validate a few
    try:
        recent = db.get_recent_facts(org_id, types, limit=60)
        if any(str(r["status"] or "").lower() in {"draft", "proposed"} for r in recent):
            auto_validate.validate_org_if_needed(org_id, types)
    except Exception:
        # non-fatal: continue if auto-validate fails
        pass
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
    # Keep only vetted facts for agenda planning
    if rows:
        rows = [r for r in rows if (str(r["status"] or "").lower() in {"validated", "published"})]
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
                # filter augmented rows to vetted statuses only
                extra_rows = [er for er in extra_rows if (str(er["status"] or "").lower() in {"validated", "published"})]
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
    # Bias core actionable types to the top
    core_order = {"decision": 0, "open_question": 1, "question": 2, "risk": 3, "action_item": 4, "milestone": 5}
    candidates.sort(key=lambda c: core_order.get((c.get("fact_type") or "").lower(), 99))
    return candidates


# --- Subject-first helpers ---

def _days_between_iso(now_iso: Optional[str], past_iso: Optional[str]) -> Optional[float]:
    from datetime import datetime, timezone
    def parse(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        try:
            # Support both Z and offsetless
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    now = parse(now_iso) or datetime.utcnow().replace(tzinfo=timezone.utc)
    past = parse(past_iso)
    if not past:
        return None
    return (now - past).total_seconds() / 86400.0


def _urgency_from_due(due_iso: Optional[str]) -> float:
    # Map due in days to 0..1 with simple bands
    if not due_iso:
        return 0.1
    from datetime import datetime, timezone
    try:
        due = datetime.fromisoformat(due_iso.replace("Z", "+00:00"))
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        delta_days = (due - now).total_seconds() / 86400.0
    except Exception:
        return 0.1
    if delta_days <= 0:
        return 1.0
    if delta_days <= 3:
        return 0.9
    if delta_days <= 7:
        return 0.7
    if delta_days <= 14:
        return 0.5
    return 0.3


def find_subject_candidates(org_id: str, lookback_days: int = 30, k: int = 5, language: str = "auto") -> list[dict]:
    org_id = org_id or DEFAULT_ORG_ID
    rows = db.get_recent_facts(org_id, ["decision", "open_question", "risk", "action_item", "milestone"], 300)
    if not rows:
        return []
    # Keep only vetted
    rows = [r for r in rows if (str(r["status"] or "").lower() in {"validated", "published"})]
    if not rows:
        return []
    # Optional lookback filter
    from datetime import datetime, timezone, timedelta
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    def _within(row):
        try:
            ts = datetime.fromisoformat((row["created_at"] or "").replace("Z", "+00:00"))
            return (now - ts) <= timedelta(days=lookback_days)
        except Exception:
            return True
    rows = [r for r in rows if _within(r)]
    if not rows:
        return []
    # Hydrate related
    fact_ids = [r["fact_id"] for r in rows]
    related = _hydrate_related(fact_ids)
    ev_map = related["evidence"]

    # Build simple theme clusters by normalized text key (first sentence refined)
    from collections import defaultdict
    clusters: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        ftype = (r["fact_type"] or "").lower()
        fid = r["fact_id"]
        payload = _parse_payload(r["payload"])  # type: ignore[arg-type]
        # Avoid evidence quotes when forming subjects; prefer payload fields only
        text = _extract_subject_text(payload, []) or (payload.get("text") or "")
        text = refine_subject_text(text, language=(language if language != "auto" else (db.get_org_context(org_id)["language"] if db.get_org_context(org_id) else "en-US")))  # type: ignore[index]
        key = _normalize_key(text)
        if not key:
            continue
        c = clusters.get(key)
        if not c:
            due_val = r["due_iso"] if "due_iso" in r.keys() else None
            conf_val = r["confidence"] if "confidence" in r.keys() else 0.6
            created_val = r["created_at"] if "created_at" in r.keys() else None
            clusters[key] = {
                "text": text,
                "fact_types": {ftype: 1},
                "supporting_fact_ids": [fid],
                "due_list": [due_val],
                "conf": [conf_val],
                "created": [created_val],
            }
        else:
            c["fact_types"][ftype] = c["fact_types"].get(ftype, 0) + 1
            c["supporting_fact_ids"].append(fid)
            c["due_list"].append(r["due_iso"] if "due_iso" in r.keys() else None)
            c["conf"].append(r["confidence"] if "confidence" in r.keys() else 0.6)
            c["created"].append(r["created_at"] if "created_at" in r.keys() else None)

    # Score clusters
    def _type_impact(ft_counts: Dict[str, int]) -> float:
        w = {"decision": 1.0, "open_question": 0.8, "risk": 0.9, "action_item": 0.7, "milestone": 0.9}
        num = sum(ft_counts.values()) or 1
        return sum(w.get(t, 0.5) * n for t, n in ft_counts.items()) / num

    cands: List[Dict[str, Any]] = []
    for key, c in clusters.items():
        due = None
        # earliest due in cluster
        dues = [d for d in c["due_list"] if d]
        if dues:
            due = sorted(dues)[0]
        urgency = _urgency_from_due(due)
        impact = _type_impact(c["fact_types"])  # average type weight
        # recency = newest item is best
        newest = None
        created = [dt for dt in c["created"] if dt]
        if created:
            newest = max(created)
        days = _days_between_iso(None, newest) if newest else 30.0
        recency = 1.0 / (1.0 + (days or 30.0) / 7.0)
        confidence = sum(c["conf"]) / max(1, len(c["conf"]))
        coverage = min(1.0, len(c["supporting_fact_ids"]) / 6.0)
        score = round(0.35 * urgency + 0.25 * impact + 0.20 * recency + 0.10 * confidence + 0.10 * coverage, 4)
        # Subject phrasing by dominant type
        dom = sorted(c["fact_types"].items(), key=lambda kv: kv[1], reverse=True)[0][0]
        base = c["text"].strip().rstrip(".")
        if (language or "en-US") == "pt-BR":
            prefix = {"decision": "Decidir:", "open_question": "Resolver:", "risk": "Mitigar:", "action_item": "Planejar:", "milestone": "Alcançar:"}.get(dom, "Alinhar:")
        else:
            prefix = {"decision": "Decide:", "open_question": "Resolve:", "risk": "Mitigate:", "action_item": "Plan:", "milestone": "Achieve:"}.get(dom, "Align:")
        subj = f"{prefix} {base}"
        cands.append({
            "subject": subj,
            "score": score,
            "due_iso": due,
            "dominant_type": dom,
            "supporting_fact_ids": c["supporting_fact_ids"],
        })
    cands.sort(key=lambda x: x["score"], reverse=True)
    return cands[:k]


def retrieve_facts_for_subject(org_id: str, subject: str, limit: int = 60, language: str = "auto") -> list[dict]:
    org_id = org_id or DEFAULT_ORG_ID
    # Opportunistic auto-validation to avoid empty subject retrievals due to draft/proposed
    try:
        recent = db.get_recent_facts(org_id, ["decision", "open_question", "risk", "action_item", "milestone"], 120)
        if any(str(r["status"] or "").lower() in {"draft", "proposed"} for r in recent):
            auto_validate.validate_org_if_needed(org_id, ["decision", "open_question", "risk", "action_item", "milestone"], max_to_validate=120)
    except Exception:
        pass
    # Try embedding-based search if available
    items: List[Any] = []
    try:
        from .indexing import similarity_search  # type: ignore
        items = similarity_search(org_id, subject, top_k=limit, filters={
            "types": ["decision", "open_question", "risk", "action_item", "milestone"],
            "status": ["validated", "published"],
        })
    except Exception:
        # Fallback to FTS/LIKE hybrid
        rows = db.search_facts(org_id, subject or "", ["decision", "open_question", "risk", "action_item", "milestone"], limit)
        if not rows:
            # OR-token fallback
            tokens = [t for t in re.findall(r"\w+", (subject or "").lower()) if len(t) >= 3]
            toks = []
            seen = set()
            for t in tokens:
                if t not in seen:
                    seen.add(t); toks.append(t)
            if toks:
                or_query = " OR ".join(toks)
                rows = db.search_facts(org_id, or_query, ["decision", "open_question", "risk", "action_item", "milestone"], limit)
        items = rows or []
    if not items:
        return []
    # Keep vetted only and allowed types
    allowed = {"decision", "open_question", "risk", "action_item", "milestone"}
    def _row_like(r):
        # If embedding result already a dict-like row
        return r
    rows2 = []
    for r in items:
        try:
            typ = (r["fact_type"] or "").lower()
            st = (r["status"] or "").lower()
        except Exception:
            # assume dict-like
            typ = (r.get("fact_type") or "").lower()
            st = (r.get("status") or "").lower()
        if st in {"validated", "published"} and typ in allowed:
            rows2.append(r)
    # Hydrate
    fact_ids = [r["fact_id"] if isinstance(r, dict) else r["fact_id"] for r in rows2]  # type: ignore[index]
    related = _hydrate_related(fact_ids)
    evidence_map = related["evidence"]
    entities_map = related["entities"]
    # Rank: similarity (fts_score if available → smaller better ⇒ invert), due date asc, recency desc
    def sim_score(r: Any) -> float:
        s = None
        if isinstance(r, dict):
            s = r.get("fts_score")
        else:
            try:
                s = r["fts_score"]
            except Exception:
                s = None
        if s is None:
            # crude token overlap vs subject
            a = set(re.findall(r"\w+", subject.lower()))
            b = set(re.findall(r"\w+", (_parse_payload(r.get("payload") if isinstance(r, dict) else r["payload"]).get("text", "").lower())))  # type: ignore[index]
            inter = len(a & b)
            return float(inter)
        try:
            return 1.0 / (1.0 + float(s))
        except Exception:
            return 0.0
    def due_of(r: Any) -> str:
        try:
            return (r.get("due_iso") or r.get("due_at") or "") if isinstance(r, dict) else (r["due_iso"] or r["due_at"] or "")
        except Exception:
            return ""
    def created_of(r: Any) -> str:
        try:
            return (r.get("created_at") or "") if isinstance(r, dict) else (r["created_at"] or "")
        except Exception:
            return ""
    rows2.sort(key=lambda r: ( -sim_score(r), (due_of(r) or "9999-12-31"), created_of(r) ), reverse=False)
    # De-duplicate by normalized text; cap meeting_metadata ≤ 1 (shouldn’t appear due to allowed types, but safety)
    seen = set(); out: List[Candidate] = []; mm_count = 0
    for r in rows2:
        row_dict = _row_to_dict(r) if not isinstance(r, dict) else r
        payload = _parse_payload(row_dict.get("payload"))
        txt = payload.get("subject") or payload.get("title") or payload.get("text") or ""
        key = _normalize_key(txt)
        if not key or key in seen:
            continue
        if (row_dict.get("fact_type") or "").lower() == "meeting_metadata":
            if mm_count >= 1: continue
            mm_count += 1
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
        out.append(data)
        seen.add(key)
        if len(out) >= limit:
            break
    return out


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
    # Use scored clusters (validated|published only)
    cands = find_subject_candidates(org_id, lookback_days=30, k=5, language=language)
    if not cands:
        return None

    # Helper: fast reject low-quality/banlist subjects (esp. PT)
    def _bad_subject(s: str) -> bool:
        if not isinstance(s, str):
            return True
        t = (s or "").strip()
        if len(t.split()) < 2:
            return True
        low = t.lower()
        # Ban common conversational tokens that leak from transcripts
        ban_pt = {"hoje", "hj", "gente", "pessoal", "galera", "participante", "participantes"}
        if language == "pt-BR" and any(b in low.split() for b in ban_pt):
            return True
        return looks_generic_subject(t, language)

    # Pick the top candidate, LLM-polish it if possible, else refine heuristically
    top = None
    for c in cands:
        subj = c.get("subject") or ""
        # Try validator LLM rewrite if available
        try:
            # Expected to exist in your validator module; safe no-op if missing.
            from . import auto_validate
            subj2 = auto_validate.rewrite_subject(
                subject=subj,
                supporting_fact_ids=c.get("supporting_fact_ids") or [],
                language=language,
                max_words=10,
            )
            if isinstance(subj2, str) and subj2.strip():
                subj = subj2.strip()
        except Exception:
            # Fallback: heuristic refine
            subj = refine_subject_text(subj, language)

        if not _bad_subject(subj):
            top = subj
            break

    if not top:
        # As a last resort: refine the best raw candidate
        top = refine_subject_text(cands[0].get("subject") or "", language)

    return top or None


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
    stop_pt = {"de","da","do","das","dos","e","em","para","por","que","uma","um","uns","umas","na","no","nas","nos","com","sobre","ao","a","o","as","os","pra","pro","hoje","hj","gente","pessoal","galera","participante","participantes","todo","mundo"}
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
