from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    from pathlib import Path
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded environment from {env_path}")
except ImportError:
    print("⚠️  python-dotenv not installed - environment variables must be set manually")

try:
    from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
    from fastapi.responses import JSONResponse, StreamingResponse
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    HAVE_FASTAPI = True
except Exception:  # pragma: no cover - FastAPI optional in local envs
    HAVE_FASTAPI = False

from . import agenda, db_router as db, retrieval, textgen, nl_parser, workstream_auto
from . import config
import logging
import time

logger = logging.getLogger(__name__)


def _row_to_fact(row: Any) -> Dict[str, Any]:
    payload = row["payload"]
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    fact: Dict[str, Any] = {k: row[k] for k in row.keys()}
    fact["payload"] = payload
    return fact


if HAVE_FASTAPI:
    app = FastAPI(title="Meeting Agenda Agent", version="0.2")
    
    # Add CORS middleware to allow frontend access
    # Get allowed origins from environment or use defaults for local development
    allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
    if allowed_origins_env:
        # Split comma-separated origins from environment variable
        allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")]
        print(f"✅ CORS: Using origins from ALLOWED_ORIGINS env var: {allowed_origins}")
    else:
        # Default to localhost for local development
        allowed_origins = ["http://localhost:5000", "http://127.0.0.1:5000"]
        print(f"⚠️  CORS: Using default localhost origins (set ALLOWED_ORIGINS for production)")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class AgendaRequest(BaseModel):
        org: Optional[str] = Field(default=None, description="Org id or text hint")
        subject: Optional[str] = Field(default=None, description="Optional meeting subject")
        meeting_id: Optional[str] = None
        transcript_id: Optional[str] = None
        duration_minutes: Optional[int] = Field(default=None, ge=5)
        language: Optional[str] = None
        prompt: Optional[str] = Field(default=None, description="Free-text request")
        format: Optional[str] = Field(default="json", description="json|nl")
        justify: Optional[bool] = Field(default=False, description="Include references in text output when format=nl")

    class StatusRequest(BaseModel):
        status: str = Field(description="New fact status")

    class NLPlanRequest(BaseModel):
        text: str
        org: Optional[str] = None
        duration_minutes: Optional[int] = Field(default=None, ge=5)
        language: Optional[str] = None
        context: Optional[str] = None
        format: Optional[str] = Field(default="json", description="json|nl")
        justify: Optional[bool] = Field(default=False, description="Include references in output where applicable")
        macro: Optional[str] = Field(default=None, description="auto|strict|off - macro planning mode")

    class WorkstreamIn(BaseModel):
        workstream_id: Optional[str] = None
        org_id: str
        title: str
        description: Optional[str] = None
        status: str = Field(default="green", pattern="^(green|yellow|red)$")
        priority: int = Field(default=1, ge=0)
        owner: Optional[str] = None
        start_iso: Optional[str] = None
        target_iso: Optional[str] = None
        tags: Optional[List[str]] = Field(default_factory=list)

    class LinkFactsIn(BaseModel):
        fact_ids: List[str]
        weight: float = Field(default=1.0, ge=0.0, le=1.0)

    @app.post("/agenda/propose")
    def agenda_propose(req: AgendaRequest):
        # Be conservative here: do not auto-create orgs from noisy inputs
        org_id = retrieval.resolve_org_id(req.org, allow_create=False, full_text=(req.prompt or req.subject or ""))
        result = agenda.propose_agenda(
            org=org_id,
            subject=req.subject,
            prompt=req.prompt,
            meeting_id=req.meeting_id,
            transcript_id=req.transcript_id,
            duration_minutes=req.duration_minutes,
            language=req.language,
        )
        snapshot = result.get("snapshot") or {}
        preview = result.get("proposal_preview") or {}
        # Text output option
        if (req.format or "json").lower() == "nl":
            # Determine language: explicit > org context > preview > default
            lang = req.language
            if not lang:
                ctx = db.get_org_context(org_id)
                if ctx and ctx.get("language"):
                    lang = ctx["language"]
            lang = lang or preview.get("language") or "pt-BR"
            agenda_obj = preview.get("agenda")
            if agenda_obj:
                text = textgen.agenda_to_text({"agenda": agenda_obj, "subject": preview.get("subject")}, language=lang, with_refs=bool(req.justify))
            else:
                text = ""
            return JSONResponse({
                "fact_id": result.get("fact_id"),
                "text": text,
                "subject": preview.get("subject"),
                "language": lang,
            })
        response = {
            "fact_id": result.get("fact_id"),
            "agenda": preview.get("agenda"),
            "subject": preview.get("subject"),
            "status": snapshot.get("status"),
            "created_at": snapshot.get("created_at"),
        }
        return JSONResponse(response)

    @app.get("/agenda/proposals")
    def agenda_proposals(org: Optional[str] = None, limit: int = 20):
        org_id = retrieval.resolve_org_id(org)
        listing = agenda.list_agenda_proposals(org_id, limit=limit)
        return JSONResponse(listing)

    @app.get("/facts/search")
    def facts_search(org: Optional[str] = None, q: Optional[str] = None, types: Optional[str] = None, limit: int = 50):
        org_id = retrieval.resolve_org_id(org)
        type_list: Optional[List[str]] = None
        if types:
            type_list = [t.strip() for t in types.split(",") if t.strip()]
        rows = db.search_facts(org_id, q or "", type_list, limit)
        facts = [_row_to_fact(row) for row in rows]
        return JSONResponse({"org_id": org_id, "query": q, "types": type_list, "items": facts})

    # ========== LangGraph Agenda Planning Helpers ==========

    def _plan_with_langgraph(raw_query: str, org_id: str, language: str = "pt", session_id: str = None) -> Dict[str, Any]:
        """
        Plan agenda using LangGraph workflow (v2.0).
        
        Returns same format as legacy planner for compatibility.
        Plus session_id for progress tracking via SSE.
        
        Args:
            raw_query: User's natural language query
            org_id: Organization ID
            language: Language code (pt-BR or en-US)
            session_id: Optional pre-created session ID (for async workflows)
        """
        import uuid
        from .graph.graph import agenda_graph
        from .graph.state import AgendaState
        from .graph.progress import create_session, cleanup_session
        
        # Use provided session_id or generate new one
        if not session_id:
            session_id = str(uuid.uuid4())
            create_session(session_id, language)
        
        logger.info(f"🔧 _plan_with_langgraph using session_id: {session_id}")
        
        # Initialize state
        initial_state: AgendaState = {
            "raw_query": raw_query,
            "org_id": org_id,
            "session_id": session_id,  # Pass session_id to graph for progress tracking
            "step_times": {},
            "errors": [],
            "refinement_count": 0,
        }
        
        # Run graph
        start = time.time()
        
        try:
            final_state = agenda_graph.invoke(initial_state)
            elapsed = time.time() - start
            
            # Format response (compatible with legacy format)
            result = {
                "proposal": {
                    "agenda": final_state.get("final_agenda"),
                    "choice": f"langgraph-{final_state.get('intent')}",
                    "reason": "LLM-driven iterative planning with quality review",
                    "subject": {
                        "query": final_state.get("subject") or raw_query,
                        "coverage": final_state.get("quality_score", 0.0),
                        "facts": len(final_state.get("ranked_facts", [])),
                    },
                    "supporting_fact_ids": [f["fact_id"] for f in final_state.get("ranked_facts", [])],
                },
                "metadata": {
                    "version": "2.0",
                    "generator": "langgraph",
                    "elapsed_seconds": round(elapsed, 2),
                    "quality_score": final_state.get("quality_score"),
                    "refinement_count": final_state.get("refinement_count"),
                    "intent": final_state.get("intent"),
                    "intent_confidence": final_state.get("intent_confidence"),
                    "step_times": final_state.get("step_times"),
                    "retrieval_stats": final_state.get("retrieval_stats"),
                    "errors": final_state.get("errors", []),
                    "session_id": session_id,  # Include session_id for progress tracking
                    "ranked_facts": final_state.get("ranked_facts", []),  # ✅ Include ranked_facts for ref resolution
                },
                "subject": final_state.get("subject") or raw_query,
                "org_id": org_id,
            }
            
            # Progress session will be auto-cleaned up when SSE client disconnects
            # or after completion in the SSE endpoint
            
            return result
            
        except Exception as e:
            # Clean up session on error
            cleanup_session(session_id)
            logger.exception("LangGraph workflow failed")
            raise HTTPException(status_code=500, detail=f"LangGraph planning failed: {str(e)}")

    def _plan_with_legacy(req: "NLPlanRequest", org_id: str) -> Dict[str, Any]:
        """Legacy planner (for fallback)."""
        parsed = nl_parser.parse_nl(req.text, {})
        minutes = req.duration_minutes or parsed.target_duration_minutes
        lang = req.language or parsed.language
        
        return agenda.plan_agenda_next_only(
            org=org_id,
            subject=parsed.subject,
            company_context=req.context,
            duration_minutes=minutes,
            language=lang,
            macro_mode=req.macro,
        )

    def _should_use_langgraph(org_id: str) -> bool:
        """Check if org is whitelisted for LangGraph."""
        if not config.USE_LANGGRAPH_AGENDA:
            return False
        
        # If whitelist defined, check if org is in it
        if config.LANGGRAPH_ORGS:
            whitelist = [o.strip() for o in config.LANGGRAPH_ORGS.split(",")]
            return org_id in whitelist
        
        # Otherwise, use for all orgs if flag is enabled
        return True

    def _run_workflow_background(session_id: str, text: str, org_id: str, language: str, req: "NLPlanRequest"):
        """
        Run LangGraph workflow in background and store result in session.
        This allows the endpoint to return immediately with session_id.
        """
        from .graph.progress import set_final_result
        
        try:
            logger.info(f"🚀 Starting background workflow for session {session_id}")
            logger.info(f"📝 Query: {text[:100]}...")
            logger.info(f"🏢 Org: {org_id}, Language: {language}")
            
            # Pass session_id to workflow so it uses the same one
            result = _plan_with_langgraph(text, org_id, language, session_id=session_id)
            
            logger.info(f"✅ LangGraph completed for session {session_id}")
            logger.info(f"📊 Result keys: {list(result.keys())}")
            
            # Format response based on requested format
            minutes = req.duration_minutes
            lang = req.language or language
            fmt = (req.format or "json").lower()
            justify = bool(req.justify)
            
            logger.info(f"🔍 Format: {fmt}, Justify: {justify}, will enter branch: {fmt == 'json' and justify}")
            
            if fmt == "json" and justify:
                logger.info(f"📋 Processing JSON with refs (justify=True)")
                try:
                    # Process references (same logic as before)
                    prop = result.get("proposal") or {}
                    agenda = prop.get("agenda") or {}
                    
                    logger.info(f"📊 Agenda has {len(agenda.get('sections', []))} sections")
                    
                    # DEBUG: Log ranked_facts count from result metadata
                    metadata = result.get("metadata", {})
                    ranked_facts = metadata.get("ranked_facts", [])
                    logger.info(f"📚 Metadata has {len(ranked_facts)} ranked_facts")
                    
                    fact_ids_to_resolve = set()
                    for sec in agenda.get("sections", []):
                        for item in sec.get("items", []):
                            for bullet in item.get("bullets", []):
                                refs = bullet.get("refs", [])
                                for ref in refs:
                                    if isinstance(ref, str):
                                        fact_ids_to_resolve.add(ref)
                    
                    logger.info(f"📝 Found {len(fact_ids_to_resolve)} fact IDs to resolve")
                    if len(fact_ids_to_resolve) > 0:
                        logger.info(f"📋 Sample fact IDs: {list(fact_ids_to_resolve)[:5]}")
                    
                    fact_objects = {}
                    if fact_ids_to_resolve:
                        rows = db.get_facts_by_ids(list(fact_ids_to_resolve), org_id=org_id)
                        logger.info(f"📥 Retrieved {len(rows)} fact objects from DB")
                        for row in rows:
                            fact_objects[row["fact_id"]] = _row_to_fact(row)
                    
                    for sec in agenda.get("sections", []):
                        for item in sec.get("items", []):
                            for bullet in item.get("bullets", []):
                                resolved_refs = []
                                for ref in bullet.get("refs", []):
                                    if isinstance(ref, str) and ref in fact_objects:
                                        resolved_refs.append(fact_objects[ref])
                                    elif isinstance(ref, dict):
                                        resolved_refs.append(ref)
                                bullet["refs"] = resolved_refs
                    
                    logger.info(f"📤 Calling agenda_to_json with with_refs=True")
                    payload = textgen.agenda_to_json(
                        {"agenda": agenda, "subject": result.get("subject")},
                        language=lang,
                        with_refs=True
                    )
                    payload["metadata"] = result.get("metadata", {})
                    
                    logger.info(f"💾 About to call set_final_result for session {session_id}")
                    # Store final result in session
                    set_final_result(session_id, payload)
                    logger.info(f"✅ Background workflow completed for session {session_id}")
                    
                except Exception as ref_error:
                    logger.exception(f"❌ Error processing refs for session {session_id}: {ref_error}")
                    # Try to save without refs as fallback
                    try:
                        prop = result.get("proposal") or {}
                        payload = textgen.agenda_to_json(
                            {"agenda": prop.get("agenda"), "subject": result.get("subject")},
                            language=lang,
                            with_refs=False
                        )
                        payload["metadata"] = result.get("metadata", {})
                        set_final_result(session_id, payload)
                        logger.info(f"✅ Saved result WITHOUT refs due to error")
                    except Exception as fallback_error:
                        logger.exception(f"❌ Even fallback failed: {fallback_error}")
                        raise
                
            elif fmt == "json":
                prop = result.get("proposal") or {}
                payload = textgen.agenda_to_json(
                    {"agenda": prop.get("agenda"), "subject": result.get("subject")},
                    language=lang,
                    with_refs=False
                )
                payload["metadata"] = result.get("metadata", {})
                set_final_result(session_id, payload)
                logger.info(f"✅ Background workflow completed for session {session_id}")
                
            else:  # nl format
                prop = result.get("proposal") or {}
                text_result = textgen.agenda_to_text(
                    {"agenda": prop.get("agenda"), "subject": result.get("subject")},
                    language=lang,
                    with_refs=justify,
                )
                payload = {"org_id": org_id, "text": text_result, "language": lang, "subject": result.get("subject")}
                set_final_result(session_id, payload)
                logger.info(f"✅ Background workflow completed for session {session_id}")
                
        except Exception as e:
            logger.exception(f"❌ Background workflow failed for session {session_id}")
            from .graph.progress import update_progress
            update_progress(session_id, "workflow", "error", str(e))

    # ========== Agenda Planning Endpoints ==========

    @app.post("/agenda/plan-nl")
    def agenda_plan_nl(req: NLPlanRequest, background_tasks: BackgroundTasks):
        import uuid
        from .graph.progress import create_session
        
        parsed = nl_parser.parse_nl(req.text, {})
        org_id = retrieval.resolve_org_id(parsed.org_hint or req.org, allow_create=False, full_text=req.text)
        
        logger.info(f"📨 NL Plan - req.org={req.org}, parsed.org_hint={parsed.org_hint} → org_id={org_id}")
        logger.info(f"📝 Query: '{req.text}'")
        
        # Check if we should use LangGraph
        use_langgraph = _should_use_langgraph(org_id)
        
        if use_langgraph:
            # Create session and return immediately
            session_id = str(uuid.uuid4())
            language = req.language or parsed.language or "pt"
            create_session(session_id, language)
            
            # Run workflow in background
            background_tasks.add_task(
                _run_workflow_background,
                session_id, req.text, org_id, language, req
            )
            
            logger.info(f"📡 Returning session_id {session_id} - workflow running in background")
            
            # Return 202 Accepted with session_id
            return JSONResponse(
                status_code=202,
                content={
                    "session_id": session_id,
                    "status": "processing",
                    "message": "Workflow started, connect to SSE for progress",
                    "sse_endpoint": f"/agenda/progress/{session_id}"
                }
            )
        else:
            # Legacy synchronous flow
            result = _plan_with_legacy(req, org_id)
        
            # Format response based on requested format
            minutes = req.duration_minutes or parsed.target_duration_minutes
            lang = req.language or parsed.language
            fmt = (req.format or "json").lower()
            justify = bool(req.justify)
        
        if fmt == "nl":
            prop = result.get("proposal") or {}
            text = textgen.agenda_to_text(
                {"agenda": prop.get("agenda"), "subject": result.get("subject")},
                language=lang,
                with_refs=justify,
            )
            return JSONResponse({"org_id": org_id, "text": text, "language": lang, "subject": result.get("subject")})
        if fmt == "json":
            if justify:
                try:
                    prop = result.get("proposal") or {}
                    agenda = prop.get("agenda") or {}
                    
                    # Resolve fact IDs to actual fact objects for references
                    # The agenda has refs as strings (fact_ids), but textgen.agenda_to_json expects dict objects
                    fact_ids_to_resolve = set()
                    for sec in agenda.get("sections", []):
                        for item in sec.get("items", []):
                            for bullet in item.get("bullets", []):
                                refs = bullet.get("refs", [])
                                for ref in refs:
                                    if isinstance(ref, str):  # It's a fact_id
                                        fact_ids_to_resolve.add(ref)
                    
                    # Load fact objects from DB
                    fact_objects = {}
                    if fact_ids_to_resolve:
                        fact_rows = db.get_fact_rows(list(fact_ids_to_resolve))
                        for row in fact_rows:
                            fact_id = row["fact_id"]
                            # Convert row to dict that textgen expects
                            payload_data = json.loads(row["payload"]) if row["payload"] else {}
                            fact_objects[fact_id] = {
                                "id": fact_id,
                                "fact_id": fact_id,
                                "title": payload_data.get("title") or payload_data.get("text", "")[:100],
                                "excerpt": payload_data.get("text", "")[:200],
                                "fact_type": row["fact_type"],
                                "status": row["status"],
                                "updated_at": row["updated_at"],
                                "confidence": payload_data.get("confidence", 0.5),
                                "source": payload_data.get("source", ""),
                                "owner": payload_data.get("owner"),
                            }
                    
                    # Replace fact_id strings with fact objects in agenda
                    agenda_with_facts = json.loads(json.dumps(agenda))  # Deep copy
                    for sec in agenda_with_facts.get("sections", []):
                        for item in sec.get("items", []):
                            for bullet in item.get("bullets", []):
                                refs = bullet.get("refs", [])
                                resolved_refs = []
                                for ref in refs:
                                    if isinstance(ref, str) and ref in fact_objects:
                                        resolved_refs.append(fact_objects[ref])
                                    elif isinstance(ref, dict):
                                        resolved_refs.append(ref)  # Already an object
                                bullet["refs"] = resolved_refs
                    
                    payload = textgen.agenda_to_json(
                        {"agenda": agenda_with_facts, "subject": result.get("subject")}, 
                        language=lang, 
                        with_refs=True
                    )
                    logger.info(f"📤 Returning JSON with refs - Sections: {len(payload.get('sections', []))}")
                    logger.info(f"📤 Full payload sections: {[s.get('title') for s in payload.get('sections', [])]}")
                    logger.info(f"📤 Payload keys: {list(payload.keys())}")
                    logger.info(f"📤 Payload has 'sections' key: {'sections' in payload}")
                    logger.info(f"📤 Payload has 'subject' key: {'subject' in payload}")
                    logger.info(f"📤 Payload has 'references' key: {'references' in payload}")
                    
                    # Try to serialize to catch any JSON issues
                    try:
                        json_str = json.dumps(payload, ensure_ascii=False, default=str)
                        logger.info(f"✅ JSON serialization successful - {len(json_str)} bytes")
                    except Exception as json_err:
                        logger.error(f"❌ JSON serialization failed: {json_err}")
                        logger.error(f"Payload type: {type(payload)}")
                        logger.error(f"Payload keys: {list(payload.keys()) if isinstance(payload, dict) else 'NOT A DICT'}")
                        raise
                    
                    logger.info(f"🚀 About to return JSONResponse with payload")
                    
                    # IMPORTANT: Include metadata (with session_id) in the response!
                    payload["metadata"] = result.get("metadata", {})
                    
                    return JSONResponse(payload)
                except Exception as e:
                    logger.exception(f"❌ Error in justify path: {e}")
                    raise HTTPException(status_code=500, detail=f"Failed to format agenda: {str(e)}")
            logger.info(f"📤 Returning raw result - Keys: {list(result.keys())}")
            return JSONResponse(result)
        return JSONResponse(result)

    @app.get("/agenda/plan-nl")
    def agenda_plan_nl_get(
        text: str,
        org: Optional[str] = None,
        duration_minutes: Optional[int] = None,
        language: Optional[str] = None,
        context: Optional[str] = None,
        format: Optional[str] = "json",
        justify: Optional[str] = None,
        macro: Optional[str] = None,
    ):
        parsed = nl_parser.parse_nl(text, {})
        org_id = retrieval.resolve_org_id(parsed.org_hint or org, allow_create=False, full_text=text)
        minutes = duration_minutes or parsed.target_duration_minutes
        lang = language or parsed.language
        result = agenda.plan_agenda_next_only(
            org=org_id,
            subject=parsed.subject,
            company_context=context,
            duration_minutes=minutes,
            language=lang,
            macro_mode=macro,
        )
        fmt = (format or "json").lower()
        just = False
        if isinstance(justify, str):
            just = justify.strip().lower() in {"1", "true", "yes", "y"}
        if fmt == "nl":
            prop = result.get("proposal") or {}
            text_out = textgen.agenda_to_text(
                {"agenda": prop.get("agenda"), "subject": result.get("subject")},
                language=lang,
                with_refs=just,
            )
            return JSONResponse({"org_id": org_id, "text": text_out, "language": lang, "subject": result.get("subject")})
        if fmt == "json":
            if just:
                prop = result.get("proposal") or {}
                payload = textgen.agenda_to_json({"agenda": prop.get("agenda"), "subject": result.get("subject")}, language=lang, with_refs=True)
                return JSONResponse(payload)
            return JSONResponse(result)
        return JSONResponse(result)

    @app.get("/health")
    def health():
        return JSONResponse({"ok": True})

    @app.get("/agenda/progress/{session_id}")
    async def get_agenda_progress(session_id: str):
        """
        Server-Sent Events endpoint for real-time agenda planning progress.
        
        Usage:
            const eventSource = new EventSource(`/agenda/progress/${sessionId}`);
            eventSource.onmessage = (event) => {
                const progress = JSON.parse(event.data);
                console.log(progress.current_message);
            };
        """
        import asyncio
        from .graph.progress import get_progress, cleanup_session
        
        async def event_generator():
            """Generate SSE events with progress updates."""
            try:
                sent_completed_steps = set()
                
                while True:
                    progress = get_progress(session_id)
                    
                    if not progress:
                        # Session not found or cleaned up
                        yield f"data: {json.dumps({'error': 'Session not found'})}\n\n"
                        break
                    
                    # Send individual events for each completed step (for animation)
                    for step in progress.get("completed_steps", []):
                        if step not in sent_completed_steps:
                            step_event = {
                                "step": step,
                                "message": progress.get("current_message", ""),
                                "completed_steps": progress.get("completed_steps", []),
                                "status": "completed"
                            }
                            yield f"event: progress\ndata: {json.dumps(step_event)}\n\n"
                            sent_completed_steps.add(step)
                            await asyncio.sleep(0.3)  # 300ms delay for visible animation
                    
                    # Send current progress update
                    yield f"event: progress\ndata: {json.dumps(progress)}\n\n"
                    
                    # If completed AND has final_result, send completion event
                    if progress.get("completed") and progress.get("final_result"):
                        final_result = progress["final_result"]
                        
                        completion_event = {
                            "completed": True,
                            "result": final_result
                        }
                        yield f"event: complete\ndata: {json.dumps(completion_event)}\n\n"
                        logger.info(f"✅ Sent complete event with result for session {session_id}")
                        
                        await asyncio.sleep(0.5)  # Give client time to receive
                        cleanup_session(session_id)
                        break
                    
                    # Don't cleanup on errors - workflow might still complete with fallbacks
                    # Just send error info in progress updates
                    # The session will be cleaned up when completed=True + final_result exists
                    
                    # Poll every 500ms
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"SSE error for session {session_id}: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            }
        )

    # ---------------------------------------------------------------------------
    # Workstream endpoints (macro-context layer)
    # ---------------------------------------------------------------------------

    @app.post("/orgs/{org_id}/workstreams")
    def create_workstream(org_id: str, req: WorkstreamIn):
        """Create or update a workstream."""
        ws_dict = req.dict()
        ws_dict["org_id"] = org_id  # Override with path param
        result = db.upsert_workstream(ws_dict)
        return JSONResponse(result)

    @app.get("/orgs/{org_id}/workstreams")
    def list_workstreams_for_org(
        org_id: str,
        status: Optional[str] = None,
        min_priority: int = 0,
    ):
        """List workstreams for an org."""
        workstreams = db.list_workstreams(org_id, status=status, min_priority=min_priority)
        return JSONResponse({"org_id": org_id, "workstreams": workstreams})

    @app.get("/workstreams/{workstream_id}")
    def get_workstream_detail(workstream_id: str):
        """Get a single workstream by ID."""
        ws = db.get_workstream(workstream_id)
        if not ws:
            raise HTTPException(status_code=404, detail=f"Workstream not found: {workstream_id}")
        return JSONResponse(ws)

    @app.post("/workstreams/{workstream_id}/link-facts")
    def link_facts_to_workstream(workstream_id: str, req: LinkFactsIn):
        """Link facts to a workstream."""
        # Verify workstream exists
        ws = db.get_workstream(workstream_id)
        if not ws:
            raise HTTPException(status_code=404, detail=f"Workstream not found: {workstream_id}")
        
        count = db.link_facts(workstream_id, req.fact_ids, req.weight)
        return JSONResponse({
            "workstream_id": workstream_id,
            "linked_count": count,
            "fact_ids": req.fact_ids,
        })

    @app.get("/workstreams/{workstream_id}/facts")
    def get_workstream_facts(workstream_id: str, limit: int = 50):
        """Get facts linked to a workstream, hydrated with evidence and entities."""
        ws = db.get_workstream(workstream_id)
        if not ws:
            raise HTTPException(status_code=404, detail=f"Workstream not found: {workstream_id}")
        
        facts = db.get_facts_by_workstreams([workstream_id], limit_per_ws=limit)
        return JSONResponse({
            "workstream_id": workstream_id,
            "workstream": ws,
            "facts": facts,
        })

    @app.post("/orgs/{org_id}/workstreams:suggest")
    def suggest_workstreams(org_id: str, limit: int = 5):
        """Suggest workstreams from recent fact clusters (optional/experimental).
        
        Returns suggested workstream titles and linked fact IDs with lower weight.
        """
        # Get recent high-value facts
        recent = db.get_recent_facts(
            org_id,
            ["decision", "open_question", "risk", "milestone", "action_item"],
            limit=100,
        )
        
        # Filter to validated/published
        recent = [r for r in recent if r["status"] in ("validated", "published")]
        
        if not recent:
            return JSONResponse({"org_id": org_id, "suggestions": []})
        
        # Simple clustering by keywords in payload
        from collections import defaultdict
        clusters: Dict[str, List[str]] = defaultdict(list)
        
        for row in recent:
            payload = row["payload"]
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = {}
            
            # Extract keywords
            text = ""
            for key in ("subject", "title", "name", "text"):
                val = payload.get(key)
                if isinstance(val, str) and val.strip():
                    text = val.strip()
                    break
            
            if not text:
                continue
            
            # Simple keyword extraction
            import re
            tokens = re.findall(r"[\wÀ-ÿ]{4,}", text.lower())
            
            # Use first meaningful token as cluster key (simplified)
            if tokens:
                key = tokens[0]
                clusters[key].append(row["fact_id"])
        
        # Build suggestions
        suggestions = []
        for key, fact_ids in sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True)[:limit]:
            suggestions.append({
                "suggested_title": key.capitalize(),
                "fact_ids": fact_ids[:20],
                "weight": 0.6,  # Suggested links have lower weight
            })
        
        return JSONResponse({"org_id": org_id, "suggestions": suggestions})

    @app.post("/orgs/{org_id}/workstreams:auto-create")
    def auto_create_workstreams(org_id: str):
        """Auto-create workstreams using fact clustering (🤖).
        
        Uses entity co-occurrence and keyword clustering to identify
        natural workstream boundaries. Auto-created workstreams get 🤖 badge.
        
        Returns:
            {
                "created": [{id, title, description, fact_count}],
                "suggested": [{title, description, fact_ids}],
                "total_facts_clustered": int
            }
        """
        try:
            result = workstream_auto.auto_create_workstreams_for_org(org_id)
            return JSONResponse(result)
        except Exception as e:
            return JSONResponse(
                {"error": f"Auto-creation failed: {str(e)}"},
                status_code=500
            )

    @app.get("/orgs/{org_id}/workstreams:auto-suggested")
    def get_auto_suggested_workstreams(org_id: str):
        """Get suggested workstreams without creating them.
        
        Useful for preview/review before auto-creation.
        
        Returns:
            {
                "org_id": str,
                "suggestions": [{title, description, fact_ids, fact_count}]
            }
        """
        try:
            suggestions = workstream_auto.get_suggested_workstreams(org_id)
            return JSONResponse({
                "org_id": org_id,
                "suggestions": suggestions
            })
        except Exception as e:
            return JSONResponse(
                {"error": f"Suggestion failed: {str(e)}"},
                status_code=500
            )

    # Meeting-Workstream Linking
    @app.post("/meetings/{meeting_id}/link-workstream")
    def link_meeting_workstream(meeting_id: str, body: dict):
        """Link a meeting to a workstream.
        
        Body: { "workstream_id": "ws_xxx" }
        """
        workstream_id = body.get("workstream_id")
        if not workstream_id:
            return JSONResponse({"error": "workstream_id required"}, status_code=400)
        
        try:
            linked = db.link_meeting_to_workstream(meeting_id, workstream_id)
            return JSONResponse({"meeting_id": meeting_id, "workstream_id": workstream_id, "linked": linked})
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    @app.delete("/meetings/{meeting_id}/link-workstream/{workstream_id}")
    def unlink_meeting_workstream(meeting_id: str, workstream_id: str):
        """Unlink a meeting from a workstream."""
        unlinked = db.unlink_meeting_from_workstream(meeting_id, workstream_id)
        return JSONResponse({"meeting_id": meeting_id, "workstream_id": workstream_id, "unlinked": unlinked})

    @app.get("/meetings/{meeting_id}/workstreams")
    def get_meeting_workstreams_endpoint(meeting_id: str):
        """Get all workstreams linked to a meeting."""
        workstreams = db.get_meeting_workstreams(meeting_id)
        return JSONResponse({"meeting_id": meeting_id, "workstreams": workstreams})

    @app.get("/workstreams/{workstream_id}/meetings")
    def get_workstream_meetings_endpoint(workstream_id: str, limit: int = 50):
        """Get all meetings linked to a workstream."""
        meeting_ids = db.get_workstream_meetings(workstream_id, limit)
        meeting_count = db.get_workstream_meeting_count(workstream_id)
        return JSONResponse({
            "workstream_id": workstream_id,
            "meeting_ids": meeting_ids,
            "meeting_count": meeting_count,
        })

    @app.post("/agenda/plan-nl-raw")
    async def agenda_plan_nl_raw(request: Request):
        """Accept a raw plain-text body (no JSON) and return an agenda preview.

        Usage example (PowerShell / Windows):
            curl.exe -X POST http://localhost:8000/agenda/plan-nl-raw \
              -H "Content-Type: text/plain" \
              --data "próxima reunião com a BYD sobre integrações, 45 min"

        You can optionally pass query params: ?org=byd&format=nl&language=pt-BR
        """
        raw = await request.body()
        text = raw.decode("utf-8", errors="ignore").strip()
        if not text:
            return JSONResponse({"error": "empty_body"}, status_code=400)
        qp = request.query_params
        org_q = qp.get("org") or None
        fmt = (qp.get("format") or "json").lower()
        justify_q = qp.get("justify") or qp.get("refs") or None
        justify = False
        if isinstance(justify_q, str):
            justify = justify_q.strip().lower() in {"1", "true", "yes", "y"}
        lang_override = qp.get("language") or None
        parsed = nl_parser.parse_nl(text, {})
        org_id = retrieval.resolve_org_id(parsed.org_hint or org_q, allow_create=False, full_text=text)
        lang = lang_override or parsed.language
        result = agenda.plan_agenda_next_only(
            org=org_id,
            subject=parsed.subject,
            duration_minutes=parsed.target_duration_minutes,
            language=lang,
        )
        if fmt == "nl":
            prop = result.get("proposal") or {}
            txt = textgen.agenda_to_text(
                {"agenda": prop.get("agenda"), "subject": result.get("subject")},
                language=lang,
                with_refs=justify,
            )
            return JSONResponse({
                "org_id": org_id,
                "language": lang,
                "subject": result.get("subject"),
                "text": txt,
            })
        # JSON format
        if fmt == "json":
            if justify:
                prop = result.get("proposal") or {}
                payload = textgen.agenda_to_json({"agenda": prop.get("agenda"), "subject": result.get("subject")}, language=lang, with_refs=True)
                return JSONResponse(payload)
            return JSONResponse({
                "org_id": org_id,
                "subject": result.get("subject"),
                "proposal": result.get("proposal"),
                "language": lang,
                "parsed_minutes": parsed.target_duration_minutes,
            })
        return JSONResponse(result)

    @app.post("/facts/{fact_id}/status")
    def facts_update_status(fact_id: str, req: StatusRequest):
        status = req.status.strip().lower()
        if status not in db.ALLOWED_FACT_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status '{status}'")
        db.update_fact_status(fact_id, status)
        rows = db.get_fact_rows([fact_id])
        if not rows:
            raise HTTPException(status_code=404, detail=f"Fact not found: {fact_id}")
        fact = _row_to_fact(rows[0])
        return JSONResponse({"fact_id": fact_id, "status": fact["status"], "updated_at": fact.get("updated_at")})


def main() -> None:
    if not HAVE_FASTAPI:
        print("FastAPI not installed. Install fastapi and uvicorn to run the API.")
        return
    import uvicorn

    uvicorn.run("agent.api:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":  # pragma: no cover
    main()
