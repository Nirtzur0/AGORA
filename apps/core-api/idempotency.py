"""
Idempotency key support for AGORA Core API.

Prevents duplicate processing of agent write requests.
"""

from fastapi import Header, HTTPException, Depends
from typing import Optional, Any, Dict
import hashlib
import json
from datetime import datetime

from database import get_db_session


def compute_payload_hash(payload: Any) -> str:
    """
    Compute deterministic hash of request payload.
    
    Args:
        payload: Request body (dict, list, or primitive)
    
    Returns:
        SHA256 hex digest
    """
    # Convert to canonical JSON string (sorted keys)
    json_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(json_str.encode()).hexdigest()


async def check_idempotency(
    idempotency_key: Optional[str],
    workspace_id: str,
    agent_id: str,
    request_name: str,
    payload_hash: str,
    db
) -> Optional[Dict[str, Any]]:
    """
    Check if request with idempotency key was already processed.
    
    Args:
        idempotency_key: Client-provided idempotency key
        workspace_id: Workspace scope
        agent_id: Agent making request
        request_name: Endpoint/operation name
        payload_hash: Hash of request payload
        db: Database connection
    
    Returns:
        Previous response if key exists, None otherwise
    
    Raises:
        HTTPException 409: If key exists with different payload
    """
    if not idempotency_key:
        return None
    
    # Check for existing key
    result = db.execute(
        """
        SELECT response_data, payload_hash, created_at
        FROM idempotency_keys
        WHERE workspace_id = %s 
          AND agent_id = %s 
          AND request_name = %s 
          AND idempotency_key = %s
        """,
        (workspace_id, agent_id, request_name, idempotency_key)
    ).fetchone()
    
    if result:
        stored_response, stored_hash, created_at = result
        
        # Check if payload matches
        if stored_hash != payload_hash:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "IDEMPOTENCY_KEY_CONFLICT",
                    "message": f"Idempotency key '{idempotency_key}' was already used with different payload",
                    "first_used_at": created_at.isoformat()
                }
            )
        
        # Return stored response
        return stored_response
    
    return None


async def store_idempotency_result(
    idempotency_key: str,
    workspace_id: str,
    agent_id: str,
    request_name: str,
    payload_hash: str,
    response_data: Dict[str, Any],
    db
):
    """
    Store idempotency key and response for future deduplication.
    
    Args:
        idempotency_key: Client-provided idempotency key
        workspace_id: Workspace scope
        agent_id: Agent making request
        request_name: Endpoint/operation name
        payload_hash: Hash of request payload
        response_data: Response to store
        db: Database connection
    """
    db.execute(
        """
        INSERT INTO idempotency_keys (
            workspace_id, agent_id, request_name, idempotency_key,
            payload_hash, response_data
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (workspace_id, agent_id, request_name, idempotency_key) 
        DO NOTHING
        """,
        (workspace_id, agent_id, request_name, idempotency_key, 
         payload_hash, json.dumps(response_data))
    )
    db.commit()


class IdempotencyChecker:
    """
    Dependency for idempotent write endpoints.
    
    Usage:
        @router.post("/claims")
        async def create_claim(
            request: ClaimRequest,
            idempotency: IdempotencyChecker = Depends(IdempotencyChecker("create_claim")),
            agent: AgentContext = Depends(get_agent_context),
            db = Depends(get_db_session)
        ):
            # Check for duplicate
            cached = await idempotency.check(request, agent, db)
            if cached:
                return cached
            
            # Process request
            result = ...
            
            # Store result
            await idempotency.store(result, agent, db)
            return result
    """
    
    def __init__(self, request_name: str):
        self.request_name = request_name
        self.idempotency_key: Optional[str] = None
        self.payload_hash: Optional[str] = None
    
    async def __call__(
        self,
        idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
    ):
        self.idempotency_key = idempotency_key
        return self
    
    async def check(
        self,
        payload: Any,
        agent,
        db,
        workspace_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Check if request was already processed.
        
        Returns cached response if key exists, None otherwise.
        """
        if not self.idempotency_key:
            return None
        
        # Compute payload hash
        self.payload_hash = compute_payload_hash(
            payload.dict() if hasattr(payload, 'dict') else payload
        )
        
        # Use workspace_id from agent context if not provided
        ws_id = workspace_id or getattr(agent, 'workspace_id', None)
        if not ws_id:
            # If no workspace context, skip idempotency check
            return None
        
        return await check_idempotency(
            self.idempotency_key,
            ws_id,
            agent.agent_id,
            self.request_name,
            self.payload_hash,
            db
        )
    
    async def store(
        self,
        response_data: Dict[str, Any],
        agent,
        db,
        workspace_id: Optional[str] = None
    ):
        """
        Store response for future deduplication.
        """
        if not self.idempotency_key:
            return
        
        # Use workspace_id from agent context if not provided
        ws_id = workspace_id or getattr(agent, 'workspace_id', None)
        if not ws_id:
            return
        
        await store_idempotency_result(
            self.idempotency_key,
            ws_id,
            agent.agent_id,
            self.request_name,
            self.payload_hash,
            response_data,
            db
        )