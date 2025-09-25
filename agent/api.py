from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
    HAVE_FASTAPI = True
except Exception:  # pragma: no cover - FastAPI optional in local envs
    HAVE_FASTAPI = False

from . import agenda, db, retrieval, textgen, nl_parser


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
        prompt: Optional[str] = Field(default=None, description="Free-text request")
        format: Optional[str] = Field(default="json", description="json|nl")

    class StatusRequest(BaseModel):
        status: str = Field(description="New fact status")

    class NLPlanRequest(BaseModel):
        text: str
        org: Optional[str] = None
        duration_minutes: Optional[int] = Field(default=None, ge=5)
        language: Optional[str] = None
        context: Optional[str] = None
        format: Optional[str] = Field(default="json", description="json|nl")

    @app.post("/agenda/propose")
    def agenda_propose(req: AgendaRequest):
        org_id = retrieval.resolve_org_id(req.org)
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
                text = textgen.agenda_to_text({"agenda": agenda_obj, "subject": preview.get("subject")}, language=lang)
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

    @app.post("/agenda/plan-nl")
    def agenda_plan_nl(req: NLPlanRequest):
        parsed = nl_parser.parse_nl(req.text, {})
        org_id = retrieval.resolve_org_id(parsed.org_hint or req.org)
        minutes = req.duration_minutes or parsed.target_duration_minutes
        lang = req.language or parsed.language
        result = agenda.plan_agenda_next_only(
            org=org_id,
            subject=parsed.subject,
            company_context=req.context,
            duration_minutes=minutes,
            language=lang,
        )
        if (req.format or "json").lower() == "nl":
            text = textgen.agenda_to_text(result["proposal"], language=lang)
            return JSONResponse({"org_id": org_id, "text": text, "language": lang, "subject": result.get("subject")})
        return JSONResponse(result)

    @app.get("/health")
    def health():
        return JSONResponse({"ok": True})

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
        lang_override = qp.get("language") or None
        parsed = nl_parser.parse_nl(text, {})
        org_id = retrieval.resolve_org_id(parsed.org_hint or org_q)
        lang = lang_override or parsed.language
        result = agenda.plan_agenda_next_only(
            org=org_id,
            subject=parsed.subject,
            duration_minutes=parsed.target_duration_minutes,
            language=lang,
        )
        if fmt == "nl":
            txt = textgen.agenda_to_text(result["proposal"], language=lang)
            return JSONResponse({
                "org_id": org_id,
                "language": lang,
                "subject": result.get("subject"),
                "text": txt,
            })
        return JSONResponse({
            "org_id": org_id,
            "subject": result.get("subject"),
            "proposal": result.get("proposal"),
            "language": lang,
            "parsed_minutes": parsed.target_duration_minutes,
        })

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
