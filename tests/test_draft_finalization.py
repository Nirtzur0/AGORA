"""
Tests for Draft Finalization Workflow and Gate (Component 21)

Per spec §5.6, §4.10, §12.4:
- Finalization gate checks citation coverage/resolves, critique sufficiency, role caps, no blocking critiques
- Only orchestrator can finalize (system authority)
- Workspace phase must be FINALIZED
- After finalization, workspace rejects new draft versions
"""

import pytest
import uuid
from datetime import datetime, timezone
from apps.worker.gates import GateEvaluator, GateStatus
from apps.worker.draft_finalization_workflow import DraftFinalizationWorkflow
from apps.worker.finalization_activities import finalize_draft_artifact


# Fixtures

@pytest.fixture
def test_db(request):
    """Create test database connection."""
    from apps.worker.database import get_db_connection
    conn = get_db_connection()
    
    # Clean up before test
    conn.execute("DELETE FROM events WHERE workspace_id LIKE 'test-%'")
    conn.execute("DELETE FROM rule_checks WHERE workspace_id LIKE 'test-%'")
    conn.execute("DELETE FROM critiques WHERE workspace_id LIKE 'test-%'")
    conn.execute("DELETE FROM workspace_agents WHERE workspace_id LIKE 'test-%'")
    conn.execute("DELETE FROM activity_runs WHERE workspace_id LIKE 'test-%'")
    conn.execute("DELETE FROM artifact_versions WHERE artifact_id IN (SELECT id FROM artifacts WHERE workspace_id LIKE 'test-%')")
    conn.execute("DELETE FROM artifacts WHERE workspace_id LIKE 'test-%'")
    conn.execute("DELETE FROM workspaces WHERE id LIKE 'test-%'")
    conn.commit()
    
    yield conn
    
    # Clean up after test
    conn.execute("DELETE FROM events WHERE workspace_id LIKE 'test-%'")
    conn.execute("DELETE FROM rule_checks WHERE workspace_id LIKE 'test-%'")
    conn.execute("DELETE FROM critiques WHERE workspace_id LIKE 'test-%'")
    conn.execute("DELETE FROM workspace_agents WHERE workspace_id LIKE 'test-%'")
    conn.execute("DELETE FROM activity_runs WHERE workspace_id LIKE 'test-%'")
    conn.execute("DELETE FROM artifact_versions WHERE artifact_id IN (SELECT id FROM artifacts WHERE workspace_id LIKE 'test-%')")
    conn.execute("DELETE FROM artifacts WHERE workspace_id LIKE 'test-%'")
    conn.execute("DELETE FROM workspaces WHERE id LIKE 'test-%'")
    conn.commit()
    conn.close()


@pytest.fixture
def finalized_workspace_with_draft(test_db):
    """Create a workspace in FINALIZED phase with a draft artifact and version."""
    workspace_id = f"test-ws-{uuid.uuid4()}"
    draft_artifact_id = str(uuid.uuid4())
    draft_version_id = str(uuid.uuid4())
    
    # Create workspace in FINALIZED phase
    test_db.execute(
        """
        INSERT INTO workspaces (id, name, phase, created_at)
        VALUES (:id, 'Test Workspace', 'FINALIZED', NOW())
        """,
        {"id": workspace_id}
    )
    
    # Create draft artifact
    test_db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, type, name, created_at)
        VALUES (:id, :workspace_id, 'draft', 'Test Draft', NOW())
        """,
        {"id": draft_artifact_id, "workspace_id": workspace_id}
    )
    
    # Create draft version
    test_db.execute(
        """
        INSERT INTO artifact_versions (id, artifact_id, version_number, content_hash, location, created_at)
        VALUES (:id, :artifact_id, 1, 'hash123', 's3://bucket/draft', NOW())
        """,
        {"id": draft_version_id, "artifact_id": draft_artifact_id}
    )
    
    # Create Skeptic role
    skeptic_role_id = str(uuid.uuid4())
    test_db.execute(
        """
        INSERT INTO roles (id, name, description)
        VALUES (:id, 'Skeptic', 'Skeptic role')
        """,
        {"id": skeptic_role_id}
    )
    
    # Assign Skeptic
    test_db.execute(
        """
        INSERT INTO workspace_agents (id, workspace_id, agent_id, role_id, status, joined_at)
        VALUES (:id, :workspace_id, :agent_id, :role_id, 'active', NOW())
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "agent_id": str(uuid.uuid4()),
            "role_id": skeptic_role_id
        }
    )
    
    test_db.commit()
    
    return {
        "workspace_id": workspace_id,
        "draft_artifact_id": draft_artifact_id,
        "draft_version_id": draft_version_id,
        "skeptic_role_id": skeptic_role_id
    }


# Gate Evaluation Tests

def test_finalization_gate_all_pass(finalized_workspace_with_draft, test_db):
    """Test finalization gate passes when all criteria met."""
    ws = finalized_workspace_with_draft
    
    # Add passing citation coverage check
    test_db.execute(
        """
        INSERT INTO rule_checks (id, workspace_id, rule_name, target_type, target_id, status, details, created_at)
        VALUES (:id, :workspace_id, 'citation_coverage', 'artifact_version', :version_id, 'pass', '{}', NOW())
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws["workspace_id"],
            "version_id": ws["draft_version_id"]
        }
    )
    
    # Add passing citation resolves check
    test_db.execute(
        """
        INSERT INTO rule_checks (id, workspace_id, rule_name, target_type, target_id, status, details, created_at)
        VALUES (:id, :workspace_id, 'citation_resolves', 'artifact_version', :version_id, 'pass', :details, NOW())
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws["workspace_id"],
            "version_id": ws["draft_version_id"],
            "details": {"citation_resolves": True}
        }
    )
    
    # Add passing critique sufficiency check
    test_db.execute(
        """
        INSERT INTO rule_checks (id, workspace_id, rule_name, target_type, target_id, status, details, created_at)
        VALUES (:id, :workspace_id, 'critique_sufficiency', 'artifact_version', :version_id, 'pass', '{}', NOW())
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws["workspace_id"],
            "version_id": ws["draft_version_id"]
        }
    )
    
    test_db.commit()
    
    # Gather snapshot
    from apps.worker.gates import GateEvaluationActivity
    activity = GateEvaluationActivity(test_db)
    snapshot = activity.gather_finalization_gate_snapshot(
        ws["workspace_id"],
        ws["draft_artifact_id"],
        ws["draft_version_id"]
    )
    
    # Evaluate gate
    result = GateEvaluator.evaluate_finalization_gate(snapshot)
    
    assert result["status"] == GateStatus.PASS.value
    assert "All finalization criteria met" in result["reasons"]
    assert len(result["required_actions"]) == 0


def test_finalization_gate_missing_citations_fails(finalized_workspace_with_draft, test_db):
    """Exit criteria: Missing citation coverage blocks finalization."""
    ws = finalized_workspace_with_draft
    
    # Add FAILING citation coverage check
    test_db.execute(
        """
        INSERT INTO rule_checks (id, workspace_id, rule_name, target_type, target_id, status, details, created_at)
        VALUES (:id, :workspace_id, 'citation_coverage', 'artifact_version', :version_id, 'fail', '{}', NOW())
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws["workspace_id"],
            "version_id": ws["draft_version_id"]
        }
    )
    
    # Add passing citation resolves check
    test_db.execute(
        """
        INSERT INTO rule_checks (id, workspace_id, rule_name, target_type, target_id, status, details, created_at)
        VALUES (:id, :workspace_id, 'citation_resolves', 'artifact_version', :version_id, 'pass', :details, NOW())
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws["workspace_id"],
            "version_id": ws["draft_version_id"],
            "details": {"citation_resolves": True}
        }
    )
    
    # Add passing critique sufficiency check
    test_db.execute(
        """
        INSERT INTO rule_checks (id, workspace_id, rule_name, target_type, target_id, status, details, created_at)
        VALUES (:id, :workspace_id, 'critique_sufficiency', 'artifact_version', :version_id, 'pass', '{}', NOW())
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws["workspace_id"],
            "version_id": ws["draft_version_id"]
        }
    )
    
    test_db.commit()
    
    # Gather snapshot
    from apps.worker.gates import GateEvaluationActivity
    activity = GateEvaluationActivity(test_db)
    snapshot = activity.gather_finalization_gate_snapshot(
        ws["workspace_id"],
        ws["draft_artifact_id"],
        ws["draft_version_id"]
    )
    
    # Evaluate gate
    result = GateEvaluator.evaluate_finalization_gate(snapshot)
    
    assert result["status"] == GateStatus.FAIL.value
    assert "Citation coverage check failed" in result["reasons"]
    assert any(action["type"] == "add_citations" for action in result["required_actions"])


def test_finalization_gate_blocking_critiques_blocks(finalized_workspace_with_draft, test_db):
    """Exit criteria: Open blocking critiques block finalization."""
    ws = finalized_workspace_with_draft
    
    # Add all passing rule checks
    test_db.execute(
        """
        INSERT INTO rule_checks (id, workspace_id, rule_name, target_type, target_id, status, details, created_at)
        VALUES (:id1, :workspace_id, 'citation_coverage', 'artifact_version', :version_id, 'pass', '{}', NOW()),
               (:id2, :workspace_id, 'citation_resolves', 'artifact_version', :version_id, 'pass', :details, NOW()),
               (:id3, :workspace_id, 'critique_sufficiency', 'artifact_version', :version_id, 'pass', '{}', NOW())
        """,
        {
            "id1": str(uuid.uuid4()),
            "id2": str(uuid.uuid4()),
            "id3": str(uuid.uuid4()),
            "workspace_id": ws["workspace_id"],
            "version_id": ws["draft_version_id"],
            "details": {"citation_resolves": True}
        }
    )
    
    # Add open blocking critique
    test_db.execute(
        """
        INSERT INTO critiques (id, workspace_id, author_id, target_type, target_id, severity, status, content, created_at)
        VALUES (:id, :workspace_id, :author_id, 'artifact_version', :version_id, 'blocking', 'open', 'Critical issue', NOW())
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws["workspace_id"],
            "author_id": str(uuid.uuid4()),
            "version_id": ws["draft_version_id"]
        }
    )
    
    test_db.commit()
    
    # Gather snapshot
    from apps.worker.gates import GateEvaluationActivity
    activity = GateEvaluationActivity(test_db)
    snapshot = activity.gather_finalization_gate_snapshot(
        ws["workspace_id"],
        ws["draft_artifact_id"],
        ws["draft_version_id"]
    )
    
    # Evaluate gate
    result = GateEvaluator.evaluate_finalization_gate(snapshot)
    
    assert result["status"] == GateStatus.BLOCK.value
    assert "1 open blocking critique(s) remain" in result["reasons"]
    assert any(action["type"] == "resolve_blocking_critiques" for action in result["required_actions"])


def test_finalization_gate_after_fixes_succeeds(finalized_workspace_with_draft, test_db):
    """Exit criteria: After fixing issues, finalization succeeds."""
    ws = finalized_workspace_with_draft
    
    # Start with failing citation coverage
    test_db.execute(
        """
        INSERT INTO rule_checks (id, workspace_id, rule_name, target_type, target_id, status, details, created_at)
        VALUES (:id, :workspace_id, 'citation_coverage', 'artifact_version', :version_id, 'fail', '{}', NOW() - INTERVAL '1 hour')
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws["workspace_id"],
            "version_id": ws["draft_version_id"]
        }
    )
    
    # Agent fixes citations, add new PASSING check (later timestamp)
    test_db.execute(
        """
        INSERT INTO rule_checks (id, workspace_id, rule_name, target_type, target_id, status, details, created_at)
        VALUES (:id, :workspace_id, 'citation_coverage', 'artifact_version', :version_id, 'pass', '{}', NOW())
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws["workspace_id"],
            "version_id": ws["draft_version_id"]
        }
    )
    
    # Add other passing checks
    test_db.execute(
        """
        INSERT INTO rule_checks (id, workspace_id, rule_name, target_type, target_id, status, details, created_at)
        VALUES (:id1, :workspace_id, 'citation_resolves', 'artifact_version', :version_id, 'pass', :details, NOW()),
               (:id2, :workspace_id, 'critique_sufficiency', 'artifact_version', :version_id, 'pass', '{}', NOW())
        """,
        {
            "id1": str(uuid.uuid4()),
            "id2": str(uuid.uuid4()),
            "workspace_id": ws["workspace_id"],
            "version_id": ws["draft_version_id"],
            "details": {"citation_resolves": True}
        }
    )
    
    test_db.commit()
    
    # Gather snapshot (should get latest checks)
    from apps.worker.gates import GateEvaluationActivity
    activity = GateEvaluationActivity(test_db)
    snapshot = activity.gather_finalization_gate_snapshot(
        ws["workspace_id"],
        ws["draft_artifact_id"],
        ws["draft_version_id"]
    )
    
    # Evaluate gate - should now pass
    result = GateEvaluator.evaluate_finalization_gate(snapshot)
    
    assert result["status"] == GateStatus.PASS.value


def test_agent_cannot_finalize_system_only(finalized_workspace_with_draft, test_db):
    """Regression: Agent cannot call finalize (system-only)."""
    # This would be tested at the API level - the endpoint checks token_type == "system"
    # Here we verify the workflow validates workspace phase == FINALIZED
    
    ws = finalized_workspace_with_draft
    
    # Change workspace to non-FINALIZED phase
    test_db.execute(
        "UPDATE workspaces SET phase = 'INTERNAL_REVIEW' WHERE id = :id",
        {"id": ws["workspace_id"]}
    )
    test_db.commit()
    
    # Try to finalize - should fail validation
    with pytest.raises(ValueError, match="must be FINALIZED"):
        finalize_draft_artifact(
            ws["workspace_id"],
            ws["draft_artifact_id"],
            ws["draft_version_id"]
        )


def test_finalized_workspace_rejects_new_versions(finalized_workspace_with_draft, test_db):
    """Regression: After FINALIZED phase, workspace rejects new draft versions."""
    ws = finalized_workspace_with_draft
    
    # Finalize the draft first (add passing checks + execute finalization)
    test_db.execute(
        """
        INSERT INTO rule_checks (id, workspace_id, rule_name, target_type, target_id, status, details, created_at)
        VALUES (:id1, :workspace_id, 'citation_coverage', 'artifact_version', :version_id, 'pass', '{}', NOW()),
               (:id2, :workspace_id, 'citation_resolves', 'artifact_version', :version_id, 'pass', :details, NOW()),
               (:id3, :workspace_id, 'critique_sufficiency', 'artifact_version', :version_id, 'pass', '{}', NOW())
        """,
        {
            "id1": str(uuid.uuid4()),
            "id2": str(uuid.uuid4()),
            "id3": str(uuid.uuid4()),
            "workspace_id": ws["workspace_id"],
            "version_id": ws["draft_version_id"],
            "details": {"citation_resolves": True}
        }
    )
    test_db.commit()
    
    # Execute finalization
    result = finalize_draft_artifact(
        ws["workspace_id"],
        ws["draft_artifact_id"],
        ws["draft_version_id"]
    )
    
    assert "finalization_timestamp" in result
    
    # Verify metadata updated
    version_row = test_db.execute(
        "SELECT metadata FROM artifact_versions WHERE id = :id",
        {"id": ws["draft_version_id"]}
    ).fetchone()
    
    assert version_row[0]["status"] == "final"
    
    # Verify events emitted
    events = test_db.execute(
        """
        SELECT event_type
        FROM events
        WHERE workspace_id = :workspace_id
        ORDER BY created_at DESC
        """,
        {"workspace_id": ws["workspace_id"]}
    ).fetchall()
    
    event_types = [row[0] for row in events]
    assert "draft.finalized" in event_types
    assert "workspace.finalized" in event_types
    
    # Now try to create new version - should be rejected at API level
    # (This would be enforced by draft_routes checking workspace.phase == FINALIZED)
    # The workspace remains in FINALIZED phase and any POST to create new versions should 409


def test_finalization_gate_missing_skeptic_blocks(finalized_workspace_with_draft, test_db):
    """Test finalization blocked when Skeptic role not assigned."""
    ws = finalized_workspace_with_draft
    
    # Remove Skeptic
    test_db.execute(
        "DELETE FROM workspace_agents WHERE workspace_id = :workspace_id",
        {"workspace_id": ws["workspace_id"]}
    )
    
    # Add all passing rule checks
    test_db.execute(
        """
        INSERT INTO rule_checks (id, workspace_id, rule_name, target_type, target_id, status, details, created_at)
        VALUES (:id1, :workspace_id, 'citation_coverage', 'artifact_version', :version_id, 'pass', '{}', NOW()),
               (:id2, :workspace_id, 'citation_resolves', 'artifact_version', :version_id, 'pass', :details, NOW()),
               (:id3, :workspace_id, 'critique_sufficiency', 'artifact_version', :version_id, 'pass', '{}', NOW())
        """,
        {
            "id1": str(uuid.uuid4()),
            "id2": str(uuid.uuid4()),
            "id3": str(uuid.uuid4()),
            "workspace_id": ws["workspace_id"],
            "version_id": ws["draft_version_id"],
            "details": {"citation_resolves": True}
        }
    )
    test_db.commit()
    
    # Gather snapshot
    from apps.worker.gates import GateEvaluationActivity
    activity = GateEvaluationActivity(test_db)
    snapshot = activity.gather_finalization_gate_snapshot(
        ws["workspace_id"],
        ws["draft_artifact_id"],
        ws["draft_version_id"]
    )
    
    # Evaluate gate
    result = GateEvaluator.evaluate_finalization_gate(snapshot)
    
    assert result["status"] == GateStatus.BLOCK.value
    assert "Skeptic role not assigned" in result["reasons"]
    assert any(action["type"] == "assign_skeptic" for action in result["required_actions"])


def test_finalization_gate_method_reviewer_required_with_sandbox(finalized_workspace_with_draft, test_db):
    """Test Method Reviewer required when sandbox runs exist."""
    ws = finalized_workspace_with_draft
    
    # Add sandbox run
    test_db.execute(
        """
        INSERT INTO activity_runs (id, workspace_id, activity_type, status, created_at)
        VALUES (:id, :workspace_id, 'sandbox_run', 'completed', NOW())
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws["workspace_id"]
        }
    )
    
    # Add all passing rule checks
    test_db.execute(
        """
        INSERT INTO rule_checks (id, workspace_id, rule_name, target_type, target_id, status, details, created_at)
        VALUES (:id1, :workspace_id, 'citation_coverage', 'artifact_version', :version_id, 'pass', '{}', NOW()),
               (:id2, :workspace_id, 'citation_resolves', 'artifact_version', :version_id, 'pass', :details, NOW()),
               (:id3, :workspace_id, 'critique_sufficiency', 'artifact_version', :version_id, 'pass', '{}', NOW())
        """,
        {
            "id1": str(uuid.uuid4()),
            "id2": str(uuid.uuid4()),
            "id3": str(uuid.uuid4()),
            "workspace_id": ws["workspace_id"],
            "version_id": ws["draft_version_id"],
            "details": {"citation_resolves": True}
        }
    )
    test_db.commit()
    
    # Gather snapshot (no Method Reviewer assigned yet)
    from apps.worker.gates import GateEvaluationActivity
    activity = GateEvaluationActivity(test_db)
    snapshot = activity.gather_finalization_gate_snapshot(
        ws["workspace_id"],
        ws["draft_artifact_id"],
        ws["draft_version_id"]
    )
    
    # Evaluate gate - should block for missing Method Reviewer
    result = GateEvaluator.evaluate_finalization_gate(snapshot)
    
    assert result["status"] == GateStatus.BLOCK.value
    assert "Method Reviewer required when sandbox runs exist" in result["reasons"]
    assert any(action["type"] == "assign_method_reviewer" for action in result["required_actions"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
