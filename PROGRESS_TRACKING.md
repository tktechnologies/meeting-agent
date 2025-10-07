# Real-Time Progress Tracking

The meeting-agent now includes real-time progress tracking for the LangGraph v2.0 workflow using Server-Sent Events (SSE).

## Architecture

### Components

1. **Progress Tracking Module** (`agent/graph/progress.py`)
   - Thread-safe session management
   - Portuguese and English message translations
   - Status tracking: `running`, `completed`, `error`

2. **SSE Endpoint** (`/agenda/progress/{session_id}`)
   - Streams progress updates as Server-Sent Events
   - Auto-cleanup when workflow completes
   - 500ms polling interval

3. **Node Instrumentation** (`agent/graph/nodes.py`)
   - Each node calls `_update_progress()` at start/success/error
   - Pattern established in `parse_and_understand` node

4. **State Integration** (`agent/graph/state.py`)
   - `session_id` field added to `AgendaState`
   - Passed from API through entire workflow

## Usage

### Backend

When a client requests an agenda via `/agenda/plan-nl`, the API:

1. Generates a unique `session_id`
2. Creates a progress session with `create_session(session_id, language)`
3. Passes `session_id` in the initial state to the LangGraph workflow
4. Returns `session_id` in the response metadata

Example response:
```json
{
  "proposal": { ... },
  "metadata": {
    "version": "2.0",
    "generator": "langgraph",
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    ...
  }
}
```

### Frontend

The frontend can connect to the SSE endpoint to stream progress:

```javascript
// 1. Request agenda
const response = await fetch('/agenda/plan-nl', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    text: "planejar reunião sobre projeto BYD",
    org: "byd",
    language: "pt"
  })
});

const data = await response.json();
const sessionId = data.metadata.session_id;

// 2. Connect to SSE endpoint for progress
const eventSource = new EventSource(`/agenda/progress/${sessionId}`);

eventSource.onmessage = (event) => {
  const progress = JSON.parse(event.data);
  
  // Update UI with current step
  console.log(progress.current_message);
  // Example: "Entendendo pedido do usuário..."
  
  // Check if completed
  if (progress.completed) {
    eventSource.close();
    console.log('Workflow completed!');
  }
};

eventSource.onerror = (error) => {
  console.error('SSE error:', error);
  eventSource.close();
};
```

## Progress Messages

Each workflow node has user-friendly messages in Portuguese and English:

### Portuguese (pt)
- **parse_and_understand**: "Entendendo pedido do usuário..."
- **analyze_context**: "Analisando reuniões recentes..."
- **detect_intent**: "Detectando intenção da reunião..."
- **retrieve_facts**: "Buscando informações relevantes..."
- **synthesize_workstream_status**: "Analisando status do projeto..."
- **generate_macro_summary**: "Gerando contexto macro..."
- **build_agenda**: "Construindo pauta estruturada..."
- **review_quality**: "Revisando qualidade da pauta..."
- **finalize_agenda**: "Finalizando pauta..."

### English (en)
- **parse_and_understand**: "Understanding user request..."
- **analyze_context**: "Analyzing recent meetings..."
- **detect_intent**: "Detecting meeting intent..."
- **retrieve_facts**: "Retrieving relevant information..."
- **synthesize_workstream_status**: "Analyzing project status..."
- **generate_macro_summary**: "Generating macro context..."
- **build_agenda**: "Building structured agenda..."
- **review_quality**: "Reviewing agenda quality..."
- **finalize_agenda**: "Finalizing agenda..."

## Testing

Run the test script to verify SSE endpoint:

```bash
# 1. Start the API
uvicorn agent.api:app --reload --port 8001

# 2. In another terminal, run the test
python scripts/test_progress_sse.py
```

The test will:
1. Create a progress session
2. Simulate the 9-node workflow with delays
3. Stream progress updates via SSE
4. Display real-time messages

Expected output:
```
==========================================================
SSE Progress Tracking Test
==========================================================

1️⃣  Creating progress session: test-session-1234567890
   ✅ Session created

2️⃣  Starting workflow simulation (background thread)
🚀 Starting workflow simulation for session test-session-1234567890
   ▶️  parse_and_understand - running

3️⃣  Streaming progress from SSE endpoint

📡 Connecting to SSE endpoint: http://localhost:8001/agenda/progress/test-session-1234567890
✅ Connected! Streaming progress...

⏳ Entendendo pedido do usuário...
   ✅ parse_and_understand - completed
✅ Entendendo pedido do usuário...
⏳ Analisando reuniões recentes...
...
```

## Implementation Status

✅ **Completed:**
- Progress tracking module (`progress.py`)
- SSE endpoint (`/agenda/progress/{session_id}`)
- Session ID generation and management
- State integration (`session_id` in `AgendaState`)
- First node instrumented (`parse_and_understand`)

🔄 **In Progress:**
- Remaining 8 nodes need `_update_progress()` calls
- Frontend integration to display progress

📋 **Next Steps:**
1. Add `_update_progress()` to remaining 8 nodes
2. Update chat-agent frontend to consume SSE stream
3. Create progress UI component (stepper, progress bar, or similar)
4. Test end-to-end with real agenda requests

## Node Instrumentation Pattern

To add progress tracking to a node:

```python
def my_node(state: AgendaState) -> AgendaState:
    """My node description."""
    
    # 1. Mark as running at start
    _update_progress(state, "my_node", "running")
    
    try:
        # 2. Do node work
        result = do_work(state)
        
        # 3. Mark as completed on success
        _update_progress(state, "my_node", "completed")
        
        return result
        
    except Exception as e:
        # 4. Mark as error on failure
        _update_progress(state, "my_node", "error", str(e))
        raise
```

## Performance

- **Polling interval**: 500ms (configurable in SSE endpoint)
- **Session cleanup**: Automatic after completion or when SSE client disconnects
- **Timeout**: 300s (5 minutes) - matches workflow timeout
- **Thread safety**: Lock-based session management prevents race conditions
