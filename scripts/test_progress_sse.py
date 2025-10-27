"""
Test script for SSE progress tracking endpoint.

This script:
1. Creates a progress session
2. Simulates progress updates
3. Connects to the SSE endpoint and streams progress

Usage:
    python scripts/test_progress_sse.py
"""

import sys
import os
import time
import threading
import requests
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.graph.progress import create_session, update_progress


def simulate_workflow(session_id: str):
    """Simulate a LangGraph workflow with progress updates."""
    
    nodes = [
        ("parse_and_understand", 1.5),
        ("analyze_context", 2.0),
        ("detect_intent", 1.0),
        ("retrieve_facts", 3.0),
        ("synthesize_workstream_status", 2.5),
        ("generate_macro_summary", 1.5),
        ("build_agenda", 3.0),
        ("review_quality", 1.0),
        ("finalize_agenda", 1.5),
    ]
    
    print(f"🚀 Starting workflow simulation for session {session_id}")
    
    for node_name, delay in nodes:
        # Mark as running
        update_progress(session_id, node_name, "running")
        print(f"   ▶️  {node_name} - running")
        
        # Simulate work
        time.sleep(delay)
        
        # Mark as completed
        update_progress(session_id, node_name, "completed")
        print(f"   ✅ {node_name} - completed")
    
    print(f"🎉 Workflow simulation completed!")


def stream_progress(session_id: str, base_url: str = "http://localhost:8000"):
    """Connect to SSE endpoint and stream progress updates."""
    
    url = f"{base_url}/agenda/progress/{session_id}"
    
    print(f"\n📡 Connecting to SSE endpoint: {url}")
    
    try:
        response = requests.get(url, stream=True, timeout=60)
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code} - {response.text}")
            return
        
        print("✅ Connected! Streaming progress...\n")
        
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                
                # SSE format: "data: {json}"
                if line_str.startswith('data: '):
                    import json
                    data_str = line_str[6:]  # Remove "data: " prefix
                    data = json.loads(data_str)
                    
                    # Display progress
                    if 'error' in data:
                        print(f"❌ Error: {data['error']}")
                        break
                    
                    msg = data.get('current_message', 'Working...')
                    status = data.get('status', 'unknown')
                    completed = data.get('completed', False)
                    
                    status_emoji = {
                        'running': '⏳',
                        'completed': '✅',
                        'error': '❌'
                    }.get(status, '❓')
                    
                    print(f"{status_emoji} {msg}")
                    
                    if completed:
                        print("\n🎉 Workflow completed!")
                        break
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Could not connect to {base_url}. Is the API running?")
        print("   Start the API with: uvicorn agent.api:app --reload --port 8000")
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Main test function."""
    
    print("=" * 60)
    print("SSE Progress Tracking Test")
    print("=" * 60)
    
    # 1. Create session
    session_id = "test-session-" + str(int(time.time()))
    language = "pt"
    
    print(f"\n1️⃣  Creating progress session: {session_id}")
    create_session(session_id, language)
    print(f"   ✅ Session created\n")
    
    # 2. Start workflow simulation in background thread
    print(f"2️⃣  Starting workflow simulation (background thread)")
    workflow_thread = threading.Thread(
        target=simulate_workflow,
        args=(session_id,),
        daemon=True
    )
    workflow_thread.start()
    
    # 3. Give workflow a moment to start
    time.sleep(0.5)
    
    # 4. Stream progress from SSE endpoint
    print(f"\n3️⃣  Streaming progress from SSE endpoint")
    stream_progress(session_id)
    
    # Wait for workflow to finish
    workflow_thread.join(timeout=30)
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
