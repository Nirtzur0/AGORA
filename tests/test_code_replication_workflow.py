"""
Integration tests for Component 18: Code Replication Workflow

Tests per Docs/06 exit criteria:
- Full run: ingest repo -> run sandbox -> claim + cite log -> draft -> citation_check PASS

Tests code replication workflow per spec §5.2, §12.3:
- Workflow B end-to-end flow
- Repo ingestion + sandbox execution integration
- Agent task creation for result summarization
- Citation check on draft citing log artifact
"""
import pytest
import uuid
import json
import tempfile
import shutil
from pathlib import Path
import tarfile
import subprocess


def test_code_replication_workflow_full(test_db, test_storage):
    """Test full code replication workflow end-to-end."""
    import asyncio
    from apps.worker.code_replication_workflow import code_replication_workflow
    
    workspace_id = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"}
    )
    test_db.commit()
    
    # Create a test git repo
    test_repo_dir = tempfile.mkdtemp(prefix="test_repo_")
    
    try:
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=test_repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=test_repo_dir,
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=test_repo_dir,
            check=True,
            capture_output=True
        )
        
        # Create test script
        script_path = Path(test_repo_dir) / "experiment.py"
        script_path.write_text("""#!/usr/bin/env python3
print("Experiment starting...")
import math
result = math.sqrt(144)
print(f"Result: {result}")
print("Experiment complete!")
""")
        
        # Commit script
        subprocess.run(["git", "add", "."], cwd=test_repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add experiment script"],
            cwd=test_repo_dir,
            check=True,
            capture_output=True
        )
        
        # Get commit hash
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=test_repo_dir,
            check=True,
            capture_output=True,
            text=True
        )
        commit_hash = commit_result.stdout.strip()
        
        # Run code replication workflow
        result = asyncio.run(
            code_replication_workflow(
                workspace_id=workspace_id,
                repo_url=test_repo_dir,  # Use local path for testing
                script_path="experiment.py",
                commit_hash=commit_hash,
                sandbox_parameters=None,
                db=test_db
            )
        )
        
        # Verify workflow completed
        assert "workflow_run_id" in result
        assert "repo_artifact_id" in result
        assert "log_artifact_id" in result
        assert "task_id" in result
        assert result["exit_code"] == 0
        
        # Verify workflow_run created
        workflow_run = test_db.execute(
            "SELECT workflow_type, status FROM workflow_runs WHERE id = :id",
            {"id": result["workflow_run_id"]}
        ).fetchone()
        
        assert workflow_run is not None
        assert workflow_run[0] == "code_replication"
        assert workflow_run[1] == "completed"
        
        # Verify repo artifact created
        repo_artifact = test_db.execute(
            "SELECT type FROM artifacts WHERE id = :id",
            {"id": result["repo_artifact_id"]}
        ).fetchone()
        
        assert repo_artifact is not None
        assert repo_artifact[0] == "code"
        
        # Verify log artifact created
        log_artifact = test_db.execute(
            "SELECT type FROM artifacts WHERE id = :id",
            {"id": result["log_artifact_id"]}
        ).fetchone()
        
        assert log_artifact is not None
        assert log_artifact[0] == "log"
        
        # Verify log content
        log_path = f"{workspace_id}/artifacts/{result['log_artifact_id']}/v{result['log_artifact_version_id']}/log.txt"
        response = test_storage.get_object("agora", log_path)
        log_content = response.read().decode('utf-8')
        response.close()
        response.release_conn()
        
        assert "Experiment starting..." in log_content
        assert "Result: 12.0" in log_content
        assert "Experiment complete!" in log_content
        
        # Verify agent_task created
        task = test_db.execute(
            "SELECT task_type, status, target_artifact_id FROM agent_tasks WHERE id = :id",
            {"id": result["task_id"]}
        ).fetchone()
        
        assert task is not None
        assert task[0] == "summarize_results"
        assert task[1] == "pending"
        assert task[2] == result["log_artifact_id"]
        
        # Verify activity_runs created for both activities
        activities = test_db.execute(
            """
            SELECT activity_type, status
            FROM activity_runs
            WHERE workflow_run_id = :workflow_run_id
            ORDER BY created_at
            """,
            {"workflow_run_id": result["workflow_run_id"]}
        ).fetchall()
        
        assert len(activities) == 2
        assert activities[0][0] == "repo_ingest"
        assert activities[0][1] == "completed"
        assert activities[1][0] == "sandbox_run"
        assert activities[1][1] == "completed"
        
    finally:
        shutil.rmtree(test_repo_dir, ignore_errors=True)


def test_code_replication_with_draft_and_citation_check(test_db, test_storage):
    """Test full workflow including draft creation and citation check."""
    import asyncio
    from apps.worker.code_replication_workflow import code_replication_workflow
    from apps.worker.citation_check import CitationCheckActivity
    
    workspace_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"}
    )
    
    # Create agent
    test_db.execute(
        "INSERT INTO agents (id, moltbook_id, display_name) VALUES (:id, :moltbook_id, :display_name)",
        {"id": agent_id, "moltbook_id": "test_moltbook", "display_name": "Test Agent"}
    )
    
    test_db.commit()
    
    # Create test repo
    test_repo_dir = tempfile.mkdtemp(prefix="test_repo_")
    
    try:
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=test_repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=test_repo_dir,
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=test_repo_dir,
            check=True,
            capture_output=True
        )
        
        # Create test script
        script_path = Path(test_repo_dir) / "analysis.py"
        script_path.write_text("""#!/usr/bin/env python3
# Statistical analysis
import statistics
data = [1, 2, 3, 4, 5]
mean = statistics.mean(data)
print(f"Mean: {mean}")
print(f"Median: {statistics.median(data)}")
""")
        
        subprocess.run(["git", "add", "."], cwd=test_repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add analysis script"],
            cwd=test_repo_dir,
            check=True,
            capture_output=True
        )
        
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=test_repo_dir,
            check=True,
            capture_output=True,
            text=True
        )
        commit_hash = commit_result.stdout.strip()
        
        # Run workflow
        workflow_result = asyncio.run(
            code_replication_workflow(
                workspace_id=workspace_id,
                repo_url=test_repo_dir,
                script_path="analysis.py",
                commit_hash=commit_hash,
                db=test_db
            )
        )
        
        # Now simulate agent creating a draft with citation to log
        draft_artifact_id = str(uuid.uuid4())
        
        test_db.execute(
            """
            INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
            VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
            """,
            {
                "id": draft_artifact_id,
                "workspace_id": workspace_id,
                "short_id": "D1",
                "type": "draft",
                "metadata": json.dumps({"purpose": "experiment_results"}),
                "storage_uri": f"s3://agora/{workspace_id}/artifacts/{draft_artifact_id}/",
                "created_by": agent_id
            }
        )
        
        # Create draft content that cites the log
        log_version_id = workflow_result["log_artifact_version_id"]
        
        # Get actual log length for citation
        log_path = f"{workspace_id}/artifacts/{workflow_result['log_artifact_id']}/v{log_version_id}/log.txt"
        response = test_storage.get_object("agora", log_path)
        log_content = response.read().decode('utf-8')
        response.close()
        response.release_conn()
        
        # Find position of "Mean:" in log
        mean_pos = log_content.find("Mean:")
        mean_end = log_content.find("\n", mean_pos)
        
        draft_content = f"""# Experiment Results

[[claim:mean_value]]The analysis computed a mean value.[[/claim]]

[[cite:{log_version_id}:log:char={mean_pos}-{mean_end}]]

The execution completed successfully.
"""
        
        # Store draft in MinIO
        draft_version_id = str(uuid.uuid4())
        draft_object_path = f"{workspace_id}/artifacts/{draft_artifact_id}/v{draft_version_id}/draft.md"
        
        from io import BytesIO
        draft_bytes = draft_content.encode('utf-8')
        test_storage.put_object(
            "agora",
            draft_object_path,
            BytesIO(draft_bytes),
            len(draft_bytes),
            content_type="text/markdown"
        )
        
        # Create draft version
        import hashlib
        draft_hash = hashlib.sha256(draft_bytes).hexdigest()
        
        test_db.execute(
            """
            INSERT INTO artifact_versions (id, artifact_id, version_number, content_hash, location, created_by, created_at)
            VALUES (:id, :artifact_id, :version_number, :content_hash, :location, :created_by, NOW())
            """,
            {
                "id": draft_version_id,
                "artifact_id": draft_artifact_id,
                "version_number": 1,
                "content_hash": draft_hash,
                "location": "draft.md",
                "created_by": agent_id
            }
        )
        
        test_db.commit()
        
        # Run citation check on draft
        citation_activity = CitationCheckActivity(test_storage, test_db)
        
        check_result = citation_activity.check_draft_citations(
            draft_artifact_version_id=draft_version_id,
            workspace_id=workspace_id
        )
        
        # Verify citation check passed
        assert check_result["status"] == "pass"
        assert check_result["citation_coverage_pass"] is True
        assert check_result["citation_resolves_pass"] is True
        
        # Verify rule_checks created
        rule_checks = test_db.execute(
            """
            SELECT rule_name, status
            FROM rule_checks
            WHERE target_type = 'draft_version'
              AND target_id = :version_id
            """,
            {"version_id": draft_version_id}
        ).fetchall()
        
        assert len(rule_checks) >= 2
        rule_dict = {r[0]: r[1] for r in rule_checks}
        assert rule_dict.get("citation_coverage") == "pass"
        assert rule_dict.get("citation_resolves") == "pass"
        
    finally:
        shutil.rmtree(test_repo_dir, ignore_errors=True)


def test_code_replication_workflow_with_script_error(test_db, test_storage):
    """Test workflow handles script execution errors gracefully."""
    import asyncio
    from apps.worker.code_replication_workflow import code_replication_workflow
    
    workspace_id = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"}
    )
    test_db.commit()
    
    # Create test repo with failing script
    test_repo_dir = tempfile.mkdtemp(prefix="test_repo_")
    
    try:
        subprocess.run(["git", "init"], cwd=test_repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=test_repo_dir,
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=test_repo_dir,
            check=True,
            capture_output=True
        )
        
        # Create failing script
        script_path = Path(test_repo_dir) / "fail.py"
        script_path.write_text("""#!/usr/bin/env python3
print("Starting...")
raise ValueError("Intentional error for testing")
print("This won't print")
""")
        
        subprocess.run(["git", "add", "."], cwd=test_repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add failing script"],
            cwd=test_repo_dir,
            check=True,
            capture_output=True
        )
        
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=test_repo_dir,
            check=True,
            capture_output=True,
            text=True
        )
        commit_hash = commit_result.stdout.strip()
        
        # Run workflow
        result = asyncio.run(
            code_replication_workflow(
                workspace_id=workspace_id,
                repo_url=test_repo_dir,
                script_path="fail.py",
                commit_hash=commit_hash,
                db=test_db
            )
        )
        
        # Verify workflow completed (non-zero exit is not a workflow failure)
        assert result["exit_code"] != 0
        assert "log_artifact_id" in result
        
        # Verify error captured in log
        log_path = f"{workspace_id}/artifacts/{result['log_artifact_id']}/v{result['log_artifact_version_id']}/log.txt"
        response = test_storage.get_object("agora", log_path)
        log_content = response.read().decode('utf-8')
        response.close()
        response.release_conn()
        
        assert "Starting..." in log_content
        assert "ValueError" in log_content or "Traceback" in log_content
        
    finally:
        shutil.rmtree(test_repo_dir, ignore_errors=True)


def test_code_replication_workflow_with_parameters(test_db, test_storage):
    """Test workflow with sandbox parameters (env vars)."""
    import asyncio
    from apps.worker.code_replication_workflow import code_replication_workflow
    
    workspace_id = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"}
    )
    test_db.commit()
    
    # Create test repo
    test_repo_dir = tempfile.mkdtemp(prefix="test_repo_")
    
    try:
        subprocess.run(["git", "init"], cwd=test_repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=test_repo_dir,
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=test_repo_dir,
            check=True,
            capture_output=True
        )
        
        # Create script that uses env var
        script_path = Path(test_repo_dir) / "config_test.py"
        script_path.write_text("""#!/usr/bin/env python3
import os
config_value = os.environ.get('CONFIG_PARAM', 'default')
print(f"Config: {config_value}")
""")
        
        subprocess.run(["git", "add", "."], cwd=test_repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add config test script"],
            cwd=test_repo_dir,
            check=True,
            capture_output=True
        )
        
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=test_repo_dir,
            check=True,
            capture_output=True,
            text=True
        )
        commit_hash = commit_result.stdout.strip()
        
        # Run workflow with parameters
        result = asyncio.run(
            code_replication_workflow(
                workspace_id=workspace_id,
                repo_url=test_repo_dir,
                script_path="config_test.py",
                commit_hash=commit_hash,
                sandbox_parameters={"env": {"CONFIG_PARAM": "test_value"}},
                db=test_db
            )
        )
        
        # Verify log contains env var value
        log_path = f"{workspace_id}/artifacts/{result['log_artifact_id']}/v{result['log_artifact_version_id']}/log.txt"
        response = test_storage.get_object("agora", log_path)
        log_content = response.read().decode('utf-8')
        response.close()
        response.release_conn()
        
        assert "Config: test_value" in log_content
        
    finally:
        shutil.rmtree(test_repo_dir, ignore_errors=True)
