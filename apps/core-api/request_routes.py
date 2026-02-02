"""
Request Action Routes (Component 15)

Per spec §4.15:
- POST /workspaces/{id}/requests/ingest_pdf: Start literature_grounding workflow
- POST /workspaces/{id}/requests/ingest_repo: Start repo ingestion (Component 16)
- POST /workspaces/{id}/requests/run_sandbox: Start sandbox execution
- POST /workspaces/{id}/requests/finalize_draft: Finalize draft version

All endpoints start workflows/activities and return tracking IDs.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import uuid

from database import DBWrapper, get_db
from auth_middleware import require_agent_token


router = APIRouter()


# Request/Response Models

class IngestPdfRequest(BaseModel):
    """Request to ingest a PDF artifact."""
    artifact_id: str = Field(..., description="UUID of PDF artifact to ingest")


class IngestPdfResponse(BaseModel):
    """Response for PDF ingestion request."""
    request_id: str
    workflow_run_id: str
    artifact_id: str
    message: str


class IngestRepoRequest(BaseModel):
    """Request to ingest a code repository."""
    repo_url: str = Field(..., description="Git repository URL")
    branch: Optional[str] = Field(None, description="Branch to clone (default: main/master)")
    commit_hash: Optional[str] = Field(None, description="Specific commit hash to pin")


class IngestRepoResponse(BaseModel):
    """Response for repo ingestion request."""
    request_id: str
    activity_run_id: str
    artifact_id: str
    message: str


class FinalizeDraftRequest(BaseModel):
    """Request to finalize a draft."""
    draft_artifact_id: str = Field(..., description="UUID of draft artifact")
    draft_artifact_version_id: str = Field(..., description="UUID of specific draft version to finalize")


class FinalizeDraftResponse(BaseModel):
    """Response for draft finalization request."""
    request_id: str
    draft_artifact_id: str
    draft_artifact_version_id: str
    message: str


# Endpoints

@router.post("/workspaces/{workspace_id}/requests/ingest_pdf", response_model=IngestPdfResponse, tags=["Request Actions"])
async def request_ingest_pdf(
    workspace_id: uuid.UUID,
    request: IngestPdfRequest,
    current_agent: dict = Depends(require_agent_token),
    db: DBWrapper = Depends(get_db)
):
    """
    Start literature_grounding workflow to ingest PDF.
    
    Per spec §4.15, §12.2:
    - Starts literature_grounding workflow
    - Workflow executes: pdf_ingest -> create agent_task -> agent creates claims/drafts -> citation_check
    - Returns tracking IDs for monitoring
    """
    workspace_id_str = str(workspace_id)
    
    # Verify workspace exists
    ws_row = db.execute(
        "SELECT id, phase FROM workspaces WHERE id = :id",
        {"id": workspace_id_str}
    ).fetchone()
    
    if not ws_row:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id_str} not found")
    
    # Verify artifact exists and belongs to workspace
    artifact_row = db.execute(
        """
        SELECT id, type, workspace_id
        FROM artifacts
        WHERE id = :id
        """,
        {"id": request.artifact_id}
    ).fetchone()
    
    if not artifact_row:
        raise HTTPException(status_code=404, detail=f"Artifact {request.artifact_id} not found")
    
    if artifact_row[2] != workspace_id_str:
        raise HTTPException(
            status_code=403,
            detail=f"Artifact {request.artifact_id} does not belong to workspace {workspace_id_str}"
        )
    
    if artifact_row[1] != "pdf":
        raise HTTPException(
            status_code=400,
            detail=f"Artifact {request.artifact_id} is not a PDF (type={artifact_row[1]})"
        )
    
    # Check if already ingested (idempotency)
    existing_version = db.execute(
        """
        SELECT id FROM artifact_versions
        WHERE artifact_id = :artifact_id
        ORDER BY version DESC
        LIMIT 1
        """,
        {"artifact_id": request.artifact_id}
    ).fetchone()
    
    if existing_version:
        # Already ingested, return existing workflow if found
        existing_workflow = db.execute(
            """
            SELECT id FROM workflow_runs
            WHERE workspace_id = :workspace_id
              AND workflow_type = 'literature_grounding'
              AND input::jsonb @> jsonb_build_object('artifact_id', :artifact_id::text)
            ORDER BY created_at DESC
            LIMIT 1
            """,
            {"workspace_id": workspace_id_str, "artifact_id": request.artifact_id}
        ).fetchone()
        
        if existing_workflow:
            return IngestPdfResponse(
                request_id=str(uuid.uuid4()),
                workflow_run_id=existing_workflow[0],
                artifact_id=request.artifact_id,
                message="PDF already ingested. Returning existing workflow."
            )
    
    # Start literature_grounding workflow
    from literature_grounding_workflow import literature_grounding_workflow
    
    try:
        result = await literature_grounding_workflow(
            workspace_id=workspace_id_str,
            artifact_id=request.artifact_id,
            db=db
        )
        
        request_id = str(uuid.uuid4())
        
        return IngestPdfResponse(
            request_id=request_id,
            workflow_run_id=result["workflow_run_id"],
            artifact_id=request.artifact_id,
            message=f"Literature grounding workflow started. Task {result['task_id']} created for claim extraction."
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {str(e)}")


@router.post("/workspaces/{workspace_id}/requests/ingest_repo", response_model=IngestRepoResponse, tags=["Request Actions"])
async def request_ingest_repo(
    workspace_id: uuid.UUID,
    request: IngestRepoRequest,
    current_agent: dict = Depends(require_agent_token),
    db: DBWrapper = Depends(get_db)
):
    """
    Start repo ingestion activity.
    
    Per spec §4.15, §6.2:
    - Creates code artifact
    - Starts repo_ingest activity
    - Activity clones repo, indexes files, stores in MinIO
    - Returns artifact_id and activity_run_id for tracking
    """
    workspace_id_str = str(workspace_id)
    
    # Verify workspace exists
    ws_row = db.execute(
        "SELECT id, phase FROM workspaces WHERE id = :id",
        {"id": workspace_id_str}
    ).fetchone()
    
    if not ws_row:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id_str} not found")
    
    # Check if repo already ingested (idempotency by repo_url + commit_hash)
    existing_artifact = None
    if request.commit_hash:
        existing_artifact = db.execute(
            """
            SELECT a.id FROM artifacts a
            JOIN artifact_versions av ON a.id = av.artifact_id
            WHERE a.workspace_id = :workspace_id
              AND a.type = 'code'
              AND av.content_hash = :commit_hash
            LIMIT 1
            """,
            {"workspace_id": workspace_id_str, "commit_hash": request.commit_hash}
        ).fetchone()
    
    if existing_artifact:
        return IngestRepoResponse(
            request_id=str(uuid.uuid4()),
            activity_run_id="existing",
            artifact_id=existing_artifact[0],
            message=f"Repository already ingested at commit {request.commit_hash}"
        )
    
    # Create code artifact
    import json
    artifact_id = str(uuid.uuid4())
    
    db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
        VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
        """,
        {
            "id": artifact_id,
            "workspace_id": workspace_id_str,
            "short_id": f"C{abs(hash(artifact_id)) % 10000}",
            "type": "code",
            "metadata": json.dumps({"repo_url": request.repo_url}),
            "storage_uri": f"s3://agora/{workspace_id_str}/artifacts/{artifact_id}/",
            "created_by": current_agent["agent_id"]
        }
    )
    
    # Create activity_run for tracking
    activity_run_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO activity_runs (id, workflow_run_id, activity_type, status, input, created_at)
        VALUES (:id, :workflow_run_id, :activity_type, :status, :input, NOW())
        """,
        {
            "id": activity_run_id,
            "workflow_run_id": None,  # Standalone activity
            "activity_type": "repo_ingest",
            "status": "running",
            "input": json.dumps({
                "artifact_id": artifact_id,
                "workspace_id": workspace_id_str,
                "repo_url": request.repo_url,
                "branch": request.branch,
                "commit_hash": request.commit_hash,
                "created_by": current_agent["agent_id"]
            })
        }
    )
    
    db.commit()
    
    # Execute repo_ingest activity (synchronously for MVP)
    import sys
    sys.path.insert(0, "/Users/nirtzur/Documents/projects/AGORA/apps/worker")
    from repo_ingest import RepoIngestActivity
    from storage import get_storage
    
    try:
        storage = get_storage()
        repo_activity = RepoIngestActivity(storage, db)
        
        result = repo_activity.ingest_repo(
            artifact_id=artifact_id,
            workspace_id=workspace_id_str,
            repo_url=request.repo_url,
            created_by=current_agent["agent_id"],
            branch=request.branch,
            commit_hash=request.commit_hash,
            activity_run_id=activity_run_id
        )
        
        # Update activity_run status
        db.execute(
            """
            UPDATE activity_runs
            SET status = :status, output = :output, completed_at = NOW()
            WHERE id = :id
            """,
            {
                "id": activity_run_id,
                "status": "completed",
                "output": json.dumps(result)
            }
        )
        db.commit()
        
        return IngestRepoResponse(
            request_id=str(uuid.uuid4()),
            activity_run_id=activity_run_id,
            artifact_id=artifact_id,
            message=f"Repository ingested: {result['file_count']} files at commit {result['commit_hash']}"
        )
    
    except Exception as e:
        # Update activity_run with failure
        db.execute(
            """
            UPDATE activity_runs
            SET status = :status, output = :output, completed_at = NOW()
            WHERE id = :id
            """,
            {
                "id": activity_run_id,
                "status": "failed",
                "output": json.dumps({"error": str(e)})
            }
        )
        db.commit()
        raise HTTPException(status_code=500, detail=f"Repo ingestion failed: {str(e)}")


@router.post("/workspaces/{workspace_id}/requests/finalize_draft", response_model=FinalizeDraftResponse, tags=["Request Actions"])
def request_finalize_draft(
    workspace_id: uuid.UUID,
    request: FinalizeDraftRequest,
    current_agent: dict = Depends(require_agent_token),
    db: DBWrapper = Depends(get_db)
):
    """
    Request draft finalization (SYSTEM will finalize after gates pass).
    
    Per spec §4.15, §12.4:
    - Citation checks run continuously on draft versions
    - If all rule checks pass, orchestrator finalizes the draft
    - This endpoint validates and queues the finalization request
    """
    workspace_id_str = str(workspace_id)
    
    # Verify workspace exists
    ws_row = db.execute(
        "SELECT id, phase FROM workspaces WHERE id = :id",
        {"id": workspace_id_str}
    ).fetchone()
    
    if not ws_row:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id_str} not found")
    
    # Verify draft artifact exists and belongs to workspace
    draft_row = db.execute(
        """
        SELECT id, type, workspace_id, metadata
        FROM artifacts
        WHERE id = :id
        """,
        {"id": request.draft_artifact_id}
    ).fetchone()
    
    if not draft_row:
        raise HTTPException(status_code=404, detail=f"Draft artifact {request.draft_artifact_id} not found")
    
    if draft_row[2] != workspace_id_str:
        raise HTTPException(
            status_code=403,
            detail=f"Draft artifact {request.draft_artifact_id} does not belong to workspace {workspace_id_str}"
        )
    
    if draft_row[1] != "draft":
        raise HTTPException(
            status_code=400,
            detail=f"Artifact {request.draft_artifact_id} is not a draft (type={draft_row[1]})"
        )
    
    # Verify draft version exists
    version_row = db.execute(
        """
        SELECT id, artifact_id
        FROM artifact_versions
        WHERE id = :id
        """,
        {"id": request.draft_artifact_version_id}
    ).fetchone()
    
    if not version_row:
        raise HTTPException(status_code=404, detail=f"Draft version {request.draft_artifact_version_id} not found")
    
    if version_row[1] != request.draft_artifact_id:
        raise HTTPException(
            status_code=400,
            detail=f"Version {request.draft_artifact_version_id} does not belong to draft {request.draft_artifact_id}"
        )
    
    # Check rule checks for this version
    import json
    rule_checks = db.execute(
        """
        SELECT rule_name, status, details
        FROM rule_checks
        WHERE target_type = 'draft_version'
          AND target_id = :version_id
        ORDER BY created_at DESC
        """,
        {"version_id": request.draft_artifact_version_id}
    ).fetchall()
    
    # Verify required rule checks exist and passed
    required_rules = {"citation_coverage", "citation_resolves"}
    found_rules = {}
    
    for rule_name, status, details in rule_checks:
        if rule_name in required_rules:
            found_rules[rule_name] = status
    
    missing_rules = required_rules - set(found_rules.keys())
    if missing_rules:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required rule checks: {', '.join(missing_rules)}. Run citation check first."
        )
    
    failed_rules = [rule for rule, status in found_rules.items() if status != "pass"]
    if failed_rules:
        raise HTTPException(
            status_code=400,
            detail=f"Rule checks failed: {', '.join(failed_rules)}. Cannot finalize draft with failed checks."
        )
    
    # All checks passed - finalize the draft (SYSTEM action via draft_routes)
    # For MVP, we call the finalize endpoint directly
    from draft_routes import finalize_draft, FinalizeDraftRequest as DraftFinalizeRequest
    
    mock_system = {"token_type": "system"}
    
    try:
        finalize_draft(
            draft_id=uuid.UUID(request.draft_artifact_id),
            request=DraftFinalizeRequest(draft_artifact_version_id=request.draft_artifact_version_id),
            system_token=mock_system,
            db=db
        )
        
        request_id = str(uuid.uuid4())
        
        return FinalizeDraftResponse(
            request_id=request_id,
            draft_artifact_id=request.draft_artifact_id,
            draft_artifact_version_id=request.draft_artifact_version_id,
            message="Draft finalized successfully. All rule checks passed."
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to finalize draft: {str(e)}")
