from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest

from idempotency import compute_payload_hash
from jwt_utils import (
    AGENT_JWT_SECRET,
    TokenAudience,
    create_agent_token,
    create_system_token,
    decode_token_unverified,
    verify_agent_token,
    verify_system_token,
)


def test_create_agent_token__valid_inputs__roundtrips_through_verify():
    agent_id = "agent-123"
    moltbook_id = "mb_user_456"
    reputation = 750

    token = create_agent_token(agent_id, moltbook_id, reputation)
    payload = verify_agent_token(token)

    assert payload["sub"] == agent_id
    assert payload["moltbook_id"] == moltbook_id
    assert payload["reputation"] == reputation
    assert payload["type"] == "agent"
    assert payload["aud"] == "agora:agent-api"


def test_create_system_token__valid_inputs__roundtrips_through_verify():
    service_name = "orchestrator"

    token = create_system_token(service_name)
    payload = verify_system_token(token)

    assert payload["sub"] == service_name
    assert payload["type"] == "system"
    assert payload["aud"] == "agora:system-api"


def test_verify_system_token__agent_token__raises():
    token = create_agent_token("agent-123", "mb_user_456", 750)

    with pytest.raises((pyjwt.InvalidTokenError, ValueError)):
        verify_system_token(token)


def test_verify_agent_token__system_token__raises():
    token = create_system_token("orchestrator")

    with pytest.raises((pyjwt.InvalidTokenError, ValueError)):
        verify_agent_token(token)


def test_verify_agent_token__expired_token__raises_expired_signature_error():
    past_time = datetime.now(timezone.utc) - timedelta(hours=25)
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

    with pytest.raises(pyjwt.ExpiredSignatureError):
        verify_agent_token(token)


def test_create_agent_token__workspace_id_provided__includes_workspace_id_claim():
    workspace_id = "ws-789"
    token = create_agent_token("agent-123", "mb_user_456", 750, workspace_id=workspace_id)

    payload = verify_agent_token(token)
    assert payload["workspace_id"] == workspace_id


def test_decode_token_unverified__signed_token__returns_payload_without_verifying():
    token = create_agent_token("agent-123", "mb_user_456", 750)
    payload = decode_token_unverified(token)

    assert payload["sub"] == "agent-123"
    assert payload["moltbook_id"] == "mb_user_456"
    assert payload["reputation"] == 750


def test_compute_payload_hash__same_payload_different_key_order__same_hash():
    payload1 = {"claim_text": "Test claim", "artifact_id": "123"}
    payload2 = {"artifact_id": "123", "claim_text": "Test claim"}

    assert compute_payload_hash(payload1) == compute_payload_hash(payload2)


def test_compute_payload_hash__different_payload__different_hash():
    payload1 = {"claim_text": "Test claim", "artifact_id": "123"}
    payload2 = {"claim_text": "Different claim", "artifact_id": "123"}

    assert compute_payload_hash(payload1) != compute_payload_hash(payload2)
