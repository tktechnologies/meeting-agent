"""
Test LangGraph v2.0 workflow directly.
"""
import json
from agent.graph.graph import agenda_graph
from agent.graph.state import AgendaState

# Initialize state for BYD meeting
initial_state: AgendaState = {
    "raw_query": "faça a pauta da minha próxima reunião com a BYD",
    "org_id": "byd",
    "step_times": {},
    "errors": [],
    "refinement_count": 0,
}

print("=== Testing LangGraph v2.0 Workflow ===")
print(f"Query: {initial_state['raw_query']}")
print(f"Org: {initial_state['org_id']}")
print("\nRunning workflow...\n")

# Run the graph
final_state = agenda_graph.invoke(initial_state)

# Print results
print("\n=== RESULTS ===\n")

print(f"Subject: {final_state.get('subject')}")
print(f"Language: {final_state.get('language')}")
print(f"Duration: {final_state.get('duration')} minutes")
print(f"Intent: {final_state.get('intent')} (confidence: {final_state.get('intent_confidence')})")

print(f"\n📊 Retrieval Stats:")
stats = final_state.get('retrieval_stats', {})
print(f"   - Total facts: {stats.get('total', 0)}")
print(f"   - Workstream: {stats.get('workstream', 0)}")
print(f"   - Semantic: {stats.get('semantic', 0)}")
print(f"   - Urgent: {stats.get('urgent', 0)}")

print(f"\n🔍 Web Search:")
web_context = final_state.get('web_search_context', '')
if web_context:
    print(f"   Triggered: YES")
    print(f"   Context length: {len(web_context)} chars")
else:
    print(f"   Triggered: NO")

print(f"\n🎯 Workstream Status:")
ws_status = final_state.get('workstream_status', '')
if ws_status:
    print(f"   {ws_status[:200]}..." if len(ws_status) > 200 else f"   {ws_status}")
else:
    print(f"   Not synthesized")

print(f"\n⭐ Quality Score: {final_state.get('quality_score', 0)}/10")
print(f"🔄 Refinements: {final_state.get('refinement_count', 0)}")

print("\n📋 Final Agenda:")
agenda = final_state.get('final_agenda', [])
print(f"   Type: {type(agenda)}")
if agenda:
    if isinstance(agenda, list) and len(agenda) > 0:
        print(f"   First item type: {type(agenda[0])}")
        if isinstance(agenda[0], dict):
            for section in agenda:
                print(f"\n   {section.get('title')} ({section.get('duration_minutes')}min)")
                print(f"   {section.get('description')}")
        else:
            # Might be serialized JSON
            print(f"   Content: {json.dumps(agenda, indent=2, ensure_ascii=False)}")
    else:
        print(f"   Content: {agenda}")
else:
    print("   No agenda generated")

print(f"\n⏱️ Step Times:")
for step, duration in final_state.get('step_times', {}).items():
    print(f"   - {step}: {duration:.2f}s")

if final_state.get('errors'):
    print(f"\n❌ Errors:")
    for error in final_state['errors']:
        print(f"   - {error}")

print("\n=== Test Complete ===")
