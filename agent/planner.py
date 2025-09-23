import hashlib
import json
from typing import Any, Dict, List, Optional, Sequence
import re

from . import db
from .config import DEFAULT_ORG_ID


DEFAULT_FACT_TYPES = (
    "decision",
    "action_item",
    "risk",
    "milestone",
    "question",
    "topic",
    "objective",
    "insight",
    "meeting_metadata",
)

SECTION_TEMPLATES = [
    ("Context", {"topic", "objective", "insight", "context", "meeting_metadata"}),
    ("Key Decisions", {"decision", "decision_needed"}),
    ("Risks & Blockers", {"risk", "blocker"}),
    ("Milestones", {"milestone", "deadline"}),
    ("Action Items", {"action_item", "task"}),
    ("Open Questions", {"question", "open_question"}),
]


def _section_labels_next(language: str) -> List[Dict[str, str]]:
    if language == "pt-BR":
        return [
            {"key": "alignments", "title": "Alinhamentos"},
            {"key": "open_questions", "title": "Perguntas em aberto"},
            {"key": "decisions", "title": "Decisões"},
            {"key": "risks", "title": "Riscos"},
            {"key": "integrations", "title": "Integrações e dependências"},
            {"key": "next_steps", "title": "Próximos passos"},
        ]
    return [
        {"key": "alignments", "title": "Alignments"},
        {"key": "open_questions", "title": "Open Questions"},
        {"key": "decisions", "title": "Decisions"},
        {"key": "risks", "title": "Risks"},
        {"key": "integrations", "title": "Integrations & Dependencies"},
        {"key": "next_steps", "title": "Next Steps"},
    ]


def _short_text_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("subject", "title", "name", "headline", "summary", "text"):
        val = (payload or {}).get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _refine_phrase(text: str, language: str) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    low = s.lower()
    # Remove common lead-ins (PT/EN)
    lead_pt = [
        r"^temos\s+um[au]?\s+", r"^tem\s+um[au]?\s+", r"^estamos\s+", r"^a\s+gente\s+", r"^vamos\s+",
        r"^que\s+fala\s+s[oó]\s+de\s+", r"^ent[aã]o\s+", r"^aqui\s+", r"^eu\s+", r"^porque\s+", r"^ok\s+", r"^bom\s+", r"^tipo\s+", r"^n[ée]\s+", r"^assim\s+",
    ]
    lead_en = [r"^we\s+have\s+", r"^there\s+is\s+", r"^we'?re\s+", r"^we\s+are\s+"]
    import re
    for p in (lead_pt if language == "pt-BR" else lead_en):
        s = re.sub(p, "", s, flags=re.IGNORECASE)
    # Trim trailing clauses
    tails_pt = [r"\b(a|à)\s+medida\s+em?\s+que\b.*$", r"\bquando\b.*$", r"\bse\b.*$"]
    tails_en = [r"\bwhen\b.*$", r"\bif\b.*$"]
    for p in (tails_pt if language == "pt-BR" else tails_en):
        s = re.sub(p, "", s, flags=re.IGNORECASE)
    s = s.strip().strip("…").strip(" .,:-;")
    # Shorten
    if len(s) > 72:
        # Prefer cutting at comma or coordinator
        options = ([",", " e "] if language == "pt-BR" else [",", " and "])
        cuts = [s.lower().find(tok) for tok in options]
        cuts = [c for c in cuts if 0 < c < 72]
        if cuts:
            s = s[: max(cuts)]
        else:
            s = s[:72].rstrip()
    # Capitalize
    if s:
        s = s[0].upper() + s[1:]
    return s


def _keywords_phrase(texts: Sequence[str], language: str) -> Optional[str]:
    import re
    toks: List[str] = []
    for t in texts:
        if not isinstance(t, str):
            continue
        # basic tokenization; keep unicode letters
        toks.extend([w.lower() for w in re.findall(r"[\wÀ-ÿ]+", t)])
    # Drop very short tokens
    toks = [w for w in toks if len(w) >= 3]
    # Drop tokens without vowels (likely IDs/fragments)
    vowels = set("aeiouáéíóúâêôãõà")
    toks = [w for w in toks if any(ch in vowels for ch in w)]
    if not toks:
        return None
    stop_pt = {"de","da","do","das","dos","e","em","para","por","que","uma","um","uns","umas","na","no","nas","nos","com","sobre","ao","a","o","as","os","pra","pro","então","entao","essa","esse","isso","aqui","eu","ok","bom","tipo","né","ne","assim","porque","tá","ta","ai","aí","ai"}
    stop_en = {"the","and","for","with","a","an","of","in","on","to","by","about","from","as","at","is","are","this","that"}
    stop = stop_pt if language == "pt-BR" else stop_en
    from collections import Counter
    freq = Counter([w for w in toks if w not in stop])
    if not freq:
        return None
    top = [w for (w, _c) in freq.most_common(6)]
    if language == "pt-BR":
        phrase = " ".join(top[:3]).strip()
        phrase = _refine_phrase(phrase, language) if phrase else None
        return phrase.capitalize() if phrase else None
    phrase = " ".join(top[:3]).strip()
    phrase = _refine_phrase(phrase, language) if phrase else None
    return phrase.title() if phrase else None


def _abstract_text_from_fact(fact: Dict[str, Any], language: str) -> Optional[str]:
    payload = fact.get("payload") or {}
    # Prefer payload subject/title, refined
    t = _short_text_from_payload(payload)
    t = _refine_phrase(t or "", language) if t else None
    if t:
        return t
    # Else synthesize from payload strings and entities (avoid evidence quotes)
    texts: List[str] = []
    for k in ("subject", "title", "name", "headline", "summary", "text"):
        val = payload.get(k)
        if isinstance(val, str) and val.strip():
            texts.append(val.strip())
    for ent in (fact.get("entities") or []):
        dn = ent.get("display_name")
        if isinstance(dn, str) and dn.strip():
            texts.append(dn.strip())
    phrase = _keywords_phrase(texts, language)
    return phrase


def _quality_score(text: str, language: str) -> float:
    s = (text or "").strip()
    if not s:
        return 0.0
    import re
    # Token and alpha ratio checks
    tokens = re.findall(r"[\wÀ-ÿ]+", s)
    if len(tokens) < 3:
        return 0.1
    alpha = sum(ch.isalpha() for ch in s)
    ratio = alpha / max(1, len(s))
    score = 0.3 + 0.5 * min(1.0, ratio)
    # Penalize bad starts/ends and filler heads
    bad_heads_pt = ["eu ", "a gente ", "aqui ", "então ", "olha "]
    bad_heads_en = ["i ", "we ", "here ", "so ", "well "]
    bad_heads = bad_heads_pt if language == "pt-BR" else bad_heads_en
    low = s.lower()
    if any(low.startswith(h) for h in bad_heads):
        score -= 0.2
    last = tokens[-1].lower()
    stop_pt = {"de","da","do","das","dos","e","em","para","por","que","uma","um","na","no","pra","pro"}
    stop_en = {"the","and","for","with","a","an","of","in","on","to","by","about","from","as","at","is","are"}
    stop = stop_pt if language == "pt-BR" else stop_en
    if last in stop:
        score -= 0.2
    # Penalize likely truncated words
    if language == "pt-BR" and (last.endswith("çã") or last.endswith("negóci") or last.endswith("inform") or last.endswith("cont") or last.endswith("cadast")):
        score -= 0.3
    return max(0.0, min(1.0, score))


def _infer_kind_from_text(text: str, language: str) -> Optional[str]:
    s = (text or "").strip()
    if not s:
        return None
    low = s.lower()
    # Question signals (even if missing '?', we look for interrogatives)
    pt_q = [r"\?$", r"\bpor\s+que\b", r"\bcomo\b", r"\bquando\b", r"\bonde\b", r"\bo\s+que\b", r"\bqual\b", r"\bquais\b", r"\bquem\b", r"\bse\b", r"\bpergunta\b"]
    en_q = [r"\?$", r"\bwhy\b", r"\bhow\b", r"\bwhen\b", r"\bwhere\b", r"\bwhat\b", r"\bwhich\b", r"\bwho\b", r"\bif\b", r"\bquestion\b"]
    q_patterns = pt_q if language == "pt-BR" else en_q
    if any(re.search(p, low) for p in q_patterns):
        return "question"
    # Decision signals
    pt_dec = [r"\bdecid(?:ir|ir\s+se|ir\s+por)?\b", r"\bdecis[aã]o\b", r"\baprovar\b", r"\baprova[cç][aã]o\b", r"\bescolher\b", r"\bconfirmar\b", r"\bvalidar\b", r"\bdefinir\b", r"\bfechar\b"]
    en_dec = [r"\bdecid(?:e|e\s+if|e\s+on)\b", r"\bdecision\b", r"\bapprove\b", r"\bapproval\b", r"\bchoose\b", r"\bconfirm\b", r"\bvalidate\b", r"\bdefine\b", r"\bfinali[sz]e\b"]
    dec_patterns = pt_dec if language == "pt-BR" else en_dec
    if any(re.search(p, low) for p in dec_patterns):
        return "decision"
    # Risk signals
    pt_risk = [r"\brisco\b", r"\briscos\b", r"\bbloqueio\b", r"\bbloqueador\b", r"\bimpedimento\b", r"\bproblema\b", r"\bfalha\b", r"\batraso\b", r"\bn[ãa]o\s+conformidade\b", r"\blgpd\b", r"\bseguran[cç]a\b"]
    en_risk = [r"\brisk\b", r"\brisks\b", r"\bblocker\b", r"\bimpediment\b", r"\bissue\b", r"\bfailure\b", r"\bdelay\b", r"\bnon\-?compliance\b", r"\blgpd\b", r"\bsecurity\b"]
    risk_patterns = pt_risk if language == "pt-BR" else en_risk
    if any(re.search(p, low) for p in risk_patterns):
        return "risk"
    # Integration/Dependency signals
    pt_int = [r"\bintegra(ç|c)[aã]o\b", r"\bapis?\b", r"\bdepend[êe]ncia\b", r"\bprocesso\b", r"\bpipeline\b", r"\bprotocolo\b", r"\bwebhook\b", r"\bendpoints?\b", r"\besquema\b", r"\bmapeamento\b"]
    en_int = [r"\bintegration\b", r"\bapis?\b", r"\bdependenc(y|ies)\b", r"\bprocess\b", r"\bpipeline\b", r"\bprotocol\b", r"\bwebhook\b", r"\bendpoints?\b", r"\bschema\b", r"\bmapping\b"]
    int_patterns = pt_int if language == "pt-BR" else en_int
    if any(re.search(p, low) for p in int_patterns):
        return "integration"
    # Action/Next-step signals
    pt_act = [r"\bpr[óo]ximo\s+passo\b", r"\ba[cç][aã]o\b", r"\btarefa\b", r"\bentregar\b", r"\bimplementar\b", r"\bcriar\b", r"\bfazer\b", r"\bplanejar\b", r"\bplanejamento\b", r"\bacompanhar\b"]
    en_act = [r"\bnext\s+step\b", r"\baction\b", r"\btask\b", r"\bdeliver\b", r"\bimplement\b", r"\bcreate\b", r"\bdo\b", r"\bplan\b", r"\bplanning\b", r"\bfollow\s*up\b"]
    act_patterns = pt_act if language == "pt-BR" else en_act
    if any(re.search(p, low) for p in act_patterns):
        return "action_item"
    # Metrics/Objectives
    pt_metric = [r"\bm(é|e)trica\b", r"\bmeta\b", r"\bobjetivo\b"]
    en_metric = [r"\bmetric\b", r"\btarget\b", r"\bobjective\b", r"\bgoal\b"]
    metric_patterns = pt_metric if language == "pt-BR" else en_metric
    if any(re.search(p, low) for p in metric_patterns):
        return "metric"
    return None


def _derive_next_bullets(candidates: Sequence[Dict[str, Any]], language: str) -> Dict[str, List[Dict[str, Any]]]:
    # key -> list of bullets
    res: Dict[str, List[Dict[str, Any]]] = {
        "alignments": [],
        "open_questions": [],
        "decisions": [],
        "integrations": [],
        "risks": [],
        "next_steps": [],
    }
    seen_texts = set()
    for fact in candidates:
        ftype = (fact.get("fact_type") or "").lower()
        text = _abstract_text_from_fact(fact, language)
        if not text:
            continue
        if _quality_score(text, language) < 0.6:
            # Try to synthesize from payload strings only
            payload = fact.get("payload") or {}
            synth = _keywords_phrase([
                payload.get("subject"), payload.get("title"), payload.get("headline"), payload.get("summary"), payload.get("text")
            ], language)
            text = _refine_phrase(synth or "", language) if synth else None
            if not text or _quality_score(text, language) < 0.6:
                continue
        inferred = _infer_kind_from_text(text, language)
        if inferred:
            ftype = inferred
        # Deduplicate by normalized text key to avoid repeated bullets
        norm_key = (text or "").strip().lower().rstrip(" .:;?!")
        if norm_key in seen_texts:
            continue
        seen_texts.add(norm_key)
        bullet = {
            "text": text,
            "owner": (fact.get("payload") or {}).get("owner"),
            "due": fact.get("due_iso") or fact.get("due_at"),
            "source_fact_id": fact.get("fact_id"),
        }
        # Classify with forward-looking orientation
        if ftype in {"question", "open_question"}:
            if language == "pt-BR":
                bullet["text"] = ("Responder: " + text.rstrip(".?") + "?")
            else:
                bullet["text"] = ("Answer: " + text.rstrip(".?") + "?")
            res["open_questions"].append(bullet)
        elif ftype in {"decision", "decision_needed"}:
            if language == "pt-BR":
                bullet["text"] = ("Decidir: " + text.rstrip(". "))
            else:
                bullet["text"] = ("Decide: " + text.rstrip(". "))
            res["decisions"].append(bullet)
        elif ftype in {"risk", "blocker"}:
            if language == "pt-BR":
                bullet["text"] = ("Mitigar: " + text.rstrip("."))
            else:
                bullet["text"] = ("Mitigate: " + text.rstrip("."))
            res["risks"].append(bullet)
        elif ftype in {"integration", "dependency", "process_step"}:
            if language == "pt-BR":
                bullet["text"] = ("Próximo passo de integração/processo: " + text.rstrip("."))
            else:
                bullet["text"] = ("Next step for integration/process: " + text.rstrip("."))
            res["integrations"].append(bullet)
        elif ftype in {"action_item", "task", "milestone", "deadline"}:
            if language == "pt-BR":
                bullet["text"] = ("Acompanhar ação: " + text.rstrip("."))
            else:
                bullet["text"] = ("Follow up action: " + text.rstrip("."))
            res["next_steps"].append(bullet)
        elif ftype in {"metric", "objective", "insight", "topic"}:
            if language == "pt-BR":
                bullet["text"] = ("Alinhar: " + text.rstrip("."))
            else:
                bullet["text"] = ("Align: " + text.rstrip("."))
            res["alignments"].append(bullet)
        else:
            # reference/other → put into alignments
            if language == "pt-BR":
                bullet["text"] = ("Alinhar: " + text.rstrip("."))
            else:
                bullet["text"] = ("Align: " + text.rstrip("."))
            res["alignments"].append(bullet)
    return res


def _fill_core_sections(buckets: Dict[str, List[Dict[str, Any]]], language: str) -> Dict[str, List[Dict[str, Any]]]:
    # Derive conservative placeholders for empty core sections from existing bullets
    def _base_text(txt: str) -> str:
        t = (txt or "").strip()
        # Drop common prefixes we added
        for pref in [
            "Alinhar: ", "Align: ",
            "Próximo passo de integração/processo: ", "Next step for integration/process: ",
            "Acompanhar ação: ", "Follow up action: ",
        ]:
            if t.startswith(pref):
                return t[len(pref):].strip()
        return t

    # Open Questions from Alignments
    if not buckets.get("open_questions"):
        src = (buckets.get("alignments") or [])[:2]
        derived = []
        for b in src:
            base = _base_text(b.get("text") or "")
            if not base:
                continue
            txt = ("Responder: " + base.rstrip(".?") + "?") if language == "pt-BR" else ("Answer: " + base.rstrip(".?") + "?")
            derived.append({"text": txt, "source_fact_id": b.get("source_fact_id")})
        if derived:
            buckets.setdefault("open_questions", []).extend(derived)

    # Decisions from Alignments
    if not buckets.get("decisions"):
        src = (buckets.get("alignments") or [])[:2]
        derived = []
        for b in src:
            base = _base_text(b.get("text") or "")
            if not base:
                continue
            txt = ("Decidir: " + base.rstrip(". ")) if language == "pt-BR" else ("Decide: " + base.rstrip(". "))
            derived.append({"text": txt, "source_fact_id": b.get("source_fact_id")})
        if derived:
            buckets.setdefault("decisions", []).extend(derived)

    # Risks from Integrations/Next Steps keywords (aggregate into a single synthesized risk)
    if not buckets.get("risks"):
        src = (buckets.get("integrations") or []) + (buckets.get("next_steps") or [])
        bases: List[str] = []
        seen = set()
        for b in src:
            base = _base_text(b.get("text") or "")
            low = base.lower()
            if not base:
                continue
            if any(k in low for k in ["api", "integra", "dependenc", "depende", "pipeline", "protocolo", "webhook", "endpoint", "schema", "esquema"]):
                key = low
                if key not in seen:
                    seen.add(key)
                    bases.append(base)
        if bases:
            if language == "pt-BR":
                joined = "; ".join(bases[:3]) + ("…" if len(bases) > 3 else "")
                txt = f"Mitigar: possíveis atrasos/bloqueios nas integrações previstas ({joined})"
            else:
                joined = "; ".join(bases[:3]) + ("…" if len(bases) > 3 else "")
                txt = f"Mitigate: potential delays/blockers in planned integrations ({joined})"
            buckets.setdefault("risks", []).append({"text": txt})
    return buckets


def _build_sections_next(buckets: Dict[str, List[Dict[str, Any]]], total_minutes: int, language: str, company_context: Optional[str]) -> List[Dict[str, Any]]:
    sections: List[Dict[str, Any]] = []
    labels = _section_labels_next(language)
    core_keys = {"alignments", "open_questions", "decisions", "risks"}
    # Always render core sections; include optional ones only if they have items
    keys_to_render: List[str] = []
    for lab in labels:
        k = lab["key"]
        if k in core_keys or (buckets.get(k)):
            keys_to_render.append(k)
    # Context section at top (short)
    context_minutes = 0
    if company_context and company_context.strip():
        context_minutes = max(3, int(total_minutes * 0.1))  # ~10% or min 3
    # Optional context section at top
    if company_context and company_context.strip():
        ctx_title = "Contexto da empresa" if language == "pt-BR" else "Company Context"
        sections.append({
            "title": ctx_title,
            "minutes": context_minutes,
            "items": [{"heading": ctx_title, "bullets": [{"text": company_context.strip()}]}],
        })
    # Compute weighted minutes for remaining sections
    available = max(0, total_minutes - context_minutes)
    # Weights: non-empty sections get higher weight; empty core get minimal presence
    weights: Dict[str, int] = {}
    for lab in labels:
        key = lab["key"]
        if key not in keys_to_render:
            continue
        items = buckets.get(key) or []
        n = len(items)
        if n > 0:
            weights[key] = 2 + min(5, n)  # cap influence
        else:
            # empty core sections still get small timebox
            weights[key] = 1
    total_weight = sum(weights.values()) or 1
    # Initial allocation
    alloc: Dict[str, int] = {}
    for key, w in weights.items():
        base_min = 3 if len(buckets.get(key) or []) == 0 else 5
        minutes_i = max(base_min, int(available * (w / total_weight)))
        alloc[key] = minutes_i
    # Adjust rounding to match available minutes
    diff = available - sum(alloc.values())
    if diff != 0:
        # Give/take minutes from the heaviest sections first
        order = sorted(alloc.keys(), key=lambda k: weights[k], reverse=True)
        i = 0
        step = 1 if diff > 0 else -1
        while diff != 0 and order:
            k = order[i % len(order)]
            new_val = alloc[k] + step
            if new_val >= (3 if len(buckets.get(k) or []) == 0 else 5):
                alloc[k] = new_val
                diff -= step
            i += 1
            if i > 1000:
                break
    # Emit sections
    for lab in labels:
        key = lab["key"]
        if key not in keys_to_render:
            continue
        items = buckets.get(key) or []
        sections.append({
            "title": lab["title"],
            "minutes": alloc.get(key, 5),
            "items": ([{"heading": lab["title"], "bullets": items[:4]}] if items else []),
        })
    return sections


def _first_non_empty(*values: Any) -> Optional[str]:
    for val in values:
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _bullet_from_fact(fact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    payload = fact.get("payload") or {}
    entities = fact.get("entities") or []
    lang = "pt-BR" if (fact.get("lang") == "pt-BR") else "en-US"
    text = _abstract_text_from_fact(fact, language=lang) or _short_text_from_payload(payload)
    if not text:
        return None
    if _quality_score(text, lang) < 0.45:
        synth = _keywords_phrase([
            payload.get("subject"), payload.get("title"), payload.get("headline"), payload.get("summary"), payload.get("text")
        ], lang)
        text = _refine_phrase(synth or "", lang) if synth else ""
        if _quality_score(text, lang) < 0.45:
            return None
    owner = payload.get("owner")
    if not owner:
        for ent in entities:
            if (ent.get("type") or "").lower() == "person":
                owner = ent.get("display_name")
                break
    due = payload.get("due") or fact.get("due_iso") or fact.get("due_at")
    bullet = {
        "text": text,
        "owner": owner,
        "due": due,
        "source_fact_id": fact.get("fact_id"),
    }
    return bullet


def _categorise_candidates(candidates: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {
        title: [] for title, _ in SECTION_TEMPLATES
    }
    for fact in candidates:
        bullet = _bullet_from_fact(fact)
        if not bullet:
            continue
        fact_type = (fact.get("fact_type") or "").lower()
        placed = False
        for title, accepted in SECTION_TEMPLATES:
            if fact_type in accepted:
                buckets[title].append(bullet)
                placed = True
                break
        if not placed:
            buckets[SECTION_TEMPLATES[0][0]].append(bullet)
    return buckets


def _build_sections(buckets: Dict[str, List[Dict[str, Any]]], total_minutes: int) -> List[Dict[str, Any]]:
    sections = []
    active = [title for title, items in buckets.items() if items]
    if not active:
        return sections
    minutes_per_section = max(5, int(total_minutes / max(1, len(active))))
    for title, _ in SECTION_TEMPLATES:
        bullets = buckets.get(title) or []
        if not bullets:
            continue
        sections.append({
            "title": title,
            "minutes": minutes_per_section,
            "items": [
                {
                    "heading": title,
                    "bullets": bullets[:5],
                }
            ],
        })
    return sections


def _compute_coverage(buckets: Dict[str, List[Dict[str, Any]]]) -> float:
    non_empty = sum(1 for items in buckets.values() if items)
    if non_empty == 0:
        return 0.0
    total_bullets = sum(len(items) for items in buckets.values())
    diversity = non_empty / len(SECTION_TEMPLATES)
    density = min(1.0, total_bullets / 10.0)
    return round(0.4 + 0.4 * diversity + 0.2 * density, 2)


def plan_agenda(
    org_id: str,
    subject: Optional[str],
    candidates: Sequence[Dict[str, Any]],
    *,
    duration_minutes: int = 30,
    language: str = "en-US",
) -> Dict[str, Any]:
    org_id = org_id or DEFAULT_ORG_ID
    buckets = _categorise_candidates(candidates)
    sections = _build_sections(buckets, duration_minutes)
    coverage = _compute_coverage(buckets)
    title = "Reunião" if language == "pt-BR" else "Meeting"
    agenda = {
        "title": title,
        "minutes": duration_minutes,
        "sections": sections,
    }
    choice = "subject" if subject else "default"
    reason = "subject coverage" if subject and coverage >= 0.5 else "default template"
    supporting_fact_ids = [fact.get("fact_id") for fact in candidates if fact.get("fact_id")]
    proposal = {
        "agenda": agenda,
        "choice": choice,
        "reason": reason,
        "subject": {
            "query": subject,
            "coverage": coverage,
            "facts": len(candidates),
        },
        "supporting_fact_ids": supporting_fact_ids,
    }
    return proposal


def plan_agenda_next(
    org_id: str,
    subject: Optional[str],
    candidates: Sequence[Dict[str, Any]],
    *,
    company_context: Optional[str] = None,
    duration_minutes: int = 30,
    language: str = "en-US",
) -> Dict[str, Any]:
    org_id = org_id or DEFAULT_ORG_ID
    buckets = _derive_next_bullets(candidates, language)
    buckets = _fill_core_sections(buckets, language)
    sections = _build_sections_next(buckets, duration_minutes, language, company_context)
    # Simple coverage proxy
    coverage = 1.0 if sections else 0.0
    title = "Reunião" if language == "pt-BR" else "Meeting"
    agenda = {"title": title, "minutes": duration_minutes, "sections": sections}
    choice = "next" if subject else "next-default"
    reason = "forward-looking heuristics"
    supporting_fact_ids = [fact.get("fact_id") for fact in candidates if fact.get("fact_id")]
    return {
        "agenda": agenda,
        "choice": choice,
        "reason": reason,
        "subject": {"query": subject, "coverage": coverage, "facts": len(candidates)},
        "supporting_fact_ids": supporting_fact_ids,
    }


def _compute_idempotency_key(org_id: str, meeting_id: Optional[str], subject: Optional[str], agenda: Dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update((org_id or "").encode("utf-8"))
    h.update((meeting_id or "").encode("utf-8"))
    h.update((subject or "").encode("utf-8"))
    h.update(json.dumps(agenda or {}, sort_keys=True).encode("utf-8"))
    return h.hexdigest()


def persist_agenda_proposal(
    org_id: str,
    proposal: Dict[str, Any],
    *,
    meeting_id: Optional[str] = None,
    transcript_id: Optional[str] = None,
) -> str:
    agenda_obj = proposal.get("agenda") or {}
    subject = proposal.get("subject", {}).get("query")
    idem = _compute_idempotency_key(org_id, meeting_id, subject, agenda_obj)
    payload = {
        "kind": "agenda_proposal",
        "subject": subject,
        "agenda": agenda_obj,
        "choice": proposal.get("choice"),
        "reason": proposal.get("reason"),
        "supporting_fact_ids": proposal.get("supporting_fact_ids", []),
    }
    fact = {
        "org_id": org_id or DEFAULT_ORG_ID,
        "meeting_id": meeting_id,
        "transcript_id": transcript_id,
        "fact_type": "meeting_metadata",
        "status": "proposed",
        "payload": payload,
        "idempotency_key": idem,
    }
    fact_id = db.insert_or_update_fact(fact)
    proposal["idempotency_key"] = idem
    return fact_id
