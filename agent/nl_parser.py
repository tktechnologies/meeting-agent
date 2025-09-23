import re
from dataclasses import dataclass
from typing import Optional, Dict, Any

from .config import default_timezone, default_window_days, default_duration_minutes


@dataclass
class AgendaNLRequest:
    text: str
    org_hint: Optional[str]
    meeting_hint: Optional[str]
    subject: Optional[str]
    window_days: int
    target_duration_minutes: int
    language: str
    timezone: str


def _detect_language(text: str) -> str:
    s = (text or "").lower()
    # Token-based heuristic to avoid substring false positives
    words = re.findall(r"[a-záéíóúâêôãõç]+", s)
    if not words:
        return "en-US"
    pt_tokens = {"sobre", "reunião", "proxima", "próxima", "amanha", "amanhã", "sexta", "terça", "terca", "quarta", "interno", "interna"}
    en_tokens = {"about", "meeting", "today", "tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday"}
    pt = sum(1 for w in words if w in pt_tokens)
    en = sum(1 for w in words if w in en_tokens)
    has_accents = any(ch in s for ch in "áéíóúâêôãõç")
    if pt > en or (pt == en and has_accents):
        return "pt-BR"
    return "en-US"


def _extract_subject(text: str, lang: str) -> Optional[str]:
    s = text.strip()
    if not s:
        return None
    if lang == "pt-BR":
        # sobre <assunto>
        m = re.search(r"(?i)\bsobre\s+(.+)$", s)
        if m:
            out = m.group(1).strip().strip(". ")
            out = re.sub(r"\s*\([^)]*\)\s*$", "", out)  # drop trailing (..)
            return out
    else:
        # about <subject>
        m = re.search(r"(?i)\babout\s+(.+)$", s)
        if m:
            out = m.group(1).strip().strip(". ")
            out = re.sub(r"\s*\([^)]*\)\s*$", "", out)  # drop trailing (..)
            return out
    # fallback: last comma-delimited chunk if it seems like a topic
    parts = [p.strip() for p in re.split(r"[,:]", s) if p.strip()]
    if parts:
        tail = parts[-1]
        # discard common date/time tokens
        if not re.search(r"(?i)today|tomorrow|next|\bseg|ter|qua|qui|sex|sab|dom|segunda|terça|quarta|quinta|sexta", tail):
            return tail
    return None


def _extract_org_hint(text: str) -> Optional[str]:
    # English: for <org> ... (stop before time hints and about/on)
    m = re.search(r"(?i)\bfor\s+(.+?)\s*(?=(about|on|,|$|today|tomorrow|next\s+\w+))", text)
    if m:
        out = m.group(1).strip().strip(". ")
        out = re.sub(r"^(?:da|do|de|d’|d'|a|o|as|os)\s+", "", out, flags=re.IGNORECASE)
        return out
    # Portuguese: para <org> ...
    m = re.search(r"(?i)\bpara\s+(.+?)\s*(?=(sobre|,|$|hoje|amanhã|próxima\s+\w+))", text)
    if m:
        out = m.group(1).strip().strip(". ")
        out = re.sub(r"^(?:da|do|de|d’|d'|a|o|as|os)\s+", "", out, flags=re.IGNORECASE)
        return out
    # Also accept: agenda <org> ...
    m = re.search(r"(?i)\bagenda\s+(?:da|do|de)?\s*(.+?)\s*(?=(sobre|about|,|$|hoje|amanhã|today|tomorrow|next\s+\w+))", text)
    if m:
        out = m.group(1).strip().strip(". ")
        out = re.sub(r"^(?:da|do|de|d’|d'|a|o|as|os)\s+", "", out, flags=re.IGNORECASE)
        return out
    # Portuguese: com <org> ... (e.g., "reunião com a BYD")
    m = re.search(r"(?i)\bcom\s+(?:a|o|as|os)?\s*(.+?)\s*(?=(sobre|,|$|hoje|amanhã|próxima\s+\w+))", text)
    if m:
        out = m.group(1).strip().strip(". ")
        out = re.sub(r"^(?:da|do|de|d’|d'|a|o|as|os)\s+", "", out, flags=re.IGNORECASE)
        return out
    # English: with <org> ...
    m = re.search(r"(?i)\bwith\s+(?:the\s+)?(.+?)\s*(?=(about|on|,|$|today|tomorrow|next\s+\w+))", text)
    if m:
        out = m.group(1).strip().strip(". ")
        out = re.sub(r"^(?:the|da|do|de|d’|d'|a|o|as|os)\s+", "", out, flags=re.IGNORECASE)
        return out
    return None


def _extract_meeting_hint(text: str) -> Optional[str]:
    # MVP: keep as raw phrase like "next Tuesday", "hoje", etc.
    m = re.search(r"(?i)(today|tomorrow|next\s+\w+|hoje|amanhã|próxima\s+\w+)", text)
    if m:
        return m.group(1)
    return None


def parse_nl(text: str, defaults: Optional[Dict[str, Any]] = None) -> AgendaNLRequest:
    defaults = defaults or {}
    lang = _detect_language(text)
    tz = defaults.get("timezone") or default_timezone()
    window_days = int(defaults.get("window_days") or default_window_days())
    minutes = int(defaults.get("target_duration_minutes") or default_duration_minutes())
    org = defaults.get("org_name") or _extract_org_hint(text)
    mt_hint = _extract_meeting_hint(text)
    subject = defaults.get("subject") or _extract_subject(text, lang)
    return AgendaNLRequest(
        text=text,
        org_hint=org,
        meeting_hint=mt_hint,
        subject=subject,
        window_days=window_days,
        target_duration_minutes=minutes,
        language=lang,
        timezone=tz,
    )
