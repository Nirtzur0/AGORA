"""
Evidence Resolution API Routes - Component 10

GET /evidence/resolve endpoint per Docs/04 §5.8.

This endpoint is the canonical evidence pointer resolver used by:
- Agents (to validate citations before submission)
- UI (click-to-evidence functionality)
- citation_check validation
- claim-evidence validation
"""
from fastapi import APIRouter, Query, Depends, HTTPException
from typing import Dict, Any

from auth_middleware import get_current_agent_or_system
from evidence_resolver import create_resolver
from storage import get_storage
from database import get_db


router = APIRouter(prefix="/evidence", tags=["Evidence Resolution"])


@router.get(
    "/resolve",
    summary="Resolve evidence pointer to text snippet",
    description="""
    Canonical evidence pointer resolver per §5.8.
    
    Takes an artifact_version_id and location string, returns the resolved text snippet.
    
    Supported location formats:
    - pdf:p={page}#char={start}-{end}
    - repo:path={path}#L{start}-L{end}
    - log:jsonpath={jsonpath}
    - log:char={start}-{end}
    
    Returns:
    - 200: {ok: true, snippet: "...", normalized_location: "...", ...}
    - 422: {ok: false, code: "...", message: "..."}
    
    Used by agents, UI, citation_check, and claim-evidence validation.
    """
)
def resolve_evidence(
    artifact_version_id: str = Query(..., description="UUID of artifact_versions.id"),
    location: str = Query(..., description="Location string (pdf:..., repo:..., log:...)"),
    current_user: Dict[str, Any] = Depends(get_current_agent_or_system),
    db = Depends(get_db),
    storage = Depends(get_storage)
) -> Dict[str, Any]:
    """
    Resolve an evidence pointer to a text snippet.
    
    This is the single source of truth for evidence resolution.
    All citation checks and claim-evidence validation MUST use this endpoint
    to ensure deterministic resolution.
    """
    # Create resolver
    resolver = create_resolver(storage, db)
    
    # Resolve evidence
    result = resolver.resolve(artifact_version_id, location)
    
    # Check if resolution succeeded
    if not result.ok:
        # Return 422 with error details per spec
        raise HTTPException(
            status_code=422,
            detail=result.to_dict()
        )
    
    # Return success response
    return result.to_dict()
