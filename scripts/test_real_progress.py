"""
Test script for SSE progress tracking with real API call.

This script:
1. Makes an actual /agenda/plan-nl request to trigger workflow
2. Extracts session_id from response
3. Connects to SSE endpoint and streams progress

Usage:
    python scripts/test_real_progress.py
"""

import sys
import json
import time
import threading
import requests
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def make_agenda_request(base_url: str = "http://localhost:8000"):
    """Make agenda request and return session_id."""
    
    url = f"{base_url}/agenda/plan-nl"
    
    payload = {
        "org_id": "org_demo",
        "text": "Quero uma reunião para discutir o andamento dos projetos de automação e RPA",
        "language": "pt-BR"
    }
    
    print(f"📤 Sending agenda request to {url}")
    print(f"   Query: {payload['text']}\n")
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            return None
        
        data = response.json()
        session_id = data.get("metadata", {}).get("session_id")
        
        if not session_id:
            print(f"⚠️  Warning: No session_id in response")
            print(f"   Response keys: {list(data.keys())}")
            print(f"   Metadata: {data.get('metadata', {})}")
            return None
        
        print(f"✅ Request completed!")
        print(f"   Session ID: {session_id}")
        agenda_id = data.get("proposal", {}).get("agenda", {}).get("agenda_id")
        if not agenda_id:
            # Try alternate location
            agenda_id = data.get("agenda_id")
        print(f"   Agenda ID: {agenda_id}")
        sections = data.get("proposal", {}).get("agenda", {}).get("sections", [])
        print(f"   Sections: {len(sections)}\n")
        
        return session_id
        
    except requests.exceptions.Timeout:
        print(f"❌ Request timed out after 120 seconds")
        return None
    except requests.exceptions.ConnectionError:
        print(f"❌ Could not connect to {base_url}")
        print("   Is the API running? Start with: uvicorn agent.api:app --reload --port 8000")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def stream_progress(session_id: str, base_url: str = "http://localhost:8000"):
    """Connect to SSE endpoint and stream progress updates."""
    
    url = f"{base_url}/agenda/progress/{session_id}"
    
    print(f"📡 Connecting to SSE endpoint: {url}\n")
    
    try:
        response = requests.get(url, stream=True, timeout=120)
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code} - {response.text}")
            return
        
        print("✅ Connected! Streaming progress...\n")
        
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                
                # SSE format: "data: {json}"
                if line_str.startswith('data: '):
                    data_str = line_str[6:]  # Remove "data: " prefix
                    data = json.loads(data_str)
                    
                    # Display progress
                    if 'error' in data:
                        print(f"❌ Error: {data['error']}")
                        break
                    
                    msg = data.get('current_message', 'Working...')
                    status = data.get('status', 'unknown')
                    completed = data.get('completed', False)
                    current_step = data.get('current_step', '')
                    completed_steps = len(data.get('completed_steps', []))
                    total_steps = data.get('total_steps', 9)
                    
                    status_emoji = {
                        'running': '⏳',
                        'completed': '✅',
                        'error': '❌'
                    }.get(status, '❓')
                    
                    progress_bar = f"[{completed_steps}/{total_steps}]"
                    print(f"{status_emoji} {progress_bar} {msg}")
                    
                    if completed:
                        print("\n🎉 Workflow completed!")
                        break
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Could not connect to {base_url}")
    except Exception as e:
        print(f"❌ Error: {e}")


def stream_progress_threaded(session_id: str, base_url: str = "http://localhost:8000"):
    """Stream progress in a separate thread while API request is processing."""
    
    def stream():
        # Give API a moment to start the workflow
        time.sleep(0.3)
        stream_progress(session_id, base_url)
    
    thread = threading.Thread(target=stream, daemon=True)
    thread.start()
    return thread


def main():
    """Main test function."""
    
    print("=" * 70)
    print("SSE Progress Tracking Test - Real API Call")
    print("=" * 70)
    print()
    
    base_url = "http://localhost:8000"
    
    # Check if API is running
    try:
        health_check = requests.get(f"{base_url}/health", timeout=2)
        if not health_check.ok:
            print(f"❌ API health check failed")
            return
    except:
        print(f"❌ API is not running at {base_url}")
        print("   Start the API with: uvicorn agent.api:app --reload --port 8000")
        return
    
    print(f"✅ API is running at {base_url}\n")
    
    # Option 1: Stream progress in parallel with request
    print("🚀 Making agenda request with parallel progress streaming...\n")
    
    # We can't easily get session_id before making the request
    # So let's make the request synchronously first
    
    session_id = make_agenda_request(base_url)
    
    if not session_id:
        print("\n❌ Could not get session_id from response")
        print("   Note: Progress tracking may not be implemented in the /agenda/plan-nl endpoint yet")
        return
    
    print("\n" + "=" * 70)
    print("Test completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
