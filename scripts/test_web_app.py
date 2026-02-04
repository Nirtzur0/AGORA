#!/usr/bin/env python3
"""
Test the web app functionality end-to-end.
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2Y2M4ZDA0NS01ZmJmLTRkOGYtOTFjYS01OWE4MTM0ZWM5ZTYiLCJ0eXBlIjoiYWdlbnQiLCJhdWQiOiJhZ29yYTphZ2VudC1hcGkiLCJpc3MiOiJhZ29yYS1jb3JlLWFwaSIsImlhdCI6MTc3MDExNzk0NywiZXhwIjoxNzcwMjA0MzQ3LCJtb2x0Ym9va19pZCI6InRlc3RfYWdlbnRfMDAxIiwicmVwdXRhdGlvbiI6MTAwfQ.2N1kq53Cb18L3E2EugSKrYI53IWhSdnKbIa-ep8gkgk"

def test_endpoint(name, method, path, expected_status=200):
    """Test an API endpoint."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")
    
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    try:
        if method == "GET":
            response = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=5)
        else:
            print(f"Method {method} not implemented in test script")
            return False
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == expected_status:
            try:
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2)[:500]}")
                print("✓ PASSED")
                return True
            except:
                print(f"Response (text): {response.text[:200]}")
                print("✓ PASSED")
                return True
        else:
            print(f"✗ FAILED - Expected {expected_status}, got {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
    except Exception as e:
        print(f"✗ FAILED - Exception: {e}")
        return False

def main():
    print("=" * 60)
    print("AGORA Web App End-to-End Test")
    print("=" * 60)
    
    tests = [
        ("Get Agent Profile", "GET", "/agents/me"),
        ("List Workspaces", "GET", "/workspaces"),
        ("List Workspace Events", "GET", "/workspaces/c5a1c06c-edd8-45c0-b882-7f9271652e97/events"),
        ("List Workspace Logs", "GET", "/workspaces/c5a1c06c-edd8-45c0-b882-7f9271652e97/logs"),
        ("List Workspace Claims", "GET", "/workspaces/c5a1c06c-edd8-45c0-b882-7f9271652e97/claims"),
        ("List Workspace Critiques", "GET", "/workspaces/c5a1c06c-edd8-45c0-b882-7f9271652e97/critiques"),
        ("List Workspace Artifacts", "GET", "/workspaces/c5a1c06c-edd8-45c0-b882-7f9271652e97/artifacts"),
    ]
    
    passed = 0
    failed = 0
    
    for name, method, path in tests:
        if test_endpoint(name, method, path):
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
