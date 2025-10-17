# Meeting Agent MongoDB Compatibility Fix

## Issues Fixed

### 1. `db_router.get_conn()` AttributeError

**Error:**
```
WARNING:agent.graph.nodes:⚠️  Could not fetch workstreams from DB: module 'agent.db_router' has no attribute 'get_conn'
```

**Root Cause:**
The `db_router.py` module only exposes `get_conn()` when using SQLite mode. When `USE_MONGODB_STORAGE=true`, the MongoDB adapter doesn't have this function because MongoDB doesn't use SQL connections.

Code in `agent/graph/nodes.py` was using raw SQL queries:
```python
conn = db.get_conn()  # ❌ Only exists in SQLite mode
cursor = conn.cursor()
rows = cursor.execute("SELECT * FROM workstreams WHERE org_id = ?", ...).fetchall()
```

**Solution:**
Use the `db_router` abstraction layer instead of raw SQL:

```python
# Before (SQLite-only):
conn = db.get_conn()
cursor = conn.cursor()
rows = cursor.execute("SELECT ... FROM workstreams WHERE org_id = ?", (org_id,)).fetchall()

# After (MongoDB + SQLite compatible):
workstream_rows = db.list_workstreams(org_id=org_id)
```

### 2. Recent Meetings Query (SQLite-only feature)

The `analyze_context` node was querying a `meetings` table that only exists in SQLite. This feature isn't supported in MongoDB yet.

**Solution:**
Wrapped the query in a `hasattr` check:
```python
if hasattr(db, 'get_conn'):
    # SQLite mode - use direct SQL query
    conn = db.get_conn()
    # ... execute query
else:
    logger.info("📝 MongoDB mode: Recent meetings analysis skipped")
```

## Changes Made

### File: `meeting-agent/agent/graph/nodes.py`

**Lines 335-352** (detect_intent node):
```python
# OLD CODE (SQLite-only):
conn = db.get_conn()
cursor = conn.cursor()
ws_query = """
    SELECT workstream_id, title, description, status, priority, owner
    FROM workstreams
    WHERE org_id = ?
    ORDER BY priority DESC, title ASC
"""
rows = cursor.execute(ws_query, (org_id,)).fetchall()

# NEW CODE (MongoDB + SQLite):
workstream_rows = db.list_workstreams(org_id=org_id)

for ws in workstream_rows:
    available_workstreams.append({
        "workstream_id": ws.get("workstream_id") or ws.get("id"),
        "title": ws.get("title", ""),
        # ... etc
    })
```

**Lines 224-250** (analyze_context node):
```python
# NEW CODE: Check if get_conn exists (SQLite mode)
if hasattr(db, 'get_conn'):
    conn = db.get_conn()
    cursor = conn.cursor()
    # ... execute meetings query
else:
    logger.info("📝 MongoDB mode: Recent meetings analysis skipped (not yet supported)")
```

## Environment Configuration

**File: `meeting-agent/.env`**
```bash
USE_MONGODB_STORAGE=true  # ✅ Now working!
```

This tells `db_router.py` to use the MongoDB adapter (`db_mongo.py`) which connects to the chat-agent's Spine API instead of local SQLite.

## Testing

### Start Services

```bash
# Terminal 1: Chat Agent (with Spine MongoDB)
cd chat-agent
npm start

# Terminal 2: Meeting Agent (with MongoDB router)
cd meeting-agent
python -m uvicorn agent.api:app --host 0.0.0.0 --port 8001 --reload
```

### Expected Output

**Meeting Agent:**
```
[db_router] Using MongoDB storage via Chat Agent API
INFO:     Application startup complete.
```

**When calling meeting agent:**
```
📚 Found X workstreams in DB for org=org_demo
   Workstreams: ['Product Roadmap', 'Sales Pipeline', ...]
```

No more `get_conn` errors! ✅

## Known Limitations

### SQLite-Only Features (Not Yet Supported in MongoDB):
1. **Recent meetings analysis** (`analyze_context` node)
   - The `meetings` table doesn't exist in MongoDB schema
   - This node gracefully skips analysis when MongoDB is enabled
   - Future: Add meetings collection to Spine schema

2. **Direct SQL queries**
   - Any code using `db.get_conn()` will fail in MongoDB mode
   - Use `db_router` abstraction functions instead

### Available Functions (MongoDB + SQLite):

See `agent/db_router.py` `__all__` list:

- ✅ `list_workstreams(org_id)` - Get all workstreams
- ✅ `get_workstream(workstream_id)` - Get specific workstream
- ✅ `upsert_workstream(...)` - Create/update workstream
- ✅ `search_facts(...)` - Search facts
- ✅ `get_recent_facts(...)` - Get recent facts
- ✅ `list_orgs()` - Get organizations
- ✅ All other Spine functions from `db_mongo.py`

## Multiple Pipelines Issue

**User Report:** "sometimes more then one pipeline in the same chat"

**Investigation:**
- Checked `chat.js` - `processMessage()` only called once ✅
- Checked `meeting-agent/index.js` - proper early return logic ✅
- Code path analysis:
  ```javascript
  if (persistTriggers.some(t => lc.includes(t))) {
    return await this.proposeAgenda(...);  // Returns early!
  }
  return await this.planAgendaNL(...);  // Only called if above didn't match
  ```

**Possible Causes:**
1. **Frontend issue**: Multiple API calls from UI
2. **Race condition**: User clicking multiple times
3. **SSE reconnection**: Multiple SSE streams for same session
4. **Async workflow**: LangGraph creating intermediate states

**Recommendation:** Test with user input and monitor backend logs to see if:
- Multiple POST requests to `/agenda/plan-nl`
- Multiple LangGraph session IDs created
- Frontend making duplicate requests

## Verification Checklist

- [x] Meeting agent starts without errors
- [x] MongoDB storage enabled (`USE_MONGODB_STORAGE=true`)
- [x] Workstreams can be fetched via `db.list_workstreams()`
- [x] No `get_conn` AttributeError
- [ ] Test workstream creation in UI
- [ ] Test meeting agenda generation
- [ ] Monitor for duplicate pipeline creation

## Next Steps

1. **Test End-to-End:**
   - Create a workstream via UI
   - Ask meeting-agent to plan a meeting
   - Verify single pipeline execution

2. **Add Meetings Support to MongoDB:**
   - Create `meetings` collection in Spine schema
   - Add `list_meetings()` function to `db_mongo.py`
   - Update `analyze_context` node to use abstraction

3. **Monitor Multiple Pipelines:**
   - Add request logging with unique IDs
   - Check for duplicate session_ids
   - Investigate frontend request patterns
