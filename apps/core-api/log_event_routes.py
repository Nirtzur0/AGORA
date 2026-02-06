"""
Log and Event routes for AGORA Core API.

Implements append-only audit trail per spec §4.5, §4.8, §5.7:
- POST /workspaces/{id}/logs: Agent writes (append-only)
- GET /workspaces/{id}/logs: Read logs with filters
- POST /workspaces/{id}/events: SYSTEM-only writes (append-only)
- GET /workspaces/{id}/events: Read events with filters

Authority model:
- Logs: Agent-written (action audit trail)
- Events: System-written only (state mutations)
- Both are append-only (no updates/deletes)
- Every mutation is recorded with actor_type (agent|system)
"""
from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth_middleware import get_current_agent, require_system_token, AgentContext
from database import get_db_session
from rbac import require_permission

router = APIRouter()


class CreateLogRequest(BaseModel):
    """Request to create a log entry (agent action)."""
    action: str = Field(..., description="Action being logged (e.g., 'claim.created', 'artifact.uploaded')")
    payload: Optional[dict] = Field(default=None, description="Optional payload JSON")


class LogResponse(BaseModel):
    """Log entry response."""
    id: str
    workspace_id: str
    agent_id: str
    action: str
    payload: Optional[dict]
    created_at: str


class CreateEventRequest(BaseModel):
    """Request to create an event (system state mutation)."""
    actor_type: str = Field(..., description="Actor type: 'agent' or 'system'")
    actor_id: str = Field(..., description="UUID of actor (agent or system component)")
    event_type: str = Field(..., description="Event type (e.g., 'workspace.phase_changed', 'claim.created')")
    payload: Optional[dict] = Field(default=None, description="Event payload JSON")


class EventResponse(BaseModel):
    """Event entry response."""
    id: str
    workspace_id: str
    actor_type: str
    actor_id: str
    event_type: str
    payload: Optional[dict]
    created_at: str


def _coerce_event_actor_id(actor_type: str, actor_id: str) -> str:
    """
    events.actor_id is stored as UUID in Postgres.

    Agents have natural UUIDs. System components may provide a stable string
    identifier (e.g., "worker-1"); map it deterministically to a UUID.
    """
    import uuid as _uuid

    if actor_type == "agent":
        try:
            return str(_uuid.UUID(str(actor_id)))
        except Exception:
            raise HTTPException(status_code=422, detail="actor_id must be a UUID when actor_type='agent'")

    # actor_type == "system"
    try:
        return str(_uuid.UUID(str(actor_id)))
    except Exception:
        return str(_uuid.uuid5(_uuid.NAMESPACE_URL, f"agora-system:{actor_id}"))


@router.post("/workspaces/{workspace_id}/logs", status_code=201)
async def create_log(
    workspace_id: UUID,
    req: CreateLogRequest,
    agent: AgentContext = Depends(get_current_agent),
    db=Depends(get_db_session)
):
    """
    Create log entry (agent action audit trail).
    
    Logs are append-only records of agent actions.
    No updates or deletes are permitted.
    
    Authority: Requires log.write permission.
    """
    # Check permission
    require_permission(db, agent.agent_id, str(workspace_id), "log.write")
    
    # Verify workspace exists
    result = db.execute(
        "SELECT id FROM workspaces WHERE id = :workspace_id",
        {"workspace_id": str(workspace_id)}
    )
    if result.fetchone() is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Create log entry
    log_id = uuid4()
    created_at = datetime.utcnow()
    
    db.execute(
        """
        INSERT INTO logs (id, workspace_id, agent_id, action, payload, created_at)
        VALUES (:id, :workspace_id, :agent_id, :action, :payload, :created_at)
        """,
        {
            "id": str(log_id),
            "workspace_id": str(workspace_id),
            "agent_id": agent.agent_id,
            "action": req.action,
            "payload": req.payload,
            "created_at": created_at
        }
    )
    
    db.commit()
    
    return {
        "id": str(log_id),
        "workspace_id": str(workspace_id),
        "agent_id": agent.agent_id,
        "action": req.action,
        "payload": req.payload,
        "created_at": created_at.isoformat()
    }


@router.get("/workspaces/{workspace_id}/logs")
async def list_logs(
    workspace_id: UUID,
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    action: Optional[str] = Query(None, description="Filter by action"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of logs to return"),
    offset: int = Query(0, ge=0, description="Number of logs to skip"),
    agent: AgentContext = Depends(get_current_agent),
    db=Depends(get_db_session)
):
    """
    List logs in workspace with optional filters.
    
    Filters:
    - agent_id: Filter by specific agent
    - action: Filter by action type
    - limit: Maximum results (default 100, max 1000)
    - offset: Pagination offset
    
    Results ordered by created_at DESC (newest first).
    
    Authority: Requires log.read permission.
    """
    # Check permission
    require_permission(db, agent.agent_id, str(workspace_id), "log.read")
    
    # Build query
    query = """
        SELECT id, workspace_id, agent_id, action, payload, created_at
        FROM logs
        WHERE workspace_id = :workspace_id
    """
    params = {"workspace_id": str(workspace_id)}
    
    if agent_id:
        query += " AND agent_id = :agent_id"
        params["agent_id"] = agent_id
    
    if action:
        query += " AND action = :action"
        params["action"] = action
    
    query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset
    
    result = db.execute(query, params)
    rows = result.fetchall()
    
    logs = []
    for row in rows:
        logs.append({
            "id": row[0],
            "workspace_id": row[1],
            "agent_id": row[2],
            "action": row[3],
            "payload": row[4],
            "created_at": row[5].isoformat()
        })
    
    return {"logs": logs, "count": len(logs)}


@router.post("/workspaces/{workspace_id}/events", status_code=201)
async def create_event(
    workspace_id: UUID,
    req: CreateEventRequest,
    system_token=Depends(require_system_token),
    db=Depends(get_db_session)
):
    """
    Create event entry (system state mutation record).
    
    **SYSTEM-ONLY**: This endpoint requires a system JWT token.
    Events record all state mutations (workspace phases, claim creation, etc.).
    Events are append-only; no updates or deletes are permitted.
    
    Authority: Requires system JWT token (not agent token).
    """
    # Validate actor_type
    if req.actor_type not in ["agent", "system"]:
        raise HTTPException(
            status_code=400,
            detail="actor_type must be 'agent' or 'system'"
        )
    
    # Verify workspace exists
    result = db.execute(
        "SELECT id FROM workspaces WHERE id = :workspace_id",
        {"workspace_id": str(workspace_id)}
    )
    if result.fetchone() is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Create event entry
    event_id = uuid4()
    created_at = datetime.utcnow()
    actor_id_uuid = _coerce_event_actor_id(req.actor_type, req.actor_id)
    
    db.execute(
        """
        INSERT INTO events (id, workspace_id, actor_type, actor_id, event_type, payload, created_at)
        VALUES (:id, :workspace_id, :actor_type, :actor_id, :event_type, :payload, :created_at)
        """,
        {
            "id": str(event_id),
            "workspace_id": str(workspace_id),
            "actor_type": req.actor_type,
            "actor_id": actor_id_uuid,
            "event_type": req.event_type,
            "payload": req.payload,
            "created_at": created_at
        }
    )
    
    db.commit()
    
    return {
        "id": str(event_id),
        "workspace_id": str(workspace_id),
        "actor_type": req.actor_type,
        "actor_id": actor_id_uuid,
        "event_type": req.event_type,
        "payload": req.payload,
        "created_at": created_at.isoformat()
    }


@router.get("/workspaces/{workspace_id}/events")
async def list_events(
    workspace_id: UUID,
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    actor_type: Optional[str] = Query(None, description="Filter by actor type (agent|system)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    agent: AgentContext = Depends(get_current_agent),
    db=Depends(get_db_session)
):
    """
    List events in workspace with optional filters.
    
    Filters:
    - event_type: Filter by event type (e.g., 'claim.created')
    - actor_type: Filter by actor type ('agent' or 'system')
    - limit: Maximum results (default 100, max 1000)
    - offset: Pagination offset
    
    Results ordered by created_at DESC (newest first).
    
    Authority: Requires log.read permission.
    """
    # Check permission
    require_permission(db, agent.agent_id, str(workspace_id), "log.read")
    
    # Build query
    query = """
        SELECT id, workspace_id, actor_type, actor_id, event_type, payload, created_at
        FROM events
        WHERE workspace_id = :workspace_id
    """
    params = {"workspace_id": str(workspace_id)}
    
    if event_type:
        query += " AND event_type = :event_type"
        params["event_type"] = event_type
    
    if actor_type:
        if actor_type not in ["agent", "system"]:
            raise HTTPException(
                status_code=400,
                detail="actor_type must be 'agent' or 'system'"
            )
        query += " AND actor_type = :actor_type"
        params["actor_type"] = actor_type
    
    query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset
    
    result = db.execute(query, params)
    rows = result.fetchall()
    
    events = []
    for row in rows:
        events.append({
            "id": row[0],
            "workspace_id": row[1],
            "actor_type": row[2],
            "actor_id": row[3],
            "event_type": row[4],
            "payload": row[5],
            "created_at": row[6].isoformat()
        })
    
    return {"events": events, "count": len(events)}
