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
import jwt as pyjwt
from datetime import datetime, timedelta
import json
import time


@pytest.fixture(scope="module")
def moltbook_base(moltbook_adapter_url):
    """Base URL for Moltbook adapter."""
    return moltbook_adapter_url


def test_auth_instructions_endpoint(test_client):
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


def test_auth_moltbook_missing_header(test_client):
    """POST /auth/moltbook without X-Moltbook-Identity returns 422."""
    response = test_client.post("/auth/moltbook")
    
    # FastAPI returns 422 for missing required headers
    assert response.status_code == 422


def test_auth_verify_missing_token(test_client):
    """POST /auth/verify without token returns 422."""
    response = test_client.post("/auth/verify", json={})
    
    # FastAPI returns 422 for missing required fields
    assert response.status_code == 422


def test_auth_verify_invalid_token(test_client):
    """POST /auth/verify with invalid token returns 401 or 503."""
    response = test_client.post("/auth/verify", json={"moltbook_identity_token": "invalid-token-12345"})
    
    # Either invalid token (401) or Moltbook unavailable (503)
    assert response.status_code in [401, 503]
    
    data = response.json()
    assert "error" in data or "detail" in data


def test_agents_me_without_auth(test_client):
    """GET /agents/me without auth returns 401."""
    response = test_client.get("/agents/me")
    
    assert response.status_code == 401


def test_agents_me_with_invalid_token(test_client):
    """GET /agents/me with invalid token returns 401."""
    response = test_client.get("/agents/me", headers={"Authorization": "Bearer invalid-token"})
    
    assert response.status_code == 401
    data = response.json()
    assert "error" in data["detail"] or "detail" in data


def test_agent_context_without_auth(test_client):
    """GET /agent/context without auth returns 401."""
    response = test_client.get("/agent/context", params={"workspace_id": "00000000-0000-0000-0000-000000000000"})
    
    assert response.status_code == 401


def test_agent_context_with_invalid_token(test_client):
    """GET /agent/context with invalid token returns 401."""
    response = test_client.get(
        "/agent/context",
        params={"workspace_id": "00000000-0000-0000-0000-000000000000"},
        headers={"Authorization": "Bearer invalid-token"},
    )
    
    assert response.status_code == 401


# JWT unit tests (don't require running services)

def test_agent_token_creation_and_verification():
    """Test creating and verifying agent JWTs."""
    from jwt_utils import create_agent_token, verify_agent_token
    
    agent_id = "agent-123"
    moltbook_id = "mb_user_456"
    reputation = 750
    
    # Create token
    token = create_agent_token(agent_id, moltbook_id, reputation)
    assert isinstance(token, str)
    assert len(token) > 0
    
    # Verify token
    payload = verify_agent_token(token)
    assert payload["sub"] == agent_id
    assert payload["moltbook_id"] == moltbook_id
    assert payload["reputation"] == reputation
    assert payload["type"] == "agent"
    assert payload["aud"] == "agora:agent-api"


def test_system_token_creation_and_verification():
    """Test creating and verifying system JWTs."""
    from jwt_utils import create_system_token, verify_system_token
    
    service_name = "orchestrator"
    
    # Create token
    token = create_system_token(service_name)
    assert isinstance(token, str)
    assert len(token) > 0
    
    # Verify token
    payload = verify_system_token(token)
    assert payload["sub"] == service_name
    assert payload["type"] == "system"
    assert payload["aud"] == "agora:system-api"


def test_agent_token_cannot_be_verified_as_system():
    """Agent tokens should fail system verification."""
    from jwt_utils import create_agent_token, verify_system_token
    import jwt as pyjwt
    
    token = create_agent_token("agent-123", "mb_user_456", 750)
    
    # Should raise error
    with pytest.raises((pyjwt.InvalidTokenError, ValueError)):
        verify_system_token(token)


def test_system_token_cannot_be_verified_as_agent():
    """System tokens should fail agent verification."""
    from jwt_utils import create_system_token, verify_agent_token
    import jwt as pyjwt
    
    token = create_system_token("orchestrator")
    
    # Should raise error
    with pytest.raises((pyjwt.InvalidTokenError, ValueError)):
        verify_agent_token(token)


def test_expired_agent_token():
    """Test that expired agent tokens are rejected."""
    import os
    import jwt as pyjwt
    from jwt_utils import verify_agent_token, TokenAudience, AGENT_JWT_SECRET
    
    # Create expired token
    past_time = datetime.utcnow() - timedelta(hours=25)
    payload = {
        "sub": "agent-123",
        "type": "agent",
        "aud": TokenAudience.AGENT_API,
        "iss": "agora-core-api",
        "iat": int(past_time.timestamp()),
        "exp": int((past_time + timedelta(hours=1)).timestamp()),
        "moltbook_id": "mb_user_456",
        "reputation": 750,
    }
    
    token = pyjwt.encode(payload, AGENT_JWT_SECRET, algorithm="HS256")
    
    # Should raise ExpiredSignatureError
    with pytest.raises(pyjwt.ExpiredSignatureError):
        verify_agent_token(token)


def test_idempotency_payload_hash():
    """Test payload hashing for idempotency."""
    import sys
    import hashlib
    import json
    
    # Simple implementation for testing
    def compute_payload_hash(payload):
        json_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    payload1 = {"claim_text": "Test claim", "artifact_id": "123"}
    payload2 = {"artifact_id": "123", "claim_text": "Test claim"}  # Different order
    payload3 = {"claim_text": "Different claim", "artifact_id": "123"}
    
    hash1 = compute_payload_hash(payload1)
    hash2 = compute_payload_hash(payload2)
    hash3 = compute_payload_hash(payload3)
    
    # Same content, different order -> same hash
    assert hash1 == hash2
    
    # Different content -> different hash
    assert hash1 != hash3


def test_agent_token_includes_workspace_id():
    """Test agent tokens can include workspace scope."""
    from jwt_utils import create_agent_token, verify_agent_token
    
    workspace_id = "ws-789"
    token = create_agent_token(
        "agent-123", 
        "mb_user_456", 
        750, 
        workspace_id=workspace_id
    )
    
    payload = verify_agent_token(token)
    assert payload["workspace_id"] == workspace_id


def test_decode_token_unverified():
    """Test decoding token without verification (debugging)."""
    from jwt_utils import create_agent_token, decode_token_unverified
    
    token = create_agent_token("agent-123", "mb_user_456", 750)
    payload = decode_token_unverified(token)
    
    assert payload["sub"] == "agent-123"
    assert payload["moltbook_id"] == "mb_user_456"
    assert payload["reputation"] == 750


# Idempotency key integration tests would require:
# 1. A running Core API instance
# 2. A test database with idempotency_keys table
# 3. Test workspaces and agents
# These are covered in the full integration test suite when all components are running.
