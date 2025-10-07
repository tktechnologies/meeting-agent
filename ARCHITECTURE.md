# Meeting Agent Architecture - v2.0

## 📁 Directory Structure

```
meeting-agent/
├── agent/
│   ├── graph/                    # 🆕 LangGraph v2.0 Workflow
│   │   ├── __init__.py
│   │   ├── state.py             # AgendaState TypedDict
│   │   ├── nodes.py             # 8 workflow nodes
│   │   ├── graph.py             # StateGraph definition
│   │   └── prompts.py           # LLM prompt templates
│   │
│   ├── intent/                   # 🆕 LLM-Based Intent Detection
│   │   ├── __init__.py
│   │   └── templates.py         # Section templates per intent
│   │
│   ├── retrieval/                # 🆕 Multi-Strategy Fact Retrieval
│   │   ├── __init__.py
│   │   └── multi_strategy.py    # MultiStrategyRetriever class
│   │
│   ├── legacy/                   # 🗂️ Legacy Code (Pre-LangGraph)
│   │   ├── __init__.py
│   │   ├── planner.py           # Original macro-aware planner
│   │   ├── planner_v3.py        # Experimental intent planner
│   │   ├── intent.py            # Heuristic intent detection
│   │   └── text_quality.py      # Text extraction utils
│   │
│   ├── agenda.py                 # High-level planning API (uses legacy)
│   ├── api.py                    # FastAPI endpoints (routes to v2.0 or legacy)
│   ├── config.py                 # Feature flags & environment vars
│   ├── db.py                     # Database layer
│   ├── retrieval.py              # Core fact retrieval (used by both)
│   ├── textgen.py                # Agenda formatting
│   ├── nl_parser.py              # Natural language parsing
│   ├── auto_validate.py          # Fact validation
│   └── workstream_auto.py        # Auto workstream creation
│
├── scripts/                      # Utility scripts
├── LANGGRAPH_SETUP.md            # 🆕 Setup guide for v2.0
└── spine_dev.sqlite3             # Database
```

---

## 🔄 Code Flow Comparison

### **Legacy Flow (Pre-v2.0)**
```
User Query
  ↓
agenda.py → planner.py (heuristics)
  ↓
Agenda JSON
```

### **LangGraph v2.0 Flow**
```
User Query
  ↓
api.py (_should_use_langgraph?)
  ↓ YES
graph/graph.py (agenda_graph)
  ├─ parse_and_understand (LLM)
  ├─ analyze_context (DB + LLM)
  ├─ detect_intent (LLM)
  ├─ retrieve_facts (multi-strategy + LLM ranking)
  ├─ generate_macro_summary (LLM)
  ├─ build_agenda (LLM + templates)
  ├─ review_quality (LLM)
  └─ finalize_agenda (persist)
  ↓
Agenda JSON v2.0 + Metadata
```

---

## 🎛️ Feature Flags

### **Enable LangGraph v2.0:**
```bash
export USE_LANGGRAPH_AGENDA="true"
export ANTHROPIC_API_KEY="sk-ant-..."
```

### **Gradual Rollout:**
```bash
export LANGGRAPH_ORGS="org_demo,org_byd"  # Whitelist specific orgs
```

### **Fallback Behavior:**
```bash
export LANGGRAPH_FALLBACK_LEGACY="true"   # Fallback to legacy on errors
```

---

## 🗂️ Legacy Code Usage

The legacy modules in `agent/legacy/` are still used for:

1. **Fallback**: When `USE_LANGGRAPH_AGENDA=false` or LangGraph errors
2. **Compatibility**: Existing tests and scripts reference legacy planners
3. **Comparison**: A/B testing between v2.0 and legacy

### **When Legacy is Used:**
- `USE_LANGGRAPH_AGENDA=false` (default for safety)
- Org not in `LANGGRAPH_ORGS` whitelist
- LangGraph workflow errors (if `LANGGRAPH_FALLBACK_LEGACY=true`)
- Missing `ANTHROPIC_API_KEY`

---

## 🆕 What's New in v2.0

| Feature | Legacy | v2.0 (LangGraph) |
|---------|--------|------------------|
| **Intent Detection** | Regex heuristics | LLM-powered classification |
| **Fact Retrieval** | Simple workstream query | Multi-strategy + LLM ranking |
| **Section Structure** | Fixed templates | Intent-driven dynamic templates |
| **Quality Control** | None | LLM review with auto-refinement |
| **Iteration** | Single-pass | Iterative with max 2 refinements |
| **Observability** | Minimal | Full metadata (timings, scores, stats) |
| **Languages** | PT-BR only | PT-BR + EN-US |

---

## 🧪 Testing Both Versions

### **Test Legacy:**
```bash
curl -X POST http://localhost:8000/agenda/plan-nl \
  -H "Content-Type: application/json" \
  -d '{"text": "próxima reunião BYD", "org": "org_demo"}'
```
*(No env vars needed - legacy is default)*

### **Test LangGraph v2.0:**
```bash
export USE_LANGGRAPH_AGENDA=true
export ANTHROPIC_API_KEY="sk-ant-..."

curl -X POST http://localhost:8000/agenda/plan-nl \
  -H "Content-Type: application/json" \
  -d '{"text": "próxima reunião BYD", "org": "org_demo"}'
```

**Check response metadata:**
```json
{
  "metadata": {
    "version": "2.0",
    "generator": "langgraph",  // ← Confirms v2.0 was used
    "quality_score": 0.85
  }
}
```

---

## 🚀 Migration Plan

### **Phase 1: Beta Testing** (Current)
- LangGraph disabled by default (`USE_LANGGRAPH_AGENDA=false`)
- Test with 2-3 orgs via whitelist
- Monitor quality scores and errors

### **Phase 2: Gradual Rollout** (Week 2-3)
- Expand whitelist to 10+ orgs
- Compare quality metrics vs legacy
- Tune prompts based on feedback

### **Phase 3: Default Enable** (Week 4)
- Set `USE_LANGGRAPH_AGENDA=true` by default
- Keep fallback enabled
- Legacy available via flag

### **Phase 4: Deprecation** (Month 2)
- Move legacy to separate archive repo
- Remove fallback logic
- LangGraph only

---

## 📝 Key Files to Know

### **For Development:**
- `agent/graph/nodes.py` - Add/modify workflow steps
- `agent/graph/prompts.py` - Tune LLM prompts
- `agent/intent/templates.py` - Adjust section templates
- `agent/retrieval/multi_strategy.py` - Modify fact retrieval logic

### **For Configuration:**
- `agent/config.py` - Add environment variables
- `agent/api.py` - Modify API routing logic

### **For Debugging:**
- Check `metadata.errors` in response
- Review `metadata.step_times` for performance
- Inspect `metadata.retrieval_stats` for fact counts

---

## 🐛 Troubleshooting

### **"Still using legacy planner"**
✅ Set `USE_LANGGRAPH_AGENDA=true`  
✅ Set `ANTHROPIC_API_KEY`  
✅ Check org is in `LANGGRAPH_ORGS` whitelist (if set)  
✅ Restart server

### **"LangGraph errors out"**
✅ Check API key is valid  
✅ Review `metadata.errors` in response  
✅ Set `LANGGRAPH_FALLBACK_LEGACY=false` to surface errors  
✅ Check server logs for stack traces

---

## 📚 Documentation

- **Setup**: `LANGGRAPH_SETUP.md`
- **Architecture**: This file
- **Legacy Planners**: `agent/legacy/__init__.py`
- **Migration Guide**: `MIGRATION_GUIDE.md` (if needed)

---

**Status**: ✅ **v2.0 Implementation Complete - Ready for Beta Testing**
