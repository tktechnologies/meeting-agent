"""
Progress tracking for LangGraph workflow.
Allows emitting real-time progress updates via SSE.
"""
import time
from typing import Dict, Any, Optional, Callable
from threading import Lock

# Global progress tracker
_progress_lock = Lock()
_progress_sessions: Dict[str, Dict[str, Any]] = {}

# Portuguese translations for each node
NODE_MESSAGES_PT = {
    "parse_and_understand": "Entendendo pedido do usuário...",
    "analyze_context": "Analisando reuniões anteriores...",
    "detect_intent": "Detectando intenção da reunião...",
    "retrieve_facts": "Buscando informações relevantes...",
    "synthesize_workstream_status": "Analisando status dos projetos...",
    "generate_macro_summary": "Gerando resumo executivo...",
    "build_agenda": "Construindo pauta personalizada...",
    "review_quality": "Revisando qualidade da pauta...",
    "finalize_agenda": "Finalizando e salvando pauta...",
}

NODE_MESSAGES_EN = {
    "parse_and_understand": "Understanding your request...",
    "analyze_context": "Analyzing previous meetings...",
    "detect_intent": "Detecting meeting intent...",
    "retrieve_facts": "Searching relevant information...",
    "synthesize_workstream_status": "Analyzing project status...",
    "generate_macro_summary": "Generating executive summary...",
    "build_agenda": "Building personalized agenda...",
    "review_quality": "Reviewing agenda quality...",
    "finalize_agenda": "Finalizing and saving agenda...",
}


def create_session(session_id: str, language: str = "pt-BR"):
    """Create a new progress tracking session."""
    with _progress_lock:
        _progress_sessions[session_id] = {
            "session_id": session_id,
            "language": language,
            "started_at": time.time(),
            "current_step": None,
            "current_message": None,
            "completed_steps": [],
            "total_steps": 9,
            "errors": [],
            "completed": False,
            "final_result": None,  # Will store the final agenda when workflow completes
        }


def update_progress(session_id: str, step: str, status: str = "running", error: str = None):
    """
    Update progress for a session.
    
    Args:
        session_id: Unique session identifier
        step: Current node name (e.g., "parse_and_understand")
        status: "running", "completed", or "error"
        error: Error message if status is "error"
    """
    with _progress_lock:
        if session_id not in _progress_sessions:
            return
        
        session = _progress_sessions[session_id]
        language = session.get("language", "pt-BR")
        messages = NODE_MESSAGES_PT if language == "pt-BR" else NODE_MESSAGES_EN
        
        if status == "running":
            session["current_step"] = step
            session["current_message"] = messages.get(step, f"Processing {step}...")
        
        elif status == "completed":
            if step not in session["completed_steps"]:
                session["completed_steps"].append(step)
            
            # Check if all steps are done
            if len(session["completed_steps"]) >= session["total_steps"]:
                session["completed"] = True
                session["current_step"] = None
                session["current_message"] = "Concluído!" if language == "pt-BR" else "Completed!"
        
        elif status == "error":
            session["errors"].append({"step": step, "error": error})


def get_progress(session_id: str) -> Optional[Dict[str, Any]]:
    """Get current progress for a session."""
    with _progress_lock:
        session = _progress_sessions.get(session_id)
        return session.copy() if session else None


def cleanup_session(session_id: str):
    """Remove a session from tracking (call after completion)."""
    with _progress_lock:
        _progress_sessions.pop(session_id, None)


def get_all_sessions() -> Dict[str, Dict[str, Any]]:
    """Get all active sessions (for debugging)."""
    with _progress_lock:
        return _progress_sessions.copy()


def set_final_result(session_id: str, result: Dict[str, Any]):
    """Store the final workflow result in the session."""
    with _progress_lock:
        if session_id in _progress_sessions:
            _progress_sessions[session_id]["final_result"] = result
            _progress_sessions[session_id]["completed"] = True
