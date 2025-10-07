"""
Section templates for different meeting intents.

Templates guide the LLM to build appropriate agenda structures
based on the detected meeting intent.
"""

from typing import Dict, Any, List


def get_section_template(intent: str, language: str = "pt-BR") -> Dict[str, Any]:
    """
    Get section template for a specific meeting intent.
    
    Args:
        intent: One of decision_making, problem_solving, planning, alignment, status_update, kickoff
        language: "pt-BR" or "en-US"
    
    Returns:
        Template dict with suggested sections and time allocations
    """
    templates = {
        "decision_making": _decision_making_template(language),
        "problem_solving": _problem_solving_template(language),
        "planning": _planning_template(language),
        "alignment": _alignment_template(language),
        "status_update": _status_update_template(language),
        "kickoff": _kickoff_template(language),
    }
    
    return templates.get(intent, _alignment_template(language))


def _decision_making_template(lang: str) -> Dict[str, Any]:
    """Template for decision-making meetings."""
    if lang == "pt-BR":
        return {
            "suggested_sections": [
                {"type": "opening", "title": "Abertura", "time_pct": 0.10},
                {"type": "context", "title": "Contexto", "time_pct": 0.15},
                {"type": "decisions", "title": "Decisões Necessárias", "time_pct": 0.40},
                {"type": "impacts", "title": "Impactos e Próximos Passos", "time_pct": 0.25},
                {"type": "next_steps", "title": "Próximos Passos", "time_pct": 0.10},
            ],
            "focus": "decisions",
            "bullet_style": "decision-oriented"
        }
    else:
        return {
            "suggested_sections": [
                {"type": "opening", "title": "Opening", "time_pct": 0.10},
                {"type": "context", "title": "Context", "time_pct": 0.15},
                {"type": "decisions", "title": "Decisions Needed", "time_pct": 0.40},
                {"type": "impacts", "title": "Impacts & Next Steps", "time_pct": 0.25},
                {"type": "next_steps", "title": "Action Items", "time_pct": 0.10},
            ],
            "focus": "decisions",
            "bullet_style": "decision-oriented"
        }


def _problem_solving_template(lang: str) -> Dict[str, Any]:
    """Template for problem-solving meetings."""
    if lang == "pt-BR":
        return {
            "suggested_sections": [
                {"type": "opening", "title": "Abertura", "time_pct": 0.08},
                {"type": "problems", "title": "Problemas e Bloqueios", "time_pct": 0.35},
                {"type": "solutions", "title": "Soluções Propostas", "time_pct": 0.30},
                {"type": "actions", "title": "Ações e Responsáveis", "time_pct": 0.20},
                {"type": "next_steps", "title": "Próximos Passos", "time_pct": 0.07},
            ],
            "focus": "problems",
            "bullet_style": "problem-solution-action"
        }
    else:
        return {
            "suggested_sections": [
                {"type": "opening", "title": "Opening", "time_pct": 0.08},
                {"type": "problems", "title": "Problems & Blockers", "time_pct": 0.35},
                {"type": "solutions", "title": "Proposed Solutions", "time_pct": 0.30},
                {"type": "actions", "title": "Actions & Owners", "time_pct": 0.20},
                {"type": "next_steps", "title": "Next Steps", "time_pct": 0.07},
            ],
            "focus": "problems",
            "bullet_style": "problem-solution-action"
        }


def _planning_template(lang: str) -> Dict[str, Any]:
    """Template for planning meetings."""
    if lang == "pt-BR":
        return {
            "suggested_sections": [
                {"type": "opening", "title": "Abertura", "time_pct": 0.10},
                {"type": "objectives", "title": "Objetivos e Marcos", "time_pct": 0.25},
                {"type": "roadmap", "title": "Roadmap e Cronograma", "time_pct": 0.30},
                {"type": "resources", "title": "Recursos e Dependências", "time_pct": 0.20},
                {"type": "next_steps", "title": "Próximos Passos", "time_pct": 0.15},
            ],
            "focus": "planning",
            "bullet_style": "milestone-oriented"
        }
    else:
        return {
            "suggested_sections": [
                {"type": "opening", "title": "Opening", "time_pct": 0.10},
                {"type": "objectives", "title": "Objectives & Milestones", "time_pct": 0.25},
                {"type": "roadmap", "title": "Roadmap & Timeline", "time_pct": 0.30},
                {"type": "resources", "title": "Resources & Dependencies", "time_pct": 0.20},
                {"type": "next_steps", "title": "Next Steps", "time_pct": 0.15},
            ],
            "focus": "planning",
            "bullet_style": "milestone-oriented"
        }


def _alignment_template(lang: str) -> Dict[str, Any]:
    """Template for alignment/sync meetings."""
    if lang == "pt-BR":
        return {
            "suggested_sections": [
                {"type": "opening", "title": "Abertura", "time_pct": 0.10},
                {"type": "status", "title": "Status Atual", "time_pct": 0.25},
                {"type": "questions", "title": "Dúvidas e Alinhamentos", "time_pct": 0.35},
                {"type": "decisions", "title": "Decisões Menores", "time_pct": 0.20},
                {"type": "next_steps", "title": "Próximos Passos", "time_pct": 0.10},
            ],
            "focus": "alignment",
            "bullet_style": "status-question-decision"
        }
    else:
        return {
            "suggested_sections": [
                {"type": "opening", "title": "Opening", "time_pct": 0.10},
                {"type": "status", "title": "Current Status", "time_pct": 0.25},
                {"type": "questions", "title": "Questions & Alignment", "time_pct": 0.35},
                {"type": "decisions", "title": "Minor Decisions", "time_pct": 0.20},
                {"type": "next_steps", "title": "Next Steps", "time_pct": 0.10},
            ],
            "focus": "alignment",
            "bullet_style": "status-question-decision"
        }


def _status_update_template(lang: str) -> Dict[str, Any]:
    """Template for status update meetings."""
    if lang == "pt-BR":
        return {
            "suggested_sections": [
                {"type": "opening", "title": "Abertura", "time_pct": 0.08},
                {"type": "milestones", "title": "Marcos Atingidos", "time_pct": 0.20},
                {"type": "metrics", "title": "Métricas e Progresso", "time_pct": 0.25},
                {"type": "blockers", "title": "Bloqueios e Riscos", "time_pct": 0.25},
                {"type": "next_period", "title": "Próximo Período", "time_pct": 0.15},
                {"type": "next_steps", "title": "Ações", "time_pct": 0.07},
            ],
            "focus": "status",
            "bullet_style": "metric-oriented"
        }
    else:
        return {
            "suggested_sections": [
                {"type": "opening", "title": "Opening", "time_pct": 0.08},
                {"type": "milestones", "title": "Milestones Reached", "time_pct": 0.20},
                {"type": "metrics", "title": "Metrics & Progress", "time_pct": 0.25},
                {"type": "blockers", "title": "Blockers & Risks", "time_pct": 0.25},
                {"type": "next_period", "title": "Next Period", "time_pct": 0.15},
                {"type": "next_steps", "title": "Actions", "time_pct": 0.07},
            ],
            "focus": "status",
            "bullet_style": "metric-oriented"
        }


def _kickoff_template(lang: str) -> Dict[str, Any]:
    """Template for kickoff meetings."""
    if lang == "pt-BR":
        return {
            "suggested_sections": [
                {"type": "opening", "title": "Apresentações", "time_pct": 0.15},
                {"type": "objectives", "title": "Objetivos do Projeto", "time_pct": 0.20},
                {"type": "scope", "title": "Escopo e Entregas", "time_pct": 0.25},
                {"type": "roles", "title": "Papéis e Responsabilidades", "time_pct": 0.15},
                {"type": "timeline", "title": "Cronograma Inicial", "time_pct": 0.15},
                {"type": "next_steps", "title": "Primeiros Passos", "time_pct": 0.10},
            ],
            "focus": "kickoff",
            "bullet_style": "introduction-oriented"
        }
    else:
        return {
            "suggested_sections": [
                {"type": "opening", "title": "Introductions", "time_pct": 0.15},
                {"type": "objectives", "title": "Project Objectives", "time_pct": 0.20},
                {"type": "scope", "title": "Scope & Deliverables", "time_pct": 0.25},
                {"type": "roles", "title": "Roles & Responsibilities", "time_pct": 0.15},
                {"type": "timeline", "title": "Initial Timeline", "time_pct": 0.15},
                {"type": "next_steps", "title": "First Steps", "time_pct": 0.10},
            ],
            "focus": "kickoff",
            "bullet_style": "introduction-oriented"
        }
