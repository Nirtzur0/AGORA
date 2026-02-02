"""
Integration tests for RBAC (Role-Based Access Control).

Tests permission enforcement across all 6 roles with canonical permission keys.
"""

import pytest
import sys
import os
from pathlib import Path

# Add packages to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "packages" / "db"))
sys.path.insert(0, str(repo_root / "apps" / "core-api"))

from database import get_db
import rbac
import uuid


class TestRoleSeeding:
    """Test that roles are seeded correctly."""
    
    def test_all_roles_exist(self):
        """All 6 MVP roles should exist."""
        with get_db() as db:
            roles = rbac.list_all_roles(db)
        
        role_names = {r["name"] for r in roles}
        expected_roles = {
            "Maintainer",
            "Literature Analyst",
            "Experimentalist",
            "Method Reviewer",
            "Skeptic",
            "Synthesizer",
        }
        
        assert role_names == expected_roles, f"Expected {expected_roles}, got {role_names}"
    
    def test_maintainer_permissions(self):
        """Maintainer has full access."""
        with get_db() as db:
            roles = rbac.list_all_roles(db)
        maintainer = next(r for r in roles if r["name"] == "Maintainer")
        
        perms = set(maintainer["permissions"]["allow"])
        
        # Check key permissions
        assert "workspace.create" in perms
        assert "workspace.update" in perms
        assert "execution.request.run_sandbox" in perms
        assert "join_request.review" in perms
        assert "draft.create" in perms
        assert "critique.resolve" in perms
        
        # Should have 20+ permissions
        assert len(perms) >= 20
    
    def test_literature_analyst_permissions(self):
        """Literature Analyst can ingest PDFs and create claims."""
        with get_db() as db:
            roles = rbac.list_all_roles(db)
        analyst = next(r for r in roles if r["name"] == "Literature Analyst")
        
        perms = set(analyst["permissions"]["allow"])
        
        assert "artifact.request.ingest_pdf" in perms
        assert "claim.create" in perms
        assert "claim.evidence.add" in perms
        assert "workspace.read" in perms
        
        # Should NOT have sandbox execution
        assert "execution.request.run_sandbox" not in perms
    
    def test_experimentalist_permissions(self):
        """Experimentalist can run sandbox."""
        with get_db() as db:
            roles = rbac.list_all_roles(db)
        exp = next(r for r in roles if r["name"] == "Experimentalist")
        
        perms = set(exp["permissions"]["allow"])
        
        assert "execution.request.run_sandbox" in perms
        assert "artifact.request.ingest_repo" in perms
        assert "artifact.version.create" in perms
        assert "claim.create" in perms
        
        # Should NOT have draft permissions
        assert "draft.create" not in perms
    
    def test_synthesizer_permissions(self):
        """Synthesizer can create drafts but NOT run sandbox."""
        with get_db() as db:
            roles = rbac.list_all_roles(db)
        synth = next(r for r in roles if r["name"] == "Synthesizer")
        
        perms = set(synth["permissions"]["allow"])
        
        # CAN create drafts
        assert "draft.create" in perms
        assert "draft.version.create" in perms
        
        # CAN read
        assert "claim.read" in perms
        assert "critique.read" in perms
        
        # CANNOT run sandbox
        assert "execution.request.run_sandbox" not in perms
        
        # CANNOT create claims
        assert "claim.create" not in perms
    
    def test_reputation_requirements(self):
        """Roles have correct reputation requirements."""
        with get_db() as db:
            roles = {r["name"]: r for r in rbac.list_all_roles(db)}
        
        assert roles["Maintainer"]["min_reputation"] == 0
        assert roles["Literature Analyst"]["min_reputation"] == 100
        assert roles["Experimentalist"]["min_reputation"] == 200
        assert roles["Method Reviewer"]["min_reputation"] == 300
        assert roles["Skeptic"]["min_reputation"] == 250
        assert roles["Synthesizer"]["min_reputation"] == 200


class TestPermissionChecking:
    """Test permission checking logic."""
    
    @pytest.fixture
    def test_workspace(self):
        """Create a test workspace."""
        with get_db() as db:
            workspace_id = str(uuid.uuid4())
            
            db.execute(
                """
                INSERT INTO workspaces (id, name, phase, reputation_config)
                VALUES (%s, %s, %s, %s)
                """,
                (workspace_id, "Test Workspace", "setup", {})
            )
            db.commit()
        
        yield workspace_id
        
        # Cleanup
        with get_db() as db:
            db.execute("DELETE FROM workspaces WHERE id = %s", (workspace_id,))
            db.commit()
    
    @pytest.fixture
    def test_agent(self):
        """Create a test agent."""
        with get_db() as db:
            agent_id = str(uuid.uuid4())
            
            db.execute(
                """
                INSERT INTO agents (id, moltbook_id, reputation, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                """,
                (agent_id, f"moltbook-{agent_id}", 200)
            )
            db.commit()
        
        yield agent_id
        
        # Cleanup
        with get_db() as db:
            db.execute("DELETE FROM agents WHERE id = %s", (agent_id,))
            db.commit()
    
    def test_agent_not_in_workspace(self, test_workspace, test_agent):
        """Agent not in workspace should fail permission check."""
        with get_db() as db:
            has_perm = rbac.check_permission(
                db,
                test_agent,
                test_workspace,
                "workspace.read"
            )
        
        assert not has_perm
    
    def test_experimentalist_can_run_sandbox(self, test_workspace, test_agent):
        """Experimentalist should be able to request sandbox execution."""
        with get_db() as db:
            # Get Experimentalist role
            exp_role = db.execute(
                "SELECT id FROM roles WHERE name = %s",
                ("Experimentalist",)
            ).fetchone()
            
            # Add agent to workspace as Experimentalist
            db.execute(
                """
                INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status)
                VALUES (%s, %s, %s, %s)
                """,
                (test_workspace, test_agent, exp_role[0], "active")
            )
            db.commit()
            
            # Check permission
            has_perm = rbac.check_permission(
                db,
                test_agent,
                test_workspace,
                "execution.request.run_sandbox"
            )
        
        assert has_perm, "Experimentalist should have sandbox execution permission"
        
        # Cleanup
        with get_db() as db:
            db.execute(
                "DELETE FROM workspace_agents WHERE workspace_id = %s AND agent_id = %s",
                (test_workspace, test_agent)
            )
            db.commit()
    
    def test_synthesizer_cannot_run_sandbox(self, test_workspace, test_agent):
        """Synthesizer should NOT be able to request sandbox execution."""
        with get_db() as db:
            # Get Synthesizer role
            synth_role = db.execute(
                "SELECT id FROM roles WHERE name = %s",
                ("Synthesizer",)
            ).fetchone()
            
            # Add agent to workspace as Synthesizer
            db.execute(
                """
                INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status)
                VALUES (%s, %s, %s, %s)
                """,
                (test_workspace, test_agent, synth_role[0], "active")
            )
            db.commit()
            
            # Check permission
            has_perm = rbac.check_permission(
                db,
                test_agent,
                test_workspace,
                "execution.request.run_sandbox"
            )
            
            assert not has_perm, "Synthesizer should NOT have sandbox execution permission"
            
            # But Synthesizer CAN create drafts
            can_draft = rbac.check_permission(
                db,
                test_agent,
                test_workspace,
                "draft.create"
            )
        
        assert can_draft, "Synthesizer should have draft creation permission"
        
        # Cleanup
        with get_db() as db:
            db.execute(
                "DELETE FROM workspace_agents WHERE workspace_id = %s AND agent_id = %s",
                (test_workspace, test_agent)
            )
            db.commit()
    
    def test_maintainer_has_all_permissions(self, test_workspace, test_agent):
        """Maintainer should have all key permissions."""
        with get_db() as db:
            # Get Maintainer role
            maint_role = db.execute(
                "SELECT id FROM roles WHERE name = %s",
                ("Maintainer",)
            ).fetchone()
            
            # Add agent to workspace as Maintainer
            db.execute(
                """
                INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status)
                VALUES (%s, %s, %s, %s)
                """,
                (test_workspace, test_agent, maint_role[0], "active")
            )
            db.commit()
            
            # Check multiple permissions
            permissions_to_check = [
                "workspace.create",
                "workspace.update",
                "execution.request.run_sandbox",
                "draft.create",
                "critique.resolve",
                "claim.create",
            ]
            
            for perm in permissions_to_check:
                has_perm = rbac.check_permission(
                    db,
                    test_agent,
                    test_workspace,
                    perm
                )
                assert has_perm, f"Maintainer should have {perm} permission"
        
        # Cleanup
        with get_db() as db:
            db.execute(
                "DELETE FROM workspace_agents WHERE workspace_id = %s AND agent_id = %s",
                (test_workspace, test_agent)
            )
            db.commit()
    
    def test_require_permission_raises_on_deny(self, test_workspace, test_agent):
        """require_permission should raise HTTPException when denied."""
        with get_db() as db:
            # Get Synthesizer role (no sandbox permission)
            synth_role = db.execute(
                "SELECT id FROM roles WHERE name = %s",
                ("Synthesizer",)
            ).fetchone()
            
            # Add agent to workspace as Synthesizer
            db.execute(
                """
                INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status)
                VALUES (%s, %s, %s, %s)
                """,
                (test_workspace, test_agent, synth_role[0], "active")
            )
            db.commit()
            
            # Should raise HTTPException
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                rbac.require_permission(
                    db,
                    test_agent,
                    test_workspace,
                    "execution.request.run_sandbox",
                    agent_role="Synthesizer"
                )
        
        assert exc_info.value.status_code == 403
        assert "PERMISSION_DENIED" in exc_info.value.detail["error"]
        
        # Cleanup
        with get_db() as db:
            db.execute(
                "DELETE FROM workspace_agents WHERE workspace_id = %s AND agent_id = %s",
                (test_workspace, test_agent)
            )
            db.commit()


class TestReputationChecking:
    """Test reputation requirements."""
    
    def test_low_reputation_fails_analyst_check(self):
        """Agent with reputation < 100 should fail Literature Analyst check."""
        with get_db() as db:
            # Create agent with low reputation
            agent_id = str(uuid.uuid4())
            db.execute(
                """
                INSERT INTO agents (id, moltbook_id, reputation, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                """,
                (agent_id, f"moltbook-{agent_id}", 50)
            )
            db.commit()
            
            # Check reputation requirement
            meets_req = rbac.check_reputation_requirement(db, agent_id, "Literature Analyst")
            
            # Cleanup
            db.execute("DELETE FROM agents WHERE id = %s", (agent_id,))
            db.commit()
        
        assert not meets_req
    
    def test_high_reputation_passes_all_checks(self):
        """Agent with reputation >= 300 should pass all role checks."""
        with get_db() as db:
            # Create agent with high reputation
            agent_id = str(uuid.uuid4())
            db.execute(
                """
                INSERT INTO agents (id, moltbook_id, reputation, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                """,
                (agent_id, f"moltbook-{agent_id}", 300)
            )
            db.commit()
            
            # Check all roles
            roles = [
                "Maintainer",
                "Literature Analyst",
                "Experimentalist",
                "Method Reviewer",
                "Skeptic",
                "Synthesizer",
            ]
            
            results = {}
            for role in roles:
                results[role] = rbac.check_reputation_requirement(db, agent_id, role)
            
            # Cleanup
            db.execute("DELETE FROM agents WHERE id = %s", (agent_id,))
            db.commit()
        
        for role, meets_req in results.items():
            assert meets_req, f"Agent with rep 300 should meet {role} requirement"


class TestRoleRetrieval:
    """Test get_agent_role function."""
    
    @pytest.fixture
    def test_setup(self):
        """Create workspace, agent, and assign role."""
        with get_db() as db:
            workspace_id = str(uuid.uuid4())
            agent_id = str(uuid.uuid4())
            
            # Create workspace
            db.execute(
                """
                INSERT INTO workspaces (id, name, phase, reputation_config)
                VALUES (%s, %s, %s, %s)
                """,
                (workspace_id, "Test Workspace", "setup", {})
            )
            
            # Create agent
            db.execute(
                """
                INSERT INTO agents (id, moltbook_id, reputation, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                """,
                (agent_id, f"moltbook-{agent_id}", 200)
            )
            
            # Get Experimentalist role
            exp_role = db.execute(
                "SELECT id FROM roles WHERE name = %s",
                ("Experimentalist",)
            ).fetchone()
            
            # Assign role
            db.execute(
                """
                INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status)
                VALUES (%s, %s, %s, %s)
                """,
                (workspace_id, agent_id, exp_role[0], "active")
            )
            db.commit()
        
        yield {"workspace_id": workspace_id, "agent_id": agent_id}
        
        # Cleanup
        with get_db() as db:
            db.execute("DELETE FROM workspace_agents WHERE workspace_id = %s", (workspace_id,))
            db.execute("DELETE FROM workspaces WHERE id = %s", (workspace_id,))
            db.execute("DELETE FROM agents WHERE id = %s", (agent_id,))
            db.commit()
    
    def test_get_agent_role_returns_correct_info(self, test_setup):
        """get_agent_role should return role_id, role_name, and permissions."""
        with get_db() as db:
            role_info = rbac.get_agent_role(
                db,
                test_setup["agent_id"],
                test_setup["workspace_id"]
            )
        
        assert role_info is not None
        assert role_info["role_name"] == "Experimentalist"
        assert "permissions" in role_info
        assert "allow" in role_info["permissions"]
        assert "execution.request.run_sandbox" in role_info["permissions"]["allow"]
    
    def test_get_agent_role_returns_none_for_nonmember(self):
        """get_agent_role should return None for non-member."""
        fake_agent = str(uuid.uuid4())
        fake_workspace = str(uuid.uuid4())
        
        with get_db() as db:
            role_info = rbac.get_agent_role(db, fake_agent, fake_workspace)
        
        assert role_info is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
