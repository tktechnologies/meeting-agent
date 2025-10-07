# LangGraph Agenda Planner v2.0 - Quick Start

## 🚀 Setup

### 1. Install Dependencies

```bash
cd meeting-agent
pip install -r requirements.txt
```

### 2. Environment Variables

**✅ v2.0 is now enabled by default!** Just ensure your OpenAI credentials are set:

```bash
# Required: OpenAI API key (already configured for parsing-agent)
export OPENAI_API_KEY="sk-..."

# Optional: Custom OpenAI endpoint
export OPENAI_BASE_URL="https://..."

# Optional: Model selection (default: gpt-5-nano)
export OPENAI_MODEL="gpt-5-nano"

# Optional: Disable v2.0 to use legacy planner
export USE_LANGGRAPH_AGENDA="false"

# Optional: Whitelist specific orgs (comma-separated)
# If not set, applies to all orgs
export LANGGRAPH_ORGS="org_demo,org_byd"

# Optional: Fallback to legacy planner on errors (default: true)
export LANGGRAPH_FALLBACK_LEGACY="true"
```

**PowerShell (Windows):**
```powershell
# v2.0 uses your existing OpenAI setup - no changes needed!
# Just start the server (see step 3)

# Optional: To disable v2.0 and use legacy:
$env:USE_LANGGRAPH_AGENDA = "false"
```

### 3. Start Server

```bash
python -m uvicorn agent.api:app --host 127.0.0.1 --port 8000 --reload
```

## 📊 Testing

### Test with BYD case:

```bash
curl -X POST http://localhost:8000/agenda/plan-nl \
  -H "Content-Type: application/json" \
  -d '{
    "text": "faça a pauta da minha próxima reunião com a BYD",
    "org": "org_demo",
    "format": "json"
  }'
```

### Expected Response Structure:

```json
{
  "proposal": {
    "agenda": {
      "title": "...",
      "minutes": 30,
      "sections": [...]
    },
    "choice": "langgraph-decision_making",
    "reason": "LLM-driven iterative planning with quality review"
  },
  "metadata": {
    "version": "2.0",
    "generator": "langgraph",
    "elapsed_seconds": 8.5,
    "quality_score": 0.85,
    "refinement_count": 0,
    "intent": "decision_making",
    "intent_confidence": 0.9,
    "step_times": {
      "parse_and_understand": 1.2,
      "analyze_context": 0.5,
      "detect_intent": 1.3,
      "retrieve_facts": 2.1,
      "generate_macro_summary": 0.8,
      "build_agenda": 2.0,
      "review_quality": 0.6
    },
    "retrieval_stats": {
      "workstream": 15,
      "semantic": 20,
      "urgent": 5,
      "total": 38
    }
  }
}
```

## 🔧 Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_LANGGRAPH_AGENDA` | `false` | Enable LangGraph v2.0 planner |
| `LANGGRAPH_ORGS` | `null` | Whitelist orgs (comma-separated) |
| `LANGGRAPH_FALLBACK_LEGACY` | `true` | Fallback to legacy on errors |
| `ANTHROPIC_API_KEY` | Required | Claude API key |

## 📈 Features

### ✅ Implemented:
- 8-node LangGraph workflow with iterative refinement
- LLM-powered intent detection (6 types)
- Multi-strategy fact retrieval (workstreams + semantic + urgent)
- Intent-specific section templates
- Quality review with automatic refinement (max 2 loops)
- Backward-compatible API (same format as legacy)
- Graceful fallback to legacy planner
- Observability (step times, retrieval stats, quality scores)

### 🎯 Intent Types:
1. **decision_making** - Approve/choose/finalize
2. **problem_solving** - Resolve blockers/risks
3. **planning** - Roadmap/milestones
4. **alignment** - Sync understanding
5. **status_update** - Progress reports
6. **kickoff** - First meetings

## 🐛 Troubleshooting

### Server won't start:
- Check if `ANTHROPIC_API_KEY` is set
- Verify all dependencies installed: `pip install -r requirements.txt`

### LangGraph not being used:
- Ensure `USE_LANGGRAPH_AGENDA=true`
- Check if org is whitelisted (if `LANGGRAPH_ORGS` is set)
- Look for errors in server logs

### Falling back to legacy:
- Check `metadata.errors` in response
- Common causes: Missing API key, timeout, JSON parsing errors
- Set `LANGGRAPH_FALLBACK_LEGACY=false` to surface errors

## 📚 Architecture

```
User Query
  ↓
[1] Parse & Understand → Extract subject, language, duration
  ↓
[2] Context Analysis → Analyze recent meetings, open items
  ↓
[3] Intent Detection (LLM) → Classify meeting type
  ↓
[4] Smart Fact Retrieval → Multi-strategy + LLM ranking
  ↓
[5] Macro Summary (LLM) → 3-4 sentence synthesis
  ↓
[6] Build Agenda (LLM) → Populate intent-driven template
  ↓
[7] Quality Review (LLM) → Score and suggest improvements
  ↓
[8] Conditional: quality < 0.7? → Refine (loop to step 4) OR Finalize
  ↓
Final Agenda + Metadata
```

## 🚀 Next Steps

1. Test with more complex queries
2. Monitor quality scores and refinement rates
3. Tune prompts based on user feedback
4. Expand to more organizations
5. Add A/B testing between legacy and v2.0
