"""
LangGraph workflow definition for agenda planning.

This module builds the StateGraph that orchestrates all nodes
into a coherent iterative workflow.
"""

from langgraph.graph import StateGraph, END

from .state import AgendaState
from .nodes import (
    parse_and_understand,
    analyze_context,
    detect_intent,
    retrieve_facts,
    synthesize_workstream_status,
    generate_macro_summary,
    build_agenda,
    review_quality,
    should_refine,
    finalize_agenda,
)


def create_agenda_graph() -> StateGraph:
    """
    Create the LangGraph workflow for agenda planning.
    
    Flow:
    1. Parse user query → structured data
    2. Analyze recent meeting context
    3. Detect intent (LLM)
    4. Retrieve facts (multi-strategy + LLM ranking + web search)
    4.5. Synthesize workstream status from facts
    5. Generate macro summary (LLM)
    6. Build agenda (LLM with templates)
    7. Review quality (LLM)
    8. [CONDITIONAL] Refine (loop to step 4) OR Finalize
    9. Persist to DB
    
    Returns:
        Compiled StateGraph ready to invoke
    """
    workflow = StateGraph(AgendaState)
    
    # ===== Add nodes =====
    workflow.add_node("parse", parse_and_understand)
    workflow.add_node("context", analyze_context)
    workflow.add_node("intent", detect_intent)
    workflow.add_node("retrieve", retrieve_facts)
    workflow.add_node("ws_status", synthesize_workstream_status)
    workflow.add_node("macro", generate_macro_summary)
    workflow.add_node("build", build_agenda)
    workflow.add_node("review", review_quality)
    workflow.add_node("finalize", finalize_agenda)
    
    # ===== Add edges (linear flow) =====
    workflow.set_entry_point("parse")
    workflow.add_edge("parse", "context")
    workflow.add_edge("context", "intent")
    workflow.add_edge("intent", "retrieve")
    workflow.add_edge("retrieve", "ws_status")
    workflow.add_edge("ws_status", "macro")
    workflow.add_edge("macro", "build")
    workflow.add_edge("build", "review")
    
    # ===== Conditional edge: refine or finalize =====
    workflow.add_conditional_edges(
        "review",
        should_refine,
        {
            "refine": "retrieve",  # Loop back for more facts/rebuild
            "finalize": "finalize",
        }
    )
    
    # ===== End after finalization =====
    workflow.add_edge("finalize", END)
    
    return workflow.compile()


# ===== Global graph instance =====
# This is the main entry point for the LangGraph workflow
agenda_graph = create_agenda_graph()
