import json
import uuid

import pytest

from database import get_raw_db


TEST_AGENT_ID = "00000000-0000-0000-0000-000000000001"


def _ensure_agent_raw(agent_id: str = TEST_AGENT_ID) -> None:
    with get_raw_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO NOTHING
            """,
            (agent_id, "test_moltbook_id", "Test Agent", 0.0),
        )
        conn.commit()


def test_sandbox_run_endpoint__agent_request__creates_workflow_request(
    test_client,
    test_db,
    test_storage,
    mock_agent_token,
):
    """POST /workspaces/{id}/requests/run_sandbox creates workflow request + artifacts."""
    workspace_id = str(uuid.uuid4())
    script_artifact_id = str(uuid.uuid4())

    with get_raw_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO NOTHING
            """,
            (TEST_AGENT_ID, "test_moltbook_id", "Test Agent", 0.0),
        )
        cursor.execute(
            "INSERT INTO workspaces (id, name, phase) VALUES (%s, %s, %s)",
            (workspace_id, "Test Workspace", "active"),
        )
        cursor.execute(
            """
            INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                script_artifact_id,
                workspace_id,
                "SCR4",
                "code",
                json.dumps({"language": "python"}),
                f"s3://agora/{workspace_id}/artifacts/{script_artifact_id}/",
                TEST_AGENT_ID,
            ),
        )
        conn.commit()

    script_content = 'print("Test output")'
    version_id = str(uuid.uuid4())
    script_storage_uri = f"s3://agora/{workspace_id}/artifacts/{script_artifact_id}/v1/script.py"
    test_storage.put_object(script_storage_uri, script_content.encode("utf-8"))

    with get_raw_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO artifact_versions (id, artifact_id, version, storage_uri, content_hash, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """,
            (version_id, script_artifact_id, 1, script_storage_uri, "test_hash4", TEST_AGENT_ID),
        )
        conn.commit()

    response = test_client.post(
        f"/workspaces/{workspace_id}/requests/run_sandbox",
        headers={"Authorization": f"Bearer {mock_agent_token}"},
        json={
            "script_artifact_id": script_artifact_id,
            "timeout_seconds": 60,
            "memory_limit": "256m",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "request_id" in data
    assert "activity_run_id" in data
    assert "log_artifact_id" in data
    assert "config_artifact_id" in data
    assert "completed with exit code" in data["message"]

    log_artifact = test_db.execute(
        "SELECT id, type FROM artifacts WHERE id = :id",
        {"id": data["log_artifact_id"]},
    ).fetchone()
    assert log_artifact is not None
    assert log_artifact[1] == "log"

    activity_run = test_db.execute(
        "SELECT status, activity_type FROM activity_runs WHERE id = :id",
        {"id": data["activity_run_id"]},
    ).fetchone()
    assert activity_run is not None
    assert activity_run[0] == "completed"
    assert activity_run[1] == "sandbox_run"


def test_sandbox_run_endpoint__budget_exceeded__returns_400(test_client, test_db, mock_agent_token):
    """Per-workspace sandbox budget enforcement returns 429 + Retry-After."""
    workspace_id = str(uuid.uuid4())
    script_artifact_id = str(uuid.uuid4())

    with get_raw_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO NOTHING
            """,
            (TEST_AGENT_ID, "test_moltbook_id", "Test Agent", 0.0),
        )
        cursor.execute(
            "INSERT INTO workspaces (id, name, phase) VALUES (%s, %s, %s)",
            (workspace_id, "Test Workspace", "active"),
        )
        cursor.execute(
            """
            INSERT INTO artifacts (id, workspace_id, short_id, type, storage_uri, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                script_artifact_id,
                workspace_id,
                "SCR5",
                "code",
                f"s3://agora/{workspace_id}/artifacts/{script_artifact_id}/",
                TEST_AGENT_ID,
            ),
        )
        conn.commit()

    workflow_run_id = str(uuid.uuid4())
    with get_raw_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO workflow_runs (id, workspace_id, workflow_type, temporal_workflow_id, status)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (workflow_run_id, workspace_id, "sandbox_run", f"sandbox_run_{workflow_run_id}", "completed"),
        )

        for _ in range(100):
            run_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO activity_runs (id, workflow_run_id, activity_type, temporal_activity_id, status)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (run_id, workflow_run_id, "sandbox_run", f"sandbox_run_{run_id}", "completed"),
            )
        conn.commit()

    response = test_client.post(
        f"/workspaces/{workspace_id}/requests/run_sandbox",
        headers={"Authorization": f"Bearer {mock_agent_token}"},
        json={"script_artifact_id": script_artifact_id},
    )

    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert "budget exhausted" in response.json()["detail"]
