"""
Artifact routes for AGORA Core API.

Implements artifact lifecycle and version management per spec §4.4 and §7:
- POST /workspaces/{id}/artifacts: Create artifact metadata record
- POST /artifacts/{id}/versions: Upload new version (immutable)
- GET /workspaces/{id}/artifacts: List artifacts
- GET /artifacts/{id}: Get artifact metadata
- GET /artifacts/{id}/versions: List versions
- GET /artifact-versions/{id}/content: Get exact version content (for citations)
- GET /artifacts/{id}/content: Get latest version content (convenience only)

Authority model:
- Artifacts are created by agents (RBAC enforced)
- Versions are immutable (no overwrites)
- short_id allocated automatically (A1, A2, ... per workspace)
- Events emitted: artifact.created, artifact.version_created
"""
import hashlib
import io
import json
from typing import Optional, List, Any
from uuid import UUID, uuid4
from datetime import datetime

import fitz  # PyMuPDF

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from auth_middleware import get_current_agent, AgentContext
from database import get_db_session
from storage import create_storage_from_env, StorageError, ObjectExistsError
from rbac import require_permission

router = APIRouter()

# Initialize storage
storage = create_storage_from_env()


class CreateArtifactRequest(BaseModel):
    """Request to create artifact metadata (no content yet)."""
    type: str = Field(..., description="Artifact type: pdf|code|dataset|log|draft|config")
    metadata: Optional[dict] = Field(default=None, description="Optional metadata JSON")


class ArtifactResponse(BaseModel):
    """Artifact metadata response."""
    id: str
    workspace_id: str
    short_id: str
    type: str
    metadata: Optional[dict]
    storage_uri: str
    created_by: str
    created_at: str


class ArtifactVersionResponse(BaseModel):
    """Artifact version response."""
    id: str
    artifact_id: str
    version: int
    storage_uri: str
    content_hash: Optional[str]
    created_by: str
    created_at: str


class ArtifactDetailResponse(BaseModel):
    """Artifact with versions."""
    artifact: ArtifactResponse
    versions: List[ArtifactVersionResponse]


def _allocate_short_id(workspace_id: UUID, db) -> str:
    """
    Allocate next short_id for workspace (A1, A2, ...).
    
    Args:
        workspace_id: Workspace UUID
        db: Database session
        
    Returns:
        Next available short_id (e.g., "A5")
    """
    # Find highest existing short_id in workspace
    result = db.execute(
        """
        SELECT short_id FROM artifacts 
        WHERE workspace_id = :workspace_id 
          AND short_id LIKE 'A%%'
        ORDER BY created_at DESC 
        LIMIT 1
        """,
        {"workspace_id": str(workspace_id)}
    )
    row = result.fetchone()
    
    if row is None:
        return "A1"
    
    # Parse existing short_id (e.g., "A5" -> 5)
    last_short_id = row[0]
    if not last_short_id.startswith("A"):
        # Fallback if data is malformed
        return "A1"
    
    try:
        last_num = int(last_short_id[1:])
        return f"A{last_num + 1}"
    except (ValueError, IndexError):
        # Fallback if parsing fails
        return "A1"


def _process_content(content: bytes, artifact_type: str) -> dict:
    """
    Process raw content based on artifact type.
    
    Args:
        content: Raw content bytes
        artifact_type: Artifact type (pdf, repo, log, draft, etc.)
        
    Returns:
        JSON-serializable dict with processed content
    """
    if artifact_type == "pdf":
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            pages = []
            for i, page in enumerate(doc):
                pages.append({
                    "page_number": i + 1,
                    "text": page.get_text()
                })
            return {"pages": pages}
        except Exception as e:
            return {"error": f"Failed to process PDF: {str(e)}"}
            
    elif artifact_type == "repo":
        try:
            # Repo content should be a JSON file tree
            return json.loads(content)
        except json.JSONDecodeError:
            return {"error": "Invalid repository content format (expected JSON)"}
            
    elif artifact_type == "log":
        return {"text": content.decode("utf-8", errors="replace")}
        
    elif artifact_type == "draft":
        return {"text": content.decode("utf-8", errors="replace")}
        
    elif artifact_type == "config":
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"text": content.decode("utf-8", errors="replace")}
            
    else:
        # Default fallback
        try:
            return {"raw_content": content.decode("utf-8", errors="replace")}
        except Exception:
            return {"message": "Binary content cannot be displayed"}


def _ensure_uuid(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _emit_event(workspace_id: UUID, event_type: str, actor_id: UUID, payload: dict, db):
    """
    Emit an event to the events table.
    
    Args:
        workspace_id: Workspace UUID
        event_type: Event type (e.g., artifact.created)
        actor_id: Agent UUID (actor)
        payload: Event payload
        db: Database session
    """
    event_id = uuid4()
    db.execute(
        """
        INSERT INTO events (id, workspace_id, actor_type, actor_id, event_type, payload, created_at)
        VALUES (:id, :workspace_id, :actor_type, :actor_id, :event_type, :payload, :created_at)
        """,
        {
            "id": str(event_id),
            "workspace_id": str(workspace_id),
            "actor_type": "agent",
            "actor_id": str(actor_id),
            "event_type": event_type,
            "payload": payload,
            "created_at": datetime.utcnow()
        }
    )


@router.post("/workspaces/{workspace_id}/artifacts", status_code=201)
async def create_artifact(
    workspace_id: UUID,
    req: CreateArtifactRequest,
    agent: AgentContext = Depends(get_current_agent),
    db=Depends(get_db_session)
):
    """
    Create artifact metadata record (no content yet).
    
    Allocates short_id automatically (A1, A2, ...).
    Emits artifact.created event.
    Supports idempotency via Idempotency-Key header.
    
    Authority: Requires artifact.create permission.
    """
    # Check permission
    require_permission(db, agent.agent_id, str(workspace_id), "artifact.create")
    
    # Verify workspace exists
    result = db.execute(
        "SELECT id FROM workspaces WHERE id = :workspace_id",
        {"workspace_id": str(workspace_id)}
    )
    if result.fetchone() is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Allocate short_id
    short_id = _allocate_short_id(workspace_id, db)
    
    # Generate artifact ID and storage URI (root for all versions)
    artifact_id = uuid4()
    storage_uri = f"s3://agora/{workspace_id}/artifacts/{artifact_id}/"
    
    # Insert artifact metadata
    db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
        VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, :created_at)
        """,
        {
            "id": str(artifact_id),
            "workspace_id": str(workspace_id),
            "short_id": short_id,
            "type": req.type,
            "metadata": req.metadata,
            "storage_uri": storage_uri,
            "created_by": agent.agent_id,
            "created_at": datetime.utcnow()
        }
    )
    
    # Emit event
    _emit_event(
        workspace_id=workspace_id,
        event_type="artifact.created",
        actor_id=UUID(agent.agent_id),
        payload={
            "artifact_id": str(artifact_id),
            "short_id": short_id,
            "type": req.type
        },
        db=db
    )
    
    db.commit()
    
    return {
        "id": str(artifact_id),
        "workspace_id": str(workspace_id),
        "short_id": short_id,
        "type": req.type,
        "metadata": req.metadata,
        "storage_uri": storage_uri,
        "created_by": agent.agent_id,
        "created_at": datetime.utcnow().isoformat()
    }


@router.post("/artifacts/{artifact_id}/versions", status_code=201)
async def create_artifact_version(
    artifact_id: UUID,
    file: UploadFile = File(...),
    agent: AgentContext = Depends(get_current_agent),
    db=Depends(get_db_session)
):
    """
    Upload new version for artifact (writes to MinIO + artifact_versions).
    
    Enforces:
    - Immutability (versions cannot be overwritten)
    - Content hash calculation for integrity
    - Automatic version numbering
    
    Emits artifact.version_created event.
    Supports idempotency via Idempotency-Key header.
    
    Authority: Requires artifact.version.create permission.
    """
    # Get artifact and verify access
    result = db.execute(
        "SELECT workspace_id, short_id, type FROM artifacts WHERE id = :artifact_id",
        {"artifact_id": str(artifact_id)}
    )
    artifact = result.fetchone()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    workspace_id = _ensure_uuid(artifact[0])
    short_id = artifact[1]
    artifact_type = artifact[2]
    
    # Check permission
    require_permission(db, agent.agent_id, str(workspace_id), "artifact.version.create")
    
    # Get next version number
    result = db.execute(
        """
        SELECT MAX(version) FROM artifact_versions WHERE artifact_id = :artifact_id
        """,
        {"artifact_id": str(artifact_id)}
    )
    max_version = result.fetchone()[0]
    next_version = (max_version or 0) + 1
    
    # Read file content
    content = await file.read()
    
    # Calculate content hash
    content_hash = hashlib.sha256(content).hexdigest()
    
    # Generate storage URI for this version
    version_storage_uri = f"s3://agora/{workspace_id}/artifacts/{artifact_id}/v{next_version}/content"
    
    # Store content in MinIO
    try:
        storage.put_object(version_storage_uri, content)
    except ObjectExistsError:
        raise HTTPException(
            status_code=409,
            detail="Version already exists. Artifacts are immutable."
        )
    except StorageError as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}")
    
    # Create artifact_versions record
    version_id = uuid4()
    db.execute(
        """
        INSERT INTO artifact_versions (id, artifact_id, version, storage_uri, content_hash, created_by, created_at)
        VALUES (:id, :artifact_id, :version, :storage_uri, :content_hash, :created_by, :created_at)
        """,
        {
            "id": str(version_id),
            "artifact_id": str(artifact_id),
            "version": next_version,
            "storage_uri": version_storage_uri,
            "content_hash": content_hash,
            "created_by": agent.agent_id,
            "created_at": datetime.utcnow()
        }
    )
    
    # Emit event
    _emit_event(
        workspace_id=workspace_id,
        event_type="artifact.version_created",
        actor_id=UUID(agent.agent_id),
        payload={
            "artifact_id": str(artifact_id),
            "artifact_version_id": str(version_id),
            "short_id": short_id,
            "version": next_version,
            "content_hash": content_hash
        },
        db=db
    )
    
    db.commit()
    
    return {
        "id": str(version_id),
        "artifact_id": str(artifact_id),
        "version": next_version,
        "storage_uri": version_storage_uri,
        "content_hash": content_hash,
        "created_by": agent.agent_id,
        "created_at": datetime.utcnow().isoformat()
    }


@router.get("/workspaces/{workspace_id}/artifacts")
async def list_artifacts(
    workspace_id: UUID,
    type: Optional[str] = None,
    agent: AgentContext = Depends(get_current_agent),
    db=Depends(get_db_session)
):
    """
    List artifacts in workspace.
    
    Optional filters:
    - type: Filter by artifact type
    
    Authority: Requires artifact.read permission.
    """
    # Check permission
    require_permission(db, agent.agent_id, str(workspace_id), "artifact.read")
    
    # Build query
    query = """
        SELECT id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at
        FROM artifacts
        WHERE workspace_id = :workspace_id
    """
    params = {"workspace_id": str(workspace_id)}
    
    if type:
        query += " AND type = :type"
        params["type"] = type
    
    query += " ORDER BY created_at DESC"
    
    result = db.execute(query, params)
    rows = result.fetchall()
    
    artifacts = []
    for row in rows:
        artifacts.append({
            "id": row[0],
            "workspace_id": row[1],
            "short_id": row[2],
            "type": row[3],
            "metadata": row[4],
            "storage_uri": row[5],
            "created_by": row[6],
            "created_at": row[7].isoformat()
        })
    
    return {"artifacts": artifacts}


@router.get("/artifacts/{artifact_id}")
async def get_artifact(
    artifact_id: UUID,
    agent: AgentContext = Depends(get_current_agent),
    db=Depends(get_db_session)
):
    """
    Get artifact metadata.
    
    Authority: Requires artifact.read permission.
    """
    # Get artifact
    result = db.execute(
        """
        SELECT id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at
        FROM artifacts
        WHERE id = :artifact_id
        """,
        {"artifact_id": str(artifact_id)}
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    workspace_id = _ensure_uuid(row[1])
    
    # Check permission
    require_permission(db, agent.agent_id, str(workspace_id), "artifact.read")
    
    return {
        "id": row[0],
        "workspace_id": row[1],
        "short_id": row[2],
        "type": row[3],
        "metadata": row[4],
        "storage_uri": row[5],
        "created_by": row[6],
        "created_at": row[7].isoformat()
    }


@router.get("/artifacts/{artifact_id}/versions")
async def list_artifact_versions(
    artifact_id: UUID,
    agent: AgentContext = Depends(get_current_agent),
    db=Depends(get_db_session)
):
    """
    List all versions of an artifact.
    
    Authority: Requires artifact.read permission.
    """
    # Get artifact to check permission
    result = db.execute(
        "SELECT workspace_id FROM artifacts WHERE id = :artifact_id",
        {"artifact_id": str(artifact_id)}
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    workspace_id = _ensure_uuid(row[0])
    
    # Check permission
    require_permission(db, agent.agent_id, str(workspace_id), "artifact.read")
    
    # Get versions
    result = db.execute(
        """
        SELECT id, artifact_id, version, storage_uri, content_hash, created_by, created_at
        FROM artifact_versions
        WHERE artifact_id = :artifact_id
        ORDER BY version DESC
        """,
        {"artifact_id": str(artifact_id)}
    )
    rows = result.fetchall()
    
    versions = []
    for row in rows:
        versions.append({
            "id": row[0],
            "artifact_id": row[1],
            "version": row[2],
            "storage_uri": row[3],
            "content_hash": row[4],
            "created_by": row[5],
            "created_at": row[6].isoformat()
        })
    
    return {"versions": versions}


@router.get("/artifact-versions/{version_id}/content")
async def get_artifact_version_content(
    version_id: UUID,
    agent: AgentContext = Depends(get_current_agent),
    db=Depends(get_db_session)
):
    """
    Get exact version bytes (required for citations).
    
    This endpoint returns the immutable raw bytes for a specific version.
    Evidence/citations must reference this endpoint by `artifact_versions.id`.
    
    Authority: Requires artifact.read permission.
    """
    # Get version and check permission
    result = db.execute(
        """
        SELECT av.storage_uri, av.content_hash, a.workspace_id, a.type
        FROM artifact_versions av
        JOIN artifacts a ON av.artifact_id = a.id
        WHERE av.id = :version_id
        """,
        {"version_id": str(version_id)}
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact version not found")
    
    storage_uri = row[0]
    content_hash = row[1]
    workspace_id = _ensure_uuid(row[2])
    artifact_type = row[3]
    
    # Check permission
    require_permission(db, agent.agent_id, str(workspace_id), "artifact.read")
    
    # Retrieve from storage (raw bytes, no processing)
    try:
        content_stream = storage.get_object(storage_uri)
        content = content_stream.read()
        computed_hash = hashlib.sha256(content).hexdigest()

        # Prefer persisted content_hash, but still emit a header even if null/incorrect.
        # (Tests and callers validate immutability by comparing bytes and the hash header.)
        resp_hash = content_hash or computed_hash

        # Content-Type is intentionally generic: many artifacts are not strongly typed.
        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={
                "X-Content-Hash": resp_hash,
            },
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve content: {str(e)}")


@router.get("/artifact-versions/{version_id}/view")
async def get_artifact_version_view(
    version_id: UUID,
    agent: AgentContext = Depends(get_current_agent),
    db=Depends(get_db_session)
):
    """
    Get a processed/parsed view of a specific version (UI convenience).

    This endpoint is NOT the citation mechanism; citations must use `/content`.
    """
    result = db.execute(
        """
        SELECT av.storage_uri, av.content_hash, a.workspace_id, a.type
        FROM artifact_versions av
        JOIN artifacts a ON av.artifact_id = a.id
        WHERE av.id = :version_id
        """,
        {"version_id": str(version_id)}
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact version not found")

    storage_uri = row[0]
    workspace_id = _ensure_uuid(row[2])
    artifact_type = row[3]

    require_permission(db, agent.agent_id, str(workspace_id), "artifact.read")

    try:
        content_stream = storage.get_object(storage_uri)
        content = content_stream.read()
        return _process_content(content, artifact_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve content: {str(e)}")


@router.get("/artifacts/{artifact_id}/content")
async def get_artifact_latest_content(
    artifact_id: UUID,
    agent: AgentContext = Depends(get_current_agent),
    db=Depends(get_db_session)
):
    """
    Get latest version bytes (convenience only).
    
    WARNING: This endpoint MUST NOT be used for evidence pointers.
    Evidence/citations must reference exact version_id via
    /artifact-versions/{version_id}/content endpoint.
    
    Authority: Requires artifact.read permission.
    """
    # Get artifact
    result = db.execute(
        "SELECT workspace_id, type FROM artifacts WHERE id = :artifact_id",
        {"artifact_id": str(artifact_id)}
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    workspace_id = _ensure_uuid(row[0])
    artifact_type = row[1]
    
    # Check permission
    require_permission(db, agent.agent_id, str(workspace_id), "artifact.read")
    
    # Get latest version
    result = db.execute(
        """
        SELECT id, storage_uri, content_hash, version
        FROM artifact_versions
        WHERE artifact_id = :artifact_id
        ORDER BY version DESC
        LIMIT 1
        """,
        {"artifact_id": str(artifact_id)}
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="No versions found for artifact")
    
    version_id = row[0]
    storage_uri = row[1]
    content_hash = row[2]
    version = row[3]
    
    # Retrieve from storage (raw bytes, no processing)
    try:
        content_stream = storage.get_object(storage_uri)
        content = content_stream.read()
        computed_hash = hashlib.sha256(content).hexdigest()
        resp_hash = content_hash or computed_hash

        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={
                "X-Content-Hash": resp_hash,
                "X-Artifact-Version": str(version_id),
                "X-Artifact-Version-Number": str(version),
            },
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve content: {str(e)}")


@router.get("/artifacts/{artifact_id}/view")
async def get_artifact_latest_view(
    artifact_id: UUID,
    agent: AgentContext = Depends(get_current_agent),
    db=Depends(get_db_session)
):
    """
    Get processed/parsed view of the latest version (UI convenience).

    This endpoint is NOT a valid evidence pointer.
    """
    result = db.execute(
        "SELECT workspace_id, type FROM artifacts WHERE id = :artifact_id",
        {"artifact_id": str(artifact_id)}
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    workspace_id = _ensure_uuid(row[0])
    artifact_type = row[1]

    require_permission(db, agent.agent_id, str(workspace_id), "artifact.read")

    result = db.execute(
        """
        SELECT storage_uri
        FROM artifact_versions
        WHERE artifact_id = :artifact_id
        ORDER BY version DESC
        LIMIT 1
        """,
        {"artifact_id": str(artifact_id)}
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="No versions found for artifact")

    storage_uri = row[0]

    try:
        content_stream = storage.get_object(storage_uri)
        content = content_stream.read()
        return _process_content(content, artifact_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve content: {str(e)}")
