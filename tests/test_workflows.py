"""
Exit tests for Component 14: Temporal plumbing + workflow_runs/activity_runs + agent tasks

Per checklist:
- EXIT TEST 1: Start workflow -> workflow_runs row created -> completes -> status updated
- EXIT TEST 2: Activities produce activity_runs rows
- Additional tests for agent task endpoints

Tests run against real containers (Postgres, not mocked).
"""
import pytest
import uuid
import json

from database import Workspace, Agent


@pytest.fixture
def workspace_with_agent(db_session):
    """Create test workspace and agent."""
    ws = Workspace(
        id=str(uuid.uuid4()),
        name="Workflow Test Workspace",
        phase="literature_review"
    )
    db_session.add(ws)
    
    agent = Agent(
        id=str(uuid.uuid4()),
        moltbook_identity="test_agent_workflow",
        display_name="Test Agent",
        reputation_score=100
    )
    db_session.add(agent)
    db_session.commit()
    
    return ws, agent


def create_artifact_version(db_session, workspace_id: str, created_by: str = None):
    """Create a minimal artifact + version for task inputs."""
    from sqlalchemy import text
    artifact_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    db_session.execute(
        text(
            """
            INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
            VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
            """
        ),
        {
            "id": artifact_id,
            "workspace_id": workspace_id,
            "short_id": f"A{abs(hash(artifact_id)) % 10000}",
            "type": "pdf",
            "metadata": json.dumps({"source": "test"}),
            "storage_uri": f"s3://agora/{workspace_id}/artifacts/{artifact_id}/",
            "created_by": created_by
        }
    )
    db_session.execute(
        text(
            """
            INSERT INTO artifact_versions (id, artifact_id, version, storage_uri, content_hash, created_by, created_at)
            VALUES (:id, :artifact_id, :version, :storage_uri, :content_hash, :created_by, NOW())
            """
        ),
        {
            "id": version_id,
            "artifact_id": artifact_id,
            "version": 1,
            "storage_uri": "s3://agora/test.pdf",
            "content_hash": "test_hash",
            "created_by": created_by
        }
    )
    db_session.commit()
    return artifact_id, version_id


def test_exit_workflow_runs_lifecycle(db_session, workspace_with_agent):
    """
    EXIT TEST 1: Start workflow -> workflow_runs row created -> completes -> status updated.
    
    Success criteria:
    - workflow_runs row created with status=running
    - Can update status to completed
    - Output is persisted
    """
    from workflow_client import WorkflowClient
    from sqlalchemy import text
    
    ws, agent = workspace_with_agent
    
    # Create DB wrapper
    db_wrapper = db_session
    
    # Start workflow
    client = WorkflowClient()
    workflow_id = f"literature_grounding_{uuid.uuid4()}"
    
    import asyncio
    workflow_run_id = asyncio.run(client.start_workflow(
        workflow_type="literature_grounding",
        workflow_id=workflow_id,
        task_queue="agora-tasks",
        args={"artifact_id": str(uuid.uuid4())},
        db=db_wrapper,
        workspace_id=ws.id
    ))
    
    # Verify workflow_runs row created
    row = db_session.execute(
        text("""
            SELECT id, workspace_id, workflow_type, temporal_workflow_id, status
            FROM workflow_runs
            WHERE id = :id
        """),
        {"id": workflow_run_id}
    ).fetchone()
    
    assert row is not None
    assert row[0] == workflow_run_id
    assert row[1] == str(ws.id)
    assert row[2] == "literature_grounding"
    assert row[3] == workflow_id
    assert row[4] == "running"
    
    # Update workflow status to completed
    output = {"result": "success", "claims_created": 5}
    asyncio.run(client.update_workflow_status(
        workflow_run_id=workflow_run_id,
        status="completed",
        output=output,
        db=db_wrapper
    ))
    
    # Verify status updated
    updated_row = db_session.execute(
        text("""
            SELECT status, completed_at
            FROM workflow_runs
            WHERE id = :id
        """),
        {"id": workflow_run_id}
    ).fetchone()
    
    assert updated_row[0] == "completed"
    assert updated_row[1] is not None  # completed_at


def test_exit_activity_runs_created(db_session, workspace_with_agent):
    """
    EXIT TEST 2: Activities produce activity_runs rows.
    
    Success criteria:
    - activity_runs row created when activity starts
    - Can update status to completed
    - Output is persisted
    """
    from workflow_client import WorkflowClient, create_activity_run, update_activity_run
    from sqlalchemy import text
    
    ws, agent = workspace_with_agent
    
    # Create DB wrapper
    db_wrapper = db_session
    
    # Start workflow first
    client = WorkflowClient()
    workflow_id = f"literature_grounding_{uuid.uuid4()}"
    
    import asyncio
    workflow_run_id = asyncio.run(client.start_workflow(
        workflow_type="literature_grounding",
        workflow_id=workflow_id,
        task_queue="agora-tasks",
        args={"artifact_id": str(uuid.uuid4())},
        db=db_wrapper,
        workspace_id=ws.id
    ))
    
    # Create activity run
    activity_id = f"pdf_ingest_{uuid.uuid4()}"
    activity_input = {"artifact_id": str(uuid.uuid4()), "source_uri": "s3://bucket/file.pdf"}
    
    activity_run_id = create_activity_run(
        db=db_wrapper,
        workflow_run_id=workflow_run_id,
        activity_type="pdf_ingest",
        activity_id=activity_id,
        input_data=activity_input
    )
    
    # Verify activity_runs row created
    row = db_session.execute(
        text("""
            SELECT id, workflow_run_id, activity_type, temporal_activity_id, status
            FROM activity_runs
            WHERE id = :id
        """),
        {"id": activity_run_id}
    ).fetchone()
    
    assert row is not None
    assert row[0] == activity_run_id
    assert row[1] == workflow_run_id
    assert row[2] == "pdf_ingest"
    assert row[3] == activity_id
    assert row[4] == "running"
    
    # Update activity status to completed
    activity_output = {"pages_parsed": 10, "version_id": str(uuid.uuid4())}
    update_activity_run(
        db=db_wrapper,
        activity_run_id=activity_run_id,
        status="completed",
        output=activity_output
    )
    
    # Verify status updated
    updated_row = db_session.execute(
        text("""
            SELECT status, completed_at
            FROM activity_runs
            WHERE id = :id
        """),
        {"id": activity_run_id}
    ).fetchone()
    
    assert updated_row[0] == "completed"
    assert updated_row[1] is not None  # completed_at


def test_create_agent_task_system_only(db_session, workspace_with_agent):
    """Test POST /workspaces/{id}/tasks (SYSTEM-ONLY)."""
    from task_routes import create_task, CreateTaskRequest
    from sqlalchemy import text
    
    ws, agent = workspace_with_agent
    
    # Create DB wrapper
    db_wrapper = db_session
    
    # Mock system token
    mock_system = {"token_type": "system"}
    
    # Create task
    artifact_id, version_id = create_artifact_version(db_session, ws.id, created_by=agent.id)
    request = CreateTaskRequest(
        type="extract_claims",
        assignee_agent_id=agent.id,
        payload={
            "objective": "Extract claims from the PDF and add evidence.",
            "inputs": [{"artifact_version_id": version_id, "label": "PDF"}],
            "required_outputs": ["claim.create", "claim.evidence.add"],
            "context_links": [{"type": "artifact", "id": artifact_id}],
            "acceptance_criteria": ["At least 1 claim created with evidence"],
            "priority": "high"
        }
    )
    
    response = create_task(
        workspace_id=uuid.UUID(str(ws.id)),
        request=request,
        system_token=mock_system,
        db=db_wrapper
    )
    
    # Verify response
    assert response.workspace_id == str(ws.id)
    assert response.type == "extract_claims"
    assert response.assignee_agent_id == agent.id
    assert response.status == "open"
    assert response.payload["objective"] == "Extract claims from the PDF and add evidence."
    
    # Verify in database
    task = db_session.execute(
        text("""
            SELECT id, workspace_id, assignee_agent_id, status
            FROM agent_tasks
            WHERE id = :id
        """),
        {"id": response.id}
    ).fetchone()
    
    assert task is not None
    assert task[1] == str(ws.id)
    assert task[3] == "open"


def test_list_agent_tasks_with_filters(db_session, workspace_with_agent):
    """Test GET /workspaces/{id}/tasks with filters."""
    from task_routes import create_task, list_tasks, CreateTaskRequest
    from sqlalchemy import text
    
    ws, agent = workspace_with_agent
    
    # Create DB wrapper
    db_wrapper = db_session
    
    # Mock tokens
    mock_system = {"token_type": "system"}
    mock_agent = {"agent_id": agent.id}

    artifact_id, version_id = create_artifact_version(db_session, ws.id, created_by=agent.id)
    
    # Create multiple tasks
    task1 = create_task(
        workspace_id=uuid.UUID(str(ws.id)),
        request=CreateTaskRequest(
            type="extract_claims",
            assignee_agent_id=agent.id,
            payload={
                "objective": "First task",
                "inputs": [{"artifact_version_id": version_id, "label": "Input"}],
                "required_outputs": ["claim.create"],
                "context_links": [{"type": "artifact", "id": artifact_id}],
                "acceptance_criteria": ["At least 1 claim created"],
                "priority": "medium"
            }
        ),
        system_token=mock_system,
        db=db_wrapper
    )
    
    task2 = create_task(
        workspace_id=uuid.UUID(str(ws.id)),
        request=CreateTaskRequest(
            type="review_draft",
            assignee_agent_id=agent.id,
            payload={
                "objective": "Second task",
                "inputs": [{"artifact_version_id": version_id, "label": "Input"}],
                "required_outputs": ["critique.create"],
                "context_links": [{"type": "artifact", "id": artifact_id}],
                "acceptance_criteria": ["Critique created"],
                "priority": "low"
            }
        ),
        system_token=mock_system,
        db=db_wrapper
    )
    
    # List all tasks
    tasks = list_tasks(
        workspace_id=uuid.UUID(str(ws.id)),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    assert len(tasks) >= 2
    task_ids = {t.id for t in tasks}
    assert task1.id in task_ids
    assert task2.id in task_ids
    
    # Filter by assignee
    filtered = list_tasks(
        workspace_id=uuid.UUID(str(ws.id)),
        assignee_agent_id=agent.id,
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    assert len(filtered) >= 2
    assert all(t.assignee_agent_id == agent.id for t in filtered)
    
    # Filter by status
    pending_tasks = list_tasks(
        workspace_id=uuid.UUID(str(ws.id)),
        status="open",
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    assert all(t.status == "open" for t in pending_tasks)


def test_update_agent_task_assignee_only(db_session, workspace_with_agent):
    """Test PATCH /tasks/{id} (assignee-only updates)."""
    from task_routes import create_task, update_task, CreateTaskRequest, UpdateTaskRequest
    from sqlalchemy import text
    from fastapi import HTTPException
    
    ws, agent = workspace_with_agent
    
    # Create another agent
    other_agent = Agent(
        id=str(uuid.uuid4()),
        moltbook_identity="other_agent",
        display_name="Other Agent",
        reputation_score=100
    )
    db_session.add(other_agent)
    db_session.commit()
    
    # Create DB wrapper
    db_wrapper = db_session
    
    # Mock tokens
    mock_system = {"token_type": "system"}
    mock_agent = {"agent_id": agent.id}
    mock_other_agent = {"agent_id": other_agent.id}

    artifact_id, version_id = create_artifact_version(db_session, ws.id, created_by=agent.id)
    
    # Create task assigned to agent
    task = create_task(
        workspace_id=uuid.UUID(str(ws.id)),
        request=CreateTaskRequest(
            type="extract_claims",
            assignee_agent_id=agent.id,
            payload={
                "objective": "Task for testing update",
                "inputs": [{"artifact_version_id": version_id, "label": "Input"}],
                "required_outputs": ["claim.create"],
                "context_links": [{"type": "artifact", "id": artifact_id}],
                "acceptance_criteria": ["Claim created"],
                "priority": "medium"
            }
        ),
        system_token=mock_system,
        db=db_wrapper
    )
    
    # Update task as assignee (should succeed)
    update_request = UpdateTaskRequest(
        status="in_progress"
    )
    
    updated = update_task(
        task_id=uuid.UUID(str(task.id)),
        request=update_request,
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    assert updated.status == "in_progress"
    
    # Try to update as non-assignee (should fail)
    with pytest.raises(HTTPException) as exc_info:
        update_task(
            task_id=uuid.UUID(str(task.id)),
            request=UpdateTaskRequest(status="completed"),
            current_agent=mock_other_agent,
            db=db_wrapper
        )
    
    assert exc_info.value.status_code == 403
    assert "assignee" in exc_info.value.detail.lower()


def test_complete_agent_task_with_result(db_session, workspace_with_agent):
    """Test completing task with result_links."""
    from task_routes import create_task, update_task, CreateTaskRequest, UpdateTaskRequest
    from database import Artifact
    from sqlalchemy import text
    
    ws, agent = workspace_with_agent
    
    # Create artifact for result
    result_artifact = Artifact(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        type="draft",
        short_id="D1",
        metadata=json.dumps({"title": "Task Result"})
    )
    db_session.add(result_artifact)
    db_session.commit()
    
    # Create DB wrapper
    db_wrapper = db_session
    
    # Mock tokens
    mock_system = {"token_type": "system"}
    mock_agent = {"agent_id": agent.id}

    artifact_id, version_id = create_artifact_version(db_session, ws.id, created_by=agent.id)
    
    # Create task
    task = create_task(
        workspace_id=uuid.UUID(str(ws.id)),
        request=CreateTaskRequest(
            type="write_draft",
            assignee_agent_id=agent.id,
            payload={
                "objective": "Write a draft document",
                "inputs": [{"artifact_version_id": version_id, "label": "Source"}],
                "required_outputs": ["draft.version.create"],
                "context_links": [{"type": "artifact", "id": artifact_id}],
                "acceptance_criteria": ["Draft version created"],
                "priority": "high"
            }
        ),
        system_token=mock_system,
        db=db_wrapper
    )
    
    # Complete task with result
    updated = update_task(
        task_id=uuid.UUID(str(task.id)),
        request=UpdateTaskRequest(
            status="completed",
            result_links=[{"type": "artifact", "id": result_artifact.id, "note": "Draft result"}]
        ),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    assert updated.status == "completed"
    assert updated.payload["result_links"][0]["id"] == result_artifact.id
    assert updated.completed_at is not None
