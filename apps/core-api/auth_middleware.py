"""
Authentication middleware for AGORA Core API.

Provides decorators and dependencies for:
- Agent authentication (via JWT)
- System authentication (internal services)
- RBAC enforcement
"""

from fastapi import Depends, HTTPException, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any, List
import jwt as pyjwt

from jwt_utils import verify_agent_token, verify_system_token, TokenType
from database import get_db_session

# HTTP Bearer scheme for JWT tokens
bearer_scheme = HTTPBearer(auto_error=False)


class AgentContext:
    """Authenticated agent context."""
    def __init__(self, agent_id: str, moltbook_id: str, reputation: int, workspace_id: Optional[str] = None):
        self.agent_id = agent_id
        self.moltbook_id = moltbook_id
        self.reputation = reputation
        self.workspace_id = workspace_id


class SystemContext:
    """Authenticated system service context."""
    def __init__(self, service_name: str):
        self.service_name = service_name


async def get_agent_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> AgentContext:
    """
    Dependency for agent-authenticated routes.
    
    Verifies JWT and returns agent context.
    Raises 401 if token is missing or invalid.
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail={"error": "MISSING_TOKEN", "message": "Authorization header required"},
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    try:
        payload = verify_agent_token(credentials.credentials)
        
        return AgentContext(
            agent_id=payload["sub"],
            moltbook_id=payload["moltbook_id"],
            reputation=payload["reputation"],
            workspace_id=payload.get("workspace_id")
        )
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail={"error": "EXPIRED_TOKEN", "message": "Token has expired"},
            headers={"WWW-Authenticate": "Bearer"}
        )
    except (pyjwt.InvalidTokenError, ValueError) as e:
        raise HTTPException(
            status_code=401,
            detail={"error": "INVALID_TOKEN", "message": str(e)},
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_system_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> SystemContext:
    """
    Dependency for system-only routes.
    
    Verifies system JWT and returns service context.
    Raises 401 if token is missing or invalid.
    Raises 403 if agent token is used on system-only route.
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail={"error": "MISSING_TOKEN", "message": "Authorization header required"},
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    try:
        payload = verify_system_token(credentials.credentials)
        
        return SystemContext(service_name=payload["sub"])
    except ValueError as e:
        # Wrong token type (agent token on system route)
        raise HTTPException(
            status_code=403,
            detail={"error": "FORBIDDEN", "message": "Agent tokens cannot access system-only endpoints"}
        )
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail={"error": "EXPIRED_TOKEN", "message": "Token has expired"},
            headers={"WWW-Authenticate": "Bearer"}
        )
    except pyjwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=401,
            detail={"error": "INVALID_TOKEN", "message": str(e)},
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_optional_agent_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> Optional[AgentContext]:
    """
    Dependency for routes that optionally use agent context.
    
    Returns AgentContext if valid token present, None otherwise.
    Does not raise errors for missing/invalid tokens.
    """
    if not credentials:
        return None
    
    try:
        payload = verify_agent_token(credentials.credentials)
        return AgentContext(
            agent_id=payload["sub"],
            moltbook_id=payload["moltbook_id"],
            reputation=payload["reputation"],
            workspace_id=payload.get("workspace_id")
        )
    except (pyjwt.InvalidTokenError, ValueError):
        return None


def require_permissions(required_permissions: List[str]):
    """
    Decorator factory for requiring specific permissions.
    
    Usage:
        @router.get("/protected")
        async def protected_route(
            agent: AgentContext = Depends(require_permissions(["workspace.read"]))
        ):
            ...
    
    Args:
        required_permissions: List of permission keys (OR logic - any one suffices)
    
    Raises:
        HTTPException 403: Agent lacks required permissions
    """
    from rbac import require_any_permission, get_agent_role
    
    async def permission_checker(
        agent: AgentContext = Depends(get_agent_context),
        db = Depends(get_db_session),
        workspace_id: Optional[str] = None
    ) -> AgentContext:
        # Use workspace_id from agent context if not provided
        ws_id = workspace_id or agent.workspace_id
        
        if not ws_id:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "NO_WORKSPACE_CONTEXT",
                    "message": "This endpoint requires workspace context"
                }
            )
        
        # Get agent role for error message
        role_info = get_agent_role(db, agent.agent_id, ws_id)
        role_name = role_info["role_name"] if role_info else None
        
        # Check permissions
        require_any_permission(
            db,
            agent.agent_id,
            ws_id,
            required_permissions,
            agent_role=role_name
        )
        
        return agent
    
    return permission_checker


def require_role(required_role: str):
    """
    Decorator factory for requiring specific role.
    
    Usage:
        @router.post("/claim")
        async def create_claim(
            agent: AgentContext = Depends(require_role("Literature Analyst"))
        ):
            ...
    
    Args:
        required_role: Required role name (e.g., "Maintainer")
    
    Raises:
        HTTPException 403: Agent does not have required role
    """
    from rbac import get_agent_role
    
    async def role_checker(
        agent: AgentContext = Depends(get_agent_context),
        db = Depends(get_db_session),
        workspace_id: Optional[str] = None
    ) -> AgentContext:
        # Use workspace_id from agent context if not provided
        ws_id = workspace_id or agent.workspace_id
        
        if not ws_id:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "NO_WORKSPACE_CONTEXT",
                    "message": "This endpoint requires workspace context"
                }
            )
        
        role_info = get_agent_role(db, agent.agent_id, ws_id)
        
        if not role_info or role_info["role_name"] != required_role:
            current_role = role_info["role_name"] if role_info else "none"
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "ROLE_REQUIRED",
                    "message": f"This endpoint requires role '{required_role}'",
                    "required_role": required_role,
                    "current_role": current_role
                }
            )
        
        return agent
    
    return role_checker


async def require_system_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> SystemContext:
    """
    Dependency for system-only routes (alias for get_system_context).
    
    Verifies system JWT and returns service context.
    Raises 401 if token is missing or invalid.
    Raises 403 if agent token is used on system-only route.
    """
    return await get_system_context(credentials)


# Aliases for backward compatibility
get_current_agent = get_agent_context
get_current_system = get_system_context
require_agent_token = get_agent_context