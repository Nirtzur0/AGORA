"""
Claims and Evidence API Routes - Component 11

Endpoints per `Docs/manifest/04_api_contracts.md`:
- POST /workspaces/{id}/claims
- POST /claims/{id}/evidence
- GET /workspaces/{id}/claims

Claims are always grounded or explicitly fail.
All evidence pointers MUST be validated and resolvable.
"""
from fastapi import APIRouter, Depends, HTTPException, Path, Body
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from uuid import UUID
import uuid

from auth_middleware import get_current_agent, AgentContext
from evidence_resolver import create_resolver
from storage import create_storage_from_env
from database import get_db_session


router = APIRouter(tags=["Claims"])

# Storage dependency
def get_storage():
    """Dependency to get storage instance."""
    return create_storage_from_env()

def _agent_id(current_agent: AgentContext) -> str:
    if isinstance(current_agent, dict):
        return str(current_agent.get("agent_id"))
    return str(current_agent.agent_id)


# Request/Response Models

class CreateClaimRequest(BaseModel):
    """Request to create a claim."""
    kind: str = Field(default="fact", description="Claim kind (fact, hypothesis, conclusion)")
    text: str = Field(..., description="Claim text")
    confidence: Optional[str] = Field(None, description="Confidence level (high, medium, low)")


class AddEvidenceRequest(BaseModel):
    """Request to add evidence to a claim."""
    artifact_version_id: str = Field(..., description="UUID of artifact_versions.id")
    location: str = Field(..., description="Evidence location (pdf:p=1#char=0-10, etc.)")


class ClaimResponse(BaseModel):
    """Claim response."""
    id: str
    workspace_id: str
    kind: str
    text: str
    confidence: Optional[str]
    is_key: bool
    status: str
    created_by: Optional[str]
    created_at: str
    evidence: List[Dict[str, Any]] = []


# Endpoints

@router.post(
    "/workspaces/{workspace_id}/claims",
    status_code=201,
    summary="Create a claim",
    description="""
    Create a new claim in a workspace per §4.9.
    
    Claims can be of different kinds:
    - fact: A factual statement
    - hypothesis: A proposed explanation
    - conclusion: A derived conclusion
    
    Note: is_key is system-owned and cannot be set by agents.
    """
)
def create_claim(
    workspace_id: UUID = Path(..., description="Workspace ID"),
    request: CreateClaimRequest = Body(...),
    current_agent: AgentContext = Depends(get_current_agent),
    db = Depends(get_db_session)
) -> ClaimResponse:
    """
    Create a new claim in a workspace.
    
    Claims are created without evidence initially.
    Evidence is added via POST /claims/{id}/evidence.
    """
    # Verify workspace exists
    result = db.execute(
        "SELECT id FROM workspaces WHERE id = %s",
        (str(workspace_id),)
    )
    workspace = result.fetchone()
    if not workspace:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
    
    # Create claim
    claim_id = str(uuid.uuid4())
    created_at = db.execute("SELECT NOW()").fetchone()[0]
    
    db.execute(
        """
        INSERT INTO claims (id, workspace_id, kind, text, confidence, is_key, status, created_by, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            claim_id,
            str(workspace_id),
            request.kind,
            request.text,
            request.confidence,
            False,  # is_key is system-owned, not settable by agents
            "active",
            _agent_id(current_agent),
            created_at
        )
    )
    
    return ClaimResponse(
        id=claim_id,
        workspace_id=str(workspace_id),
        kind=request.kind,
        text=request.text,
        confidence=request.confidence,
        is_key=False,
        status="active",
        created_by=_agent_id(current_agent),
        created_at=created_at.isoformat(),
        evidence=[]
    )


@router.post(
    "/claims/{claim_id}/evidence",
    status_code=201,
    summary="Add evidence to a claim",
    description="""
    Add evidence pointer to a claim per §4.9.
    
    Validation (MVP):
    - artifact_version_id must exist and be in same workspace as claim
    - location must be syntactically valid
    - location must resolve to a real span/snippet (validated via resolver)
    
    Rejects with 422 and concrete error if validation fails:
    - PAGE_OUT_OF_RANGE
    - CHAR_RANGE_INVALID
    - LINE_RANGE_INVALID
    - PATH_NOT_FOUND
    - UNSUPPORTED_LOCATION
    """
)
def add_evidence_to_claim(
    claim_id: UUID = Path(..., description="Claim ID"),
    request: AddEvidenceRequest = Body(...),
    current_agent: AgentContext = Depends(get_current_agent),
    db = Depends(get_db_session),
    storage = Depends(get_storage)
) -> Dict[str, Any]:
    """
    Add evidence pointer to a claim with full validation.
    
    Per spec: Core API MUST validate (artifact_version_id, location) is
    syntactically valid and resolvable to a real span/snippet.
    """
    # Verify claim exists
    result = db.execute(
        "SELECT workspace_id FROM claims WHERE id = %s",
        (str(claim_id),)
    )
    claim = result.fetchone()
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    
    claim_workspace_id = claim[0]
    
    # Verify artifact_version exists
    result = db.execute(
        "SELECT artifact_id FROM artifact_versions WHERE id = %s",
        (request.artifact_version_id,)
    )
    artifact_version = result.fetchone()
    if not artifact_version:
        raise HTTPException(
            status_code=422,
            detail={
                "ok": False,
                "code": "ARTIFACT_VERSION_NOT_FOUND",
                "message": f"Artifact version {request.artifact_version_id} not found"
            }
        )
    
    artifact_id = artifact_version[0]
    
    # Verify artifact_version is in same workspace as claim
    result = db.execute(
        "SELECT workspace_id FROM artifacts WHERE id = %s",
        (str(artifact_id),)
    )
    artifact = result.fetchone()
    if not artifact or str(artifact[0]) != str(claim_workspace_id):
        raise HTTPException(
            status_code=422,
            detail={
                "ok": False,
                "code": "WORKSPACE_MISMATCH",
                "message": f"Artifact version {request.artifact_version_id} is not in the same workspace as claim {claim_id}"
            }
        )
    
    # Validate location resolves (per spec: recommended to prevent junk evidence pointers)
    resolver = create_resolver(storage, db)
    resolution_result = resolver.resolve(
        artifact_version_id=request.artifact_version_id,
        location=request.location
    )
    
    if not resolution_result.ok:
        # Return 422 with resolver's error details
        raise HTTPException(
            status_code=422,
            detail={
                "ok": False,
                "code": resolution_result.code,
                "message": resolution_result.message
            }
        )
    
    snippet = resolution_result.snippet
    
    # Create evidence link
    evidence_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO claim_evidence (id, claim_id, artifact_version_id, location)
        VALUES (%s, %s, %s, %s)
        """,
        (evidence_id, str(claim_id), request.artifact_version_id, request.location)
    )
    
    return {
        "id": evidence_id,
        "claim_id": str(claim_id),
        "artifact_version_id": request.artifact_version_id,
        "location": request.location,
        "resolved_snippet": snippet[:200] + "..." if len(snippet) > 200 else snippet
    }


@router.get(
    "/workspaces/{workspace_id}/claims",
    summary="List claims for a workspace",
    description="""
    Get all claims for a workspace with linked evidence per §4.9.
    
    Returns claims with their evidence pointers.
    """
)
def list_claims(
    workspace_id: UUID = Path(..., description="Workspace ID"),
    current_agent: AgentContext = Depends(get_current_agent),
    db = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    List all claims in a workspace with their evidence.
    """
    # Verify workspace exists
    result = db.execute(
        "SELECT id FROM workspaces WHERE id = %s",
        (str(workspace_id),)
    )
    workspace = result.fetchone()
    if not workspace:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
    
    # Get all claims
    result = db.execute(
        """
        SELECT id, workspace_id, kind, text, confidence, is_key, status, created_by, created_at
        FROM claims
        WHERE workspace_id = %s
        ORDER BY created_at DESC
        """,
        (str(workspace_id),)
    )
    claims = result.fetchall()
    
    # Build response
    claims_data = []
    for claim in claims:
        claim_id, ws_id, kind, text, confidence, is_key, status, created_by, created_at = claim
        
        # Get evidence for this claim
        evidence_result = db.execute(
            """
            SELECT id, artifact_version_id, location
            FROM claim_evidence
            WHERE claim_id = %s
            """,
            (str(claim_id),)
        )
        evidence_list = evidence_result.fetchall()
        
        evidence_data = [
            {
                "id": str(ev[0]),
                "artifact_version_id": ev[1],
                "location": ev[2]
            }
            for ev in evidence_list
        ]
        
        claims_data.append(
            ClaimResponse(
                id=str(claim_id),
                workspace_id=str(ws_id),
                kind=kind,
                text=text,
                confidence=confidence,
                is_key=is_key,
                status=status,
                created_by=str(created_by) if created_by else None,
                created_at=created_at.isoformat(),
                evidence=evidence_data
            )
        )
    
    return {
        "workspace_id": str(workspace_id),
        "claims": [claim.model_dump() for claim in claims_data],
        "total": len(claims_data)
    }
