#!/usr/bin/env python3
"""
Seed script to create workstreams and link facts for testing the macro planning layer.

Usage:
    python -m scripts.seed_workstreams

Creates workstreams for BYD and links relevant facts.
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import db_router as db


def seed_byd_workstreams():
    """Create workstreams for BYD org and link existing facts."""
    
    # Ensure BYD org exists
    org_id = "byd"
    db.ensure_org(org_id, "BYD")
    
    print(f"Seeding workstreams for org: {org_id}")
    
    # Workstream 1: Integração com API
    ws1 = {
        "org_id": org_id,
        "title": "Integração com API",
        "description": "Integração técnica entre sistemas BYD e parceiros via API REST",
        "status": "yellow",  # In progress with some blockers
        "priority": 2,
        "owner": "Equipe Técnica",
        "start_iso": "2025-09-01T00:00:00Z",
        "target_iso": "2025-11-30T00:00:00Z",
        "tags": ["api", "integração", "técnico", "bms", "webhook"],
    }
    
    result1 = db.upsert_workstream(ws1)
    ws1_id = result1["workstream_id"]
    print(f"✓ Created workstream: {ws1['title']} ({ws1_id})")
    
    # Workstream 2: Parceria comercial 2025
    ws2 = {
        "org_id": org_id,
        "title": "Parceria comercial 2025",
        "description": "Desenvolvimento da parceria estratégica e comercial para 2025",
        "status": "green",
        "priority": 1,
        "owner": "Comercial",
        "start_iso": "2025-01-15T00:00:00Z",
        "target_iso": "2025-12-31T00:00:00Z",
        "tags": ["comercial", "parceria", "estratégia", "2025"],
    }
    
    result2 = db.upsert_workstream(ws2)
    ws2_id = result2["workstream_id"]
    print(f"✓ Created workstream: {ws2['title']} ({ws2_id})")
    
    # Workstream 3: Adequação LGPD
    ws3 = {
        "org_id": org_id,
        "title": "Adequação LGPD e compliance",
        "description": "Garantir conformidade com LGPD e padrões de segurança",
        "status": "yellow",
        "priority": 2,
        "owner": "Legal/TI",
        "start_iso": "2025-08-01T00:00:00Z",
        "target_iso": "2025-10-31T00:00:00Z",
        "tags": ["lgpd", "compliance", "segurança", "legal"],
    }
    
    result3 = db.upsert_workstream(ws3)
    ws3_id = result3["workstream_id"]
    print(f"✓ Created workstream: {ws3['title']} ({ws3_id})")
    
    # Find and link relevant facts to each workstream
    print("\nLinking facts to workstreams...")
    
    # Get recent BYD facts
    all_facts = db.get_recent_facts(org_id, limit=100)
    
    # Simple keyword matching to link facts
    api_keywords = ["api", "integra", "webhook", "endpoint", "bms", "técnic", "sistem"]
    comercial_keywords = ["parceria", "comercial", "negó", "contrat", "venda", "2025"]
    lgpd_keywords = ["lgpd", "compliance", "seguran", "legal", "dado", "privacidad"]
    
    def matches_keywords(fact, keywords):
        """Check if fact payload matches any keywords."""
        payload = fact["payload"]
        if isinstance(payload, str):
            import json
            try:
                payload = json.loads(payload)
            except Exception:
                return False
        
        # Check in common text fields
        text = ""
        for key in ("subject", "title", "text", "summary", "description"):
            val = payload.get(key)
            if isinstance(val, str):
                text += " " + val.lower()
        
        return any(kw in text for kw in keywords)
    
    ws1_facts = [f["fact_id"] for f in all_facts if matches_keywords(f, api_keywords)]
    ws2_facts = [f["fact_id"] for f in all_facts if matches_keywords(f, comercial_keywords)]
    ws3_facts = [f["fact_id"] for f in all_facts if matches_keywords(f, lgpd_keywords)]
    
    # Link facts with different weights
    if ws1_facts:
        count1 = db.link_facts(ws1_id, ws1_facts[:30], weight=1.0)
        print(f"  ✓ Linked {count1} facts to '{ws1['title']}'")
    
    if ws2_facts:
        count2 = db.link_facts(ws2_id, ws2_facts[:30], weight=1.0)
        print(f"  ✓ Linked {count2} facts to '{ws2['title']}'")
    
    if ws3_facts:
        count3 = db.link_facts(ws3_id, ws3_facts[:20], weight=0.9)
        print(f"  ✓ Linked {count3} facts to '{ws3['title']}'")
    
    print(f"\n✅ Seeding complete!")
    print(f"\nTo test, call:")
    print(f'  POST /agenda/plan-nl?macro=auto')
    print(f'    {{"text": "faça a pauta para minha próxima reunião com a BYD", "org": "byd"}}')
    print(f'\n  POST /agenda/plan-nl?macro=strict')
    print(f'    {{"text": "reunião com a BYD focado em integração com API", "org": "byd"}}')


def main():
    """Initialize DB and seed workstreams."""
    db.init_db()
    seed_byd_workstreams()


if __name__ == "__main__":
    main()
