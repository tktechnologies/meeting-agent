"""Test MultiStrategyRetriever directly"""
import sys
sys.path.insert(0, 'c:/Users/mateu/OneDrive/Documentos/Stok AI/meeting-agent')

from agent.retrievers.multi_strategy import MultiStrategyRetriever

print("=== Testing MultiStrategyRetriever ===\n")

org_id = "byd"
subject = "BYD"

retriever = MultiStrategyRetriever(org_id)

print("1. Testing semantic_search:")
try:
    results = retriever.semantic_search(subject, limit=30)
    print(f"   Found {len(results)} facts")
    if results:
        print(f"   First result: {results[0].get('fact_id')}")
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n2. Testing get_urgent_facts:")
try:
    results = retriever.get_urgent_facts(limit=20)
    print(f"   Found {len(results)} facts")
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n3. Testing retrieve_all:")
try:
    result = retriever.retrieve_all(workstream_ids=None, subject=subject)
    print(f"   Total facts: {len(result['facts'])}")
    print(f"   Stats: {result['stats']}")
except Exception as e:
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()
