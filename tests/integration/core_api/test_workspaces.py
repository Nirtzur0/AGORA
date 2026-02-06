"""
Integration tests for workspace management + join flow.

These tests exercise the Core API boundary (FastAPI routing + auth + RBAC +
Postgres persistence) instead of writing directly to tables.
"""

from __future__ import annotations

import pytest

from jwt_utils import create_agent_token
from database import get_db
from tests.helpers.factories import insert_agent, new_uuid, role_id


def _delete_workspace(*, workspace_id: str) -> None:
    with get_db() as db:
        # Delete dependent rows first (no cascades assumed).
        db.execute("DELETE FROM join_requests WHERE workspace_id = :ws", {"ws": workspace_id})
        db.execute("DELETE FROM workspace_agents WHERE workspace_id = :ws", {"ws": workspace_id})
        db.execute("DELETE FROM events WHERE workspace_id = :ws", {"ws": workspace_id})
        db.execute("DELETE FROM workspaces WHERE id = :ws", {"ws": workspace_id})
        db.commit()


@pytest.fixture
def agent_tokens(migrated_db):
    maintainer_id = new_uuid()
    requester_id = new_uuid()

    with get_db() as db:
        insert_agent(db, agent_id=maintainer_id, moltbook_id=f"moltbook-{maintainer_id}", reputation=100)
        insert_agent(db, agent_id=requester_id, moltbook_id=f"moltbook-{requester_id}", reputation=200)

    maintainer_token = create_agent_token(maintainer_id, f"moltbook-{maintainer_id}", 100)
    requester_token = create_agent_token(requester_id, f"moltbook-{requester_id}", 200)

    bundle = {
        "maintainer": {"agent_id": maintainer_id, "headers": {"Authorization": f"Bearer {maintainer_token}"}},
        "requester": {"agent_id": requester_id, "headers": {"Authorization": f"Bearer {requester_token}"}},
    }

    try:
        yield bundle
    finally:
        # FK-safe cleanup. Workspaces are cleaned up by created_workspace.
        with get_db() as db:
            db.execute("DELETE FROM workspace_agents WHERE agent_id = :id", {"id": maintainer_id})
            db.execute("DELETE FROM workspace_agents WHERE agent_id = :id", {"id": requester_id})
            db.execute("DELETE FROM join_requests WHERE agent_id = :id", {"id": maintainer_id})
            db.execute("DELETE FROM join_requests WHERE agent_id = :id", {"id": requester_id})
            db.execute("DELETE FROM agents WHERE id = :id", {"id": maintainer_id})
            db.execute("DELETE FROM agents WHERE id = :id", {"id": requester_id})
            db.commit()


@pytest.fixture
def created_workspace(test_client, agent_tokens):
    r = test_client.post(
        "/workspaces",
        json={"name": "Test Workspace", "description": "Test description"},
        headers=agent_tokens["maintainer"]["headers"],
    )
    assert r.status_code == 201, r.text
    workspace_id = r.json()["id"]

    try:
        yield workspace_id
    finally:
        _delete_workspace(workspace_id=workspace_id)


def test_workspaces_create__valid_request__returns_init_phase_and_team_roster(test_client, created_workspace, agent_tokens):
    r = test_client.get(f"/workspaces/{created_workspace}", headers=agent_tokens["maintainer"]["headers"])
    assert r.status_code == 200, r.text

    payload = r.json()
    assert payload["workspace"]["id"] == created_workspace
    assert payload["workspace"]["phase"] == "INIT"
    assert payload["workspace"]["created_by"] == agent_tokens["maintainer"]["agent_id"]

    team = payload["team"]
    assert len(team) >= 1
    assert any(m["agent_id"] == agent_tokens["maintainer"]["agent_id"] and m["role_name"] == "Maintainer" for m in team)


def test_join_request_create__valid_role__returns_pending_request(test_client, created_workspace, agent_tokens):
    with get_db() as db:
        exp_role_id = role_id(db, role_name="Experimentalist")

    r = test_client.post(
        f"/workspaces/{created_workspace}/join-requests",
        json={"role_id": exp_role_id},
        headers=agent_tokens["requester"]["headers"],
    )
    assert r.status_code == 201, r.text

    payload = r.json()
    assert payload["workspace_id"] == created_workspace
    assert payload["agent_id"] == agent_tokens["requester"]["agent_id"]
    assert payload["role_id"] == exp_role_id
    assert payload["status"] == "pending"


def test_join_request_review__approved__adds_member_and_returns_approved_status(test_client, created_workspace, agent_tokens):
    with get_db() as db:
        exp_role_id = role_id(db, role_name="Experimentalist")

    jr = test_client.post(
        f"/workspaces/{created_workspace}/join-requests",
        json={"role_id": exp_role_id},
        headers=agent_tokens["requester"]["headers"],
    )
    assert jr.status_code == 201, jr.text
    request_id = jr.json()["id"]

    review = test_client.post(
        f"/workspaces/{created_workspace}/join-requests/{request_id}/review",
        json={"approve": True, "reason": "ok"},
        headers=agent_tokens["maintainer"]["headers"],
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "approved"

    ws = test_client.get(f"/workspaces/{created_workspace}", headers=agent_tokens["maintainer"]["headers"])
    assert ws.status_code == 200, ws.text
    assert any(m["agent_id"] == agent_tokens["requester"]["agent_id"] and m["role_id"] == exp_role_id for m in ws.json()["team"])


def test_join_request_review__role_at_capacity__returns_409(test_client, created_workspace, agent_tokens):
    # Maintainer role is expected to have capacity=1. The creator already occupies it.
    with get_db() as db:
        maintainer_role_id = role_id(db, role_name="Maintainer")

    jr = test_client.post(
        f"/workspaces/{created_workspace}/join-requests",
        json={"role_id": maintainer_role_id},
        headers=agent_tokens["requester"]["headers"],
    )
    assert jr.status_code == 201, jr.text

    request_id = jr.json()["id"]
    review = test_client.post(
        f"/workspaces/{created_workspace}/join-requests/{request_id}/review",
        json={"approve": True, "reason": "try"},
        headers=agent_tokens["maintainer"]["headers"],
    )
    assert review.status_code == 409, review.text


def test_join_request_create__insufficient_reputation__returns_403(test_client, created_workspace):
    low_rep_agent_id = new_uuid()
    with get_db() as db:
        insert_agent(db, agent_id=low_rep_agent_id, moltbook_id=f"moltbook-{low_rep_agent_id}", reputation=50)
    low_rep_headers = {"Authorization": f"Bearer {create_agent_token(low_rep_agent_id, f'moltbook-{low_rep_agent_id}', 50)}"}

    with get_db() as db:
        analyst_role_id = role_id(db, role_name="Literature Analyst")

    try:
        r = test_client.post(
            f"/workspaces/{created_workspace}/join-requests",
            json={"role_id": analyst_role_id},
            headers=low_rep_headers,
        )
        assert r.status_code == 403, r.text
    finally:
        with get_db() as db:
            db.execute("DELETE FROM join_requests WHERE agent_id = :id", {"id": low_rep_agent_id})
            db.execute("DELETE FROM workspace_agents WHERE agent_id = :id", {"id": low_rep_agent_id})
            db.execute("DELETE FROM agents WHERE id = :id", {"id": low_rep_agent_id})
            db.commit()


def test_workspaces_patch__description_only__updates_description(test_client, created_workspace, agent_tokens):
    r = test_client.patch(
        f"/workspaces/{created_workspace}",
        json={"description": "Updated description"},
        headers=agent_tokens["maintainer"]["headers"],
    )
    assert r.status_code == 200, r.text
    assert r.json()["description"] == "Updated description"


def test_workspaces_patch__phase_in_payload__does_not_change_phase(test_client, created_workspace, agent_tokens):
    before = test_client.get(f"/workspaces/{created_workspace}", headers=agent_tokens["maintainer"]["headers"])
    assert before.status_code == 200, before.text
    assert before.json()["workspace"]["phase"] == "INIT"

    r = test_client.patch(
        f"/workspaces/{created_workspace}",
        json={"description": "noop", "phase": "FINALIZED"},
        headers=agent_tokens["maintainer"]["headers"],
    )
    assert r.status_code == 200, r.text

    after = test_client.get(f"/workspaces/{created_workspace}", headers=agent_tokens["maintainer"]["headers"])
    assert after.status_code == 200, after.text
    assert after.json()["workspace"]["phase"] == "INIT"
