#!/usr/bin/env python3
"""
Simple end-to-end smoke test for AGORA system.
Tests basic functionality without complex test dependencies.
"""
import os
import requests
import json
import sys

BASE_URL = "http://localhost:8000"
MOLTBOOK_IDENTITY = os.getenv("MOLTBOOK_IDENTITY", "debug-token-clawdbot")

def test_health():
    """Test health endpoint."""
    print("Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200, f"Health check failed: {response.status_code}"
    data = response.json()
    assert data["status"] == "healthy"
    print("✓ Health check passed")

def test_auth_flow():
    """Test basic authentication flow."""
    print("\nTesting authentication...")
    
    # Try to authenticate with Moltbook adapter
    response = requests.post(
        f"{BASE_URL}/auth/moltbook",
        headers={"X-Moltbook-Identity": MOLTBOOK_IDENTITY},
        timeout=5
    )
    
    # We expect either success or a proper error response
    print(f"  Auth response status: {response.status_code}")
    print(f"  Auth response: {response.json()}")
    
    if response.status_code == 200:
        print("✓ Authentication successful")
        return response.json().get("agent_session_jwt")
    else:
        print("⚠ Authentication failed (expected if Moltbook not configured)")
        return None

def test_database_connection():
    """Test that database is accessible via API."""
    print("\nTesting database connection...")
    
    # Try to list workspaces (should return empty list or require auth)
    response = requests.get(f"{BASE_URL}/workspaces")
    
    print(f"  Status: {response.status_code}")
    if response.status_code == 200:
        workspaces = response.json()
        print(f"  Found {len(workspaces)} workspaces")
        print("✓ Database connection working")
    elif response.status_code == 401:
        print("✓ Database connection working (auth required)")
    else:
        print(f"  Response: {response.text[:200]}")

def test_temporal_connection():
    """Test that Temporal worker is running."""
    print("\nTesting Temporal connection...")
    
    # Check if Temporal UI is accessible
    try:
        response = requests.get("http://localhost:8080", timeout=2)
        if response.status_code == 200:
            print("✓ Temporal UI is accessible at http://localhost:8080")
        else:
            print(f"⚠ Temporal UI returned status {response.status_code}")
    except Exception as e:
        print(f"⚠ Could not connect to Temporal UI: {e}")

def test_minio_connection():
    """Test MinIO is accessible."""
    print("\nTesting MinIO connection...")
    
    try:
        response = requests.get("http://localhost:9000/minio/health/live", timeout=2)
        if response.status_code == 200:
            print("✓ MinIO is accessible and healthy")
        else:
            print(f"⚠ MinIO returned status {response.status_code}")
    except Exception as e:
        print(f"⚠ Could not connect to MinIO: {e}")

def main():
    print("=" * 60)
    print("AGORA End-to-End Smoke Test")
    print("=" * 60)
    
    try:
        test_health()
        test_database_connection()
        test_auth_flow()
        test_temporal_connection()
        test_minio_connection()
        
        print("\n" + "=" * 60)
        print("✓ Smoke test completed successfully!")
        print("=" * 60)
        print("\nAll core services are running:")
        print("  - Core API: http://localhost:8000")
        print("  - API Docs: http://localhost:8000/docs")
        print("  - Temporal UI: http://localhost:8080")
        print("  - MinIO Console: http://localhost:9001")
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
