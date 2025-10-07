# Quick Fix: Add Debug Logging to API

This will show you exactly what's being returned from LangGraph before it gets formatted.

Add this right after line 237 in agent/api.py:

```python
if use_langgraph:
    try:
        result = _plan_with_langgraph(req.text, org_id)
        # DEBUG: Log what LangGraph returned
        logger.info(f"🔍 LangGraph result keys: {list(result.keys())}")
        logger.info(f"🔍 Proposal keys: {list(result.get('proposal', {}).keys())}")
        logger.info(f"🔍 Agenda sections: {len(result.get('proposal', {}).get('agenda', {}).get('sections', []))}")
        logger.info(f"🔍 First section: {result.get('proposal', {}).get('agenda', {}).get('sections', [{}])[0] if result.get('proposal', {}).get('agenda', {}).get('sections') else 'None'}")
```

And add this right before the return in lines 263-265:

```python
if justify:
    prop = result.get("proposal") or {}
    payload = textgen.agenda_to_json({"agenda": prop.get("agenda"), "subject": result.get("subject")}, language=lang, with_refs=True)
    # DEBUG: Check what's being returned
    logger.info(f"🔍 Final payload keys: {list(payload.keys())}")
    logger.info(f"🔍 Final sections count: {len(payload.get('sections', []))}")
    logger.info(f"🔍 Final payload: {json.dumps(payload, indent=2, ensure_ascii=False)[:500]}")
    return JSONResponse(payload)
```

This will show you exactly where the data is getting lost!
