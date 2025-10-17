"""
LangGraph nodes for agenda planning workflow.

Each function is a node in the graph that transforms the AgendaState.
"""

# Load .env file FIRST before any LLM initialization
import os
try:
    from dotenv import load_dotenv
    from pathlib import Path
    # Look for .env in meeting-agent root (parent of agent/)
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ [nodes.py] Loaded environment from {env_path}")
    else:
        print(f"⚠️  [nodes.py] .env not found at {env_path}")
except ImportError:
    print("⚠️  [nodes.py] python-dotenv not installed")

import json
import time
import logging
from typing import Dict, Any, Literal
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

from .state import AgendaState
from .prompts import (
    get_parse_prompt,
    get_context_analysis_prompt,
    get_intent_detection_prompt,
    get_fact_ranking_prompt,
    get_macro_summary_prompt,
    get_agenda_builder_prompt,
    get_quality_review_prompt,
)
from ..retrievers.multi_strategy import MultiStrategyRetriever
from ..intent.templates import get_section_template
from .. import db_router as db
from .progress import update_progress

# Import web search tool
try:
    from ..tools.web_search import perform_web_search
    HAVE_WEB_SEARCH = True
except ImportError:
    HAVE_WEB_SEARCH = False
    logger.warning("Web search tool not available - install httpx")
from ..legacy.planner import persist_agenda_proposal


# Initialize LLM (using OpenAI - same as legacy planner)
def _get_llm(temperature: float = 0) -> ChatOpenAI:
    """Get LLM instance configured from environment variables."""
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")
    model = (
        os.environ.get("MEETING_AGENT_LLM_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or "gpt-5-nano"
    )
    
    # Debug logging for API key availability
    if not api_key:
        logger.error("❌ OPENAI_API_KEY not found in environment!")
        logger.error(f"Available env vars: {list(os.environ.keys())[:10]}...")
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    logger.debug(f"Using OpenAI model: {model}, base_url: {base_url or 'default'}")
    
    kwargs = {
        "model": model,
    }
    
    # GPT-5 doesn't support temperature parameter - only reasoning effort
    if "gpt-5" in model:
        kwargs["reasoning"] = {
            "effort": os.environ.get("MEETING_AGENT_REASONING_EFFORT", "medium")
        }
        logger.debug(f"GPT-5 detected: Using reasoning effort instead of temperature")
    else:
        # Only add temperature for non-GPT-5 models
        kwargs["temperature"] = temperature
    
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    
    return ChatOpenAI(**kwargs)


def _track_time(state: AgendaState, node_name: str, start_time: float):
    """Helper to track node execution time."""
    elapsed = time.time() - start_time
    step_times = state.get("step_times", {})
    step_times[node_name] = round(elapsed, 3)
    state["step_times"] = step_times


def _log_node_start(node_name: str, description: str):
    """Log when a node starts processing."""
    logger.info(f"🔄 [{node_name}] {description}")


def _log_node_complete(node_name: str, details: str = ""):
    """Log when a node completes."""
    logger.info(f"✅ [{node_name}] Complete{f': {details}' if details else ''}")


def _update_progress(state: AgendaState, node_name: str, status: str = "running", error: str = None):
    """Update progress tracking for this workflow session."""
    session_id = state.get("session_id")
    if session_id:
        logger.info(f"📊 Updating progress: session={session_id}, node={node_name}, status={status}")
        update_progress(session_id, node_name, status, error)
    else:
        logger.warning(f"⚠️ No session_id in state, cannot update progress for node {node_name}")


def _parse_llm_response(response) -> dict:
    """
    Parse LLM response content into JSON.
    
    Handles both:
    - Standard string responses (GPT-4, etc.)
    - GPT-5 reasoning responses (list of content blocks)
    """
    if isinstance(response.content, list):
        # GPT-5 with reasoning returns list of content blocks
        content_text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                content_text += block.text
            elif isinstance(block, dict) and 'text' in block:
                content_text += block['text']
            elif isinstance(block, str):
                content_text += block
        return json.loads(content_text)
    elif isinstance(response.content, str):
        # Standard response format
        return json.loads(response.content)
    else:
        raise ValueError(f"Unexpected response content type: {type(response.content)}")


# ========== NODE 1: Parse & Understand ==========

def parse_and_understand(state: AgendaState) -> AgendaState:
    """
    Parse natural language query into structured data.
    
    Extracts:
    - Subject/topic
    - Language (pt-BR or en-US)
    - Duration
    - Constraints
    """
    start = time.time()
    _log_node_start("parse_and_understand", "Parsing natural language query...")
    _update_progress(state, "parse_and_understand", "running")
    
    try:
        llm = _get_llm(temperature=0)
        
        prompt = get_parse_prompt(
            state.get("raw_query", ""),
            state.get("org_id", "org_demo")
        )
        
        response = llm.invoke([HumanMessage(content=prompt)])
        parsed = _parse_llm_response(response)
        
        state.update({
            "subject": parsed.get("subject"),
            "language": parsed.get("language", "pt-BR"),
            "duration_minutes": parsed.get("duration_minutes", 30),
            "constraints": parsed.get("constraints", {}),
        })
        _log_node_complete("parse_and_understand", f"Subject: {parsed.get('subject')}, Language: {parsed.get('language')}")
        
    except Exception as e:
        _update_progress(state, "parse_and_understand", "error", str(e))
        errors = state.get("errors", [])
        errors.append(f"parse_and_understand: {str(e)}")
        state["errors"] = errors
        
        # Fallback values
        state.update({
            "subject": None,
            "language": "pt-BR",
            "duration_minutes": 30,
            "constraints": {},
        })
    
    _track_time(state, "parse_and_understand", start)
    _update_progress(state, "parse_and_understand", "completed")
    return state


# ========== NODE 2: Context Analysis ==========

def analyze_context(state: AgendaState) -> AgendaState:
    """
    Analyze recent meetings to understand patterns.
    
    - Fetches last 5 meetings
    - Extracts open items from agendas
    - Uses LLM to synthesize context
    """
    start = time.time()
    _log_node_start("analyze_context", "Analyzing recent meetings and context...")
    _update_progress(state, "analyze_context", "running")
    
    try:
        org_id = state.get("org_id", "org_demo")
        
        # Fetch recent meetings from DB (SQLite only - not supported in MongoDB yet)
        recent_meetings = []
        try:
            # Check if we have get_conn (SQLite mode)
            if hasattr(db, 'get_conn'):
                conn = db.get_conn()
                cursor = conn.cursor()
                
                recent_query = """
                    SELECT meeting_id, created_at, participants, agenda
                    FROM meetings
                    WHERE org_id = ?
                    ORDER BY created_at DESC
                    LIMIT 5
                """
                
                rows = cursor.execute(recent_query, (org_id,)).fetchall()
                
                for row in rows:
                    meeting = {
                        "meeting_id": row[0],
                        "created_at": row[1],
                        "participants": json.loads(row[2]) if row[2] else [],
                        "agenda": json.loads(row[3]) if row[3] else {},
                    }
                    recent_meetings.append(meeting)
            else:
                logger.info("📝 MongoDB mode: Recent meetings analysis skipped (not yet supported)")
        except Exception as db_err:
            logger.warning(f"⚠️  Could not fetch recent meetings: {db_err}")
            recent_meetings = []
        
        # Extract open items from agendas
        open_items = []
        for meeting in recent_meetings:
            agenda = meeting.get("agenda", {})
            for section in agenda.get("sections", []):
                for item in section.get("items", []):
                    for bullet in item.get("bullets", []):
                        if not bullet.get("completed", False):
                            open_items.append({
                                "text": bullet.get("text"),
                                "from_meeting": meeting["meeting_id"],
                                "date": meeting.get("created_at"),
                            })
        
        # Use LLM to synthesize context (if we have meetings)
        if recent_meetings:
            llm = _get_llm(temperature=0.3)
            
            prompt = get_context_analysis_prompt(
                recent_meetings,
                open_items,
                org_id
            )
            
            response = llm.invoke([HumanMessage(content=prompt)])
            context_data = _parse_llm_response(response)
            
            state.update({
                "recent_meetings": recent_meetings,
                "meeting_context": context_data.get("summary", ""),
                "open_items": open_items[:20],
                "themes": context_data.get("themes", []),
                "meeting_frequency": context_data.get("frequency"),
            })
        else:
            # No recent meetings - first time
            state.update({
                "recent_meetings": [],
                "meeting_context": "This appears to be the first meeting for this organization.",
                "open_items": [],
                "themes": [],
                "meeting_frequency": None,
            })
        
    except Exception as e:
        _update_progress(state, "analyze_context", "error", str(e))
        errors = state.get("errors", [])
        errors.append(f"analyze_context: {str(e)}")
        state["errors"] = errors
        
        # Fallback
        state.update({
            "recent_meetings": [],
            "meeting_context": "",
            "open_items": [],
            "themes": [],
        })
    
    _track_time(state, "analyze_context", start)
    _update_progress(state, "analyze_context", "completed")
    return state


# ========== NODE 3: Intent Detection ==========

def detect_intent(state: AgendaState) -> AgendaState:
    """
    Detect meeting intent using LLM reasoning.
    
    Intent types:
    - decision_making
    - problem_solving
    - planning
    - alignment
    - status_update
    - kickoff
    """
    start = time.time()
    _log_node_start("detect_intent", "Detecting meeting intent and workstreams...")
    _update_progress(state, "detect_intent", "running")
    
    try:
        org_id = state.get("org_id", "org_demo")
        
        # STEP 1: Fetch ALL workstreams from DB first
        available_workstreams = []
        try:
            # Use db_router abstraction for MongoDB/SQLite compatibility
            workstream_rows = db.list_workstreams(org_id=org_id)
            
            for ws in workstream_rows:
                available_workstreams.append({
                    "workstream_id": ws.get("workstream_id") or ws.get("id"),
                    "title": ws.get("title", ""),
                    "description": ws.get("description", ""),
                    "status": ws.get("status", "green"),
                    "priority": ws.get("priority", 1),
                    "owner": ws.get("owner", ""),
                })
            
            logger.info(f"📚 Found {len(available_workstreams)} workstreams in DB for org={org_id}")
            if available_workstreams:
                logger.info(f"   Workstreams: {[ws['title'] for ws in available_workstreams[:10]]}")
        except Exception as db_err:
            logger.warning(f"⚠️  Could not fetch workstreams from DB: {db_err}")
            available_workstreams = []
        
        # STEP 2: Ask LLM to detect intent AND select relevant workstreams
        llm = _get_llm(temperature=0)
        
        prompt = get_intent_detection_prompt(
            state.get("subject", ""),
            state.get("meeting_context", ""),
            state.get("themes", []),
            len(state.get("open_items", [])),
            state.get("language", "pt-BR"),
            available_workstreams=available_workstreams  # Pass DB workstreams to LLM
        )
        
        response = llm.invoke([HumanMessage(content=prompt)])
        intent_data = _parse_llm_response(response)
        
        logger.info(f"🎯 Detected intent: {intent_data.get('intent')} (confidence: {intent_data.get('confidence')})")
        
        # STEP 3: Match LLM-selected workstream titles to DB workstreams
        selected_ws_titles = intent_data.get("workstreams", [])
        matched_workstreams = []
        
        if selected_ws_titles and available_workstreams:
            logger.info(f"📋 LLM selected workstreams: {selected_ws_titles}")
            
            # Create a lookup dict for fast matching
            ws_lookup = {ws["title"].lower(): ws for ws in available_workstreams}
            
            for title in selected_ws_titles:
                title_lower = title.lower()
                
                # Try exact match first
                if title_lower in ws_lookup:
                    matched_workstreams.append(ws_lookup[title_lower])
                    logger.info(f"✅ Exact match: '{title}' → {ws_lookup[title_lower]['workstream_id'][:8]}...")
                else:
                    # Try fuzzy match (contains)
                    found = False
                    for ws_title, ws_data in ws_lookup.items():
                        if title_lower in ws_title or ws_title in title_lower:
                            matched_workstreams.append(ws_data)
                            logger.info(f"✅ Fuzzy match: '{title}' → '{ws_data['title']}' ({ws_data['workstream_id'][:8]}...)")
                            found = True
                            break
                    
                    if not found:
                        logger.warning(f"⚠️  Could not match workstream: '{title}' (not found in available list)")
        
        logger.info(f"🗂️  Final matched workstreams: {len(matched_workstreams)}")
        
        state.update({
            "intent": intent_data.get("intent", "alignment"),
            "intent_confidence": intent_data.get("confidence", 0.5),
            "intent_reasoning": intent_data.get("reasoning", ""),
            "workstreams": matched_workstreams,
            "focus_areas": intent_data.get("focus_areas", []),
        })
        
    except Exception as e:
        _update_progress(state, "detect_intent", "error", str(e))
        errors = state.get("errors", [])
        errors.append(f"detect_intent: {str(e)}")
        state["errors"] = errors
        
        # Fallback to alignment
        state.update({
            "intent": "alignment",
            "intent_confidence": 0.3,
            "intent_reasoning": "Defaulted to alignment due to error",
            "workstreams": [],
            "focus_areas": [],
        })
    
    _track_time(state, "detect_intent", start)
    _update_progress(state, "detect_intent", "completed")
    _log_node_complete("detect_intent", f"Intent: {state.get('intent')}, Workstreams: {len(state.get('workstreams', []))}")
    return state


# ========== NODE 4: Smart Fact Retrieval ==========

def retrieve_facts(state: AgendaState) -> AgendaState:
    """
    Multi-strategy fact retrieval with LLM ranking.
    
    Strategies:
    1. Workstream-linked facts
    2. Semantic/subject search
    3. Urgent/overdue items
    4. LLM ranking to prioritize
    """
    start = time.time()
    _log_node_start("retrieve_facts", "Retrieving relevant facts and context...")
    _update_progress(state, "retrieve_facts", "running")
    
    try:
        org_id = state.get("org_id", "org_demo")
        subject = state.get("subject", "")
        logger.info(f"🔍 Retrieving facts for org={org_id}, subject={subject}")
        
        retriever = MultiStrategyRetriever(org_id)
        
        # Get workstream IDs
        workstream_ids = [ws["workstream_id"] for ws in state.get("workstreams", [])]
        
        # Execute multi-strategy retrieval
        result = retriever.retrieve_all(
            workstream_ids=workstream_ids if workstream_ids else None,
            subject=state.get("subject")
        )
        
        all_facts = result["facts"]
        stats = result["stats"]
        
        logger.info(f"📊 Retrieved {len(all_facts)} facts | Stats: {stats}")
        if all_facts:
            logger.info(f"📝 Sample facts: {[f.get('content', '')[:50] for f in all_facts[:3]]}")
            logger.info(f"📋 Sample fact IDs: {[f.get('fact_id') for f in all_facts[:5]]}")
        else:
            logger.warning("⚠️  No internal facts found - will try web search for external context")
        
        # If we have very few facts, supplement with web search
        web_search_context = None
        subject_or_query = state.get("subject") or state.get("raw_query", "")
        
        if len(all_facts) < 5 and HAVE_WEB_SEARCH and subject_or_query:
            logger.info(f"🌐 Few internal facts ({len(all_facts)}) - searching web for context...")
            try:
                import asyncio
                
                # Create or get event loop
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                # Build search query
                search_query = f"{subject_or_query} latest news recent developments 2025"
                logger.info(f"🔍 Web search query: '{search_query}'")
                
                search_result = loop.run_until_complete(
                    perform_web_search(search_query, max_results=3, search_depth="basic", days=30)
                )
                
                if search_result["success"]:
                    web_search_context = search_result["formatted_summary"]
                    logger.info(f"✅ Web search found {search_result.get('results_count', 0)} results")
                    logger.info(f"📰 Web search answer: {search_result.get('answer', 'N/A')[:100]}...")
                else:
                    logger.warning(f"⚠️ Web search failed: {search_result.get('error')}")
            except Exception as e:
                logger.error(f"❌ Web search error: {str(e)}", exc_info=True)
        
        # If we have facts, use LLM to rank them
        if all_facts and len(all_facts) > 0:
            llm = _get_llm(temperature=0)
            
            prompt = get_fact_ranking_prompt(
                all_facts,
                state.get("intent", "alignment"),
                state.get("subject", ""),
                state.get("focus_areas", []),
                state.get("language", "pt-BR"),
                selected_workstreams=state.get("workstreams", [])  # Pass selected workstreams for prioritization
            )
            
            response = llm.invoke([HumanMessage(content=prompt)])
            ranking = _parse_llm_response(response)
            
            # Reorder facts by LLM ranking
            ranked_ids = ranking.get("ranked_fact_ids", [])
            fact_map = {f["fact_id"]: f for f in all_facts}
            ranked_facts = [fact_map[fid] for fid in ranked_ids if fid in fact_map]
            
            logger.info(f"🎯 LLM ranked {len(ranked_facts)} facts, using top 40")
            
            state.update({
                "candidate_facts": all_facts,
                "ranked_facts": ranked_facts[:40],
                "retrieval_strategy": "multi-strategy+llm-ranked",
                "retrieval_stats": stats,
                "web_search_context": web_search_context,  # Add web search results
            })
        else:
            # No facts found - web search context becomes primary source
            state.update({
                "candidate_facts": [],
                "ranked_facts": [],
                "retrieval_strategy": "web-search-only" if web_search_context else "multi-strategy",
                "retrieval_stats": stats,
                "web_search_context": web_search_context,
            })
        
    except Exception as e:
        _update_progress(state, "retrieve_facts", "error", str(e))
        errors = state.get("errors", [])
        errors.append(f"retrieve_facts: {str(e)}")
        state["errors"] = errors
        
        # Fallback to empty
        state.update({
            "candidate_facts": [],
            "ranked_facts": [],
            "retrieval_strategy": "failed",
            "retrieval_stats": {},
        })
    
    _track_time(state, "retrieve_facts", start)
    _update_progress(state, "retrieve_facts", "completed")
    _log_node_complete("retrieve_facts", f"{len(state.get('ranked_facts', []))} facts ranked")
    return state


# ========== NODE 4.5: Synthesize Workstream Status ==========

def synthesize_workstream_status(state: AgendaState) -> AgendaState:
    """
    Synthesize current workstream status from recent facts.
    
    Reads last 20 facts to understand:
    - Current state of workstreams
    - Active initiatives
    - Blockers or risks
    
    This gives context before generating the macro summary.
    """
    start = time.time()
    _log_node_start("synthesize_workstream_status", "Analyzing workstream current status...")
    _update_progress(state, "synthesize_workstream_status", "running")
    
    try:
        workstreams = state.get("workstreams", [])
        ranked_facts = state.get("ranked_facts", [])
        
        # Only run if we have workstreams or facts to analyze
        if not workstreams and not ranked_facts:
            logger.info("⏭️  No workstreams or facts - skipping status synthesis")
            state["workstream_status"] = None
            _track_time(state, "synthesize_workstream_status", start)
            _update_progress(state, "synthesize_workstream_status", "completed")
            return state
        
        logger.info(f"📊 Analyzing {len(workstreams)} workstreams and {len(ranked_facts)} facts")
        
        llm = _get_llm(temperature=0.3)
        
        from .prompts import get_workstream_status_prompt
        prompt = get_workstream_status_prompt(
            workstreams,
            ranked_facts[:20],  # Use top 20 most relevant facts
            state.get("language", "pt-BR")
        )
        
        response = llm.invoke([HumanMessage(content=prompt)])
        status_summary = response.content if isinstance(response.content, str) else str(response.content)
        
        state["workstream_status"] = status_summary
        logger.info(f"✅ Workstream status: {status_summary[:100]}...")
        _log_node_complete("synthesize_workstream_status", "Status synthesized")
        
    except Exception as e:
        logger.error(f"❌ synthesize_workstream_status error: {str(e)}")
        _update_progress(state, "synthesize_workstream_status", "error", str(e))
        errors = state.get("errors", [])
        errors.append(f"synthesize_workstream_status: {str(e)}")
        state["errors"] = errors
        state["workstream_status"] = None
    
    _track_time(state, "synthesize_workstream_status", start)
    _update_progress(state, "synthesize_workstream_status", "completed")
    return state


# ========== NODE 5: Macro Summary ==========

def generate_macro_summary(state: AgendaState) -> AgendaState:
    """
    Generate high-level meeting context summary.
    
    3-4 sentence synthesis of:
    - Workstream status
    - Critical items
    - Meeting goal
    """
    start = time.time()
    _update_progress(state, "generate_macro_summary", "running")
    
    try:
        llm = _get_llm(temperature=0.3)
        
        prompt = get_macro_summary_prompt(
            state.get("workstreams", []),
            state.get("ranked_facts", []),
            state.get("meeting_context", ""),
            state.get("language", "pt-BR"),
            state.get("web_search_context"),  # Pass web search results
            state.get("workstream_status")  # Pass workstream status synthesis
        )
        
        response = llm.invoke([HumanMessage(content=prompt)])
        
        # Handle both string and list responses (GPT-5 can return list)
        content = response.content
        if isinstance(content, list):
            # Extract text from list of content blocks
            content = " ".join(
                block.get("text", str(block)) if isinstance(block, dict) else str(block)
                for block in content
            )
        
        state["macro_summary"] = content.strip()
        
    except Exception as e:
        _update_progress(state, "generate_macro_summary", "error", str(e))
        errors = state.get("errors", [])
        errors.append(f"generate_macro_summary: {str(e)}")
        state["errors"] = errors
        
        # Fallback
        subject = state.get("subject", "a próxima reunião")
        state["macro_summary"] = f"Reunião para discutir {subject}."
    
    _track_time(state, "generate_macro_summary", start)
    _update_progress(state, "generate_macro_summary", "completed")
    return state


# ========== NODE 6: Build Agenda ==========

def build_agenda(state: AgendaState) -> AgendaState:
    """
    Build intent-driven agenda with LLM assistance.
    
    Uses section templates based on intent,
    populates with ranked facts.
    """
    start = time.time()
    _log_node_start("build_agenda", "Building agenda based on intent template...")
    _update_progress(state, "build_agenda", "running")
    
    try:
        intent = state.get("intent", "alignment")
        language = state.get("language", "pt-BR")
        
        logger.info(f"📝 Building agenda - Intent: {intent}, Language: {language}")
        
        # Get template for this intent
        template = get_section_template(intent, language)
        template_sections = template.get('suggested_sections', [])
        logger.info(f"📋 Template has {len(template_sections)} suggested sections")
        logger.info(f"📋 Template sections: {[s.get('title') for s in template_sections]}")
        
        llm = _get_llm(temperature=0.3)
        
        prompt = get_agenda_builder_prompt(
            intent,
            template,
            state.get("ranked_facts", []),
            state.get("macro_summary", ""),
            state.get("duration_minutes", 30),
            language,
            state.get("web_search_context")  # Pass web search results
        )
        
        # DEBUG: Log facts being sent to LLM
        ranked_facts = state.get("ranked_facts", [])
        if ranked_facts:
            fact_ids = [f.get("fact_id") for f in ranked_facts[:5]]
            logger.info(f"📋 [build_agenda] Sending {len(ranked_facts)} facts to LLM, sample IDs: {fact_ids}")
        
        logger.info(f"🤖 Calling LLM to build agenda (model: {llm.model_name if hasattr(llm, 'model_name') else 'unknown'})...")
        response = llm.invoke([HumanMessage(content=prompt)])
        draft_agenda = _parse_llm_response(response)
        
        sections_count = len(draft_agenda.get("sections", []))
        logger.info(f"✨ LLM returned agenda with {sections_count} sections")
        logger.info(f"📋 Section titles: {[s.get('title') for s in draft_agenda.get('sections', [])]}")
        
        # DEBUG: Check if LLM included refs in bullets
        total_bullets = 0
        bullets_with_refs = 0
        total_refs = 0
        for section in draft_agenda.get("sections", []):
            for item in section.get("items", []):
                for bullet in item.get("bullets", []):
                    total_bullets += 1
                    refs = bullet.get("refs", [])
                    if refs:
                        bullets_with_refs += 1
                        total_refs += len(refs)
        
        logger.info(f"🔍 [build_agenda] Bullets: {total_bullets}, With refs: {bullets_with_refs}, Total refs: {total_refs}")
        if total_refs > 0:
            # Log sample refs
            sample_refs = []
            for section in draft_agenda.get("sections", [])[:2]:  # First 2 sections
                for item in section.get("items", [])[:2]:  # First 2 items
                    for bullet in item.get("bullets", [])[:2]:  # First 2 bullets
                        refs = bullet.get("refs", [])
                        if refs:
                            sample_refs.append(refs)
                            if len(sample_refs) >= 3:
                                break
            logger.info(f"📎 [build_agenda] Sample refs: {sample_refs[:3]}")
        
        state["draft_agenda"] = draft_agenda
        _log_node_complete("build_agenda", f"{sections_count} sections created")
        
    except Exception as e:
        logger.error(f"❌ build_agenda error: {str(e)}")
        _update_progress(state, "build_agenda", "error", str(e))
        errors = state.get("errors", [])
        errors.append(f"build_agenda: {str(e)}")
        state["errors"] = errors
        
        # Fallback to minimal agenda
        language = state.get("language", "pt-BR")
        state["draft_agenda"] = {
            "title": "Reunião" if language == "pt-BR" else "Meeting",
            "minutes": state.get("duration_minutes", 30),
            "sections": [
                {
                    "title": "Abertura" if language == "pt-BR" else "Opening",
                    "minutes": 5,
                    "items": []
                }
            ]
        }
    
    _track_time(state, "build_agenda", start)
    _update_progress(state, "build_agenda", "completed")
    return state


# ========== NODE 7: Review Quality ==========

def review_quality(state: AgendaState) -> AgendaState:
    """
    Review agenda quality and determine if refinement needed.
    
    Quality criteria:
    - Sections balanced
    - Time adds up
    - Open items addressed
    - Bullets actionable
    - Evidence present
    """
    start = time.time()
    _update_progress(state, "review_quality", "running")
    
    try:
        llm = _get_llm(temperature=0)
        
        prompt = get_quality_review_prompt(
            state.get("draft_agenda", {}),
            state.get("intent", "alignment"),
            state.get("subject", ""),
            len(state.get("open_items", [])),
            state.get("language", "pt-BR")
        )
        
        response = llm.invoke([HumanMessage(content=prompt)])
        review = _parse_llm_response(response)
        
        state.update({
            "quality_score": review.get("quality_score", 0.0),
            "quality_issues": review.get("issues", []),
            "quality_suggestions": review.get("suggestions", []),
        })
        
    except Exception as e:
        _update_progress(state, "review_quality", "error", str(e))
        errors = state.get("errors", [])
        errors.append(f"review_quality: {str(e)}")
        state["errors"] = errors
        
        # Fallback to passing
        state.update({
            "quality_score": 0.7,
            "quality_issues": [],
            "quality_suggestions": [],
        })
    
    _track_time(state, "review_quality", start)
    _update_progress(state, "review_quality", "completed")
    return state


# ========== CONDITIONAL EDGE: Should Refine? ==========

def should_refine(state: AgendaState) -> Literal["refine", "finalize"]:
    """
    Determine if agenda needs refinement or is ready to finalize.
    
    Criteria:
    - Quality score >= 0.7: finalize
    - Quality score < 0.7 AND refinement_count < 2: refine
    - Else: finalize (avoid infinite loops)
    """
    quality_score = state.get("quality_score", 0.0)
    refinement_count = state.get("refinement_count", 0)
    
    # Max 2 refinements to avoid loops
    if quality_score < 0.7 and refinement_count < 2:
        # Increment refinement counter
        state["refinement_count"] = refinement_count + 1
        return "refine"
    
    return "finalize"


# ========== NODE 8: Finalize & Persist ==========

def finalize_agenda(state: AgendaState) -> AgendaState:
    """
    Finalize agenda and persist to database.
    
    - Adds metadata v2.0
    - Persists to DB
    - Returns agenda_id
    """
    start = time.time()
    _log_node_start("finalize_agenda", "Finalizing and persisting agenda...")
    _update_progress(state, "finalize_agenda", "running")
    
    try:
        final_agenda = state.get("draft_agenda", {})
        
        sections_count = len(final_agenda.get("sections", []))
        logger.info(f"📋 Finalizing agenda with {sections_count} sections")
        logger.info(f"📋 Section titles: {[s.get('title') for s in final_agenda.get('sections', [])]}")
        
        # DEBUG: Check if refs survived to finalization
        total_bullets = 0
        bullets_with_refs = 0
        total_refs = 0
        for section in final_agenda.get("sections", []):
            for item in section.get("items", []):
                for bullet in item.get("bullets", []):
                    total_bullets += 1
                    refs = bullet.get("refs", [])
                    if refs:
                        bullets_with_refs += 1
                        total_refs += len(refs)
        
        logger.info(f"🔍 [finalize_agenda] Bullets: {total_bullets}, With refs: {bullets_with_refs}, Total refs: {total_refs}")
        
        # Add metadata v2.0
        final_agenda["_metadata"] = {
            "agenda_v": "2.0",
            "generator": "langgraph",
            "intent": state.get("intent"),
            "intent_confidence": state.get("intent_confidence"),
            "quality_score": state.get("quality_score"),
            "workstreams": state.get("workstreams", []),
            "macro_summary": state.get("macro_summary"),
            "refinement_count": state.get("refinement_count", 0),
            "step_times": state.get("step_times", {}),
            "retrieval_stats": state.get("retrieval_stats", {}),
        }
        
        # Persist to DB
        org_id = state.get("org_id", "org_demo")
        
        proposal = {
            "agenda": final_agenda,
            "choice": f"langgraph-{state.get('intent')}",
            "reason": "LLM-driven iterative planning with quality review",
            "subject": {
                "query": state.get("subject") or state.get("raw_query"),
                "coverage": state.get("quality_score", 0.0),
                "facts": len(state.get("ranked_facts", [])),
            },
            "supporting_fact_ids": [f["fact_id"] for f in state.get("ranked_facts", [])],
        }
        
        agenda_id = persist_agenda_proposal(
            org_id,
            proposal,
            meeting_id=None,
            transcript_id=None,
        )
        
        state.update({
            "final_agenda": final_agenda,
            "agenda_id": agenda_id,
        })
        
        _log_node_complete("finalize_agenda", f"Persisted with {sections_count} sections, ID: {agenda_id}")
        
    except Exception as e:
        _update_progress(state, "finalize_agenda", "error", str(e))
        errors = state.get("errors", [])
        errors.append(f"finalize_agenda: {str(e)}")
        state["errors"] = errors
        
        # Use draft as final
        state["final_agenda"] = state.get("draft_agenda", {})
        state["agenda_id"] = None
    
    _track_time(state, "finalize_agenda", start)
    _update_progress(state, "finalize_agenda", "completed")
    return state
