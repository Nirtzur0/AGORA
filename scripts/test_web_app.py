#!/usr/bin/env python3
"""
Test the web app functionality end-to-end.
"""
import requests
import json
import os
import sys

BASE_URL = "http://localhost:8000"
MOLTBOOK_IDENTITY = os.getenv("MOLTBOOK_IDENTITY", "debug-token-clawdbot")
TOKEN = os.getenv("TEST_JWT")


def get_token():
    if TOKEN:
        return TOKEN

    response = requests.post(
        f"{BASE_URL}/auth/moltbook",
        headers={"X-Moltbook-Identity": MOLTBOOK_IDENTITY},
        timeout=5
    )
    response.raise_for_status()
    return response.json()["agent_session_jwt"]

def test_endpoint(name, method, path, expected_status=200):
    """Test an API endpoint."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")
    
    headers = {"Authorization": f"Bearer {get_token()}"}
    
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
                return True, data
            except:
                print(f"Response (text): {response.text[:200]}")
                print("✓ PASSED")
                return True, None
        else:
            print(f"✗ FAILED - Expected {expected_status}, got {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False, None
    except Exception as e:
        print(f"✗ FAILED - Exception: {e}")
        return False, None

def main():
    print("=" * 60)
    print("AGORA Web App End-to-End Test")
    print("=" * 60)
    
    passed = 0
    failed = 0

    ok, _ = test_endpoint("Get Agent Profile", "GET", "/agents/me")
    if ok:
        passed += 1
    else:
        failed += 1

    ok, workspaces = test_endpoint("List Workspaces", "GET", "/workspaces")
    if ok:
        passed += 1
    else:
        failed += 1

    workspace_id = None
    if isinstance(workspaces, list) and workspaces:
        workspace_id = workspaces[0].get("id")
    elif isinstance(workspaces, dict) and workspaces.get("workspaces"):
        workspace_id = workspaces["workspaces"][0].get("id")

    if not workspace_id:
        print("✗ FAILED - No workspace_id found in list workspaces response")
        failed += 1
    else:
        for name, path in [
            ("List Workspace Events", f"/workspaces/{workspace_id}/events"),
            ("List Workspace Logs", f"/workspaces/{workspace_id}/logs"),
            ("List Workspace Claims", f"/workspaces/{workspace_id}/claims"),
            ("List Workspace Critiques", f"/workspaces/{workspace_id}/critiques"),
            ("List Workspace Artifacts", f"/workspaces/{workspace_id}/artifacts"),
        ]:
            ok, _ = test_endpoint(name, "GET", path)
            if ok:
                passed += 1
            else:
                failed += 1
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
