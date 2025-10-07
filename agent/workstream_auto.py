"""
Auto-Workstream Creation
========================
Automatically creates workstreams from fact patterns using clustering.

Strategy: 80% automatic creation via co-occurrence clustering, 20% manual review.
Auto-created workstreams get 🤖 badge for easy identification.
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from . import config
from . import db

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration from config.py
# ============================================================================

MIN_CLUSTER_SIZE = config.AUTO_WS_MIN_CLUSTER_SIZE  # Minimum facts to form a workstream
MAX_PER_ORG = config.AUTO_WS_MAX_PER_ORG  # Max auto-workstreams per org
STALE_DAYS = config.AUTO_WS_STALE_DAYS  # Don't cluster facts older than this


# ============================================================================
# Graph Building: Entity Co-Occurrence Network
# ============================================================================

def build_fact_graph(org_id: str, session) -> Dict[str, Set[str]]:
    """
    Build co-occurrence graph from facts.
    
    Returns:
        adjacency_list: {fact_id: {connected_fact_ids}}
    
    Connection logic:
    - Same entities (people, orgs, systems)
    - Same keywords (extracted from text)
    - Same agenda proposals
    - Temporal proximity (within 7 days)
    """
    logger.info(f"[workstream_auto] Building fact graph for org {org_id}")
    
    # Fetch all non-stale facts
    cutoff = datetime.utcnow() - timedelta(days=STALE_DAYS)
    rows = session.execute(
        """
        SELECT fact_id, created_at, raw_text, fact_type
        FROM facts
        WHERE org_id = :org_id
          AND created_at >= :cutoff
          AND deleted_at IS NULL
        ORDER BY created_at DESC
        """,
        {"org_id": org_id, "cutoff": cutoff}
    ).fetchall()
    
    if not rows:
        logger.info(f"[workstream_auto] No recent facts found for org {org_id}")
        return {}
    
    logger.info(f"[workstream_auto] Found {len(rows)} recent facts")
    
    # Build fact metadata
    fact_meta: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        fact_id = row["fact_id"]
        fact_meta[fact_id] = {
            "created_at": row["created_at"],
            "raw_text": row["raw_text"] or "",
            "fact_type": row["fact_type"],
            "entities": set(),
            "keywords": set(),
            "agendas": set(),
        }
    
    # Enrich with entities
    entity_rows = session.execute(
        """
        SELECT fe.fact_id, e.text
        FROM fact_entities fe
        JOIN entities e ON e.id = fe.entity_id
        WHERE fe.fact_id IN :fact_ids
        """,
        {"fact_ids": tuple(fact_meta.keys())}
    ).fetchall()
    
    for row in entity_rows:
        fact_meta[row["fact_id"]]["entities"].add(row["text"].lower())
    
    # Enrich with agenda proposals
    agenda_rows = session.execute(
        """
        SELECT fact_id, agenda_id
        FROM agenda_proposals
        WHERE fact_id IN :fact_ids
        """,
        {"fact_ids": tuple(fact_meta.keys())}
    ).fetchall()
    
    for row in agenda_rows:
        fact_meta[row["fact_id"]]["agendas"].add(row["agenda_id"])
    
    # Extract keywords from raw_text
    for fact_id, meta in fact_meta.items():
        meta["keywords"] = extract_keywords(meta["raw_text"], meta["fact_type"])
    
    # Build adjacency list
    adjacency: Dict[str, Set[str]] = defaultdict(set)
    fact_ids = list(fact_meta.keys())
    
    for i, fact1 in enumerate(fact_ids):
        for fact2 in fact_ids[i+1:]:
            if _should_connect(fact_meta[fact1], fact_meta[fact2]):
                adjacency[fact1].add(fact2)
                adjacency[fact2].add(fact1)
    
    logger.info(f"[workstream_auto] Graph built: {len(adjacency)} facts with connections")
    return dict(adjacency)


def _should_connect(meta1: Dict[str, Any], meta2: Dict[str, Any]) -> bool:
    """Check if two facts should be connected in the graph."""
    
    # Same agenda → strong connection
    if meta1["agendas"] & meta2["agendas"]:
        return True
    
    # Same entities → connection (need at least 2 overlap)
    entity_overlap = meta1["entities"] & meta2["entities"]
    if len(entity_overlap) >= 2:
        return True
    
    # Same keywords → connection (need at least 3 overlap)
    keyword_overlap = meta1["keywords"] & meta2["keywords"]
    if len(keyword_overlap) >= 3:
        return True
    
    # Temporal proximity + some overlap
    time_diff = abs((meta1["created_at"] - meta2["created_at"]).days)
    if time_diff <= 7:
        if len(entity_overlap) >= 1 or len(keyword_overlap) >= 2:
            return True
    
    return False


def extract_keywords(text: str, fact_type: str) -> Set[str]:
    """
    Extract meaningful keywords from fact text.
    
    Strategy:
    - Remove stopwords
    - Focus on nouns (capitalized words in PT-BR)
    - Include fact type specific terms
    """
    if not text:
        return set()
    
    # Stopwords (PT-BR + EN)
    stopwords = {
        "a", "o", "de", "da", "do", "e", "para", "com", "em", "no", "na",
        "the", "and", "of", "to", "in", "on", "for", "with", "at", "by",
        "que", "como", "ser", "foi", "está", "sobre", "mais", "muito",
        "this", "that", "from", "are", "was", "were", "been", "being"
    }
    
    # Clean and tokenize
    words = text.lower().split()
    keywords = set()
    
    for word in words:
        # Remove punctuation
        word = "".join(c for c in word if c.isalnum() or c == "-")
        
        # Skip short words and stopwords
        if len(word) < 4 or word in stopwords:
            continue
        
        keywords.add(word)
    
    # Add fact type as keyword
    keywords.add(fact_type.lower())
    
    return keywords


# ============================================================================
# Clustering: Find Connected Components
# ============================================================================

def find_connected_components(adjacency: Dict[str, Set[str]]) -> List[Set[str]]:
    """
    Find connected components in the fact graph using DFS.
    
    Returns:
        clusters: List of fact ID sets, each representing a potential workstream
    """
    visited = set()
    clusters = []
    
    def dfs(node: str, cluster: Set[str]):
        """Depth-first search to find all connected facts."""
        if node in visited:
            return
        visited.add(node)
        cluster.add(node)
        
        for neighbor in adjacency.get(node, []):
            dfs(neighbor, cluster)
    
    # Visit all nodes
    for node in adjacency:
        if node not in visited:
            cluster = set()
            dfs(node, cluster)
            
            # Only keep clusters above minimum size
            if len(cluster) >= MIN_CLUSTER_SIZE:
                clusters.append(cluster)
    
    # Sort by size (largest first)
    clusters.sort(key=len, reverse=True)
    
    logger.info(f"[workstream_auto] Found {len(clusters)} clusters (min size {MIN_CLUSTER_SIZE})")
    return clusters


# ============================================================================
# Workstream Generation: Create Titles and Descriptions
# ============================================================================

def generate_workstream_title(fact_ids: Set[str], session) -> str:
    """
    Generate a descriptive title for a workstream cluster.
    
    Strategy:
    - Extract most common entities
    - Extract most common keywords
    - Build title: "🤖 {entity} - {keyword theme}"
    """
    # Fetch fact metadata
    rows = session.execute(
        """
        SELECT f.fact_id, f.raw_text, f.fact_type, e.text AS entity_text
        FROM facts f
        LEFT JOIN fact_entities fe ON fe.fact_id = f.fact_id
        LEFT JOIN entities e ON e.entity_id = fe.entity_id
        WHERE f.fact_id IN :fact_ids
        """,
        {"fact_ids": tuple(fact_ids)}
    ).fetchall()
    
    # Count entities and keywords
    entities = Counter()
    keywords = Counter()
    fact_types = Counter()
    
    for row in rows:
        if row["entity_text"]:
            entities[row["entity_text"]] += 1
        
        kws = extract_keywords(row["raw_text"] or "", row["fact_type"])
        keywords.update(kws)
        
        fact_types[row["fact_type"]] += 1
    
    # Build title
    title_parts = ["🤖"]  # Badge for auto-created
    
    # Add top entity (if exists)
    if entities:
        top_entity = entities.most_common(1)[0][0]
        title_parts.append(top_entity)
    
    # Add keyword theme
    if keywords:
        # Remove fact type keywords
        for ft in fact_types:
            keywords.pop(ft.lower(), None)
        
        top_keywords = [k for k, _ in keywords.most_common(2)]
        if top_keywords:
            theme = " + ".join(top_keywords[:2])
            title_parts.append(theme.title())
    
    # Fallback: use fact type
    if len(title_parts) == 1:
        top_type = fact_types.most_common(1)[0][0]
        title_parts.append(f"Cluster de {top_type}")
    
    title = " - ".join(title_parts)
    
    # Truncate if too long
    if len(title) > 100:
        title = title[:97] + "..."
    
    return title


def generate_workstream_description(fact_ids: Set[str], session) -> str:
    """
    Generate a description summarizing the workstream cluster.
    
    Returns:
        description: "{N} fatos relacionados a {entities}. Temas: {keywords}"
    """
    rows = session.execute(
        """
        SELECT f.raw_text, f.fact_type, e.text AS entity_text
        FROM facts f
        LEFT JOIN fact_entities fe ON fe.fact_id = f.fact_id
        LEFT JOIN entities e ON e.entity_id = fe.entity_id
        WHERE f.fact_id IN :fact_ids
        """,
        {"fact_ids": tuple(fact_ids)}
    ).fetchall()
    
    entities = Counter()
    keywords = Counter()
    
    for row in rows:
        if row["entity_text"]:
            entities[row["entity_text"]] += 1
        
        kws = extract_keywords(row["raw_text"] or "", row["fact_type"])
        keywords.update(kws)
    
    # Build description
    parts = [f"{len(fact_ids)} fatos relacionados"]
    
    if entities:
        top_entities = [e for e, _ in entities.most_common(3)]
        parts.append(f"a {', '.join(top_entities)}")
    
    if keywords:
        top_keywords = [k for k, _ in keywords.most_common(5)]
        parts.append(f"Temas: {', '.join(top_keywords)}")
    
    return ". ".join(parts) + "."


# ============================================================================
# Main API: Auto-Create Workstreams
# ============================================================================

def auto_create_workstreams_for_org(org_id: str) -> Dict[str, Any]:
    """
    Auto-create workstreams for an org using clustering.
    
    Returns:
        {
            "created": [{id, title, description, fact_count}],
            "suggested": [{title, description, fact_ids}],
            "total_facts_clustered": int
        }
    
    Strategy:
    1. Build fact co-occurrence graph
    2. Find connected components (clusters)
    3. Generate titles and descriptions
    4. Create workstreams (up to MAX_PER_ORG)
    5. Link facts to workstreams
    """
    if not config.USE_AUTO_WORKSTREAMS:
        logger.info(f"[workstream_auto] Auto-workstreams disabled in config")
        return {"created": [], "suggested": [], "total_facts_clustered": 0}
    
    logger.info(f"[workstream_auto] Starting auto-creation for org {org_id}")
    
    # Build graph
    adjacency = build_fact_graph(org_id, db.get_session())
    
    if not adjacency:
        return {"created": [], "suggested": [], "total_facts_clustered": 0}
    
    # Find clusters
    clusters = find_connected_components(adjacency)
    
    if not clusters:
        return {"created": [], "suggested": [], "total_facts_clustered": 0}
    
    # Generate workstreams
    created = []
    suggested = []
    total_facts = 0
    
    session = db.get_session()
    
    for i, fact_ids in enumerate(clusters):
        total_facts += len(fact_ids)
        
        # Generate metadata
        title = generate_workstream_title(fact_ids, session)
        description = generate_workstream_description(fact_ids, session)
        
        # Create if within limit
        if i < MAX_PER_ORG:
            # Generate workstream ID
            import uuid
            ws_id = f"ws_{uuid.uuid4().hex[:12]}"
            
            # Insert workstream
            session.execute(
                """
                INSERT INTO workstreams (workstream_id, org_id, title, description, status, priority, created_at, updated_at)
                VALUES (:ws_id, :org_id, :title, :description, 'green', 1, :now, :now)
                """,
                {
                    "ws_id": ws_id,
                    "org_id": org_id,
                    "title": title,
                    "description": description,
                    "now": datetime.utcnow()
                }
            )
            
            # Link facts
            for fact_id in fact_ids:
                session.execute(
                    """
                    INSERT INTO workstream_facts (workstream_id, fact_id, created_at)
                    VALUES (:ws_id, :fact_id, :now)
                    ON CONFLICT DO NOTHING
                    """,
                    {"ws_id": ws_id, "fact_id": fact_id, "now": datetime.utcnow()}
                )
            
            session.commit()
            
            created.append({
                "id": ws_id,
                "title": title,
                "description": description,
                "fact_count": len(fact_ids)
            })
            
            logger.info(f"[workstream_auto] Created workstream {ws_id}: {title} ({len(fact_ids)} facts)")
        
        else:
            # Beyond limit → suggest for manual review
            suggested.append({
                "title": title,
                "description": description,
                "fact_ids": list(fact_ids)
            })
    
    logger.info(
        f"[workstream_auto] Created {len(created)} workstreams, "
        f"{len(suggested)} suggested, {total_facts} facts clustered"
    )
    
    return {
        "created": created,
        "suggested": suggested,
        "total_facts_clustered": total_facts
    }


def get_suggested_workstreams(org_id: str) -> List[Dict[str, Any]]:
    """
    Get suggested workstreams without creating them.
    
    Returns:
        suggested: [{title, description, fact_ids, fact_count}]
    """
    adjacency = build_fact_graph(org_id, db.get_session())
    
    if not adjacency:
        return []
    
    clusters = find_connected_components(adjacency)
    
    if not clusters:
        return []
    
    session = db.get_session()
    suggested = []
    
    for fact_ids in clusters:
        title = generate_workstream_title(fact_ids, session)
        description = generate_workstream_description(fact_ids, session)
        
        suggested.append({
            "title": title,
            "description": description,
            "fact_ids": list(fact_ids),
            "fact_count": len(fact_ids)
        })
    
    return suggested
