"""
MongoDB Adapter for Meeting Agent

Retrieves SPINE data from MongoDB via chat-agent HTTP API instead of local SQLite.
This allows the meeting-agent to work with centralized MongoDB storage.

All functions match the signatures from db.py to ensure drop-in compatibility.
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional, Sequence
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


class Row(dict):
    """
    sqlite3.Row replacement - dict with attribute access
    Allows both row['key'] and row.key syntax
    """
    def __getattr__(self, name):
        if name in self:
            return self[name]
        raise AttributeError(f"Row has no attribute '{name}'")
    
    def keys(self):
        return super().keys()


class MongoDBAdapter:
    """Adapter to retrieve SPINE data from MongoDB via chat-agent API"""
    
    def __init__(self, chat_agent_url: str | None = None, service_token: str | None = None):
        """
        Initialize MongoDB adapter
        
        Args:
            chat_agent_url: URL of chat-agent API (default from env CHAT_AGENT_URL)
            service_token: Service authentication token (default from env SERVICE_TOKEN)
        """
        self.base_url = (chat_agent_url or os.getenv('CHAT_AGENT_URL', 'http://localhost:5000')).rstrip('/')
        self.service_token = service_token or os.getenv('SERVICE_TOKEN')
        self.headers = {'Content-Type': 'application/json'}
        if self.service_token:
            self.headers['x-service-token'] = self.service_token
    
    def _request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Synchronous HTTP request wrapper"""
        url = f'{self.base_url}{endpoint}'
        with httpx.Client(timeout=30.0) as client:
            response = client.request(method, url, headers=self.headers, **kwargs)
            return response
    
    def _get(self, endpoint: str, **kwargs) -> Any:
        """GET request helper"""
        response = self._request('GET', endpoint, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f'GET {endpoint} failed: HTTP {response.status_code}')
        return response.json()
    
    def _post(self, endpoint: str, **kwargs) -> Any:
        """POST request helper"""
        response = self._request('POST', endpoint, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f'POST {endpoint} failed: HTTP {response.status_code} - {response.text[:200]}')
        return response.json()
    
    def _patch(self, endpoint: str, **kwargs) -> Any:
        """PATCH request helper"""
        response = self._request('PATCH', endpoint, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f'PATCH {endpoint} failed: HTTP {response.status_code}')
        return response.json()
    
    def _delete(self, endpoint: str, **kwargs) -> Any:
        """DELETE request helper"""
        response = self._request('DELETE', endpoint, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f'DELETE {endpoint} failed: HTTP {response.status_code}')
        return response.json()
    
    # =========================================================================
    # ORGANIZATION METHODS
    # =========================================================================
    
    def list_orgs(self) -> List[Row]:
        """List all organizations"""
        data = self._get('/api/spine/orgs')
        return [Row({'org_id': org.get('id') or org.get('org_id'), 'name': org['name']}) for org in data]
    
    def get_org(self, org_id: str) -> Optional[Row]:
        """Get single organization by ID"""
        try:
            orgs = self.list_orgs()
            for org in orgs:
                if org['org_id'] == org_id:
                    return org
            return None
        except Exception:
            return None
    
    def find_org_by_text(self, text: str) -> Optional[Row]:
        """Find organization by name or ID (case-insensitive partial match)"""
        needle = (text or '').strip().lower()
        if not needle:
            return None
        
        orgs = self.list_orgs()
        
        for org in orgs:
            if org['org_id'].lower() == needle or org['name'].lower() == needle:
                return org
        
        matches = [org for org in orgs if needle in org['name'].lower()]
        if matches:
            return min(matches, key=lambda o: len(o['name']))
        
        return None
    
    def ensure_org(self, org_id: str, name: Optional[str] = None) -> None:
        """Ensure organization exists, create if needed"""
        existing = self.get_org(org_id)
        
        if existing:
            if name and name != existing['name']:
                self._patch(f'/api/spine/orgs/{org_id}', json={'name': name})
        else:
            self._post('/api/spine/orgs', json={'name': name or org_id})
    
    # =========================================================================
    # FACT METHODS
    # =========================================================================
    
    def insert_or_update_fact(self, fact: Dict[str, Any]) -> str:
        """Insert or update a fact"""
        self.ensure_org(fact['org_id'])
        
        fact_data = {
            'org_id': fact['org_id'],
            'fact_type': fact['fact_type'],
            'status': fact.get('status', 'proposed'),
            'payload': fact['payload'] if isinstance(fact['payload'], dict) else json.loads(fact['payload']),
            'confidence': fact.get('confidence'),
            'meeting_id': fact.get('meeting_id'),
            'transcript_id': fact.get('transcript_id'),
            'due_iso': fact.get('due_iso'),
            'due_at': fact.get('due_at')
        }
        
        fact_id = fact.get('fact_id')
        
        if fact_id:
            fact_data['fact_id'] = fact_id
            result = self._post('/api/spine/facts', json=fact_data)
            return result.get('fact_id') or fact_id
        else:
            result = self._post('/api/spine/facts', json=fact_data)
            return result['fact_id']
    
    def search_facts(
        self, 
        org_id: str, 
        query: Optional[str], 
        types: Optional[Sequence[str]] = None, 
        limit: int = 50
    ) -> List[Row]:
        """Search for facts with optional text query and type filter"""
        params = {'orgId': org_id, 'limit': str(limit)}
        
        if types:
            params['types'] = ','.join(types)
        if query:
            params['q'] = query
        
        data = self._get('/api/spine/facts/search', params=params)
        facts = data.get('facts', [])
        
        return [self._fact_to_row(f) for f in facts]
    
    def get_recent_facts(
        self, 
        org_id: str, 
        types: Optional[Sequence[str]] = None, 
        limit: int = 100
    ) -> List[Row]:
        """Get recent facts sorted by created_at DESC"""
        return self.search_facts(org_id, query=None, types=types, limit=limit)
    
    def get_facts_by_ids(self, fact_ids: List[str], org_id: str = 'org_demo') -> List[Row]:
        """Get multiple facts by their IDs"""
        if not fact_ids:
            return []
        
        # Make individual requests for each fact_id
        # (API doesn't support batch lookup yet, but search now matches fact_id exactly)
        facts = []
        for fact_id in fact_ids:
            try:
                # search_facts now matches fact_id exactly (after chat-agent fix)
                result_rows = self.search_facts(org_id, query=fact_id, limit=1)
                logger.info(f"🔍 Searching for fact_id={fact_id}, got {len(result_rows)} results")
                if result_rows:
                    # Verify it's the exact fact we're looking for
                    # Row is a dict, so access directly
                    fact_dict = result_rows[0]
                    actual_id = fact_dict.get('fact_id')
                    logger.info(f"📋 Search returned fact_id={actual_id}, expected={fact_id}")
                    if actual_id == fact_id:
                        facts.append(result_rows[0])
                        logger.info(f"✅ Found fact {fact_id}")
                    else:
                        logger.warning(f"⚠️ Search for {fact_id} returned {actual_id}, skipping")
                else:
                    logger.warning(f"⚠️ No results for fact_id={fact_id}")
            except Exception as e:
                logger.exception(f"❌ Failed to retrieve fact {fact_id}: {e}")
                continue
        
        return facts
    
    def get_fact_rows(self, fact_ids: Sequence[str]) -> List[Row]:
        """Alias for get_facts_by_ids"""
        return self.get_facts_by_ids(list(fact_ids))
    
    def update_fact_status(self, fact_id: str, status: str) -> None:
        """Update fact status"""
        self._patch(f'/api/spine/facts/{fact_id}', json={'status': status})
    
    def _fact_to_row(self, fact: Dict[str, Any]) -> Row:
        """Convert API fact to Row object matching SQLite structure"""
        payload = fact.get('payload')
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {'text': payload}
        
        return Row({
            'fact_id': fact['fact_id'],
            'org_id': fact['org_id'],
            'meeting_id': fact.get('meeting_id'),
            'transcript_id': fact.get('transcript_id'),
            'fact_type': fact['fact_type'],
            'status': fact.get('status', 'proposed'),
            'confidence': fact.get('confidence'),
            'payload': json.dumps(payload, ensure_ascii=False, sort_keys=True),
            'due_iso': fact.get('due_iso'),
            'due_at': fact.get('due_at'),
            'idempotency_key': fact.get('idempotency_key'),
            'created_at': fact.get('created_at'),
            'updated_at': fact.get('updated_at')
        })
    
    # =========================================================================
    # EVIDENCE & ENTITY METHODS (Embedded in facts)
    # =========================================================================
    
    def add_evidence(self, fact_id: str, items: Sequence[Dict[str, Any]]) -> None:
        """Add evidence to a fact (handled during fact creation)"""
        pass
    
    def get_evidence_for_fact_ids(self, fact_ids: Sequence[str]) -> Dict[str, List[Row]]:
        """Get evidence for multiple facts"""
        return {fid: [] for fid in fact_ids}
    
    def link_entities(self, fact_id: str, links: Sequence[Dict[str, Any]]) -> None:
        """Link entities to a fact (handled during fact creation)"""
        pass
    
    def get_entities_for_fact_ids(self, fact_ids: Sequence[str]) -> Dict[str, List[Row]]:
        """Get entities linked to facts"""
        return {fid: [] for fid in fact_ids}
    
    # =========================================================================
    # TRANSCRIPT METHODS
    # =========================================================================
    
    def record_transcript(self, transcript: Dict[str, Any]) -> str:
        """Record a transcript (created via bundle ingestion)"""
        return transcript.get('transcript_id', f"t_{os.urandom(8).hex()}")
    
    # =========================================================================
    # ORG CONTEXT METHODS
    # =========================================================================
    
    def set_org_context(
        self, 
        org_id: str, 
        *, 
        context_text: str, 
        language: Optional[str] = None, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Set organization context"""
        self.ensure_org(org_id)
        
        data = {'context_text': context_text}
        if language:
            data['language'] = language
        if metadata:
            data['metadata'] = metadata
        
        self._post(f'/api/spine/org-context/{org_id}', json=data)
    
    def get_org_context(self, org_id: str) -> Optional[Row]:
        """Get organization context"""
        try:
            data = self._get(f'/api/spine/org-context/{org_id}')
            return Row({
                'org_id': data['org_id'],
                'language': data.get('language'),
                'context_text': data['context_text'],
                'metadata': json.dumps(data.get('metadata')) if data.get('metadata') else None,
                'created_at': data.get('created_at'),
                'updated_at': data.get('updated_at')
            })
        except Exception:
            return None
    
    # =========================================================================
    # GLOBAL CONTEXT METHODS
    # =========================================================================
    
    def set_global_context(
        self, 
        *, 
        context_text: str, 
        language: Optional[str] = None, 
        metadata: Optional[Dict[str, Any]] = None, 
        context_id: str = 'default'
    ) -> None:
        """Set global context"""
        data = {'context_text': context_text}
        if language:
            data['language'] = language
        if metadata:
            data['metadata'] = metadata
        
        self._post(f'/api/spine/global-context/{context_id}', json=data)
    
    def get_global_context(self, context_id: str = 'default') -> Optional[Row]:
        """Get global context"""
        try:
            data = self._get(f'/api/spine/global-context/{context_id}')
            return Row({
                'context_id': data['context_id'],
                'language': data.get('language'),
                'context_text': data['context_text'],
                'metadata': json.dumps(data.get('metadata')) if data.get('metadata') else None,
                'created_at': data.get('created_at'),
                'updated_at': data.get('updated_at')
            })
        except Exception:
            return None
    
    # =========================================================================
    # WORKSTREAM METHODS
    # =========================================================================
    
    def upsert_workstream(self, ws: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a workstream"""
        workstream_id = ws.get('workstream_id', f"ws_{os.urandom(8).hex()}")
        
        data = {
            'workstream_id': workstream_id,
            'org_id': ws['org_id'],
            'title': ws['title'],
            'description': ws.get('description'),
            'status': ws.get('status', 'green'),
            'priority': ws.get('priority', 1),
            'owner': ws.get('owner'),
            'start_iso': ws.get('start_iso'),
            'target_iso': ws.get('target_iso'),
            'tags': ws.get('tags', [])
        }
        
        result = self._post('/api/spine/workstreams', json=data)
        
        return {
            'workstream_id': result['workstream_id'],
            'org_id': result['org_id'],
            'title': result['title'],
            'description': result.get('description'),
            'status': result.get('status', 'green'),
            'priority': result.get('priority', 1),
            'owner': result.get('owner'),
            'start_iso': result.get('start_iso'),
            'target_iso': result.get('target_iso'),
            'tags': result.get('tags', []),
            'created_at': result.get('created_at'),
            'updated_at': result.get('updated_at')
        }
    
    def list_workstreams(
        self, 
        org_id: str, 
        status: Optional[str] = None, 
        min_priority: int = 0
    ) -> List[Dict[str, Any]]:
        """List workstreams for an org"""
        params = {'orgId': org_id, 'minPriority': str(min_priority)}
        
        if status:
            params['status'] = status
        
        data = self._get('/api/spine/workstreams', params=params)
        return data.get('workstreams', [])
    
    def find_workstreams(self, org_id: str, subject: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Find workstreams matching subject"""
        params = {'orgId': org_id, 'subject': subject, 'limit': str(limit)}
        data = self._get('/api/spine/workstreams/find', params=params)
        return data.get('workstreams', [])
    
    def get_workstream(self, workstream_id: str) -> Optional[Dict[str, Any]]:
        """Get single workstream by ID"""
        try:
            return self._get(f'/api/spine/workstreams/{workstream_id}')
        except Exception:
            return None
    
    def top_workstreams(self, org_id: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Get top priority workstreams"""
        params = {'orgId': org_id, 'limit': str(limit)}
        data = self._get('/api/spine/workstreams/top', params=params)
        return data.get('workstreams', [])
    
    def link_facts(self, workstream_id: str, fact_ids: List[str], weight: float = 1.0) -> int:
        """Link facts to a workstream"""
        if not fact_ids:
            return 0
        
        result = self._post(
            f'/api/spine/workstreams/{workstream_id}/facts',
            json={'fact_ids': fact_ids, 'weight': weight}
        )
        
        return result.get('created', 0) + result.get('updated', 0)
    
    def get_facts_by_workstreams(
        self, 
        workstream_ids: List[str], 
        limit_per_ws: int = 20
    ) -> List[Dict[str, Any]]:
        """Get facts linked to workstreams"""
        if not workstream_ids:
            return []
        
        all_facts = []
        
        for ws_id in workstream_ids:
            try:
                data = self._get(f'/api/spine/workstreams/{ws_id}/facts', params={'limit': str(limit_per_ws)})
                facts = data.get('facts', [])
                
                for f in facts:
                    payload = f.get('payload')
                    if isinstance(payload, str):
                        try:
                            payload = json.loads(payload)
                        except Exception:
                            payload = {'text': payload}
                    
                    fact_dict = {
                        'fact_id': f['fact_id'],
                        'org_id': f['org_id'],
                        'meeting_id': f.get('meeting_id'),
                        'transcript_id': f.get('transcript_id'),
                        'fact_type': f['fact_type'],
                        'status': f.get('status', 'proposed'),
                        'confidence': f.get('confidence'),
                        'payload': payload,
                        'due_iso': f.get('due_iso'),
                        'due_at': f.get('due_at'),
                        'created_at': f.get('created_at'),
                        'updated_at': f.get('updated_at'),
                        'workstream_id': ws_id,
                        'weight': f.get('weight', 1.0),
                        'evidence': f.get('evidence', []),
                        'entities': f.get('entities', [])
                    }
                    all_facts.append(fact_dict)
            except Exception as e:
                print(f'[db_mongo] Error fetching facts for workstream {ws_id}: {e}')
                continue
        
        return all_facts
    
    # =========================================================================
    # MEETING-WORKSTREAM LINK METHODS
    # =========================================================================
    
    def link_meeting_to_workstream(self, meeting_id: str, workstream_id: str) -> bool:
        """Link a meeting to a workstream"""
        try:
            result = self._post(f'/api/spine/meetings/{meeting_id}/workstreams/{workstream_id}')
            return result.get('linked', False) or True
        except Exception:
            return False
    
    def unlink_meeting_from_workstream(self, meeting_id: str, workstream_id: str) -> bool:
        """Unlink a meeting from a workstream"""
        try:
            result = self._delete(f'/api/spine/meetings/{meeting_id}/workstreams/{workstream_id}')
            return result.get('unlinked', False)
        except Exception:
            return False
    
    def get_meeting_workstreams(self, meeting_id: str) -> List[Dict[str, Any]]:
        """Get all workstreams linked to a meeting"""
        try:
            data = self._get(f'/api/spine/meetings/{meeting_id}/workstreams')
            return data.get('workstreams', [])
        except Exception:
            return []
    
    def get_workstream_meetings(self, workstream_id: str, limit: int = 50) -> List[str]:
        """Get all meeting IDs linked to a workstream"""
        try:
            data = self._get(f'/api/spine/workstreams/{workstream_id}/meetings', params={'limit': str(limit)})
            return data.get('meeting_ids', [])
        except Exception:
            return []
    
    def get_workstream_meeting_count(self, workstream_id: str) -> int:
        """Get count of meetings linked to a workstream"""
        meeting_ids = self.get_workstream_meetings(workstream_id, limit=1000)
        return len(meeting_ids)
    
    # =========================================================================
    # AGENDA PROPOSAL METHODS
    # =========================================================================
    
    def get_agenda_proposals(self, org_id: str, limit: int = 20) -> List[Row]:
        """Get agenda proposals (facts with type='meeting_metadata' and payload.kind='agenda_proposal')"""
        facts = self.search_facts(org_id, query=None, types=['meeting_metadata'], limit=limit)
        
        proposals = []
        for fact in facts:
            payload = fact.get('payload')
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    continue
            
            if isinstance(payload, dict) and payload.get('kind') == 'agenda_proposal':
                proposals.append(fact)
        
        return proposals[:limit]
    
    # =========================================================================
    # HELPER METHODS FOR COMPATIBILITY
    # =========================================================================
    
    def init_db(self) -> None:
        """
        Compatibility method - MongoDB doesn't require database initialization.
        The chat-agent backend handles schema management.
        This is a no-op to maintain compatibility with CLI commands.
        """
        logger.info('[MongoDB] init_db called - no action required (MongoDB managed by chat-agent)')
        pass
    
    def now_iso(self) -> str:
        """Get current ISO timestamp"""
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    def refresh_fact_fts(self, fact_id: str, conn=None) -> None:
        """Compatibility method - MongoDB handles FTS automatically"""
        pass
    
    def refresh_org_context_fts(self, org_id: str, conn=None) -> None:
        """Compatibility method - MongoDB handles FTS automatically"""
        pass
    
    def refresh_global_context_fts(self, context_id: str = 'default', conn=None) -> None:
        """Compatibility method - MongoDB handles FTS automatically"""
        pass


# Singleton instance
_adapter_instance = None


def get_adapter() -> MongoDBAdapter:
    """Get or create MongoDB adapter singleton"""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = MongoDBAdapter()
    return _adapter_instance
