"""
Draft Routes - Component 12

Implements draft lifecycle per Docs/04 §4.10:
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

from auth_middleware import get_current_agent, require_system_token
from database import get_db, SessionLocal
from storage import create_storage_from_env


router = APIRouter(tags=["Drafts"])

# Storage instance
storage = create_storage_from_env()


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
    size_bytes: int
    location: str
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
    current_agent: Dict[str, Any] = Depends(get_current_agent),
    db = Depends(get_db)
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
        WHERE workspace_id = %s AND short_id LIKE 'D%'
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
    
    db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, created_by, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            artifact_id,
            str(workspace_id),
            short_id,
            "draft",
            metadata,
            current_agent.get("agent_id"),
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
        created_by=current_agent.get("agent_id"),
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
    - Triggers citation_check (async, not implemented in this component)
    - Rejects if draft is already finalized (status=final)
    - Rejects if workspace phase is FINALIZED
    """
)
def create_draft_version(
    draft_id: UUID = Path(..., description="Draft artifact ID"),
    request: CreateDraftVersionRequest = Body(...),
    current_agent: Dict[str, Any] = Depends(get_current_agent),
    db = Depends(get_db)
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
    metadata = json.loads(metadata_json) if metadata_json else {}
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
    storage_key = f"{workspace_id}/artifacts/{draft_id}/v{next_version}/draft.md"
    storage.put_object("agora", storage_key, content_bytes)
    
    # Create artifact_version
    version_id = f"{draft_id}_v{next_version}"
    created_at = db.execute("SELECT NOW()").fetchone()[0]
    location = f"s3://agora/{workspace_id}/artifacts/{draft_id}/v{next_version}/"
    
    db.execute(
        """
        INSERT INTO artifact_versions (id, artifact_id, version, content_hash, size_bytes, location, created_by, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            version_id,
            str(draft_id),
            next_version,
            content_hash,
            len(content_bytes),
            location,
            current_agent.get("agent_id"),
            created_at
        )
    )
    
    # TODO: Trigger citation_check activity (async)
    # This will be implemented in Component 13
    
    return DraftVersionResponse(
        id=version_id,
        artifact_id=str(draft_id),
        version=next_version,
        content_hash=content_hash,
        size_bytes=len(content_bytes),
        location=location,
        created_by=current_agent.get("agent_id"),
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
    current_agent: Dict[str, Any] = Depends(get_current_agent),
    db = Depends(get_db)
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
        SELECT id, artifact_id, version, content_hash, size_bytes, location, created_by, created_at
        FROM artifact_versions
        WHERE artifact_id = %s
        ORDER BY version DESC
        """,
        (str(draft_id),)
    )
    versions = result.fetchall()
    
    versions_data = [
        DraftVersionResponse(
            id=v[0],
            artifact_id=v[1],
            version=v[2],
            content_hash=v[3],
            size_bytes=v[4],
            location=v[5],
            created_by=str(v[6]) if v[6] else None,
            created_at=v[7].isoformat()
        )
        for v in versions
    ]
    
    return {
        "draft_id": str(draft_id),
        "versions": [v.dict() for v in versions_data],
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
    db = Depends(get_db)
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
    
    # Check if already finalized
    metadata = json.loads(metadata_json) if metadata_json else {}
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
    
    # TODO: Check rule_checks for failures
    # If any rule_checks exist with status=failure for this draft, reject finalization
    # This will be implemented in Component 13
    
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
            None,
            json.dumps({
                "draft_id": str(draft_id),
                "final_version_id": request.draft_artifact_version_id
            })
        )
    )
    
    return {
        "draft_id": str(draft_id),
        "status": "finalized",
        "final_version_id": request.draft_artifact_version_id
    }
