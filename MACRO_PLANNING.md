# Macro Planning Layer (Workstreams)

This document describes the macro-context layer added to the meeting-agent to improve agenda planning through workstreams.

## Overview

The macro planning layer adds a strategic context layer on top of the existing micro-facts. Instead of relying solely on individual facts, the planner now organizes agendas around **workstreams** - macro-level initiatives or focus areas that group related facts.

### Flow

```
MACRO (workstreams) → MICRO (linked facts) → AGENDA
```

1. **Select workstreams**: Find 1-3 relevant workstreams by subject or priority
2. **Retrieve facts**: Get linked facts + widen search with workstream keywords
3. **Plan agenda**: Group sections by workstream with Goals/Decisions/Risks/Actions
4. **Add justifications**: Each bullet includes "why" grounded in evidence quotes

## Database Schema

### New Tables

**workstreams**
- `workstream_id` (PK): Unique ID
- `org_id`: Organization
- `title`: Workstream name (e.g., "Integração com API")
- `description`: Optional detailed description
- `status`: "green" | "yellow" | "red"
- `priority`: Integer (higher = more important)
- `owner`: Optional owner/team
- `start_iso`, `target_iso`: Optional ISO dates
- `tags`: JSON array of keywords
- `created_at`, `updated_at`: Timestamps

**workstream_facts**
- `workstream_id` (FK)
- `fact_id` (FK)
- `weight`: 0.0-1.0 (confidence/relevance)
- `created_at`

**account_snapshots** (optional)
- `snapshot_id` (PK)
- `org_id`
- `as_of_iso`: Snapshot date
- `summary`, `top_workstreams`, `metrics`: JSON

### SQLite vs Cosmos

- **Dev (SQLite)**: Regular tables as shown above
- **Prod (Cosmos)**: Documents with `type` discriminator:
  - `type: "workstream"`
  - `type: "workstream_fact"`
  - `type: "account_snapshot"`
  - Partitioned by `org_id`

## API Endpoints

### Workstream CRUD

**Create/Update Workstream**
```
POST /orgs/{org_id}/workstreams
{
  "title": "Integração com API",
  "description": "...",
  "status": "yellow",
  "priority": 2,
  "owner": "Tech Team",
  "tags": ["api", "integration"]
}
```

**List Workstreams**
```
GET /orgs/{org_id}/workstreams?status=yellow&min_priority=1
```

**Get Workstream**
```
GET /workstreams/{workstream_id}
```

**Link Facts to Workstream**
```
POST /workstreams/{workstream_id}/link-facts
{
  "fact_ids": ["fact_123", "fact_456"],
  "weight": 1.0
}
```

**Get Workstream Facts**
```
GET /workstreams/{workstream_id}/facts?limit=50
```

**Suggest Workstreams** (optional)
```
POST /orgs/{org_id}/workstreams:suggest?limit=5
```
Returns suggested workstream titles from fact clusters.

### Planning with Macro

**Plan with Macro Mode**
```
POST /agenda/plan-nl?macro=auto
{
  "text": "faça a pauta para minha próxima reunião com a BYD",
  "org": "byd"
}
```

**Macro Modes**:
- `auto` (default): Try macro; fallback to micro if no workstreams
- `strict`: MUST use workstreams; return nudge if none exist
- `off`: Bypass macro (legacy behavior)

## Configuration

Environment variables in `config.py`:

```bash
USE_MACRO_PLAN=1          # Enable macro planning (default: True)
MACRO_DEFAULT_MODE=auto   # auto|strict|off (default: auto)
```

## Metadata v2.0

Agendas from macro planning include enhanced metadata:

```json
{
  "agenda": {
    "title": "Reunião: Integração com API",
    "minutes": 30,
    "sections": [...],
    "_metadata": {
      "agenda_v": "2.0",
      "workstreams": [
        {
          "workstream_id": "ws_abc123",
          "title": "Integração com API",
          "status": "yellow",
          "priority": 2
        }
      ],
      "refs": [
        {
          "fact_id": "fact_123",
          "type": "decision",
          "status": "validated",
          "quote": "Integração BMS envia 2 arquivos...",
          "char_span": [10234, 10321],
          "workstream_id": "ws_abc123"
        }
      ],
      "nudge": "macro_context_missing",  // Optional
      "health": "stale_macro"             // Optional (if WS not updated in 14+ days)
    }
  }
}
```

### Section Structure

Each section is grouped by workstream with subsections:

```json
{
  "title": "Integração com API",
  "minutes": 15,
  "workstream_id": "ws_abc123",
  "items": [
    {
      "heading": "Metas",
      "bullets": [
        {
          "text": "Finalizar integração webhook",
          "why": "(evidência: Sistema BMS confirmou...)",
          "owner": "Tech Team",
          "due": "2025-11-30T00:00:00Z"
        }
      ]
    },
    {
      "heading": "Decisões",
      "bullets": [...]
    },
    {
      "heading": "Riscos",
      "bullets": [...]
    },
    {
      "heading": "Ações",
      "bullets": [...]
    }
  ]
}
```

## Retrieval Functions

### `select_workstreams(org_id, subject, k=3)`
Select top k workstreams:
1. If subject: exact match in title/tags
2. Otherwise: top by priority/status/recency

### `facts_for_workstreams(org_id, workstreams, per_ws=20)`
Get facts for workstreams:
1. Linked facts (direct associations)
2. Widened facts (keyword search using WS tags)
3. Rank and deduplicate

### `rank_micro_facts(items)`
Score and sort facts by:
- Status (validated > published > proposed > draft)
- Urgency (due date)
- Recency
- Evidence quality (quote count)
- Type weight (decision > risk > action > etc)

## Important Constraints

### UI Compatibility

✅ **Preserved**:
- Existing `_metadata` fields (not removed)
- Tooltip behavior (opaque, quote-only, no IDs)
- Refs with quotes and char_spans
- Section/items structure

✅ **Extended**:
- `_metadata.agenda_v = "2.0"`
- `_metadata.workstreams` array
- `refs[*].workstream_id` for grouping
- `nudge` and `health` indicators

### Subject Handling

**When subject provided**:
- Select workstreams matching subject
- If vetted facts empty, include draft/proposed **for that subject only**
- Mark with `status` in refs; do NOT fall back to generic recent

**No subject**:
- Select top priority workstreams
- Use broader fact retrieval

### Deterministic Ranking

All ranking uses consistent tie-breakers:
- Primary: calculated score
- Secondary: `created_at` (newest first)
- Tertiary: `fact_id` (alphabetical)

## Testing

### Seed Data

```bash
cd meeting-agent
python -m scripts.seed_workstreams
```

Creates:
- BYD workstreams: "Integração com API", "Parceria comercial 2025", "Adequação LGPD"
- Links ~20-30 existing facts to each

### Smoke Tests

```bash
python -m scripts.test_macro_planning
```

Validates:
1. Workstream selection
2. Fact retrieval and ranking
3. Agenda generation with metadata v2.0
4. All three macro modes (auto/strict/off)

### Acceptance Tests

**Test 1: Generic meeting (macro=auto)**
```bash
curl -X POST http://localhost:8000/agenda/plan-nl?macro=auto \
  -H "Content-Type: application/json" \
  -d '{"text": "faça a pauta para minha próxima reunião com a BYD", "org": "byd"}'
```
Expected: Agenda groups by top-priority workstreams, not identical to other orgs.

**Test 2: Subject-specific (macro=strict)**
```bash
curl -X POST http://localhost:8000/agenda/plan-nl?macro=strict \
  -H "Content-Type: application/json" \
  -d '{"text": "reunião com a BYD focado em integração com API", "org": "byd"}'
```
Expected: 
- Agenda scoped to "Integração com API" workstream
- If vetted facts empty, includes draft/proposed for that subject (marked by status)
- Bullets include `why` justifications with quotes

**Test 3: Recent facts query**
```bash
curl "http://localhost:8000/facts/search?org=byd&q=integração"
```
Expected: Facts may group by workstream in future UI; refs include `workstream_id`.

**Test 4: Verify metadata**
Check response includes:
- `_metadata.agenda_v == "2.0"`
- `_metadata.workstreams` with IDs/titles/status
- `refs[*].workstream_id` present
- Every bullet has `why` line (or empty if no evidence)

**Test 5: Tooltip unchanged**
In UI, hover over bullet → opaque tooltip shows quote only, no IDs.

## Edge Cases

### No Workstreams (macro=auto)
- Falls back to legacy micro planning
- Adds `_metadata.nudge = "macro_context_missing"`
- UI can show "Criar macro" button

### No Workstreams (macro=strict)
- Returns empty agenda structure
- `nudge = "macro_context_missing"`
- Reason: "No workstreams available; macro=strict requires workstreams"

### Stale Workstreams
- If not updated in 14+ days: status capped at `yellow`
- Adds `_metadata.health = "stale_macro"`
- Non-blocking; agenda still generated

### Subject with No Vetted Facts
- Include draft/proposed **for that subject**
- Mark with `status: "draft"` or `"proposed"` in refs
- Do NOT revert to generic recent facts

## Migration Notes

### Existing Code

All legacy endpoints continue to work:
- `/agenda/propose`
- `/agenda/plan-nl` (without `macro` param defaults to `auto`)
- Existing fact/evidence/entity APIs unchanged

### Cosmos Migration

For production Cosmos deployments:

1. Add `type` field to new documents:
   ```json
   {
     "type": "workstream",
     "workstream_id": "...",
     "org_id": "...",
     ...
   }
   ```

2. Partition by `org_id`

3. Update queries to filter `type IN ('workstream', 'workstream_fact', 'account_snapshot')`

4. Index on `(org_id, priority, status, updated_at)` for fast workstream selection

## Future Enhancements

### UI Enhancements (not in scope)
- Side panel with workstream list
- Drag-drop facts to workstreams
- Visual health indicators (green/yellow/red)
- Workstream timeline view

### Agent Enhancements
- Auto-create workstreams from fact clusters
- Sentiment analysis for status detection
- Cross-org workstream templates
- Workstream dependencies graph

## Logging

Key log points (INFO level):
- Selected workstream titles and count
- Fact counts by type (decision=X, risk=Y, ...)
- Planning mode chosen (macro vs legacy)
- Nudge/health indicators added

Example:
```
INFO: Selected 2 workstreams: ['Integração com API', 'Parceria comercial 2025']
INFO: Retrieved 45 facts (decision=12, risk=8, action_item=15, ...)
INFO: Planning mode=macro, choice=macro
```

## Support

For issues or questions:
1. Check logs for INFO/ERROR entries
2. Run `scripts.test_macro_planning.py` to validate setup
3. Verify workstreams exist: `GET /orgs/{org_id}/workstreams`
4. Test with `macro=off` to isolate macro-specific issues

---

**Implementation Status**: ✅ Complete

All deliverables implemented:
- ✅ DB schema + migrations
- ✅ DAO functions
- ✅ Macro retrieval layer
- ✅ Workstream planner with `why` justifications
- ✅ Agenda integration (auto/strict/off)
- ✅ FastAPI CRUD endpoints
- ✅ Config flags
- ✅ Pydantic models
- ✅ Seed + test scripts
