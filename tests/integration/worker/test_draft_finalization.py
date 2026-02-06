"""
Tests for Draft Finalization Gate + Activity (Component 21).

These are DB-backed unit/integration tests for the worker-side gate snapshot and
finalization activity. They validate behavior against the canonical schema.
"""

import uuid
import pytest
from sqlalchemy import text as sql_text

from apps.worker.gates import GateEvaluator, GateStatus, GateEvaluationActivity
from apps.worker.finalization_activities import finalize_draft_artifact


def _seed_agent(db, agent_id: str, name: str) -> None:
    db.execute(
        """
        INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
        VALUES (:id, :moltbook_id, :name, :reputation, NOW())
        """,
        {
            "id": agent_id,
            "moltbook_id": f"test-moltbook-{agent_id}",
            "name": name,
            "reputation": 100,
        },
    )


def _role_id(db, role_name: str) -> str:
    row = db.execute(
        "SELECT id FROM roles WHERE name = :name",
        {"name": role_name},
    ).fetchone()
    assert row, f"Role not seeded: {role_name}"
    return str(row[0])


def _cleanup_workspace(db, workspace_id: str, agent_ids: list[str]) -> None:
    # Delete dependent rows first (no cascades assumed).
    db.execute("DELETE FROM events WHERE workspace_id = :ws", {"ws": workspace_id})
    db.execute("DELETE FROM rule_checks WHERE workspace_id = :ws", {"ws": workspace_id})
    db.execute("DELETE FROM critiques WHERE workspace_id = :ws", {"ws": workspace_id})
    db.execute("DELETE FROM workspace_agents WHERE workspace_id = :ws", {"ws": workspace_id})
    db.execute(
        sql_text(
            """
            DELETE FROM activity_runs ar
            USING workflow_runs wr
            WHERE ar.workflow_run_id = wr.id
              AND wr.workspace_id = :ws
            """
        ),
        {"ws": workspace_id},
    )
    db.execute("DELETE FROM workflow_runs WHERE workspace_id = :ws", {"ws": workspace_id})
    db.execute(
        """
        DELETE FROM artifact_versions
        WHERE artifact_id IN (SELECT id FROM artifacts WHERE workspace_id = :ws)
        """,
        {"ws": workspace_id},
    )
    db.execute("DELETE FROM artifacts WHERE workspace_id = :ws", {"ws": workspace_id})
    db.execute("DELETE FROM workspaces WHERE id = :ws", {"ws": workspace_id})
    for aid in agent_ids:
        db.execute("DELETE FROM agents WHERE id = :id", {"id": aid})
    db.commit()


@pytest.fixture
def db(migrated_db):
    from apps.worker.database import get_db_connection

    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def finalized_workspace_with_draft(db):
    """
    Create a workspace in FINALIZED phase with:
    - a draft artifact + version
    - an assigned Skeptic
    """
    workspace_id = str(uuid.uuid4())
    draft_artifact_id = str(uuid.uuid4())
    draft_version_id = str(uuid.uuid4())

    skeptic_agent_id = str(uuid.uuid4())
    _seed_agent(db, skeptic_agent_id, "Skeptic Agent")

    skeptic_role_id = _role_id(db, "Skeptic")

    db.execute(
        """
        INSERT INTO workspaces (id, name, description, phase, created_by, created_at)
        VALUES (:id, :name, :description, 'FINALIZED', :created_by, NOW())
        """,
        {
            "id": workspace_id,
            "name": "Test Workspace",
            "description": "Draft finalization tests",
            "created_by": skeptic_agent_id,
        },
    )

    # Draft artifact is an artifact row with type='draft'. Title/status live in metadata.
    db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
        VALUES (:id, :workspace_id, :short_id, 'draft', :metadata, :storage_uri, :created_by, NOW())
        """,
        {
            "id": draft_artifact_id,
            "workspace_id": workspace_id,
            "short_id": "A1",
            "metadata": {"title": "Test Draft"},
            "storage_uri": f"s3://agora/{workspace_id}/artifacts/{draft_artifact_id}/",
            "created_by": skeptic_agent_id,
        },
    )

    db.execute(
        """
        INSERT INTO artifact_versions (id, artifact_id, version, storage_uri, content_hash, created_by, created_at)
        VALUES (:id, :artifact_id, 1, :storage_uri, :content_hash, :created_by, NOW())
        """,
        {
            "id": draft_version_id,
            "artifact_id": draft_artifact_id,
            "storage_uri": f"s3://agora/{workspace_id}/artifacts/{draft_artifact_id}/v1/draft.md",
            "content_hash": "hash123",
            "created_by": skeptic_agent_id,
        },
    )

    db.execute(
        """
        INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status, joined_at)
        VALUES (:workspace_id, :agent_id, :role_id, 'active', NOW())
        """,
        {
            "workspace_id": workspace_id,
            "agent_id": skeptic_agent_id,
            "role_id": skeptic_role_id,
        },
    )

    db.commit()

    bundle = {
        "workspace_id": workspace_id,
        "draft_artifact_id": draft_artifact_id,
        "draft_version_id": draft_version_id,
        "skeptic_agent_id": skeptic_agent_id,
    }

    try:
        yield bundle
    finally:
        _cleanup_workspace(db, workspace_id, [skeptic_agent_id])


def _insert_citation_check(db, ws_id: str, version_id: str, status: str, all_resolve: bool = True):
    db.execute(
        """
        INSERT INTO rule_checks (id, workspace_id, target_type, target_id, rule_name, status, details, created_at)
        VALUES (:id, :workspace_id, 'artifact_version', :target_id, 'citation_check', :status, :details, NOW())
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws_id,
            "target_id": version_id,
            "status": status,
            "details": {"all_citations_resolve": all_resolve},
        },
    )


def _insert_critique_sufficiency(db, ws_id: str, version_id: str, status: str):
    db.execute(
        """
        INSERT INTO rule_checks (id, workspace_id, target_type, target_id, rule_name, status, details, created_at)
        VALUES (:id, :workspace_id, 'artifact_version', :target_id, 'critique_sufficiency', :status, :details, NOW())
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws_id,
            "target_id": version_id,
            "status": status,
            "details": {},
        },
    )


def test_finalization_gate_all_pass(finalized_workspace_with_draft, db):
    ws = finalized_workspace_with_draft

    _insert_citation_check(db, ws["workspace_id"], ws["draft_version_id"], status="pass", all_resolve=True)
    _insert_critique_sufficiency(db, ws["workspace_id"], ws["draft_version_id"], status="pass")
    db.commit()

    activity = GateEvaluationActivity(db)
    snapshot = activity.gather_finalization_gate_snapshot(
        ws["workspace_id"], ws["draft_artifact_id"], ws["draft_version_id"]
    )

    result = GateEvaluator.evaluate_finalization_gate(snapshot)
    assert result["status"] == GateStatus.PASS.value
    assert "All finalization criteria met" in result["reasons"]


def test_finalization_gate_missing_or_failing_citation_check_fails(finalized_workspace_with_draft, db):
    ws = finalized_workspace_with_draft

    _insert_citation_check(db, ws["workspace_id"], ws["draft_version_id"], status="fail", all_resolve=True)
    _insert_critique_sufficiency(db, ws["workspace_id"], ws["draft_version_id"], status="pass")
    db.commit()

    activity = GateEvaluationActivity(db)
    snapshot = activity.gather_finalization_gate_snapshot(
        ws["workspace_id"], ws["draft_artifact_id"], ws["draft_version_id"]
    )
    result = GateEvaluator.evaluate_finalization_gate(snapshot)

    assert result["status"] == GateStatus.FAIL.value
    assert "Citation coverage check failed" in result["reasons"]


def test_finalization_gate_citation_resolves_fails(finalized_workspace_with_draft, db):
    ws = finalized_workspace_with_draft

    _insert_citation_check(db, ws["workspace_id"], ws["draft_version_id"], status="pass", all_resolve=False)
    _insert_critique_sufficiency(db, ws["workspace_id"], ws["draft_version_id"], status="pass")
    db.commit()

    activity = GateEvaluationActivity(db)
    snapshot = activity.gather_finalization_gate_snapshot(
        ws["workspace_id"], ws["draft_artifact_id"], ws["draft_version_id"]
    )
    result = GateEvaluator.evaluate_finalization_gate(snapshot)

    assert result["status"] == GateStatus.FAIL.value
    assert "Citation resolve check failed" in result["reasons"]


def test_finalization_gate_blocking_critiques_blocks(finalized_workspace_with_draft, db):
    ws = finalized_workspace_with_draft

    _insert_citation_check(db, ws["workspace_id"], ws["draft_version_id"], status="pass", all_resolve=True)
    _insert_critique_sufficiency(db, ws["workspace_id"], ws["draft_version_id"], status="pass")

    # Add open blocking critique targeting the draft version.
    critic_id = str(uuid.uuid4())
    _seed_agent(db, critic_id, "Critic")
    db.execute(
        """
        INSERT INTO critiques (
          id, workspace_id, target_type, target_id, target_location,
          critic_agent_id, status, severity, message, resolution, created_at
        ) VALUES (
          :id, :workspace_id, 'artifact_version', :target_id, NULL,
          :critic_agent_id, 'open', 'blocking', :message, NULL, NOW()
        )
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": ws["workspace_id"],
            "target_id": ws["draft_version_id"],
            "critic_agent_id": critic_id,
            "message": "Critical issue",
        },
    )

    db.commit()

    activity = GateEvaluationActivity(db)
    snapshot = activity.gather_finalization_gate_snapshot(
        ws["workspace_id"], ws["draft_artifact_id"], ws["draft_version_id"]
    )
    result = GateEvaluator.evaluate_finalization_gate(snapshot)

    assert result["status"] == GateStatus.BLOCK.value
    assert any("open blocking critique" in r for r in result["reasons"])


def test_finalization_gate_missing_skeptic_blocks(finalized_workspace_with_draft, db):
    ws = finalized_workspace_with_draft

    # Remove Skeptic membership.
    db.execute("DELETE FROM workspace_agents WHERE workspace_id = :ws", {"ws": ws["workspace_id"]})

    _insert_citation_check(db, ws["workspace_id"], ws["draft_version_id"], status="pass", all_resolve=True)
    _insert_critique_sufficiency(db, ws["workspace_id"], ws["draft_version_id"], status="pass")
    db.commit()

    activity = GateEvaluationActivity(db)
    snapshot = activity.gather_finalization_gate_snapshot(
        ws["workspace_id"], ws["draft_artifact_id"], ws["draft_version_id"]
    )
    result = GateEvaluator.evaluate_finalization_gate(snapshot)

    assert result["status"] == GateStatus.BLOCK.value
    assert "Skeptic role not assigned" in result["reasons"]


def test_finalization_gate_method_reviewer_required_with_sandbox(finalized_workspace_with_draft, db):
    ws = finalized_workspace_with_draft

    # Add sandbox_run activity.
    workflow_run_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO workflow_runs (id, workspace_id, workflow_type, temporal_workflow_id, status, started_at)
        VALUES (:id, :workspace_id, 'sandbox_run', :twid, 'completed', NOW())
        """,
        {"id": workflow_run_id, "workspace_id": ws["workspace_id"], "twid": f"wf-{workflow_run_id}"},
    )
    db.execute(
        """
        INSERT INTO activity_runs (id, workflow_run_id, activity_type, temporal_activity_id, status, started_at)
        VALUES (:id, :workflow_run_id, 'sandbox_run', :taid, 'completed', NOW())
        """,
        {"id": str(uuid.uuid4()), "workflow_run_id": workflow_run_id, "taid": f"act-{workflow_run_id}"},
    )

    _insert_citation_check(db, ws["workspace_id"], ws["draft_version_id"], status="pass", all_resolve=True)
    _insert_critique_sufficiency(db, ws["workspace_id"], ws["draft_version_id"], status="pass")
    db.commit()

    activity = GateEvaluationActivity(db)
    snapshot = activity.gather_finalization_gate_snapshot(
        ws["workspace_id"], ws["draft_artifact_id"], ws["draft_version_id"]
    )
    result = GateEvaluator.evaluate_finalization_gate(snapshot)

    assert result["status"] == GateStatus.BLOCK.value
    assert "Method Reviewer required when sandbox runs exist" in result["reasons"]


@pytest.mark.asyncio
async def test_finalize_draft_activity_updates_metadata_and_emits_events(finalized_workspace_with_draft, db):
    ws = finalized_workspace_with_draft

    result = await finalize_draft_artifact(
        ws["workspace_id"], ws["draft_artifact_id"], ws["draft_version_id"]
    )

    assert "finalization_timestamp" in result
    assert result["final_version_id"] == ws["draft_version_id"]

    artifact_row = db.execute(
        "SELECT metadata FROM artifacts WHERE id = :id",
        {"id": ws["draft_artifact_id"]},
    ).fetchone()
    assert artifact_row
    assert artifact_row[0]["status"] == "final"

    event_types = [
        r[0]
        for r in db.execute(
            """
            SELECT event_type
            FROM events
            WHERE workspace_id = :workspace_id
            ORDER BY created_at DESC
            """,
            {"workspace_id": ws["workspace_id"]},
        ).fetchall()
    ]
    assert "draft.finalized" in event_types
    assert "workspace.finalized" in event_types


@pytest.mark.asyncio
async def test_finalize_draft_activity_rejects_non_finalized_phase(finalized_workspace_with_draft, db):
    ws = finalized_workspace_with_draft

    db.execute(
        "UPDATE workspaces SET phase = 'INTERNAL_REVIEW' WHERE id = :id",
        {"id": ws["workspace_id"]},
    )
    db.commit()

    with pytest.raises(RuntimeError, match="must be FINALIZED"):
        await finalize_draft_artifact(
            ws["workspace_id"], ws["draft_artifact_id"], ws["draft_version_id"]
        )
