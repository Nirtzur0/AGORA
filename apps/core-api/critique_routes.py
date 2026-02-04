"""
Critique Routes (Component 19)

Per spec §4.7:
- POST /workspaces/{id}/critiques: Create critique
- PATCH /critiques/{id}: Update critique status/resolution (with authority rules)
- GET /workspaces/{id}/critiques: List/filter critiques

Authorization rules (§4.7):
- Only critic_agent_id may change status/resolution
- Maintainer may override ONLY if NOT the target author
- Target author MUST NOT resolve their own critique
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import uuid
import json

from database import DBWrapper, get_db_session
from auth_middleware import require_agent_token, get_optional_agent_context, AgentContext


router = APIRouter()


# Request/Response Models

class CritiqueResolution(BaseModel):
    """Critique resolution details."""
    status: str = Field(..., description="accepted_fix|deferred_with_rationale|rejected_with_evidence")
    link: Optional[Dict[str, Any]] = Field(None, description="Optional link to artifact/log/version")
    rationale: Optional[str] = Field(None, description="Rationale for deferral/rejection")


class CreateCritiqueRequest(BaseModel):
    """Request to create a critique."""
    target_type: str = Field(..., description="claim|workflow_run|artifact_version")
    target_id: str = Field(..., description="UUID of target")
    target_location: Optional[str] = Field(None, description="Optional span/section within target")
    severity: str = Field(..., description="info|minor|major|blocking")
    message: str = Field(..., description="Critique message")


class UpdateCritiqueRequest(BaseModel):
    """Request to update critique status/resolution."""
    status: str = Field(..., description="open|resolved|deferred|rejected")
    resolution: Optional[CritiqueResolution] = Field(None, description="Resolution details")


class CritiqueResponse(BaseModel):
    """Critique response."""
    id: str
    workspace_id: str
    target_type: str
    target_id: str
    target_location: Optional[str]
    critic_agent_id: str
    status: str
    severity: str
    message: str
    resolution: Optional[Dict[str, Any]]
    created_at: str


@router.post("/workspaces/{workspace_id}/critiques", response_model=CritiqueResponse, tags=["Critiques"])
async def create_critique(
    workspace_id: uuid.UUID,
    request: CreateCritiqueRequest,
    current_agent: AgentContext = Depends(require_agent_token),
    db: DBWrapper = Depends(get_db_session)
):
    """
    Create a critique on a target (claim, workflow_run, artifact_version).
    
    Per spec §4.7:
    - Creates critique record
    - Links to target via target_type + target_id
    - Records critic_agent_id
    
    Returns:
        CritiqueResponse with created critique
        
    Raises:
        404: Workspace or target not found
        400: Invalid request
    """
    workspace_id_str = str(workspace_id)
    
    # Verify workspace exists
    ws_row = db.execute(
        "SELECT id FROM workspaces WHERE id = :id",
        {"id": workspace_id_str}
    ).fetchone()
    
    if not ws_row:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id_str} not found")
    
    # Validate target_type
    valid_target_types = ["claim", "workflow_run", "artifact_version"]
    if request.target_type not in valid_target_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target_type: {request.target_type}. Must be one of: {', '.join(valid_target_types)}"
        )
    
    # Validate severity
    valid_severities = ["info", "minor", "major", "blocking"]
    if request.severity not in valid_severities:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid severity: {request.severity}. Must be one of: {', '.join(valid_severities)}"
        )
    
    # Verify target exists based on type
    if request.target_type == "claim":
        target = db.execute(
            "SELECT id, workspace_id FROM claims WHERE id = :id",
            {"id": request.target_id}
        ).fetchone()
    elif request.target_type == "workflow_run":
        target = db.execute(
            "SELECT id, workspace_id FROM workflow_runs WHERE id = :id",
            {"id": request.target_id}
        ).fetchone()
    elif request.target_type == "artifact_version":
        target = db.execute(
            """
            SELECT av.id, a.workspace_id
            FROM artifact_versions av
            JOIN artifacts a ON av.artifact_id = a.id
            WHERE av.id = :id
            """,
            {"id": request.target_id}
        ).fetchone()
    
    if not target:
        raise HTTPException(
            status_code=404,
            detail=f"Target {request.target_type} {request.target_id} not found"
        )
    
    if str(target[1]) != workspace_id_str:
        raise HTTPException(
            status_code=403,
            detail=f"Target does not belong to workspace {workspace_id_str}"
        )
    
    # Create critique
    critique_id = str(uuid.uuid4())
    
    db.execute(
        """
        INSERT INTO critiques (
            id, workspace_id, target_type, target_id, target_location,
            critic_agent_id, status, severity, message, created_at
        ) VALUES (
            :id, :workspace_id, :target_type, :target_id, :target_location,
            :critic_agent_id, :status, :severity, :message, NOW()
        )
        """,
        {
            "id": critique_id,
            "workspace_id": workspace_id_str,
            "target_type": request.target_type,
            "target_id": request.target_id,
            "target_location": request.target_location,
            "critic_agent_id": current_agent.agent_id,
            "status": "open",
            "severity": request.severity,
            "message": request.message
        }
    )
    
    db.commit()
    
    # Log event
    db.execute(
        """
        INSERT INTO events (
            id, workspace_id, actor_type, actor_id, event_type, payload, created_at
        ) VALUES (
            :id, :workspace_id, :actor_type, :actor_id, :event_type, :payload, NOW()
        )
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id_str,
            "actor_type": "agent",
            "actor_id": current_agent.agent_id,
            "event_type": "critique.created",
            "payload": json.dumps({
                "critique_id": critique_id,
                "target_type": request.target_type,
                "target_id": request.target_id,
                "severity": request.severity
            })
        }
    )
    
    db.commit()
    
    # Retrieve created critique
    critique = db.execute(
        """
        SELECT id, workspace_id, target_type, target_id, target_location,
               critic_agent_id, status, severity, message, resolution, created_at
        FROM critiques
        WHERE id = :id
        """,
        {"id": critique_id}
    ).fetchone()
    
    return CritiqueResponse(
        id=str(critique[0]),
        workspace_id=str(critique[1]),
        target_type=critique[2],
        target_id=str(critique[3]),
        target_location=critique[4],
        critic_agent_id=str(critique[5]),
        status=critique[6],
        severity=critique[7],
        message=critique[8],
        resolution=json.loads(critique[9]) if critique[9] else None,
        created_at=critique[10].isoformat()
    )


@router.patch("/critiques/{critique_id}", response_model=CritiqueResponse, tags=["Critiques"])
async def update_critique(
    critique_id: uuid.UUID,
    request: UpdateCritiqueRequest,
    current_agent: AgentContext = Depends(require_agent_token),
    db: DBWrapper = Depends(get_db_session)
):
    """
    Update critique status/resolution.
    
    Per spec §4.7 Authorization Rules:
    - Only critic_agent_id may change status/resolution
    - Maintainer may override ONLY if NOT the target author
    - Target author MUST NOT resolve their own critique
    
    Returns:
        CritiqueResponse with updated critique
        
    Raises:
        404: Critique not found
        403: Unauthorized to update critique
        400: Invalid status/resolution
    """
    critique_id_str = str(critique_id)
    
    # Get critique with target author info
    critique = db.execute(
        """
        SELECT c.id, c.workspace_id, c.target_type, c.target_id, c.target_location,
               c.critic_agent_id, c.status, c.severity, c.message, c.resolution, c.created_at,
               CASE 
                   WHEN c.target_type = 'claim' THEN cl.created_by
                   WHEN c.target_type = 'workflow_run' THEN NULL
                   WHEN c.target_type = 'artifact_version' THEN av.created_by
                   ELSE NULL
               END as target_author_id
        FROM critiques c
        LEFT JOIN claims cl ON c.target_type = 'claim' AND c.target_id = cl.id
        LEFT JOIN artifact_versions av ON c.target_type = 'artifact_version' AND c.target_id = av.id
        WHERE c.id = :id
        """,
        {"id": critique_id_str}
    ).fetchone()
    
    if not critique:
        raise HTTPException(status_code=404, detail=f"Critique {critique_id_str} not found")
    
    critic_agent_id = str(critique[5]) if critique[5] is not None else None
    target_author_id = str(critique[11]) if critique[11] is not None else None
    workspace_id = critique[1]
    
    # Check authorization
    agent_id = current_agent.agent_id
    
    # Rule 1: Target author MUST NOT resolve their own critique
    if target_author_id and agent_id == target_author_id:
        raise HTTPException(
            status_code=403,
            detail="Target author cannot resolve their own critique"
        )
    
    # Rule 2: Only critic or authorized Maintainer may update
    is_critic = agent_id == critic_agent_id
    
    # Check if agent is Maintainer
    is_maintainer = False
    maintainer_check = db.execute(
        """
        SELECT 1
        FROM workspace_agents wa
        JOIN roles r ON wa.role_id = r.id
        WHERE wa.workspace_id = :workspace_id
          AND wa.agent_id = :agent_id
          AND r.name = 'Maintainer'
          AND wa.status = 'active'
        """,
        {"workspace_id": workspace_id, "agent_id": agent_id}
    ).fetchone()
    
    is_maintainer = maintainer_check is not None
    
    # Rule 3: Maintainer override requires they are NOT the target author
    if not is_critic:
        if is_maintainer and target_author_id and agent_id == target_author_id:
            raise HTTPException(
                status_code=403,
                detail="Maintainer cannot override critique on their own work"
            )
        
        if not is_maintainer:
            raise HTTPException(
                status_code=403,
                detail="Only the critic or a Maintainer may update this critique"
            )
        
        # Log maintainer override event
        db.execute(
            """
            INSERT INTO events (
                id, workspace_id, actor_type, actor_id, event_type, payload, created_at
            ) VALUES (
                :id, :workspace_id, :actor_type, :actor_id, :event_type, :payload, NOW()
            )
            """,
            {
                "id": str(uuid.uuid4()),
                "workspace_id": workspace_id,
                "actor_type": "agent",
                "actor_id": agent_id,
                "event_type": "critique.maintainer_override",
                "payload": json.dumps({
                    "critique_id": critique_id_str,
                    "original_critic": critic_agent_id,
                    "new_status": request.status
                })
            }
        )
        db.commit()
    
    # Validate status
    valid_statuses = ["open", "resolved", "deferred", "rejected"]
    if request.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: {request.status}. Must be one of: {', '.join(valid_statuses)}"
        )
    
    # Validate resolution if provided
    if request.resolution:
        valid_resolution_statuses = ["accepted_fix", "deferred_with_rationale", "rejected_with_evidence"]
        if request.resolution.status not in valid_resolution_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid resolution status: {request.resolution.status}. Must be one of: {', '.join(valid_resolution_statuses)}"
            )
    
    # Update critique
    resolution_json = json.dumps(request.resolution.dict()) if request.resolution else None
    
    db.execute(
        """
        UPDATE critiques
        SET status = :status, resolution = :resolution
        WHERE id = :id
        """,
        {
            "id": critique_id_str,
            "status": request.status,
            "resolution": resolution_json
        }
    )
    
    db.commit()
    
    # Log event
    db.execute(
        """
        INSERT INTO events (
            id, workspace_id, actor_type, actor_id, event_type, payload, created_at
        ) VALUES (
            :id, :workspace_id, :actor_type, :actor_id, :event_type, :payload, NOW()
        )
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "actor_type": "agent",
            "actor_id": agent_id,
            "event_type": "critique.updated",
            "payload": json.dumps({
                "critique_id": critique_id_str,
                "new_status": request.status,
                "has_resolution": request.resolution is not None
            })
        }
    )
    
    db.commit()
    
    # Retrieve updated critique
    updated = db.execute(
        """
        SELECT id, workspace_id, target_type, target_id, target_location,
               critic_agent_id, status, severity, message, resolution, created_at
        FROM critiques
        WHERE id = :id
        """,
        {"id": critique_id_str}
    ).fetchone()
    
    resolution_value = updated[9]
    if isinstance(resolution_value, str):
        resolution_value = json.loads(resolution_value)

    return CritiqueResponse(
        id=str(updated[0]),
        workspace_id=str(updated[1]),
        target_type=updated[2],
        target_id=str(updated[3]),
        target_location=updated[4],
        critic_agent_id=str(updated[5]),
        status=updated[6],
        severity=updated[7],
        message=updated[8],
        resolution=resolution_value if resolution_value else None,
        created_at=updated[10].isoformat()
    )


@router.get("/workspaces/{workspace_id}/critiques", response_model=List[CritiqueResponse], tags=["Critiques"])
async def list_critiques(
    workspace_id: uuid.UUID,
    target_id: Optional[str] = Query(None, description="Filter by target_id"),
    status: Optional[str] = Query(None, description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    current_agent: Optional[AgentContext] = Depends(get_optional_agent_context),
    db: DBWrapper = Depends(get_db_session)
):
    """
    List critiques in workspace with optional filters.
    
    Per spec §4.7:
    - Filters: target_id, status, severity
    - Returns all critiques matching filters
    
    Returns:
        List of CritiqueResponse
        
    Raises:
        404: Workspace not found
    """
    workspace_id_str = str(workspace_id)
    
    # Verify workspace exists
    ws_row = db.execute(
        "SELECT id FROM workspaces WHERE id = :id",
        {"id": workspace_id_str}
    ).fetchone()
    
    if not ws_row:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id_str} not found")
    
    # Build query with filters
    query = """
        SELECT id, workspace_id, target_type, target_id, target_location,
               critic_agent_id, status, severity, message, resolution, created_at
        FROM critiques
        WHERE workspace_id = :workspace_id
    """
    
    params = {"workspace_id": workspace_id_str}
    
    if target_id:
        query += " AND target_id = :target_id"
        params["target_id"] = target_id
    
    if status:
        query += " AND status = :status"
        params["status"] = status
    
    if severity:
        query += " AND severity = :severity"
        params["severity"] = severity
    
    query += " ORDER BY created_at DESC"
    
    critiques = db.execute(query, params).fetchall()
    
    return [
        CritiqueResponse(
            id=str(c[0]),
            workspace_id=str(c[1]),
            target_type=c[2],
            target_id=str(c[3]),
            target_location=c[4],
            critic_agent_id=str(c[5]),
            status=c[6],
            severity=c[7],
            message=c[8],
            resolution=json.loads(c[9]) if c[9] else None,
            created_at=c[10].isoformat()
        )
        for c in critiques
    ]
