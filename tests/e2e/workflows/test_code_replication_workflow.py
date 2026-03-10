"""
Integration tests for Component 18: Code Replication Workflow

Tests per milestone/checklist exit criteria:
- Full run: ingest repo -> run sandbox -> claim + cite log -> draft -> citation_check PASS

Tests code replication workflow per spec §5.2, §12.3:
- Workflow B end-to-end flow
- Repo ingestion + sandbox execution integration
- Agent task creation for result summarization
- Citation check on draft citing log artifact
"""

import asyncio
import json
import uuid

import pytest

from tests.helpers.factories import (
    insert_agent,
    insert_artifact,
    insert_artifact_version,
    insert_claim,
    insert_workspace,
    make_artifact_version_uri,
    sha256_hex,
)
from tests.helpers.git_repo import temporary_git_repo


EXPERIMENT_SCRIPT = """#!/usr/bin/env python3
print("Experiment starting...")
import math
result = math.sqrt(144)
print(f"Result: {result}")
print("Experiment complete!")
"""


ANALYSIS_SCRIPT = """#!/usr/bin/env python3
# Statistical analysis
import statistics
data = [1, 2, 3, 4, 5]
mean = statistics.mean(data)
print(f"Mean: {mean}")
print(f"Median: {statistics.median(data)}")
"""


FAILING_SCRIPT = """#!/usr/bin/env python3
print("Starting...")
raise ValueError("Intentional error for testing")
print("This won't print")
"""


CONFIG_SCRIPT = """#!/usr/bin/env python3
import os
config_value = os.environ.get('CONFIG_PARAM', 'default')
print(f"Config: {config_value}")
"""


def _create_workspace(test_db, *, name: str = "Test Workspace") -> str:
    return insert_workspace(test_db, name=name, phase="active")


def _read_artifact_version_text(test_db, test_storage, artifact_version_id: str) -> str:
    row = test_db.execute(
        "SELECT storage_uri FROM artifact_versions WHERE id = :id",
        {"id": artifact_version_id},
    ).fetchone()
    assert row is not None
    return test_storage.get_object(row[0]).read().decode("utf-8")


def _run_code_replication_workflow(
    test_db,
    *,
    workspace_id: str,
    repo_url: str,
    script_path: str,
    commit_hash: str,
    sandbox_parameters=None,
):
    from apps.worker.code_replication_workflow import code_replication_workflow

    return asyncio.run(
        code_replication_workflow(
            workspace_id=workspace_id,
            repo_url=repo_url,
            script_path=script_path,
            commit_hash=commit_hash,
            sandbox_parameters=sandbox_parameters,
            db=test_db,
        )
    )


def _coerce_task_payload(payload):
    if isinstance(payload, str):
        return json.loads(payload)
    return payload or {}


def test_code_replication_workflow__happy_path__completes(test_db, test_storage):
    """Test full code replication workflow end-to-end."""

    # Arrange
    workspace_id = _create_workspace(test_db)

    with temporary_git_repo({"experiment.py": EXPERIMENT_SCRIPT}, message="Add experiment script") as (
        repo_dir,
        commit_hash,
    ):
        # Act
        result = _run_code_replication_workflow(
            test_db,
            workspace_id=workspace_id,
            repo_url=repo_dir,
            script_path="experiment.py",
            commit_hash=commit_hash,
        )

    # Assert
    assert "workflow_run_id" in result
    assert "repo_artifact_id" in result
    assert "log_artifact_id" in result
    assert "task_id" in result
    assert result["exit_code"] == 0

    workflow_run = test_db.execute(
        "SELECT workflow_type, status FROM workflow_runs WHERE id = :id",
        {"id": result["workflow_run_id"]},
    ).fetchone()
    assert workflow_run is not None
    assert workflow_run[0] == "code_replication"
    assert workflow_run[1] == "completed"

    repo_artifact = test_db.execute(
        "SELECT type FROM artifacts WHERE id = :id",
        {"id": result["repo_artifact_id"]},
    ).fetchone()
    assert repo_artifact is not None
    assert repo_artifact[0] == "code"

    log_artifact = test_db.execute(
        "SELECT type FROM artifacts WHERE id = :id",
        {"id": result["log_artifact_id"]},
    ).fetchone()
    assert log_artifact is not None
    assert log_artifact[0] == "log"

    log_content = _read_artifact_version_text(test_db, test_storage, result["log_artifact_version_id"])
    assert "Experiment starting..." in log_content
    assert "Result: 12.0" in log_content
    assert "Experiment complete!" in log_content

    task = test_db.execute(
        "SELECT type, status, payload FROM agent_tasks WHERE id = :id",
        {"id": result["task_id"]},
    ).fetchone()
    assert task is not None
    assert task[0] == "summarize_results"
    assert task[1] == "open"
    payload = _coerce_task_payload(task[2])
    assert payload["inputs"][0]["artifact_version_id"] == result["log_artifact_version_id"]

    activities = test_db.execute(
        """
        SELECT activity_type, status
        FROM activity_runs
        WHERE workflow_run_id = :workflow_run_id
        ORDER BY started_at
        """,
        {"workflow_run_id": result["workflow_run_id"]},
    ).fetchall()
    assert len(activities) == 2
    assert activities[0][0] == "repo_ingest"
    assert activities[0][1] == "completed"
    assert activities[1][0] == "sandbox_run"
    assert activities[1][1] == "completed"


def test_code_replication_workflow__with_draft_and_citation_check__completes(test_db, test_storage):
    """Test full workflow including draft creation and citation check."""
    from apps.worker.citation_check import citation_check_activity

    # Arrange
    workspace_id = _create_workspace(test_db)
    agent = insert_agent(test_db, moltbook_id="test_moltbook", name="Test Agent")
    claim_id = insert_claim(
        test_db,
        workspace_id=workspace_id,
        kind="fact",
        text="Mean value was computed",
        created_by=agent.agent_id,
    )

    with temporary_git_repo({"analysis.py": ANALYSIS_SCRIPT}, message="Add analysis script") as (
        repo_dir,
        commit_hash,
    ):
        workflow_result = _run_code_replication_workflow(
            test_db,
            workspace_id=workspace_id,
            repo_url=repo_dir,
            script_path="analysis.py",
            commit_hash=commit_hash,
        )

    draft_artifact_id = insert_artifact(
        test_db,
        workspace_id=workspace_id,
        short_id="D1",
        type="draft",
        metadata={"purpose": "experiment_results"},
        created_by=agent.agent_id,
    )

    log_version_id = workflow_result["log_artifact_version_id"]
    log_content = _read_artifact_version_text(test_db, test_storage, log_version_id)

    mean_pos = log_content.find("Mean:")
    assert mean_pos >= 0
    mean_end = log_content.find("\n", mean_pos)
    if mean_end < 0:
        mean_end = len(log_content)

    draft_content = f"""# Experiment Results

[[claim:{claim_id}]]The analysis computed a mean value.[[/claim]]
[[cite:{log_version_id}|log:char={mean_pos}-{mean_end}]]

The execution completed successfully.
"""

    draft_bytes = draft_content.encode("utf-8")
    draft_storage_uri = make_artifact_version_uri(workspace_id, draft_artifact_id, 1, "draft.md")
    test_storage.put_object(draft_storage_uri, draft_bytes)

    draft_version_id = insert_artifact_version(
        test_db,
        artifact_id=draft_artifact_id,
        version=1,
        storage_uri=draft_storage_uri,
        content_hash=sha256_hex(draft_bytes),
        created_by=agent.agent_id,
    )

    # Act
    check_result = citation_check_activity(draft_artifact_version_id=draft_version_id, db=test_db)

    # Assert
    assert check_result.coverage_pass is True
    assert check_result.resolves_pass is True

    rule_checks = test_db.execute(
        """
        SELECT rule_name, status
        FROM rule_checks
        WHERE target_type = 'draft_version'
          AND target_id = :version_id
        """,
        {"version_id": draft_version_id},
    ).fetchall()

    assert len(rule_checks) >= 2
    rule_dict = {row[0]: row[1] for row in rule_checks}
    assert rule_dict.get("citation_coverage") == "pass"
    assert rule_dict.get("citation_resolves") == "pass"


def test_code_replication_workflow__script_error__records_failure(test_db, test_storage):
    """Test workflow handles script execution errors gracefully."""

    # Arrange
    workspace_id = _create_workspace(test_db)

    with temporary_git_repo({"fail.py": FAILING_SCRIPT}, message="Add failing script") as (
        repo_dir,
        commit_hash,
    ):
        # Act
        result = _run_code_replication_workflow(
            test_db,
            workspace_id=workspace_id,
            repo_url=repo_dir,
            script_path="fail.py",
            commit_hash=commit_hash,
        )

    # Assert
    assert result["exit_code"] != 0
    assert "log_artifact_id" in result

    log_content = _read_artifact_version_text(test_db, test_storage, result["log_artifact_version_id"])
    assert "Starting..." in log_content
    assert "ValueError" in log_content or "Traceback" in log_content


def test_code_replication_workflow__parameters__passed_to_sandbox(test_db, test_storage):
    """Test workflow with sandbox parameters (env vars)."""

    # Arrange
    workspace_id = _create_workspace(test_db)

    with temporary_git_repo({"config_test.py": CONFIG_SCRIPT}, message="Add config test script") as (
        repo_dir,
        commit_hash,
    ):
        # Act
        result = _run_code_replication_workflow(
            test_db,
            workspace_id=workspace_id,
            repo_url=repo_dir,
            script_path="config_test.py",
            commit_hash=commit_hash,
            sandbox_parameters={"env": {"CONFIG_PARAM": "test_value"}},
        )

    # Assert
    log_content = _read_artifact_version_text(test_db, test_storage, result["log_artifact_version_id"])
    assert "Config: test_value" in log_content


def test_code_replication_workflow__invalid_repo_url__records_failed_activity_and_workflow(
    test_db, test_storage
):
    # Arrange
    workspace_id = _create_workspace(test_db, name="Code Replication Failure Path")
    invalid_repo_url = f"/tmp/agora-missing-repo-{uuid.uuid4()}"

    # Act
    with pytest.raises(Exception):
        _run_code_replication_workflow(
            test_db,
            workspace_id=workspace_id,
            repo_url=invalid_repo_url,
            script_path="experiment.py",
            commit_hash=None,
        )

    # Assert workflow marked failed
    workflow_run = test_db.execute(
        """
        SELECT id, status
        FROM workflow_runs
        WHERE workspace_id = :workspace_id
          AND workflow_type = 'code_replication'
        ORDER BY started_at DESC
        LIMIT 1
        """,
        {"workspace_id": workspace_id},
    ).fetchone()
    assert workflow_run is not None
    workflow_run_id = str(workflow_run[0])
    assert workflow_run[1] == "failed"

    # Assert repo_ingest activity is explicitly marked failed (not left running)
    activities = test_db.execute(
        """
        SELECT activity_type, status
        FROM activity_runs
        WHERE workflow_run_id = :workflow_run_id
        ORDER BY started_at
        """,
        {"workflow_run_id": workflow_run_id},
    ).fetchall()
    assert activities
    assert activities[0][0] == "repo_ingest"
    assert activities[0][1] == "failed"
    assert all(status != "running" for _, status in activities)
