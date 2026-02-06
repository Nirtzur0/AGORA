"""
RBAC (Role-Based Access Control) implementation for AGORA.

Provides permission checking based on agent's role in workspace.
"""

from typing import List, Optional, Set
from fastapi import HTTPException
import json


class PermissionDeniedError(Exception):
    """Raised when agent lacks required permission."""
    def __init__(self, required_permission: str, role: Optional[str] = None):
        self.required_permission = required_permission
        self.role = role
        super().__init__(
            f"Permission denied: requires '{required_permission}'" +
            (f" (current role: {role})" if role else "")
        )


def get_agent_permissions(db, agent_id: str, workspace_id: str) -> Set[str]:
    """
    Get agent's permissions in a workspace.
    
    Args:
        db: Database connection
        agent_id: Agent UUID
        workspace_id: Workspace UUID
    
    Returns:
        Set of permission keys the agent has
    
    Raises:
        HTTPException 403: Agent is not a member of workspace
    """
    # Get agent's role in workspace
    result = db.execute(
        """
        SELECT r.permissions
        FROM workspace_agents wa
        JOIN roles r ON wa.role_id = r.id
        WHERE wa.workspace_id = :workspace_id AND wa.agent_id = :agent_id
        """,
        {"workspace_id": workspace_id, "agent_id": agent_id}
    ).fetchone()
    
    if not result:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "NOT_WORKSPACE_MEMBER",
                "message": "Agent is not a member of this workspace"
            }
        )
    
    permissions_json = result[0]
    
    # Parse permissions JSON
    if isinstance(permissions_json, str):
        permissions_data = json.loads(permissions_json)
    else:
        permissions_data = permissions_json
    
    # Extract allow list
    return set(permissions_data.get("allow", []))


def check_permission(
    db,
    agent_id: str,
    workspace_id: str,
    required_permission: str
) -> bool:
    """
    Check if agent has required permission in workspace.
    
    Args:
        db: Database connection
        agent_id: Agent UUID
        workspace_id: Workspace UUID
        required_permission: Permission key to check (e.g., "artifact.create")
    
    Returns:
        True if agent has permission, False otherwise
    """
    try:
        permissions = get_agent_permissions(db, agent_id, workspace_id)
        return required_permission in permissions
    except HTTPException:
        return False


def require_permission(
    db,
    agent_id: str,
    workspace_id: str,
    required_permission: str,
    agent_role: Optional[str] = None
):
    """
    Require agent to have permission, raise error if not.
    
    Args:
        db: Database connection
        agent_id: Agent UUID
        workspace_id: Workspace UUID
        required_permission: Permission key to check
        agent_role: Optional role name for error message
    
    Raises:
        HTTPException 403: Agent lacks required permission
    """
    if not check_permission(db, agent_id, workspace_id, required_permission):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "PERMISSION_DENIED",
                "message": f"Permission denied: requires '{required_permission}'",
                "required_permission": required_permission,
                "agent_role": agent_role
            }
        )


def require_any_permission(
    db,
    agent_id: str,
    workspace_id: str,
    required_permissions: List[str],
    agent_role: Optional[str] = None
):
    """
    Require agent to have at least one of the specified permissions.
    
    Args:
        db: Database connection
        agent_id: Agent UUID
        workspace_id: Workspace UUID
        required_permissions: List of permission keys (OR logic)
        agent_role: Optional role name for error message
    
    Raises:
        HTTPException 403: Agent lacks all required permissions
    """
    permissions = get_agent_permissions(db, agent_id, workspace_id)
    
    if not any(perm in permissions for perm in required_permissions):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "PERMISSION_DENIED",
                "message": f"Permission denied: requires one of {required_permissions}",
                "required_permissions": required_permissions,
                "agent_role": agent_role
            }
        )


def get_agent_role(db, agent_id: str, workspace_id: str) -> Optional[dict]:
    """
    Get agent's role information in workspace.
    
    Args:
        db: Database connection
        agent_id: Agent UUID
        workspace_id: Workspace UUID
    
    Returns:
        Dict with role_id, role_name, permissions, or None if not a member
    """
    result = db.execute(
        """
        SELECT r.id, r.name, r.permissions
        FROM workspace_agents wa
        JOIN roles r ON wa.role_id = r.id
        WHERE wa.workspace_id = :workspace_id AND wa.agent_id = :agent_id
        """,
        {"workspace_id": workspace_id, "agent_id": agent_id}
    ).fetchone()
    
    if not result:
        return None
    
    permissions_json = result[2]
    if isinstance(permissions_json, str):
        permissions_data = json.loads(permissions_json)
    else:
        permissions_data = permissions_json
    
    return {
        "role_id": result[0],
        "role_name": result[1],
        "permissions": permissions_data
    }


def list_all_roles(db) -> List[dict]:
    """
    List all available roles.
    
    Args:
        db: Database connection
    
    Returns:
        List of role dicts with id, name, permissions, min_reputation, role_capacity, is_unique
    """
    results = db.execute(
        """
        SELECT id, name, permissions, min_reputation, role_capacity, is_unique
        FROM roles
        ORDER BY name
        """
    ).fetchall()
    
    roles = []
    for row in results:
        permissions_json = row[2]
        if isinstance(permissions_json, str):
            permissions_data = json.loads(permissions_json)
        else:
            permissions_data = permissions_json

        min_rep = row[3]
        if min_rep is not None:
            try:
                min_rep = int(min_rep)
            except (TypeError, ValueError):
                # If the DB contains unexpected types, treat as unset rather than crashing.
                min_rep = None
        
        roles.append({
            "id": row[0],
            "name": row[1],
            "permissions": permissions_data,
            "min_reputation": min_rep,
            "role_capacity": row[4],
            "is_unique": row[5],
        })
    
    return roles


def check_reputation_requirement(db, agent_id: str, role_name: str) -> bool:
    """
    Check if agent meets reputation requirement for role.
    
    Args:
        db: Database connection
        agent_id: Agent UUID
        role_name: Role name
    
    Returns:
        True if agent's reputation >= role's min_reputation
    """
    # Get agent's reputation
    agent_result = db.execute(
        "SELECT reputation FROM agents WHERE id = :agent_id",
        {"agent_id": agent_id}
    ).fetchone()
    
    if not agent_result:
        return False
    
    agent_reputation = agent_result[0]
    
    # Get role's min_reputation
    role_result = db.execute(
        "SELECT min_reputation FROM roles WHERE name = :role_name",
        {"role_name": role_name}
    ).fetchone()
    
    if not role_result:
        return False
    
    min_reputation = role_result[0]
    
    return agent_reputation >= min_reputation
