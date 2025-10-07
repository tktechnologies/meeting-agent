# Macro Planning Implementation Summary

## ✅ Implementation Complete

All deliverables from the specification have been implemented successfully.

---

## Files Modified

### Core Modules

1. **`agent/config.py`**
   - Added `USE_MACRO_PLAN` flag (default: True)
   - Added `MACRO_DEFAULT_MODE` setting (auto|strict|off)

2. **`agent/db.py`**
   - Added workstreams table schema
   - Added workstream_facts link table
   - Added account_snapshots table (optional)
   - Implemented DAO functions:
     - `upsert_workstream()` - Create/update workstream
     - `list_workstreams()` - List with filters
     - `find_workstreams()` - Search by title/tags
     - `link_facts()` - Link facts to workstream
     - `get_facts_by_workstreams()` - Get hydrated facts
     - `top_workstreams()` - Get by priority/status
     - `get_workstream()` - Get single workstream
   - Updated `_migrate_schema()` to create workstream tables

3. **`agent/retrieval.py`**
   - Added `select_workstreams()` - Select by subject or priority
   - Added `facts_for_workstreams()` - Get linked + widened facts
   - Added `rank_micro_facts()` - Score and sort facts
   - Added `search_related_facts()` - Keyword-based widening

4. **`agent/planner.py`**
   - Added `plan_agenda_from_workstreams()` - Macro planner
   - Generates sections grouped by workstream
   - Each bullet includes "why" justification from evidence
   - Returns metadata v2.0 with workstreams and refs

5. **`agent/agenda.py`**
   - Updated `plan_agenda_next_only()` to support `macro_mode` parameter
   - Implements auto/strict/off modes:
     - **auto**: Try macro, fallback to micro if no workstreams
     - **strict**: Require workstreams, return nudge if missing
     - **off**: Bypass macro layer (legacy behavior)
   - Handles subject-specific fact retrieval with draft/proposed fallback

6. **`agent/api.py`**
   - Added Pydantic models:
     - `WorkstreamIn` - Workstream creation/update
     - `LinkFactsIn` - Fact linking
   - Updated `NLPlanRequest` to include `macro` field
   - Added workstream CRUD endpoints:
     - `POST /orgs/{org_id}/workstreams` - Create/update
     - `GET /orgs/{org_id}/workstreams` - List
     - `GET /workstreams/{ws_id}` - Get single
     - `POST /workstreams/{ws_id}/link-facts` - Link facts
     - `GET /workstreams/{ws_id}/facts` - Get facts
     - `POST /orgs/{org_id}/workstreams:suggest` - Suggest from clusters
   - Updated `/agenda/plan-nl` (POST & GET) to accept `macro` param

### Scripts

7. **`scripts/seed_workstreams.py`**
   - Seeds 3 test workstreams for BYD org:
     - "Integração com API" (yellow, P2)
     - "Parceria comercial 2025" (green, P1)
     - "Adequação LGPD e compliance" (yellow, P2)
   - Links ~20-30 existing facts to each workstream

8. **`scripts/test_macro_planning.py`**
   - Comprehensive smoke tests covering:
     - Workstream selection
     - Fact retrieval and ranking
     - Agenda generation with metadata v2.0
     - All three macro modes (auto/strict/off)
     - Metadata validation

### Documentation

9. **`MACRO_PLANNING.md`**
   - Complete feature documentation
   - API reference
   - Database schema
   - Metadata v2.0 specification
   - Testing guide
   - Edge cases and constraints

10. **`MACRO_QUICK_START.md`**
    - Quick reference for developers
    - Setup instructions
    - API examples
    - Python usage examples
    - Common patterns
    - Troubleshooting

---

## Key Features Implemented

### 1. Database Layer ✅
- SQLite schema with workstreams, workstream_facts, account_snapshots
- Automatic migrations in `init_db()`
- Cosmos-compatible design with type discriminator
- Indexes for efficient queries

### 2. Retrieval Layer ✅
- Workstream selection by subject or priority
- Linked facts retrieval
- Keyword-based fact widening
- Deterministic ranking with blend score:
  - 35% status (validated > published > proposed > draft)
  - 25% urgency (due date proximity)
  - 15% recency
  - 15% evidence quality
  - 10% fact type weight

### 3. Planning Layer ✅
- Macro-first planning grouped by workstream
- Sections: Goals / Decisions / Risks / Actions per workstream
- "Why" justifications using evidence quotes (no IDs in text)
- Time allocation proportional to workstream priority and fact count
- Metadata v2.0 with:
  - `agenda_v: "2.0"`
  - `workstreams` array
  - `refs` with workstream_id
  - `nudge` for missing context
  - `health` for stale workstreams

### 4. API Layer ✅
- Full CRUD for workstreams
- Fact linking with weights
- Macro mode control (auto/strict/off)
- Backward compatible with existing endpoints

### 5. Configuration ✅
- `USE_MACRO_PLAN` flag
- `MACRO_DEFAULT_MODE` setting
- Environment variable support

---

## Testing

### Seed Data
```bash
python -m scripts.seed_workstreams
```
Creates BYD workstreams with linked facts.

### Smoke Tests
```bash
python -m scripts.test_macro_planning
```
Validates all components end-to-end.

### Manual Testing
```bash
# Start server
python -m uvicorn agent.api:app --host 127.0.0.1 --port 8000

# Test macro=auto
curl -X POST http://localhost:8000/agenda/plan-nl?macro=auto \
  -H "Content-Type: application/json" \
  -d '{"text": "reunião com a BYD", "org": "byd"}'

# Test macro=strict with subject
curl -X POST http://localhost:8000/agenda/plan-nl?macro=strict \
  -H "Content-Type: application/json" \
  -d '{"text": "focado em integração com API", "org": "byd"}'
```

---

## Acceptance Criteria Met

### ✅ 1. Seeded workstreams exist
- [x] 2-3 workstreams for BYD
- [x] Different priorities and statuses
- [x] 10-30 facts linked to each

### ✅ 2. Generic meeting request uses workstreams
```bash
POST /agenda/plan-nl?macro=auto
{"text": "faça a pauta para minha próxima reunião com a BYD"}
```
- [x] Agenda groups by top-priority workstreams
- [x] Different from other orgs (not generic)
- [x] Sections organized by workstream

### ✅ 3. Subject-focused request
```bash
POST /agenda/plan-nl?macro=strict
{"text": "reunião com a BYD focado em integração com API"}
```
- [x] Scoped to matching workstream
- [x] If vetted facts empty, includes draft/proposed for that subject
- [x] Marked by status in refs
- [x] No fallback to generic recent facts

### ✅ 4. Metadata v2.0 validation
- [x] `_metadata.agenda_v == "2.0"`
- [x] `refs[*].workstream_id` present
- [x] Every bullet has `why` justification (or empty if no evidence)
- [x] Workstreams array with id/title/status/priority

### ✅ 5. Tooltip behavior unchanged
- [x] Refs contain quotes and char_spans
- [x] No IDs exposed in user-visible text
- [x] UI can render opaque tooltips with quotes only

---

## Edge Cases Handled

### No workstreams with macro=auto
- Falls back to legacy micro planning
- Adds `_metadata.nudge = "macro_context_missing"`
- Non-blocking, agenda still generated

### No workstreams with macro=strict
- Returns empty agenda structure
- Includes nudge indicator
- Clear error message in `reason`

### Stale workstreams (14+ days)
- Status capped at yellow
- Adds `_metadata.health = "stale_macro"`
- Non-blocking warning

### Subject with no vetted facts
- Includes draft/proposed for that subject only
- Marked with status in refs
- No generic fallback

---

## Backward Compatibility

### ✅ All existing endpoints work
- `/agenda/propose` - unchanged
- `/agenda/plan-nl` without `macro` - defaults to `auto`
- `/facts/search` - unchanged
- Fact/evidence/entity APIs - unchanged

### ✅ Existing metadata preserved
- All legacy `_metadata` fields kept
- Only extended, never removed
- UI rendering unaffected

---

## Performance Considerations

### Efficient Queries
- Indexes on `(org_id, priority DESC, updated_at DESC)`
- Indexes on `(org_id, status, priority DESC)`
- Fact retrieval limited per workstream (default 20)
- Widened search capped at 10 keywords

### Caching Opportunities
- Workstream list can be cached (5 min TTL)
- Fact rankings can be cached per org (1 min TTL)
- Top workstreams query is lightweight

---

## Future Enhancements (Not in Scope)

### UI Improvements
- Side panel with workstream list
- Visual status indicators
- Drag-drop fact linking
- Workstream timeline

### Agent Features
- Auto-workstream creation from clusters
- Sentiment-based status detection
- Cross-org templates
- Dependency graphs

---

## Deliverables Checklist

- [x] 1. DB schema with workstreams tables
- [x] 2. DAO functions in `db.py`
- [x] 3. Macro retrieval in `retrieval.py`
- [x] 4. Workstream planner in `planner.py`
- [x] 5. Agenda integration in `agenda.py`
- [x] 6. API routes in `api.py`
- [x] 7. Config flags in `config.py`
- [x] 8. Pydantic models
- [x] 9. Seed script
- [x] 10. Test script
- [x] 11. Documentation
- [x] 12. Quick start guide

---

## How to Use

### For Developers

1. **Setup**
   ```bash
   python -m scripts.seed_workstreams
   python -m scripts.test_macro_planning
   ```

2. **Create workstreams**
   ```python
   from agent import db
   ws = db.upsert_workstream({
       "org_id": "my_org",
       "title": "Project Alpha",
       "status": "green",
       "priority": 1,
       "tags": ["important"]
   })
   ```

3. **Plan with macro**
   ```python
   from agent import agenda
   result = agenda.plan_agenda_next_only(
       org="my_org",
       subject="project update",
       macro_mode="auto"
   )
   ```

### For API Users

```bash
# Create workstream
curl -X POST http://localhost:8000/orgs/my_org/workstreams \
  -H "Content-Type: application/json" \
  -d '{"title": "Project Alpha", "status": "green", "priority": 1}'

# Plan agenda
curl -X POST http://localhost:8000/agenda/plan-nl?macro=auto \
  -H "Content-Type: application/json" \
  -d '{"text": "next meeting", "org": "my_org"}'
```

---

## Success Metrics

The implementation successfully:
- ✅ Reduces over-reliance on vetted micro-facts
- ✅ Prevents different prompts from collapsing to same agenda
- ✅ Grounds agendas on strategic workstreams
- ✅ Maintains all existing UI interfaces
- ✅ Preserves tooltip quote-only behavior
- ✅ Adds 1-line justifications with evidence
- ✅ Enables auto/strict/off modes for flexibility

---

**Status**: ✅ **COMPLETE AND TESTED**

All acceptance checks pass. Ready for production deployment after:
1. Running seed script in target environment
2. Verifying Cosmos compatibility (if applicable)
3. Testing with real user data
