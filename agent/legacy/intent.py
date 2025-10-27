"""Meeting intent detection and subject enrichment.

This module detects what kind of meeting is being planned and enriches
generic subjects with specific, actionable context.
"""

from typing import Dict, List, Optional, Any
import re
from difflib import SequenceMatcher


class MeetingIntent:
    """Detect and classify meeting intent from context."""
    
    # Intent patterns by language
    INTENT_PATTERNS = {
        "pt-BR": {
            "decision_making": [
                r"\b(decidir|aprovar|escolher|definir|selecionar|optar)\b",
                r"\bdecis[aã]o\b",
                r"\baprovação\b",
            ],
            "problem_solving": [
                r"\b(resolver|mitigar|desbloquear|corrigir|solucionar)\b",
                r"\b(problema|bloqueio|bloqueador|impedimento)\b",
                r"\brisco\b",
            ],
            "planning": [
                r"\b(planejar|roadmap|cronograma|timeline|agendar)\b",
                r"\bpr[óo]ximos?\s+passos?\b",
                r"\b(sprint|trimestre|quarter|semestre)\b",
            ],
            "alignment": [
                r"\b(alinhar|sincronizar|revisar|compartilhar)\b",
                r"\balinhamento\b",
                r"\breuni[aã]o\s+de\s+(status|alinhamento)\b",
            ],
            "status_update": [
                r"\b(status|atualiza[çc][aã]o|andamento|progresso)\b",
                r"\breport\b",
                r"\b(weekly|semanal|mensal)\b",
            ],
            "kickoff": [
                r"\b(in[íi]cio|kickoff|lan[çc]amento|come[çc]ar)\b",
                r"\bprimeiro\s+contato\b",
                r"\bintrodução\b",
            ],
        },
        "en-US": {
            "decision_making": [
                r"\b(decide|approve|choose|select|pick)\b",
                r"\bdecision\b",
                r"\bapproval\b",
            ],
            "problem_solving": [
                r"\b(solve|resolve|mitigate|fix|unblock)\b",
                r"\b(problem|blocker|impediment|issue)\b",
                r"\brisk\b",
            ],
            "planning": [
                r"\b(plan|roadmap|schedule|timeline)\b",
                r"\bnext\s+steps?\b",
                r"\b(sprint|quarter|semester)\b",
            ],
            "alignment": [
                r"\b(align|sync|review|share)\b",
                r"\balignment\b",
                r"\b(status|sync)\s+meeting\b",
            ],
            "status_update": [
                r"\b(status|update|progress|report)\b",
                r"\b(weekly|monthly)\b",
            ],
            "kickoff": [
                r"\b(kickoff|start|launch|begin|introduction)\b",
                r"\bfirst\s+contact\b",
            ],
        },
    }
    
    @classmethod
    def detect_intent(
        cls,
        subject: Optional[str],
        workstreams: List[Dict[str, Any]],
        facts: List[Dict[str, Any]],
        language: str = "pt-BR",
    ) -> str:
        """Detect primary meeting intent from context.
        
        Args:
            subject: User-provided subject or None
            workstreams: List of workstreams for this meeting
            facts: List of relevant facts
            language: Language code
            
        Returns:
            Intent type: decision_making, problem_solving, planning, 
                        alignment, status_update, or kickoff
        """
        scores: Dict[str, float] = {
            "decision_making": 0.0,
            "problem_solving": 0.0,
            "planning": 0.0,
            "alignment": 0.0,
            "status_update": 0.0,
            "kickoff": 0.0,
        }
        
        patterns = cls.INTENT_PATTERNS.get(language, cls.INTENT_PATTERNS["en-US"])
        
        # 1. Score from subject
        if subject:
            subject_lower = subject.lower()
            for intent_type, regexes in patterns.items():
                for regex in regexes:
                    if re.search(regex, subject_lower, re.IGNORECASE):
                        scores[intent_type] += 3.0
        
        # 2. Score from workstream status
        for ws in workstreams:
            status = ws.get("status", "green")
            if status in ["yellow", "red"]:
                scores["problem_solving"] += 2.0
            priority = ws.get("priority", 1)
            if priority >= 3:
                scores["decision_making"] += 1.0
        
        # 3. Score from fact types
        fact_type_weights = {
            "decision_needed": {"decision_making": 3.0},
            "decision": {"decision_making": 2.0},
            "blocker": {"problem_solving": 3.0},
            "risk": {"problem_solving": 2.0},
            "open_question": {"alignment": 2.0},
            "question": {"alignment": 1.5},
            "action_item": {"planning": 1.5},
            "milestone": {"planning": 2.0},
            "process_step": {"planning": 1.0},
            "meeting_metadata": {"kickoff": 1.0},
        }
        
        for fact in facts:
            ftype = (fact.get("fact_type") or "").lower()
            weights = fact_type_weights.get(ftype, {})
            for intent_type, weight in weights.items():
                scores[intent_type] += weight
        
        # 4. Special case: no facts or very few → kickoff
        if len(facts) < 3:
            scores["kickoff"] += 5.0
        
        # 5. Check for overdue items → planning
        overdue_count = sum(1 for f in facts if cls._is_overdue(f))
        if overdue_count > 0:
            scores["planning"] += overdue_count * 1.5
        
        # Find highest score
        if not any(scores.values()):
            # Default to alignment if no signals
            return "alignment"
        
        return max(scores.items(), key=lambda x: x[1])[0]
    
    @classmethod
    def enrich_subject(
        cls,
        subject: Optional[str],
        intent: str,
        workstreams: List[Dict[str, Any]],
        language: str = "pt-BR",
    ) -> str:
        """Build a rich, specific subject if missing or generic.
        
        Args:
            subject: User-provided subject or None
            intent: Detected intent type
            workstreams: List of workstreams
            language: Language code
            
        Returns:
            Enriched subject string
        """
        # If subject is good enough, keep it
        if subject and cls._is_quality_subject(subject, language):
            return subject
        
        # Build from workstreams
        if not workstreams:
            return cls._default_subject_for_intent(intent, language)
        
        # Use workstream titles
        if len(workstreams) == 1:
            ws_title = workstreams[0].get("title", "")
            return cls._add_intent_prefix(ws_title, intent, language)
        
        # Multiple workstreams: combine top 2-3
        titles = [ws.get("title", "") for ws in workstreams[:3] if ws.get("title")]
        if titles:
            combined = ", ".join(titles)
            return cls._add_intent_prefix(combined, intent, language)
        
        # Fallback
        return cls._default_subject_for_intent(intent, language)
    
    @classmethod
    def _is_quality_subject(cls, subject: str, language: str) -> bool:
        """Check if subject is specific enough (not generic)."""
        if not subject or len(subject.strip()) < 10:
            return False
        
        # Check for generic patterns
        generic_pt = [
            r"^(fazer?|criar|montar)\s+(a\s+)?pauta",
            r"^pr[óo]xima\s+reuni[aã]o",
            r"^reuni[aã]o\s*$",
            r"^alinhamento\s*$",
            r"^status\s*$",
        ]
        generic_en = [
            r"^(make|create)\s+agenda",
            r"^next\s+meeting",
            r"^meeting\s*$",
            r"^alignment\s*$",
            r"^status\s*$",
        ]
        
        patterns = generic_pt if language == "pt-BR" else generic_en
        subject_lower = subject.lower().strip()
        
        return not any(re.search(p, subject_lower) for p in patterns)
    
    @classmethod
    def _add_intent_prefix(cls, title: str, intent: str, language: str) -> str:
        """Add intent-specific prefix to title."""
        if language == "pt-BR":
            prefixes = {
                "decision_making": "Decidir sobre",
                "problem_solving": "Resolver",
                "planning": "Planejar",
                "alignment": "Alinhar",
                "status_update": "Status de",
                "kickoff": "Kickoff",
            }
        else:
            prefixes = {
                "decision_making": "Decide on",
                "problem_solving": "Resolve",
                "planning": "Plan",
                "alignment": "Align on",
                "status_update": "Status of",
                "kickoff": "Kickoff",
            }
        
        prefix = prefixes.get(intent, "")
        if not prefix:
            return title
        
        # Don't duplicate if title already starts with similar word
        title_lower = title.lower()
        prefix_word = prefix.split()[0].lower()
        if title_lower.startswith(prefix_word):
            return title
        
        return f"{prefix} {title}"
    
    @classmethod
    def _default_subject_for_intent(cls, intent: str, language: str) -> str:
        """Get default subject for intent when no context available."""
        if language == "pt-BR":
            defaults = {
                "decision_making": "Reunião de decisões",
                "problem_solving": "Resolução de problemas",
                "planning": "Planejamento",
                "alignment": "Alinhamento",
                "status_update": "Atualização de status",
                "kickoff": "Reunião inicial",
            }
        else:
            defaults = {
                "decision_making": "Decision meeting",
                "problem_solving": "Problem solving",
                "planning": "Planning session",
                "alignment": "Alignment meeting",
                "status_update": "Status update",
                "kickoff": "Kickoff meeting",
            }
        
        return defaults.get(intent, "Reunião" if language == "pt-BR" else "Meeting")
    
    @staticmethod
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
