"""Goal-oriented agenda planner v3.

This planner builds forward-looking agendas based on meeting intent
and actionable facts, not retrospective summaries.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from .. import db_router as db
from . import text_quality
from ..config import DEFAULT_ORG_ID


def plan_agenda_v3(
    org_id: str,
    subject: str,
    intent: str,
    workstreams: List[Dict[str, Any]],
    actionable_facts: List[Dict[str, Any]],
    duration_minutes: int,
    language: str = "pt-BR",
) -> Dict[str, Any]:
    """Build forward-looking agenda based on intent and actionable facts.
    
    Structure:
    1. Opening (5-10%): Goal + Why this meeting
    2. Core Sections (70-80%, intent-driven): Decisions / Problem Solving / Planning / etc.
    3. Next Steps (10-15%): Who does what by when
    4. Parking Lot (optional): Items deferred
    
    Args:
        org_id: Organization ID
        subject: Meeting subject
        intent: Meeting intent (decision_making, problem_solving, etc.)
        workstreams: List of workstreams
        actionable_facts: Pre-filtered actionable facts with urgency_score
        duration_minutes: Meeting duration
        language: Language code
        
    Returns:
        Agenda proposal with v2.0 metadata
    """
    org_id = org_id or DEFAULT_ORG_ID
    
    # Step 1: Build opening section
    opening = build_opening_section(
        subject, intent, workstreams, actionable_facts, duration_minutes, language
    )
    
    # Step 2: Build core sections based on intent
    core_sections = build_intent_driven_sections(
        intent, actionable_facts, workstreams, duration_minutes, language
    )
    
    # Step 3: Build closing section (next steps)
    closing = build_next_steps_section(actionable_facts, duration_minutes, language)
    
    # Step 4: Add parking lot if needed (low-priority items)
    parking_lot = build_parking_lot(actionable_facts, duration_minutes, language)
    
    sections = [opening] + core_sections + [closing]
    if parking_lot and parking_lot.get("items"):
        sections.append(parking_lot)
    
    # Build metadata v2.0
    metadata = build_metadata_v2(workstreams, actionable_facts, intent, language)
    
    # Build title
    title = build_agenda_title(subject, intent, workstreams, language)
    
    agenda = {
        "title": title,
        "minutes": duration_minutes,
        "sections": sections,
        "_metadata": metadata,
    }
    
    return {
        "agenda": agenda,
        "choice": "intent_driven_v3",
        "reason": f"Planejamento orientado a {intent}" if language == "pt-BR" else f"Intent-driven planning: {intent}",
        "subject": {"query": subject, "coverage": 1.0, "facts": len(actionable_facts)},
        "supporting_fact_ids": [f.get("fact_id") for f in actionable_facts if f.get("fact_id")],
    }


def build_opening_section(
    subject: str,
    intent: str,
    workstreams: List[Dict[str, Any]],
    facts: List[Dict[str, Any]],
    duration: int,
    language: str,
) -> Dict[str, Any]:
    """Build opening section with goal and context."""
    opening_minutes = max(3, int(duration * 0.1))
    
    # Build goal bullet
    goal_bullet = build_goal_bullet(subject, intent, workstreams, language)
    
    # Build context bullets (2-3 key facts for background)
    context_bullets = []
    context_facts = [f for f in facts if (f.get("fact_type") or "").lower() in ["context", "objective", "milestone"]][:3]
    for fact in context_facts:
        text = text_quality.extract_actionable_text(fact, intent, language)
        why = fact.get("why_relevant", "")
        if text:
            context_bullets.append({
                "text": text,
                "why": why,
                "refs": [build_ref(fact)],
            })
    
    items = []
    if goal_bullet:
        items.append({
            "heading": "Meta" if language == "pt-BR" else "Goal",
            "bullets": [goal_bullet],
        })
    
    if context_bullets:
        items.append({
            "heading": "Contexto" if language == "pt-BR" else "Context",
            "bullets": context_bullets,
        })
    
    return {
        "title": "Abertura" if language == "pt-BR" else "Opening",
        "minutes": opening_minutes,
        "items": items,
    }


def build_goal_bullet(
    subject: str,
    intent: str,
    workstreams: List[Dict[str, Any]],
    language: str,
) -> Optional[Dict[str, str]]:
    """Build goal bullet based on intent."""
    if language == "pt-BR":
        intent_goals = {
            "decision_making": f"Tomar decisões sobre {subject}",
            "problem_solving": f"Resolver problemas relacionados a {subject}",
            "planning": f"Planejar ações para {subject}",
            "alignment": f"Alinhar entendimento sobre {subject}",
            "status_update": f"Atualizar status de {subject}",
            "kickoff": f"Iniciar trabalho em {subject}",
        }
    else:
        intent_goals = {
            "decision_making": f"Make decisions about {subject}",
            "problem_solving": f"Resolve problems related to {subject}",
            "planning": f"Plan actions for {subject}",
            "alignment": f"Align understanding of {subject}",
            "status_update": f"Update status of {subject}",
            "kickoff": f"Kickoff work on {subject}",
        }
    
    goal_text = intent_goals.get(intent, subject)
    
    # Add workstream context if available
    ws_context = ""
    if workstreams and len(workstreams) == 1:
        ws_status = workstreams[0].get("status", "green")
        if ws_status in ["yellow", "red"]:
            ws_context = f" (Status: {ws_status})"
    
    return {
        "text": goal_text + ws_context,
        "why": "",
    }


def build_intent_driven_sections(
    intent: str,
    facts: List[Dict[str, Any]],
    workstreams: List[Dict[str, Any]],
    duration: int,
    language: str,
) -> List[Dict[str, Any]]:
    """Build core sections based on meeting intent."""
    core_duration = int(duration * 0.75)  # 75% for core content
    
    if intent == "decision_making":
        return build_decision_sections(facts, workstreams, core_duration, language)
    
    elif intent == "problem_solving":
        return build_problem_solving_sections(facts, workstreams, core_duration, language)
    
    elif intent == "planning":
        return build_planning_sections(facts, workstreams, core_duration, language)
    
    elif intent == "alignment":
        return build_alignment_sections(facts, workstreams, core_duration, language)
    
    elif intent == "status_update":
        return build_status_sections(facts, workstreams, core_duration, language)
    
    else:  # kickoff or unknown
        return build_kickoff_sections(facts, workstreams, core_duration, language)


def build_decision_sections(
    facts: List[Dict[str, Any]],
    workstreams: List[Dict[str, Any]],
    duration: int,
    language: str,
) -> List[Dict[str, Any]]:
    """Build sections for decision-making meetings.
    
    Structure: Context (10%) → Decisions (70%) → Implications (20%)
    """
    sections = []
    
    # Filter facts by type (normalize to lowercase)
    decision_facts = [f for f in facts if (f.get("fact_type") or "").lower() in ["decision_needed", "decision"]][:10]
    risk_facts = [f for f in facts if (f.get("fact_type") or "").lower() in ["risk", "blocker"]][:5]
    
    # 1. Context (if we have background facts)
    context_facts = [f for f in facts if (f.get("fact_type") or "").lower() in ["context", "objective"]][:2]
    if context_facts:
        context_minutes = max(3, int(duration * 0.1))
        context_bullets = []
        for fact in context_facts:
            text = text_quality.extract_actionable_text(fact, "decision_making", language)
            if text:
                context_bullets.append({
                    "text": text,
                    "why": fact.get("why_relevant", ""),
                    "refs": [build_ref(fact)],
                })
        
        if context_bullets:
            sections.append({
                "title": "Contexto" if language == "pt-BR" else "Context",
                "minutes": context_minutes,
                "items": [{"heading": "", "bullets": context_bullets}],
            })
    
    # 2. Decisions (main section)
    if decision_facts:
        decision_minutes = int(duration * 0.7)
        decision_bullets = []
        for fact in decision_facts:
            text = text_quality.extract_actionable_text(fact, "decision_making", language)
            why = fact.get("why_relevant", "")
            owner = fact.get("payload", {}).get("owner")
            
            if text:
                decision_bullets.append({
                    "text": text,
                    "why": why,
                    "owner": owner,
                    "refs": [build_ref(fact)],
                })
        
        sections.append({
            "title": "Decisões" if language == "pt-BR" else "Decisions",
            "minutes": decision_minutes,
            "items": [{"heading": "", "bullets": decision_bullets}],
        })
    
    # 3. Implications (risks/impacts)
    if risk_facts:
        implications_minutes = int(duration * 0.2)
        risk_bullets = []
        for fact in risk_facts:
            text = text_quality.extract_actionable_text(fact, "decision_making", language)
            why = fact.get("why_relevant", "")
            
            if text:
                risk_bullets.append({
                    "text": text,
                    "why": why,
                    "refs": [build_ref(fact)],
                })
        
        sections.append({
            "title": "Implicações" if language == "pt-BR" else "Implications",
            "minutes": implications_minutes,
            "items": [{"heading": "", "bullets": risk_bullets}],
        })
    
    return sections


def build_problem_solving_sections(
    facts: List[Dict[str, Any]],
    workstreams: List[Dict[str, Any]],
    duration: int,
    language: str,
) -> List[Dict[str, Any]]:
    """Build sections for problem-solving meetings.
    
    Structure: Problem Statement → Solutions → Action Plan
    """
    sections = []
    
    # Filter facts
    blocker_facts = [f for f in facts if (f.get("fact_type") or "").lower() in ["blocker", "risk"]][:8]
    action_facts = [f for f in facts if (f.get("fact_type") or "").lower() in ["action_item", "task"]][:6]
    
    # 1. Problem Statement
    if blocker_facts:
        problem_minutes = int(duration * 0.4)
        problem_bullets = []
        for fact in blocker_facts[:5]:
            text = text_quality.extract_actionable_text(fact, "problem_solving", language)
            why = fact.get("why_relevant", "")
            
            if text:
                problem_bullets.append({
                    "text": text,
                    "why": why,
                    "refs": [build_ref(fact)],
                })
        
        sections.append({
            "title": "Problemas" if language == "pt-BR" else "Problems",
            "minutes": problem_minutes,
            "items": [{"heading": "", "bullets": problem_bullets}],
        })
    
    # 2. Action Plan
    if action_facts:
        action_minutes = int(duration * 0.6)
        action_bullets = []
        for fact in action_facts:
            text = text_quality.extract_actionable_text(fact, "problem_solving", language)
            why = fact.get("why_relevant", "")
            owner = fact.get("payload", {}).get("owner")
            due = fact.get("due_iso") or fact.get("due_at")
            
            if text:
                action_bullets.append({
                    "text": text,
                    "why": why,
                    "owner": owner,
                    "due": due,
                    "refs": [build_ref(fact)],
                })
        
        sections.append({
            "title": "Plano de Ação" if language == "pt-BR" else "Action Plan",
            "minutes": action_minutes,
            "items": [{"heading": "", "bullets": action_bullets}],
        })
    
    return sections


def build_planning_sections(
    facts: List[Dict[str, Any]],
    workstreams: List[Dict[str, Any]],
    duration: int,
    language: str,
) -> List[Dict[str, Any]]:
    """Build sections for planning meetings.
    
    Structure: Objectives → Timeline → Dependencies → Milestones
    """
    sections = []
    
    # Filter facts
    milestone_facts = [f for f in facts if (f.get("fact_type") or "").lower() in ["milestone", "objective"]][:5]
    action_facts = [f for f in facts if (f.get("fact_type") or "").lower() in ["action_item", "process_step"]][:8]
    
    # 1. Objectives
    if milestone_facts:
        obj_minutes = int(duration * 0.3)
        obj_bullets = []
        for fact in milestone_facts:
            text = text_quality.extract_actionable_text(fact, "planning", language)
            why = fact.get("why_relevant", "")
            due = fact.get("due_iso") or fact.get("due_at")
            
            if text:
                obj_bullets.append({
                    "text": text,
                    "why": why,
                    "due": due,
                    "refs": [build_ref(fact)],
                })
        
        sections.append({
            "title": "Objetivos" if language == "pt-BR" else "Objectives",
            "minutes": obj_minutes,
            "items": [{"heading": "", "bullets": obj_bullets}],
        })
    
    # 2. Timeline/Actions
    if action_facts:
        timeline_minutes = int(duration * 0.7)
        timeline_bullets = []
        for fact in action_facts:
            text = text_quality.extract_actionable_text(fact, "planning", language)
            why = fact.get("why_relevant", "")
            owner = fact.get("payload", {}).get("owner")
            due = fact.get("due_iso") or fact.get("due_at")
            
            if text:
                timeline_bullets.append({
                    "text": text,
                    "why": why,
                    "owner": owner,
                    "due": due,
                    "refs": [build_ref(fact)],
                })
        
        sections.append({
            "title": "Cronograma" if language == "pt-BR" else "Timeline",
            "minutes": timeline_minutes,
            "items": [{"heading": "", "bullets": timeline_bullets}],
        })
    
    return sections


def build_alignment_sections(
    facts: List[Dict[str, Any]],
    workstreams: List[Dict[str, Any]],
    duration: int,
    language: str,
) -> List[Dict[str, Any]]:
    """Build sections for alignment meetings.
    
    Structure: Current State → Gaps → Agreements → Open Questions
    """
    sections = []
    
    # Filter facts
    status_facts = [f for f in facts if (f.get("fact_type") or "").lower() in ["metric", "context"]][:4]
    question_facts = [f for f in facts if (f.get("fact_type") or "").lower() in ["open_question", "question"]][:6]
    decision_facts = [f for f in facts if (f.get("fact_type") or "").lower() in ["decision", "decision_needed"]][:4]
    
    # 1. Current State
    if status_facts:
        state_minutes = int(duration * 0.3)
        state_bullets = []
        for fact in status_facts:
            text = text_quality.extract_actionable_text(fact, "alignment", language)
            why = fact.get("why_relevant", "")
            
            if text:
                state_bullets.append({
                    "text": text,
                    "why": why,
                    "refs": [build_ref(fact)],
                })
        
        sections.append({
            "title": "Estado Atual" if language == "pt-BR" else "Current State",
            "minutes": state_minutes,
            "items": [{"heading": "", "bullets": state_bullets}],
        })
    
    # 2. Open Questions
    if question_facts:
        question_minutes = int(duration * 0.4)
        question_bullets = []
        for fact in question_facts:
            text = text_quality.extract_actionable_text(fact, "alignment", language)
            why = fact.get("why_relevant", "")
            
            if text:
                question_bullets.append({
                    "text": text,
                    "why": why,
                    "refs": [build_ref(fact)],
                })
        
        sections.append({
            "title": "Questões Abertas" if language == "pt-BR" else "Open Questions",
            "minutes": question_minutes,
            "items": [{"heading": "", "bullets": question_bullets}],
        })
    
    # 3. Agreements
    if decision_facts:
        agreement_minutes = int(duration * 0.3)
        agreement_bullets = []
        for fact in decision_facts:
            text = text_quality.extract_actionable_text(fact, "alignment", language)
            why = fact.get("why_relevant", "")
            
            if text:
                agreement_bullets.append({
                    "text": text,
                    "why": why,
                    "refs": [build_ref(fact)],
                })
        
        sections.append({
            "title": "Alinhamentos" if language == "pt-BR" else "Agreements",
            "minutes": agreement_minutes,
            "items": [{"heading": "", "bullets": agreement_bullets}],
        })
    
    return sections


def build_status_sections(
    facts: List[Dict[str, Any]],
    workstreams: List[Dict[str, Any]],
    duration: int,
    language: str,
) -> List[Dict[str, Any]]:
    """Build sections for status update meetings.
    
    Structure: Progress → Blockers → Upcoming → Risks
    """
    sections = []
    
    # Filter facts
    milestone_facts = [f for f in facts if (f.get("fact_type") or "").lower() in ["milestone", "metric"]][:4]
    blocker_facts = [f for f in facts if (f.get("fact_type") or "").lower() in ["blocker", "risk"]][:4]
    action_facts = [f for f in facts if (f.get("fact_type") or "").lower() in ["action_item"]][:6]
    
    # 1. Progress
    if milestone_facts:
        progress_minutes = int(duration * 0.4)
        progress_bullets = []
        for fact in milestone_facts:
            text = text_quality.extract_actionable_text(fact, "status_update", language)
            why = fact.get("why_relevant", "")
            
            if text:
                progress_bullets.append({
                    "text": text,
                    "why": why,
                    "refs": [build_ref(fact)],
                })
        
        sections.append({
            "title": "Progresso" if language == "pt-BR" else "Progress",
            "minutes": progress_minutes,
            "items": [{"heading": "", "bullets": progress_bullets}],
        })
    
    # 2. Blockers
    if blocker_facts:
        blocker_minutes = int(duration * 0.3)
        blocker_bullets = []
        for fact in blocker_facts:
            text = text_quality.extract_actionable_text(fact, "status_update", language)
            why = fact.get("why_relevant", "")
            
            if text:
                blocker_bullets.append({
                    "text": text,
                    "why": why,
                    "refs": [build_ref(fact)],
                })
        
        sections.append({
            "title": "Bloqueios" if language == "pt-BR" else "Blockers",
            "minutes": blocker_minutes,
            "items": [{"heading": "", "bullets": blocker_bullets}],
        })
    
    # 3. Upcoming
    if action_facts:
        upcoming_minutes = int(duration * 0.3)
        upcoming_bullets = []
        for fact in action_facts:
            text = text_quality.extract_actionable_text(fact, "status_update", language)
            why = fact.get("why_relevant", "")
            due = fact.get("due_iso") or fact.get("due_at")
            
            if text:
                upcoming_bullets.append({
                    "text": text,
                    "why": why,
                    "due": due,
                    "refs": [build_ref(fact)],
                })
        
        sections.append({
            "title": "Próximas Ações" if language == "pt-BR" else "Upcoming",
            "minutes": upcoming_minutes,
            "items": [{"heading": "", "bullets": upcoming_bullets}],
        })
    
    return sections


def build_kickoff_sections(
    facts: List[Dict[str, Any]],
    workstreams: List[Dict[str, Any]],
    duration: int,
    language: str,
) -> List[Dict[str, Any]]:
    """Build sections for kickoff meetings.
    
    Structure: Objectives → Scope → Next Steps
    """
    sections = []
    
    # Filter facts (likely very few for kickoff)
    objective_facts = [f for f in facts if (f.get("fact_type") or "").lower() in ["objective", "milestone"]][:3]
    context_facts = [f for f in facts if (f.get("fact_type") or "").lower() in ["context", "requirement"]][:5]
    action_facts = [f for f in facts if (f.get("fact_type") or "").lower() in ["action_item"]][:4]
    
    # 1. Objectives
    if objective_facts:
        obj_minutes = int(duration * 0.3)
        obj_bullets = []
        for fact in objective_facts:
            text = text_quality.extract_actionable_text(fact, "kickoff", language)
            why = fact.get("why_relevant", "")
            
            if text:
                obj_bullets.append({
                    "text": text,
                    "why": why,
                    "refs": [build_ref(fact)],
                })
        
        sections.append({
            "title": "Objetivos" if language == "pt-BR" else "Objectives",
            "minutes": obj_minutes,
            "items": [{"heading": "", "bullets": obj_bullets}],
        })
    
    # 2. Scope
    if context_facts:
        scope_minutes = int(duration * 0.4)
        scope_bullets = []
        for fact in context_facts:
            text = text_quality.extract_actionable_text(fact, "kickoff", language)
            why = fact.get("why_relevant", "")
            
            if text:
                scope_bullets.append({
                    "text": text,
                    "why": why,
                    "refs": [build_ref(fact)],
                })
        
        sections.append({
            "title": "Escopo" if language == "pt-BR" else "Scope",
            "minutes": scope_minutes,
            "items": [{"heading": "", "bullets": scope_bullets}],
        })
    
    # 3. Initial Actions
    if action_facts:
        action_minutes = int(duration * 0.3)
        action_bullets = []
        for fact in action_facts:
            text = text_quality.extract_actionable_text(fact, "kickoff", language)
            why = fact.get("why_relevant", "")
            owner = fact.get("payload", {}).get("owner")
            
            if text:
                action_bullets.append({
                    "text": text,
                    "why": why,
                    "owner": owner,
                    "refs": [build_ref(fact)],
                })
        
        sections.append({
            "title": "Primeiros Passos" if language == "pt-BR" else "Initial Steps",
            "minutes": action_minutes,
            "items": [{"heading": "", "bullets": action_bullets}],
        })
    
    return sections


def build_next_steps_section(
    facts: List[Dict[str, Any]],
    duration: int,
    language: str,
) -> Dict[str, Any]:
    """Build next steps section (closing)."""
    next_steps_minutes = max(3, int(duration * 0.1))
    
    # Get actionable items (action_item, decision_needed with owners/due dates)
    actionable = [
        f for f in facts
        if (f.get("fact_type") or "").lower() in ["action_item", "decision_needed", "blocker"]
        and (f.get("payload", {}).get("owner") or f.get("due_iso") or f.get("due_at"))
    ][:5]
    
    bullets = []
    for fact in actionable:
        text = text_quality.extract_actionable_text(fact, "planning", language)
        owner = fact.get("payload", {}).get("owner")
        due = fact.get("due_iso") or fact.get("due_at")
        
        if text:
            bullets.append({
                "text": text,
                "owner": owner,
                "due": due,
                "refs": [build_ref(fact)],
            })
    
    return {
        "title": "Próximos Passos" if language == "pt-BR" else "Next Steps",
        "minutes": next_steps_minutes,
        "items": [{"heading": "", "bullets": bullets}] if bullets else [],
    }


def build_parking_lot(
    facts: List[Dict[str, Any]],
    duration: int,
    language: str,
) -> Optional[Dict[str, Any]]:
    """Build parking lot for low-priority items."""
    # Get low-urgency facts that didn't make it to main sections
    # Only include facts with urgency < 0.3 AND that aren't core types
    parking_facts = []
    for f in facts:
        urgency = f.get("urgency_score", 0)
        ftype = (f.get("fact_type") or "").lower()
        
        # Skip high-priority types even if low urgency score
        if ftype in ["blocker", "decision_needed", "risk", "action_item"]:
            continue
        
        if urgency < 0.3:
            parking_facts.append(f)
        
        if len(parking_facts) >= 4:
            break
    
    if not parking_facts or len(parking_facts) < 2:
        return None
    
    bullets = []
    for fact in parking_facts:
        text = text_quality.extract_actionable_text(fact, "alignment", language)
        why = fact.get("why_relevant", "")
        
        if text:
            bullets.append({
                "text": text,
                "why": why,
                "refs": [build_ref(fact)],
            })
    
    if not bullets:
        return None
    
    return {
        "title": "Itens para Depois" if language == "pt-BR" else "Parking Lot",
        "minutes": 5,
        "items": [{"heading": "", "bullets": bullets}],
    }


def build_metadata_v2(
    workstreams: List[Dict[str, Any]],
    facts: List[Dict[str, Any]],
    intent: str,
    language: str,
) -> Dict[str, Any]:
    """Build metadata v2.0 with workstreams and enriched refs."""
    metadata = {
        "agenda_v": "2.0",
        "intent": intent,
        "workstreams": [
            {
                "workstream_id": ws.get("workstream_id"),
                "title": ws.get("title", ""),
                "status": ws.get("status", "green"),
                "priority": ws.get("priority", 1),
            }
            for ws in workstreams
        ],
        "refs": [build_ref(f) for f in facts],
    }
    
    return metadata


def build_ref(fact: Dict[str, Any]) -> Dict[str, Any]:
    """Build reference from fact."""
    evidence = fact.get("evidence") or []
    quote = ""
    if evidence:
        for ev in evidence:
            q = ev.get("quote", "")
            if isinstance(q, str) and len(q.strip()) > 20:
                quote = q.strip()[:150]
                break
    
    return {
        "fact_id": fact.get("fact_id"),
        "type": fact.get("fact_type"),
        "status": fact.get("status"),
        "quote": quote,
        "urgency_score": fact.get("urgency_score"),
        "why_relevant": fact.get("why_relevant"),
        "workstream_id": fact.get("workstream_id"),
    }


def build_agenda_title(
    subject: str,
    intent: str,
    workstreams: List[Dict[str, Any]],
    language: str,
) -> str:
    """Build agenda title based on subject, intent, and workstreams."""
    # If single workstream, use its title
    if len(workstreams) == 1:
        ws_title = workstreams[0].get("title", "")
        if ws_title:
            prefix = "Reunião: " if language == "pt-BR" else "Meeting: "
            return f"{prefix}{ws_title}"
    
    # Otherwise use subject
    if subject:
        return subject
    
    # Fallback to intent-based title
    if language == "pt-BR":
        intent_titles = {
            "decision_making": "Reunião de Decisões",
            "problem_solving": "Resolução de Problemas",
            "planning": "Planejamento",
            "alignment": "Alinhamento",
            "status_update": "Atualização de Status",
            "kickoff": "Kickoff",
        }
    else:
        intent_titles = {
            "decision_making": "Decision Meeting",
            "problem_solving": "Problem Solving",
            "planning": "Planning Session",
            "alignment": "Alignment Meeting",
            "status_update": "Status Update",
            "kickoff": "Kickoff Meeting",
        }
    
    return intent_titles.get(intent, "Reunião" if language == "pt-BR" else "Meeting")
