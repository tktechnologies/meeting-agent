# Macro Planning Quick Start

Quick reference for using the workstreams (macro planning) feature.

## Setup (First Time)

```bash
# 1. Initialize database with new tables
cd meeting-agent
python -c "from agent import db; db.init_db()"

# 2. Seed test workstreams for BYD
python -m scripts.seed_workstreams

# 3. Run smoke tests
python -m scripts.test_macro_planning

# 4. Start API server
python -m uvicorn agent.api:app --host 127.0.0.1 --port 8000
```

## API Quick Reference

### Create a Workstream

```bash
curl -X POST http://localhost:8000/orgs/byd/workstreams \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Integração com API",
    "description": "Tech integration project",
    "status": "yellow",
    "priority": 2,
    "tags": ["api", "integration", "technical"]
  }'
```

### List Workstreams

```bash
# All workstreams for org
curl http://localhost:8000/orgs/byd/workstreams

# Filter by status
curl "http://localhost:8000/orgs/byd/workstreams?status=yellow"

# High priority only
curl "http://localhost:8000/orgs/byd/workstreams?min_priority=2"
```

### Link Facts to Workstream

```bash
curl -X POST http://localhost:8000/workstreams/{ws_id}/link-facts \
  -H "Content-Type: application/json" \
  -d '{
    "fact_ids": ["fact_abc123", "fact_def456"],
    "weight": 1.0
  }'
```

### Get Workstream Facts

```bash
curl http://localhost:8000/workstreams/{ws_id}/facts?limit=20
```

### Plan Agenda with Macro

```bash
# Auto mode (try macro, fallback to micro)
curl -X POST http://localhost:8000/agenda/plan-nl?macro=auto \
  -H "Content-Type: application/json" \
  -d '{
    "text": "próxima reunião com a BYD",
    "org": "byd",
    "duration_minutes": 30,
    "language": "pt-BR"
  }'

# Strict mode (must use workstreams)
curl -X POST http://localhost:8000/agenda/plan-nl?macro=strict \
  -H "Content-Type: application/json" \
  -d '{
    "text": "reunião focada em integração com API",
    "org": "byd"
  }'

# Off mode (legacy, no workstreams)
curl -X POST http://localhost:8000/agenda/plan-nl?macro=off \
  -H "Content-Type: application/json" \
  -d '{
    "text": "próxima reunião",
    "org": "byd"
  }'
```

## Python Usage

### Create Workstream

```python
from agent import db

ws = db.upsert_workstream({
    "org_id": "byd",
    "title": "Integração com API",
    "description": "Technical integration",
    "status": "yellow",
    "priority": 2,
    "tags": ["api", "integration"],
})

print(f"Created: {ws['workstream_id']}")
```

### Select Workstreams

```python
from agent import retrieval

# With subject
workstreams = retrieval.select_workstreams(
    org_id="byd",
    subject="integração com API",
    k=3
)

# Top priority
workstreams = retrieval.select_workstreams(
    org_id="byd",
    subject=None,
    k=3
)
```

### Get Facts for Workstreams

```python
facts = retrieval.facts_for_workstreams(
    org_id="byd",
    workstreams=workstreams,
    per_ws=20
)

print(f"Retrieved {len(facts)} facts")
for f in facts[:5]:
    print(f"  - {f['fact_type']}: score={f.get('score', 0):.3f}")
```

### Plan Agenda

```python
from agent import planner

proposal = planner.plan_agenda_from_workstreams(
    org_id="byd",
    workstreams=workstreams[:2],
    facts=facts,
    duration_minutes=30,
    language="pt-BR"
)

agenda = proposal["agenda"]
print(f"Agenda: {agenda['title']}")
print(f"Sections: {len(agenda['sections'])}")
print(f"Metadata version: {agenda['_metadata']['agenda_v']}")
```

### Full Flow with Agenda Module

```python
from agent import agenda

result = agenda.plan_agenda_next_only(
    org="byd",
    subject="integração com API",
    duration_minutes=30,
    language="pt-BR",
    macro_mode="auto"  # or "strict" or "off"
)

proposal = result["proposal"]
print(f"Choice: {proposal['choice']}")
print(f"Reason: {proposal['reason']}")
```

## Configuration

Set in environment or `.env` file:

```bash
# Enable/disable macro planning
USE_MACRO_PLAN=1

# Default mode when not specified in API
MACRO_DEFAULT_MODE=auto

# Other existing configs
SPINE_DB_PATH=./spine_dev.sqlite3
DEFAULT_ORG_ID=org_demo
```

## Metadata Structure

Agendas from macro planning have this structure:

```python
{
  "agenda": {
    "title": "Reunião: Integração com API",
    "minutes": 30,
    "sections": [
      {
        "title": "Integração com API",
        "minutes": 15,
        "workstream_id": "ws_abc123",
        "items": [
          {
            "heading": "Metas",
            "bullets": [
              {
                "text": "Finalizar webhook",
                "why": "(evidência: Sistema confirmou...)",
                "owner": "Tech",
                "due": "2025-11-30T00:00:00Z"
              }
            ]
          }
        ]
      }
    ],
    "_metadata": {
      "agenda_v": "2.0",
      "workstreams": [...],
      "refs": [...],
      "nudge": "macro_context_missing",  # optional
      "health": "stale_macro"  # optional
    }
  }
}
```

## Common Patterns

### Check if Workstreams Exist

```python
from agent import db

workstreams = db.list_workstreams("byd")
if not workstreams:
    print("No workstreams - create some first!")
```

### Auto-link Facts by Keywords

```python
from agent import db

# Get workstream
ws = db.get_workstream("ws_abc123")

# Find facts matching workstream tags
all_facts = db.get_recent_facts("byd", limit=100)

matching_facts = []
for fact in all_facts:
    payload = fact["payload"]
    # Simple keyword match
    text = str(payload).lower()
    if any(tag in text for tag in ws.get("tags", [])):
        matching_facts.append(fact["fact_id"])

# Link them
if matching_facts:
    db.link_facts(ws["workstream_id"], matching_facts, weight=0.8)
```

### Update Workstream Status

```python
from agent import db

ws = db.get_workstream("ws_abc123")
ws["status"] = "green"  # or "yellow" or "red"
db.upsert_workstream(ws)
```

## Troubleshooting

### No workstreams returned

```python
# Check if they exist
workstreams = db.list_workstreams("byd")
print(f"Found: {len(workstreams)}")

# Create one if needed
if not workstreams:
    ws = db.upsert_workstream({
        "org_id": "byd",
        "title": "Test Workstream",
        "status": "green",
        "priority": 1,
    })
```

### Agenda uses legacy planner instead of macro

```python
# Check config
from agent.config import USE_MACRO_PLAN, MACRO_DEFAULT_MODE
print(f"USE_MACRO_PLAN: {USE_MACRO_PLAN}")
print(f"MACRO_DEFAULT_MODE: {MACRO_DEFAULT_MODE}")

# Explicitly set macro mode
result = agenda.plan_agenda_next_only(
    org="byd",
    macro_mode="strict"  # Force macro
)
```

### No facts linked to workstream

```python
# Check links
facts = db.get_facts_by_workstreams(["ws_abc123"], limit_per_ws=50)
print(f"Linked facts: {len(facts)}")

# Link some manually
db.link_facts("ws_abc123", ["fact_1", "fact_2", "fact_3"])
```

## Testing

```bash
# Quick smoke test
python -m scripts.test_macro_planning

# Start interactive Python session
python -i -c "from agent import db, retrieval, planner, agenda; db.init_db()"

# Then experiment:
>>> workstreams = db.list_workstreams("byd")
>>> len(workstreams)
```

## See Also

- [MACRO_PLANNING.md](./MACRO_PLANNING.md) - Full documentation
- [scripts/seed_workstreams.py](./scripts/seed_workstreams.py) - Seed script
- [scripts/test_macro_planning.py](./scripts/test_macro_planning.py) - Test script
