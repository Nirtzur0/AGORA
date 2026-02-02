"""
Agent Task Routes (Component 14)

Per spec §4.6:
- POST /workspaces/{id}/tasks (SYSTEM-ONLY): Assigns task to agent
- GET /workspaces/{id}/tasks: List tasks with filters
- PATCH /tasks/{id}: Update task status (assignee-only)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid

from database import DBWrapper, get_db
from auth_middleware import require_agent_token, require_system_token


router = APIRouter()


# Request/Response Models

class CreateTaskRequest(BaseModel):
    """Request to create an agent task (SYSTEM-ONLY)."""
    title: str = Field(..., description="Task title")
    description: str = Field(..., description="Task description")
    task_type: str = Field(..., description="Type of task (e.g., extract_claims, review_draft)")
    assignee_agent_id: Optional[str] = Field(None, description="UUID of assignee agent")
    assignee_role_id: Optional[str] = Field(None, description="UUID of assignee role")
    target_artifact_id: Optional[str] = Field(None, description="UUID of target artifact")
    workflow_run_id: Optional[str] = Field(None, description="UUID of parent workflow_run")


class TaskResponse(BaseModel):
    """Response for an agent task."""
    id: str
    workspace_id: str
    title: str
    description: str
    task_type: str
    assignee_agent_id: Optional[str]
    assignee_role_id: Optional[str]
    target_artifact_id: Optional[str]
    workflow_run_id: Optional[str]
    status: str
    result_artifact_id: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]


class UpdateTaskRequest(BaseModel):
    """Request to update task status."""
    status: str = Field(..., description="New status (in_progress, completed, failed)")
    result_artifact_id: Optional[str] = Field(None, description="UUID of result artifact")


# Endpoints

@router.post("/workspaces/{workspace_id}/tasks", response_model=TaskResponse, tags=["Agent Tasks"])
def create_task(
    workspace_id: uuid.UUID,
    request: CreateTaskRequest,
    system_token: dict = Depends(require_system_token),
    db: DBWrapper = Depends(get_db)
):
    """
    Create an agent task (SYSTEM-ONLY).
    
    Per spec §4.6: System-only; assigns a task to an agent.
    Writes to agent_tasks table.
    """
    workspace_id_str = str(workspace_id)
    
    # Verify workspace exists
    ws_row = db.execute(
        "SELECT id FROM workspaces WHERE id = :id",
        {"id": workspace_id_str}
    ).fetchone()
    
    if not ws_row:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id_str} not found")
    
    # Verify assignee agent if provided
    if request.assignee_agent_id:
        agent_row = db.execute(
            "SELECT id FROM agents WHERE id = :id",
            {"id": request.assignee_agent_id}
        ).fetchone()
        
        if not agent_row:
            raise HTTPException(status_code=404, detail=f"Agent {request.assignee_agent_id} not found")
    
    # Verify assignee role if provided
    if request.assignee_role_id:
        role_row = db.execute(
            "SELECT id FROM roles WHERE id = :id",
            {"id": request.assignee_role_id}
        ).fetchone()
        
        if not role_row:
            raise HTTPException(status_code=404, detail=f"Role {request.assignee_role_id} not found")
    
    # Verify target artifact if provided
    if request.target_artifact_id:
        artifact_row = db.execute(
            """
            SELECT id FROM artifacts
            WHERE id = :id AND workspace_id = :workspace_id
            """,
            {"id": request.target_artifact_id, "workspace_id": workspace_id_str}
        ).fetchone()
        
        if not artifact_row:
            raise HTTPException(
                status_code=404,
                detail=f"Artifact {request.target_artifact_id} not found in workspace {workspace_id_str}"
            )
    
    # Verify workflow_run if provided
    if request.workflow_run_id:
        workflow_row = db.execute(
            """
            SELECT id FROM workflow_runs
            WHERE id = :id AND workspace_id = :workspace_id
            """,
            {"id": request.workflow_run_id, "workspace_id": workspace_id_str}
        ).fetchone()
        
        if not workflow_row:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow run {request.workflow_run_id} not found in workspace {workspace_id_str}"
            )
    
    # Create task
    task_id = str(uuid.uuid4())
    
    db.execute(
        """
        INSERT INTO agent_tasks (
            id,
            workspace_id,
            title,
            description,
            task_type,
            assignee_agent_id,
            assignee_role_id,
            target_artifact_id,
            workflow_run_id,
            status
        ) VALUES (
            :id,
            :workspace_id,
            :title,
            :description,
            :task_type,
            :assignee_agent_id,
            :assignee_role_id,
            :target_artifact_id,
            :workflow_run_id,
            :status
        )
        """,
        {
            "id": task_id,
            "workspace_id": workspace_id_str,
            "title": request.title,
            "description": request.description,
            "task_type": request.task_type,
            "assignee_agent_id": request.assignee_agent_id,
            "assignee_role_id": request.assignee_role_id,
            "target_artifact_id": request.target_artifact_id,
            "workflow_run_id": request.workflow_run_id,
            "status": "pending"
        }
    )
    
    db.commit()
    
    # Fetch and return
    row = db.execute(
        """
        SELECT id, workspace_id, title, description, task_type,
               assignee_agent_id, assignee_role_id, target_artifact_id,
               workflow_run_id, status, result_artifact_id,
               created_at, completed_at
        FROM agent_tasks
        WHERE id = :id
        """,
        {"id": task_id}
    ).fetchone()
    
    return TaskResponse(
        id=row[0],
        workspace_id=row[1],
        title=row[2],
        description=row[3],
        task_type=row[4],
        assignee_agent_id=row[5],
        assignee_role_id=row[6],
        target_artifact_id=row[7],
        workflow_run_id=row[8],
        status=row[9],
        result_artifact_id=row[10],
        created_at=row[11],
        completed_at=row[12]
    )


@router.get("/workspaces/{workspace_id}/tasks", response_model=List[TaskResponse], tags=["Agent Tasks"])
def list_tasks(
    workspace_id: uuid.UUID,
    assignee_agent_id: Optional[str] = Query(None, description="Filter by assignee agent"),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_agent: dict = Depends(require_agent_token),
    db: DBWrapper = Depends(get_db)
):
    """
    List agent tasks with optional filters.
    
    Per spec §4.6: Filters by assignee_agent_id, status.
    """
    workspace_id_str = str(workspace_id)
    
    # Verify workspace exists
    ws_row = db.execute(
        "SELECT id FROM workspaces WHERE id = :id",
        {"id": workspace_id_str}
    ).fetchone()
    
    if not ws_row:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id_str} not found")
    
    # Build query
    conditions = ["workspace_id = :workspace_id"]
    params = {"workspace_id": workspace_id_str}
    
    if assignee_agent_id:
        conditions.append("assignee_agent_id = :assignee_agent_id")
        params["assignee_agent_id"] = assignee_agent_id
    
    if status:
        conditions.append("status = :status")
        params["status"] = status
    
    where_clause = " AND ".join(conditions)
    
    query = f"""
        SELECT id, workspace_id, title, description, task_type,
               assignee_agent_id, assignee_role_id, target_artifact_id,
               workflow_run_id, status, result_artifact_id,
               created_at, completed_at
        FROM agent_tasks
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT 100
    """
    
    rows = db.execute(query, params).fetchall()
    
    results = []
    for row in rows:
        results.append(TaskResponse(
            id=row[0],
            workspace_id=row[1],
            title=row[2],
            description=row[3],
            task_type=row[4],
            assignee_agent_id=row[5],
            assignee_role_id=row[6],
            target_artifact_id=row[7],
            workflow_run_id=row[8],
            status=row[9],
            result_artifact_id=row[10],
            created_at=row[11],
            completed_at=row[12]
        ))
    
    return results


@router.patch("/tasks/{task_id}", response_model=TaskResponse, tags=["Agent Tasks"])
def update_task(
    task_id: uuid.UUID,
    request: UpdateTaskRequest,
    current_agent: dict = Depends(require_agent_token),
    db: DBWrapper = Depends(get_db)
):
    """
    Update task status (assignee-only).
    
    Per spec §4.6: PATCH /tasks/{id} - Input: status update, optional result link.
    Only the assignee agent can update the task.
    """
    task_id_str = str(task_id)
    agent_id = current_agent["agent_id"]
    
    # Fetch task
    task_row = db.execute(
        """
        SELECT id, assignee_agent_id, workspace_id, status
        FROM agent_tasks
        WHERE id = :id
        """,
        {"id": task_id_str}
    ).fetchone()
    
    if not task_row:
        raise HTTPException(status_code=404, detail=f"Task {task_id_str} not found")
    
    # Verify assignee
    if task_row[1] != agent_id:
        raise HTTPException(
            status_code=403,
            detail=f"Only the assignee agent can update this task"
        )
    
    # Validate status transition
    valid_statuses = ["pending", "in_progress", "completed", "failed"]
    if request.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )
    
    # Verify result artifact if provided
    if request.result_artifact_id:
        artifact_row = db.execute(
            """
            SELECT id FROM artifacts
            WHERE id = :id AND workspace_id = :workspace_id
            """,
            {"id": request.result_artifact_id, "workspace_id": task_row[2]}
        ).fetchone()
        
        if not artifact_row:
            raise HTTPException(
                status_code=404,
                detail=f"Result artifact {request.result_artifact_id} not found in workspace"
            )
    
    # Update task
    completed_at = None
    if request.status in ["completed", "failed"]:
        completed_at = datetime.utcnow()
    
    if completed_at:
        db.execute(
            """
            UPDATE agent_tasks
            SET status = :status,
                result_artifact_id = :result_artifact_id,
                completed_at = :completed_at
            WHERE id = :id
            """,
            {
                "id": task_id_str,
                "status": request.status,
                "result_artifact_id": request.result_artifact_id,
                "completed_at": completed_at
            }
        )
    else:
        db.execute(
            """
            UPDATE agent_tasks
            SET status = :status,
                result_artifact_id = :result_artifact_id
            WHERE id = :id
            """,
            {
                "id": task_id_str,
                "status": request.status,
                "result_artifact_id": request.result_artifact_id
            }
        )
    
    db.commit()
    
    # Fetch and return
    row = db.execute(
        """
        SELECT id, workspace_id, title, description, task_type,
               assignee_agent_id, assignee_role_id, target_artifact_id,
               workflow_run_id, status, result_artifact_id,
               created_at, completed_at
        FROM agent_tasks
        WHERE id = :id
        """,
        {"id": task_id_str}
    ).fetchone()
    
    return TaskResponse(
        id=row[0],
        workspace_id=row[1],
        title=row[2],
        description=row[3],
        task_type=row[4],
        assignee_agent_id=row[5],
        assignee_role_id=row[6],
        target_artifact_id=row[7],
        workflow_run_id=row[8],
        status=row[9],
        result_artifact_id=row[10],
        created_at=row[11],
        completed_at=row[12]
    )
