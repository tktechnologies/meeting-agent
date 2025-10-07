"""
Live test for SSE progress tracking with concurrent request/streaming.

This script:
1. Starts streaming SSE progress
2. Makes /agenda/plan-nl request in parallel
3. Shows real-time progress as the workflow executes

Usage:
    python scripts/test_live_progress.py
"""

import sys
import json
import time
import threading
import requests
from pathlib import Path
import queue

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def make_agenda_request_async(base_url: str, result_queue: queue.Queue):
    """Make agenda request and put session_id in queue immediately after parsing response."""
    
    url = f"{base_url}/agenda/plan-nl"
    
    payload = {
        "org_id": "org_demo",
        "text": "Quero uma reunião para discutir o andamento dos projetos de automação e RPA, incluindo novos casos de uso",
        "language": "pt-BR"
    }
    
    print(f"📤 Sending agenda request...")
    print(f"   Query: {payload['text'][:80]}...\n")
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            result_queue.put({"error": response.text})
            return
        
        data = response.json()
        session_id = data.get("metadata", {}).get("session_id")
        
        result_queue.put({
            "session_id": session_id,
            "data": data
        })
        
    except Exception as e:
        print(f"❌ Request error: {e}")
        result_queue.put({"error": str(e)})


def stream_progress(session_id: str, base_url: str = "http://localhost:8000"):
    """Stream progress from SSE endpoint."""
    
    url = f"{base_url}/agenda/progress/{session_id}"
    
    print(f"📡 Streaming progress for session: {session_id}\n")
    
    try:
        response = requests.get(url, stream=True, timeout=120)
        
        if response.status_code != 200:
            print(f"❌ SSE Error: {response.status_code}")
            return
        
        start_time = time.time()
        
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                
                if line_str.startswith('data: '):
                    data_str = line_str[6:]
                    data = json.loads(data_str)
                    
                    if 'error' in data:
                        print(f"❌ Error: {data['error']}")
                        break
                    
                    msg = data.get('current_message', '')
                    completed_steps = len(data.get('completed_steps', []))
                    total_steps = data.get('total_steps', 9)
                    completed = data.get('completed', False)
                    elapsed = time.time() - start_time
                    
                    progress_bar = f"[{completed_steps}/{total_steps}]"
                    timestamp = f"[{elapsed:>5.1f}s]"
                    print(f"⏳ {timestamp} {progress_bar} {msg}")
                    
                    if completed:
                        print(f"\n🎉 Workflow completed in {elapsed:.1f} seconds!\n")
                        break
        
    except Exception as e:
        print(f"❌ Stream error: {e}")


def main():
    """Main test function with concurrent request + streaming."""
    
    print("=" * 75)
    print("Live SSE Progress Tracking Test")
    print("=" * 75)
    print()
    
    base_url = "http://localhost:8000"
    
    # Check API
    try:
        health = requests.get(f"{base_url}/health", timeout=2)
        if not health.ok:
            print("❌ API health check failed")
            return
    except:
        print(f"❌ API not running at {base_url}")
        return
    
    print(f"✅ API is running\n")
    
    # We'll use a two-phase approach:
    # 1. Make a quick request to get a session_id
    # 2. Make another request and stream its progress
    
    print("🧪 Phase 1: Quick test to get session pattern\n")
    
    test_payload = {
        "org_id": "org_demo",
        "text": "reunião rápida de teste",
        "language": "pt-BR"
    }
    
    test_resp = requests.post(f"{base_url}/agenda/plan-nl", json=test_payload, timeout=60)
    if test_resp.ok:
        test_session = test_resp.json().get("metadata", {}).get("session_id")
        if test_session:
            print(f"✅ Sessions are being created: {test_session}\n")
        else:
            print("⚠️  No session_id found - LangGraph may not be enabled\n")
            return
    
    print("\n" + "=" * 75)
    print("🧪 Phase 2: Live Progress Streaming")
    print("=" * 75)
    print()
    print("NOTE: The workflow executes quickly (2-5 seconds), so progress")
    print("      updates stream rapidly. Watch for the Portuguese messages!\n")
    
    # Now do the live test
    result_queue = queue.Queue()
    
    # Start request in background
    request_thread = threading.Thread(
        target=make_agenda_request_async,
        args=(base_url, result_queue),
        daemon=True
    )
    request_thread.start()
    
    # Wait a moment for request to start and get session_id
    time.sleep(0.3)
    
    try:
        result = result_queue.get(timeout=5)
        
        if "error" in result:
            print(f"❌ Request failed: {result['error']}")
            return
        
        session_id = result.get("session_id")
        if not session_id:
            print("❌ No session_id in response")
            return
        
        # Stream the progress (this should happen while request is still processing)
        stream_progress(session_id, base_url)
        
        # Wait for request to finish
        request_thread.join(timeout=120)
        
        # Show final results
        data = result.get("data", {})
        sections = data.get("proposal", {}).get("agenda", {}).get("sections", [])
        print(f"📊 Final Result:")
        print(f"   - Sections: {len(sections)}")
        print(f"   - Quality: {data.get('metadata', {}).get('quality_score', 'N/A')}")
        print(f"   - Refinements: {data.get('metadata', {}).get('refinement_count', 0)}\n")
        
    except queue.Empty:
        print("❌ Timeout waiting for request response")
    
    print("=" * 75)
    print("Test completed!")
    print("=" * 75)


if __name__ == "__main__":
    main()
