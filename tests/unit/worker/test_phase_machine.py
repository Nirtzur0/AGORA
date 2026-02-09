"""Unit tests for worker phase machine logic and activity behavior."""

import json

import pytest

import phase_machine


class _FakeResult:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeDB:
    def __init__(self, current_phase_row=("LIT_REVIEW",)):
        self._current_phase_row = current_phase_row
        self.executed = []
        self.commit_count = 0

    def execute(self, query, params=None):
        self.executed.append((query, params))
        if "SELECT phase FROM workspaces" in query:
            return _FakeResult(self._current_phase_row)
        return _FakeResult()

    def commit(self):
        self.commit_count += 1


def test_is_valid_transition__allowed_forward_transition__returns_true():
    assert phase_machine.PhaseMachine.is_valid_transition("LIT_REVIEW", "CLAIM_VALIDATION") is True


def test_is_valid_transition__unknown_phase__returns_false():
    assert phase_machine.PhaseMachine.is_valid_transition("NOT_A_PHASE", "CLAIM_VALIDATION") is False


def test_validate_transition__disallowed_transition__raises():
    with pytest.raises(phase_machine.PhaseTransitionError, match="Invalid phase transition"):
        phase_machine.PhaseMachine.validate_transition("INIT", "SYNTHESIS")


def test_get_allowed_next_phases__claim_validation__returns_forward_and_loopback():
    next_phases = phase_machine.PhaseMachine.get_allowed_next_phases("CLAIM_VALIDATION")

    assert set(next_phases) == {"HYPOTHESIS_PLANNING", "LIT_REVIEW"}


def test_is_loopback_transition__known_pairs__returns_true():
    assert phase_machine.PhaseMachine.is_loopback_transition("INTERNAL_REVIEW", "EXPERIMENTATION") is True
    assert phase_machine.PhaseMachine.is_loopback_transition("CLAIM_VALIDATION", "LIT_REVIEW") is True
    assert phase_machine.PhaseMachine.is_loopback_transition("LIT_REVIEW", "CLAIM_VALIDATION") is False


def test_is_terminal_phase__archived__returns_true():
    assert phase_machine.PhaseMachine.is_terminal_phase("ARCHIVED") is True
    assert phase_machine.PhaseMachine.is_terminal_phase("FINALIZED") is False


def test_advance_phase__valid_transition__updates_workspace_and_emits_event():
    db = _FakeDB(current_phase_row=("INTERNAL_REVIEW",))
    activity = phase_machine.PhaseAdvancementActivity(db)
    workflow_run_id = "00000000-0000-0000-0000-000000000123"

    result = activity.advance_phase(
        workspace_id="workspace-1",
        next_phase="EXPERIMENTATION",
        gate_summary={"status": "fail"},
        workflow_run_id=workflow_run_id,
    )

    assert result["success"] is True
    assert result["previous_phase"] == "INTERNAL_REVIEW"
    assert result["next_phase"] == "EXPERIMENTATION"
    assert result["is_loopback"] is True
    assert db.commit_count == 1
    assert any("UPDATE workspaces" in query for query, _ in db.executed)
    assert any("INSERT INTO events" in query for query, _ in db.executed)

    event_call = next((params for query, params in db.executed if "INSERT INTO events" in query), None)
    assert event_call is not None
    assert event_call["actor_type"] == "system"
    assert event_call["actor_id"] == workflow_run_id
    assert event_call["event_type"] == "workspace.phase_changed"
    payload = json.loads(event_call["payload"])
    assert payload["previous_phase"] == "INTERNAL_REVIEW"
    assert payload["next_phase"] == "EXPERIMENTATION"
    assert payload["is_loopback"] is True


def test_advance_phase__workspace_missing__raises_value_error():
    db = _FakeDB(current_phase_row=None)
    activity = phase_machine.PhaseAdvancementActivity(db)

    with pytest.raises(ValueError, match="Workspace not found"):
        activity.advance_phase(
            workspace_id="missing-workspace",
            next_phase="CLAIM_VALIDATION",
            gate_summary={"status": "pass"},
        )

    assert db.commit_count == 0


def test_advance_phase__invalid_workflow_id__falls_back_to_zero_uuid_actor():
    db = _FakeDB(current_phase_row=("LIT_REVIEW",))
    activity = phase_machine.PhaseAdvancementActivity(db)

    activity.advance_phase(
        workspace_id="workspace-2",
        next_phase="CLAIM_VALIDATION",
        gate_summary={"status": "pass"},
        workflow_run_id="not-a-uuid",
    )

    event_call = next((params for query, params in db.executed if "INSERT INTO events" in query), None)
    assert event_call is not None
    assert event_call["actor_id"] == "00000000-0000-0000-0000-000000000000"


def test_create_required_action_tasks__assign_actions_only__creates_tasks(monkeypatch):
    captured = []

    def fake_insert_agent_task(db, task_id, workspace_id, assignee_agent_id, task_type, status, payload):
        captured.append(
            {
                "task_id": task_id,
                "workspace_id": workspace_id,
                "assignee_agent_id": assignee_agent_id,
                "task_type": task_type,
                "status": status,
                "payload": payload,
            }
        )

    monkeypatch.setattr(phase_machine, "insert_agent_task", fake_insert_agent_task)

    db = _FakeDB()
    activity = phase_machine.PhaseAdvancementActivity(db)
    task_ids = activity.create_required_action_tasks(
        workspace_id="workspace-3",
        required_actions=[
            {
                "type": "assign_task",
                "role": "Method Reviewer",
                "payload": {
                    "task": "review_methods",
                    "objective": "Review sandbox methodology",
                    "required_outputs": ["review.complete"],
                    "priority": "high",
                },
            },
            {
                "type": "log_only",
                "payload": {"task": "ignored"},
            },
        ],
        workflow_run_id="workflow-3",
    )

    assert len(task_ids) == 1
    assert len(captured) == 1
    assert captured[0]["workspace_id"] == "workspace-3"
    assert captured[0]["task_type"] == "review_methods"
    assert captured[0]["status"] == phase_machine.TaskStatus.OPEN.value
    assert captured[0]["payload"]["objective"] == "Review sandbox methodology"
    assert captured[0]["payload"]["required_outputs"] == ["review.complete"]
    assert captured[0]["payload"]["assignee_role"] == "Method Reviewer"
    assert captured[0]["payload"]["workflow_run_id"] == "workflow-3"
    assert db.commit_count == 1
