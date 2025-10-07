"""
Multi-strategy fact retrieval for LangGraph agenda planning.

Combines multiple retrieval strategies to find the most relevant facts:
1. Workstream-linked facts (when workstreams detected)
2. Semantic/subject-based search
3. Urgent/overdue items (always included)
4. LLM-based ranking to prioritize
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json

from .. import db


def _row_to_dict(row) -> Dict[str, Any]:
    """Convert sqlite3.Row to dict."""
    return {k: row[k] for k in row.keys()}


class MultiStrategyRetriever:
    """
    Retrieves facts using multiple strategies and combines results.
    """
    
    def __init__(self, org_id: str):
        self.org_id = org_id
        self.conn = db.get_conn()
    
    def get_workstream_facts(
        self,
        workstream_ids: List[str],
        limit_per_ws: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Get facts linked to specific workstreams.
        
        Args:
            workstream_ids: List of workstream identifiers
            limit_per_ws: Max facts per workstream
        
        Returns:
            List of fact dicts
        """
        if not workstream_ids:
            return []
        
        facts = []
        cursor = self.conn.cursor()
        
        for ws_id in workstream_ids:
            query = """
                SELECT DISTINCT
                    f.fact_id,
                    f.fact_type,
                    f.payload,
                    f.status,
                    f.created_at,
                    f.due_iso,
                    f.org_id
                FROM facts f
                INNER JOIN workstream_facts wf ON f.fact_id = wf.fact_id
                WHERE wf.workstream_id = ?
                  AND f.org_id = ?
                ORDER BY f.created_at DESC
                LIMIT ?
            """
            
            rows = cursor.execute(query, (ws_id, self.org_id, limit_per_ws)).fetchall()
            
            for row in rows:
                fact = _row_to_dict(row)
                # Parse payload if string
                if isinstance(fact.get("payload"), str):
                    try:
                        fact["payload"] = json.loads(fact["payload"])
                    except:
                        fact["payload"] = {}
                facts.append(fact)
        
        return facts
    
    def semantic_search(
        self,
        query: str,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Search facts by subject/text similarity.
        
        For now uses simple text search. Can be enhanced with embeddings later.
        
        Args:
            query: Search query (e.g., "BYD integration")
            limit: Max results
        
        Returns:
            List of fact dicts
        """
        cursor = self.conn.cursor()
        
        # Use FTS if available, otherwise LIKE search
        # Try FTS first
        try:
            fts_query = """
                SELECT DISTINCT
                    f.fact_id,
                    f.fact_type,
                    f.payload,
                    f.status,
                    f.created_at,
                    f.due_iso,
                    f.org_id
                FROM facts_fts fts
                INNER JOIN facts f ON f.rowid = fts.rowid
                WHERE fts.facts_fts MATCH ?
                  AND f.org_id = ?
                ORDER BY f.created_at DESC
                LIMIT ?
            """
            
            rows = cursor.execute(fts_query, (query, self.org_id, limit)).fetchall()
        except Exception:
            # Fallback to LIKE search
            like_query = """
                SELECT DISTINCT
                    fact_id,
                    fact_type,
                    payload,
                    status,
                    created_at,
                    due_iso,
                    org_id
                FROM facts
                WHERE org_id = ?
                  AND (
                    payload LIKE ? OR
                    fact_type LIKE ?
                  )
                ORDER BY created_at DESC
                LIMIT ?
            """
            
            like_pattern = f"%{query}%"
            rows = cursor.execute(
                like_query,
                (self.org_id, like_pattern, like_pattern, limit)
            ).fetchall()
        
        facts = []
        for row in rows:
            fact = _row_to_dict(row)
            # Parse payload if string
            if isinstance(fact.get("payload"), str):
                try:
                    fact["payload"] = json.loads(fact["payload"])
                except:
                    fact["payload"] = {}
            facts.append(fact)
        
        return facts
    
    def get_urgent_facts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get urgent/overdue facts that should be prioritized.
        
        Criteria:
        - Overdue (due_iso < now)
        - High-priority types (blocker, decision_needed, risk)
        - Recent action items
        
        Args:
            limit: Max results
        
        Returns:
            List of fact dicts
        """
        cursor = self.conn.cursor()
        
        now_iso = datetime.utcnow().isoformat() + "Z"
        week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"
        
        query = """
            SELECT DISTINCT
                fact_id,
                fact_type,
                payload,
                status,
                created_at,
                due_iso,
                org_id
            FROM facts
            WHERE org_id = ?
              AND (
                -- Overdue items
                (due_iso IS NOT NULL AND due_iso < ?) OR
                -- High-priority types
                fact_type IN ('blocker', 'decision_needed', 'risk', 'decision') OR
                -- Recent action items
                (fact_type = 'action_item' AND created_at > ?)
              )
            ORDER BY
                CASE
                    WHEN due_iso < ? THEN 0  -- Overdue first
                    WHEN fact_type = 'blocker' THEN 1
                    WHEN fact_type = 'decision_needed' THEN 2
                    WHEN fact_type = 'risk' THEN 3
                    ELSE 4
                END,
                created_at DESC
            LIMIT ?
        """
        
        rows = cursor.execute(
            query,
            (self.org_id, now_iso, week_ago, now_iso, limit)
        ).fetchall()
        
        facts = []
        for row in rows:
            fact = _row_to_dict(row)
            # Parse payload if string
            if isinstance(fact.get("payload"), str):
                try:
                    fact["payload"] = json.loads(fact["payload"])
                except:
                    fact["payload"] = {}
            facts.append(fact)
        
        return facts
    
    def deduplicate(
        self,
        fact_lists: List[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Deduplicate facts from multiple retrieval strategies.
        
        Args:
            fact_lists: List of fact lists from different strategies
        
        Returns:
            Deduplicated list of facts
        """
        seen_ids = set()
        deduped = []
        
        for fact_list in fact_lists:
            for fact in fact_list:
                fact_id = fact.get("fact_id")
                if fact_id and fact_id not in seen_ids:
                    seen_ids.add(fact_id)
                    deduped.append(fact)
        
        return deduped
    
    def retrieve_all(
        self,
        workstream_ids: Optional[List[str]] = None,
        subject: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute all retrieval strategies and combine results.
        
        Args:
            workstream_ids: Workstream IDs (if detected)
            subject: Meeting subject for semantic search
        
        Returns:
            Dict with {
                "facts": deduped list of all facts,
                "stats": {"workstream": N, "semantic": M, "urgent": K}
            }
        """
        ws_facts = []
        if workstream_ids:
            ws_facts = self.get_workstream_facts(workstream_ids, limit_per_ws=15)
        
        subject_facts = []
        if subject and subject.strip():
            subject_facts = self.semantic_search(subject, limit=30)
        
        urgent_facts = self.get_urgent_facts(limit=20)
        
        all_facts = self.deduplicate([ws_facts, subject_facts, urgent_facts])
        
        return {
            "facts": all_facts,
            "stats": {
                "workstream": len(ws_facts),
                "semantic": len(subject_facts),
                "urgent": len(urgent_facts),
                "total": len(all_facts),
            }
        }
