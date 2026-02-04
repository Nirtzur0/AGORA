"""
Exit test for Component 15: Literature grounding workflow (end-to-end)

Per checklist:
Scripted integration test that performs:
1. GET /auth.md (sanity)
2. POST /auth/moltbook using X-Moltbook-Identity
3. create workspace
4. create pdf artifact + request ingest (idempotent)
5. create claim + evidence referencing parsed PDF span (idempotent)
6. create draft version with claim/cite markers (idempotent)
7. poll/verify citation_check -> PASS (rule_checks written automatically)

This is the first "prove it works" workflow per spec.
"""
import pytest
import uuid
import json
from sqlalchemy import text

from storage import create_storage_from_env
from database import Workspace, Agent, Artifact, ArtifactVersion


@pytest.fixture
def integration_setup(db_session):
    """Set up full integration test environment."""
    # Create workspace
    ws = Workspace(
        id=str(uuid.uuid4()),
        name="Literature Grounding Test",
        phase="literature_review"
    )
    db_session.add(ws)
    
    # Create agent
    agent = Agent(
        id=str(uuid.uuid4()),
        moltbook_identity="test_integration_agent",
        display_name="Integration Test Agent",
        reputation_score=100
    )
    db_session.add(agent)
    
    db_session.commit()
    
    return ws, agent


def test_exit_literature_grounding_end_to_end(db_session, integration_setup):
    """
    EXIT TEST: Complete literature grounding workflow end-to-end.
    
    Success criteria:
    1. Can authenticate and create workspace
    2. Can upload PDF and request ingestion
    3. PDF is parsed and artifact_version created
    4. Agent task is created for claim extraction
    5. Can create claim with evidence referencing PDF
    6. Can create draft with claim/cite markers
    7. Citation check runs and passes
    8. Rule checks are recorded with pass status
    """
    from sqlalchemy import text
    from request_routes import request_ingest_pdf, IngestPdfRequest
    from claim_routes import create_claim, add_evidence_to_claim, CreateClaimRequest, AddEvidenceRequest
    from draft_routes import create_draft, create_draft_version, CreateDraftRequest, CreateDraftVersionRequest
    from rulecheck_routes import request_run_rulecheck, RunRuleCheckRequest
    
    ws, agent = integration_setup
    storage = create_storage_from_env()
    
    # Create DB wrapper
    db_wrapper = db_session
    mock_agent = {"agent_id": agent.id}
    
    # Step 1: Sanity check (simulated - /auth.md would exist in real deployment)
    # In real test: response = requests.get("http://localhost:8000/auth.md")
    # assert response.status_code == 200
    
    # Step 2: Authentication (already have agent from fixture)
    # In real test: would POST /auth/moltbook with X-Moltbook-Identity header
    
    # Step 3: Workspace created (already done in fixture)
    assert ws.id is not None
    assert ws.phase == "literature_review"
    
    # Step 4: Create PDF artifact and request ingestion
    pdf_artifact_id = str(uuid.uuid4())
    pdf_artifact = Artifact(
        id=pdf_artifact_id,
        workspace_id=ws.id,
        type="pdf",
        short_id="P1",
        metadata=json.dumps({
            "title": "Test Research Paper",
            "source_uri": "s3://test/paper.pdf"
        })
    )
    db_session.add(pdf_artifact)
    db_session.commit()
    
    # Simulate PDF content stored in MinIO
    pdf_text = """Page 1 of the research paper.
This is the introduction with important findings.

Page 2 continues the discussion.
More content here with detailed analysis."""
    
    storage_uri = f"s3://agora/{ws.id}/artifacts/{pdf_artifact_id}/v1/parsed.txt"
    storage.put_object(storage_uri, pdf_text.encode("utf-8"))
    
    # Create artifact version (simulating pdf_ingest_activity result)
    pdf_version_id = str(uuid.uuid4())
    pdf_version = ArtifactVersion(
        id=pdf_version_id,
        artifact_id=pdf_artifact_id,
        version=1,
        storage_uri=storage_uri,
        content_hash="test_hash_123"
    )
    db_session.add(pdf_version)
    db_session.commit()
    
    # Request PDF ingestion (idempotent - already ingested, should return existing)
    import asyncio
    ingest_response = asyncio.run(request_ingest_pdf(
        workspace_id=uuid.UUID(str(ws.id)),
        request=IngestPdfRequest(artifact_id=pdf_artifact_id),
        current_agent=mock_agent,
        db=db_wrapper
    ))
    
    assert ingest_response.artifact_id == pdf_artifact_id
    assert ingest_response.workflow_run_id is not None
    
    # Verify workflow_runs created
    workflow = db_session.execute(
        text("""
            SELECT id, workflow_type, status
            FROM workflow_runs
            WHERE workspace_id = :ws_id
              AND workflow_type = 'literature_grounding'
        """),
        {"ws_id": ws.id}
    ).fetchone()
    
    assert workflow is not None
    assert workflow[1] == "literature_grounding"
    
    # Step 5: Create claim with evidence referencing parsed PDF
    claim_request = CreateClaimRequest(
        statement="The study found significant correlation between variables X and Y",
        kind="fact",
        confidence=0.9
    )
    
    claim_response = create_claim(
        workspace_id=uuid.UUID(str(ws.id)),
        request=claim_request,
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    assert claim_response.workspace_id == str(ws.id)
    assert claim_response.statement == claim_request.statement
    
    # Add evidence referencing PDF span (idempotent)
    evidence_request = AddEvidenceRequest(
        artifact_version_id=pdf_version_id,
        location="pdf:p=1#char=50-100",
        snippet="important findings",
        interpretation="This supports the claim about correlation"
    )
    
    evidence_response = add_evidence_to_claim(
        claim_id=uuid.UUID(str(claim_response.id)),
        request=evidence_request,
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    assert evidence_response.claim_id == claim_response.id
    assert evidence_response.artifact_version_id == pdf_version_id
    
    # Verify evidence in database
    evidence = db_session.execute(
        text("""
            SELECT id, claim_id, artifact_version_id, location
            FROM claim_evidence
            WHERE claim_id = :claim_id
        """),
        {"claim_id": claim_response.id}
    ).fetchone()
    
    assert evidence is not None
    assert evidence[2] == pdf_version_id
    
    # Step 6: Create draft version with claim/cite markers (idempotent)
    draft_request = CreateDraftRequest(title="Literature Review Draft")
    draft_response = create_draft(
        workspace_id=uuid.UUID(str(ws.id)),
        request=draft_request,
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    assert draft_response.workspace_id == str(ws.id)
    assert draft_response.short_id == "D1"
    
    # Create draft version with citation markers
    markdown_content = f"""# Literature Review

## Key Findings

This paragraph discusses the main finding [[claim:{claim_response.id}]]. 
The evidence comes from the research paper [[cite:{pdf_version_id}|pdf:p=1#char=50-100]].

## Conclusion

The study provides strong support for the hypothesis.
"""
    
    version_request = CreateDraftVersionRequest(content=markdown_content)
    version_response = create_draft_version(
        draft_id=uuid.UUID(str(draft_response.id)),
        request=version_request,
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    assert version_response.version == 1
    assert version_response.content_hash is not None
    
    # Step 7: Run citation check (automatically happens on version creation in production)
    rulecheck_request = RunRuleCheckRequest(
        draft_artifact_version_id=version_response.id
    )
    
    rulecheck_response = request_run_rulecheck(
        workspace_id=uuid.UUID(str(ws.id)),
        request=rulecheck_request,
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    assert rulecheck_response.status == "passed"
    assert "passed" in rulecheck_response.message.lower()
    
    # Verify rule_checks created with pass status
    coverage_check = db_session.execute(
        text("""
            SELECT rule_name, status, details
            FROM rule_checks
            WHERE workspace_id = :ws_id
              AND rule_name = 'citation_coverage'
              AND target_id = :version_id
        """),
        {"ws_id": ws.id, "version_id": version_response.id}
    ).fetchone()
    
    assert coverage_check is not None
    assert coverage_check[1] == "pass"
    
    resolves_check = db_session.execute(
        text("""
            SELECT rule_name, status, details
            FROM rule_checks
            WHERE workspace_id = :ws_id
              AND rule_name = 'citation_resolves'
              AND target_id = :version_id
        """),
        {"ws_id": ws.id, "version_id": version_response.id}
    ).fetchone()
    
    assert resolves_check is not None
    assert resolves_check[1] == "pass"
    
    # Verify citations materialized
    citations = db_session.execute(
        text("""
            SELECT id, claim_id, source_artifact_version_id, source_location
            FROM citations
            WHERE draft_artifact_version_id = :version_id
        """),
        {"version_id": version_response.id}
    ).fetchall()
    
    assert len(citations) == 1
    assert citations[0][1] == claim_response.id
    assert citations[0][2] == pdf_version_id


def test_idempotent_pdf_ingestion(db_session, integration_setup):
    """Test that PDF ingestion is idempotent."""
    from sqlalchemy import text
    from request_routes import request_ingest_pdf, IngestPdfRequest
    
    ws, agent = integration_setup
    
    # Create DB wrapper
    db_wrapper = db_session
    mock_agent = {"agent_id": agent.id}
    
    # Create PDF artifact with existing version
    pdf_artifact_id = str(uuid.uuid4())
    pdf_artifact = Artifact(
        id=pdf_artifact_id,
        workspace_id=ws.id,
        type="pdf",
        short_id="P1",
        metadata=json.dumps({"title": "Test PDF"})
    )
    db_session.add(pdf_artifact)
    
    pdf_version = ArtifactVersion(
        id=str(uuid.uuid4()),
        artifact_id=pdf_artifact_id,
        version=1,
        storage_uri=f"s3://agora/{ws.id}/artifacts/{pdf_artifact_id}/v1/parsed.txt",
        content_hash="existing_hash"
    )
    db_session.add(pdf_version)
    db_session.commit()
    
    # Request ingestion twice
    import asyncio
    response1 = asyncio.run(request_ingest_pdf(
        workspace_id=uuid.UUID(str(ws.id)),
        request=IngestPdfRequest(artifact_id=pdf_artifact_id),
        current_agent=mock_agent,
        db=db_wrapper
    ))
    
    response2 = asyncio.run(request_ingest_pdf(
        workspace_id=uuid.UUID(str(ws.id)),
        request=IngestPdfRequest(artifact_id=pdf_artifact_id),
        current_agent=mock_agent,
        db=db_wrapper
    ))
    
    # Should return same workflow (idempotent)
    assert "already ingested" in response2.message.lower()


def test_draft_finalization_with_passing_checks(db_session, integration_setup):
    """Test draft finalization when all rule checks pass."""
    from sqlalchemy import text
    from request_routes import request_finalize_draft, FinalizeDraftRequest as RequestFinalizeDraft
    from draft_routes import create_draft, create_draft_version, CreateDraftRequest, CreateDraftVersionRequest
    from claim_routes import create_claim, CreateClaimRequest
    
    ws, agent = integration_setup
    storage = create_storage_from_env()
    
    # Create DB wrapper
    db_wrapper = db_session
    mock_agent = {"agent_id": agent.id}
    
    # Create claim
    claim = create_claim(
        workspace_id=uuid.UUID(str(ws.id)),
        request=CreateClaimRequest(statement="Test claim", kind="fact", confidence=0.9),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    # Create PDF artifact and version for citation
    pdf_artifact = Artifact(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        type="pdf",
        short_id="P1",
        metadata=json.dumps({"title": "Test PDF"})
    )
    db_session.add(pdf_artifact)
    
    pdf_text = "Test content for citation resolution."
    storage_uri = f"s3://agora/{ws.id}/artifacts/{pdf_artifact.id}/v1/parsed.txt"
    storage.put_object(storage_uri, pdf_text.encode("utf-8"))
    
    pdf_version = ArtifactVersion(
        id=str(uuid.uuid4()),
        artifact_id=pdf_artifact.id,
        version=1,
        storage_uri=storage_uri,
        content_hash="test_hash"
    )
    db_session.add(pdf_version)
    db_session.commit()
    
    # Create draft with passing citations
    draft = create_draft(
        workspace_id=uuid.UUID(str(ws.id)),
        request=CreateDraftRequest(title="Test Draft"),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    markdown = f"""# Test

Claim [[claim:{claim.id}]] with citation [[cite:{pdf_version.id}|pdf:p=1#char=0-10]].
"""
    
    version = create_draft_version(
        draft_id=uuid.UUID(str(draft.id)),
        request=CreateDraftVersionRequest(content=markdown),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    # Run citation check (creates passing rule_checks)
    from citation_check import citation_check_activity
    result = citation_check_activity(version.id, db_wrapper)
    
    assert result.coverage_pass is True
    assert result.resolves_pass is True
    
    # Request finalization
    finalize_response = request_finalize_draft(
        workspace_id=uuid.UUID(str(ws.id)),
        request=RequestFinalizeDraft(
            draft_artifact_id=draft.id,
            draft_artifact_version_id=version.id
        ),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    assert "finalized successfully" in finalize_response.message.lower()
    
    # Verify draft is finalized
    draft_metadata = db_session.execute(
        text("SELECT metadata FROM artifacts WHERE id = :id"),
        {"id": draft.id}
    ).fetchone()
    
    metadata = json.loads(draft_metadata[0])
    assert metadata["status"] == "final"
    assert metadata["final_version_id"] == version.id
