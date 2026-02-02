"""
Exit tests for Component 11: Claims + Evidence with Validation

Per checklist:
- EXIT TEST 1: Evidence add fails if location doesn't resolve
- EXIT TEST 2: Evidence add fails if version is from another workspace

Tests run against real containers (Postgres, MinIO, not mocked).
"""
import io
import json
import pytest
import uuid
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


@pytest.fixture
def workspace_with_agent(db_session):
    """Create test workspace and agent."""
    from database import Workspace, Agent
    
    ws = Workspace(
        id=str(uuid.uuid4()),
        name="Claims Test Workspace",
        phase="literature_review"
    )
    db_session.add(ws)
    
    agent = Agent(
        id=str(uuid.uuid4()),
        moltbook_identity="test_agent_claims",
        display_name="Test Agent",
        reputation_score=100
    )
    db_session.add(agent)
    db_session.commit()
    
    return ws, agent


@pytest.fixture
def pdf_artifact_with_evidence(storage, db_session, workspace_with_agent):
    """Create a PDF artifact with resolvable evidence."""
    from database import Artifact, ArtifactVersion
    import hashlib
    
    ws, agent = workspace_with_agent
    
    # Create artifact
    art = Artifact(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        short_id="A1",
        content_type="application/pdf",
        created_by=agent.id
    )
    db_session.add(art)
    
    # Generate PDF
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawString(100, 750, "This PDF contains evidence for claim validation testing.")
    c.showPage()
    c.save()
    buffer.seek(0)
    pdf_bytes = buffer.read()
    
    # Store PDF binary
    binary_key = f"{ws.id}/artifacts/{art.id}/v1/document.pdf"
    storage.put_object("agora", binary_key, pdf_bytes)
    
    # Store extracted text
    page1_text = "This PDF contains evidence for claim validation testing."
    page1_key = f"{ws.id}/artifacts/{art.id}/v1/pages/page_1.txt"
    storage.put_object("agora", page1_key, page1_text.encode("utf-8"))
    
    # Store metadata
    metadata = {"page_count": 1, "total_chars": len(page1_text)}
    metadata_key = f"{ws.id}/artifacts/{art.id}/v1/metadata.json"
    storage.put_object("agora", metadata_key, json.dumps(metadata).encode("utf-8"))
    
    # Create artifact_version
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()
    version = ArtifactVersion(
        id=f"{art.id}_v1",
        artifact_id=art.id,
        version=1,
        content_hash=content_hash,
        size_bytes=len(pdf_bytes),
        location=f"s3://agora/{ws.id}/artifacts/{art.id}/v1/",
        created_by=agent.id
    )
    db_session.add(version)
    db_session.commit()
    
    return {
        "workspace": ws,
        "agent": agent,
        "artifact": art,
        "version": version,
        "page1_text": page1_text
    }


@pytest.fixture
def other_workspace_artifact(storage, db_session):
    """Create an artifact in a different workspace."""
    from database import Workspace, Agent, Artifact, ArtifactVersion
    import hashlib
    
    # Create different workspace
    other_ws = Workspace(
        id=str(uuid.uuid4()),
        name="Other Workspace",
        phase="ingestion"
    )
    db_session.add(other_ws)
    
    agent = Agent(
        id=str(uuid.uuid4()),
        moltbook_identity="other_agent",
        display_name="Other Agent",
        reputation_score=50
    )
    db_session.add(agent)
    
    # Create artifact
    art = Artifact(
        id=str(uuid.uuid4()),
        workspace_id=other_ws.id,
        short_id="B1",
        content_type="application/pdf",
        created_by=agent.id
    )
    db_session.add(art)
    
    # Generate PDF
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawString(100, 750, "This is from another workspace.")
    c.showPage()
    c.save()
    buffer.seek(0)
    pdf_bytes = buffer.read()
    
    # Store PDF
    binary_key = f"{other_ws.id}/artifacts/{art.id}/v1/document.pdf"
    storage.put_object("agora", binary_key, pdf_bytes)
    
    # Store extracted text
    page1_text = "This is from another workspace."
    page1_key = f"{other_ws.id}/artifacts/{art.id}/v1/pages/page_1.txt"
    storage.put_object("agora", page1_key, page1_text.encode("utf-8"))
    
    # Store metadata
    metadata = {"page_count": 1, "total_chars": len(page1_text)}
    metadata_key = f"{other_ws.id}/artifacts/{art.id}/v1/metadata.json"
    storage.put_object("agora", metadata_key, json.dumps(metadata).encode("utf-8"))
    
    # Create artifact_version
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()
    version = ArtifactVersion(
        id=f"{art.id}_v1",
        artifact_id=art.id,
        version=1,
        content_hash=content_hash,
        size_bytes=len(pdf_bytes),
        location=f"s3://agora/{other_ws.id}/artifacts/{art.id}/v1/",
        created_by=agent.id
    )
    db_session.add(version)
    db_session.commit()
    
    return {
        "workspace": other_ws,
        "artifact": art,
        "version": version
    }


def test_create_claim(db_session, workspace_with_agent):
    """Test basic claim creation."""
    from database import Claim
    from claim_routes import create_claim, CreateClaimRequest
    from unittest.mock import MagicMock
    
    ws, agent = workspace_with_agent
    
    # Mock current_agent
    mock_agent = {"agent_id": agent.id}
    
    # Create claim via route function
    request = CreateClaimRequest(
        kind="fact",
        text="Machine learning models can generalize from training data.",
        confidence="high"
    )
    
    # Create mock DB wrapper
    class DBWrapper:
        def __init__(self, session):
            self._session = session
    
    db_wrapper = DBWrapper(db_session)
    
    result = create_claim(
        workspace_id=uuid.UUID(ws.id),
        request=request,
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    # Verify claim created
    assert result.workspace_id == ws.id
    assert result.kind == "fact"
    assert result.text == request.text
    assert result.confidence == "high"
    assert result.is_key is False  # System-owned
    assert result.status == "active"
    assert len(result.evidence) == 0
    
    # Verify in database
    claim = db_session.query(Claim).filter_by(id=result.id).first()
    assert claim is not None
    assert claim.text == request.text


def test_add_evidence_with_valid_location(db_session, pdf_artifact_with_evidence):
    """Test adding evidence with valid location."""
    from database import Claim, ClaimEvidence
    from claim_routes import create_claim, add_evidence_to_claim, CreateClaimRequest, AddEvidenceRequest
    from storage import create_storage_from_env
    
    data = pdf_artifact_with_evidence
    ws = data["workspace"]
    agent = data["agent"]
    version = data["version"]
    page1_text = data["page1_text"]
    
    # Create claim
    claim = Claim(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        kind="fact",
        text="Test claim",
        status="active",
        created_by=agent.id
    )
    db_session.add(claim)
    db_session.commit()
    
    # Mock current_agent and db wrapper
    mock_agent = {"agent_id": agent.id}
    
    class DBWrapper:
        def __init__(self, session):
            self._session = session
    
    db_wrapper = DBWrapper(db_session)
    storage = create_storage_from_env()
    
    # Add evidence with valid location
    search_str = "evidence"
    start_idx = page1_text.find(search_str)
    end_idx = start_idx + len(search_str)
    
    request = AddEvidenceRequest(
        artifact_version_id=version.id,
        location=f"pdf:p=1#char={start_idx}-{end_idx}"
    )
    
    result = add_evidence_to_claim(
        claim_id=uuid.UUID(claim.id),
        request=request,
        current_agent=mock_agent,
        db=db_wrapper,
        storage=storage
    )
    
    # Verify evidence created
    assert result["claim_id"] == claim.id
    assert result["artifact_version_id"] == version.id
    assert "resolved_snippet" in result
    assert search_str in result["resolved_snippet"]
    
    # Verify in database
    evidence = db_session.query(ClaimEvidence).filter_by(claim_id=claim.id).first()
    assert evidence is not None
    assert evidence.artifact_version_id == version.id


def test_exit_1_evidence_fails_if_location_doesnt_resolve(db_session, pdf_artifact_with_evidence):
    """
    EXIT TEST 1: Evidence add fails if location doesn't resolve.
    
    Success criteria:
    - Returns 422 status
    - Returns error code from resolver (PAGE_OUT_OF_RANGE, CHAR_RANGE_INVALID, etc.)
    - Error message is actionable
    """
    from database import Claim
    from claim_routes import add_evidence_to_claim, AddEvidenceRequest
    from storage import create_storage_from_env
    from fastapi import HTTPException
    
    data = pdf_artifact_with_evidence
    ws = data["workspace"]
    agent = data["agent"]
    version = data["version"]
    
    # Create claim
    claim = Claim(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        kind="fact",
        text="Test claim",
        status="active",
        created_by=agent.id
    )
    db_session.add(claim)
    db_session.commit()
    
    # Mock dependencies
    mock_agent = {"agent_id": agent.id}
    
    class DBWrapper:
        def __init__(self, session):
            self._session = session
    
    db_wrapper = DBWrapper(db_session)
    storage = create_storage_from_env()
    
    # Test 1: Page out of range
    request1 = AddEvidenceRequest(
        artifact_version_id=version.id,
        location="pdf:p=999#char=0-10"  # Page 999 doesn't exist
    )
    
    with pytest.raises(HTTPException) as exc_info1:
        add_evidence_to_claim(
            claim_id=uuid.UUID(claim.id),
            request=request1,
            current_agent=mock_agent,
            db=db_wrapper,
            storage=storage
        )
    
    assert exc_info1.value.status_code == 422
    assert exc_info1.value.detail["ok"] is False
    assert exc_info1.value.detail["code"] == "PAGE_OUT_OF_RANGE"
    
    # Test 2: Invalid char range
    request2 = AddEvidenceRequest(
        artifact_version_id=version.id,
        location="pdf:p=1#char=100-50"  # end < start
    )
    
    with pytest.raises(HTTPException) as exc_info2:
        add_evidence_to_claim(
            claim_id=uuid.UUID(claim.id),
            request=request2,
            current_agent=mock_agent,
            db=db_wrapper,
            storage=storage
        )
    
    assert exc_info2.value.status_code == 422
    assert exc_info2.value.detail["code"] == "CHAR_RANGE_INVALID"
    
    # Test 3: Char range exceeds content
    request3 = AddEvidenceRequest(
        artifact_version_id=version.id,
        location="pdf:p=1#char=0-999999"  # Beyond text length
    )
    
    with pytest.raises(HTTPException) as exc_info3:
        add_evidence_to_claim(
            claim_id=uuid.UUID(claim.id),
            request=request3,
            current_agent=mock_agent,
            db=db_wrapper,
            storage=storage
        )
    
    assert exc_info3.value.status_code == 422
    assert exc_info3.value.detail["code"] == "CHAR_RANGE_INVALID"


def test_exit_2_evidence_fails_if_version_from_another_workspace(
    db_session, 
    pdf_artifact_with_evidence, 
    other_workspace_artifact
):
    """
    EXIT TEST 2: Evidence add fails if version is from another workspace.
    
    Success criteria:
    - Returns 422 status
    - Returns WORKSPACE_MISMATCH error code
    - Prevents cross-workspace evidence contamination
    """
    from database import Claim
    from claim_routes import add_evidence_to_claim, AddEvidenceRequest
    from storage import create_storage_from_env
    from fastapi import HTTPException
    
    data = pdf_artifact_with_evidence
    ws = data["workspace"]
    agent = data["agent"]
    
    other_data = other_workspace_artifact
    other_version = other_data["version"]
    
    # Create claim in first workspace
    claim = Claim(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        kind="fact",
        text="Test claim",
        status="active",
        created_by=agent.id
    )
    db_session.add(claim)
    db_session.commit()
    
    # Mock dependencies
    mock_agent = {"agent_id": agent.id}
    
    class DBWrapper:
        def __init__(self, session):
            self._session = session
    
    db_wrapper = DBWrapper(db_session)
    storage = create_storage_from_env()
    
    # Try to add evidence from different workspace
    request = AddEvidenceRequest(
        artifact_version_id=other_version.id,
        location="pdf:p=1#char=0-10"
    )
    
    with pytest.raises(HTTPException) as exc_info:
        add_evidence_to_claim(
            claim_id=uuid.UUID(claim.id),
            request=request,
            current_agent=mock_agent,
            db=db_wrapper,
            storage=storage
        )
    
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["ok"] is False
    assert exc_info.value.detail["code"] == "WORKSPACE_MISMATCH"
    assert "not in the same workspace" in exc_info.value.detail["message"]


def test_list_claims_with_evidence(db_session, pdf_artifact_with_evidence):
    """Test listing claims with their evidence."""
    from database import Claim, ClaimEvidence
    from claim_routes import list_claims
    
    data = pdf_artifact_with_evidence
    ws = data["workspace"]
    agent = data["agent"]
    version = data["version"]
    
    # Create claims with evidence
    claim1 = Claim(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        kind="fact",
        text="First claim",
        status="active",
        created_by=agent.id
    )
    claim2 = Claim(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        kind="hypothesis",
        text="Second claim",
        confidence="medium",
        status="active",
        created_by=agent.id
    )
    db_session.add_all([claim1, claim2])
    
    # Add evidence to claim1
    evidence1 = ClaimEvidence(
        id=str(uuid.uuid4()),
        claim_id=claim1.id,
        artifact_version_id=version.id,
        location="pdf:p=1#char=0-10"
    )
    evidence2 = ClaimEvidence(
        id=str(uuid.uuid4()),
        claim_id=claim1.id,
        artifact_version_id=version.id,
        location="pdf:p=1#char=20-30"
    )
    db_session.add_all([evidence1, evidence2])
    db_session.commit()
    
    # Mock dependencies
    mock_agent = {"agent_id": agent.id}
    
    class DBWrapper:
        def __init__(self, session):
            self._session = session
    
    db_wrapper = DBWrapper(db_session)
    
    # List claims
    result = list_claims(
        workspace_id=uuid.UUID(ws.id),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    # Verify results
    assert result["workspace_id"] == ws.id
    assert result["total"] == 2
    assert len(result["claims"]) == 2
    
    # Find claim1 in results
    claim1_result = next(c for c in result["claims"] if c["id"] == claim1.id)
    assert len(claim1_result["evidence"]) == 2
    
    # Find claim2 in results
    claim2_result = next(c for c in result["claims"] if c["id"] == claim2.id)
    assert len(claim2_result["evidence"]) == 0


def test_claim_kind_defaults_to_fact(db_session, workspace_with_agent):
    """Test that claim kind defaults to 'fact' if not specified."""
    from database import Claim
    from claim_routes import create_claim, CreateClaimRequest
    
    ws, agent = workspace_with_agent
    
    # Create claim without kind
    request = CreateClaimRequest(text="Test claim without kind")
    
    mock_agent = {"agent_id": agent.id}
    
    class DBWrapper:
        def __init__(self, session):
            self._session = session
    
    db_wrapper = DBWrapper(db_session)
    
    result = create_claim(
        workspace_id=uuid.UUID(ws.id),
        request=request,
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    assert result.kind == "fact"  # Default value


def test_is_key_cannot_be_set_by_agent(db_session, workspace_with_agent):
    """Test that is_key is always False for agent-created claims (system-owned)."""
    from claim_routes import create_claim, CreateClaimRequest
    
    ws, agent = workspace_with_agent
    
    request = CreateClaimRequest(
        kind="fact",
        text="Test claim"
    )
    
    mock_agent = {"agent_id": agent.id}
    
    class DBWrapper:
        def __init__(self, session):
            self._session = session
    
    db_wrapper = DBWrapper(db_session)
    
    result = create_claim(
        workspace_id=uuid.UUID(ws.id),
        request=request,
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    # is_key should always be False (system-owned)
    assert result.is_key is False
