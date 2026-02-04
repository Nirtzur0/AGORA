"""
JWT utilities for AGORA authentication.

Supports two token types:
- Agent tokens: Issued to research agents authenticated via Moltbook
- System tokens: Issued to internal services (orchestrator, worker)
"""

import os
import jwt
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from enum import Enum


class TokenType(str, Enum):
    AGENT = "agent"
    SYSTEM = "system"


class TokenAudience(str, Enum):
    AGENT_API = "agora:agent-api"
    SYSTEM_API = "agora:system-api"


# Separate signing keys for agent and system tokens
AGENT_JWT_SECRET = os.getenv("AGENT_JWT_SECRET", "agent-secret-change-in-production")
SYSTEM_JWT_SECRET = os.getenv("SYSTEM_JWT_SECRET", "system-secret-change-in-production")

# Token expiration
AGENT_TOKEN_EXPIRY_HOURS = int(os.getenv("AGENT_TOKEN_EXPIRY_HOURS", "24"))
SYSTEM_TOKEN_EXPIRY_HOURS = int(os.getenv("SYSTEM_TOKEN_EXPIRY_HOURS", "168"))  # 7 days


def create_agent_token_v2(
    agent_id: str,
    moltbook_id: str,
    reputation: int,
    workspace_id: Optional[str] = None,
) -> str:
    """
    Create a JWT for an authenticated agent.
    
    Args:
        agent_id: Internal agent UUID
        moltbook_id: Moltbook user ID
        reputation: Agent's reputation score
        workspace_id: Optional workspace scope
    
    Returns:
        Signed JWT string
    """
    now = datetime.utcnow()
    exp = now + timedelta(hours=AGENT_TOKEN_EXPIRY_HOURS)
    
    payload = {
        "sub": str(agent_id),
        "type": TokenType.AGENT,
        "aud": TokenAudience.AGENT_API,
        "iss": "agora-core-api",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "moltbook_id": moltbook_id,
        "reputation": reputation,
    }
    
    if workspace_id:
        payload["workspace_id"] = workspace_id
    
    print(f"DEBUG: creating agent token. AgentID type: {type(agent_id)}")
    print(f"DEBUG: payload: {payload}")
    for k, v in payload.items():
        print(f"DEBUG: key={k} value={v} type={type(v)}")
        if "uuid" in str(type(v)).lower():
            print(f"DEBUG: FOUND UUID IN PAYLOAD AT KEY {k}")
    
    return jwt.encode(payload, AGENT_JWT_SECRET, algorithm="HS256")


def create_agent_token(
    agent_id: str,
    moltbook_id: str,
    reputation: int = 0,
    workspace_id: Optional[str] = None,
) -> str:
    """
    Backwards-compatible wrapper for agent token creation.
    
    Tests and callers may omit reputation; default to 0.
    """
    return create_agent_token_v2(
        agent_id=agent_id,
        moltbook_id=moltbook_id,
        reputation=reputation,
        workspace_id=workspace_id,
    )


def create_system_token(service_name: str) -> str:
    """
    Create a JWT for an internal system service.
    
    Args:
        service_name: Service identifier (e.g., "orchestrator", "worker")
    
    Returns:
        Signed JWT string
    """
    now = datetime.utcnow()
    exp = now + timedelta(hours=SYSTEM_TOKEN_EXPIRY_HOURS)
    
    payload = {
        "sub": service_name,
        "type": TokenType.SYSTEM,
        "aud": TokenAudience.SYSTEM_API,
        "iss": "agora-core-api",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    
    return jwt.encode(payload, SYSTEM_JWT_SECRET, algorithm="HS256")


def verify_agent_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode an agent JWT.
    
    Args:
        token: JWT string
    
    Returns:
        Decoded payload
    
    Raises:
        jwt.ExpiredSignatureError: Token expired
        jwt.InvalidTokenError: Invalid token
        ValueError: Wrong token type or audience
    """
    try:
        payload = jwt.decode(
            token,
            AGENT_JWT_SECRET,
            algorithms=["HS256"],
            audience=TokenAudience.AGENT_API,
        )
        
        if payload.get("type") != TokenType.AGENT:
            raise ValueError(f"Invalid token type: {payload.get('type')}")
        
        return payload
    except jwt.ExpiredSignatureError:
        raise jwt.ExpiredSignatureError("Agent token has expired")
    except jwt.InvalidTokenError as e:
        raise jwt.InvalidTokenError(f"Invalid agent token: {str(e)}")


def verify_system_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a system JWT.
    
    Args:
        token: JWT string
    
    Returns:
        Decoded payload
    
    Raises:
        jwt.ExpiredSignatureError: Token expired
        jwt.InvalidTokenError: Invalid token
        ValueError: Wrong token type or audience
    """
    try:
        payload = jwt.decode(
            token,
            SYSTEM_JWT_SECRET,
            algorithms=["HS256"],
            audience=TokenAudience.SYSTEM_API,
        )
        
        if payload.get("type") != TokenType.SYSTEM:
            raise ValueError(f"Invalid token type: {payload.get('type')}")
        
        return payload
    except jwt.ExpiredSignatureError:
        raise jwt.ExpiredSignatureError("System token has expired")
    except jwt.InvalidTokenError as e:
        raise jwt.InvalidTokenError(f"Invalid system token: {str(e)}")


def decode_token_unverified(token: str) -> Dict[str, Any]:
    """
    Decode a token without verification (for inspection/debugging only).
    
    Args:
        token: JWT string
    
    Returns:
        Decoded payload
    """
    return jwt.decode(token, options={"verify_signature": False})
