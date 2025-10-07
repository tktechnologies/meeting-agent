# Production Migration Guide

Guide for deploying the macro planning (workstreams) feature to production.

---

## Pre-Migration Checklist

- [ ] Backup production database
- [ ] Review environment configuration
- [ ] Test in staging environment
- [ ] Verify Cosmos DB compatibility (if using Cosmos)
- [ ] Plan rollback strategy

---

## Migration Steps

### 1. Database Migration

#### SQLite (Development/Staging)

The migration runs automatically on first startup:

```python
from agent import db
db.init_db()
```

This creates:
- `workstreams` table
- `workstream_facts` table
- `account_snapshots` table
- Required indexes

**Rollback**: Drop tables if needed:
```sql
DROP TABLE IF EXISTS account_snapshots;
DROP TABLE IF EXISTS workstream_facts;
DROP TABLE IF EXISTS workstreams;
```

#### Cosmos DB (Production)

For Cosmos deployments, no schema migration needed. Documents are schema-free but should include `type` discriminator:

```json
// Workstream document
{
  "type": "workstream",
  "workstream_id": "ws_abc123",
  "org_id": "byd",
  "title": "Integration Project",
  "status": "yellow",
  "priority": 2,
  "tags": ["api", "integration"],
  "created_at": "2025-10-03T10:00:00Z",
  "updated_at": "2025-10-03T10:00:00Z"
}

// Workstream-fact link document
{
  "type": "workstream_fact",
  "workstream_id": "ws_abc123",
  "fact_id": "fact_def456",
  "weight": 1.0,
  "created_at": "2025-10-03T10:00:00Z"
}
```

**Container settings**:
- Partition key: `/org_id`
- Indexing: Include all fields (default)
- Additional index for workstreams: `(org_id, priority DESC, status, updated_at DESC)`

### 2. Environment Configuration

Add to production environment variables:

```bash
# Enable macro planning (default: true)
USE_MACRO_PLAN=1

# Default mode: auto | strict | off
MACRO_DEFAULT_MODE=auto

# Existing configs remain unchanged
SPINE_DB_PATH=/path/to/db
DEFAULT_ORG_ID=org_demo
```

**Azure App Service**: Add to Configuration > Application settings

**Docker**: Add to `.env` or `docker-compose.yml`

### 3. Code Deployment

Deploy updated files:
- `agent/config.py`
- `agent/db.py`
- `agent/retrieval.py`
- `agent/planner.py`
- `agent/agenda.py`
- `agent/api.py`

**No breaking changes** - all existing endpoints continue to work.

### 4. Verify Deployment

After deployment, verify:

```bash
# Check health endpoint
curl https://your-api.azurewebsites.net/health

# Test workstream creation
curl -X POST https://your-api.azurewebsites.net/orgs/test_org/workstreams \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Workstream",
    "status": "green",
    "priority": 1
  }'

# Test agenda planning
curl -X POST https://your-api.azurewebsites.net/agenda/plan-nl?macro=auto \
  -H "Content-Type: application/json" \
  -d '{
    "text": "test meeting",
    "org": "test_org"
  }'
```

### 5. Seed Initial Workstreams

For each production org, seed initial workstreams:

**Option A: Manual via API**
```bash
curl -X POST https://your-api.azurewebsites.net/orgs/{org}/workstreams \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Q4 Strategic Initiatives",
    "description": "Key projects for Q4 2025",
    "status": "green",
    "priority": 1,
    "tags": ["strategy", "q4"]
  }'
```

**Option B: Python script** (run on server)
```python
from agent import db

orgs = ["org1", "org2", "org3"]

for org_id in orgs:
    ws = db.upsert_workstream({
        "org_id": org_id,
        "title": "Strategic Initiatives",
        "status": "green",
        "priority": 1,
        "tags": ["strategy"]
    })
    print(f"Created workstream for {org_id}: {ws['workstream_id']}")
```

### 6. Link Existing Facts (Optional)

Use the suggest endpoint to auto-link facts:

```bash
curl -X POST https://your-api.azurewebsites.net/orgs/{org}/workstreams:suggest?limit=5
```

Or link manually:
```python
from agent import db

# Get workstream
ws = db.get_workstream("ws_abc123")

# Find relevant facts
facts = db.get_recent_facts(ws["org_id"], limit=100)

# Link based on keywords
to_link = []
for fact in facts:
    # Simple keyword matching logic
    # ... (see seed_workstreams.py for example)
    pass

if to_link:
    db.link_facts(ws["workstream_id"], to_link, weight=1.0)
```

---

## Rollback Plan

If issues arise, rollback in this order:

### 1. Disable Macro Planning

Set environment variable:
```bash
USE_MACRO_PLAN=0
```

Or force legacy mode via API:
```bash
# All requests will use legacy planner
?macro=off
```

### 2. Revert Code (if needed)

Redeploy previous version. The new database tables/documents don't affect existing functionality.

### 3. Database Rollback (SQLite only)

If tables need to be removed:
```sql
DROP TABLE IF EXISTS account_snapshots;
DROP TABLE IF EXISTS workstream_facts;
DROP TABLE IF EXISTS workstreams;
```

For Cosmos DB, no action needed - just stop creating new workstream documents.

---

## Monitoring

### Key Metrics to Track

1. **Workstream coverage**
   - How many orgs have workstreams?
   - Average workstreams per org
   - Average facts per workstream

2. **Planning mode usage**
   - % of requests using macro vs legacy
   - % of macro=strict vs macro=auto
   - Nudge frequency (missing workstreams)

3. **Performance**
   - Agenda generation time (macro vs legacy)
   - Workstream query latency
   - Fact retrieval time

4. **Quality**
   - User feedback on macro-generated agendas
   - Stale workstream frequency
   - Empty workstream frequency

### Logging

Monitor logs for:
```
INFO: Selected 2 workstreams: [...]
INFO: Planning mode=macro, choice=macro
WARNING: No workstreams found for org_xyz
WARNING: Workstream ws_abc123 stale (14+ days)
```

### Alerts

Set up alerts for:
- High rate of "no workstreams found" (>50%)
- Slow agenda generation (>5s)
- High error rate on workstream endpoints

---

## Gradual Rollout Strategy

### Phase 1: Soft Launch (Week 1)
- Deploy with `MACRO_DEFAULT_MODE=off`
- Enable macro for select test orgs only
- Monitor performance and errors

### Phase 2: Opt-In (Week 2-3)
- Set `MACRO_DEFAULT_MODE=auto`
- Workstreams available but not required
- Fallback to legacy if no workstreams exist

### Phase 3: Full Rollout (Week 4+)
- Encourage workstream creation for all orgs
- Monitor adoption metrics
- Collect user feedback

### Phase 4: Optimization (Month 2+)
- Use `macro=strict` for orgs with mature workstreams
- Auto-suggest workstreams from fact clusters
- Refine ranking algorithms based on feedback

---

## User Communication

### For Admins

**Email template:**

> Subject: New Feature: Strategic Workstreams for Better Agendas
> 
> We've added a new "Workstreams" feature to organize your meetings around strategic initiatives.
> 
> **What's New:**
> - Create workstreams for your key projects/initiatives
> - Link relevant facts to each workstream
> - Agendas now group topics by workstream for better structure
> 
> **Getting Started:**
> 1. Go to [Your Org Settings]
> 2. Create 2-3 workstreams for your top priorities
> 3. Link relevant facts or let the system suggest links
> 
> **Benefits:**
> - Better organized agendas
> - Strategic focus on key initiatives
> - Evidence-based justifications for each topic
> 
> [Learn More] [Get Started]

### For API Users

Update API documentation to include:
- New workstream endpoints
- `macro` parameter for `/agenda/plan-nl`
- Metadata v2.0 structure

---

## Support Resources

### Documentation
- [MACRO_PLANNING.md](./MACRO_PLANNING.md) - Complete reference
- [MACRO_QUICK_START.md](./MACRO_QUICK_START.md) - Quick guide
- [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md) - Implementation details

### Troubleshooting

**Issue**: No workstreams showing up

**Solution**:
```python
from agent import db
workstreams = db.list_workstreams("org_id")
if not workstreams:
    print("Create workstreams via API or seed script")
```

**Issue**: Agendas still using legacy planner

**Solution**:
```bash
# Check config
echo $USE_MACRO_PLAN
echo $MACRO_DEFAULT_MODE

# Force macro mode
?macro=strict
```

**Issue**: Empty workstreams

**Solution**:
```bash
# Use suggest endpoint
POST /orgs/{org}/workstreams:suggest

# Or link facts manually
POST /workstreams/{ws_id}/link-facts
```

---

## Post-Migration Tasks

### Week 1
- [ ] Monitor error rates
- [ ] Check workstream creation rate
- [ ] Verify agenda generation times
- [ ] Collect initial user feedback

### Week 2-4
- [ ] Seed workstreams for all active orgs
- [ ] Train customer success team
- [ ] Create internal playbook
- [ ] Monitor adoption metrics

### Month 2+
- [ ] Analyze usage patterns
- [ ] Optimize ranking algorithms
- [ ] Consider auto-workstream features
- [ ] Plan UI enhancements

---

## Success Criteria

Migration is successful when:
- ✅ Zero production errors from new code
- ✅ All existing endpoints work unchanged
- ✅ At least 50% of orgs have ≥1 workstream
- ✅ Macro planning used in ≥30% of requests
- ✅ User satisfaction with agendas improves
- ✅ Agenda generation time <3s (p95)

---

## Contact

For migration support:
- Technical issues: Check logs, verify config
- Feature questions: See MACRO_PLANNING.md
- Urgent issues: Review rollback plan above

---

**Migration Owner**: Development Team  
**Timeline**: 4 weeks gradual rollout  
**Risk Level**: Low (backward compatible, feature flag protected)
