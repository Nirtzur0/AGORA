"""
Draft Routes - Component 12

Implements draft lifecycle per `Docs/manifest/04_api_contracts.md`:
- POST /workspaces/{id}/drafts: Create draft artifact
- POST /drafts/{id}/versions: Create draft version (Markdown + content_hash)
- GET /drafts/{id}/versions: List draft versions
- POST /drafts/{id}/finalize: Finalize draft (SYSTEM-ONLY)

Drafts are first-class artifacts (type=draft) with immutable versions.
Each version has a content_hash and stores Markdown content.
"""
from fastapi import APIRouter, Depends, HTTPException, Path, Body
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from uuid import UUID
import uuid
import hashlib
import json
from pathlib import Path as FilePath
import sys

from auth_middleware import get_current_agent, require_system_token, AgentContext
from database import get_db_session
from storage import create_storage_from_env


router = APIRouter(tags=["Drafts"])

# Storage instance
storage = create_storage_from_env()


def _agent_id(current_agent: AgentContext) -> str:
    """Support both AgentContext objects and dicts used in tests."""
    value = getattr(current_agent, "agent_id", None) or current_agent["agent_id"]
    return str(value)


def _ensure_worker_path() -> None:
    """Allow Core API routes to reuse orchestrator gate evaluation logic."""
    worker_path = FilePath(__file__).resolve().parents[2] / "apps" / "worker"
    worker_path_str = str(worker_path)
    if worker_path_str not in sys.path:
        sys.path.insert(0, worker_path_str)


def _evaluate_finalization_gate(
    db,
    workspace_id: str,
    draft_artifact_id: str,
    draft_artifact_version_id: str,
) -> Dict[str, Any]:
    """Evaluate finalization gate from persisted state (single source of truth)."""
    _ensure_worker_path()
    from gates import GateEvaluationActivity, GateEvaluator

    snapshot = GateEvaluationActivity(db).gather_finalization_gate_snapshot(
        workspace_id=workspace_id,
        draft_artifact_id=draft_artifact_id,
        draft_artifact_version_id=draft_artifact_version_id,
    )
    return GateEvaluator.evaluate_finalization_gate(snapshot)


def _json_safe(value: Any) -> Any:
    """Convert nested structures into JSON-serializable values."""
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    return value


def _persist_finalization_gate_result(
    db,
    workspace_id: str,
    draft_artifact_id: str,
    draft_artifact_version_id: str,
    gate_response: Dict[str, Any],
) -> None:
    """
    Persist gate outcome so failures are never silent.

    We record both:
    - rule_checks row (machine-evaluable)
    - logs row (human-auditable timeline)
    """
    safe_gate_response = _json_safe(gate_response)
    normalized_status = str(safe_gate_response.get("status", "FAIL")).lower()

    db.execute(
        """
        INSERT INTO rule_checks (
            id, workspace_id, target_type, target_id, rule_name, status, details, created_at
        )
        VALUES (
            :id, :workspace_id, :target_type, :target_id, :rule_name, :status, :details, NOW()
        )
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "target_type": "artifact_version",
            "target_id": draft_artifact_version_id,
            "rule_name": "finalization_gate",
            "status": normalized_status,
            "details": {
                "gate_name": safe_gate_response.get("gate_name"),
                "status": safe_gate_response.get("status"),
                "reasons": safe_gate_response.get("reasons", []),
                "required_actions": safe_gate_response.get("required_actions", []),
                "snapshot": safe_gate_response.get("snapshot", {}),
                "draft_artifact_id": draft_artifact_id,
            },
        },
    )

    db.execute(
        """
        INSERT INTO logs (id, workspace_id, agent_id, action, payload, created_at)
        VALUES (:id, :workspace_id, NULL, :action, :payload, NOW())
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "action": "draft.finalization_gate_evaluated",
            "payload": {
                "draft_artifact_id": draft_artifact_id,
                "draft_artifact_version_id": draft_artifact_version_id,
                "status": safe_gate_response.get("status"),
                "reasons": safe_gate_response.get("reasons", []),
            },
        },
    )


# Request/Response Models

class CreateDraftRequest(BaseModel):
    """Request to create a draft artifact."""
    title: str = Field(..., description="Draft title")


class CreateDraftVersionRequest(BaseModel):
    """Request to create a draft version."""
    content: str = Field(..., description="Markdown content")


class FinalizeDraftRequest(BaseModel):
    """Request to finalize a draft (SYSTEM-ONLY)."""
    draft_artifact_version_id: str = Field(..., description="Artifact version ID to finalize")


class DraftResponse(BaseModel):
    """Draft artifact response."""
    id: str
    workspace_id: str
    short_id: str
    title: str
    status: Optional[str] = None
    final_version_id: Optional[str] = None
    created_by: Optional[str]
    created_at: str


class DraftVersionResponse(BaseModel):
    """Draft version response."""
    id: str
    artifact_id: str
    version: int
    content_hash: str
    storage_uri: str
    created_by: Optional[str]
    created_at: str


# Endpoints

@router.post(
    "/workspaces/{workspace_id}/drafts",
    status_code=201,
    summary="Create a draft artifact",
    description="""
    Create a new draft artifact per §4.10.
    
    Creates an artifact with type=draft and metadata.title set.
    Content is added via POST /drafts/{id}/versions.
    """
)
def create_draft(
    workspace_id: UUID = Path(..., description="Workspace ID"),
    request: CreateDraftRequest = Body(...),
    current_agent: AgentContext = Depends(get_current_agent),
    db = Depends(get_db_session)
) -> DraftResponse:
    """
    Create a new draft artifact in a workspace.
    
    Drafts are type=draft artifacts with metadata containing the title.
    """
    # Verify workspace exists
    result = db.execute(
        "SELECT id FROM workspaces WHERE id = %s",
        (str(workspace_id),)
    )
    workspace = result.fetchone()
    if not workspace:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
    
    # Allocate short_id (D1, D2, ...)
    result = db.execute(
        """
        SELECT short_id FROM artifacts 
        WHERE workspace_id = %s AND short_id LIKE 'D%%'
        ORDER BY short_id DESC LIMIT 1
        """,
        (str(workspace_id),)
    )
    last_draft = result.fetchone()
    
    if last_draft:
        last_num = int(last_draft[0][1:])
        short_id = f"D{last_num + 1}"
    else:
        short_id = "D1"
    
    # Create artifact
    artifact_id = str(uuid.uuid4())
    created_at = db.execute("SELECT NOW()").fetchone()[0]
    
    metadata = json.dumps({"title": request.title})
    
    storage_uri = f"s3://agora/{workspace_id}/artifacts/{artifact_id}/"
    db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            artifact_id,
            str(workspace_id),
            short_id,
            "draft",
            metadata,
            storage_uri,
            _agent_id(current_agent),
            created_at
        )
    )
    
    return DraftResponse(
        id=artifact_id,
        workspace_id=str(workspace_id),
        short_id=short_id,
        title=request.title,
        status=None,
        final_version_id=None,
        created_by=_agent_id(current_agent),
        created_at=created_at.isoformat()
    )


@router.post(
    "/drafts/{draft_id}/versions",
    status_code=201,
    summary="Create a draft version",
    description="""
    Create a new version of a draft per §4.10.
    
    - Stores Markdown content with content_hash
    - Creates immutable artifact_version
    - Triggers citation_check immediately for the new version
    - Rejects if draft is already finalized (status=final)
    - Rejects if workspace phase is FINALIZED
    """
)
def create_draft_version(
    draft_id: UUID = Path(..., description="Draft artifact ID"),
    request: CreateDraftVersionRequest = Body(...),
    current_agent: AgentContext = Depends(get_current_agent),
    db = Depends(get_db_session)
) -> DraftVersionResponse:
    """
    Create a new version of a draft artifact.
    
    Computes content_hash and stores Markdown in MinIO.
    """
    # Verify draft exists and is a draft type
    result = db.execute(
        """
        SELECT workspace_id, type, metadata
        FROM artifacts
        WHERE id = %s
        """,
        (str(draft_id),)
    )
    artifact = result.fetchone()
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
    
    workspace_id, artifact_type, metadata_json = artifact
    
    if artifact_type != "draft":
        raise HTTPException(status_code=400, detail=f"Artifact {draft_id} is not a draft")

    # Check if draft is already finalized
    if metadata_json:
        metadata = metadata_json if isinstance(metadata_json, dict) else json.loads(metadata_json)
    else:
        metadata = {}
    if metadata.get("status") == "final":
        raise HTTPException(
            status_code=409,
            detail=f"Draft {draft_id} is already finalized"
        )
    
    # Check workspace phase
    result = db.execute(
        "SELECT phase FROM workspaces WHERE id = %s",
        (str(workspace_id),)
    )
    workspace_phase = result.fetchone()[0]
    
    if workspace_phase == "FINALIZED":
        raise HTTPException(
            status_code=409,
            detail=f"Workspace is FINALIZED; cannot create new draft versions"
        )
    
    # Get next version number
    result = db.execute(
        """
        SELECT MAX(version) FROM artifact_versions WHERE artifact_id = %s
        """,
        (str(draft_id),)
    )
    max_version = result.fetchone()[0]
    next_version = (max_version or 0) + 1
    
    # Compute content_hash
    content_bytes = request.content.encode("utf-8")
    content_hash = hashlib.sha256(content_bytes).hexdigest()
    
    # Store content in MinIO
    storage_uri = f"s3://agora/{workspace_id}/artifacts/{draft_id}/v{next_version}/draft.md"
    storage.put_object(storage_uri, content_bytes)
    
    # Create artifact_version
    version_id = str(uuid.uuid4())
    created_at = db.execute("SELECT NOW()").fetchone()[0]
    
    db.execute(
        """
        INSERT INTO artifact_versions (id, artifact_id, version, content_hash, storage_uri, created_by, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            version_id,
            str(draft_id),
            next_version,
            content_hash,
            storage_uri,
            _agent_id(current_agent),
            created_at
        )
    )
    
    # Run citation_check immediately so failures surface without waiting for finalization.
    _ensure_worker_path()
    from citation_check import citation_check_activity
    citation_check_activity(version_id, db)
    
    return DraftVersionResponse(
        id=version_id,
        artifact_id=str(draft_id),
        version=next_version,
        content_hash=content_hash,
        storage_uri=storage_uri,
        created_by=_agent_id(current_agent),
        created_at=created_at.isoformat()
    )


@router.get(
    "/drafts/{draft_id}/versions",
    summary="List draft versions",
    description="""
    Get all versions of a draft per §4.10.
    
    Returns versions in descending order (newest first).
    """
)
def list_draft_versions(
    draft_id: UUID = Path(..., description="Draft artifact ID"),
    current_agent: AgentContext = Depends(get_current_agent),
    db = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    List all versions of a draft artifact.
    """
    # Verify draft exists
    result = db.execute(
        "SELECT id, type FROM artifacts WHERE id = %s",
        (str(draft_id),)
    )
    artifact = result.fetchone()
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
    
    if artifact[1] != "draft":
        raise HTTPException(status_code=400, detail=f"Artifact {draft_id} is not a draft")
    
    # Get all versions
    result = db.execute(
        """
        SELECT id, artifact_id, version, content_hash, storage_uri, created_by, created_at
        FROM artifact_versions
        WHERE artifact_id = %s
        ORDER BY version DESC
        """,
        (str(draft_id),)
    )
    versions = result.fetchall()
    
    versions_data = [
        DraftVersionResponse(
            id=str(v[0]),
            artifact_id=str(v[1]),
            version=v[2],
            content_hash=v[3],
            storage_uri=v[4],
            created_by=str(v[5]) if v[5] else None,
            created_at=v[6].isoformat()
        )
        for v in versions
    ]
    
    return {
        "draft_id": str(draft_id),
        "versions": [v.model_dump() for v in versions_data],
        "total": len(versions_data)
    }


@router.post(
    "/drafts/{draft_id}/finalize",
    summary="Finalize a draft (SYSTEM-ONLY)",
    description="""
    Finalize a draft per §4.10 (SYSTEM-ONLY).
    
    This endpoint is invoked by the orchestrator workflow only.
    
    - Triggers citation and rule checks
    - Blocks if failures exist
    - On success: sets metadata status=final and final_version_id
    - Emits draft.finalized event
    """
)
def finalize_draft(
    draft_id: UUID = Path(..., description="Draft artifact ID"),
    request: FinalizeDraftRequest = Body(...),
    system_token: Dict[str, Any] = Depends(require_system_token),
    db = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Finalize a draft (SYSTEM-ONLY).
    
    Only the orchestrator can call this endpoint.
    """
    # Verify draft exists
    result = db.execute(
        """
        SELECT workspace_id, type, metadata
        FROM artifacts
        WHERE id = %s
        """,
        (str(draft_id),)
    )
    artifact = result.fetchone()
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")
    
    workspace_id, artifact_type, metadata_json = artifact
    
    if artifact_type != "draft":
        raise HTTPException(status_code=400, detail=f"Artifact {draft_id} is not a draft")

    workspace_row = db.execute(
        "SELECT phase FROM workspaces WHERE id = :id",
        {"id": str(workspace_id)},
    ).fetchone()
    if not workspace_row:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
    if workspace_row[0] != "FINALIZED":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot finalize draft: workspace phase is {workspace_row[0]}, must be FINALIZED",
        )
    
    # Check if already finalized
    if metadata_json:
        metadata = metadata_json if isinstance(metadata_json, dict) else json.loads(metadata_json)
    else:
        metadata = {}
    if metadata.get("status") == "final":
        raise HTTPException(
            status_code=409,
            detail=f"Draft {draft_id} is already finalized"
        )
    
    # Verify draft_artifact_version_id exists
    result = db.execute(
        "SELECT artifact_id FROM artifact_versions WHERE id = %s",
        (request.draft_artifact_version_id,)
    )
    version = result.fetchone()
    if not version or str(version[0]) != str(draft_id):
        raise HTTPException(
            status_code=400,
            detail=f"Version {request.draft_artifact_version_id} does not belong to draft {draft_id}"
        )
    
    try:
        gate_response = _evaluate_finalization_gate(
            db=db,
            workspace_id=str(workspace_id),
            draft_artifact_id=str(draft_id),
            draft_artifact_version_id=request.draft_artifact_version_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _persist_finalization_gate_result(
        db=db,
        workspace_id=str(workspace_id),
        draft_artifact_id=str(draft_id),
        draft_artifact_version_id=request.draft_artifact_version_id,
        gate_response=gate_response,
    )

    gate_status = str(gate_response.get("status", "FAIL")).upper()
    if gate_status != "PASS":
        db.commit()
        raise HTTPException(
            status_code=409,
            detail={
                "error": "FINALIZATION_GATE_BLOCKED",
                "gate_status": gate_status,
                "reasons": gate_response.get("reasons", []),
                "required_actions": gate_response.get("required_actions", []),
            },
        )
    
    # Update metadata to mark as finalized
    metadata["status"] = "final"
    metadata["final_version_id"] = request.draft_artifact_version_id
    
    db.execute(
        """
        UPDATE artifacts
        SET metadata = %s
        WHERE id = %s
        """,
        (json.dumps(metadata), str(draft_id))
    )
    
    # Emit event
    event_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO events (id, workspace_id, event_type, actor_type, actor_id, payload, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """,
        (
            event_id,
            str(workspace_id),
            "draft.finalized",
            "system",
            str(workspace_id),
            json.dumps({
                "draft_id": str(draft_id),
                "final_version_id": request.draft_artifact_version_id
            })
        )
    )

    db.execute(
        """
        INSERT INTO logs (id, workspace_id, agent_id, action, payload, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        """,
        (
            str(uuid.uuid4()),
            str(workspace_id),
            None,
            "draft.finalized",
            json.dumps({
                "draft_id": str(draft_id),
                "final_version_id": request.draft_artifact_version_id,
                "event_id": event_id,
            }),
        ),
    )

    db.commit()
    
    return {
        "draft_id": str(draft_id),
        "status": "finalized",
        "final_version_id": request.draft_artifact_version_id
    }
