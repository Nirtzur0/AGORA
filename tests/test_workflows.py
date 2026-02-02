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
    class DBWrapper:
        def __init__(self, session):
            self._session = session
        
        def execute(self, query, params=None):
            if params:
                return self._session.execute(text(query), params)
            return self._session.execute(text(query))
        
        def commit(self):
            return self._session.commit()
    
    db_wrapper = DBWrapper(db_session)
    
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
            SELECT id, workspace_id, workflow_type, workflow_id, status, input
            FROM workflow_runs
            WHERE id = :id
        """),
        {"id": workflow_run_id}
    ).fetchone()
    
    assert row is not None
    assert row[0] == workflow_run_id
    assert row[1] == ws.id
    assert row[2] == "literature_grounding"
    assert row[3] == workflow_id
    assert row[4] == "running"
    
    input_data = json.loads(row[5])
    assert "artifact_id" in input_data
    
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
            SELECT status, output, completed_at
            FROM workflow_runs
            WHERE id = :id
        """),
        {"id": workflow_run_id}
    ).fetchone()
    
    assert updated_row[0] == "completed"
    
    output_data = json.loads(updated_row[1])
    assert output_data["result"] == "success"
    assert output_data["claims_created"] == 5
    assert updated_row[2] is not None  # completed_at


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
    class DBWrapper:
        def __init__(self, session):
            self._session = session
        
        def execute(self, query, params=None):
            if params:
                return self._session.execute(text(query), params)
            return self._session.execute(text(query))
        
        def commit(self):
            return self._session.commit()
    
    db_wrapper = DBWrapper(db_session)
    
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
            SELECT id, workflow_run_id, activity_type, activity_id, status, input
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
    
    input_data = json.loads(row[5])
    assert input_data["artifact_id"] == activity_input["artifact_id"]
    
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
            SELECT status, output, completed_at
            FROM activity_runs
            WHERE id = :id
        """),
        {"id": activity_run_id}
    ).fetchone()
    
    assert updated_row[0] == "completed"
    
    output_data = json.loads(updated_row[1])
    assert output_data["pages_parsed"] == 10
    assert "version_id" in output_data
    assert updated_row[2] is not None  # completed_at


def test_create_agent_task_system_only(db_session, workspace_with_agent):
    """Test POST /workspaces/{id}/tasks (SYSTEM-ONLY)."""
    from task_routes import create_task, CreateTaskRequest
    from sqlalchemy import text
    
    ws, agent = workspace_with_agent
    
    # Create DB wrapper
    class DBWrapper:
        def __init__(self, session):
            self._session = session
        
        def execute(self, query, params=None):
            if params:
                return self._session.execute(text(query), params)
            return self._session.execute(text(query))
        
        def commit(self):
            return self._session.commit()
    
    db_wrapper = DBWrapper(db_session)
    
    # Mock system token
    mock_system = {"token_type": "system"}
    
    # Create task
    request = CreateTaskRequest(
        title="Extract claims from PDF",
        description="Parse the uploaded PDF and create claim records",
        task_type="extract_claims",
        assignee_agent_id=agent.id
    )
    
    response = create_task(
        workspace_id=uuid.UUID(ws.id),
        request=request,
        system_token=mock_system,
        db=db_wrapper
    )
    
    # Verify response
    assert response.workspace_id == ws.id
    assert response.title == "Extract claims from PDF"
    assert response.task_type == "extract_claims"
    assert response.assignee_agent_id == agent.id
    assert response.status == "pending"
    
    # Verify in database
    task = db_session.execute(
        text("""
            SELECT id, workspace_id, title, assignee_agent_id, status
            FROM agent_tasks
            WHERE id = :id
        """),
        {"id": response.id}
    ).fetchone()
    
    assert task is not None
    assert task[1] == ws.id
    assert task[4] == "pending"


def test_list_agent_tasks_with_filters(db_session, workspace_with_agent):
    """Test GET /workspaces/{id}/tasks with filters."""
    from task_routes import create_task, list_tasks, CreateTaskRequest
    from sqlalchemy import text
    
    ws, agent = workspace_with_agent
    
    # Create DB wrapper
    class DBWrapper:
        def __init__(self, session):
            self._session = session
        
        def execute(self, query, params=None):
            if params:
                return self._session.execute(text(query), params)
            return self._session.execute(text(query))
        
        def commit(self):
            return self._session.commit()
    
    db_wrapper = DBWrapper(db_session)
    
    # Mock tokens
    mock_system = {"token_type": "system"}
    mock_agent = {"agent_id": agent.id}
    
    # Create multiple tasks
    task1 = create_task(
        workspace_id=uuid.UUID(ws.id),
        request=CreateTaskRequest(
            title="Task 1",
            description="First task",
            task_type="extract_claims",
            assignee_agent_id=agent.id
        ),
        system_token=mock_system,
        db=db_wrapper
    )
    
    task2 = create_task(
        workspace_id=uuid.UUID(ws.id),
        request=CreateTaskRequest(
            title="Task 2",
            description="Second task",
            task_type="review_draft",
            assignee_agent_id=agent.id
        ),
        system_token=mock_system,
        db=db_wrapper
    )
    
    # List all tasks
    tasks = list_tasks(
        workspace_id=uuid.UUID(ws.id),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    assert len(tasks) >= 2
    task_ids = {t.id for t in tasks}
    assert task1.id in task_ids
    assert task2.id in task_ids
    
    # Filter by assignee
    filtered = list_tasks(
        workspace_id=uuid.UUID(ws.id),
        assignee_agent_id=agent.id,
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    assert len(filtered) >= 2
    assert all(t.assignee_agent_id == agent.id for t in filtered)
    
    # Filter by status
    pending_tasks = list_tasks(
        workspace_id=uuid.UUID(ws.id),
        status="pending",
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    assert all(t.status == "pending" for t in pending_tasks)


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
    class DBWrapper:
        def __init__(self, session):
            self._session = session
        
        def execute(self, query, params=None):
            if params:
                return self._session.execute(text(query), params)
            return self._session.execute(text(query))
        
        def commit(self):
            return self._session.commit()
    
    db_wrapper = DBWrapper(db_session)
    
    # Mock tokens
    mock_system = {"token_type": "system"}
    mock_agent = {"agent_id": agent.id}
    mock_other_agent = {"agent_id": other_agent.id}
    
    # Create task assigned to agent
    task = create_task(
        workspace_id=uuid.UUID(ws.id),
        request=CreateTaskRequest(
            title="Test Task",
            description="Task for testing update",
            task_type="extract_claims",
            assignee_agent_id=agent.id
        ),
        system_token=mock_system,
        db=db_wrapper
    )
    
    # Update task as assignee (should succeed)
    update_request = UpdateTaskRequest(
        status="in_progress"
    )
    
    updated = update_task(
        task_id=uuid.UUID(task.id),
        request=update_request,
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    assert updated.status == "in_progress"
    
    # Try to update as non-assignee (should fail)
    with pytest.raises(HTTPException) as exc_info:
        update_task(
            task_id=uuid.UUID(task.id),
            request=UpdateTaskRequest(status="completed"),
            current_agent=mock_other_agent,
            db=db_wrapper
        )
    
    assert exc_info.value.status_code == 403
    assert "assignee" in exc_info.value.detail.lower()


def test_complete_agent_task_with_result(db_session, workspace_with_agent):
    """Test completing task with result_artifact_id."""
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
    class DBWrapper:
        def __init__(self, session):
            self._session = session
        
        def execute(self, query, params=None):
            if params:
                return self._session.execute(text(query), params)
            return self._session.execute(text(query))
        
        def commit(self):
            return self._session.commit()
    
    db_wrapper = DBWrapper(db_session)
    
    # Mock tokens
    mock_system = {"token_type": "system"}
    mock_agent = {"agent_id": agent.id}
    
    # Create task
    task = create_task(
        workspace_id=uuid.UUID(ws.id),
        request=CreateTaskRequest(
            title="Create Draft",
            description="Write a draft document",
            task_type="write_draft",
            assignee_agent_id=agent.id
        ),
        system_token=mock_system,
        db=db_wrapper
    )
    
    # Complete task with result
    updated = update_task(
        task_id=uuid.UUID(task.id),
        request=UpdateTaskRequest(
            status="completed",
            result_artifact_id=result_artifact.id
        ),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    assert updated.status == "completed"
    assert updated.result_artifact_id == result_artifact.id
    assert updated.completed_at is not None
