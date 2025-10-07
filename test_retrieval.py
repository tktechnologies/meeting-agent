import sqlite3
import json

conn = sqlite3.connect('spine_dev.sqlite3')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=== Testing Retrieval ===\n")

org_id = "byd"
subject = "BYD"

# Test 1: Check if facts exist
print("1. Total facts for org='byd':")
total = cursor.execute("SELECT COUNT(*) FROM facts WHERE org_id = ?", (org_id,)).fetchone()[0]
print(f"   Found: {total} facts\n")

# Test 2: Try semantic search with LIKE
print(f"2. Semantic search for subject='{subject}':")
try:
    rows = cursor.execute("""
        SELECT fact_id, fact_type, payload
        FROM facts
        WHERE org_id = ?
          AND payload LIKE ?
        LIMIT 5
    """, (org_id, f"%{subject}%")).fetchall()
    print(f"   Found: {len(rows)} facts")
    for row in rows:
        payload = row['payload']
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except:
                pass
        print(f"   - Type: {row['fact_type']}, Payload: {str(payload)[:80]}...")
except Exception as e:
    print(f"   Error: {e}")

print("\n3. Check workstream_facts table:")
ws_id = cursor.execute("SELECT workstream_id FROM workstreams WHERE org_id = ? LIMIT 1", (org_id,)).fetchone()
if ws_id:
    ws_id = ws_id[0]
    print(f"   Workstream ID: {ws_id}")
    wf_count = cursor.execute("SELECT COUNT(*) FROM workstream_facts WHERE workstream_id = ?", (ws_id,)).fetchone()[0]
    print(f"   Facts linked to this workstream: {wf_count}")
else:
    print("   No workstreams found")

conn.close()
