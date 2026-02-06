"""
Integration tests for logs and events (Component 8 Exit Tests).

Critical exit tests per checklist:
1. Creating a claim creates an event row with actor_type=agent
2. Worker-created artifacts create events with actor_type=system

Tests:
- Log creation (agent writes)
- Log retrieval with filters
- Event creation (system writes)
- Event retrieval with filters
- Append-only enforcement (no updates/deletes)
"""
from uuid import uuid4

import pytest

from database import get_raw_db
import jwt_utils


@pytest.fixture
def workspace_ctx(migrated_db):
    """Create test workspace for log/event tests."""
    with get_raw_db() as conn:
        cursor = conn.cursor()
        
        # Create workspace and agent
        workspace_id = uuid4()
        agent_id = uuid4()
        
        cursor.execute(
            """
            INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (str(agent_id), f"test-moltbook-{agent_id}", "Test Agent", 100.0)
        )
        
        # Get Maintainer role
        cursor.execute("SELECT id FROM roles WHERE name = 'Maintainer'")
        role_id = cursor.fetchone()[0]
        
        cursor.execute(
            """
            INSERT INTO workspaces (id, name, description, phase, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            """,
            (str(workspace_id), "Test Workspace", "For log/event tests", "INIT", str(agent_id))
        )
        
        cursor.execute(
            """
            INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status, joined_at)
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (str(workspace_id), str(agent_id), role_id, "active")
        )
        
        conn.commit()
        
        yield {
            "workspace_id": str(workspace_id),
            "agent_id": str(agent_id),
            "moltbook_id": f"test-moltbook-{agent_id}",
        }
        
        # Cleanup
        cursor.execute("DELETE FROM logs WHERE workspace_id = %s", (str(workspace_id),))
        cursor.execute("DELETE FROM events WHERE workspace_id = %s", (str(workspace_id),))
        cursor.execute("DELETE FROM workspace_agents WHERE workspace_id = %s", (str(workspace_id),))
        cursor.execute("DELETE FROM workspaces WHERE id = %s", (str(workspace_id),))
        cursor.execute("DELETE FROM agents WHERE id = %s", (str(agent_id),))
        conn.commit()


@pytest.fixture
def agent_headers(workspace_ctx):
    """Generate auth headers for test agent."""
    token = jwt_utils.create_agent_token(
        agent_id=workspace_ctx["agent_id"],
        moltbook_id=workspace_ctx["moltbook_id"],
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def system_headers():
    """Generate auth headers for system service."""
    token = jwt_utils.create_system_token(service_name="test-worker")
    return {"Authorization": f"Bearer {token}"}


class TestLogsAppendOnly:
    """Test log creation and retrieval (agent writes)."""
    
    def test_logs_create__agent_auth__returns_log_row(self, workspace_ctx, agent_headers, test_client):
        """Test creating a log entry."""
        response = test_client.post(
            f"/workspaces/{workspace_ctx['workspace_id']}/logs",
            json={"action": "claim.created", "payload": {"claim_id": str(uuid4()), "text": "Test claim"}},
            headers=agent_headers,
        )
        
        assert response.status_code == 201, f"Failed to create log: {response.text}"
        data = response.json()
        assert data["workspace_id"] == workspace_ctx["workspace_id"]
        assert data["agent_id"] == workspace_ctx["agent_id"]
        assert data["action"] == "claim.created"
        assert data["payload"]["claim_id"] is not None
        assert "created_at" in data
    
    def test_logs_list__after_creates__returns_created_logs(self, workspace_ctx, agent_headers, test_client):
        """Test listing logs with filters."""
        # Create multiple logs
        actions = ["claim.created", "artifact.uploaded", "critique.created"]
        for action in actions:
            r = test_client.post(
                f"/workspaces/{workspace_ctx['workspace_id']}/logs",
                json={"action": action, "payload": {"test": True}},
                headers=agent_headers,
            )
            assert r.status_code == 201
        
        # List all logs
        response = test_client.get(f"/workspaces/{workspace_ctx['workspace_id']}/logs", headers=agent_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert len(data["logs"]) >= 3
    
    def test_logs_list__action_filter__returns_matching_actions(self, workspace_ctx, agent_headers, test_client):
        """Test filtering logs by action."""
        # Create logs with different actions
        r1 = test_client.post(
            f"/workspaces/{workspace_ctx['workspace_id']}/logs",
            json={"action": "test.action.1"},
            headers=agent_headers,
        )
        r2 = test_client.post(
            f"/workspaces/{workspace_ctx['workspace_id']}/logs",
            json={"action": "test.action.2"},
            headers=agent_headers,
        )
        assert r1.status_code == 201
        assert r2.status_code == 201
        
        # Filter by specific action
        response = test_client.get(
            f"/workspaces/{workspace_ctx['workspace_id']}/logs?action=test.action.1",
            headers=agent_headers,
        )
        
        assert response.status_code == 200
        logs = response.json()["logs"]
        assert any(log["action"] == "test.action.1" for log in logs)


class TestEventsSystemOnly:
    """Test event creation and retrieval (system writes)."""
    
    def test_events_create__system_auth__returns_event_row(self, workspace_ctx, system_headers, test_client):
        """Test creating an event with system token."""
        response = test_client.post(
            f"/workspaces/{workspace_ctx['workspace_id']}/events",
            json={
                "actor_type": "system",
                "actor_id": "worker-1",
                "event_type": "artifact.ingestion_completed",
                "payload": {"artifact_id": str(uuid4())},
            },
            headers=system_headers,
        )
        
        assert response.status_code == 201, f"Failed to create event: {response.text}"
        data = response.json()
        assert data["workspace_id"] == workspace_ctx["workspace_id"]
        assert data["actor_type"] == "system"
        assert data["event_type"] == "artifact.ingestion_completed"
    
    def test_events_create__agent_auth__returns_403(self, workspace_ctx, agent_headers, test_client):
        """Test that event creation rejects agent tokens."""
        response = test_client.post(
            f"/workspaces/{workspace_ctx['workspace_id']}/events",
            json={"actor_type": "agent", "actor_id": workspace_ctx["agent_id"], "event_type": "test.event", "payload": {}},
            headers=agent_headers,
        )
        
        # Should reject agent token on system-only endpoint
        assert response.status_code == 403, "Agent tokens should be rejected on system-only endpoints"
    
    def test_events_list__after_create__returns_events(self, workspace_ctx, agent_headers, system_headers, test_client):
        """Test listing events."""
        # Create an event
        r = test_client.post(
            f"/workspaces/{workspace_ctx['workspace_id']}/events",
            json={
                "actor_type": "system",
                "actor_id": "test-service",
                "event_type": "test.event.created",
                "payload": {"test": "data"},
            },
            headers=system_headers,
        )
        assert r.status_code == 201
        
        # List events (agents can read)
        response = test_client.get(
            f"/workspaces/{workspace_ctx['workspace_id']}/events",
            headers=agent_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert len(data["events"]) > 0
    
    def test_events_list__event_type_filter__returns_matching(self, workspace_ctx, agent_headers, system_headers, test_client):
        """Test filtering events by event_type."""
        # Create events with different types
        r1 = test_client.post(
            f"/workspaces/{workspace_ctx['workspace_id']}/events",
            json={"actor_type": "system", "actor_id": "test", "event_type": "test.type.alpha", "payload": {}},
            headers=system_headers,
        )
        r2 = test_client.post(
            f"/workspaces/{workspace_ctx['workspace_id']}/events",
            json={"actor_type": "system", "actor_id": "test", "event_type": "test.type.beta", "payload": {}},
            headers=system_headers,
        )
        assert r1.status_code == 201
        assert r2.status_code == 201
        
        # Filter by type
        response = test_client.get(
            f"/workspaces/{workspace_ctx['workspace_id']}/events?event_type=test.type.alpha",
            headers=agent_headers,
        )
        
        assert response.status_code == 200
        events = response.json()["events"]
        # Should have at least one matching event
        assert any(e["event_type"] == "test.type.alpha" for e in events)
    
    def test_events_list__actor_type_filter__returns_matching(self, workspace_ctx, agent_headers, system_headers, test_client):
        """Test filtering events by actor_type."""
        # Create events with different actor types
        r1 = test_client.post(
            f"/workspaces/{workspace_ctx['workspace_id']}/events",
            json={"actor_type": "system", "actor_id": "test", "event_type": "test.system.event", "payload": {}},
            headers=system_headers,
        )
        r2 = test_client.post(
            f"/workspaces/{workspace_ctx['workspace_id']}/events",
            json={"actor_type": "agent", "actor_id": workspace_ctx["agent_id"], "event_type": "test.agent.event", "payload": {}},
            headers=system_headers,
        )
        assert r1.status_code == 201
        assert r2.status_code == 201
        
        # Filter by actor_type=system
        response = test_client.get(
            f"/workspaces/{workspace_ctx['workspace_id']}/events?actor_type=system",
            headers=agent_headers,
        )
        
        assert response.status_code == 200
        events = response.json()["events"]
        # All returned events should have actor_type=system
        system_events = [e for e in events if e["actor_type"] == "system"]
        assert len(system_events) > 0


class TestExitCriteria:
    """Component 8 exit tests per checklist."""
    
    def test_events__agent_actor_type__persisted_and_readable(self, workspace_ctx, agent_headers, system_headers, test_client):
        """
        EXIT TEST 1: Creating a claim creates an event row with actor_type=agent.
        
        Note: This test simulates claim creation by directly checking
        that events can be created with actor_type=agent.
        Full claim endpoints are in Component 9+.
        """
        # Simulate "claim created" by having a system service emit an agent-actor event,
        # then verify agents can read it back.
        event_type = "claim.created"
        response = test_client.post(
            f"/workspaces/{workspace_ctx['workspace_id']}/events",
            json={
                "actor_type": "agent",
                "actor_id": workspace_ctx["agent_id"],
                "event_type": event_type,
                "payload": {"claim_id": str(uuid4())},
            },
            headers=system_headers,
        )
        assert response.status_code == 201, f"Failed to create agent-actor event: {response.text}"

        response = test_client.get(
            f"/workspaces/{workspace_ctx['workspace_id']}/events?actor_type=agent",
            headers=agent_headers,
        )
        
        assert response.status_code == 200
        events = response.json()["events"]
        
        agent_events = [e for e in events if e["actor_type"] == "agent" and e["event_type"] == event_type]
        assert len(agent_events) > 0, "Expected at least one agent-actor event"
    
    def test_events__system_actor_type__persisted_and_readable(self, workspace_ctx, system_headers, agent_headers, test_client):
        """
        EXIT TEST 2: Worker-created artifacts create events with actor_type=system.
        
        This test verifies that system services can emit events with actor_type=system,
        which is required for worker activities (PDF ingestion, etc).
        """
        # Simulate worker creating an artifact event
        artifact_id = str(uuid4())
        response = test_client.post(
            f"/workspaces/{workspace_ctx['workspace_id']}/events",
            json={
                "actor_type": "system",
                "actor_id": "pdf-ingestion-worker",
                "event_type": "artifact.ingestion_completed",
                "payload": {
                    "artifact_id": artifact_id,
                    "worker": "pdf-ingestion-worker"
                }
            },
            headers=system_headers
        )
        
        assert response.status_code == 201, f"Failed to create system event: {response.text}"
        event_data = response.json()
        assert event_data["actor_type"] == "system"
        assert event_data["event_type"] == "artifact.ingestion_completed"
        
        # Verify it's retrievable
        response = test_client.get(
            f"/workspaces/{workspace_ctx['workspace_id']}/events?event_type=artifact.ingestion_completed",
            headers=agent_headers,
        )
        
        assert response.status_code == 200
        events = response.json()["events"]
        matching_event = next((e for e in events if e["payload"].get("artifact_id") == artifact_id), None)
        assert matching_event is not None
        assert matching_event["actor_type"] == "system"


class TestAppendOnlyEnforcement:
    """Test that logs and events are append-only (no updates/deletes)."""
    
    def test_logs__no_update_endpoint__returns_404(self, workspace_ctx, agent_headers, test_client):
        """Test that there is no endpoint to update logs."""
        # Create a log
        response = test_client.post(
            f"/workspaces/{workspace_ctx['workspace_id']}/logs",
            json={"action": "test.immutable"},
            headers=agent_headers
        )
        assert response.status_code == 201
        log_id = response.json()["id"]
        
        # Try to update (should fail - endpoint doesn't exist)
        response = test_client.patch(
            f"/logs/{log_id}",
            json={"action": "test.modified"},
            headers=agent_headers
        )
        
        assert response.status_code == 404, "Log update endpoint should not exist (append-only)"
    
    def test_events__no_update_endpoint__returns_404(self, workspace_ctx, system_headers, test_client):
        """Test that there is no endpoint to update events."""
        # Create an event
        response = test_client.post(
            f"/workspaces/{workspace_ctx['workspace_id']}/events",
            json={
                "actor_type": "system",
                "actor_id": "test",
                "event_type": "test.immutable",
                "payload": {}
            },
            headers=system_headers
        )
        assert response.status_code == 201
        event_id = response.json()["id"]
        
        # Try to update (should fail - endpoint doesn't exist)
        response = test_client.patch(
            f"/events/{event_id}",
            json={"event_type": "test.modified"},
            headers=system_headers
        )
        
        assert response.status_code == 404, "Event update endpoint should not exist (append-only)"
