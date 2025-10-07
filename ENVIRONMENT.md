# Environment Variables Guide

## ✅ Required (Already Configured)

These are the **same environment variables** you're already using for the parsing-agent and legacy meeting-agent:

```bash
# OpenAI Configuration (REQUIRED)
OPENAI_API_KEY=sk-...                    # Your OpenAI API key
OPENAI_BASE_URL=https://...              # Optional: Custom OpenAI endpoint
OPENAI_MODEL=gpt-5-nano                  # Optional: Default model (gpt-5-nano, gpt-4o, etc.)

# Meeting Agent Specific (OPTIONAL)
MEETING_AGENT_LLM_MODEL=gpt-5-nano       # Override model for meeting agent
MEETING_AGENT_REASONING_EFFORT=medium    # GPT-5 reasoning effort: low|medium|high
MEETING_AGENT_TZ=America/Sao_Paulo       # Timezone for date handling
MEETING_AGENT_WINDOW_DAYS=60             # How many days back to search
MEETING_AGENT_DURATION_MIN=30            # Default meeting duration

# Database (OPTIONAL)
SPINE_DB_PATH=./spine_dev.sqlite3        # Path to SQLite database
DEFAULT_ORG_ID=org_demo                  # Default organization ID
```

---

## 🆕 New v2.0 Feature Flags (Optional)

These control the new LangGraph-based planner. **v2.0 is now the default!**

```bash
# LangGraph v2.0 Planner (default: true - ENABLED)
USE_LANGGRAPH_AGENDA=true  # Set to "false" to use legacy planner

# Whitelist specific orgs for gradual rollout (default: all orgs)
LANGGRAPH_ORGS=renault,byd,volkswagen    # Comma-separated list

# Fallback to legacy on errors (default: true)
LANGGRAPH_FALLBACK_LEGACY=true
```

---

## 🎯 Quick Start

### Option 1: Use LangGraph v2.0 (Default - No Changes Needed)
**v2.0 is now enabled by default!** Just start the server with your existing OpenAI credentials:
```powershell
cd "c:\Users\mateu\OneDrive\Documentos\Stok AI\meeting-agent"
python -m uvicorn agent.api:app --host 127.0.0.1 --port 8000 --reload
```

### Option 2: Disable v2.0 (Use Legacy Planner)
If you need to use the legacy planner:
```powershell
$env:USE_LANGGRAPH_AGENDA = "false"
python -m uvicorn agent.api:app --host 127.0.0.1 --port 8000 --reload
```

---

## 🔍 Which Planner is Running?

Check the response metadata:

**Legacy Planner:**
```json
{
  "fact_id": "fact_xxx",
  "proposal_preview": { ... }
  // No "metadata" field
}
```

**LangGraph v2.0:**
```json
{
  "fact_id": "fact_xxx",
  "proposal_preview": { ... },
  "metadata": {
    "generator": "langgraph",           // ← Confirms v2.0
    "quality_score": 0.85,
    "intent": "decision_making",
    "refinement_iterations": 0,
    "step_times": { ... },
    "retrieval_stats": { ... }
  }
}
```

---

## 🚫 What You DON'T Need

❌ **ANTHROPIC_API_KEY** - Not needed! We use OpenAI/GPT-5 (same as your existing setup)
❌ **New .env file** - The meeting-agent shares your existing environment
❌ **Additional API keys** - Everything uses your existing OPENAI_API_KEY

---

## 📊 GPT-5 Reasoning Configuration

The v2.0 planner supports GPT-5 reasoning (same as legacy):

```bash
# Control reasoning effort for GPT-5 models
MEETING_AGENT_REASONING_EFFORT=medium    # Options: low, medium, high

# The planner automatically detects GPT-5 models and enables reasoning
OPENAI_MODEL=gpt-5-nano                  # Reasoning enabled automatically
OPENAI_MODEL=gpt-4o                      # No reasoning (GPT-4)
```

**Reasoning Effort Impact:**
- `low`: Faster responses (~5-8s per agenda)
- `medium`: Balanced quality/speed (~8-12s per agenda) ← **Recommended**
- `high`: Maximum quality (~15-20s per agenda)

---

## 🔧 Testing Both Planners

Use the comparison script to test side-by-side:

```powershell
cd "c:\Users\mateu\OneDrive\Documentos\Stok AI\meeting-agent"

# Test both planners with the same query
python scripts/compare_planners.py "próxima reunião com a BYD"

# Output files for comparison
ls -Name legacy_output.json, langgraph_output.json
```

---

## 📝 Summary

**You're already configured!** The meeting-agent will work immediately with your existing OpenAI setup. The new LangGraph v2.0 planner is **opt-in** via `USE_LANGGRAPH_AGENDA=true` when you're ready to test it.
