#!/usr/bin/env python3
"""
Test script to verify the stream endpoint fix for duplicate welcome message issue.
"""
import json
import requests

API_BASE = "http://localhost:8123"
AGENT_ID = "value-canvas"

def test_stream_first_yes():
    """Test that the first 'yes' correctly triggers Step 2, not Step 1 again."""
    
    # Start a new conversation with first "yes"
    response = requests.post(
        f"{API_BASE}/{AGENT_ID}/stream",
        json={
            "message": "yes",
            "user_id": 1,
            "thread_id": None,  # New conversation
            "stream_tokens": False
        },
        stream=True,
        timeout=30.0
    )
    
    print("="*50)
    print("STREAM RESPONSE TO FIRST 'YES':")
    print("="*50)
    
    # Parse SSE stream
    messages = []
    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')
            if line_str.startswith('data: '):
                try:
                    data = json.loads(line_str[6:])
                    if data['type'] == 'message':
                        content = data['content']['content']
                        messages.append(content)
                        print(f"\nMessage: {content[:200]}...")
                except json.JSONDecodeError:
                    pass
    
    # Check if Step 1 was incorrectly repeated
    step1_message = "Let's build your Value Canvas!"
    step2_message = "Firstly, some context on working with me as an AI"
    
    print("\n" + "="*50)
    print("ANALYSIS:")
    print("="*50)
    
    for i, msg in enumerate(messages):
        if step1_message in msg:
            print(f"❌ ISSUE FOUND: Step 1 message found at position {i}: {msg[:100]}...")
            print("   This indicates the bug is still present - Agent repeated Step 1")
            return False
        elif step2_message in msg:
            print(f"✅ SUCCESS: Step 2 message found at position {i}")
            print("   The fix is working - Agent correctly moved to Step 2")
            return True
    
    print("⚠️  Neither Step 1 nor Step 2 message found in response")
    print("    Full messages received:")
    for i, msg in enumerate(messages):
        print(f"    {i}: {msg[:100]}...")
    return False

def main():
    print("\n🔧 Testing Stream Endpoint Fix for Duplicate Welcome Message")
    print("="*60)
    
    try:
        success = test_stream_first_yes()
        
        if success:
            print("\n✅ FIX VERIFIED: The agent correctly processes the first 'yes'")
        else:
            print("\n❌ FIX NEEDED: The agent still has issues with the first 'yes'")
    except requests.exceptions.ConnectionError:
        print("\n⚠️  ERROR: Cannot connect to server at", API_BASE)
        print("   Make sure the server is running: python -m src.run_service")
    except Exception as e:
        print(f"\n⚠️  ERROR: {e}")

if __name__ == "__main__":
    main()