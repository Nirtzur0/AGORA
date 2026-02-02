"""
Claims and Evidence API Routes - Component 11

Endpoints per Docs/04 §4.9:
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

from auth_middleware import get_current_agent
from evidence_resolver import create_resolver
from storage import get_storage
from database import get_db, Claim, ClaimEvidence, ArtifactVersion, Workspace


router = APIRouter(tags=["Claims"])


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
    current_agent: Dict[str, Any] = Depends(get_current_agent),
    db = Depends(get_db)
) -> ClaimResponse:
    """
    Create a new claim in a workspace.
    
    Claims are created without evidence initially.
    Evidence is added via POST /claims/{id}/evidence.
    """
    # Verify workspace exists
    workspace = db._session.query(Workspace).filter_by(id=str(workspace_id)).first()
    if not workspace:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
    
    # Create claim
    claim = Claim(
        id=uuid.uuid4(),
        workspace_id=str(workspace_id),
        kind=request.kind,
        text=request.text,
        confidence=request.confidence,
        is_key=False,  # System-owned, not settable by agents
        status="active",
        created_by=current_agent.get("agent_id")
    )
    
    db._session.add(claim)
    db._session.commit()
    db._session.refresh(claim)
    
    return ClaimResponse(
        id=str(claim.id),
        workspace_id=str(claim.workspace_id),
        kind=claim.kind,
        text=claim.text,
        confidence=claim.confidence,
        is_key=claim.is_key,
        status=claim.status,
        created_by=str(claim.created_by) if claim.created_by else None,
        created_at=claim.created_at.isoformat(),
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
    current_agent: Dict[str, Any] = Depends(get_current_agent),
    db = Depends(get_db),
    storage = Depends(get_storage)
) -> Dict[str, Any]:
    """
    Add evidence pointer to a claim with full validation.
    
    Per spec: Core API MUST validate (artifact_version_id, location) is
    syntactically valid and resolvable to a real span/snippet.
    """
    # Verify claim exists
    claim = db._session.query(Claim).filter_by(id=str(claim_id)).first()
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    
    # Verify artifact_version exists
    artifact_version = db._session.query(ArtifactVersion).filter_by(
        id=request.artifact_version_id
    ).first()
    if not artifact_version:
        raise HTTPException(
            status_code=422,
            detail={
                "ok": False,
                "code": "ARTIFACT_VERSION_NOT_FOUND",
                "message": f"Artifact version {request.artifact_version_id} not found"
            }
        )
    
    # Verify artifact_version is in same workspace as claim
    from database import Artifact
    artifact = db._session.query(Artifact).filter_by(id=artifact_version.artifact_id).first()
    if not artifact or str(artifact.workspace_id) != str(claim.workspace_id):
        raise HTTPException(
            status_code=422,
            detail={
                "ok": False,
                "code": "WORKSPACE_MISMATCH",
                "message": f"Artifact version {request.artifact_version_id} is not in the same workspace as claim {claim_id}"
            }
        )
    
    # Validate location resolves (per spec: recommended to prevent junk evidence pointers)
    resolver = create_resolver(storage, db._session)
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
    
    # Create evidence link
    evidence = ClaimEvidence(
        id=uuid.uuid4(),
        claim_id=str(claim_id),
        artifact_version_id=request.artifact_version_id,
        location=request.location
    )
    
    db._session.add(evidence)
    db._session.commit()
    db._session.refresh(evidence)
    
    return {
        "id": str(evidence.id),
        "claim_id": str(evidence.claim_id),
        "artifact_version_id": evidence.artifact_version_id,
        "location": evidence.location,
        "resolved_snippet": resolution_result.snippet[:200] + "..." if len(resolution_result.snippet) > 200 else resolution_result.snippet
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
    current_agent: Dict[str, Any] = Depends(get_current_agent),
    db = Depends(get_db)
) -> Dict[str, Any]:
    """
    List all claims in a workspace with their evidence.
    """
    # Verify workspace exists
    workspace = db._session.query(Workspace).filter_by(id=str(workspace_id)).first()
    if not workspace:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
    
    # Get all claims
    claims = db._session.query(Claim).filter_by(workspace_id=str(workspace_id)).all()
    
    # Build response
    claims_data = []
    for claim in claims:
        # Get evidence for this claim
        evidence_list = db._session.query(ClaimEvidence).filter_by(claim_id=str(claim.id)).all()
        
        evidence_data = [
            {
                "id": str(ev.id),
                "artifact_version_id": ev.artifact_version_id,
                "location": ev.location
            }
            for ev in evidence_list
        ]
        
        claims_data.append(
            ClaimResponse(
                id=str(claim.id),
                workspace_id=str(claim.workspace_id),
                kind=claim.kind,
                text=claim.text,
                confidence=claim.confidence,
                is_key=claim.is_key,
                status=claim.status,
                created_by=str(claim.created_by) if claim.created_by else None,
                created_at=claim.created_at.isoformat(),
                evidence=evidence_data
            )
        )
    
    return {
        "workspace_id": str(workspace_id),
        "claims": [claim.dict() for claim in claims_data],
        "total": len(claims_data)
    }
