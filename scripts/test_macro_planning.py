#!/usr/bin/env python3
"""
Smoke test for macro planning (workstreams layer).

Usage:
    python -m scripts.test_macro_planning

Tests the macro planning flow end-to-end.
"""

import sys
from pathlib import Path
import json

# Add parent to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import db, retrieval, planner, agenda


def test_macro_planning():
    """Test the macro planning flow."""
    
    print("=" * 70)
    print("MACRO PLANNING SMOKE TEST")
    print("=" * 70)
    
    # Initialize DB
    db.init_db()
    
    org_id = "byd"
    
    # Test 1: Check workstreams exist
    print("\n1. Checking workstreams...")
    workstreams = db.list_workstreams(org_id)
    
    if not workstreams:
        print("  ⚠️  No workstreams found. Run scripts.seed_workstreams first!")
        return
    
    print(f"  ✓ Found {len(workstreams)} workstreams:")
    for ws in workstreams:
        print(f"    - {ws['title']} (status={ws['status']}, priority={ws['priority']})")
    
    # Test 2: Select workstreams
    print("\n2. Testing workstream selection...")
    
    # Test with subject
    subject = "integração com API"
    selected = retrieval.select_workstreams(org_id, subject, k=3)
    print(f"  ✓ Selected {len(selected)} workstreams for subject '{subject}':")
    for ws in selected:
        print(f"    - {ws['title']}")
    
    # Test without subject (top priority)
    selected_top = retrieval.select_workstreams(org_id, None, k=3)
    print(f"  ✓ Selected {len(selected_top)} top priority workstreams:")
    for ws in selected_top:
        print(f"    - {ws['title']} (priority={ws['priority']})")
    
    # Test 3: Get facts for workstreams
    print("\n3. Testing fact retrieval for workstreams...")
    facts = retrieval.facts_for_workstreams(org_id, selected[:2], per_ws=10)
    print(f"  ✓ Retrieved {len(facts)} facts for workstreams")
    
    if facts:
        print(f"    Sample facts:")
        for f in facts[:3]:
            ftype = f.get("fact_type", "unknown")
            status = f.get("status", "unknown")
            score = f.get("score", 0)
            print(f"      - [{ftype}] status={status}, score={score:.3f}")
    
    # Test 4: Plan agenda from workstreams
    print("\n4. Testing agenda planning from workstreams...")
    proposal = planner.plan_agenda_from_workstreams(
        org_id=org_id,
        workstreams=selected[:2],
        facts=facts,
        duration_minutes=30,
        language="pt-BR",
    )
    
    agenda_obj = proposal.get("agenda", {})
    metadata = agenda_obj.get("_metadata", {})
    
    print(f"  ✓ Generated agenda:")
    print(f"    Title: {agenda_obj.get('title', 'N/A')}")
    print(f"    Duration: {agenda_obj.get('minutes', 0)} min")
    print(f"    Version: {metadata.get('agenda_v', 'N/A')}")
    print(f"    Sections: {len(agenda_obj.get('sections', []))}")
    print(f"    Refs: {len(metadata.get('refs', []))}")
    print(f"    Workstreams in metadata: {len(metadata.get('workstreams', []))}")
    
    # Show sections
    sections = agenda_obj.get("sections", [])
    if sections:
        print(f"\n    Sections:")
        for sec in sections:
            items_count = sum(len(item.get("bullets", [])) for item in sec.get("items", []))
            print(f"      - {sec.get('title', 'N/A')} ({sec.get('minutes', 0)} min, {items_count} bullets)")
    
    # Check refs have workstream_id
    refs = metadata.get("refs", [])
    refs_with_ws = [r for r in refs if r.get("workstream_id")]
    print(f"\n    Refs with workstream_id: {len(refs_with_ws)}/{len(refs)}")
    
    # Test 5: Full agenda flow with macro=auto
    print("\n5. Testing full agenda flow (macro=auto)...")
    result_auto = agenda.plan_agenda_next_only(
        org=org_id,
        subject="próxima reunião com a BYD",
        duration_minutes=30,
        language="pt-BR",
        macro_mode="auto",
    )
    
    prop_auto = result_auto.get("proposal", {})
    choice = prop_auto.get("choice", "unknown")
    print(f"  ✓ Planning choice: {choice}")
    print(f"    Sections: {len(prop_auto.get('agenda', {}).get('sections', []))}")
    
    # Test 6: Test macro=strict with specific subject
    print("\n6. Testing macro=strict with subject...")
    result_strict = agenda.plan_agenda_next_only(
        org=org_id,
        subject="focado em integração com API",
        duration_minutes=30,
        language="pt-BR",
        macro_mode="strict",
    )
    
    prop_strict = result_strict.get("proposal", {})
    choice_strict = prop_strict.get("choice", "unknown")
    print(f"  ✓ Planning choice: {choice_strict}")
    
    metadata_strict = prop_strict.get("agenda", {}).get("_metadata", {})
    nudge = metadata_strict.get("nudge")
    if nudge:
        print(f"    Nudge: {nudge}")
    
    # Test 7: Test macro=off (legacy)
    print("\n7. Testing macro=off (legacy behavior)...")
    result_off = agenda.plan_agenda_next_only(
        org=org_id,
        subject="próxima reunião",
        duration_minutes=30,
        language="pt-BR",
        macro_mode="off",
    )
    
    prop_off = result_off.get("proposal", {})
    choice_off = prop_off.get("choice", "unknown")
    print(f"  ✓ Planning choice: {choice_off}")
    print(f"    (Should use legacy planner, not macro)")
    
    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED")
    print("=" * 70)
    
    # Show sample agenda output
    print("\n📋 Sample agenda output (macro=auto):")
    print(json.dumps(prop_auto.get("agenda", {}), indent=2, ensure_ascii=False)[:1000] + "...")


def main():
    """Run smoke tests."""
    try:
        test_macro_planning()
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
