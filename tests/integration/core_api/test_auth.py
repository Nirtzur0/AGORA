"""
Integration tests for Core API authentication (Component 4).

Tests:
- Agent registration via Moltbook
- JWT issuance and validation
- Dual JWT model (agent vs system)
- Auth middleware
- Idempotency keys
"""

import pytest


def test_auth_md__no_auth__returns_instructions_payload(test_client):
    """GET /auth.md returns machine-readable auth instructions."""
    response = test_client.get("/auth.md")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check structure
    assert "service" in data
    assert "authentication" in data
    assert "endpoints" in data["authentication"]
    assert "errors" in data
    assert "retry_logic" in data
    
    # Check endpoints are documented
    endpoints = data["authentication"]["endpoints"]
    assert "header_based" in endpoints
    assert "body_based" in endpoints
    
    # Check header-based auth
    header_auth = endpoints["header_based"]
    assert header_auth["url"] == "/auth/moltbook"
    assert header_auth["method"] == "POST"
    assert "X-Moltbook-Identity" in header_auth["headers"]
    
    # Check body-based auth
    body_auth = endpoints["body_based"]
    assert body_auth["url"] == "/auth/verify"
    assert body_auth["method"] == "POST"
    assert "moltbook_identity_token" in body_auth["body"]


def test_auth_moltbook__missing_header__returns_422(test_client):
    """POST /auth/moltbook without X-Moltbook-Identity returns 422."""
    response = test_client.post("/auth/moltbook")
    
    # FastAPI returns 422 for missing required headers
    assert response.status_code == 422


def test_auth_verify__missing_token__returns_422(test_client):
    """POST /auth/verify without token returns 422."""
    response = test_client.post("/auth/verify", json={})
    
    # FastAPI returns 422 for missing required fields
    assert response.status_code == 422


def test_auth_verify__invalid_token__returns_401_or_503(test_client):
    """POST /auth/verify with invalid token returns 401 or 503."""
    response = test_client.post("/auth/verify", json={"moltbook_identity_token": "invalid-token-12345"})
    
    # Either invalid token (401) or Moltbook unavailable (503)
    assert response.status_code in [401, 503]
    
    data = response.json()
    assert "error" in data or "detail" in data


def test_agents_me__no_auth__returns_401(test_client):
    """GET /agents/me without auth returns 401."""
    response = test_client.get("/agents/me")
    
    assert response.status_code == 401


def test_agents_me__invalid_token__returns_401(test_client):
    """GET /agents/me with invalid token returns 401."""
    response = test_client.get("/agents/me", headers={"Authorization": "Bearer invalid-token"})
    
    assert response.status_code == 401
    data = response.json()
    assert "error" in data["detail"] or "detail" in data


def test_agent_context__no_auth__returns_401(test_client):
    """GET /agent/context without auth returns 401."""
    response = test_client.get("/agent/context", params={"workspace_id": "00000000-0000-0000-0000-000000000000"})
    
    assert response.status_code == 401


def test_agent_context__invalid_token__returns_401(test_client):
    """GET /agent/context with invalid token returns 401."""
    response = test_client.get(
        "/agent/context",
        params={"workspace_id": "00000000-0000-0000-0000-000000000000"},
        headers={"Authorization": "Bearer invalid-token"},
    )
    
    assert response.status_code == 401
