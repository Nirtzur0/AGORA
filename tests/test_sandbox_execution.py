"""
Integration tests for Component 17: Sandbox Execution Activity

Tests per Docs/06 exit criteria:
- Run a repo script that prints deterministic output
- Log artifact contains output
- Evidence pointer log:char=... resolves

Tests sandbox execution per spec §6.4:
- Docker container execution with constraints
- Log capture (stdout/stderr)
- Config/provenance storage
- Resource limits and timeouts
- Evidence resolution
"""
import pytest
import uuid
import json
import tempfile
import shutil
from pathlib import Path


def test_sandbox_run_activity(test_db, test_storage):
    """Test sandbox execution activity with deterministic output."""
    from apps.worker.sandbox_run import SandboxRunActivity
    
    workspace_id = str(uuid.uuid4())
    script_artifact_id = str(uuid.uuid4())
    log_artifact_id = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"}
    )
    
    # Create script artifact
    test_db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
        VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
        """,
        {
            "id": script_artifact_id,
            "workspace_id": workspace_id,
            "short_id": "SCR1",
            "type": "code",
            "metadata": json.dumps({"language": "python"}),
            "storage_uri": f"s3://agora/{workspace_id}/artifacts/{script_artifact_id}/",
            "created_by": "test_agent"
        }
    )
    
    # Store script content in MinIO
    script_content = """#!/usr/bin/env python3
print("Hello from sandbox!")
print("Line 2")
print("Line 3")
"""
    version_id = str(uuid.uuid4())
    script_path = f"{workspace_id}/artifacts/{script_artifact_id}/v{version_id}/script.py"
    
    from io import BytesIO
    test_storage.put_object(
        "agora",
        script_path,
        BytesIO(script_content.encode('utf-8')),
        len(script_content.encode('utf-8')),
        content_type="text/plain"
    )
    
    # Create artifact version
    test_db.execute(
        """
        INSERT INTO artifact_versions (id, artifact_id, version_number, content_hash, location, created_by, created_at)
        VALUES (:id, :artifact_id, :version_number, :content_hash, :location, :created_by, NOW())
        """,
        {
            "id": version_id,
            "artifact_id": script_artifact_id,
            "version_number": 1,
            "content_hash": "test_hash",
            "location": "script.py",
            "created_by": "test_agent"
        }
    )
    
    # Create log artifact
    test_db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
        VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
        """,
        {
            "id": log_artifact_id,
            "workspace_id": workspace_id,
            "short_id": "LOG1",
            "type": "log",
            "metadata": json.dumps({"source": "sandbox_execution"}),
            "storage_uri": f"s3://agora/{workspace_id}/artifacts/{log_artifact_id}/",
            "created_by": "test_agent"
        }
    )
    
    test_db.commit()
    
    # Execute sandbox
    activity = SandboxRunActivity(test_storage, test_db)
    
    result = activity.run_sandbox(
        artifact_id=log_artifact_id,
        workspace_id=workspace_id,
        script_artifact_id=script_artifact_id,
        parameters=None,
        created_by="test_agent",
        activity_run_id=None,
        image="python:3.11-slim",
        timeout_seconds=60,
        memory_limit="256m",
        cpu_limit="0.5"
    )
    
    # Verify result
    assert result["artifact_id"] == log_artifact_id
    assert "version_id" in result
    assert "config_artifact_id" in result
    assert result["exit_code"] == 0
    assert result["stdout_length"] > 0
    
    # Verify log artifact version created
    log_version = test_db.execute(
        "SELECT id, content_hash, location FROM artifact_versions WHERE artifact_id = :id",
        {"id": log_artifact_id}
    ).fetchone()
    
    assert log_version is not None
    assert log_version[2].startswith("log:char=")
    
    # Verify log content in MinIO
    log_path = f"{workspace_id}/artifacts/{log_artifact_id}/v{log_version[0]}/log.txt"
    response = test_storage.get_object("agora", log_path)
    log_content = response.read().decode('utf-8')
    response.close()
    response.release_conn()
    
    assert "Hello from sandbox!" in log_content
    assert "Line 2" in log_content
    assert "Line 3" in log_content
    
    # Verify config artifact created
    config_artifact = test_db.execute(
        "SELECT id, type FROM artifacts WHERE id = :id",
        {"id": result["config_artifact_id"]}
    ).fetchone()
    
    assert config_artifact is not None
    assert config_artifact[1] == "config"
    
    # Verify log entry created
    log_entry = test_db.execute(
        "SELECT message, metadata FROM logs WHERE workspace_id = :id",
        {"id": workspace_id}
    ).fetchone()
    
    assert log_entry is not None
    assert "Sandbox execution completed" in log_entry[0]
    metadata = json.loads(log_entry[1])
    assert metadata["event"] == "sandbox_execution"
    assert metadata["exit_code"] == 0


def test_sandbox_run_with_parameters(test_db, test_storage):
    """Test sandbox execution with environment variables and arguments."""
    from apps.worker.sandbox_run import SandboxRunActivity
    
    workspace_id = str(uuid.uuid4())
    script_artifact_id = str(uuid.uuid4())
    log_artifact_id = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"}
    )
    
    # Create script that uses env vars
    test_db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
        VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
        """,
        {
            "id": script_artifact_id,
            "workspace_id": workspace_id,
            "short_id": "SCR2",
            "type": "code",
            "metadata": json.dumps({"language": "python"}),
            "storage_uri": f"s3://agora/{workspace_id}/artifacts/{script_artifact_id}/",
            "created_by": "test_agent"
        }
    )
    
    # Script that reads environment variable
    script_content = """#!/usr/bin/env python3
import os
print(f"ENV_VAR={os.environ.get('TEST_VAR', 'not_set')}")
"""
    version_id = str(uuid.uuid4())
    script_path = f"{workspace_id}/artifacts/{script_artifact_id}/v{version_id}/script.py"
    
    from io import BytesIO
    test_storage.put_object(
        "agora",
        script_path,
        BytesIO(script_content.encode('utf-8')),
        len(script_content.encode('utf-8')),
        content_type="text/plain"
    )
    
    test_db.execute(
        """
        INSERT INTO artifact_versions (id, artifact_id, version_number, content_hash, location, created_by, created_at)
        VALUES (:id, :artifact_id, :version_number, :content_hash, :location, :created_by, NOW())
        """,
        {
            "id": version_id,
            "artifact_id": script_artifact_id,
            "version_number": 1,
            "content_hash": "test_hash2",
            "location": "script.py",
            "created_by": "test_agent"
        }
    )
    
    # Create log artifact
    test_db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
        VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
        """,
        {
            "id": log_artifact_id,
            "workspace_id": workspace_id,
            "short_id": "LOG2",
            "type": "log",
            "metadata": json.dumps({"source": "sandbox_execution"}),
            "storage_uri": f"s3://agora/{workspace_id}/artifacts/{log_artifact_id}/",
            "created_by": "test_agent"
        }
    )
    
    test_db.commit()
    
    # Execute with parameters
    activity = SandboxRunActivity(test_storage, test_db)
    
    result = activity.run_sandbox(
        artifact_id=log_artifact_id,
        workspace_id=workspace_id,
        script_artifact_id=script_artifact_id,
        parameters={"env": {"TEST_VAR": "test_value"}},
        created_by="test_agent"
    )
    
    assert result["exit_code"] == 0
    
    # Verify log contains env var
    log_version = test_db.execute(
        "SELECT id FROM artifact_versions WHERE artifact_id = :id",
        {"id": log_artifact_id}
    ).fetchone()
    
    log_path = f"{workspace_id}/artifacts/{log_artifact_id}/v{log_version[0]}/log.txt"
    response = test_storage.get_object("agora", log_path)
    log_content = response.read().decode('utf-8')
    response.close()
    response.release_conn()
    
    assert "ENV_VAR=test_value" in log_content


def test_log_evidence_resolution(test_db, test_storage):
    """Test log evidence pointer resolution (log:char=start-end)."""
    from apps.worker.sandbox_run import SandboxRunActivity
    
    workspace_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"}
    )
    
    # Create log artifact
    test_db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, storage_uri, created_by, created_at)
        VALUES (:id, :workspace_id, :short_id, :type, :storage_uri, :created_by, NOW())
        """,
        {
            "id": artifact_id,
            "workspace_id": workspace_id,
            "short_id": "LOG3",
            "type": "log",
            "storage_uri": f"s3://agora/{workspace_id}/artifacts/{artifact_id}/",
            "created_by": "test_agent"
        }
    )
    
    # Store log content
    log_content = "Hello from sandbox!\nLine 2\nLine 3\n"
    log_path = f"{workspace_id}/artifacts/{artifact_id}/v{version_id}/log.txt"
    
    from io import BytesIO
    test_storage.put_object(
        "agora",
        log_path,
        BytesIO(log_content.encode('utf-8')),
        len(log_content.encode('utf-8')),
        content_type="text/plain"
    )
    
    # Create artifact version
    test_db.execute(
        """
        INSERT INTO artifact_versions (id, artifact_id, version_number, content_hash, location, created_by, created_at)
        VALUES (:id, :artifact_id, :version_number, :content_hash, :location, :created_by, NOW())
        """,
        {
            "id": version_id,
            "artifact_id": artifact_id,
            "version_number": 1,
            "content_hash": "test_hash3",
            "location": f"log:char=0-{len(log_content)}",
            "created_by": "test_agent"
        }
    )
    
    test_db.commit()
    
    # Test resolution of first line
    snippet = SandboxRunActivity.resolve_log_evidence(
        artifact_version_id=version_id,
        location="log:char=0-20",
        db=test_db
    )
    
    assert snippet == "Hello from sandbox!\n"
    
    # Test resolution of second line
    snippet = SandboxRunActivity.resolve_log_evidence(
        artifact_version_id=version_id,
        location="log:char=20-27",
        db=test_db
    )
    
    assert snippet == "Line 2\n"
    
    # Test invalid range (out of bounds)
    with pytest.raises(ValueError, match="Invalid char range"):
        SandboxRunActivity.resolve_log_evidence(
            artifact_version_id=version_id,
            location="log:char=0-1000",
            db=test_db
        )
    
    # Test invalid format
    with pytest.raises(ValueError, match="Invalid log location format"):
        SandboxRunActivity.resolve_log_evidence(
            artifact_version_id=version_id,
            location="log:invalid",
            db=test_db
        )


def test_sandbox_run_endpoint(test_client, test_db, test_storage, mock_agent_token):
    """Test POST /workspaces/{id}/requests/run_sandbox endpoint."""
    workspace_id = str(uuid.uuid4())
    script_artifact_id = str(uuid.uuid4())
    agent_id = "test_agent_id"
    
    # Create workspace
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"}
    )
    
    # Create script artifact
    test_db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
        VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
        """,
        {
            "id": script_artifact_id,
            "workspace_id": workspace_id,
            "short_id": "SCR4",
            "type": "code",
            "metadata": json.dumps({"language": "python"}),
            "storage_uri": f"s3://agora/{workspace_id}/artifacts/{script_artifact_id}/",
            "created_by": agent_id
        }
    )
    
    # Store script
    script_content = """print("Test output")"""
    version_id = str(uuid.uuid4())
    script_path = f"{workspace_id}/artifacts/{script_artifact_id}/v{version_id}/script.py"
    
    from io import BytesIO
    test_storage.put_object(
        "agora",
        script_path,
        BytesIO(script_content.encode('utf-8')),
        len(script_content.encode('utf-8')),
        content_type="text/plain"
    )
    
    test_db.execute(
        """
        INSERT INTO artifact_versions (id, artifact_id, version_number, content_hash, location, created_by, created_at)
        VALUES (:id, :artifact_id, :version_number, :content_hash, :location, :created_by, NOW())
        """,
        {
            "id": version_id,
            "artifact_id": script_artifact_id,
            "version_number": 1,
            "content_hash": "test_hash4",
            "location": "script.py",
            "created_by": agent_id
        }
    )
    
    test_db.commit()
    
    # Make request
    response = test_client.post(
        f"/workspaces/{workspace_id}/requests/run_sandbox",
        headers={"Authorization": f"Bearer {mock_agent_token}"},
        json={
            "script_artifact_id": script_artifact_id,
            "timeout_seconds": 60,
            "memory_limit": "256m"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "request_id" in data
    assert "activity_run_id" in data
    assert "log_artifact_id" in data
    assert "config_artifact_id" in data
    assert "completed with exit code" in data["message"]
    
    # Verify log artifact created
    log_artifact = test_db.execute(
        "SELECT id, type FROM artifacts WHERE id = :id",
        {"id": data["log_artifact_id"]}
    ).fetchone()
    
    assert log_artifact is not None
    assert log_artifact[1] == "log"
    
    # Verify activity_run created
    activity_run = test_db.execute(
        "SELECT status, activity_type FROM activity_runs WHERE id = :id",
        {"id": data["activity_run_id"]}
    ).fetchone()
    
    assert activity_run is not None
    assert activity_run[0] == "completed"
    assert activity_run[1] == "sandbox_run"


def test_sandbox_budget_enforcement(test_client, test_db, mock_agent_token):
    """Test per-workspace sandbox budget enforcement (429 + Retry-After)."""
    workspace_id = str(uuid.uuid4())
    script_artifact_id = str(uuid.uuid4())
    agent_id = "test_agent_id"
    
    # Create workspace
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"}
    )
    
    # Create script artifact
    test_db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, storage_uri, created_by, created_at)
        VALUES (:id, :workspace_id, :short_id, :type, :storage_uri, :created_by, NOW())
        """,
        {
            "id": script_artifact_id,
            "workspace_id": workspace_id,
            "short_id": "SCR5",
            "type": "code",
            "storage_uri": f"s3://agora/{workspace_id}/artifacts/{script_artifact_id}/",
            "created_by": agent_id
        }
    )
    
    # Create 100 completed sandbox runs (at budget limit)
    for i in range(100):
        run_id = str(uuid.uuid4())
        test_db.execute(
            """
            INSERT INTO activity_runs (id, workflow_run_id, activity_type, status, input, created_at)
            VALUES (:id, :workflow_run_id, :activity_type, :status, :input, NOW())
            """,
            {
                "id": run_id,
                "workflow_run_id": None,
                "activity_type": "sandbox_run",
                "status": "completed",
                "input": json.dumps({"artifact_id": str(uuid.uuid4()), "workspace_id": workspace_id})
            }
        )
    
    test_db.commit()
    
    # Try to run another sandbox - should get 429
    response = test_client.post(
        f"/workspaces/{workspace_id}/requests/run_sandbox",
        headers={"Authorization": f"Bearer {mock_agent_token}"},
        json={"script_artifact_id": script_artifact_id}
    )
    
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert "budget exhausted" in response.json()["detail"]


def test_sandbox_run_timeout(test_db, test_storage):
    """Test sandbox execution timeout enforcement."""
    from apps.worker.sandbox_run import SandboxRunActivity, DockerError
    
    workspace_id = str(uuid.uuid4())
    script_artifact_id = str(uuid.uuid4())
    log_artifact_id = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"}
    )
    
    # Create script that sleeps forever
    test_db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, storage_uri, created_by, created_at)
        VALUES (:id, :workspace_id, :short_id, :type, :storage_uri, :created_by, NOW())
        """,
        {
            "id": script_artifact_id,
            "workspace_id": workspace_id,
            "short_id": "SCR6",
            "type": "code",
            "storage_uri": f"s3://agora/{workspace_id}/artifacts/{script_artifact_id}/",
            "created_by": "test_agent"
        }
    )
    
    script_content = """import time\ntime.sleep(1000)"""
    version_id = str(uuid.uuid4())
    script_path = f"{workspace_id}/artifacts/{script_artifact_id}/v{version_id}/script.py"
    
    from io import BytesIO
    test_storage.put_object(
        "agora",
        script_path,
        BytesIO(script_content.encode('utf-8')),
        len(script_content.encode('utf-8')),
        content_type="text/plain"
    )
    
    test_db.execute(
        """
        INSERT INTO artifact_versions (id, artifact_id, version_number, content_hash, location, created_by, created_at)
        VALUES (:id, :artifact_id, :version_number, :content_hash, :location, :created_by, NOW())
        """,
        {
            "id": version_id,
            "artifact_id": script_artifact_id,
            "version_number": 1,
            "content_hash": "test_hash6",
            "location": "script.py",
            "created_by": "test_agent"
        }
    )
    
    test_db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, storage_uri, created_by, created_at)
        VALUES (:id, :workspace_id, :short_id, :type, :storage_uri, :created_by, NOW())
        """,
        {
            "id": log_artifact_id,
            "workspace_id": workspace_id,
            "short_id": "LOG6",
            "type": "log",
            "storage_uri": f"s3://agora/{workspace_id}/artifacts/{log_artifact_id}/",
            "created_by": "test_agent"
        }
    )
    
    test_db.commit()
    
    # Execute with short timeout
    activity = SandboxRunActivity(test_storage, test_db)
    
    with pytest.raises(DockerError, match="timed out"):
        activity.run_sandbox(
            artifact_id=log_artifact_id,
            workspace_id=workspace_id,
            script_artifact_id=script_artifact_id,
            timeout_seconds=2  # Very short timeout
        )
