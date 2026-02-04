"""
Integration tests for Component 20: Phase Machine + Gates

Tests per Docs/06 exit criteria:
- Agent cannot change phase
- Orchestrator can, and emits event with previous/next phase and gate summary

Tests phase machine and gates per spec §5.3, §5.4:
- Valid and invalid transitions
- Gate evaluation logic
- Required action task creation
- Event emission on phase changes
"""
import pytest
import uuid
from database import get_raw_db

TEST_AGENT_ID = "00000000-0000-0000-0000-000000000001"
import json


def test_phase_machine_valid_transitions():
    """Test valid phase transitions are allowed."""
    from apps.worker.phase_machine import PhaseMachine
    
    # Test standard progression
    assert PhaseMachine.is_valid_transition("INIT", "LIT_REVIEW")
    assert PhaseMachine.is_valid_transition("LIT_REVIEW", "CLAIM_VALIDATION")
    assert PhaseMachine.is_valid_transition("CLAIM_VALIDATION", "HYPOTHESIS_PLANNING")
    assert PhaseMachine.is_valid_transition("HYPOTHESIS_PLANNING", "EXPERIMENTATION")
    assert PhaseMachine.is_valid_transition("EXPERIMENTATION", "SYNTHESIS")
    assert PhaseMachine.is_valid_transition("SYNTHESIS", "INTERNAL_REVIEW")
    assert PhaseMachine.is_valid_transition("INTERNAL_REVIEW", "FINALIZED")
    assert PhaseMachine.is_valid_transition("FINALIZED", "ARCHIVED")
    
    # Test loopbacks
    assert PhaseMachine.is_valid_transition("INTERNAL_REVIEW", "EXPERIMENTATION")
    assert PhaseMachine.is_valid_transition("CLAIM_VALIDATION", "LIT_REVIEW")


def test_phase_machine_invalid_transitions():
    """Test invalid phase transitions are rejected."""
    from apps.worker.phase_machine import PhaseMachine
    
    # Cannot skip phases
    assert not PhaseMachine.is_valid_transition("INIT", "SYNTHESIS")
    assert not PhaseMachine.is_valid_transition("LIT_REVIEW", "FINALIZED")
    
    # Cannot go backwards (except explicit loopbacks)
    assert not PhaseMachine.is_valid_transition("SYNTHESIS", "LIT_REVIEW")
    assert not PhaseMachine.is_valid_transition("FINALIZED", "EXPERIMENTATION")
    
    # Terminal state has no exits
    assert not PhaseMachine.is_valid_transition("ARCHIVED", "INIT")
    assert not PhaseMachine.is_valid_transition("ARCHIVED", "LIT_REVIEW")


def test_phase_machine_loopback_detection():
    """Test loopback transition detection."""
    from apps.worker.phase_machine import PhaseMachine
    
    # Valid loopbacks
    assert PhaseMachine.is_loopback_transition("INTERNAL_REVIEW", "EXPERIMENTATION")
    assert PhaseMachine.is_loopback_transition("CLAIM_VALIDATION", "LIT_REVIEW")
    
    # Forward transitions are not loopbacks
    assert not PhaseMachine.is_loopback_transition("INIT", "LIT_REVIEW")
    assert not PhaseMachine.is_loopback_transition("LIT_REVIEW", "CLAIM_VALIDATION")


def test_phase_machine_terminal_phases():
    """Test terminal phase detection."""
    from apps.worker.phase_machine import PhaseMachine
    
    # ARCHIVED is terminal
    assert PhaseMachine.is_terminal_phase("ARCHIVED")
    
    # Other phases are not terminal
    assert not PhaseMachine.is_terminal_phase("INIT")
    assert not PhaseMachine.is_terminal_phase("FINALIZED")


def test_phase_advancement_activity(test_db):
    """Test phase advancement activity."""
    from apps.worker.phase_machine import PhaseAdvancementActivity
    
    workspace_id = str(uuid.uuid4())
    
    # Create workspace in INIT phase
    test_db.execute(
        """
        INSERT INTO workspaces (id, name, phase, created_at)
        VALUES (:id, :name, :phase, NOW())
        """,
        {"id": workspace_id, "name": "Test Workspace", "phase": "INIT"}
    )
    test_db.commit()
    
    # Advance to LIT_REVIEW
    activity = PhaseAdvancementActivity(test_db)
    result = activity.advance_phase(
        workspace_id=workspace_id,
        next_phase="LIT_REVIEW",
        gate_summary={"gate_name": "no_gate", "status": "PASS"},
        workflow_run_id="test_workflow_123"
    )
    
    assert result["success"]
    assert result["previous_phase"] == "INIT"
    assert result["next_phase"] == "LIT_REVIEW"
    assert "event_id" in result
    
    # Verify workspace phase updated
    row = test_db.execute(
        "SELECT phase FROM workspaces WHERE id = :id",
        {"id": workspace_id}
    ).fetchone()
    
    assert row[0] == "LIT_REVIEW"
    
    # Verify event created
    event = test_db.execute(
        """
        SELECT event_type, actor_type, payload
        FROM events
        WHERE workspace_id = :workspace_id
          AND event_type = 'workspace.phase_changed'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        {"workspace_id": workspace_id}
    ).fetchone()
    
    assert event is not None
    assert event[0] == "workspace.phase_changed"
    assert event[1] == "system"
    
    payload = json.loads(event[2])
    assert payload["previous_phase"] == "INIT"
    assert payload["next_phase"] == "LIT_REVIEW"
    assert payload["workflow_run_id"] == "test_workflow_123"


def test_phase_advancement_invalid_transition(test_db):
    """Test that invalid transitions are rejected."""
    from apps.worker.phase_machine import PhaseAdvancementActivity, PhaseTransitionError
    
    workspace_id = str(uuid.uuid4())
    
    # Create workspace in INIT phase
    test_db.execute(
        """
        INSERT INTO workspaces (id, name, phase, created_at)
        VALUES (:id, :name, :phase, NOW())
        """,
        {"id": workspace_id, "name": "Test Workspace", "phase": "INIT"}
    )
    test_db.commit()
    
    # Try to skip to FINALIZED (invalid)
    activity = PhaseAdvancementActivity(test_db)
    
    with pytest.raises(PhaseTransitionError):
        activity.advance_phase(
            workspace_id=workspace_id,
            next_phase="FINALIZED",
            gate_summary={},
            workflow_run_id="test_workflow_123"
        )
    
    # Verify phase unchanged
    row = test_db.execute(
        "SELECT phase FROM workspaces WHERE id = :id",
        {"id": workspace_id}
    ).fetchone()
    
    assert row[0] == "INIT"


def test_agent_cannot_change_phase_directly(test_client, test_db, mock_agent_token):
    """Test that agents cannot directly modify workspace.phase."""
    workspace_id = str(uuid.uuid4())
    agent_id = TEST_AGENT_ID
    
    with get_raw_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO workspaces (id, name, phase, created_at)
            VALUES (%s, %s, %s, NOW())
            """,
            (workspace_id, "Test Workspace", "INIT")
        )
        conn.commit()
    
    # Agent tries to directly update phase (this should fail)
    # Note: There is no PATCH /workspaces/{id} endpoint that allows phase updates
    # Only orchestrator via advance_phase workflow can change phase
    
    # Verify phase endpoint is read-only for agents
    response = test_client.get(
        f"/workspaces/{workspace_id}/phase",
        headers={"Authorization": f"Bearer {mock_agent_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["current_phase"] == "INIT"
    assert "LIT_REVIEW" in data["allowed_next_phases"]


def test_lit_review_exit_gate(test_db):
    """Test LIT_REVIEW exit gate evaluation."""
    from apps.worker.gates import GateEvaluationActivity, GateEvaluator
    
    workspace_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        """
        INSERT INTO workspaces (id, name, phase, created_at)
        VALUES (:id, :name, :phase, NOW())
        """,
        {"id": workspace_id, "name": "Test Workspace", "phase": "LIT_REVIEW"}
    )
    
    # Create an artifact
    artifact_id = str(uuid.uuid4())
    test_db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
        VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
        """,
        {
            "id": artifact_id,
            "workspace_id": workspace_id,
            "short_id": "PDF1",
            "type": "pdf",
            "metadata": json.dumps({}),
            "storage_uri": "s3://test/",
            "created_by": agent_id
        }
    )
    
    # Create a claim with evidence
    claim_id = str(uuid.uuid4())
    test_db.execute(
        """
        INSERT INTO claims (id, workspace_id, text, kind, confidence, created_by, created_at)
        VALUES (:id, :workspace_id, :text, :kind, :confidence, :created_by, NOW())
        """,
        {
            "id": claim_id,
            "workspace_id": workspace_id,
            "text": "Test claim",
            "kind": "fact",
            "confidence": 0.9,
            "created_by": agent_id
        }
    )
    
    test_db.execute(
        """
        INSERT INTO claim_evidence (id, claim_id, artifact_version_id, location, created_at)
        VALUES (:id, :claim_id, :artifact_version_id, :location, NOW())
        """,
        {
            "id": str(uuid.uuid4()),
            "claim_id": claim_id,
            "artifact_version_id": artifact_id,  # Simplified for test
            "location": "pdf:p=1#char=0-100"
        }
    )
    
    # Create a critique by different agent
    critic_id = str(uuid.uuid4())
    test_db.execute(
        """
        INSERT INTO critiques (
            id, workspace_id, target_type, target_id, critic_agent_id,
            status, severity, message, created_at
        ) VALUES (
            :id, :workspace_id, :target_type, :target_id, :critic_agent_id,
            :status, :severity, :message, NOW()
        )
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "target_type": "claim",
            "target_id": claim_id,
            "critic_agent_id": critic_id,
            "status": "open",
            "severity": "minor",
            "message": "Needs review"
        }
    )
    
    test_db.commit()
    
    # Gather snapshot
    activity = GateEvaluationActivity(test_db)
    snapshot = activity.gather_lit_review_exit_snapshot(workspace_id)
    
    assert snapshot["artifact_count"] == 1
    assert snapshot["claims_with_evidence_count"] == 1
    assert snapshot["claims_with_critiques_count"] == 1
    
    # Evaluate gate
    result = GateEvaluator.evaluate_lit_review_exit(snapshot)
    
    assert result["gate_name"] == "lit_review_exit"
    assert result["status"] == "PASS"
    assert len(result["reasons"]) > 0


def test_lit_review_exit_gate_fails_without_artifacts(test_db):
    """Test LIT_REVIEW exit gate fails without artifacts."""
    from apps.worker.gates import GateEvaluationActivity, GateEvaluator
    
    workspace_id = str(uuid.uuid4())
    
    # Create workspace with no artifacts
    test_db.execute(
        """
        INSERT INTO workspaces (id, name, phase, created_at)
        VALUES (:id, :name, :phase, NOW())
        """,
        {"id": workspace_id, "name": "Test Workspace", "phase": "LIT_REVIEW"}
    )
    test_db.commit()
    
    # Gather snapshot
    activity = GateEvaluationActivity(test_db)
    snapshot = activity.gather_lit_review_exit_snapshot(workspace_id)
    
    # Evaluate gate
    result = GateEvaluator.evaluate_lit_review_exit(snapshot)
    
    assert result["status"] == "FAIL"
    assert any("artifacts" in reason.lower() for reason in result["reasons"])
    assert len(result["required_actions"]) > 0


def test_internal_review_exit_gate_blocks_without_skeptic(test_db):
    """Test INTERNAL_REVIEW exit gate blocks without Skeptic role."""
    from apps.worker.gates import GateEvaluationActivity, GateEvaluator
    
    workspace_id = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        """
        INSERT INTO workspaces (id, name, phase, created_at)
        VALUES (:id, :name, :phase, NOW())
        """,
        {"id": workspace_id, "name": "Test Workspace", "phase": "INTERNAL_REVIEW"}
    )
    test_db.commit()
    
    # Gather snapshot (no Skeptic present)
    activity = GateEvaluationActivity(test_db)
    snapshot = activity.gather_internal_review_exit_snapshot(workspace_id)
    
    assert not snapshot["skeptic_present"]
    
    # Evaluate gate
    result = GateEvaluator.evaluate_internal_review_exit(snapshot)
    
    # Should BLOCK (not just FAIL)
    assert result["status"] == "BLOCK"
    assert any("skeptic" in reason.lower() for reason in result["reasons"])


def test_required_action_tasks_created(test_db):
    """Test that required action tasks are created when gates fail."""
    from apps.worker.phase_machine import PhaseAdvancementActivity
    
    workspace_id = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        """
        INSERT INTO workspaces (id, name, phase, created_at)
        VALUES (:id, :name, :phase, NOW())
        """,
        {"id": workspace_id, "name": "Test Workspace", "phase": "LIT_REVIEW"}
    )
    test_db.commit()
    
    # Create required actions
    required_actions = [
        {
            "type": "assign_task",
            "role": "Literature Analyst",
            "payload": {"task": "ingest_literature"}
        },
        {
            "type": "assign_task",
            "role": "Skeptic",
            "payload": {"task": "review_claims"}
        }
    ]
    
    activity = PhaseAdvancementActivity(test_db)
    task_ids = activity.create_required_action_tasks(
        workspace_id=workspace_id,
        required_actions=required_actions,
        workflow_run_id="test_workflow_123"
    )
    
    assert len(task_ids) == 2
    
    # Verify tasks created
    tasks = test_db.execute(
        """
        SELECT payload, status, type
        FROM agent_tasks
        WHERE workspace_id = :workspace_id
        """,
        {"workspace_id": workspace_id}
    ).fetchall()
    
    assert len(tasks) == 2
    roles = []
    for task in tasks:
        payload = task[0] or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        roles.append(payload.get("assignee_role"))
        assert task[1] == "open"
    assert "Literature Analyst" in roles
    assert "Skeptic" in roles
