"""
Clean output of LangGraph v2.0 BYD agenda.
"""
import json
from agent.graph.graph import agenda_graph
from agent.graph.state import AgendaState

# Run workflow
initial_state: AgendaState = {
    "raw_query": "faça a pauta da minha próxima reunião com a BYD",
    "org_id": "byd",
    "step_times": {},
    "errors": [],
    "refinement_count": 0,
}

print("🚀 Running LangGraph v2.0 Workflow...\n")
final_state = agenda_graph.invoke(initial_state)

# Extract agenda
agenda_dict = final_state.get('final_agenda', {})
sections = agenda_dict.get('sections', [])

print("=" * 80)
print(f"📋 {agenda_dict.get('title', 'Agenda')}")
print(f"⏱️  Duração: {agenda_dict.get('minutes', 30)} minutos")
print("=" * 80)

for section in sections:
    print(f"\n📌 {section['title']} ({section['minutes']} min)")
    print("-" * 80)
    
    for item in section.get('items', []):
        for bullet in item.get('bullets', []):
            print(f"\n   • {bullet['text']}")
            print(f"     Por quê: {bullet['why']}")
            if bullet.get('refs'):
                print(f"     Refs: {len(bullet['refs'])} fact(s)")

# Metadata
meta = agenda_dict.get('_metadata', {})
print("\n" + "=" * 80)
print("📊 METADATA")
print("=" * 80)
print(f"Intent: {meta.get('intent')} (confidence: {meta.get('intent_confidence')})")
print(f"Quality Score: {meta.get('quality_score')}/1.0")
print(f"Facts Retrieved: {meta.get('retrieval_stats', {}).get('total', 0)}")
print(f"  - Semantic: {meta.get('retrieval_stats', {}).get('semantic', 0)}")
print(f"  - Urgent: {meta.get('retrieval_stats', {}).get('urgent', 0)}")
print(f"  - Workstream: {meta.get('retrieval_stats', {}).get('workstream', 0)}")
print(f"\n⏱️  Total Time: {sum(meta.get('step_times', {}).values()):.1f}s")
print(f"   Slowest steps:")
for step, duration in sorted(meta.get('step_times', {}).items(), key=lambda x: -x[1])[:3]:
    print(f"     - {step}: {duration:.1f}s")
