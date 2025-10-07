import json
from typing import Any, Dict, List, Optional, Sequence, Tuple
import re

from .config import DEFAULT_ORG_ID
from . import db
from . import auto_validate


Candidate = Dict[str, Any]


def _row_to_dict(row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


# --- Reference helpers (normalized refs for bullets) ---

def _make_ref(row: dict) -> dict:
    """Normalize a DB row/fact-like dict into a Ref structure.

    Ref = {
      "id": str,
      "fact_type": str | None,
      "status": str | None,
      "updated_at": str | None,
      "owner": str | None,
      "source": str | None,
      "confidence": float | None,
      "title": str | None,
      "excerpt": str | None,
      "url": str | None,
    }
    """
    def _g(k, *alts):
        for kk in (k, *alts):
            try:
                if kk in row and row.get(kk) is not None:
                    return row.get(kk)
            except Exception:
                try:
                    val = row[kk]
                    if val is not None:
                        return val
                except Exception:
                    pass
        return None

    source = _g("source") or _g("fact_type") or _g("type") or None
    # Try to parse payload for richer fields
    payload = None
    try:
        rawp = _g("payload")
        if isinstance(rawp, str):
            payload = json.loads(rawp)
        elif isinstance(rawp, dict):
            payload = rawp
    except Exception:
        payload = None
    # Prefer any concise textual field available; include quotes when present
    excerpt_src = (
        (payload.get("excerpt") if isinstance(payload, dict) else None) or
        _g("summary") or _g("text") or _g("content") or _g("quote") or _g("title") or ""
    )
    # Provide a longer excerpt so the UI can show a meaningful snippet
    excerpt = (excerpt_src or "")[:280]
    # Prefer human-friendly description for titles and headings
    description = None
    if isinstance(payload, dict):
        for k in ("description", "title", "subject", "text", "summary"):
            v = payload.get(k)
            if isinstance(v, str) and v.strip():
                description = v.strip()[:200]
                break
    # Robust fallback: derive description from row-level textual fields if payload lacks it
    if not description:
        # Try common row fields first
        desc_src = (
            _g("title") or _g("summary") or _g("text") or _g("content") or _g("quote") or None
        )
        # If still missing, reuse the excerpt source (first sentence) or payload text-like fields
        if not desc_src:
            try:
                if isinstance(payload, dict):
                    desc_src = (
                        payload.get("subject") or payload.get("title") or payload.get("summary") or payload.get("text") or None
                    )
            except Exception:
                desc_src = None
        if isinstance(desc_src, str) and desc_src.strip():
            s = desc_src.strip()
            # Pick a concise first sentence/phrase
            m = re.match(r"^[^.!?\n\r]{1,}", s)
            description = (m.group(0) if m else s)[:200]
    return {
        "id": str(_g("id") or _g("evidence_id") or _g("fact_id") or _g("rowid") or ""),
        "fact_type": (_g("fact_type") or _g("type") or None),
        "category": (_g("fact_type") or _g("type") or None),
        "status": (_g("status") or None),
        "updated_at": (_g("updated_at") or _g("last_update") or None),
        "owner": (_g("owner") or _g("who") or _g("assignee") or None),
        "source": source,
        "confidence": _g("confidence"),
        "title": (_g("title") or None),
        "description": description,
        "excerpt": (excerpt or None),
        "url": (_g("url") or _g("link") or None),
    }


def _attach_ref(bullet: dict, row: dict):
    """Attach a normalized ref for a given row/fact into a bullet under key 'refs'.

    Safely no-ops if there is no useful id/excerpt to reference.
    """
    try:
        r = _make_ref(row)
    except Exception:
        return
    if not r.get("id") and not r.get("excerpt"):
        return
    bullet.setdefault("refs", []).append(r)


def _parse_payload(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def resolve_org_id(text_or_id: Optional[str], *, allow_create: bool = True, full_text: Optional[str] = None) -> str:
    """Resolve an organization id from a user-provided hint.

    Behavior tweaks to avoid accidental org creation:
    - Try exact match (id or name) and substring match inside full_text first.
    - Try fuzzy similarity against known org ids/names.
    - Only auto-create when explicitly allowed AND the candidate looks like a short id (slug-like).
    - Otherwise fall back to DEFAULT_ORG_ID.
    """
    candidate = (text_or_id or "").strip()

    def _safe_norm(s: str) -> str:
        try:
            import unicodedata, re as _re
            s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
            s = _re.sub(r"\s+", " ", s)
            return s.strip().lower()
        except Exception:
            return (s or "").strip().lower()

    # 1) direct attempts (exact id or name)
    if candidate:
        row = db.get_org(candidate) or db.find_org_by_text(candidate)
        if row:
            return row["org_id"]

        # 2) fuzzy: look for known org names/ids within the full free text (with boundaries)
        if full_text:
            import re as _re
            hay = f" {_safe_norm(full_text)} "
            best = None
            try:
                orgs = db.list_orgs()
            except Exception:
                orgs = []

            def _get(row: Any, key: str) -> Optional[str]:
                try:
                    return row[key]
                except Exception:
                    try:
                        return row.get(key)
                    except Exception:
                        return None

            for r in orgs:
                oid = _safe_norm(_get(r, "org_id") or "")
                name = _safe_norm(_get(r, "name") or "")
                for k in filter(None, (oid, name)):
                    # require token boundary to reduce false positives
                    if f" {k} " in hay:
                        if best is None or len(k) > len(best[0]):
                            best = (k, _get(r, "org_id"))
            if best and best[1]:
                return str(best[1])

        # 3) fuzzy similarity: compare normalized candidate with known ids/names
        try:
            from difflib import SequenceMatcher
            best_ratio = 0.0
            best_id: Optional[str] = None
            cand_norm = _safe_norm(candidate)
            for r in db.list_orgs():
                oid = _safe_norm(getattr(r, "org_id", None) or (r.get("org_id") if isinstance(r, dict) else None) or "")
                name = _safe_norm(getattr(r, "name", None) or (r.get("name") if isinstance(r, dict) else None) or "")
                for k in filter(None, (oid, name)):
                    ratio = SequenceMatcher(None, cand_norm, k).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_id = getattr(r, "org_id", None) or (r.get("org_id") if isinstance(r, dict) else None)
            # Accept reasonably close matches only
            if best_id and best_ratio >= 0.82:
                return str(best_id)
        except Exception:
            pass

        # 4) create only if allowed AND the candidate looks like a short, safe id (slug-like)
        if allow_create:
            import re as _re
            # slug-like: letters/digits/_/- only, no spaces, 3..36 chars
            if _re.fullmatch(r"[A-Za-z0-9_-]{3,36}", candidate):
                db.ensure_org(candidate, candidate)
                return candidate

    # 5) Fallback to default org (ensure it exists)
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
    # Fallback: se muito poucos itens vetados, traga alguns 'proposed'
    MIN_ROWS = 8
    if rows and len(rows) < MIN_ROWS:
        recent_all = db.get_recent_facts(org_id, types, limit)
        proposed = [r for r in recent_all if (str(r["status"] or "").lower() == "proposed")]
        rows = (rows + proposed)[:limit]
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
                # filter vetted; se vazio, cair para proposed
                vetted = [er for er in extra_rows if (str(er["status"] or "").lower() in {"validated", "published"})]
                if vetted:
                    extra_rows = vetted
                else:
                    extra_rows = [er for er in extra_rows if (str(er["status"] or "").lower() == "proposed")]
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
    # Fallback: se a lista ficou curta, complete com 'proposed' do mesmo conjunto 'items'
    if len(rows2) < 6:
        need = 6 - len(rows2)
        props = []
        for r in items:
            try:
                typ = (r["fact_type"] or "").lower()
                st = (r["status"] or "").lower()
            except Exception:
                typ = (r.get("fact_type") or "").lower()
                st = (r.get("status") or "").lower()
            if st == "proposed" and typ in allowed:
                props.append(r)
        rows2.extend(props[:need])
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
        r"^\s*(alinhamento|alinhamentos?)\s*(com\s+)?(o\s+)?pessoal\b",
        r"\b(participantes|hoje|hj)\b",
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


# ---------------------------------------------------------------------------
# Macro-context retrieval (workstreams layer)
# ---------------------------------------------------------------------------

def select_workstreams(org_id: str, subject: Optional[str], k: int = 3) -> List[Dict[str, Any]]:
    """Select top k workstreams for agenda planning.
    
    Strategy:
    1. If subject provided, try exact match in title/tags
    2. Otherwise, return top workstreams by priority/status/recency
    """
    org_id = org_id or DEFAULT_ORG_ID
    
    # Try subject-based match first
    if subject and subject.strip():
        matches = db.find_workstreams(org_id, subject, limit=k)
        if matches:
            return matches
    
    # Fallback: top priority workstreams
    return db.top_workstreams(org_id, limit=k)


def search_related_facts(
    org_id: str,
    workstreams: List[Dict[str, Any]],
    per_ws: int = 20,
) -> List[Dict[str, Any]]:
    """Widen fact search using workstream tags and titles as keywords.
    
    Returns additional facts not already linked to workstreams.
    """
    org_id = org_id or DEFAULT_ORG_ID
    
    if not workstreams:
        return []
    
    # Build search terms from workstream titles and tags
    search_terms: set[str] = set()
    for ws in workstreams:
        title = ws.get("title", "")
        if title:
            # Extract meaningful words from title
            tokens = re.findall(r"[\wÀ-ÿ]+", title.lower())
            search_terms.update(t for t in tokens if len(t) >= 4)
        
        tags = ws.get("tags") or []
        for tag in tags:
            if isinstance(tag, str) and len(tag) >= 3:
                search_terms.add(tag.lower())
    
    if not search_terms:
        return []
    
    # Search for facts matching these terms
    query = " OR ".join(list(search_terms)[:10])  # Limit to avoid overly broad search
    
    try:
        rows = db.search_facts(
            org_id,
            query,
            ["decision", "open_question", "risk", "action_item", "milestone", "process_step"],
            limit=per_ws * len(workstreams),
        )
    except Exception:
        return []
    
    # Hydrate and convert to candidate format
    if not rows:
        return []
    
    fact_ids = [row["fact_id"] for row in rows]
    related = _hydrate_related(fact_ids)
    evidence_map = related["evidence"]
    entities_map = related["entities"]
    
    candidates: List[Dict[str, Any]] = []
    for row in rows:
        row_dict = _row_to_dict(row)
        payload = _parse_payload(row_dict.get("payload"))
        fid = row_dict["fact_id"]
        
        data = {
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
        candidates.append(data)
    
    return candidates


def rank_micro_facts(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rank facts using a scoring blend of status, urgency, recency, and evidence quality.
    
    Returns sorted list with 'score' field added to each item for debugging.
    """
    from datetime import datetime, timezone
    
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    
    def _score_status(status: str) -> float:
        """validated=1.0, published=0.95, proposed=0.6, draft=0.4"""
        s = (status or "").lower()
        return {
            "validated": 1.0,
            "published": 0.95,
            "proposed": 0.6,
            "draft": 0.4,
        }.get(s, 0.3)
    
    def _score_urgency(due_iso: Optional[str]) -> float:
        """Due soon = higher score. No due = low baseline."""
        if not due_iso:
            return 0.2
        try:
            due = datetime.fromisoformat(due_iso.replace("Z", "+00:00"))
            delta_days = (due - now).total_seconds() / 86400.0
            if delta_days <= 0:
                return 1.0  # Overdue
            if delta_days <= 3:
                return 0.9
            if delta_days <= 7:
                return 0.7
            if delta_days <= 14:
                return 0.5
            return 0.3
        except Exception:
            return 0.2
    
    def _score_recency(created_at: Optional[str]) -> float:
        """Recent facts score higher."""
        if not created_at:
            return 0.3
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            delta_days = (now - created).total_seconds() / 86400.0
            # Decay over 30 days
            return max(0.2, 1.0 - (delta_days / 30.0))
        except Exception:
            return 0.3
    
    def _score_evidence(evidence: List[Any]) -> float:
        """More evidence with quotes = higher score."""
        if not evidence:
            return 0.3
        quote_count = sum(1 for e in evidence if e.get("quote") and len(str(e.get("quote")).strip()) > 20)
        return min(1.0, 0.4 + (quote_count * 0.2))
    
    def _score_type(fact_type: str) -> float:
        """Weight fact types by importance for agenda planning."""
        ft = (fact_type or "").lower()
        return {
            "decision": 1.0,
            "open_question": 0.9,
            "risk": 0.95,
            "action_item": 0.85,
            "milestone": 0.9,
            "process_step": 0.7,
        }.get(ft, 0.5)
    
    for item in items:
        status_score = _score_status(item.get("status"))
        urgency_score = _score_urgency(item.get("due_iso"))
        recency_score = _score_recency(item.get("created_at"))
        evidence_score = _score_evidence(item.get("evidence", []))
        type_score = _score_type(item.get("fact_type"))
        
        # Weighted blend
        score = (
            0.35 * status_score +
            0.25 * urgency_score +
            0.15 * recency_score +
            0.15 * evidence_score +
            0.10 * type_score
        )
        
        item["score"] = round(score, 4)
    
    # Sort by score descending, then by created_at descending for ties
    items.sort(
        key=lambda x: (-x.get("score", 0), x.get("created_at") or ""),
        reverse=False,
    )
    
    return items


def facts_for_workstreams(
    org_id: str,
    workstreams: List[Dict[str, Any]],
    per_ws: int = 20,
) -> List[Dict[str, Any]]:
    """Get facts for workstreams combining linked facts and widened search.
    
    Returns ranked and deduplicated fact list.
    """
    org_id = org_id or DEFAULT_ORG_ID
    
    if not workstreams:
        return []
    
    # Get directly linked facts
    ws_ids = [ws["workstream_id"] for ws in workstreams]
    linked = db.get_facts_by_workstreams(ws_ids, limit_per_ws=per_ws)
    
    # Get widened facts from search
    widened = search_related_facts(org_id, workstreams, per_ws=per_ws)
    
    # Combine and deduplicate by fact_id
    seen_ids: set[str] = set()
    combined: List[Dict[str, Any]] = []
    
    for fact in linked + widened:
        fid = fact.get("fact_id")
        if fid and fid not in seen_ids:
            seen_ids.add(fid)
            combined.append(fact)
    
    # Auto-tag facts with workstream_id from their meeting
    combined = enrich_facts_with_meeting_workstreams(combined)
    
    # Rank all facts
    ranked = rank_micro_facts(combined)
    
    return ranked


def enrich_facts_with_meeting_workstreams(facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enrich facts with workstream_id inherited from their meeting.
    
    If a fact doesn't have a workstream_id but its meeting is linked to workstreams,
    use the first (highest priority) workstream from that meeting.
    """
    # Group facts by meeting_id
    from collections import defaultdict
    by_meeting: dict[str, List[Dict[str, Any]]] = defaultdict(list)
    
    for fact in facts:
        meeting_id = fact.get("meeting_id")
        if meeting_id and not fact.get("workstream_id"):
            by_meeting[meeting_id].append(fact)
    
    if not by_meeting:
        return facts
    
    # Fetch workstreams for each meeting
    meeting_ws_cache: dict[str, List[Dict[str, Any]]] = {}
    for meeting_id in by_meeting.keys():
        workstreams = db.get_meeting_workstreams(meeting_id)
        if workstreams:
            meeting_ws_cache[meeting_id] = workstreams
    
    # Enrich facts
    for fact in facts:
        if fact.get("workstream_id"):
            continue  # Already has workstream
        
        meeting_id = fact.get("meeting_id")
        if meeting_id and meeting_id in meeting_ws_cache:
            workstreams = meeting_ws_cache[meeting_id]
            if workstreams:
                # Use first (highest priority) workstream
                fact["workstream_id"] = workstreams[0]["workstream_id"]
                fact["_inherited_from_meeting"] = True
    
    return facts


# --- Smart Fact Selection (forward-looking, actionable facts) ---

def select_actionable_facts(
    org_id: str,
    subject: str,
    intent: str,
    workstreams: List[Dict[str, Any]],
    language: str = "pt-BR",
    limit: int = 40,
) -> List[Dict[str, Any]]:
    """Select facts that NEED to be addressed in this meeting.
    
    Priority logic:
    1. URGENT: Overdue actions, red-status items, blockers
    2. DECISION-NEEDED: Open decisions tagged as "needs approval"
    3. WORKSTREAM-DRIVEN: Facts linked to workstreams with upcoming deadlines
    4. SUBJECT-RELEVANT: Facts matching subject keywords
    5. RECENT-CONTEXT: Latest validated facts for background (max 20%)
    
    Returns ranked list with 'urgency_score' and 'why_relevant' fields.
    """
    org_id = org_id or DEFAULT_ORG_ID
    
    # Step 1: Get candidates from multiple sources
    urgent_facts = get_urgent_facts(org_id, workstreams)
    decision_facts = get_decision_needed_facts(org_id, workstreams)
    subject_facts = retrieve_facts_for_subject(org_id, subject, limit=30, language=language) if subject else []
    workstream_facts = facts_for_workstreams(org_id, workstreams, per_ws=10) if workstreams else []
    
    # Step 2: Deduplicate
    seen_ids: set[str] = set()
    all_facts: List[Dict[str, Any]] = []
    
    for fact_list in [urgent_facts, decision_facts, subject_facts, workstream_facts]:
        for fact in fact_list:
            fid = fact.get("fact_id")
            if fid and fid not in seen_ids:
                seen_ids.add(fid)
                all_facts.append(fact)
    
    if not all_facts:
        return []
    
    # Step 3: Score each fact for relevance to THIS meeting
    for fact in all_facts:
        fact["urgency_score"] = calculate_urgency(fact)
        fact["why_relevant"] = generate_relevance_reason(fact, subject, intent, workstreams, language)
    
    # Step 4: Rank by urgency
    ranked = sorted(all_facts, key=lambda f: f.get("urgency_score", 0), reverse=True)
    
    # Step 5: Balance (don't return only urgent items; include context)
    urgent = [f for f in ranked if f.get("urgency_score", 0) > 0.7][:15]
    important = [f for f in ranked if 0.4 <= f.get("urgency_score", 0) <= 0.7][:15]
    context = [f for f in ranked if f.get("urgency_score", 0) < 0.4][:10]
    
    result = urgent + important + context
    return result[:limit]


def get_urgent_facts(org_id: str, workstreams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Get urgent facts: overdue, blockers, red status."""
    org_id = org_id or DEFAULT_ORG_ID
    
    # Get recent facts with urgent types and convert to dicts
    urgent_types = ["blocker", "risk", "decision_needed", "action_item"]
    fact_rows = db.get_recent_facts(org_id, urgent_types, limit=50)
    facts = [_row_to_dict(f) for f in fact_rows]
    
    # Filter to urgent items
    urgent = []
    from datetime import datetime, timezone
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    
    for fact in facts:
        # Check if overdue
        due_iso = fact.get("due_iso") or fact.get("due_at")
        is_overdue = False
        if due_iso:
            try:
                due = datetime.fromisoformat(due_iso.replace("Z", "+00:00"))
                is_overdue = due < now
            except Exception:
                pass
        
        # Check status
        status = (fact.get("status") or "").lower()
        
        # Include if overdue, red status, or blocker type
        if is_overdue or status == "red" or fact.get("fact_type") == "blocker":
            urgent.append(fact)
    
    return urgent


def get_decision_needed_facts(org_id: str, workstreams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Get facts that need decisions."""
    org_id = org_id or DEFAULT_ORG_ID
    
    # Get decision-related facts and convert to dicts
    decision_types = ["decision_needed", "decision", "open_question"]
    fact_rows = db.get_recent_facts(org_id, decision_types, limit=30)
    facts = [_row_to_dict(f) for f in fact_rows]
    
    # Filter to validated/published only
    validated = [
        f for f in facts
        if (f.get("status") or "").lower() in {"validated", "published"}
    ]
    
    return validated


def calculate_urgency(fact: Dict[str, Any]) -> float:
    """Score 0-1 based on how urgently this needs discussion.
    
    Factors:
    - Overdue: +0.5
    - Red status: +0.3
    - Yellow status: +0.2
    - Blocker/risk type: +0.2
    - Action/milestone type: +0.1
    - Age >30 days: +0.2
    - Age >14 days: +0.1
    """
    from datetime import datetime, timezone
    
    score = 0.0
    
    # Check overdue
    due_iso = fact.get("due_iso") or fact.get("due_at")
    if due_iso:
        try:
            due = datetime.fromisoformat(due_iso.replace("Z", "+00:00"))
            now = datetime.utcnow().replace(tzinfo=timezone.utc)
            if due < now:
                score += 0.5
        except Exception:
            pass
    
    # Status
    status = (fact.get("status") or "").lower()
    if status == "red":
        score += 0.3
    elif status == "yellow":
        score += 0.2
    
    # Type
    ftype = (fact.get("fact_type") or "").lower()
    if ftype in ["blocker", "decision_needed", "risk"]:
        score += 0.2
    elif ftype in ["action_item", "milestone"]:
        score += 0.1
    
    # Age
    created_at = fact.get("created_at")
    if created_at:
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            now = datetime.utcnow().replace(tzinfo=timezone.utc)
            age_days = (now - created).total_seconds() / 86400
            if age_days > 30:
                score += 0.2
            elif age_days > 14:
                score += 0.1
        except Exception:
            pass
    
    return min(1.0, score)


def generate_relevance_reason(
    fact: Dict[str, Any],
    subject: str,
    intent: str,
    workstreams: List[Dict[str, Any]],
    language: str = "pt-BR",
) -> str:
    """Generate 1-sentence reason why this fact is relevant to THIS meeting.
    
    Examples:
    - "Decisão pendente há 21 dias sobre integração com API"
    - "Bloqueador crítico impactando lançamento do Song Plus"
    - "Meta de Q1 com deadline em 15 dias"
    """
    from datetime import datetime, timezone
    
    parts = []
    ftype = (fact.get("fact_type") or "").lower()
    status = (fact.get("status") or "").lower()
    
    # Parse payload if it's a string
    payload = fact.get("payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    
    # Add type description
    if language == "pt-BR":
        type_names = {
            "blocker": "Bloqueador",
            "risk": "Risco",
            "decision_needed": "Decisão pendente",
            "decision": "Decisão",
            "action_item": "Ação",
            "milestone": "Marco",
            "open_question": "Questão aberta",
        }
    else:
        type_names = {
            "blocker": "Blocker",
            "risk": "Risk",
            "decision_needed": "Decision needed",
            "decision": "Decision",
            "action_item": "Action",
            "milestone": "Milestone",
            "open_question": "Open question",
        }
    
    type_label = type_names.get(ftype, ftype.replace("_", " ").capitalize())
    
    # Add urgency indicator
    if status == "red":
        urgency = "crítico" if language == "pt-BR" else "critical"
        type_label = f"{type_label} {urgency}"
    
    parts.append(type_label)
    
    # Add age if old
    created_at = fact.get("created_at")
    if created_at:
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            now = datetime.utcnow().replace(tzinfo=timezone.utc)
            age_days = int((now - created).total_seconds() / 86400)
            if age_days > 14:
                age_text = f"há {age_days} dias" if language == "pt-BR" else f"{age_days} days old"
                parts.append(age_text)
        except Exception:
            pass
    
    # Add subject/title
    subject_text = (
        payload.get("subject") or
        payload.get("title") or
        payload.get("name") or
        ""
    )
    if subject_text:
        # Truncate
        if len(subject_text) > 50:
            subject_text = subject_text[:47] + "..."
        parts.append(f"sobre {subject_text}" if language == "pt-BR" else f"about {subject_text}")
    
    # Add workstream if relevant
    ws_id = fact.get("workstream_id")
    if ws_id and workstreams:
        ws = next((w for w in workstreams if w.get("workstream_id") == ws_id), None)
        if ws:
            ws_title = ws.get("title", "")
            if ws_title:
                parts.append(f"({ws_title})")
    
    return " ".join(parts) if parts else type_label

