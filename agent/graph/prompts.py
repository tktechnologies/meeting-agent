"""
LLM prompt templates for agenda planning workflow.

Each node has a dedicated prompt template optimized for its specific task.
"""

def get_parse_prompt(raw_query: str, org_id: str) -> str:
    """Prompt for parsing natural language query into structured data."""
    return f"""Parse this meeting request into structured data:

User Query: "{raw_query}"
Organization: {org_id}

Extract:
1. Subject/topic - Extract company names, participant names, or project names mentioned. Examples:
   - "reunião com a BYD" → subject: "BYD"
   - "próxima reunião sobre API" → subject: "API integration"
   - "reunião com João sobre o projeto X" → subject: "Projeto X - João"
   - "meeting about Q4 planning" → subject: "Q4 planning"
   Even if the query is simple, extract WHO or WHAT is mentioned.

2. Language (pt-BR if Portuguese, en-US if English)
3. Duration in minutes (default 30 if not specified)
4. Any constraints mentioned

Return JSON ONLY (no markdown, no explanation):
{{
  "subject": "extracted topic, company, or participant name (never null unless query is completely empty)",
  "language": "pt-BR",
  "duration_minutes": 30,
  "constraints": {{"focus": "API", "max_topics": 3}}
}}"""


def get_context_analysis_prompt(recent_meetings: list, open_items: list, org_id: str) -> str:
    """Prompt for analyzing meeting patterns and context."""
    import json
    
    meetings_str = json.dumps([{
        "date": m.get("created_at"),
        "participants": m.get("participants", []),
        "topics": [s.get("title") for s in m.get("agenda", {}).get("sections", [])]
    } for m in recent_meetings], indent=2)
    
    open_items_str = json.dumps(open_items[:10], indent=2)
    
    return f"""Analyze these recent meetings and summarize the context:

Last {len(recent_meetings)} meetings for {org_id}:
{meetings_str}

Open items from previous meetings:
{open_items_str}

Provide:
1. A 2-3 sentence summary of recent meeting patterns and focus
2. Top 3 recurring themes or topics
3. Meeting frequency estimate (e.g., "weekly", "bi-weekly", "monthly", "ad-hoc")

Return JSON ONLY (no markdown):
{{
  "summary": "Organization has been focusing on...",
  "themes": ["theme1", "theme2", "theme3"],
  "frequency": "weekly"
}}"""


def get_intent_detection_prompt(
    subject: str,
    meeting_context: str,
    themes: list,
    open_items_count: int,
    language: str,
    available_workstreams: list = None
) -> str:
    """Prompt for detecting meeting intent."""
    
    # Format workstreams list if provided
    workstreams_context = ""
    if available_workstreams:
        workstreams_context = "\n\nAvailable workstreams in database:"
        for ws in available_workstreams:
            desc = ws.get("description", "")
            status_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(ws.get("status", "green"), "⚪")
            workstreams_context += f"\n- {status_emoji} \"{ws.get('title')}\" (ID: {ws.get('workstream_id')[:8]}...)"
            if desc:
                workstreams_context += f" - {desc[:100]}"
    
    workstream_instruction = ""
    if available_workstreams:
        workstream_instruction = f"""
Based on the available workstreams above, select the ones most relevant to this meeting.
Return their EXACT titles as they appear in the database.
If none are clearly relevant, return an empty list."""
    else:
        workstream_instruction = """
No workstreams are currently defined for this organization.
Return an empty workstreams list."""
    
    return f"""Determine the primary intent of this meeting:

Subject: "{subject or 'Not specified'}"
Context: {meeting_context}
Recent themes: {', '.join(themes) if themes else 'None'}
Open items from previous meetings: {open_items_count} pending{workstreams_context}

Intent types (choose ONE):
- decision_making: Need to approve/choose/finalize something (keywords: decidir, aprovar, escolher, definir)
- problem_solving: Blocked, risks, issues to resolve (keywords: resolver, destrancar, problema, bloqueio)
- planning: Roadmap, milestones, resource allocation (keywords: planejar, roadmap, próximos passos)
- alignment: Sync understanding, review progress (keywords: alinhar, sincronizar, revisar)
- status_update: Report progress, metrics (keywords: status, andamento, progresso)
- kickoff: First meeting, introductions, scope (keywords: kickoff, início, apresentação)

{workstream_instruction}

Also identify 2-3 specific focus areas (topics that should be prioritized).

Return JSON ONLY:
{{
  "intent": "decision_making",
  "confidence": 0.85,
  "reasoning": "Subject mentions 'decidir sobre integração' and there are pending decisions...",
  "workstreams": ["BYD primeiro contato", "Integração API"],
  "focus_areas": ["API authentication", "Rate limits", "Error handling"]
}}"""


def get_fact_ranking_prompt(
    facts: list,
    intent: str,
    subject: str,
    focus_areas: list,
    language: str,
    selected_workstreams: list = None
) -> str:
    """Prompt for LLM to rank facts by relevance."""
    import json
    from datetime import datetime
    
    facts_summary = []
    for f in facts[:80]:  # Increased limit since we're being smarter about ranking
        try:
            created_at = f.get("created_at", "")
            if created_at:
                age_days = (datetime.utcnow() - datetime.fromisoformat(created_at.replace("Z", "+00:00"))).days
            else:
                age_days = 999
        except:
            age_days = 999
            
        payload = f.get("payload", {})
        if isinstance(payload, str):
            import json as json_module
            try:
                payload = json_module.loads(payload)
            except:
                payload = {}
        
        facts_summary.append({
            "fact_id": f.get("fact_id"),
            "type": f.get("fact_type"),
            "text": (payload.get("text") or payload.get("subject") or "")[:120],
            "owner": payload.get("owner"),
            "status": f.get("status"),
            "age_days": age_days,
        })
    
    # Build workstream context
    workstream_context = ""
    if selected_workstreams:
        workstream_context = "\n\nSelected Workstreams (prioritize facts from these):\n"
        for ws in selected_workstreams:
            status_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(ws.get("status", "green"), "⚪")
            workstream_context += f"- {status_emoji} {ws.get('title')} (Priority: {ws.get('priority', 1)})\n"
    
    return f"""Rank these facts by relevance to the upcoming meeting:

Meeting Intent: {intent}
Subject: {subject or 'Generic meeting'}
Focus Areas: {', '.join(focus_areas) if focus_areas else 'None specified'}{workstream_context}

Facts available (total: {len(facts_summary)}):
{json.dumps(facts_summary, indent=2, ensure_ascii=False)}

Ranking criteria (in order of importance):
1. **Workstream alignment**: Facts from selected workstreams get highest priority
2. **Direct relevance**: Matches intent and focus areas
3. **Urgency**: Overdue items, pending decisions, blockers, risks
4. **Recency**: Recent facts (< 7 days) are usually more relevant
5. **Actionability**: decision/action_item > meeting_metadata > reference
6. **Status**: 'proposed' or 'draft' items need discussion

Return JSON with fact_ids ranked by relevance (most relevant first), maximum 40 facts:
{{
  "ranked_fact_ids": ["fact_abc123", "fact_def456", ...],
  "reasoning": "Prioritized facts from BYD workstream, focusing on pending decisions and recent blockers..."
}}"""


def get_macro_summary_prompt(
    workstreams: list,
    top_facts: list,
    meeting_context: str,
    language: str,
    web_search_context: str = None,
    workstream_status: str = None
) -> str:
    """Prompt for generating macro summary."""
    import json
    
    workstreams_str = json.dumps([{
        "title": ws.get("title"),
        "status": ws.get("status"),
        "priority": ws.get("priority"),
    } for ws in workstreams], indent=2) if workstreams else "No workstreams detected"
    
    facts_str = json.dumps([{
        "type": f.get("fact_type"),
        "subject": (f.get("payload", {}).get("subject") if isinstance(f.get("payload"), dict) else "")[:80],
        "status": f.get("status"),
    } for f in top_facts[:15]], indent=2)
    
    language_name = "Portuguese" if language == "pt-BR" else "English"
    
    # Add workstream status if available
    status_section = ""
    if workstream_status:
        status_section = f"\n\nCurrent Workstream Status:\n{workstream_status}\n"
    
    # Add web search context if available
    web_section = ""
    if web_search_context:
        web_section = f"\n\nExternal Context (from web search):\n{web_search_context}\n"
    
    return f"""Synthesize a macro summary for this meeting:

Workstreams/Projects:
{workstreams_str}{status_section}

Top Facts (most relevant):
{facts_str}

Meeting Context:
{meeting_context}{web_section}

Generate a 3-4 sentence summary in {language_name} covering:
1. What's the current state of these workstreams/projects?
2. What are the critical items that NEED discussion?
3. What's the primary goal of this meeting?

{" Use the workstream status analysis to be specific about current state." if workstream_status else ""}
{" If web search context is provided, incorporate relevant external information about the company/topic." if web_search_context else ""}

Write in {language_name}. Be specific and actionable.
Return ONLY the summary text (no JSON, no markdown):"""


def get_workstream_status_prompt(
    workstreams: list,
    recent_facts: list,
    language: str
) -> str:
    """Prompt for synthesizing workstream current status from recent facts."""
    import json
    
    ws_str = json.dumps([{
        "title": ws.get("title"),
        "description": ws.get("description"),
        "status": ws.get("status"),
        "priority": ws.get("priority")
    } for ws in workstreams], indent=2) if workstreams else "No workstreams detected"
    
    facts_str = json.dumps([{
        "type": f.get("fact_type"),
        "content": f.get("content", "")[:100],
        "created": f.get("created_iso"),
        "status": f.get("status"),
        "owner": f.get("payload", {}).get("owner") if isinstance(f.get("payload"), dict) else None
    } for f in recent_facts[:20]], indent=2)
    
    language_name = "Portuguese" if language == "pt-BR" else "English"
    
    return f"""Analyze these workstreams and recent facts to determine current status:

Workstreams/Projects:
{ws_str}

Recent Facts (last activities, decisions, blockers):
{facts_str}

Synthesize in {language_name} a 2-3 sentence summary covering:
1. What's the current state of each workstream? (progress, health, momentum)
2. What are the active initiatives or recent changes?
3. Are there any blockers, delays, or risks evident?

Be specific and data-driven. Use evidence from the facts.
Return ONLY the status summary text (no JSON, no markdown):"""


def get_agenda_builder_prompt(
    intent: str,
    template: dict,
    facts: list,
    macro_summary: str,
    duration_minutes: int,
    language: str,
    web_search_context: str = None
) -> str:
    """Prompt for building the agenda with LLM."""
    import json
    
    facts_for_llm = []
    for f in facts:
        payload = f.get("payload", {})
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except:
                payload = {}
        
        evidence = f.get("evidence", [])
        evidence_quote = ""
        if evidence and len(evidence) > 0:
            evidence_quote = evidence[0].get("quote", "")[:150]
        
        facts_for_llm.append({
            "fact_id": f.get("fact_id"),
            "type": f.get("fact_type"),
            "subject": payload.get("subject", ""),
            "owner": payload.get("owner"),
            "due": f.get("due_iso"),
            "status": f.get("status"),
            "evidence_quote": evidence_quote,
        })
    
    language_name = "Portuguese" if language == "pt-BR" else "English"
    
    # Add web search context if available
    web_section = ""
    if web_search_context:
        web_section = f"\n\nExternal Context (from web search - use to make agenda more specific):\n{web_search_context}\n"
    
    return f"""Build a meeting agenda for this intent: {intent}

Template structure (use these section types):
{json.dumps(template, indent=2)}

Facts to populate sections:
{json.dumps(facts_for_llm, indent=2)}

Macro Summary:
{macro_summary}{web_section}

Duration: {duration_minutes} minutes

Rules:
1. Allocate time per section (total MUST equal {duration_minutes} minutes exactly)
2. Populate bullets from facts (maximum 4 bullets per section, use most relevant)
3. Each bullet must have:
   - "text": Forward-looking action (e.g., "Decidir sobre...", "Resolver bloqueio em...", NOT "Discutimos...")
   - "why": Brief justification with evidence quote if available
   - "owner": Person responsible (if known from fact)
   - "refs": Array of fact_ids used for this bullet
4. Balance sections (no single section should exceed 40% of total time)
5. Use {language_name} for all text
6. Include "Abertura" (Opening) and "Próximos Passos" (Next Steps) sections
7. {" IMPORTANT: Use web search context to add specific, relevant discussion points about the company/topic" if web_search_context else ""}

Return JSON ONLY (agenda structure):
{{
  "title": "Meeting title in {language_name}",
  "minutes": {duration_minutes},
  "sections": [
    {{
      "title": "Section name",
      "minutes": 10,
      "items": [
        {{
          "heading": "Optional subheading",
          "bullets": [
            {{
              "text": "Action-oriented bullet",
              "why": "Justification with evidence",
              "owner": "Person name or null",
              "refs": ["fact_id1", "fact_id2"]
            }}
          ]
        }}
      ]
    }}
  ]
}}"""


def get_quality_review_prompt(
    draft_agenda: dict,
    intent: str,
    subject: str,
    open_items_count: int,
    language: str
) -> str:
    """Prompt for reviewing agenda quality."""
    import json
    
    return f"""Review this meeting agenda for quality:

Agenda:
{json.dumps(draft_agenda, indent=2)}

Meeting Context:
- Intent: {intent}
- Subject: {subject or 'Generic meeting'}
- Open items from previous meetings: {open_items_count}

Quality Criteria:
1. ✓ Sections balanced? (no section > 40% of time)
2. ✓ Time allocation adds up to total duration?
3. ✓ All critical open items addressed?
4. ✓ Bullets actionable and forward-looking? (not retrospective like "Discutimos...")
5. ✓ Has opening/context section?
6. ✓ Has next steps section?
7. ✓ Evidence/justification present in "why" fields?
8. ✓ Appropriate depth (not too generic, not too detailed)?

Return JSON ONLY:
{{
  "quality_score": 0.85,
  "issues": ["Section 'Decisões' is 15 minutes (50% of time)", "Missing 3 open items about API testing"],
  "suggestions": ["Reduce 'Decisões' to 8 minutes", "Add 'Alinhamento' section for open items"],
  "approved": true
}}

approved = true if quality_score >= 0.7, false otherwise"""
