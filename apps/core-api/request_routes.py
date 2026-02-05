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
from typing import Optional, Dict, Any
from pathlib import Path
import sys
import uuid
import json

from database import DBWrapper, get_db_session
from auth_middleware import require_agent_token, require_system_token, AgentContext, SystemContext


router = APIRouter()


def _ensure_worker_path() -> None:
    worker_path = Path(__file__).resolve().parents[2] / "apps" / "worker"
    worker_path_str = str(worker_path)
    if worker_path_str not in sys.path:
        sys.path.insert(0, worker_path_str)


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


class RunSandboxRequest(BaseModel):
    """Request to run sandbox execution."""
    script_artifact_id: str = Field(..., description="UUID of artifact containing script to execute")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Execution parameters (env vars, args)")
    image: Optional[str] = Field(default="python:3.11-slim", description="Docker image to use")
    timeout_seconds: Optional[int] = Field(default=300, description="Execution timeout in seconds")
    memory_limit: Optional[str] = Field(default="512m", description="Container memory limit")
    cpu_limit: Optional[str] = Field(default="1.0", description="Container CPU limit")


class RunSandboxResponse(BaseModel):
    """Response for sandbox execution request."""
    request_id: str
    activity_run_id: str
    log_artifact_id: str
    config_artifact_id: str
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
    current_agent: AgentContext = Depends(require_agent_token),
    db: DBWrapper = Depends(get_db_session)
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
    
    if str(artifact_row[2]) != workspace_id_str:
        raise HTTPException(
            status_code=403,
            detail=f"Artifact {request.artifact_id} does not belong to workspace {workspace_id_str}"
        )
    
    if artifact_row[1] != "pdf":
        raise HTTPException(
            status_code=400,
            detail=f"Artifact {request.artifact_id} is not a PDF (type={artifact_row[1]})"
        )
    
    # Note: We rely on Idempotency-Key for deduplication; do not short-circuit on existing versions.
    
    # Start literature_grounding workflow
    _ensure_worker_path()
    from literature_grounding_workflow import literature_grounding_workflow
    
    try:
        result = await literature_grounding_workflow(
            workspace_id=workspace_id_str,
            artifact_id=request.artifact_id,
            db=db,
            created_by=current_agent.agent_id
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
    current_agent: AgentContext = Depends(require_agent_token),
    db: DBWrapper = Depends(get_db_session)
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
            "created_by": current_agent.agent_id
        }
    )
    
    # Create workflow_run + activity_run for tracking
    workflow_run_id = str(uuid.uuid4())
    temporal_workflow_id = f"repo_ingest_{workflow_run_id}"
    db.execute(
        """
        INSERT INTO workflow_runs (id, workspace_id, workflow_type, temporal_workflow_id, status)
        VALUES (:id, :workspace_id, :workflow_type, :temporal_workflow_id, :status)
        """,
        {
            "id": workflow_run_id,
            "workspace_id": workspace_id_str,
            "workflow_type": "repo_ingest",
            "temporal_workflow_id": temporal_workflow_id,
            "status": "running"
        }
    )
    
    activity_run_id = str(uuid.uuid4())
    temporal_activity_id = f"repo_ingest_{activity_run_id}"
    db.execute(
        """
        INSERT INTO activity_runs (id, workflow_run_id, activity_type, temporal_activity_id, status)
        VALUES (:id, :workflow_run_id, :activity_type, :temporal_activity_id, :status)
        """,
        {
            "id": activity_run_id,
            "workflow_run_id": workflow_run_id,
            "activity_type": "repo_ingest",
            "temporal_activity_id": temporal_activity_id,
            "status": "running"
        }
    )
    
    db.commit()
    
    # Execute repo_ingest activity (synchronously for MVP)
    _ensure_worker_path()
    from repo_ingest import RepoIngestActivity
    from storage import create_storage_from_env
    
    try:
        storage = create_storage_from_env()
        repo_activity = RepoIngestActivity(storage, db)
        
        result = repo_activity.ingest_repo(
            artifact_id=artifact_id,
            workspace_id=workspace_id_str,
            repo_url=request.repo_url,
            created_by=current_agent.agent_id,
            branch=request.branch,
            commit_hash=request.commit_hash,
            activity_run_id=activity_run_id
        )
        
        # Update activity_run + workflow_run status
        db.execute(
            """
            UPDATE activity_runs
            SET status = :status, completed_at = NOW()
            WHERE id = :id
            """,
            {
                "id": activity_run_id,
                "status": "completed"
            }
        )
        db.execute(
            """
            UPDATE workflow_runs
            SET status = :status, completed_at = NOW()
            WHERE id = :id
            """,
            {
                "id": workflow_run_id,
                "status": "completed"
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
        # Update activity_run + workflow_run with failure
        db.execute(
            """
            UPDATE activity_runs
            SET status = :status, completed_at = NOW()
            WHERE id = :id
            """,
            {
                "id": activity_run_id,
                "status": "failed"
            }
        )
        db.execute(
            """
            UPDATE workflow_runs
            SET status = :status, completed_at = NOW()
            WHERE id = :id
            """,
            {
                "id": workflow_run_id,
                "status": "failed"
            }
        )
        db.commit()
        raise HTTPException(status_code=500, detail=f"Repo ingestion failed: {str(e)}")


@router.post("/workspaces/{workspace_id}/requests/run_sandbox", response_model=RunSandboxResponse, tags=["Request Actions"])
async def request_run_sandbox(
    workspace_id: uuid.UUID,
    request: RunSandboxRequest,
    current_agent: AgentContext = Depends(require_agent_token),
    db: DBWrapper = Depends(get_db_session)
):
    """
    Execute script in sandbox Docker container.
    
    Per spec §4.15, §6.4:
    - Runs script in constrained Docker container (no network, resource limits)
    - Captures stdout/stderr as log artifact
    - Stores execution config/provenance
    - Enforces per-workspace sandbox budget
    
    Returns:
        RunSandboxResponse with tracking IDs
        
    Raises:
        429: Sandbox budget exhausted (with Retry-After header)
        404: Workspace or script artifact not found
        400: Invalid request
    """
    workspace_id_str = str(workspace_id)
    
    # Verify workspace exists
    ws_row = db.execute(
        "SELECT id, phase FROM workspaces WHERE id = :id",
        {"id": workspace_id_str}
    ).fetchone()
    
    if not ws_row:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id_str} not found")
    
    # Check sandbox budget (enforce per-workspace limits)
    # Per spec: reject with 429 + Retry-After when exhausted
    sandbox_limit = 100  # MVP: 100 executions per workspace
    existing_runs = db.execute(
        """
        SELECT COUNT(*)
        FROM activity_runs ar
        JOIN workflow_runs wr ON ar.workflow_run_id = wr.id
        WHERE wr.workspace_id = :workspace_id
          AND ar.activity_type = 'sandbox_run'
          AND ar.status IN ('running', 'completed')
        """,
        {"workspace_id": workspace_id_str}
    ).fetchone()
    
    if existing_runs and existing_runs[0] >= sandbox_limit:
        # Return 429 with Retry-After header
        from fastapi import Response
        raise HTTPException(
            status_code=429,
            detail=f"Sandbox budget exhausted ({existing_runs[0]}/{sandbox_limit} executions used). Contact workspace admin.",
            headers={"Retry-After": "3600"}  # Retry after 1 hour
        )
    
    # Verify script artifact exists and belongs to workspace
    script_row = db.execute(
        """
        SELECT a.id, a.type, a.workspace_id
        FROM artifacts a
        WHERE a.id = :id
        """,
        {"id": request.script_artifact_id}
    ).fetchone()
    
    if not script_row:
        raise HTTPException(status_code=404, detail=f"Script artifact {request.script_artifact_id} not found")
    
    if str(script_row[2]) != workspace_id_str:
        raise HTTPException(
            status_code=403,
            detail=f"Script artifact {request.script_artifact_id} does not belong to workspace {workspace_id_str}"
        )
    
    if script_row[1] not in ("code", "script"):
        raise HTTPException(
            status_code=400,
            detail=f"Artifact {request.script_artifact_id} is not executable (type={script_row[1]})"
        )
    
    # Create workflow_run + activity_run for tracking
    workflow_run_id = str(uuid.uuid4())
    temporal_workflow_id = f"sandbox_run_{workflow_run_id}"
    db.execute(
        """
        INSERT INTO workflow_runs (id, workspace_id, workflow_type, temporal_workflow_id, status)
        VALUES (:id, :workspace_id, :workflow_type, :temporal_workflow_id, :status)
        """,
        {
            "id": workflow_run_id,
            "workspace_id": workspace_id_str,
            "workflow_type": "sandbox_run",
            "temporal_workflow_id": temporal_workflow_id,
            "status": "running"
        }
    )
    
    # Create log artifact (after workflow_run_id is defined)
    log_artifact_id = str(uuid.uuid4())
    
    db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
        VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
        """,
        {
            "id": log_artifact_id,
            "workspace_id": workspace_id_str,
            "short_id": f"LOG{abs(hash(log_artifact_id)) % 10000}",
            "type": "log",
            "metadata": json.dumps(
                {
                    "source": "sandbox_execution",
                    "script_artifact_id": request.script_artifact_id,
                    "workflow_run_id": workflow_run_id,
                }
            ),
            "storage_uri": f"s3://agora/{workspace_id_str}/artifacts/{log_artifact_id}/",
            "created_by": current_agent.agent_id
        }
    )
    
    activity_run_id = str(uuid.uuid4())
    temporal_activity_id = f"sandbox_run_{activity_run_id}"
    db.execute(
        """
        INSERT INTO activity_runs (id, workflow_run_id, activity_type, temporal_activity_id, status)
        VALUES (:id, :workflow_run_id, :activity_type, :temporal_activity_id, :status)
        """,
        {
            "id": activity_run_id,
            "workflow_run_id": workflow_run_id,
            "activity_type": "sandbox_run",
            "temporal_activity_id": temporal_activity_id,
            "status": "running"
        }
    )
    
    db.commit()
    
    # Execute sandbox_run activity (synchronously for MVP)
    _ensure_worker_path()
    from sandbox_run import SandboxRunActivity
    from storage import create_storage_from_env
    
    try:
        storage = create_storage_from_env()
        sandbox_activity = SandboxRunActivity(storage, db)
        
        result = sandbox_activity.run_sandbox(
            artifact_id=log_artifact_id,
            workspace_id=workspace_id_str,
            script_artifact_id=request.script_artifact_id,
            parameters=request.parameters,
            created_by=current_agent.agent_id,
            activity_run_id=activity_run_id,
            image=request.image or "python:3.11-slim",
            timeout_seconds=request.timeout_seconds or 300,
            memory_limit=request.memory_limit or "512m",
            cpu_limit=request.cpu_limit or "1.0"
        )
        
        # Update activity_run + workflow_run status
        db.execute(
            """
            UPDATE activity_runs
            SET status = :status, completed_at = NOW()
            WHERE id = :id
            """,
            {
                "id": activity_run_id,
                "status": "completed"
            }
        )
        db.execute(
            """
            UPDATE workflow_runs
            SET status = :status, completed_at = NOW()
            WHERE id = :id
            """,
            {
                "id": workflow_run_id,
                "status": "completed"
            }
        )
        db.commit()
        
        return RunSandboxResponse(
            request_id=str(uuid.uuid4()),
            activity_run_id=activity_run_id,
            log_artifact_id=result["artifact_id"],
            config_artifact_id=result["config_artifact_id"],
            message=f"Sandbox execution completed with exit code {result['exit_code']} in {result['execution_time_seconds']:.2f}s"
        )
    
    except Exception as e:
        # Update activity_run + workflow_run with failure
        db.execute(
            """
            UPDATE activity_runs
            SET status = :status, completed_at = NOW()
            WHERE id = :id
            """,
            {
                "id": activity_run_id,
                "status": "failed"
            }
        )
        db.execute(
            """
            UPDATE workflow_runs
            SET status = :status, completed_at = NOW()
            WHERE id = :id
            """,
            {
                "id": workflow_run_id,
                "status": "failed"
            }
        )
        db.commit()
        raise HTTPException(status_code=500, detail=f"Sandbox execution failed: {str(e)}")


@router.post("/workspaces/{workspace_id}/requests/finalize_draft", response_model=FinalizeDraftResponse, tags=["Request Actions"])
async def request_finalize_draft(
    workspace_id: uuid.UUID,
    request: FinalizeDraftRequest,
    system_context: SystemContext = Depends(require_system_token),
    db: DBWrapper = Depends(get_db_session)
):
    """
    Start draft finalization workflow.
    
    Per spec §5.6, §4.10, §12.4:
    - System-only endpoint (orchestrator authority)
    - Validates workspace phase == FINALIZED
    - Starts DraftFinalizationWorkflow to check gate and finalize draft
    - Gate checks: citation coverage/resolves, critique sufficiency, role caps, no blocking critiques
    - On success: sets metadata status=final, emits draft.finalized + workspace.finalized events
    
    Returns:
        Workflow run ID for tracking finalization progress
    
    Raises:
        403: If agent attempts to call (system-only)
        400: If IDs don't match or workspace not in FINALIZED phase
        404: If workspace/draft/version not found
    """
    # SYSTEM-ONLY: Auth enforced by require_system_token dependency.
    
    workspace_id_str = str(workspace_id)
    
    # Validate workspace exists and is in FINALIZED phase
    ws_row = db.execute(
        "SELECT id, phase FROM workspaces WHERE id = :id",
        {"id": workspace_id_str}
    ).fetchone()
    
    if not ws_row:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id_str} not found")
    
    if ws_row[1] != "FINALIZED":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot finalize draft: workspace phase is {ws_row[1]}, must be FINALIZED"
        )
    
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
    
    if str(draft_row[2]) != workspace_id_str:
        raise HTTPException(
            status_code=403,
            detail=f"Draft artifact {request.draft_artifact_id} does not belong to workspace {workspace_id_str}"
        )
    
    if draft_row[1] != "draft":
        raise HTTPException(
            status_code=400,
            detail=f"Artifact {request.draft_artifact_id} is not a draft (type={draft_row[1]})"
        )
    
    # Verify draft version exists and belongs to artifact
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
    
    if str(version_row[1]) != request.draft_artifact_id:
        raise HTTPException(
            status_code=400,
            detail=f"Version {request.draft_artifact_version_id} does not belong to draft {request.draft_artifact_id}"
        )
    
    # Start DraftFinalizationWorkflow
    from temporalio.client import Client as TemporalClient
    _ensure_worker_path()
    from draft_finalization_workflow import DraftFinalizationWorkflow  # noqa: F401
    
    try:
        temporal_client = await TemporalClient.connect("localhost:7233")
        
        workflow_id = f"finalize-draft-{workspace_id_str}-{request.draft_artifact_version_id}-{uuid.uuid4()}"
        
        workflow_handle = await temporal_client.start_workflow(
            DraftFinalizationWorkflow.run,
            args=[workspace_id_str, request.draft_artifact_id, request.draft_artifact_version_id],
            id=workflow_id,
            task_queue="agora-orchestrator",
        )
        
        # Record workflow run
        workflow_run_id = str(uuid.uuid4())
        db.execute(
            """
            INSERT INTO workflow_runs (id, workspace_id, workflow_type, temporal_workflow_id, status)
            VALUES (:id, :workspace_id, :workflow_type, :temporal_workflow_id, :status)
            """,
            {
                "id": workflow_run_id,
                "workspace_id": workspace_id_str,
                "workflow_type": "draft_finalization",
                "temporal_workflow_id": workflow_id,
                "status": "running"
            }
        )
        
        db.commit()
        
        return FinalizeDraftResponse(
            request_id=workflow_run_id,
            draft_artifact_id=request.draft_artifact_id,
            draft_artifact_version_id=request.draft_artifact_version_id,
            message=f"Draft finalization workflow started: {workflow_id}"
        )
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to start finalization workflow: {str(e)}")
