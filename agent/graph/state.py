"""
State schema for LangGraph agenda planning workflow.

The AgendaState TypedDict tracks all data as it flows through the graph nodes.
"""

from typing import TypedDict, List, Dict, Any, Optional, Literal


class AgendaState(TypedDict, total=False):
    """State for the agenda planning workflow."""
    
    # ========== INPUT (from user query) ==========
    raw_query: str  # Original natural language request
    org_id: str  # Organization identifier
    session_id: Optional[str]  # Progress tracking session ID (for SSE)
    
    # ========== Step 1: Parse & Understand ==========
    subject: Optional[str]  # Extracted meeting subject/topic
    language: Literal["pt-BR", "en-US"]  # Detected language
    duration_minutes: int  # Meeting duration (default 30)
    constraints: Dict[str, Any]  # User constraints (e.g., {"max_topics": 3})
    
    # ========== Step 2: Context Analysis ==========
    recent_meetings: List[Dict[str, Any]]  # Last N meetings for org
    meeting_context: str  # LLM-generated summary of recent patterns
    open_items: List[Dict[str, Any]]  # Unfinished items from previous meetings
    themes: List[str]  # Recurring topics across meetings
    meeting_frequency: Optional[str]  # e.g., "weekly", "monthly"
    
    # ========== Step 3: Intent Detection ==========
    intent: Literal[
        "decision_making",  # Need to approve/choose/finalize
        "problem_solving",  # Blockers, risks, issues to resolve
        "planning",  # Roadmap, milestones, resource allocation
        "alignment",  # Sync understanding, review progress
        "status_update",  # Report progress, metrics
        "kickoff"  # First meeting, introductions, scope
    ]
    intent_confidence: float  # 0.0-1.0
    intent_reasoning: str  # Why this intent was chosen
    workstreams: List[Dict[str, Any]]  # Detected/matched workstreams
    focus_areas: List[str]  # Specific topics (e.g., ["API integration", "Q1 planning"])
    
    # ========== Step 4: Smart Fact Retrieval ==========
    candidate_facts: List[Dict[str, Any]]  # All retrieved facts (multi-strategy)
    ranked_facts: List[Dict[str, Any]]  # Top 30-40 after LLM ranking
    retrieval_strategy: str  # "workstream" | "semantic" | "urgent" | "hybrid"
    retrieval_stats: Dict[str, int]  # {"workstream": 20, "semantic": 15, "urgent": 5}
    workstream_status: Optional[str]  # LLM synthesis of workstream current state
    web_search_context: Optional[str]  # External context from web search
    
    # ========== Step 5: Macro Summary ==========
    macro_summary: str  # LLM-generated high-level context (3-4 sentences)
    
    # ========== Step 6: Agenda Builder ==========
    draft_agenda: Dict[str, Any]  # First-pass agenda structure
    
    # ========== Step 7: Quality Review ==========
    quality_score: float  # 0.0-1.0 (threshold: 0.7)
    quality_issues: List[str]  # ["Section 2 too long", "Missing context"]
    quality_suggestions: List[str]  # Actionable improvements
    refinement_count: int  # Track refinement loops (max 2)
    
    # ========== Step 8: Final Output ==========
    final_agenda: Dict[str, Any]  # Final validated agenda
    agenda_id: str  # Database identifier
    
    # ========== Metadata & Observability ==========
    step_times: Dict[str, float]  # Performance tracking per node
    errors: List[str]  # Any errors encountered
    node_outputs: Dict[str, Any]  # Debug: capture intermediate outputs
