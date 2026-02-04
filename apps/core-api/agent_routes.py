"""
Agent-facing routes for AGORA Core API.

Includes:
- Agent profile endpoint
- Agent context endpoint (workspace state)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from auth_middleware import get_agent_context, AgentContext
from database import get_db

router = APIRouter()


class AgentProfile(BaseModel):
    """Agent profile response."""
    agent_id: str
    moltbook_id: str
    name: str
    reputation: int
    profile_meta: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str


class WorkspaceContext(BaseModel):
    """Agent context within a workspace."""
    workspace_id: str
    workspace_name: str
    phase: str
    agent_role: Optional[str] = None
    agent_role_id: Optional[str] = None
    open_tasks: List[Dict[str, Any]] = []
    blocking_items: List[Dict[str, Any]] = []
    recent_events: List[Dict[str, Any]] = []


@router.get("/agents/me", response_model=AgentProfile)
async def get_agent_profile_FIXED(
    agent: AgentContext = Depends(get_agent_context)
):
    """
    Get authenticated agent's profile.
    
    Returns the agent's profile information from the database.
    """
    with get_db() as db:
        result = db.execute(
            """
            SELECT id, moltbook_id, name, reputation, created_at
            FROM agents
            WHERE id = %s
            """,
            (agent.agent_id,)
        ).fetchone()
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail={"error": "AGENT_NOT_FOUND", "message": "Agent not found in database"}
            )
        
        return AgentProfile(
            agent_id=str(result[0]),
            moltbook_id=result[1],
            name=result[2] if result[2] else "Unknown Agent",
            reputation=int(result[3]) if result[3] else 0,
            profile_meta=None,
            created_at=result[4].isoformat(),
            updated_at=result[4].isoformat()  # Use created_at for updated_at since column doesn't exist
        )


@router.get("/agent/context", response_model=WorkspaceContext)
async def get_agent_context_endpoint(
    workspace_id: str = Query(..., description="Workspace ID"),
    agent: AgentContext = Depends(get_agent_context)
):
    """
    Get agent's context within a workspace.
    
    Returns:
    - Workspace phase
    - Agent's role (if member)
    - Open tasks assigned to agent
    - Blocking items
    - Recent events
    """
    with get_db() as db:
        # Get workspace info
        workspace_result = db.execute(
            """
            SELECT id, name, phase
            FROM workspaces
            WHERE id = %s
            """,
            (workspace_id,)
        ).fetchone()
        
        if not workspace_result:
            raise HTTPException(
                status_code=404,
                detail={"error": "WORKSPACE_NOT_FOUND", "message": "Workspace not found"}
            )
        
        # Get agent's role in workspace
        role_result = db.execute(
            """
            SELECT wa.role_id, r.name as role_name
            FROM workspace_agents wa
            JOIN roles r ON wa.role_id = r.id
            WHERE wa.workspace_id = %s AND wa.agent_id = %s
            """,
            (workspace_id, agent.agent_id)
        ).fetchone()
        
        agent_role = role_result[1] if role_result else None
        agent_role_id = role_result[0] if role_result else None
        
        # Get open tasks (placeholder - will be populated when task system is implemented)
        open_tasks_result = db.execute(
            """
            SELECT id, task_name, status, created_at
            FROM agent_tasks
            WHERE workspace_id = %s AND agent_id = %s AND status = 'pending'
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (workspace_id, agent.agent_id)
        ).fetchall()
        
        open_tasks = [
            {
                "task_id": row[0],
                "task_name": row[1],
                "status": row[2],
                "created_at": row[3].isoformat()
            }
            for row in open_tasks_result
        ]
        
        # Get recent events
        events_result = db.execute(
            """
            SELECT id, event_type, event_data, created_at
            FROM events
            WHERE workspace_id = %s
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (workspace_id,)
        ).fetchall()
        
        recent_events = [
            {
                "event_id": row[0],
                "event_type": row[1],
                "event_data": row[2],
                "created_at": row[3].isoformat()
            }
            for row in events_result
        ]
        
        # Blocking items (placeholder - will be expanded)
        blocking_items = []
        
        return WorkspaceContext(
            workspace_id=workspace_result[0],
            workspace_name=workspace_result[1],
            phase=workspace_result[2],
            agent_role=agent_role,
            agent_role_id=agent_role_id,
            open_tasks=open_tasks,
            blocking_items=blocking_items,
            recent_events=recent_events
        )
