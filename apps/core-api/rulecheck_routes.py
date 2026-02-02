"""
Rule Check Routes (Component 13)

Per spec §4.11:
- POST /rule-checks (SYSTEM-ONLY): Materialized by validators
- GET /rule-checks: Filterable by workspace_id, rule_name, target_type, target_id, status
- POST /workspaces/{id}/requests/run_rulecheck: Agent-facing endpoint to trigger check
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from database import DBWrapper, get_db
from auth_middleware import require_agent_token, require_system_token


router = APIRouter()


# Request/Response Models

class CreateRuleCheckRequest(BaseModel):
    """Request to create a rule check (SYSTEM-ONLY)."""
    rule_name: str = Field(..., description="Name of the rule (e.g., citation_coverage, citation_resolves)")
    target_type: str = Field(..., description="Type of target (e.g., draft_version, workspace)")
    target_id: str = Field(..., description="UUID of the target")
    target_location: Optional[str] = Field(None, description="Optional location within target")
    status: str = Field(..., description="Status: pass or fail")
    details: Optional[Dict[str, Any]] = Field(None, description="Rule-specific details")


class RuleCheckResponse(BaseModel):
    """Response for a rule check."""
    id: str
    workspace_id: str
    rule_name: str
    target_type: str
    target_id: str
    target_location: Optional[str]
    status: str
    details: Optional[Dict[str, Any]]
    created_at: datetime


class RunRuleCheckRequest(BaseModel):
    """Request to run rule check on a draft version."""
    draft_artifact_version_id: str = Field(..., description="UUID of draft version to check")


class RunRuleCheckResponse(BaseModel):
    """Response for run rule check request."""
    request_id: str
    draft_artifact_version_id: str
    status: str
    message: str


# Dependency Functions

def get_storage():
    """Dependency to get storage client."""
    from storage import create_storage_from_env
    return create_storage_from_env()


# Endpoints

@router.post("/rule-checks", response_model=RuleCheckResponse, tags=["Rule Checks"])
def create_rule_check(
    request: CreateRuleCheckRequest,
    system_token: dict = Depends(require_system_token),
    db: DBWrapper = Depends(get_db)
):
    """
    Create a rule check record (SYSTEM-ONLY).
    
    Per spec §4.11: Materialized by validators (citation_check, critique sufficiency checks, etc.)
    """
    # Get workspace_id from target
    if request.target_type == "draft_version":
        workspace_row = db.execute(
            """
            SELECT a.workspace_id
            FROM artifact_versions av
            JOIN artifacts a ON av.artifact_id = a.id
            WHERE av.id = :target_id
            """,
            {"target_id": request.target_id}
        ).fetchone()
        
        if not workspace_row:
            raise HTTPException(status_code=404, detail=f"Target {request.target_type} {request.target_id} not found")
        
        workspace_id = workspace_row[0]
    
    elif request.target_type == "workspace":
        workspace_id = request.target_id
        # Verify workspace exists
        ws_row = db.execute(
            "SELECT id FROM workspaces WHERE id = :id",
            {"id": workspace_id}
        ).fetchone()
        if not ws_row:
            raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
    
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported target_type: {request.target_type}")
    
    # Create rule check
    rule_check_id = str(uuid.uuid4())
    
    import json
    details_json = json.dumps(request.details) if request.details else None
    
    db.execute(
        """
        INSERT INTO rule_checks (
            id,
            workspace_id,
            rule_name,
            target_type,
            target_id,
            target_location,
            status,
            details
        ) VALUES (
            :id,
            :workspace_id,
            :rule_name,
            :target_type,
            :target_id,
            :target_location,
            :status,
            :details
        )
        """,
        {
            "id": rule_check_id,
            "workspace_id": workspace_id,
            "rule_name": request.rule_name,
            "target_type": request.target_type,
            "target_id": request.target_id,
            "target_location": request.target_location,
            "status": request.status,
            "details": details_json
        }
    )
    
    db.commit()
    
    # Fetch and return
    row = db.execute(
        """
        SELECT id, workspace_id, rule_name, target_type, target_id, target_location,
               status, details, created_at
        FROM rule_checks
        WHERE id = :id
        """,
        {"id": rule_check_id}
    ).fetchone()
    
    details_obj = json.loads(row[7]) if row[7] else None
    
    return RuleCheckResponse(
        id=row[0],
        workspace_id=row[1],
        rule_name=row[2],
        target_type=row[3],
        target_id=row[4],
        target_location=row[5],
        status=row[6],
        details=details_obj,
        created_at=row[8]
    )


@router.get("/rule-checks", response_model=List[RuleCheckResponse], tags=["Rule Checks"])
def list_rule_checks(
    workspace_id: Optional[str] = Query(None, description="Filter by workspace_id"),
    rule_name: Optional[str] = Query(None, description="Filter by rule_name"),
    target_type: Optional[str] = Query(None, description="Filter by target_type"),
    target_id: Optional[str] = Query(None, description="Filter by target_id"),
    status: Optional[str] = Query(None, description="Filter by status (pass/fail)"),
    current_agent: dict = Depends(require_agent_token),
    db: DBWrapper = Depends(get_db)
):
    """
    List rule checks with optional filters.
    
    Per spec §4.11: Filters by workspace_id, rule_name, target_type, target_id, status
    """
    # Build query
    conditions = []
    params = {}
    
    if workspace_id:
        conditions.append("workspace_id = :workspace_id")
        params["workspace_id"] = workspace_id
    
    if rule_name:
        conditions.append("rule_name = :rule_name")
        params["rule_name"] = rule_name
    
    if target_type:
        conditions.append("target_type = :target_type")
        params["target_type"] = target_type
    
    if target_id:
        conditions.append("target_id = :target_id")
        params["target_id"] = target_id
    
    if status:
        conditions.append("status = :status")
        params["status"] = status
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    query = f"""
        SELECT id, workspace_id, rule_name, target_type, target_id, target_location,
               status, details, created_at
        FROM rule_checks
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT 100
    """
    
    rows = db.execute(query, params).fetchall()
    
    import json
    results = []
    for row in rows:
        details_obj = json.loads(row[7]) if row[7] else None
        results.append(RuleCheckResponse(
            id=row[0],
            workspace_id=row[1],
            rule_name=row[2],
            target_type=row[3],
            target_id=row[4],
            target_location=row[5],
            status=row[6],
            details=details_obj,
            created_at=row[8]
        ))
    
    return results


@router.post("/workspaces/{workspace_id}/requests/run_rulecheck", response_model=RunRuleCheckResponse, tags=["Request Actions"])
def request_run_rulecheck(
    workspace_id: uuid.UUID,
    request: RunRuleCheckRequest,
    current_agent: dict = Depends(require_agent_token),
    db: DBWrapper = Depends(get_db)
):
    """
    Agent-facing endpoint to request rule check on a draft version.
    
    Per spec §4.15: POST /workspaces/{id}/requests/run_rulecheck
    Triggers citation_check activity via Temporal workflow.
    
    For MVP, this runs the check synchronously. In production, this would
    start a Temporal workflow and return a tracking ID.
    """
    workspace_id_str = str(workspace_id)
    
    # Verify workspace exists
    ws_row = db.execute(
        "SELECT id, phase FROM workspaces WHERE id = :id",
        {"id": workspace_id_str}
    ).fetchone()
    
    if not ws_row:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id_str} not found")
    
    # Verify draft version exists and belongs to workspace
    version_row = db.execute(
        """
        SELECT av.id, a.workspace_id, a.type
        FROM artifact_versions av
        JOIN artifacts a ON av.artifact_id = a.id
        WHERE av.id = :version_id
        """,
        {"version_id": request.draft_artifact_version_id}
    ).fetchone()
    
    if not version_row:
        raise HTTPException(
            status_code=404,
            detail=f"Draft version {request.draft_artifact_version_id} not found"
        )
    
    if version_row[1] != workspace_id_str:
        raise HTTPException(
            status_code=403,
            detail=f"Draft version {request.draft_artifact_version_id} does not belong to workspace {workspace_id_str}"
        )
    
    if version_row[2] != "draft":
        raise HTTPException(
            status_code=400,
            detail=f"Artifact version {request.draft_artifact_version_id} is not a draft (type={version_row[2]})"
        )
    
    # Run citation check activity
    from citation_check import citation_check_activity
    
    try:
        result = citation_check_activity(request.draft_artifact_version_id, db)
        
        # Generate request ID for tracking
        request_id = str(uuid.uuid4())
        
        # Determine overall status
        if result.coverage_pass and result.resolves_pass:
            status = "passed"
            message = f"Citation check passed. {result.citations_materialized} citations materialized."
        else:
            status = "failed"
            failures = []
            if not result.coverage_pass:
                failures.append(f"{len(result.coverage_failures)} coverage failures")
            if not result.resolves_pass:
                failures.append(f"{len(result.resolves_failures)} resolution failures")
            message = f"Citation check failed: {', '.join(failures)}"
        
        return RunRuleCheckResponse(
            request_id=request_id,
            draft_artifact_version_id=request.draft_artifact_version_id,
            status=status,
            message=message
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Citation check failed: {str(e)}")
