"""
Database Router Module

Routes database calls to either SQLite (agent.db) or MongoDB (agent.db_mongo)
based on USE_MONGODB_STORAGE configuration flag.

This module provides the same interface as agent.db, allowing seamless switching
between storage backends without changing calling code.
"""
from typing import List, Dict, Any, Optional, Sequence
from .config import USE_MONGODB_STORAGE


# Import both backends
if USE_MONGODB_STORAGE:
    print('[db_router] Using MongoDB storage via Chat Agent API')
    from .db_mongo import get_adapter
    _adapter = get_adapter()
    
    # Expose all methods from MongoDB adapter
    init_db = _adapter.init_db  # No-op for MongoDB compatibility
    list_orgs = _adapter.list_orgs
    get_org = _adapter.get_org
    find_org_by_text = _adapter.find_org_by_text
    ensure_org = _adapter.ensure_org
    
    insert_or_update_fact = _adapter.insert_or_update_fact
    search_facts = _adapter.search_facts
    get_recent_facts = _adapter.get_recent_facts
    get_facts_by_ids = _adapter.get_facts_by_ids
    get_fact_rows = _adapter.get_fact_rows
    update_fact_status = _adapter.update_fact_status
    
    add_evidence = _adapter.add_evidence
    get_evidence_for_fact_ids = _adapter.get_evidence_for_fact_ids
    
    link_entities = _adapter.link_entities
    get_entities_for_fact_ids = _adapter.get_entities_for_fact_ids
    
    record_transcript = _adapter.record_transcript
    
    set_org_context = _adapter.set_org_context
    get_org_context = _adapter.get_org_context
    
    set_global_context = _adapter.set_global_context
    get_global_context = _adapter.get_global_context
    
    upsert_workstream = _adapter.upsert_workstream
    list_workstreams = _adapter.list_workstreams
    find_workstreams = _adapter.find_workstreams
    get_workstream = _adapter.get_workstream
    top_workstreams = _adapter.top_workstreams
    link_facts = _adapter.link_facts
    get_facts_by_workstreams = _adapter.get_facts_by_workstreams
    
    link_meeting_to_workstream = _adapter.link_meeting_to_workstream
    unlink_meeting_from_workstream = _adapter.unlink_meeting_from_workstream
    get_meeting_workstreams = _adapter.get_meeting_workstreams
    get_workstream_meetings = _adapter.get_workstream_meetings
    get_workstream_meeting_count = _adapter.get_workstream_meeting_count
    
    get_agenda_proposals = _adapter.get_agenda_proposals
    
    now_iso = _adapter.now_iso
    refresh_fact_fts = _adapter.refresh_fact_fts
    refresh_org_context_fts = _adapter.refresh_org_context_fts
    refresh_global_context_fts = _adapter.refresh_global_context_fts
    
else:
    print('[db_router] Using SQLite storage (local spine_dev.sqlite3)')
    # Import everything from original db module
    from . import db
    
    list_orgs = db.list_orgs
    get_org = db.get_org
    find_org_by_text = db.find_org_by_text
    ensure_org = db.ensure_org
    
    insert_or_update_fact = db.insert_or_update_fact
    search_facts = db.search_facts
    get_recent_facts = db.get_recent_facts
    get_facts_by_ids = db.get_facts_by_ids
    get_fact_rows = db.get_fact_rows
    update_fact_status = db.update_fact_status
    
    add_evidence = db.add_evidence
    get_evidence_for_fact_ids = db.get_evidence_for_fact_ids
    
    link_entities = db.link_entities
    get_entities_for_fact_ids = db.get_entities_for_fact_ids
    
    record_transcript = db.record_transcript
    
    set_org_context = db.set_org_context
    get_org_context = db.get_org_context
    
    set_global_context = db.set_global_context
    get_global_context = db.get_global_context
    
    upsert_workstream = db.upsert_workstream
    list_workstreams = db.list_workstreams
    find_workstreams = db.find_workstreams
    get_workstream = db.get_workstream
    top_workstreams = db.top_workstreams
    link_facts = db.link_facts
    get_facts_by_workstreams = db.get_facts_by_workstreams
    
    link_meeting_to_workstream = db.link_meeting_to_workstream
    unlink_meeting_from_workstream = db.unlink_meeting_from_workstream
    get_meeting_workstreams = db.get_meeting_workstreams
    get_workstream_meetings = db.get_workstream_meetings
    get_workstream_meeting_count = db.get_workstream_meeting_count
    
    get_agenda_proposals = db.get_agenda_proposals
    
    now_iso = db.now_iso
    refresh_fact_fts = db.refresh_fact_fts
    refresh_org_context_fts = db.refresh_org_context_fts
    refresh_global_context_fts = db.refresh_global_context_fts
    
    # Also expose transaction context manager and init for SQLite
    tx = db.tx
    get_conn = db.get_conn
    init_db = db.init_db


# Export all functions
__all__ = [
    'init_db',
    'list_orgs',
    'get_org',
    'find_org_by_text',
    'ensure_org',
    'insert_or_update_fact',
    'search_facts',
    'get_recent_facts',
    'get_facts_by_ids',
    'get_fact_rows',
    'update_fact_status',
    'add_evidence',
    'get_evidence_for_fact_ids',
    'link_entities',
    'get_entities_for_fact_ids',
    'record_transcript',
    'set_org_context',
    'get_org_context',
    'set_global_context',
    'get_global_context',
    'upsert_workstream',
    'list_workstreams',
    'find_workstreams',
    'get_workstream',
    'top_workstreams',
    'link_facts',
    'get_facts_by_workstreams',
    'link_meeting_to_workstream',
    'unlink_meeting_from_workstream',
    'get_meeting_workstreams',
    'get_workstream_meetings',
    'get_workstream_meeting_count',
    'get_agenda_proposals',
    'now_iso',
    'refresh_fact_fts',
    'refresh_org_context_fts',
    'refresh_global_context_fts'
]
