import json
import uuid

import pytest


TEST_AGENT_ID = "00000000-0000-0000-0000-000000000001"


def _ensure_agent(test_db, agent_id: str = TEST_AGENT_ID) -> None:
    test_db.execute(
        """
        INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
        VALUES (:id, :moltbook_id, :name, :reputation, NOW())
        ON CONFLICT (id) DO NOTHING
        """,
        {"id": agent_id, "moltbook_id": "test_moltbook_id", "name": "Test Agent", "reputation": 0},
    )


def _insert_workspace(test_db, workspace_id: str) -> None:
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"},
    )


def _insert_artifact(
    test_db,
    *,
    artifact_id: str,
    workspace_id: str,
    short_id: str,
    artifact_type: str,
    created_by: str,
    storage_uri: str,
    metadata=None,
) -> None:
    test_db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
        VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
        """,
        {
            "id": artifact_id,
            "workspace_id": workspace_id,
            "short_id": short_id,
            "type": artifact_type,
            "metadata": metadata,
            "storage_uri": storage_uri,
            "created_by": created_by,
        },
    )


def _insert_artifact_version(
    test_db,
    *,
    version_id: str,
    artifact_id: str,
    version: int,
    storage_uri: str,
    content_hash: str,
    created_by: str,
) -> None:
    test_db.execute(
        """
        INSERT INTO artifact_versions (id, artifact_id, version, storage_uri, content_hash, created_by, created_at)
        VALUES (:id, :artifact_id, :version, :storage_uri, :content_hash, :created_by, NOW())
        """,
        {
            "id": version_id,
            "artifact_id": artifact_id,
            "version": version,
            "storage_uri": storage_uri,
            "content_hash": content_hash,
            "created_by": created_by,
        },
    )


def test_sandbox_run_activity__script_success__produces_artifacts(test_db, test_storage):
    """Run script in sandbox and verify output/log artifacts."""
    from apps.worker.sandbox_run import SandboxRunActivity

    workspace_id = str(uuid.uuid4())
    script_artifact_id = str(uuid.uuid4())
    log_artifact_id = str(uuid.uuid4())

    _ensure_agent(test_db)
    _insert_workspace(test_db, workspace_id)
    _insert_artifact(
        test_db,
        artifact_id=script_artifact_id,
        workspace_id=workspace_id,
        short_id="SCR1",
        artifact_type="code",
        metadata={"language": "python"},
        storage_uri=f"s3://agora/{workspace_id}/artifacts/{script_artifact_id}/",
        created_by=TEST_AGENT_ID,
    )

    script_content = """#!/usr/bin/env python3
print("Hello from sandbox!")
print("Line 2")
print("Line 3")
"""
    version_id = str(uuid.uuid4())
    script_storage_uri = f"s3://agora/{workspace_id}/artifacts/{script_artifact_id}/v1/script.py"
    test_storage.put_object(script_storage_uri, script_content.encode("utf-8"))
    _insert_artifact_version(
        test_db,
        version_id=version_id,
        artifact_id=script_artifact_id,
        version=1,
        storage_uri=script_storage_uri,
        content_hash="test_hash",
        created_by=TEST_AGENT_ID,
    )

    _insert_artifact(
        test_db,
        artifact_id=log_artifact_id,
        workspace_id=workspace_id,
        short_id="LOG1",
        artifact_type="log",
        metadata={"source": "sandbox_execution"},
        storage_uri=f"s3://agora/{workspace_id}/artifacts/{log_artifact_id}/",
        created_by=TEST_AGENT_ID,
    )
    test_db.commit()

    activity = SandboxRunActivity(test_storage, test_db)
    result = activity.run_sandbox(
        artifact_id=log_artifact_id,
        workspace_id=workspace_id,
        script_artifact_id=script_artifact_id,
        parameters=None,
        created_by=TEST_AGENT_ID,
        activity_run_id=None,
        image="python:3.11-slim",
        timeout_seconds=60,
        memory_limit="256m",
        cpu_limit="0.5",
    )

    assert result["artifact_id"] == log_artifact_id
    assert "version_id" in result
    assert "config_artifact_id" in result
    assert result["exit_code"] == 0
    assert result["stdout_length"] > 0

    log_version = test_db.execute(
        "SELECT id, content_hash, storage_uri FROM artifact_versions WHERE artifact_id = :id",
        {"id": log_artifact_id},
    ).fetchone()
    assert log_version is not None
    assert log_version[2].startswith(f"s3://agora/{workspace_id}/artifacts/{log_artifact_id}/v")
    assert log_version[2].endswith("/log.txt")

    log_content = test_storage.get_object(log_version[2]).read().decode("utf-8")
    assert "Hello from sandbox!" in log_content
    assert "Line 2" in log_content
    assert "Line 3" in log_content

    config_artifact = test_db.execute(
        "SELECT id, type FROM artifacts WHERE id = :id",
        {"id": result["config_artifact_id"]},
    ).fetchone()
    assert config_artifact is not None
    assert config_artifact[1] == "config"

    log_entry = test_db.execute(
        "SELECT action, payload FROM logs WHERE workspace_id = :id ORDER BY created_at DESC LIMIT 1",
        {"id": workspace_id},
    ).fetchone()
    assert log_entry is not None
    assert log_entry[0] == "sandbox.execution"
    payload = log_entry[1]
    if isinstance(payload, str):
        payload = json.loads(payload)
    assert payload["event"] == "sandbox_execution"
    assert payload["exit_code"] == 0


def test_sandbox_run_activity__parameters__available_to_script(test_db, test_storage):
    """Environment variables supplied in parameters are visible to script."""
    from apps.worker.sandbox_run import SandboxRunActivity

    workspace_id = str(uuid.uuid4())
    script_artifact_id = str(uuid.uuid4())
    log_artifact_id = str(uuid.uuid4())

    _ensure_agent(test_db)
    _insert_workspace(test_db, workspace_id)
    _insert_artifact(
        test_db,
        artifact_id=script_artifact_id,
        workspace_id=workspace_id,
        short_id="SCR2",
        artifact_type="code",
        metadata={"language": "python"},
        storage_uri=f"s3://agora/{workspace_id}/artifacts/{script_artifact_id}/",
        created_by=TEST_AGENT_ID,
    )

    script_content = """#!/usr/bin/env python3
import os
print(f"ENV_VAR={os.environ.get('TEST_VAR', 'not_set')}")
"""
    version_id = str(uuid.uuid4())
    script_storage_uri = f"s3://agora/{workspace_id}/artifacts/{script_artifact_id}/v1/script.py"
    test_storage.put_object(script_storage_uri, script_content.encode("utf-8"))
    _insert_artifact_version(
        test_db,
        version_id=version_id,
        artifact_id=script_artifact_id,
        version=1,
        storage_uri=script_storage_uri,
        content_hash="test_hash2",
        created_by=TEST_AGENT_ID,
    )

    _insert_artifact(
        test_db,
        artifact_id=log_artifact_id,
        workspace_id=workspace_id,
        short_id="LOG2",
        artifact_type="log",
        metadata={"source": "sandbox_execution"},
        storage_uri=f"s3://agora/{workspace_id}/artifacts/{log_artifact_id}/",
        created_by=TEST_AGENT_ID,
    )
    test_db.commit()

    activity = SandboxRunActivity(test_storage, test_db)
    result = activity.run_sandbox(
        artifact_id=log_artifact_id,
        workspace_id=workspace_id,
        script_artifact_id=script_artifact_id,
        parameters={"env": {"TEST_VAR": "test_value"}},
        created_by=TEST_AGENT_ID,
    )
    assert result["exit_code"] == 0

    log_version = test_db.execute(
        "SELECT storage_uri FROM artifact_versions WHERE artifact_id = :id",
        {"id": log_artifact_id},
    ).fetchone()
    log_content = test_storage.get_object(log_version[0]).read().decode("utf-8")
    assert "ENV_VAR=test_value" in log_content


def test_evidence_resolution__log_char_range__resolves_snippet(test_db, test_storage):
    """Log evidence pointer resolution works for valid and invalid char ranges."""
    from apps.worker.sandbox_run import SandboxRunActivity

    workspace_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())

    _ensure_agent(test_db)
    _insert_workspace(test_db, workspace_id)
    _insert_artifact(
        test_db,
        artifact_id=artifact_id,
        workspace_id=workspace_id,
        short_id="LOG3",
        artifact_type="log",
        storage_uri=f"s3://agora/{workspace_id}/artifacts/{artifact_id}/",
        created_by=TEST_AGENT_ID,
    )

    log_content = "Hello from sandbox!\nLine 2\nLine 3\n"
    log_storage_uri = f"s3://agora/{workspace_id}/artifacts/{artifact_id}/v1/log.txt"
    test_storage.put_object(log_storage_uri, log_content.encode("utf-8"))
    _insert_artifact_version(
        test_db,
        version_id=version_id,
        artifact_id=artifact_id,
        version=1,
        storage_uri=log_storage_uri,
        content_hash="test_hash3",
        created_by=TEST_AGENT_ID,
    )
    test_db.commit()

    snippet = SandboxRunActivity.resolve_log_evidence(
        artifact_version_id=version_id,
        location="log:char=0-20",
        db=test_db,
    )
    assert snippet == "Hello from sandbox!\n"

    snippet = SandboxRunActivity.resolve_log_evidence(
        artifact_version_id=version_id,
        location="log:char=20-27",
        db=test_db,
    )
    assert snippet == "Line 2\n"

    with pytest.raises(ValueError, match="Invalid char range"):
        SandboxRunActivity.resolve_log_evidence(
            artifact_version_id=version_id,
            location="log:char=0-1000",
            db=test_db,
        )

    with pytest.raises(ValueError, match="Invalid log location format"):
        SandboxRunActivity.resolve_log_evidence(
            artifact_version_id=version_id,
            location="log:invalid",
            db=test_db,
        )


def test_sandbox_run_activity__script_hangs__times_out(test_db, test_storage):
    """Sandbox run times out for hanging script."""
    from apps.worker.sandbox_run import DockerError, SandboxRunActivity

    workspace_id = str(uuid.uuid4())
    script_artifact_id = str(uuid.uuid4())
    log_artifact_id = str(uuid.uuid4())

    _ensure_agent(test_db)
    _insert_workspace(test_db, workspace_id)
    _insert_artifact(
        test_db,
        artifact_id=script_artifact_id,
        workspace_id=workspace_id,
        short_id="SCR6",
        artifact_type="code",
        storage_uri=f"s3://agora/{workspace_id}/artifacts/{script_artifact_id}/",
        created_by=TEST_AGENT_ID,
    )

    script_content = "import time\ntime.sleep(1000)"
    version_id = str(uuid.uuid4())
    script_storage_uri = f"s3://agora/{workspace_id}/artifacts/{script_artifact_id}/v1/script.py"
    test_storage.put_object(script_storage_uri, script_content.encode("utf-8"))
    _insert_artifact_version(
        test_db,
        version_id=version_id,
        artifact_id=script_artifact_id,
        version=1,
        storage_uri=script_storage_uri,
        content_hash="test_hash6",
        created_by=TEST_AGENT_ID,
    )

    _insert_artifact(
        test_db,
        artifact_id=log_artifact_id,
        workspace_id=workspace_id,
        short_id="LOG6",
        artifact_type="log",
        storage_uri=f"s3://agora/{workspace_id}/artifacts/{log_artifact_id}/",
        created_by=TEST_AGENT_ID,
    )
    test_db.commit()

    activity = SandboxRunActivity(test_storage, test_db)
    with pytest.raises(DockerError, match="timed out"):
        activity.run_sandbox(
            artifact_id=log_artifact_id,
            workspace_id=workspace_id,
            script_artifact_id=script_artifact_id,
            timeout_seconds=2,
        )
