"""Text quality utilities for extracting clean, actionable bullet text.

This module provides functions to extract forward-looking, action-oriented
text from facts instead of retrospective, noisy summaries.
"""

from typing import Dict, Any, Optional
import re
import unicodedata


def extract_actionable_text(
    fact: Dict[str, Any],
    intent: str,
    language: str = "pt-BR",
) -> str:
    """Extract clean, forward-looking text from fact.
    
    Logic:
    1. If fact has 'action_needed' field → use that
    2. If decision → "Aprovar: [subject]"
    3. If risk → "Mitigar: [risk description]"
    4. If action_item → "Executar: [action]"
    5. Fallback to payload subject, refined
    
    Args:
        fact: Fact dictionary
        intent: Meeting intent (decision_making, problem_solving, etc.)
        language: Language code
        
    Returns:
        Clean, actionable text (max 120 chars)
    """
    import json
    
    ftype = (fact.get("fact_type") or "").lower()
    payload = fact.get("payload") or {}
    
    # Parse payload if it's a JSON string
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    
    # Check for explicit action field
    action_needed = payload.get("action_needed") or payload.get("next_step")
    if action_needed and isinstance(action_needed, str):
        return clean_text(action_needed, language, max_length=120)
    
    # Type-specific extraction
    if ftype in ["decision_needed", "decision"]:
        subject = _extract_subject(payload)
        prefix = "Decidir: " if language == "pt-BR" else "Decide: "
        # Remove "decidir" from subject if already present
        subject_clean = re.sub(r"^(decidir|aprovar)\s+", "", subject, flags=re.IGNORECASE)
        text = f"{prefix}{subject_clean}"
        return clean_text(text, language, max_length=120)
    
    elif ftype == "risk":
        risk_desc = (
            payload.get("risk_description") or
            payload.get("description") or
            _extract_subject(payload)
        )
        prefix = "Mitigar risco: " if language == "pt-BR" else "Mitigate risk: "
        subject_clean = re.sub(r"^(mitigar|risco)\s+", "", risk_desc, flags=re.IGNORECASE)
        text = f"{prefix}{subject_clean}"
        return clean_text(text, language, max_length=120)
    
    elif ftype in ["action_item", "task"]:
        action = (
            payload.get("action") or
            payload.get("task") or
            payload.get("todo") or
            _extract_subject(payload)
        )
        # Already action-oriented; just clean
        return clean_text(action, language, max_length=120)
    
    elif ftype == "blocker":
        blocker = (
            payload.get("blocker_description") or
            payload.get("description") or
            _extract_subject(payload)
        )
        prefix = "Desbloquear: " if language == "pt-BR" else "Unblock: "
        subject_clean = re.sub(r"^(desbloquear|bloqueio)\s+", "", blocker, flags=re.IGNORECASE)
        text = f"{prefix}{subject_clean}"
        return clean_text(text, language, max_length=120)
    
    elif ftype == "milestone":
        milestone = (
            payload.get("milestone") or
            payload.get("goal") or
            _extract_subject(payload)
        )
        prefix = "Alcançar: " if language == "pt-BR" else "Achieve: "
        text = f"{prefix}{milestone}"
        return clean_text(text, language, max_length=120)
    
    elif ftype in ["open_question", "question"]:
        question = (
            payload.get("question") or
            payload.get("query") or
            _extract_subject(payload)
        )
        prefix = "Responder: " if language == "pt-BR" else "Answer: "
        # Remove question mark, add prefix
        question_clean = question.rstrip("?")
        text = f"{prefix}{question_clean}"
        return clean_text(text, language, max_length=120)
    
    # Fallback to subject with intent-based prefix
    subject = _extract_subject(payload)
    return clean_text(subject, language, max_length=120)


def _extract_subject(payload: Dict[str, Any]) -> str:
    """Extract subject/title/text from payload in priority order."""
    candidates = [
        payload.get("subject"),
        payload.get("title"),
        payload.get("name"),
        payload.get("headline"),
        payload.get("summary"),
        payload.get("text"),
        payload.get("description"),
    ]
    
    for candidate in candidates:
        if candidate and isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    
    return ""


def clean_text(text: str, language: str, max_length: int = 120) -> str:
    """Clean and format text for agenda bullets.
    
    - Normalize unicode
    - Remove filler words
    - Capitalize properly
    - Remove trailing punctuation
    - Limit to max_length chars
    - Ensure starts with action verb when possible
    
    Args:
        text: Raw text
        language: Language code
        max_length: Maximum character length
        
    Returns:
        Cleaned text
    """
    if not text or not text.strip():
        return ""
    
    # Normalize unicode
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    
    # Basic cleanup
    text = text.strip()
    text = re.sub(r"\s+", " ", text)  # Collapse whitespace
    
    # Remove common filler prefixes
    if language == "pt-BR":
        fillers = [
            r"^(temos|tem|existe|h[aá])\s+(um[au]?|uma)\s+",
            r"^(a\s+gente|n[oó]s)\s+(tem|precisa|deve)\s+",
            r"^vamos\s+",
            r"^precis(a|amos)\s+(de\s+)?",
            r"^(foi|ser[aá])\s+(discutido|mencionado|falado)\s+que\s+",
        ]
    else:
        fillers = [
            r"^(we|there)\s+(have|has|is|are)\s+",
            r"^we('re|\s+are)\s+",
            r"^(need|should|must)\s+to\s+",
            r"^(it\s+was|will\s+be)\s+(discussed|mentioned)\s+that\s+",
        ]
    
    for filler in fillers:
        text = re.sub(filler, "", text, flags=re.IGNORECASE)
    
    # Remove trailing conjunctions/fluff
    if language == "pt-BR":
        tails = [
            r"\s+(para|pra)\s+que\b.*$",
            r"\s+quando\b.*$",
            r"\s+se\b.*$",
            r"\s+porque\b.*$",
        ]
    else:
        tails = [
            r"\s+so\s+that\b.*$",
            r"\s+when\b.*$",
            r"\s+if\b.*$",
            r"\s+because\b.*$",
        ]
    
    for tail in tails:
        text = re.sub(tail, "", text, flags=re.IGNORECASE)
    
    # Strip again
    text = text.strip()
    
    # Remove trailing punctuation (but keep ? for questions)
    text = text.rstrip(".,;:")
    
    # Truncate to max length at word boundary
    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0]
        if not text.endswith("..."):
            text += "..."
    
    # Capitalize first letter
    if text:
        text = text[0].upper() + text[1:]
    
    return text


def generate_why_text(
    fact: Dict[str, Any],
    language: str = "pt-BR",
) -> str:
    """Generate 'why' justification from fact evidence.
    
    Args:
        fact: Fact dictionary with evidence
        language: Language code
        
    Returns:
        Short justification (e.g., "Bloqueado há 14 dias")
    """
    evidence = fact.get("evidence") or []
    status = fact.get("status", "")
    ftype = fact.get("fact_type", "")
    
    # Try to get best quote
    quote = ""
    if evidence:
        for ev in evidence:
            q = ev.get("quote", "")
            if isinstance(q, str) and len(q.strip()) > 20:
                quote = q.strip()[:100]
                break
    
    # Build why from status/type/quote
    parts = []
    
    # Add urgency indicator
    if _is_overdue(fact):
        parts.append("Atrasado" if language == "pt-BR" else "Overdue")
    elif status == "red":
        parts.append("Crítico" if language == "pt-BR" else "Critical")
    elif status == "yellow":
        parts.append("Atenção" if language == "pt-BR" else "Attention")
    
    # Add age if old
    age_days = _get_age_days(fact)
    if age_days and age_days > 14:
        parts.append(f"Pendente há {age_days} dias" if language == "pt-BR" else f"Pending for {age_days} days")
    
    # Add quote snippet if available
    if quote and not parts:
        # Use quote as justification if no other signals
        prefix = "Evidência: " if language == "pt-BR" else "Evidence: "
        return f"{prefix}{quote[:80]}..."
    
    if parts:
        return " | ".join(parts)
    
    # Fallback: just use quote
    if quote:
        return quote[:80] + "..." if len(quote) > 80 else quote
    
    return ""


def _is_overdue(fact: Dict[str, Any]) -> bool:
    """Check if fact has overdue deadline."""
    from datetime import datetime, timezone
    
    due_iso = fact.get("due_iso") or fact.get("due_at")
    if not due_iso:
        return False
    
    try:
        due = datetime.fromisoformat(due_iso.replace("Z", "+00:00"))
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        return due < now
    except Exception:
        return False


def _get_age_days(fact: Dict[str, Any]) -> Optional[int]:
    """Get age of fact in days."""
    from datetime import datetime, timezone
    
    created_at = fact.get("created_at")
    if not created_at:
        return None
    
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        delta = now - created
        return int(delta.total_seconds() / 86400)
    except Exception:
        return None
