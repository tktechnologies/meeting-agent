import json
import os
from typing import Any, Dict, List, Tuple
import re


def _sanitize_text(text: str, language: str) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    low = s.lower()
    # Remove common speaker/time artifacts (pt/en)
    s = re.sub(r"\bParticipante\s+\d+\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\bParticipant\s+\d+\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\(\d{1,2}:\d{2}(?::\d{2})?\)", "", s)  # (mm:ss) or (hh:mm:ss)
    # Remove stray initials like 'GS.' 'SR.' at boundaries
    s = re.sub(r"\b[A-Z]{1,3}\.(?=\s|$)", "", s)
    # Drop leading interjections/fillers (pt/en)
    fillers_pt = ["olha", "então", "tipo", "né", "assim", "porque assim", "ok", "bom", "tá", "ta", "aí", "ai"]
    fillers_en = ["well", "so", "like", "uh", "um", "okay", "ok", "hmm"]
    fillers = fillers_pt if language == "pt-BR" else fillers_en
    s = re.sub(r"^(?:" + "|".join(re.escape(w) for w in fillers) + r")[\s,:-]+", "", s, flags=re.IGNORECASE)
    # Keep the first reasonably complete sentence/clause
    parts = re.split(r"(?<=[\.!?])\s+", s)
    if parts:
        first = parts[0].strip()
        # If the first is too short, try the next
        if len(first) < 12 and len(parts) > 1:
            first = parts[1].strip()
        s = first
    # Drop awkward malformed starts (PT)
    if language == "pt-BR":
        if re.match(r"^(h[áa]\s+com\b|depega\b|a minha melhor\b)", s.lower()):
            return ""
    # Remove multiple punctuation, collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"[\.,]{2,}$", ".", s)
    # Remove dangling last token if it's very short and adds noise
    tokens = s.split()
    if len(tokens) > 3 and len(tokens[-1]) <= 2 and not tokens[-1][-1].isdigit():
        s = " ".join(tokens[:-1])
    # Drop fragments that are too short or non-informative
    if len(s) < 6 or len(s.split()) < 3 or not any(ch.isalpha() for ch in s):
        return ""
    # Extra PT-BR hygiene: remove trailing coordinating conjunctions and drop acronym-heavy short bullets
    if language == "pt-BR":
        # cut trailing conjunction-only endings
        s = re.sub(r"\b(e|mas|porque|então|entao)\s*$", "", s, flags=re.IGNORECASE).strip()
        tokens = s.split()
        if tokens:
            upper_ratio = sum(t.isupper() for t in tokens) / max(1, len(tokens))
            if upper_ratio > 0.5 and len(tokens) < 5:
                return ""
    return s


class _RefIndex:
    def __init__(self):
        self.key_to_fid: Dict[str, str] = {}
        self.fid_to_ref: Dict[str, Dict[str, Any]] = {}
        self.order: List[str] = []

    def _key(self, r: Dict[str, Any]) -> str:
        return (
            (r.get("id") and f"id:{r['id']}")
            or (r.get("url") and f"url:{r['url']}")
            or (r.get("excerpt") and f"ex:{(r.get('excerpt') or '')[:50]}")
            or None
        ) or str(hash(str(sorted(r.items()))))

    def add(self, r: Dict[str, Any]) -> str:
        k = self._key(r)
        if k in self.key_to_fid:
            return self.key_to_fid[k]
        fid = f"F{len(self.order)+1}"
        self.key_to_fid[k] = fid
        self.fid_to_ref[fid] = r
        self.order.append(fid)
        return fid

    def all(self) -> List[Tuple[str, Dict[str, Any]]]:
        return [(fid, self.fid_to_ref[fid]) for fid in self.order]


from datetime import datetime, timezone, timedelta


def _parse_date(s: Any):
    if not s or not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _is_stale(dt):
    if not dt:
        return False
    return (datetime.now(timezone.utc) - dt) > timedelta(days=60)


def _confidence_label(ref: Dict[str, Any]):
    c = ref.get("confidence")
    try:
        if isinstance(c, (int, float)):
            return "Alta" if c >= 0.75 else ("Média" if c >= 0.5 else "Baixa")
    except Exception:
        pass
    st = (ref.get("status") or "").lower()
    return "Média" if st in {"validated", "published"} else "Baixa"


def _deterministic_text(agenda: Dict[str, Any], subject: Dict[str, Any], language: str, *, with_refs: bool = False, max_refs_per_bullet: int = 2) -> str:
    ref_index = _RefIndex() if with_refs else None
    def line(s: str) -> str:
        return s.rstrip() + "\n"
    def clean(s: str) -> str:
        # collapse whitespace/newlines and trim long text
        t = " ".join(str(s).split())
        MAX = 160
        return (t if len(t) <= MAX else (t[:MAX-1] + "…"))
    def _as_subject_query(sj: Any):
        if isinstance(sj, str):
            sj = sj.strip()
            return sj or None
        if isinstance(sj, dict):
            for k in ("query", "text", "title"):
                v = (sj.get(k) or "").strip()
                if v:
                    return v
        return None
    def _is_generic_request(text: str, lang: str) -> bool:
        import re as _re
        low = (text or "").strip().lower()
        if not low:
            return True
        if lang == "pt-BR":
            pats = [r"^fa[cç]a a pauta", r"^crie a pauta", r"^fazer a pauta", r"^montar a pauta", r"pr[óo]xima reuni[ãa]o"]
        else:
            pats = [r"^make (the )?agenda", r"^create (the )?agenda", r"^build (the )?agenda", r"next meeting"]
        return any(_re.search(p, low) for p in pats)
    def _strip_prefix_for_section(text: str, section_title: str) -> str:
        low = (section_title or "").lower()
        import re as _re
        # Decisions section: remove leading "Decidir:" / "Decide:" since section already implies it
        if low.startswith("decis"):
            return _re.sub(r"^(?:decidir|decide):\s*", "", text, flags=_re.IGNORECASE)
        # Open Questions section: remove redundant "Responder:" / "Answer:" prefix
        if "perguntas" in low or "open questions" in low:
            return _re.sub(r"^(?:responder|answer):\s*", "", text, flags=_re.IGNORECASE)
        # Risks section: remove redundant "Mitigar:" / "Mitigate:" prefix
        if low.startswith("riscos") or low.startswith("risks"):
            return _re.sub(r"^(?:mitigar|mitigate):\s*", "", text, flags=_re.IGNORECASE)
        return text
    def rewrite_pt(text: str, section_title: str) -> str:
        s = text
        low = s.lower()
        import re as _re
        low_clean = _re.sub(r"[\s\.,;:!?]+$", "", low)
        # Decisions phrased as questions
        if "recortar a entrega" in low or ("dividir a entrega" in low and "lote" in low):
            return "Dividir a entrega em dois lotes?"
        if ("duplicada" in low) and ("catálogo" in low or "catalogo" in low):
            return "Entidade duplicada no catálogo: mesclar/excluir?"
        # Skip vague bullets
        if low_clean in {"reduzir risco", "reduzir riscos", "mitigar risco", "mitigar riscos"}:
            return ""
        # Objectives phrasing (make them goals)
        if section_title.lower().startswith("objetivos"):
            if low.endswith("?") and not low.startswith("decidir"):
                return "Decidir: " + s.rstrip("?") + "?"
            if low.startswith("dividir a entrega"):
                return "Decidir: " + s.rstrip(".")
            if low.startswith("rever") or low.startswith("revisar"):
                return "Revisar: " + s[len("revisar"):].strip().rstrip(".")
        
        # Append (TBD) in Próximos Passos when owner/due missing is handled later
    # Future polish: we could drop ultra-generic bullets like "Alinhar objetivos" once more context rules exist
        return s

    title = agenda.get("title") or ("Reunião" if language == "pt-BR" else "Meeting")
    minutes = agenda.get("minutes") or 30
    out: List[str] = []
    out.append(line(f"{title} — {minutes} min"))
    subj_q = _as_subject_query(subject)
    def _is_generic_subject(q: str) -> bool:
        ql = (q or "").strip().lower()
        if not ql:
            return True
        # Duration-only or time-like subjects are generic
        if re.search(r"^\d+\s*(min|mins|minuto|minutos|minutes|hora|horas|hour|hours)\b", ql):
            return True
        if re.fullmatch(r"\d+", ql):
            return True
        patterns_pt = [
            r"^fa[cç]a a pauta", r"^crie a pauta", r"^fazer a pauta", r"^montar a pauta", r"pr[óo]xima reuni[ãa]o",
        ]
        patterns_en = [
            r"^make the agenda", r"^create the agenda", r"^build the agenda", r"next meeting",
        ]
        pats = patterns_pt if language == "pt-BR" else patterns_en
        return any(re.search(p, ql) for p in pats)
    if subj_q and not _is_generic_subject(subj_q):
        if language == "pt-BR":
            out.append(line(f"Assunto: {subj_q}"))
        else:
            out.append(line(f"Subject: {subj_q}"))
    sections = agenda.get("sections") or []
    # Pre-pass: apply risk filtering rules before rendering to avoid noisy lines
    def _filter_risks(sec_list):
        import re as _re
        cleaned = []
        seen_norm = set()
        for s in sec_list:
            title = (s.get("title") or "").strip()
            if not title.lower().startswith("ris") and not title.lower().startswith("risc"):
                cleaned.append(s)
                continue
            items = s.get("items") or []
            new_items = []
            for it in items:
                bullets = it.get("bullets") or []
                new_bullets = []
                for b in bullets:
                    txt = (b.get("text") or "").strip()
                    if not txt:
                        continue
                    low = txt.lower()
                    # Strip trailing punctuation for normalization
                    norm = low.rstrip(" .,:;!?")
                    # Remove terminal conjunctions
                    norm = _re.sub(r"\b(e|mas|porque|então|entao)$", "", norm).strip()
                    # Filter starts
                    bad_starts = ("mas ", "é isso", "e isso", "eu ", "a gente ")
                    if any(norm.startswith(bs) for bs in bad_starts):
                        continue
                    # Filter endings still ending with lone conjunction
                    if _re.search(r"\b(e|mas|porque|então|entao)$", norm):
                        continue
                    # Token check
                    toks = [t for t in _re.findall(r"[\wÀ-ÿ]+", norm) if t]
                    if len(toks) < 5:
                        continue
                    # Dedupe near-identical
                    norm_key = norm
                    if norm_key in seen_norm:
                        continue
                    seen_norm.add(norm_key)
                    # Rebuild possibly trimmed text (capitalize first char)
                    if norm and not norm[0].isupper():
                        norm = norm[0].upper() + norm[1:]
                    nb = dict(b)
                    nb["text"] = norm
                    new_bullets.append(nb)
                if new_bullets:
                    new_items.append({"heading": it.get("heading"), "bullets": new_bullets})
            # If after filtering no bullets, we skip; we'll add fallback later
            s2 = dict(s)
            s2["items"] = new_items
            cleaned.append(s2)
        # After processing, ensure at least one risk bullet if there was originally a Risks section
        had_risks = any((sec.get("title") or "").lower().startswith("ris") for sec in sec_list)
        if had_risks:
            # Find risk section in cleaned
            for sec in cleaned:
                if (sec.get("title") or "").lower().startswith("ris"):
                    total_bullets = sum(len(it.get("bullets") or []) for it in (sec.get("items") or []))
                    if total_bullets == 0:
                        fallback_text = (
                            "Mitigar: possíveis atrasos ou bloqueios críticos nos próximos marcos" if language == "pt-BR" else
                            "Mitigate: potential delays or blockers impacting upcoming milestones"
                        )
                        sec["items"] = [{"heading": sec.get("title"), "bullets": [{"text": fallback_text}]}]
                    break
        return cleaned

    sections = _filter_risks(sections)
    for sec in sections:
        stitle = sec.get("title") or ("Seção" if language == "pt-BR" else "Section")
        smin = sec.get("minutes") or 0
        items = sec.get("items") or []
        section_lines: List[str] = []
        for it in items:
            heading = it.get("heading")
            bullets = it.get("bullets") or []
            # Buffer item-level lines to only include heading if there are valid bullets
            item_lines: List[str] = []
            for b in bullets:
                raw = b.get("text") or b.get("title") or ""
                text = clean(raw)
                text = _sanitize_text(text, language)
                # Remove redundant action prefixes that duplicate section semantics
                text = _strip_prefix_for_section(text, stitle)
                # Skip empty/garbled bullets
                w = text.split()
                if not text or not any(ch.isalnum() for ch in text):
                    continue
                # Skip bullets identical to subject or generic requests
                norm_text = text.strip().rstrip(".").lower()
                norm_subj = (subj_q or "").strip().rstrip(".").lower()
                if norm_subj and norm_text == norm_subj:
                    continue
                if _is_generic_request(norm_text, language):
                    continue
                if w and (not w[0][:1].isupper() and len(w[0]) <= 4):
                    continue
                if len(w) == 1 and w[0].islower() and len(w[0]) <= 7 and not w[0][0].isdigit():
                    continue
                if language == "pt-BR":
                    text = rewrite_pt(text, stitle)
                    if not text:
                        continue
                else:
                    # EN vague cleanups
                    low = text.lower().strip().strip(".?!")
                    if low in {"reduce risk", "reduce risks", "mitigate risk", "mitigate risks"}:
                        continue
                owner = b.get("owner")
                due = b.get("due")
                chips = []
                # PT-BR: omit owners to avoid invented placeholders
                if owner and language != "pt-BR":
                    chips.append(("Owner") + f": {owner}")
                if due:
                    chips.append(("Prazo" if language == "pt-BR" else "Due") + f": {due}")
                # With refs: register refs and annotate bullet with [F*]
                tag = ""
                extra = 0
                conf_annot = ""
                if with_refs and ref_index is not None:
                    fids: List[str] = []
                    refs = b.get("refs") or []
                    for rr in refs:
                        try:
                            fid = ref_index.add(rr)
                            fids.append(fid)
                        except Exception:
                            continue
                    if fids:
                        tag = "".join([f"[{fid}]" for fid in fids[:max_refs_per_bullet]])
                        extra = max(0, len(fids) - max_refs_per_bullet)
                        # Optional: if first ref confidence is low, annotate
                        first_ref = refs[0]
                        if _confidence_label(first_ref) == "Baixa":
                            conf_annot = " (Confiança: Baixa)"
                # In PT-BR, mark TBD in Next Steps if no chips
                if language == "pt-BR" and (stitle.lower().startswith("próximos passos") or stitle.lower().startswith("proximos passos")) and not chips:
                    text = text.rstrip(".") + " (TBD)"
                suff = (" [" + "; ".join(chips) + "]") if chips else ""
                text_line = f"  - {text}{suff}{conf_annot}"
                if tag:
                    text_line = f"{text_line} {tag}"
                if extra > 0:
                    text_line = f"{text_line} (+{extra})"
                item_lines.append(line(text_line))
            # Only add heading if we have any bullet lines for this item
            if item_lines:
                if heading:
                    section_lines.append(line(f"- {heading}:"))
                section_lines.extend(item_lines)
        # Render the section header only if we collected any lines
        if section_lines:
            out.append(line(f"\n## {stitle} — {smin} min"))
            out.extend(section_lines)
    # Append references block if requested
    if with_refs and ref_index is not None and ref_index.order:
        out.append("\n")
        out.append(line("## Referências" if language == "pt-BR" else "## References"))
        for fid, ref in ref_index.all():
            date = _parse_date(ref.get("updated_at"))
            date_s = date.date().isoformat() if date else ""
            lab = _confidence_label(ref)
            stale = " \u26A0\uFE0F Desatualizado" if (language == "pt-BR" and _is_stale(date)) else (" \u26A0\uFE0F Stale" if _is_stale(date) else "")
            title_or_excerpt = ref.get("title") or ref.get("excerpt") or "(sem título)"
            source = ref.get("source") or ref.get("fact_type") or ""
            owner = f", {ref['owner']}" if ref.get("owner") else ""
            status = (ref.get("status") or "").lower()
            if language == "pt-BR":
                line_txt = f"{fid} — {title_or_excerpt} ({status}, {date_s}, {source}{owner}; Confiança: {lab}){stale}"
            else:
                # Simple EN variant
                line_txt = f"{fid} — {title_or_excerpt} ({status}, {date_s}, {source}{owner}; Confidence: {lab}){stale}"
            out.append(line(line_txt))
    return "".join(out).strip() + "\n"


def _llm_text(agenda: Dict[str, Any], subject: Dict[str, Any], language: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
    if not api_key:
        return _deterministic_text(agenda, subject, language)
    base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")
    model = (
        os.environ.get("MEETING_AGENT_LLM_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or "gpt-5-nano"
    )

    system = (
        "Você transforma um JSON de agenda em um texto de agenda objetivo, claro e pronto para envio. Use linguagem concisa, bullets curtos e minutos por seção."
        if language == "pt-BR"
        else "You turn an agenda JSON into a polished, ready-to-send agenda text with concise bullets and section timeboxes."
    )
    user_obj = {
        "language": language,
        "agenda": agenda,
        "subject": subject,
        "instructions": (
            "Escreva uma agenda pronta para envio, use títulos de seção, minutos e bullets."
        )
        if language == "pt-BR"
        else "Write a ready-to-send agenda with section titles, minutes, and short bullets.",
    }
    user = (
        "Formate a agenda abaixo. Retorne apenas o texto final, sem comentários.\n\n"
        if language == "pt-BR"
        else "Format the agenda below. Return only the final text, no commentary.\n\n"
    ) + json.dumps(user_obj, ensure_ascii=False)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    # Prefer openai client if available, else fallback to raw HTTP
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key, base_url=base_url)
        kwargs = {}
        if "gpt-5" in model:
            kwargs["reasoning"] = {"effort": os.environ.get("MEETING_AGENT_REASONING_EFFORT", "high")}
        resp = client.chat.completions.create(model=model, messages=messages, **kwargs)
        text = resp.choices[0].message.content or ""
        if not isinstance(text, str) or not text.strip():
            return _deterministic_text(agenda, subject, language)
        return text.strip() + "\n"
    except Exception:
        pass

    # Raw HTTP fallback using stdlib
    try:
        import urllib.request
        import time
        url = (base_url.rstrip("/") if base_url else "https://api.openai.com/v1") + "/chat/completions"
        payload = json.dumps({"model": model, "messages": messages, "reasoning": {"effort": "high"}}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            text = body["choices"][0]["message"]["content"]
            if not isinstance(text, str) or not text.strip():
                return _deterministic_text(agenda, subject, language)
            return text.strip() + "\n"
    except Exception:
        return _deterministic_text(agenda, subject, language)


def agenda_to_text(result: Dict[str, Any], language: str, use_llm: bool = False, with_refs: bool = False, max_refs_per_bullet: int = 2) -> str:
    agenda = result.get("agenda") or {}
    subject = result.get("subject") or {}
    if use_llm:
        return _llm_text(agenda, subject, language)
    return _deterministic_text(agenda, subject, language, with_refs=with_refs, max_refs_per_bullet=max_refs_per_bullet)


def agenda_to_json(obj: Dict[str, Any], language: str = "pt-BR", with_refs: bool = True, max_refs_per_bullet: int = 3) -> Dict[str, Any]:
    agenda = obj.get("agenda") or {}
    subject = obj.get("subject")
    ref_index = _RefIndex() if with_refs else None
    # Produce a shallow copy of sections with bullets and refs; de-duplicate references
    out_sections: List[Dict[str, Any]] = []
    for sec in (agenda.get("sections") or []):
        items_out: List[Dict[str, Any]] = []
        for it in (sec.get("items") or []):
            bullets_out: List[Dict[str, Any]] = []
            for b in (it.get("bullets") or []):
                bb = {k: v for k, v in b.items() if k != "refs"}
                refs = b.get("refs") or []
                if with_refs and ref_index is not None and refs:
                    fids: List[str] = []
                    for rr in refs:
                        try:
                            fid = ref_index.add(rr)
                            fids.append(fid)
                        except Exception:
                            continue
                    # Keep full refs on bullet but might be long; we keep as provided
                    bb["refs"] = refs[:]
                elif refs:
                    bb["refs"] = refs[:]
                bullets_out.append(bb)
            items_out.append({"heading": it.get("heading"), "bullets": bullets_out})
        out_sections.append({
            "title": sec.get("title"),
            "minutes": sec.get("minutes"),
            "items": items_out,
        })
    references: List[Dict[str, Any]] = []
    if with_refs and ref_index is not None:
        references = [ref for (_fid, ref) in ref_index.all()]
    return {
        "subject": subject,
        "minutes": agenda.get("minutes"),
        "sections": out_sections,
        "references": references,
    }
