"""
Agent Task Routes (Component 14)

Per spec §4.6:
- POST /workspaces/{id}/tasks (SYSTEM-ONLY): Assigns task to agent
- GET /workspaces/{id}/tasks: List tasks with filters
- PATCH /tasks/{id}: Update task status (assignee-only)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.params import Query as QueryParam
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid

from database import DBWrapper, get_db_session
from auth_middleware import require_agent_token, require_system_token, AgentContext
from agent_tasks import (
    TaskPayload,
    TaskInput,
    TaskResultLink,
    TaskStatus,
    TASK_STATUS_VALUES,
)
from queries.agent_tasks import insert_agent_task, fetch_agent_task


router = APIRouter()

def _agent_id(current_agent: AgentContext) -> str:
    """
    Extract agent_id for callers that invoke route functions directly in tests.

    In real FastAPI execution, `current_agent` is an AgentContext.
    """
    if isinstance(current_agent, dict):
        return str(current_agent.get("agent_id"))
    return str(current_agent.agent_id)


# Request/Response Models

class CreateTaskRequest(BaseModel):
    """Request to create an agent task (SYSTEM-ONLY)."""
    type: str = Field(..., description="Task type (e.g., extract_claims, review_draft)")
    assignee_agent_id: Optional[str] = Field(None, description="UUID of assignee agent")
    payload: TaskPayload = Field(..., description="Structured task payload")


class TaskResponse(BaseModel):
    """Response for an agent task."""
    id: str
    workspace_id: str
    assignee_agent_id: Optional[str]
    type: str
    status: str
    payload: Dict[str, Any]
    created_at: datetime
    completed_at: Optional[datetime]


class UpdateTaskRequest(BaseModel):
    """Request to update task status."""
    status: str = Field(..., description="New status (open, in_progress, blocked, completed)")
    result_links: Optional[List[TaskResultLink]] = Field(None, description="Result pointers")
    notes: Optional[str] = Field(None, description="Optional notes or blockers")


# Endpoints

@router.post("/workspaces/{workspace_id}/tasks", response_model=TaskResponse, tags=["Agent Tasks"])
def create_task(
    workspace_id: uuid.UUID,
    request: CreateTaskRequest,
    system_token: dict = Depends(require_system_token),
    db: DBWrapper = Depends(get_db_session)
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

    # Validate input artifact versions belong to workspace
    for task_input in request.payload.inputs:
        version_row = db.execute(
            """
            SELECT av.id
            FROM artifact_versions av
            JOIN artifacts a ON av.artifact_id = a.id
            WHERE av.id = :version_id AND a.workspace_id = :workspace_id
            """,
            {"version_id": task_input.artifact_version_id, "workspace_id": workspace_id_str}
        ).fetchone()
        
        if not version_row:
            raise HTTPException(
                status_code=404,
                detail=f"Artifact version {task_input.artifact_version_id} not found in workspace {workspace_id_str}"
            )
    
    # Create task
    task_id = str(uuid.uuid4())
    
    payload_dict = request.payload.model_dump()

    insert_agent_task(
        db,
        task_id=task_id,
        workspace_id=workspace_id_str,
        assignee_agent_id=request.assignee_agent_id,
        task_type=request.type,
        status=TaskStatus.OPEN.value,
        payload=payload_dict,
    )
    
    db.commit()
    
    # Fetch and return
    row = fetch_agent_task(db, task_id=task_id)
    
    payload = row[5] or {}
    if isinstance(payload, str):
        import json
        payload = json.loads(payload)

    return TaskResponse(
        id=str(row[0]),
        workspace_id=str(row[1]),
        assignee_agent_id=str(row[2]) if row[2] else None,
        type=row[3],
        status=row[4],
        payload=payload,
        created_at=row[6],
        completed_at=row[7]
    )


@router.get("/workspaces/{workspace_id}/tasks", response_model=List[TaskResponse], tags=["Agent Tasks"])
def list_tasks(
    workspace_id: uuid.UUID,
    assignee_agent_id: Optional[str] = Query(None, description="Filter by assignee agent"),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_agent: AgentContext = Depends(require_agent_token),
    db: DBWrapper = Depends(get_db_session)
):
    """
    List agent tasks with optional filters.
    
    Per spec §4.6: Filters by assignee_agent_id, status.
    """
    workspace_id_str = str(workspace_id)

    # When called directly in tests (not through FastAPI), defaults may still be
    # the unresolved Query(...) sentinel objects. Treat them as "not provided".
    if isinstance(assignee_agent_id, QueryParam):
        assignee_agent_id = None
    if isinstance(status, QueryParam):
        status = None
    
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
        if status not in TASK_STATUS_VALUES:
            raise HTTPException(
                status_code=400,
                detail="Invalid status. Must be one of: open, in_progress, blocked, completed"
            )
        conditions.append("status = :status")
        params["status"] = status
    
    where_clause = " AND ".join(conditions)
    
    query = f"""
        SELECT id, workspace_id, assignee_agent_id, type, status, payload,
               created_at, completed_at
        FROM agent_tasks
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT 100
    """
    
    rows = db.execute(query, params).fetchall()
    
    results = []
    for row in rows:
        payload = row[5] or {}
        if isinstance(payload, str):
            import json
            payload = json.loads(payload)

        results.append(TaskResponse(
            id=str(row[0]),
            workspace_id=str(row[1]),
            assignee_agent_id=str(row[2]) if row[2] else None,
            type=row[3],
            status=row[4],
            payload=payload,
            created_at=row[6],
            completed_at=row[7]
        ))
    
    return results


@router.patch("/tasks/{task_id}", response_model=TaskResponse, tags=["Agent Tasks"])
def update_task(
    task_id: uuid.UUID,
    request: UpdateTaskRequest,
    current_agent: AgentContext = Depends(require_agent_token),
    db: DBWrapper = Depends(get_db_session)
):
    """
    Update task status (assignee-only).
    
    Per spec §4.6: PATCH /tasks/{id} - Input: status update, optional result link.
    Only the assignee agent can update the task.
    """
    task_id_str = str(task_id)
    agent_id = _agent_id(current_agent)
    
    # Fetch task
    task_row = db.execute(
        """
        SELECT id, assignee_agent_id, workspace_id, status, payload
        FROM agent_tasks
        WHERE id = :id
        """,
        {"id": task_id_str}
    ).fetchone()
    
    if not task_row:
        raise HTTPException(status_code=404, detail=f"Task {task_id_str} not found")
    
    # Verify assignee
    if str(task_row[1]) != str(agent_id):
        raise HTTPException(
            status_code=403,
            detail=f"Only the assignee agent can update this task"
        )
    
    # Validate status transition
    if request.status not in TASK_STATUS_VALUES:
        raise HTTPException(
            status_code=400,
            detail="Invalid status. Must be one of: open, in_progress, blocked, completed"
        )
    
    # Update task payload with results/notes
    payload = task_row[4] or {}
    if isinstance(payload, str):
        import json
        payload = json.loads(payload)
    if request.result_links is not None:
        payload["result_links"] = [link.model_dump() for link in request.result_links]
    if request.notes is not None:
        payload["notes"] = request.notes

    # Update task
    completed_at = None
    if request.status == "completed":
        completed_at = datetime.now(timezone.utc)

    db.execute(
        """
        UPDATE agent_tasks
        SET status = :status,
            payload = :payload,
            completed_at = :completed_at
        WHERE id = :id
        """,
        {
            "id": task_id_str,
            "status": request.status,
            "payload": payload,
            "completed_at": completed_at
        }
    )
    
    db.commit()
    
    # Fetch and return
    row = db.execute(
        """
        SELECT id, workspace_id, assignee_agent_id, type, status, payload, created_at, completed_at
        FROM agent_tasks
        WHERE id = :id
        """,
        {"id": task_id_str}
    ).fetchone()

    payload = row[5] or {}
    if isinstance(payload, str):
        import json
        payload = json.loads(payload)
    
    return TaskResponse(
        id=str(row[0]),
        workspace_id=str(row[1]),
        assignee_agent_id=str(row[2]) if row[2] else None,
        type=row[3],
        status=row[4],
        payload=payload,
        created_at=row[6],
        completed_at=row[7]
    )
