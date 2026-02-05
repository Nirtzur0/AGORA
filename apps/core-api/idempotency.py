"""
Idempotency key support for AGORA Core API.

Prevents duplicate processing of agent write requests.
Aligned to the idempotency_keys schema (result_type/result_id, expires_at).
"""

from fastapi import Header, Depends
from typing import Optional, Any, Dict
import hashlib
import json
from datetime import datetime, timedelta, timezone
import os

from database import get_db_session

IDEMPOTENCY_TTL_HOURS = int(os.getenv("IDEMPOTENCY_TTL_HOURS", "24"))


def compute_payload_hash(payload: Any) -> str:
    """
    Compute deterministic hash of request payload.
    
    Note: schema does not store payload hashes. This is retained for
    potential future use and tests.
    """
    json_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(json_str.encode()).hexdigest()


async def check_idempotency(
    idempotency_key: Optional[str],
    agent_id: str,
    request_name: str,
    db,
    workspace_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Check if request with idempotency key was already processed.
    
    If workspace_id is None, search across all workspaces for this agent/key.
    This enables workspace creation idempotency before a workspace ID exists.
    """
    if not idempotency_key:
        return None
    
    if workspace_id:
        result = db.execute(
            """
            SELECT id, workspace_id, result_type, result_id, created_at, expires_at
            FROM idempotency_keys
            WHERE workspace_id = :workspace_id
              AND agent_id = :agent_id
              AND request_name = :request_name
              AND idempotency_key = :idempotency_key
            """,
            {
                "workspace_id": workspace_id,
                "agent_id": agent_id,
                "request_name": request_name,
                "idempotency_key": idempotency_key,
            }
        ).fetchone()
    else:
        result = db.execute(
            """
            SELECT id, workspace_id, result_type, result_id, created_at, expires_at
            FROM idempotency_keys
            WHERE agent_id = :agent_id
              AND request_name = :request_name
              AND idempotency_key = :idempotency_key
            ORDER BY created_at DESC
            LIMIT 1
            """,
            {
                "agent_id": agent_id,
                "request_name": request_name,
                "idempotency_key": idempotency_key,
            }
        ).fetchone()
    
    if not result:
        return None
    
    record_id, ws_id, result_type, result_id, created_at, expires_at = result
    
    # Drop expired idempotency keys
    now = datetime.now(timezone.utc)
    if expires_at and expires_at < now:
        db.execute(
            "DELETE FROM idempotency_keys WHERE id = :id",
            {"id": str(record_id)}
        )
        return None
    
    return {
        "id": str(record_id),
        "workspace_id": str(ws_id),
        "result_type": result_type,
        "result_id": str(result_id),
        "created_at": created_at,
        "expires_at": expires_at,
    }


async def store_idempotency_result(
    idempotency_key: str,
    workspace_id: str,
    agent_id: str,
    request_name: str,
    result_type: str,
    result_id: str,
    db
):
    """
    Store idempotency key and result for future deduplication.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(hours=IDEMPOTENCY_TTL_HOURS)
    
    db.execute(
        """
        INSERT INTO idempotency_keys (
            workspace_id, agent_id, request_name, idempotency_key,
            result_type, result_id, expires_at
        )
        VALUES (:workspace_id, :agent_id, :request_name, :idempotency_key,
                :result_type, :result_id, :expires_at)
        ON CONFLICT (workspace_id, agent_id, request_name, idempotency_key)
        DO NOTHING
        """,
        {
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "request_name": request_name,
            "idempotency_key": idempotency_key,
            "result_type": result_type,
            "result_id": result_id,
            "expires_at": expires_at,
        }
    )
    db.commit()


class IdempotencyChecker:
    """
    Dependency for idempotent write endpoints (schema-aligned).
    """
    
    def __init__(self, request_name: str):
        self.request_name = request_name
        self.idempotency_key: Optional[str] = None
    
    async def __call__(
        self,
        idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
    ):
        self.idempotency_key = idempotency_key
        return self
    
    async def check(
        self,
        agent,
        db,
        workspace_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if not self.idempotency_key:
            return None
        
        return await check_idempotency(
            self.idempotency_key,
            agent.agent_id,
            self.request_name,
            db,
            workspace_id=workspace_id
        )
    
    async def store(
        self,
        result_type: str,
        result_id: str,
        agent,
        db,
        workspace_id: Optional[str] = None
    ):
        if not self.idempotency_key or not workspace_id:
            return
        
        await store_idempotency_result(
            self.idempotency_key,
            workspace_id,
            agent.agent_id,
            self.request_name,
            result_type,
            result_id,
            db
        )
