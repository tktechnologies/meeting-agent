# 🎉 LangGraph v2.0 is Now the Default!

## Summary of Changes

### What Changed:
```python
# agent/config.py
USE_LANGGRAPH_AGENDA: bool = _env_flag("USE_LANGGRAPH_AGENDA", True)  # ✅ NOW TRUE BY DEFAULT
```

### What This Means:

**✅ BEFORE (Opt-In):**
- Legacy planner was default
- Had to set `USE_LANGGRAPH_AGENDA=true` to use v2.0
- v2.0 required explicit activation

**✅ NOW (Default):**
- **LangGraph v2.0 is the default planner**
- Uses your existing `OPENAI_API_KEY` 
- Legacy planner available via `USE_LANGGRAPH_AGENDA=false`
- No configuration changes needed!

---

## 🚀 How to Use

### Just Start the Server:
```powershell
cd "c:\Users\mateu\OneDrive\Documentos\Stok AI\meeting-agent"
python -m uvicorn agent.api:app --host 127.0.0.1 --port 8000 --reload
```

**That's it!** v2.0 will automatically use your existing OpenAI credentials.

---

## 🔍 How to Verify v2.0 is Active

Check the response from `/agenda/plan-nl`:

### ✅ v2.0 Response (Default):
```json
{
  "fact_id": "fact_xxx",
  "proposal_preview": { ... },
  "metadata": {
    "generator": "langgraph",        // ← Confirms v2.0
    "quality_score": 0.85,
    "intent": "decision_making",
    "refinement_iterations": 0,
    "step_times": {
      "parse_and_understand": 1.234,
      "analyze_context": 0.876,
      "detect_intent": 0.654,
      "retrieve_facts": 2.345,
      "generate_macro_summary": 1.123,
      "build_agenda": 1.987,
      "review_quality": 0.543,
      "finalize_agenda": 0.234
    },
    "retrieval_stats": {
      "total_candidates": 123,
      "ranked_facts": 40,
      "workstream_facts": 45,
      "semantic_facts": 60,
      "urgent_facts": 18
    }
  }
}
```

### ❌ Legacy Response (If Explicitly Disabled):
```json
{
  "fact_id": "fact_xxx",
  "proposal_preview": { ... }
  // No metadata field
}
```

---

## 🎯 v2.0 Features (Now Active by Default)

1. **8-Step LangGraph Workflow**
   - Parse & Understand → Context Analysis → Intent Detection
   - Multi-Strategy Retrieval → Macro Summary → Build Agenda
   - Quality Review → Finalize (or Refine if score < 0.7)

2. **Automatic Intent Detection**
   - Decision Making, Problem Solving, Planning
   - Alignment, Status Update, Kickoff

3. **Multi-Strategy Fact Retrieval**
   - Workstream-based facts
   - Semantic search
   - Urgent/high-priority items
   - LLM-powered ranking (top 40 most relevant)

4. **Quality Gates**
   - Self-reviews agenda with quality score (0-1)
   - Auto-refines up to 2 times if quality < 0.7
   - Metadata includes refinement count

5. **Full Observability**
   - Step-by-step timing
   - Retrieval statistics
   - Quality scores
   - Intent classification

6. **GPT-5 Reasoning Support**
   - Configured via `MEETING_AGENT_REASONING_EFFORT`
   - Options: low, medium (default), high
   - Automatically enabled for GPT-5 models

---

## 🔧 Optional: Disable v2.0

If you need to use the legacy planner:

```powershell
# PowerShell
$env:USE_LANGGRAPH_AGENDA = "false"
python -m uvicorn agent.api:app --host 127.0.0.1 --port 8000 --reload
```

```bash
# Bash
export USE_LANGGRAPH_AGENDA="false"
python -m uvicorn agent.api:app --host 127.0.0.1 --port 8000 --reload
```

---

## 📊 Performance Expectations

**v2.0 (LangGraph) with GPT-5:**
- **Latency**: ~8-12 seconds per agenda (7 LLM calls)
- **Quality**: Higher due to iterative refinement
- **Cost**: ~$0.10-0.15 per agenda (with gpt-5-nano)
- **Reasoning**: Medium effort by default (configurable)

**Legacy Planner:**
- **Latency**: ~3-5 seconds per agenda (2 LLM calls)
- **Quality**: Good for simple cases
- **Cost**: ~$0.03-0.05 per agenda
- **Reasoning**: Not used

---

## 🎊 You're All Set!

**No environment changes needed** - the meeting-agent is ready to use v2.0 with your existing OpenAI credentials!

Just start the server and test with:
```bash
curl -X POST http://localhost:8000/agenda/plan-nl \
  -H "Content-Type: application/json" \
  -d '{"text": "faça a pauta da minha próxima reunião com a BYD", "org": "org_demo"}'
```

Look for `"generator": "langgraph"` in the response metadata to confirm v2.0 is active! 🚀
