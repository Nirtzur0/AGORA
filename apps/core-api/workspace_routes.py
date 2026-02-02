"""
Workspace routes for AGORA Core API.

Implements workspace lifecycle + team formation per Docs/04 §4.2-4.3.
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid
import json

from auth_middleware import get_agent_context, AgentContext, require_permissions, require_role
from database import get_db, get_raw_db
from sqlalchemy import text
from idempotency import IdempotencyChecker
import rbac


router = APIRouter(prefix="/workspaces", tags=["workspaces"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateWorkspaceRequest(BaseModel):
    """Request to create a new workspace."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)


class WorkspaceResponse(BaseModel):
    """Workspace metadata."""
    id: str
    name: str
    description: Optional[str]
    phase: str
    reputation_config: dict
    created_by: str
    created_at: datetime
    updated_at: datetime


class WorkspaceMemberResponse(BaseModel):
    """Workspace member info."""
    agent_id: str
    role_id: str
    role_name: str
    status: str
    joined_at: datetime


class WorkspaceDetailResponse(BaseModel):
    """Workspace with team roster."""
    workspace: WorkspaceResponse
    team: List[WorkspaceMemberResponse]


class UpdateWorkspaceRequest(BaseModel):
    """Update workspace (description only)."""
    description: Optional[str] = Field(None, max_length=2000)


class CreateJoinRequestRequest(BaseModel):
    """Request to join a workspace."""
    role_id: str


class ReviewJoinRequestRequest(BaseModel):
    """Review a join request."""
    approve: bool
    reason: Optional[str] = Field(None, max_length=500)


# ============================================================================
# Event Emission
# ============================================================================

def emit_event(db, workspace_id: str, actor_type: str, actor_id: str, event_type: str, payload: dict):
    """
    Emit an event to the events table.
    
    Events are system-written only. Agents never directly write events.
    """
    event_id = str(uuid.uuid4())
    
    db.execute(
        """
        INSERT INTO events (id, workspace_id, actor_type, actor_id, event_type, payload, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """,
        (event_id, workspace_id, actor_type, actor_id, event_type, payload)
    )
    
    return event_id


# ============================================================================
# Workspace CRUD
# ============================================================================

@router.post("", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    request: CreateWorkspaceRequest,
    agent: AgentContext = Depends(get_agent_context),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    Create a new workspace.
    
    - Sets phase=INIT
    - Adds creator as Maintainer
    - Emits workspace.created and agent.joined events
    
    Requires: Agent must have reputation >= 0 (Maintainer min_reputation)
    """
    with get_db() as db:
        # Check idempotency
        if idempotency_key:
            checker = IdempotencyChecker(db, None, agent.agent_id)  # No workspace yet
            existing = checker.check_idempotency("workspace.create", idempotency_key)
            if existing:
                # Return existing workspace
                result = db.execute(
                    "SELECT id, name, description, phase, reputation_config, created_by, created_at, updated_at FROM workspaces WHERE id = %s",
                    (existing["result_id"],)
                ).fetchone()
                
                return WorkspaceResponse(
                    id=result[0],
                    name=result[1],
                    description=result[2],
                    phase=result[3],
                    reputation_config=result[4],
                    created_by=result[5],
                    created_at=result[6],
                    updated_at=result[7]
                )
        
        # Check agent's reputation meets Maintainer requirement
        if not rbac.check_reputation_requirement(db, agent.agent_id, "Maintainer"):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "INSUFFICIENT_REPUTATION",
                    "message": "Agent does not meet minimum reputation for Maintainer role",
                    "required_reputation": 0,
                    "agent_reputation": agent.reputation
                }
            )
        
        # Create workspace
        workspace_id = str(uuid.uuid4())
        
        db.execute(
            """
            INSERT INTO workspaces (id, name, description, phase, reputation_config, created_by, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (
                workspace_id,
                request.name,
                request.description,
                "INIT",  # All workspaces start in INIT phase
                {},  # Default empty reputation config
                agent.agent_id
            )
        )
        
        # Get Maintainer role
        maintainer_role = db.execute(
            "SELECT id FROM roles WHERE name = %s",
            ("Maintainer",)
        ).fetchone()
        
        if not maintainer_role:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "ROLE_NOT_FOUND",
                    "message": "Maintainer role not found (roles not seeded?)"
                }
            )
        
        # Add creator as Maintainer
        db.execute(
            """
            INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status, joined_at)
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (workspace_id, agent.agent_id, maintainer_role[0], "active")
        )
        
        # Emit events
        emit_event(
            db,
            workspace_id,
            "agent",
            agent.agent_id,
            "workspace.created",
            {
                "workspace_id": workspace_id,
                "name": request.name,
                "creator_agent_id": agent.agent_id
            }
        )
        
        emit_event(
            db,
            workspace_id,
            "system",
            "core-api",
            "agent.joined",
            {
                "agent_id": agent.agent_id,
                "role_id": maintainer_role[0],
                "role_name": "Maintainer"
            }
        )
        
        # Store idempotency result
        if idempotency_key:
            checker.store_idempotency_result(
                "workspace.create",
                idempotency_key,
                "workspace",
                workspace_id
            )
        
        db.commit()
        
        # Return created workspace
        result = db.execute(
            "SELECT id, name, description, phase, reputation_config, created_by, created_at, updated_at FROM workspaces WHERE id = %s",
            (workspace_id,)
        ).fetchone()
        
        return WorkspaceResponse(
            id=result[0],
            name=result[1],
            description=result[2],
            phase=result[3],
            reputation_config=result[4],
            created_by=result[5],
            created_at=result[6],
            updated_at=result[7]
        )


@router.get("", response_model=List[WorkspaceResponse])
async def list_workspaces(
    phase: Optional[str] = None,
    agent: AgentContext = Depends(get_agent_context)
):
    """
    List workspaces.
    
    Optional filters:
    - phase: Filter by workspace phase
    """
    with get_db() as db:
        query = """
            SELECT id, name, description, phase, reputation_config, created_by, created_at, updated_at
            FROM workspaces
        """
        params = []
        
        if phase:
            query += " WHERE phase = %s"
            params.append(phase)
        
        query += " ORDER BY created_at DESC"
        
        results = db.execute(query, tuple(params)).fetchall()
        
        return [
            WorkspaceResponse(
                id=row[0],
                name=row[1],
                description=row[2],
                phase=row[3],
                reputation_config=row[4],
                created_by=row[5],
                created_at=row[6],
                updated_at=row[7]
            )
            for row in results
        ]


@router.get("/{workspace_id}", response_model=WorkspaceDetailResponse)
async def get_workspace(
    workspace_id: str,
    agent: AgentContext = Depends(get_agent_context)
):
    """
    Get workspace metadata + team roster.
    """
    with get_db() as db:
        # Get workspace
        workspace_result = db.execute(
            "SELECT id, name, description, phase, reputation_config, created_by, created_at, updated_at FROM workspaces WHERE id = %s",
            (workspace_id,)
        ).fetchone()
        
        if not workspace_result:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "WORKSPACE_NOT_FOUND",
                    "message": f"Workspace {workspace_id} not found"
                }
            )
        
        # Get team roster
        team_results = db.execute(
            """
            SELECT wa.agent_id, wa.role_id, r.name, wa.status, wa.joined_at
            FROM workspace_agents wa
            JOIN roles r ON wa.role_id = r.id
            WHERE wa.workspace_id = %s
            ORDER BY wa.joined_at ASC
            """,
            (workspace_id,)
        ).fetchall()
        
        workspace = WorkspaceResponse(
            id=workspace_result[0],
            name=workspace_result[1],
            description=workspace_result[2],
            phase=workspace_result[3],
            reputation_config=workspace_result[4],
            created_by=workspace_result[5],
            created_at=workspace_result[6],
            updated_at=workspace_result[7]
        )
        
        team = [
            WorkspaceMemberResponse(
                agent_id=row[0],
                role_id=row[1],
                role_name=row[2],
                status=row[3],
                joined_at=row[4]
            )
            for row in team_results
        ]
        
        return WorkspaceDetailResponse(workspace=workspace, team=team)


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    request: UpdateWorkspaceRequest,
    agent: AgentContext = Depends(require_permissions(["workspace.update"]))
):
    """
    Update workspace description.
    
    Note: Phase updates are NOT allowed via this endpoint.
    Only the orchestrator can change workspace phase.
    
    Requires: workspace.update permission
    """
    with get_db() as db:
        # Check workspace exists
        workspace_result = db.execute(
            "SELECT id FROM workspaces WHERE id = %s",
            (workspace_id,)
        ).fetchone()
        
        if not workspace_result:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "WORKSPACE_NOT_FOUND",
                    "message": f"Workspace {workspace_id} not found"
                }
            )
        
        # Update description only
        db.execute(
            """
            UPDATE workspaces
            SET description = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (request.description, workspace_id)
        )
        
        db.commit()
        
        # Return updated workspace
        result = db.execute(
            "SELECT id, name, description, phase, reputation_config, created_by, created_at, updated_at FROM workspaces WHERE id = %s",
            (workspace_id,)
        ).fetchone()
        
        return WorkspaceResponse(
            id=result[0],
            name=result[1],
            description=result[2],
            phase=result[3],
            reputation_config=result[4],
            created_by=result[5],
            created_at=result[6],
            updated_at=result[7]
        )


# ============================================================================
# Join Requests
# ============================================================================

@router.post("/{workspace_id}/join-requests", status_code=201)
async def create_join_request(
    workspace_id: str,
    request: CreateJoinRequestRequest,
    agent: AgentContext = Depends(get_agent_context),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    Request to join a workspace with a specific role.
    
    Checks:
    - Agent meets min_reputation for role
    - Agent is not already a member
    - No pending join request exists
    """
    with get_db() as db:
        # Check idempotency
        if idempotency_key:
            checker = IdempotencyChecker(db, workspace_id, agent.agent_id)
            existing = checker.check_idempotency("join_request.create", idempotency_key)
            if existing:
                # Return existing join request
                result = db.execute(
                    "SELECT id, workspace_id, agent_id, role_id, status, requested_at, reviewed_at, reviewed_by FROM join_requests WHERE id = %s",
                    (existing["result_id"],)
                ).fetchone()
                
                return {
                    "id": result[0],
                    "workspace_id": result[1],
                    "agent_id": result[2],
                    "role_id": result[3],
                    "status": result[4],
                    "requested_at": result[5],
                    "reviewed_at": result[6],
                    "reviewed_by": result[7]
                }
        
        # Check workspace exists
        workspace_result = db.execute(
            "SELECT id FROM workspaces WHERE id = %s",
            (workspace_id,)
        ).fetchone()
        
        if not workspace_result:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "WORKSPACE_NOT_FOUND",
                    "message": f"Workspace {workspace_id} not found"
                }
            )
        
        # Check role exists
        role_result = db.execute(
            "SELECT id, name, min_reputation, capacity FROM roles WHERE id = %s",
            (request.role_id,)
        ).fetchone()
        
        if not role_result:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "ROLE_NOT_FOUND",
                    "message": f"Role {request.role_id} not found"
                }
            )
        
        role_name = role_result[1]
        min_reputation = role_result[2]
        
        # Check reputation requirement
        if agent.reputation < min_reputation:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "INSUFFICIENT_REPUTATION",
                    "message": f"Agent reputation {agent.reputation} below minimum {min_reputation} for role {role_name}",
                    "required_reputation": min_reputation,
                    "agent_reputation": agent.reputation,
                    "role_name": role_name
                }
            )
        
        # Check if already a member
        existing_member = db.execute(
            "SELECT id FROM workspace_agents WHERE workspace_id = %s AND agent_id = %s",
            (workspace_id, agent.agent_id)
        ).fetchone()
        
        if existing_member:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "ALREADY_MEMBER",
                    "message": "Agent is already a member of this workspace"
                }
            )
        
        # Check for pending join request
        pending_request = db.execute(
            "SELECT id FROM join_requests WHERE workspace_id = %s AND agent_id = %s AND status = %s",
            (workspace_id, agent.agent_id, "pending")
        ).fetchone()
        
        if pending_request:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "PENDING_REQUEST_EXISTS",
                    "message": "A pending join request already exists for this workspace"
                }
            )
        
        # Create join request
        join_request_id = str(uuid.uuid4())
        
        db.execute(
            """
            INSERT INTO join_requests (id, workspace_id, agent_id, role_id, status, requested_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            """,
            (join_request_id, workspace_id, agent.agent_id, request.role_id, "pending")
        )
        
        # Store idempotency result
        if idempotency_key:
            checker.store_idempotency_result(
                "join_request.create",
                idempotency_key,
                "join_request",
                join_request_id
            )
        
        db.commit()
        
        # Return created join request
        result = db.execute(
            "SELECT id, workspace_id, agent_id, role_id, status, requested_at, reviewed_at, reviewed_by FROM join_requests WHERE id = %s",
            (join_request_id,)
        ).fetchone()
        
        return {
            "id": result[0],
            "workspace_id": result[1],
            "agent_id": result[2],
            "role_id": result[3],
            "status": result[4],
            "requested_at": result[5],
            "reviewed_at": result[6],
            "reviewed_by": result[7]
        }


@router.post("/{workspace_id}/join-requests/{request_id}/review", status_code=200)
async def review_join_request(
    workspace_id: str,
    request_id: str,
    request: ReviewJoinRequestRequest,
    agent: AgentContext = Depends(require_permissions(["join_request.review"]))
):
    """
    Review a join request (approve or reject).
    
    Checks on approval:
    - Role capacity not exceeded
    - Agent still meets reputation requirement
    - Agent is not already a member
    
    Requires: join_request.review permission (Maintainer only)
    """
    with get_db() as db:
        # Get join request
        join_request_result = db.execute(
            """
            SELECT id, workspace_id, agent_id, role_id, status
            FROM join_requests
            WHERE id = %s AND workspace_id = %s
            """,
            (request_id, workspace_id)
        ).fetchone()
        
        if not join_request_result:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "JOIN_REQUEST_NOT_FOUND",
                    "message": f"Join request {request_id} not found in workspace {workspace_id}"
                }
            )
        
        jr_id, jr_workspace_id, jr_agent_id, jr_role_id, jr_status = join_request_result
        
        # Check if already reviewed
        if jr_status != "pending":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "ALREADY_REVIEWED",
                    "message": f"Join request has already been {jr_status}"
                }
            )
        
        if request.approve:
            # Get role info
            role_result = db.execute(
                "SELECT name, min_reputation, capacity FROM roles WHERE id = %s",
                (jr_role_id,)
            ).fetchone()
            
            if not role_result:
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": "ROLE_NOT_FOUND",
                        "message": "Role not found"
                    }
                )
            
            role_name, min_reputation, capacity = role_result
            
            # Check capacity
            current_count = db.execute(
                "SELECT COUNT(*) FROM workspace_agents WHERE workspace_id = %s AND role_id = %s AND status = %s",
                (workspace_id, jr_role_id, "active")
            ).fetchone()[0]
            
            if current_count >= capacity:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "ROLE_CAPACITY_EXCEEDED",
                        "message": f"Role {role_name} is at capacity ({current_count}/{capacity})",
                        "role_name": role_name,
                        "capacity": capacity,
                        "current_count": current_count
                    }
                )
            
            # Get agent reputation
            agent_result = db.execute(
                "SELECT reputation FROM agents WHERE id = %s",
                (jr_agent_id,)
            ).fetchone()
            
            if not agent_result:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "AGENT_NOT_FOUND",
                        "message": "Agent not found"
                    }
                )
            
            agent_reputation = agent_result[0]
            
            # Check reputation still meets requirement
            if agent_reputation < min_reputation:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "INSUFFICIENT_REPUTATION",
                        "message": f"Agent reputation {agent_reputation} below minimum {min_reputation} for role {role_name}",
                        "required_reputation": min_reputation,
                        "agent_reputation": agent_reputation,
                        "role_name": role_name
                    }
                )
            
            # Check if agent is already a member
            existing_member = db.execute(
                "SELECT id FROM workspace_agents WHERE workspace_id = %s AND agent_id = %s",
                (workspace_id, jr_agent_id)
            ).fetchone()
            
            if existing_member:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "ALREADY_MEMBER",
                        "message": "Agent is already a member of this workspace"
                    }
                )
            
            # Approve: add to workspace_agents
            db.execute(
                """
                INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status, joined_at)
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (workspace_id, jr_agent_id, jr_role_id, "active")
            )
            
            # Emit agent.joined event
            emit_event(
                db,
                workspace_id,
                "system",
                "core-api",
                "agent.joined",
                {
                    "agent_id": jr_agent_id,
                    "role_id": jr_role_id,
                    "role_name": role_name,
                    "approved_by": agent.agent_id
                }
            )
        
        # Update join request status
        new_status = "approved" if request.approve else "rejected"
        
        db.execute(
            """
            UPDATE join_requests
            SET status = %s, reviewed_at = NOW(), reviewed_by = %s
            WHERE id = %s
            """,
            (new_status, agent.agent_id, request_id)
        )
        
        db.commit()
        
        # Return updated join request
        result = db.execute(
            "SELECT id, workspace_id, agent_id, role_id, status, requested_at, reviewed_at, reviewed_by FROM join_requests WHERE id = %s",
            (request_id,)
        ).fetchone()
        
        return {
            "id": result[0],
            "workspace_id": result[1],
            "agent_id": result[2],
            "role_id": result[3],
            "status": result[4],
            "requested_at": result[5],
            "reviewed_at": result[6],
            "reviewed_by": result[7]
        }
