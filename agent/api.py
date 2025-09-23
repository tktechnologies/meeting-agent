from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
    HAVE_FASTAPI = True
except Exception:  # pragma: no cover - FastAPI optional in local envs
    HAVE_FASTAPI = False

from . import agenda, db, retrieval


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

    class AgendaRequest(BaseModel):
        org: Optional[str] = Field(default=None, description="Org id or text hint")
        subject: Optional[str] = Field(default=None, description="Optional meeting subject")
        meeting_id: Optional[str] = None
        transcript_id: Optional[str] = None
        duration_minutes: Optional[int] = Field(default=None, ge=5)
        language: Optional[str] = None

    class StatusRequest(BaseModel):
        status: str = Field(description="New fact status")

    @app.post("/agenda/propose")
    def agenda_propose(req: AgendaRequest):
        org_id = retrieval.resolve_org_id(req.org)
        result = agenda.propose_agenda(
            org=org_id,
            subject=req.subject,
            meeting_id=req.meeting_id,
            transcript_id=req.transcript_id,
            duration_minutes=req.duration_minutes,
            language=req.language,
        )
        snapshot = result.get("snapshot") or {}
        preview = result.get("proposal_preview") or {}
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
