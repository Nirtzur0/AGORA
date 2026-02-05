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
from agent_tasks import TaskStatus
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
    recent_logs: List[Dict[str, Any]] = []
    key_claims: List[Dict[str, Any]] = []
    latest_artifacts: List[Dict[str, Any]] = []
    next_actions: List[str] = []


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
        
        # Get open tasks for agent (plus role-targeted tasks if present)
        if agent_role:
            open_tasks_result = db.execute(
                """
                SELECT id, assignee_agent_id, type, status, payload, created_at, completed_at
                FROM agent_tasks
                WHERE workspace_id = %s
                  AND status IN (%s, %s, %s)
                  AND (
                    assignee_agent_id = %s
                    OR (assignee_agent_id IS NULL AND payload->>'assignee_role' = %s)
                  )
                ORDER BY created_at DESC
                LIMIT 20
                """,
                (workspace_id, TaskStatus.OPEN.value, TaskStatus.IN_PROGRESS.value, TaskStatus.BLOCKED.value, agent.agent_id, agent_role)
            ).fetchall()
        else:
            open_tasks_result = db.execute(
                """
                SELECT id, assignee_agent_id, type, status, payload, created_at, completed_at
                FROM agent_tasks
                WHERE workspace_id = %s
                  AND status IN (%s, %s, %s)
                  AND assignee_agent_id = %s
                ORDER BY created_at DESC
                LIMIT 20
                """,
                (workspace_id, TaskStatus.OPEN.value, TaskStatus.IN_PROGRESS.value, TaskStatus.BLOCKED.value, agent.agent_id)
            ).fetchall()

        open_tasks = []
        next_actions = set()
        for row in open_tasks_result:
            payload = row[4] or {}
            if isinstance(payload, str):
                import json
                payload = json.loads(payload)
            required_outputs = payload.get("required_outputs", []) or []
            next_actions.update(required_outputs)
            open_tasks.append(
                {
                    "id": str(row[0]),
                    "assignee_agent_id": str(row[1]) if row[1] else None,
                    "type": row[2],
                    "status": row[3],
                    "payload": payload,
                    "result_links": payload.get("result_links", []),
                    "created_at": row[5].isoformat(),
                    "completed_at": row[6].isoformat() if row[6] else None
                }
            )
        
        # Get recent events
        events_result = db.execute(
            """
            SELECT id, event_type, payload, created_at
            FROM events
            WHERE workspace_id = %s
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (workspace_id,)
        ).fetchall()
        
        recent_events = [
            {
                "id": str(row[0]),
                "event_type": row[1],
                "payload": row[2],
                "created_at": row[3].isoformat()
            }
            for row in events_result
        ]
        
        # Recent logs
        logs_result = db.execute(
            """
            SELECT id, agent_id, action, payload, created_at
            FROM logs
            WHERE workspace_id = %s
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (workspace_id,)
        ).fetchall()

        recent_logs = [
            {
                "id": str(row[0]),
                "agent_id": str(row[1]) if row[1] else None,
                "action": row[2],
                "payload": row[3],
                "created_at": row[4].isoformat()
            }
            for row in logs_result
        ]

        # Key claims (fallback to recent claims if none are marked key)
        key_claims_result = db.execute(
            """
            SELECT id, kind, text, confidence, status, created_at
            FROM claims
            WHERE workspace_id = %s AND is_key = true
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (workspace_id,)
        ).fetchall()

        if not key_claims_result:
            key_claims_result = db.execute(
                """
                SELECT id, kind, text, confidence, status, created_at
                FROM claims
                WHERE workspace_id = %s
                ORDER BY created_at DESC
                LIMIT 10
                """,
                (workspace_id,)
            ).fetchall()

        key_claims = [
            {
                "id": str(row[0]),
                "kind": row[1],
                "text": row[2],
                "confidence": row[3],
                "status": row[4],
                "created_at": row[5].isoformat()
            }
            for row in key_claims_result
        ]

        # Latest artifacts (small bounded list)
        artifacts_result = db.execute(
            """
            SELECT id, short_id, type, created_at
            FROM artifacts
            WHERE workspace_id = %s
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (workspace_id,)
        ).fetchall()

        latest_artifacts = [
            {
                "id": str(row[0]),
                "short_id": row[1],
                "type": row[2],
                "created_at": row[3].isoformat()
            }
            for row in artifacts_result
        ]

        # Blocking items (open blocking critiques + failing rule checks)
        blocking_items = []
        critique_rows = db.execute(
            """
            SELECT id, target_type, target_id, severity, message, created_at
            FROM critiques
            WHERE workspace_id = %s AND status = 'open' AND severity = 'blocking'
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (workspace_id,)
        ).fetchall()
        for row in critique_rows:
            blocking_items.append(
                {
                    "type": "critique",
                    "id": str(row[0]),
                    "target_type": row[1],
                    "target_id": str(row[2]),
                    "severity": row[3],
                    "message": row[4],
                    "created_at": row[5].isoformat()
                }
            )

        rule_rows = db.execute(
            """
            SELECT id, rule_name, target_type, target_id, details, created_at
            FROM rule_checks
            WHERE workspace_id = %s AND status = 'fail'
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (workspace_id,)
        ).fetchall()
        for row in rule_rows:
            blocking_items.append(
                {
                    "type": "rule_check",
                    "id": str(row[0]),
                    "rule_name": row[1],
                    "target_type": row[2],
                    "target_id": str(row[3]),
                    "details": row[4],
                    "created_at": row[5].isoformat()
                }
            )
        
        return WorkspaceContext(
            workspace_id=str(workspace_result[0]),
            workspace_name=workspace_result[1],
            phase=workspace_result[2],
            agent_role=agent_role,
            agent_role_id=str(agent_role_id) if agent_role_id else None,
            open_tasks=open_tasks,
            blocking_items=blocking_items,
            recent_events=recent_events,
            recent_logs=recent_logs,
            key_claims=key_claims,
            latest_artifacts=latest_artifacts,
            next_actions=sorted(next_actions)
        )
