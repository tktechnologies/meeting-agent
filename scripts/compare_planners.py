#!/usr/bin/env python3
"""
Compare Legacy vs LangGraph v2.0 agenda planning.

Usage:
    python scripts/compare_planners.py "próxima reunião com a BYD"
"""

import sys
import os
import time
import json

# Ensure we can import agent modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import config


def test_legacy(query: str, org_id: str = "org_demo"):
    """Test legacy planner."""
    print("=" * 80)
    print("🗂️  LEGACY PLANNER")
    print("=" * 80)
    
    # Force legacy
    original = config.USE_LANGGRAPH_AGENDA
    config.USE_LANGGRAPH_AGENDA = False
    
    try:
        from agent import agenda, nl_parser
        
        parsed = nl_parser.parse_nl(query, {})
        start = time.time()
        
        result = agenda.plan_agenda_next_only(
            org=org_id,
            subject=parsed.subject,
            duration_minutes=30,
            language="pt-BR",
        )
        
        elapsed = time.time() - start
        
        print(f"\n⏱️  Time: {elapsed:.2f}s")
        print(f"📊  Sections: {len(result.get('proposal', {}).get('agenda', {}).get('sections', []))}")
        
        agenda_obj = result.get('proposal', {}).get('agenda', {})
        for section in agenda_obj.get('sections', []):
            title = section.get('title', 'Untitled')
            minutes = section.get('minutes', 0)
            item_count = sum(len(item.get('bullets', [])) for item in section.get('items', []))
            print(f"  • {title}: {minutes}min, {item_count} items")
        
        print(f"\n✅ Facts used: {len(result.get('proposal', {}).get('supporting_fact_ids', []))}")
        
        # Save to file
        with open("legacy_output.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved to: legacy_output.json")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        config.USE_LANGGRAPH_AGENDA = original


def test_langgraph(query: str, org_id: str = "org_demo"):
    """Test LangGraph v2.0 planner."""
    print("\n" + "=" * 80)
    print("🚀 LANGGRAPH v2.0")
    print("=" * 80)
    
    # Check API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not set!")
        print("   Set it with: export ANTHROPIC_API_KEY='sk-ant-...'")
        return
    
    # Force LangGraph
    original = config.USE_LANGGRAPH_AGENDA
    config.USE_LANGGRAPH_AGENDA = True
    
    try:
        from agent.graph.graph import agenda_graph
        from agent.graph.state import AgendaState
        
        initial_state: AgendaState = {
            "raw_query": query,
            "org_id": org_id,
            "step_times": {},
            "errors": [],
            "refinement_count": 0,
        }
        
        print(f"\n🔄 Running workflow...")
        start = time.time()
        
        final_state = agenda_graph.invoke(initial_state)
        
        elapsed = time.time() - start
        
        print(f"\n⏱️  Total Time: {elapsed:.2f}s")
        print(f"🎯 Intent: {final_state.get('intent')} (confidence: {final_state.get('intent_confidence', 0):.2f})")
        print(f"📊 Quality Score: {final_state.get('quality_score', 0):.2f}")
        print(f"🔁 Refinements: {final_state.get('refinement_count', 0)}")
        
        # Step times
        step_times = final_state.get('step_times', {})
        print(f"\n⏱️  Step Times:")
        for step, duration in step_times.items():
            print(f"  • {step}: {duration:.2f}s")
        
        # Retrieval stats
        retrieval_stats = final_state.get('retrieval_stats', {})
        print(f"\n📥 Retrieval Stats:")
        for strategy, count in retrieval_stats.items():
            print(f"  • {strategy}: {count}")
        
        # Agenda structure
        agenda_obj = final_state.get('final_agenda', {})
        print(f"\n📋 Agenda Sections:")
        for section in agenda_obj.get('sections', []):
            title = section.get('title', 'Untitled')
            minutes = section.get('minutes', 0)
            item_count = sum(len(item.get('bullets', [])) for item in section.get('items', []))
            print(f"  • {title}: {minutes}min, {item_count} items")
        
        # Errors
        errors = final_state.get('errors', [])
        if errors:
            print(f"\n⚠️  Errors ({len(errors)}):")
            for err in errors:
                print(f"  • {err}")
        
        # Save to file
        result = {
            "proposal": {
                "agenda": final_state.get("final_agenda"),
                "choice": f"langgraph-{final_state.get('intent')}",
            },
            "metadata": {
                "version": "2.0",
                "quality_score": final_state.get('quality_score'),
                "intent": final_state.get('intent'),
                "step_times": step_times,
                "retrieval_stats": retrieval_stats,
                "errors": errors,
            }
        }
        
        with open("langgraph_output.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Saved to: langgraph_output.json")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        config.USE_LANGGRAPH_AGENDA = original


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/compare_planners.py 'query here'")
        print("Example: python scripts/compare_planners.py 'próxima reunião com a BYD'")
        sys.exit(1)
    
    query = sys.argv[1]
    org_id = sys.argv[2] if len(sys.argv) > 2 else "org_demo"
    
    print(f"📋 Query: {query}")
    print(f"🏢 Org: {org_id}\n")
    
    # Test both
    test_legacy(query, org_id)
    test_langgraph(query, org_id)
    
    print("\n" + "=" * 80)
    print("📊 COMPARISON SUMMARY")
    print("=" * 80)
    print("✅ Both outputs saved to legacy_output.json and langgraph_output.json")
    print("💡 Use `diff legacy_output.json langgraph_output.json` to compare")


if __name__ == "__main__":
    main()
