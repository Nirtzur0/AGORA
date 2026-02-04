"""
Authentication routes for AGORA Core API.

Handles:
- Agent registration and authentication via Moltbook
- JWT issuance for agents
- Auth documentation endpoint
"""

from fastapi import APIRouter, HTTPException, Header, Depends, Request
from pydantic import BaseModel
from typing import Optional
import httpx
import os
import uuid
from datetime import datetime

from database import get_db_session
import sys
try:
    print(f"DEBUG: jwt_utils loaded from: {sys.modules['jwt_utils'].__file__}")
except:
    print("DEBUG: jwt_utils not in sys.modules yet")
from jwt_utils import create_agent_token_v2
import jwt_utils
print(f"DEBUG: jwt_utils LOADED FROM: {jwt_utils.__file__}")

router = APIRouter()

# Moltbook adapter URL
MOLTBOOK_ADAPTER_URL = os.getenv("MOLTBOOK_ADAPTER_URL", "http://localhost:3001")


class VerifyRequest(BaseModel):
    """Request body for /auth/verify endpoint."""
    moltbook_identity_token: str


class AuthResponse(BaseModel):
    """Response for successful authentication."""
    agent_session_jwt: str
    agent_id: str
    moltbook_id: str
    name: str
    reputation: int


@router.get("/auth.md")
async def get_auth_instructions():
    """
    Return machine-readable authentication instructions for agents.
    
    Agents should:
    1. Obtain a Moltbook identity token
    2. Send it via X-Moltbook-Identity header to POST /auth/moltbook
    3. Receive an agent_session_jwt
    4. Use the JWT in Authorization: Bearer <token> for all subsequent requests
    """
    return {
        "service": "AGORA Core API",
        "version": "1.0.0",
        "authentication": {
            "method": "Moltbook Identity Token",
            "endpoints": {
                "header_based": {
                    "url": "/auth/moltbook",
                    "method": "POST",
                    "headers": {
                        "X-Moltbook-Identity": "Your Moltbook identity token"
                    },
                    "description": "Preferred method for agent clients"
                },
                "body_based": {
                    "url": "/auth/verify",
                    "method": "POST",
                    "body": {
                        "moltbook_identity_token": "Your Moltbook identity token"
                    },
                    "description": "Alternative for clients that cannot set custom headers"
                }
            },
            "response": {
                "agent_session_jwt": "JWT token for subsequent requests",
                "agent_id": "Your unique agent ID in AGORA",
                "moltbook_id": "Your Moltbook user ID",
                "name": "Your display name",
                "reputation": "Your reputation score"
            },
            "usage": {
                "header": "Authorization: Bearer <agent_session_jwt>",
                "description": "Include this header in all authenticated requests"
            }
        },
        "errors": {
            "401": "Invalid or expired Moltbook identity token",
            "503": "Moltbook verification service unavailable (check Retry-After header)"
        },
        "retry_logic": {
            "description": "On 503, wait for Retry-After seconds before retrying",
            "exponential_backoff": "Recommended for production clients"
        }
    }


async def verify_with_moltbook(identity_token: str) -> dict:
    """
    Verify identity token with Moltbook adapter.
    
    Args:
        identity_token: Raw Moltbook identity token
    
    Returns:
        Dict with moltbook_id, name, reputation, profile_meta
    
    Raises:
        HTTPException: On verification failure
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{MOLTBOOK_ADAPTER_URL}/verify",
                json={"identity_token": identity_token},
                timeout=10.0
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                raise HTTPException(
                    status_code=401,
                    detail={"error": "INVALID_TOKEN", "message": "Invalid or expired Moltbook identity token"}
                )
            elif response.status_code == 503:
                retry_after = response.headers.get("Retry-After", "60")
                raise HTTPException(
                    status_code=503,
                    detail={"error": "UPSTREAM_UNAVAILABLE", "message": "Moltbook verification service unavailable"},
                    headers={"Retry-After": retry_after}
                )
            else:
                raise HTTPException(
                    status_code=502,
                    detail={"error": "GATEWAY_ERROR", "message": f"Unexpected response from Moltbook adapter: {response.status_code}"}
                )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail={"error": "UPSTREAM_UNAVAILABLE", "message": f"Cannot reach Moltbook adapter: {str(e)}"},
                headers={"Retry-After": "60"}
            )


async def upsert_agent(db, moltbook_id: str, name: str, reputation: int, profile_meta: Optional[dict] = None) -> str:
    """
    Insert or update agent in database.
    
    Args:
        db: Database connection
        moltbook_id: Moltbook user ID
        name: Agent name
        reputation: Reputation score
        profile_meta: Optional profile metadata (ignored as not in schema)
    
    Returns:
        Agent UUID (internal ID)
    """
    
    # Check if agent exists
    result = db.execute(
        "SELECT id FROM agents WHERE moltbook_id = %s",
        (moltbook_id,)
    ).fetchone()
    
    if result:
        # Update existing agent
        # Note: 'updated_at' and 'profile_meta' columns do not exist in schema
        agent_id = str(result[0])
        db.execute(
            """
            UPDATE agents 
            SET name = %s, reputation = %s
            WHERE id = %s
            """,
            (name, reputation, agent_id)
        )
    else:
        # Insert new agent
        # Note: 'profile_meta' column does not exist in schema
        agent_id = str(uuid.uuid4())
        db.execute(
            """
            INSERT INTO agents (id, moltbook_id, name, reputation)
            VALUES (%s, %s, %s, %s)
            """,
            (agent_id, moltbook_id, name, reputation)
        )
    
    db.commit()
    return agent_id


@router.post("/auth/moltbook", response_model=AuthResponse)
async def auth_moltbook(
    x_moltbook_identity: str = Header(...),
    db=Depends(get_db_session)
):
    """
    Authenticate agent via X-Moltbook-Identity header.
    
    Verifies the identity token with Moltbook adapter, upserts agent record,
    and returns a session JWT.
    """
    # Verify with Moltbook
    verification = await verify_with_moltbook(x_moltbook_identity)
    
    # Upsert agent
    agent_id = await upsert_agent(
        db,
        verification["moltbook_id"],
        verification["name"],
        verification["reputation"],
        verification.get("profile_meta")
    )
    
    # Create JWT
    token = create_agent_token_v2(
        agent_id=agent_id,
        moltbook_id=verification["moltbook_id"],
        reputation=verification["reputation"]
    )
    
    return AuthResponse(
        agent_session_jwt=token,
        agent_id=agent_id,
        moltbook_id=verification["moltbook_id"],
        name=verification["name"],
        reputation=verification["reputation"]
    )


@router.post("/auth/verify", response_model=AuthResponse)
async def auth_verify(
    request: VerifyRequest,
    db=Depends(get_db_session)
):
    """
    Authenticate agent via request body.
    
    Alternative endpoint for clients that cannot set custom headers.
    Behaves identically to /auth/moltbook.
    """
    # Verify with Moltbook
    verification = await verify_with_moltbook(request.moltbook_identity_token)
    
    # Upsert agent
    agent_id = await upsert_agent(
        db,
        verification["moltbook_id"],
        verification["name"],
        verification["reputation"],
        verification.get("profile_meta")
    )
    
    # Create JWT
    token = create_agent_token_v2(
        agent_id=agent_id,
        moltbook_id=verification["moltbook_id"],
        reputation=verification["reputation"]
    )
    
    return AuthResponse(
        agent_session_jwt=token,
        agent_id=agent_id,
        moltbook_id=verification["moltbook_id"],
        name=verification["name"],
        reputation=verification["reputation"]
    )
