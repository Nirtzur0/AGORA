"""
Integration tests for Moltbook Adapter service.

Tests the adapter via HTTP (treats it as a black box).
The adapter must be running on MOLTBOOK_ADAPTER_URL.
"""

import pytest
import requests
import time


def test_root_endpoint_returns_service_info(moltbook_adapter_url):
    """GET / returns service information."""
    response = requests.get(f"{moltbook_adapter_url}/")
    
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "AGORA Moltbook Adapter"
    assert "version" in data
    assert "endpoints" in data


def test_health_endpoint(moltbook_adapter_url):
    """GET /health returns health status."""
    response = requests.get(f"{moltbook_adapter_url}/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "moltbook-adapter"
    assert "circuit_state" in data
    assert "cache_stats" in data


def test_verify_missing_identity_token(moltbook_adapter_url):
    """POST /verify without identity_token returns 400."""
    response = requests.post(f"{moltbook_adapter_url}/verify", json={})
    
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "BAD_REQUEST"
    assert "identity_token" in data["message"]


def test_verify_invalid_token_type(moltbook_adapter_url):
    """POST /verify with non-string token returns 400."""
    response = requests.post(
        f"{moltbook_adapter_url}/verify",
        json={"identity_token": 12345}
    )
    
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "BAD_REQUEST"


def test_verify_invalid_token_returns_401(moltbook_adapter_url):
    """POST /verify with invalid token returns 401."""
    # This test depends on the real Moltbook being configured
    # If Moltbook is not reachable, this might return 503 instead
    response = requests.post(
        f"{moltbook_adapter_url}/verify",
        json={"identity_token": "clearly-invalid-token-12345"}
    )
    
    # Accept either 401 (invalid token) or 503 (Moltbook unavailable)
    assert response.status_code in [401, 503]
    
    data = response.json()
    assert "error" in data
    
    if response.status_code == 401:
        assert data["error"] in ["INVALID_TOKEN", "EXPIRED_TOKEN"]
    elif response.status_code == 503:
        assert data["error"] in ["UPSTREAM_UNAVAILABLE", "CIRCUIT_OPEN"]
        # Should include Retry-After header
        assert "retry-after" in response.headers or "Retry-After" in response.headers


def test_404_for_unknown_endpoint(moltbook_adapter_url):
    """Unknown endpoints return 404."""
    response = requests.get(f"{moltbook_adapter_url}/unknown")
    
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "NOT_FOUND"


def test_health_check_includes_circuit_state(moltbook_adapter_url):
    """Health check reports circuit breaker state."""
    response = requests.get(f"{moltbook_adapter_url}/health")
    
    assert response.status_code == 200
    data = response.json()
    
    # Circuit state should be one of: CLOSED, OPEN, HALF_OPEN
    assert data["circuit_state"] in ["CLOSED", "OPEN", "HALF_OPEN"]
    
    # Cache stats should be present
    assert isinstance(data["cache_stats"], dict)


# Note: Full integration tests with valid Moltbook tokens would require
# either a real Moltbook instance or a mock Moltbook service.
# The Jest tests in the TypeScript codebase provide more detailed coverage
# using axios-mock-adapter. These pytest tests verify the service is running
# and responding correctly to basic requests.
