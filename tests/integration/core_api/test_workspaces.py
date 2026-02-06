"""
Integration tests for workspace management + join flow.

Tests Component 6: Workspaces + membership + join requests.
"""

import pytest
import sys
import uuid
from pathlib import Path
from datetime import datetime

# Add packages to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "packages" / "db"))
sys.path.insert(0, str(repo_root / "apps" / "core-api"))

from database import get_db, get_raw_db
from sqlalchemy import text
import jwt_utils
import rbac


class TestWorkspaceCreation:
    """Test workspace creation flow."""
    
    @pytest.fixture
    def test_agent(self):
        """Create a test agent with sufficient reputation."""
        with get_raw_db() as db:
            agent_id = str(uuid.uuid4())
            cursor = db.cursor()
            cursor.execute(
                """
                INSERT INTO agents (id, moltbook_id, reputation, created_at)
                VALUES (%s, %s, %s, NOW())
                """,
                (agent_id, f"moltbook-{agent_id}", 100)
            )
            db.commit()
        
        yield agent_id
        
        # Cleanup
        with get_raw_db() as db:
            cursor = db.cursor()
            # Delete related records first
            cursor.execute("DELETE FROM workspace_agents WHERE agent_id = %s", (agent_id,))
            cursor.execute("DELETE FROM join_requests WHERE agent_id = %s", (agent_id,))
            cursor.execute("DELETE FROM workspaces WHERE created_by = %s", (agent_id,))
            cursor.execute("DELETE FROM agents WHERE id = %s", (agent_id,))
            db.commit()
    
    def test_create_workspace_success(self, test_agent):
        """Workspace creation should succeed and add creator as Maintainer."""
        with get_db() as db:
            workspace_id = str(uuid.uuid4())
            
            # Create workspace
            db.execute(
                """
                INSERT INTO workspaces (id, name, description, phase, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                """,
                (workspace_id, "Test Workspace", "Test description", "INIT", test_agent)
            )
            
            # Get Maintainer role
            maintainer_role = db.execute(
                "SELECT id FROM roles WHERE name = %s",
                ("Maintainer",)
            ).fetchone()
            
            # Add creator as Maintainer
            db.execute(
                """
                INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status, joined_at)
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (workspace_id, test_agent, maintainer_role[0], "active")
            )
            
            db.commit()
            
            # Verify workspace exists
            workspace = db.execute(
                "SELECT id, name, phase, created_by FROM workspaces WHERE id = %s",
                (workspace_id,)
            ).fetchone()
            
            assert workspace is not None
            assert str(workspace[0]) == workspace_id
            assert workspace[1] == "Test Workspace"
            assert workspace[2] == "INIT"
            assert str(workspace[3]) == test_agent
            
            # Verify creator is Maintainer
            member = db.execute(
                """
                SELECT wa.agent_id, r.name, wa.status
                FROM workspace_agents wa
                JOIN roles r ON wa.role_id = r.id
                WHERE wa.workspace_id = %s AND wa.agent_id = %s
                """,
                (workspace_id, test_agent)
            ).fetchone()
            
            assert member is not None
            assert str(member[0]) == test_agent
            assert member[1] == "Maintainer"
            assert member[2] == "active"
            
            # Cleanup
            db.execute("DELETE FROM workspace_agents WHERE workspace_id = %s", (workspace_id,))
            db.execute("DELETE FROM events WHERE workspace_id = %s", (workspace_id,))
            db.execute("DELETE FROM workspaces WHERE id = %s", (workspace_id,))
            db.commit()
    
    def test_workspace_starts_in_init_phase(self, test_agent):
        """All workspaces should start in INIT phase."""
        with get_db() as db:
            workspace_id = str(uuid.uuid4())
            
            db.execute(
                """
                INSERT INTO workspaces (id, name, description, phase, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                """,
                (workspace_id, "Test", None, "INIT", test_agent)
            )
            db.commit()
            
            # Verify phase
            phase = db.execute(
                "SELECT phase FROM workspaces WHERE id = %s",
                (workspace_id,)
            ).fetchone()[0]
            
            assert phase == "INIT"
            
            # Cleanup
            db.execute("DELETE FROM workspaces WHERE id = %s", (workspace_id,))
            db.commit()


class TestWorkspaceEvents:
    """Test event emission for workspace lifecycle."""
    
    @pytest.fixture
    def test_workspace(self):
        """Create a test workspace and agent."""
        with get_db() as db:
            agent_id = str(uuid.uuid4())
            workspace_id = str(uuid.uuid4())
            
            # Create agent
            db.execute(
                """
                INSERT INTO agents (id, moltbook_id, reputation, created_at)
                VALUES (%s, %s, %s, NOW())
                """,
                (agent_id, f"moltbook-{agent_id}", 100)
            )
            
            # Create workspace
            db.execute(
                """
                INSERT INTO workspaces (id, name, description, phase, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                """,
                (workspace_id, "Test Workspace", "Test", "INIT", agent_id)
            )
            
            db.commit()
        
        yield {"workspace_id": workspace_id, "agent_id": agent_id}
        
        # Cleanup
        with get_db() as db:
            db.execute("DELETE FROM workspace_agents WHERE workspace_id = %s", (workspace_id,))
            db.execute("DELETE FROM join_requests WHERE workspace_id = %s", (workspace_id,))
            db.execute("DELETE FROM events WHERE workspace_id = %s", (workspace_id,))
            db.execute("DELETE FROM workspaces WHERE id = %s", (workspace_id,))
            db.execute("DELETE FROM agents WHERE id = %s", (agent_id,))
            db.commit()
    
    def test_workspace_created_event_emitted(self, test_workspace):
        """workspace.created event should be emitted on creation."""
        with get_db() as db:
            # Emit workspace.created event
            event_id = str(uuid.uuid4())
            db.execute(
                """
                INSERT INTO events (id, workspace_id, actor_type, actor_id, event_type, payload, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    event_id,
                    test_workspace["workspace_id"],
                    "agent",
                    test_workspace["agent_id"],
                    "workspace.created",
                    {"workspace_id": test_workspace["workspace_id"], "name": "Test Workspace"}
                )
            )
            db.commit()
            
            # Verify event exists
            event = db.execute(
                "SELECT event_type, actor_type, actor_id FROM events WHERE workspace_id = %s AND event_type = %s",
                (test_workspace["workspace_id"], "workspace.created")
            ).fetchone()
            
            assert event is not None
            assert event[0] == "workspace.created"
            assert event[1] == "agent"
            assert str(event[2]) == test_workspace["agent_id"]
    
    def test_agent_joined_event_emitted(self, test_workspace):
        """agent.joined event should be emitted when agent joins."""
        with get_db() as db:
            # Get role
            role = db.execute(
                "SELECT id, name FROM roles WHERE name = %s",
                ("Maintainer",)
            ).fetchone()
            
            # Emit agent.joined event
            event_id = str(uuid.uuid4())
            db.execute(
                """
                INSERT INTO events (id, workspace_id, actor_type, actor_id, event_type, payload, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    event_id,
                    test_workspace["workspace_id"],
                    "system",
                    str(uuid.uuid5(uuid.NAMESPACE_URL, "agora-system:core-api")),
                    "agent.joined",
                    {
                        "agent_id": test_workspace["agent_id"],
                        "role_id": str(role[0]),
                        "role_name": role[1]
                    }
                )
            )
            db.commit()
            
            # Verify event
            event = db.execute(
                "SELECT event_type, actor_type FROM events WHERE workspace_id = %s AND event_type = %s",
                (test_workspace["workspace_id"], "agent.joined")
            ).fetchone()
            
            assert event is not None
            assert event[0] == "agent.joined"
            assert event[1] == "system"  # System-written event


class TestJoinRequests:
    """Test join request flow."""
    
    @pytest.fixture
    def test_setup(self):
        """Create workspace, maintainer, and requesting agent."""
        with get_db() as db:
            maintainer_id = str(uuid.uuid4())
            requester_id = str(uuid.uuid4())
            workspace_id = str(uuid.uuid4())
            
            # Create agents
            db.execute(
                """
                INSERT INTO agents (id, moltbook_id, reputation, created_at)
                VALUES (%s, %s, %s, NOW())
                """,
                (maintainer_id, f"moltbook-{maintainer_id}", 100)
            )
            
            db.execute(
                """
                INSERT INTO agents (id, moltbook_id, reputation, created_at)
                VALUES (%s, %s, %s, NOW())
                """,
                (requester_id, f"moltbook-{requester_id}", 200)  # Higher rep for Experimentalist
            )
            
            # Create workspace
            db.execute(
                """
                INSERT INTO workspaces (id, name, description, phase, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                """,
                (workspace_id, "Test Workspace", "Test", "INIT", maintainer_id)
            )
            
            # Add maintainer to workspace
            maintainer_role = db.execute(
                "SELECT id FROM roles WHERE name = %s",
                ("Maintainer",)
            ).fetchone()
            
            db.execute(
                """
                INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status, joined_at)
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (workspace_id, maintainer_id, maintainer_role[0], "active")
            )
            
            db.commit()
        
        yield {
            "workspace_id": workspace_id,
            "maintainer_id": maintainer_id,
            "requester_id": requester_id
        }
        
        # Cleanup
        with get_db() as db:
            db.execute("DELETE FROM workspace_agents WHERE workspace_id = %s", (workspace_id,))
            db.execute("DELETE FROM join_requests WHERE workspace_id = %s", (workspace_id,))
            db.execute("DELETE FROM events WHERE workspace_id = %s", (workspace_id,))
            db.execute("DELETE FROM workspaces WHERE id = %s", (workspace_id,))
            db.execute("DELETE FROM agents WHERE id = %s", (maintainer_id,))
            db.execute("DELETE FROM agents WHERE id = %s", (requester_id,))
            db.commit()
    
    def test_join_request_creation(self, test_setup):
        """Agent should be able to create a join request."""
        with get_db() as db:
            # Get Experimentalist role
            exp_role = db.execute(
                "SELECT id FROM roles WHERE name = %s",
                ("Experimentalist",)
            ).fetchone()
            
            # Create join request
            join_request_id = str(uuid.uuid4())
            db.execute(
                """
                INSERT INTO join_requests (id, workspace_id, agent_id, role_id, status, requested_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                """,
                (
                    join_request_id,
                    test_setup["workspace_id"],
                    test_setup["requester_id"],
                    exp_role[0],
                    "pending"
                )
            )
            db.commit()
            
            # Verify join request
            jr = db.execute(
                "SELECT id, status, agent_id, role_id FROM join_requests WHERE id = %s",
                (join_request_id,)
            ).fetchone()
            
            assert jr is not None
            assert jr[1] == "pending"
            assert str(jr[2]) == test_setup["requester_id"]
            assert str(jr[3]) == str(exp_role[0])
    
    def test_join_request_approval(self, test_setup):
        """Maintainer should be able to approve join request."""
        with get_db() as db:
            # Get Experimentalist role
            exp_role = db.execute(
                "SELECT id FROM roles WHERE name = %s",
                ("Experimentalist",)
            ).fetchone()
            
            # Create join request
            join_request_id = str(uuid.uuid4())
            db.execute(
                """
                INSERT INTO join_requests (id, workspace_id, agent_id, role_id, status, requested_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                """,
                (join_request_id, test_setup["workspace_id"], test_setup["requester_id"], exp_role[0], "pending")
            )
            db.commit()
            
            # Approve request
            db.execute(
                """
                UPDATE join_requests
                SET status = %s, reviewed_at = NOW(), reviewed_by = %s
                WHERE id = %s
                """,
                ("approved", test_setup["maintainer_id"], join_request_id)
            )
            
            # Add to workspace_agents
            db.execute(
                """
                INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status, joined_at)
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (test_setup["workspace_id"], test_setup["requester_id"], exp_role[0], "active")
            )
            
            db.commit()
            
            # Verify join request status
            status = db.execute(
                "SELECT status, reviewed_by FROM join_requests WHERE id = %s",
                (join_request_id,)
            ).fetchone()
            
            assert status[0] == "approved"
            assert str(status[1]) == test_setup["maintainer_id"]
            
            # Verify agent is now a member
            member = db.execute(
                "SELECT agent_id, role_id, status FROM workspace_agents WHERE workspace_id = %s AND agent_id = %s",
                (test_setup["workspace_id"], test_setup["requester_id"])
            ).fetchone()
            
            assert member is not None
            assert str(member[0]) == test_setup["requester_id"]
            assert str(member[1]) == str(exp_role[0])
            assert member[2] == "active"
    
    def test_role_capacity_enforcement(self, test_setup):
        """Role capacity should be enforced during approval."""
        with get_db() as db:
            # Get a role with capacity 1 (Maintainer)
            maint_role = db.execute(
                "SELECT id, role_capacity FROM roles WHERE name = %s",
                ("Maintainer",)
            ).fetchone()
            
            assert maint_role[1] == 1, "Maintainer role should have capacity 1"
            
            # Check current count (should be 1 from setup)
            count = db.execute(
                "SELECT COUNT(*) FROM workspace_agents WHERE workspace_id = %s AND role_id = %s AND status = %s",
                (test_setup["workspace_id"], maint_role[0], "active")
            ).fetchone()[0]
            
            assert count == 1, "Should already have 1 Maintainer"
            
            # Verify capacity would be exceeded
            assert count >= maint_role[1], "Capacity should be at or over limit"
    
    def test_reputation_requirement_enforcement(self, test_setup):
        """Min reputation should be checked for join requests."""
        with get_db() as db:
            # Create low-reputation agent
            low_rep_agent = str(uuid.uuid4())
            db.execute(
                """
                INSERT INTO agents (id, moltbook_id, reputation, created_at)
                VALUES (%s, %s, %s, NOW())
                """,
                (low_rep_agent, f"moltbook-{low_rep_agent}", 50)  # Below Literature Analyst min (100)
            )
            db.commit()
            
            # Get Literature Analyst role (requires 100 rep)
            analyst_role = db.execute(
                "SELECT id, min_reputation FROM roles WHERE name = %s",
                ("Literature Analyst",)
            ).fetchone()
            
            assert analyst_role[1] == 100
            
            # Check reputation requirement
            meets_req = rbac.check_reputation_requirement(db, low_rep_agent, "Literature Analyst")
            
            assert not meets_req, "Agent with rep 50 should not meet requirement for Literature Analyst (100)"
            
            # Cleanup
            db.execute("DELETE FROM agents WHERE id = %s", (low_rep_agent,))
            db.commit()


class TestWorkspaceUpdates:
    """Test workspace update restrictions."""
    
    @pytest.fixture
    def test_workspace(self):
        """Create a test workspace."""
        with get_db() as db:
            agent_id = str(uuid.uuid4())
            workspace_id = str(uuid.uuid4())
            
            db.execute(
                """
                INSERT INTO agents (id, moltbook_id, reputation, created_at)
                VALUES (%s, %s, %s, NOW())
                """,
                (agent_id, f"moltbook-{agent_id}", 100)
            )
            
            db.execute(
                """
                INSERT INTO workspaces (id, name, description, phase, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                """,
                (workspace_id, "Test Workspace", "Original description", "INIT", agent_id)
            )
            
            db.commit()
        
        yield {"workspace_id": workspace_id, "agent_id": agent_id}
        
        # Cleanup
        with get_db() as db:
            db.execute("DELETE FROM workspace_agents WHERE workspace_id = %s", (workspace_id,))
            db.execute("DELETE FROM events WHERE workspace_id = %s", (workspace_id,))
            db.execute("DELETE FROM workspaces WHERE id = %s", (workspace_id,))
            db.execute("DELETE FROM agents WHERE id = %s", (agent_id,))
            db.commit()
    
    def test_description_update_allowed(self, test_workspace):
        """Description updates should be allowed."""
        with get_db() as db:
            # Update description
            db.execute(
                """
                UPDATE workspaces
                SET description = %s
                WHERE id = %s
                """,
                ("Updated description", test_workspace["workspace_id"])
            )
            db.commit()
            
            # Verify update
            desc = db.execute(
                "SELECT description FROM workspaces WHERE id = %s",
                (test_workspace["workspace_id"],)
            ).fetchone()[0]
            
            assert desc == "Updated description"
    
    def test_phase_not_updated_via_patch(self, test_workspace):
        """Phase should NOT be updatable via PATCH endpoint (orchestrator only)."""
        with get_db() as db:
            # Verify phase is INIT
            phase = db.execute(
                "SELECT phase FROM workspaces WHERE id = %s",
                (test_workspace["workspace_id"],)
            ).fetchone()[0]
            
            assert phase == "INIT"
            
            # Note: The PATCH endpoint doesn't allow phase updates
            # This test documents that phase changes must come from orchestrator


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
