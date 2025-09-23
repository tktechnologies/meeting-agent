import json
import os
from typing import Any, Dict, List
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
    return s


def _deterministic_text(agenda: Dict[str, Any], subject: Dict[str, Any], language: str) -> str:
    def line(s: str) -> str:
        return s.rstrip() + "\n"
    def clean(s: str) -> str:
        # collapse whitespace/newlines and trim long text
        t = " ".join(str(s).split())
        MAX = 160
        return (t if len(t) <= MAX else (t[:MAX-1] + "…"))
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
        return s

    title = agenda.get("title") or ("Reunião" if language == "pt-BR" else "Meeting")
    minutes = agenda.get("minutes") or 30
    out: List[str] = []
    out.append(line(f"{title} — {minutes} min"))
    subj_q = subject.get("query")
    def _is_generic_subject(q: str) -> bool:
        ql = (q or "").strip().lower()
        if not ql:
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
    for sec in sections:
        stitle = sec.get("title") or ("Seção" if language == "pt-BR" else "Section")
        smin = sec.get("minutes") or 0
        out.append(line(f"\n## {stitle} — {smin} min"))
        items = sec.get("items") or []
        for it in items:
            heading = it.get("heading")
            bullets = it.get("bullets") or []
            # If item has only bullets, show heading then bullets
            if heading:
                out.append(line(f"- {heading}:"))
            for b in bullets:
                raw = b.get("text") or b.get("title") or ""
                text = clean(raw)
                text = _sanitize_text(text, language)
                # Skip empty/garbled bullets
                w = text.split()
                if not text or not any(ch.isalnum() for ch in text):
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
                # In PT-BR, mark TBD in Next Steps if no chips
                if language == "pt-BR" and (stitle.lower().startswith("próximos passos") or stitle.lower().startswith("proximos passos")) and not chips:
                    text = text.rstrip(".") + " (TBD)"
                suff = (" [" + "; ".join(chips) + "]") if chips else ""
                out.append(line(f"  - {text}{suff}"))
        # If section has no items, leave the header as is
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


def agenda_to_text(result: Dict[str, Any], language: str, use_llm: bool = False) -> str:
    agenda = result.get("agenda") or {}
    subject = result.get("subject") or {}
    if use_llm:
        return _llm_text(agenda, subject, language)
    return _deterministic_text(agenda, subject, language)
