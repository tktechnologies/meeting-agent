# Bug Fixes Applied

## Issue 1: Module Naming Conflict

### Problem
When creating the v2.0 LangGraph implementation, we created a directory `agent/retrieval/` which conflicted with the existing `agent/retrieval.py` file. Python's import system was finding the directory first, causing `AttributeError: module 'agent.retrieval' has no attribute 'resolve_org_id'`.

### Root Cause
- **Existing**: `agent/retrieval.py` - Contains `resolve_org_id()` and other retrieval utilities
- **New**: `agent/retrieval/` - Directory for v2.0 multi-strategy retriever
- When importing `from . import retrieval`, Python found the directory instead of the file

### Solution
1. **Renamed directory**: `agent/retrieval/` → `agent/retrievers/`
2. **Updated import**: In `agent/graph/nodes.py`:
   - Changed: `from ..retrieval.multi_strategy import MultiStrategyRetriever`
   - To: `from ..retrievers.multi_strategy import MultiStrategyRetriever`

3. **Fixed additional import**: In `agent/auto_validate.py`:
   - Changed: `from . import db, planner`
   - To: `from . import db` + `from .legacy import planner`
   - This was needed because `planner` was moved to `agent/legacy/`

### Verification
✅ All imports now work correctly:
- `from agent import api, retrieval` - Success
- `retrieval.resolve_org_id` - Exists
- `from agent.graph.graph import agenda_graph` - Success

---

## Issue 2: Wrong LLM Provider (Anthropic Instead of OpenAI)

### Problem
The initial LangGraph implementation used `ChatAnthropic` (Claude), requiring `ANTHROPIC_API_KEY`, which was inconsistent with the existing infrastructure that uses OpenAI/GPT-5.

### Root Cause
- Hardcoded `ChatAnthropic` with `model="claude-sonnet-4-20250514"` in `agent/graph/nodes.py`
- Legacy planner uses OpenAI with GPT-5 and has full GPT-5 reasoning support
- Created unnecessary dependency on Anthropic API keys

### Solution
1. **Replaced LLM provider** in `agent/graph/nodes.py`:
   - Changed: `from langchain_anthropic import ChatAnthropic`
   - To: `from langchain_openai import ChatOpenAI`

2. **Updated _get_llm() function** to match legacy planner configuration:
   ```python
   def _get_llm(temperature: float = 0) -> ChatOpenAI:
       """Get LLM instance configured from environment variables."""
       api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
       base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")
       model = (
           os.environ.get("MEETING_AGENT_LLM_MODEL")
           or os.environ.get("OPENAI_MODEL")
           or "gpt-5-nano"
       )
       
       # GPT-5 reasoning configuration
       if "gpt-5" in model:
           kwargs["model_kwargs"] = {
               "reasoning": {
                   "effort": os.environ.get("MEETING_AGENT_REASONING_EFFORT", "medium")
               }
           }
   ```

3. **Updated dependencies** in `requirements.txt`:
   - Removed: `langchain-anthropic>=0.1.0`
   - Added: `langchain-openai>=0.1.0`

### Benefits
✅ **No new API key needed** - Uses existing `OPENAI_API_KEY`
✅ **Consistent infrastructure** - Same LLM provider as legacy planner
✅ **GPT-5 reasoning support** - Inherits `MEETING_AGENT_REASONING_EFFORT` configuration
✅ **Azure OpenAI compatible** - Supports `AZURE_OPENAI_API_KEY` and custom `OPENAI_BASE_URL`

---

## Files Modified
- `agent/retrieval/` → `agent/retrievers/` (directory rename)
- `agent/graph/nodes.py` - Updated import path + Changed to ChatOpenAI
- `agent/auto_validate.py` - Fixed planner import
- `requirements.txt` - Replaced langchain-anthropic with langchain-openai

## Current Directory Structure
```
agent/
  ├── retrieval.py              # Original retrieval utilities (resolve_org_id, etc.)
  ├── retrievers/               # New v2.0 multi-strategy retriever
  │   ├── __init__.py
  │   └── multi_strategy.py
  ├── legacy/                   # Archived pre-v2.0 code
  │   ├── planner.py
  │   ├── planner_v3.py
  │   ├── intent.py
  │   └── text_quality.py
  └── graph/                    # LangGraph workflow (now using OpenAI)
      ├── state.py
      ├── nodes.py              # Uses ChatOpenAI + GPT-5 reasoning
      ├── graph.py
      └── prompts.py
```

## Status
🟢 **FIXED** - Server can now start and handle requests using existing OpenAI infrastructure.
🟢 **NO NEW API KEYS NEEDED** - Uses same environment variables as legacy planner.
