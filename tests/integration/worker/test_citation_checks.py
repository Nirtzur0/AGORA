"""
Exit tests for Component 13: Citation check activity + RuleChecks

Per checklist:
- EXIT TEST 1: Draft missing citations -> citation_coverage fail recorded
- EXIT TEST 2: Bad location -> citation_resolves fail recorded
- EXIT TEST 3: Good draft -> both pass

Tests run against real containers (Postgres, MinIO, not mocked).
"""
import pytest
import uuid
import json
from sqlalchemy import text

from storage import create_storage_from_env


@pytest.fixture
def workspace_with_agent_and_artifacts(db_session):
    """Create test workspace, agent, and artifacts for citation tests."""
    from database import Workspace, Agent, Artifact, ArtifactVersion, Claim
    
    ws = Workspace(
        id=str(uuid.uuid4()),
        name="Citation Test Workspace",
        phase="LIT_REVIEW"
    )
    db_session.add(ws)
    
    agent = Agent(
        id=str(uuid.uuid4()),
        moltbook_identity="test_agent_citation",
        display_name="Test Agent",
        reputation_score=100
    )
    db_session.add(agent)
    db_session.flush()
    
    # Create a PDF artifact for citations
    pdf_artifact = Artifact(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        type="pdf",
        short_id="P1",
        metadata=json.dumps({"title": "Test Paper"})
    )
    db_session.add(pdf_artifact)
    
    # Create PDF version with parsed text
    page_1_text = "This is page 1.\nSecond line of page 1."
    page_2_text = "This is page 2.\nSecond line of page 2."
    pdf_text = f"{page_1_text}\n\n{page_2_text}"
    
    storage = create_storage_from_env()
    storage_uri = f"s3://agora/{ws.id}/artifacts/{pdf_artifact.id}/v1/parsed.txt"
    storage.put_object(storage_uri, pdf_text.encode("utf-8"))
    storage.put_object(
        f"s3://agora/{ws.id}/artifacts/{pdf_artifact.id}/v1/pages/page_1.txt",
        page_1_text.encode("utf-8")
    )
    storage.put_object(
        f"s3://agora/{ws.id}/artifacts/{pdf_artifact.id}/v1/pages/page_2.txt",
        page_2_text.encode("utf-8")
    )
    
    pdf_version = ArtifactVersion(
        id=str(uuid.uuid4()),
        artifact_id=pdf_artifact.id,
        version=1,
        storage_uri=storage_uri,
        content_hash="abc123"
    )
    db_session.add(pdf_version)
    
    # Create claims
    claim1 = Claim(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        agent_id=agent.id,
        kind="fact",
        statement="Test claim 1",
        status="open"
    )
    db_session.add(claim1)
    
    claim2 = Claim(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        agent_id=agent.id,
        kind="fact",
        statement="Test claim 2",
        status="open"
    )
    db_session.add(claim2)
    
    db_session.commit()
    
    return {
        "workspace": ws,
        "agent": agent,
        "pdf_artifact": pdf_artifact,
        "pdf_version": pdf_version,
        "claim1": claim1,
        "claim2": claim2
    }


def test_citation_check__missing_citations__fails_coverage(db_session, workspace_with_agent_and_artifacts):
    """
    EXIT TEST 1: Draft missing citations -> citation_coverage fail recorded.
    
    Success criteria:
    - Draft with claim marker but no cite marker in same paragraph
    - citation_coverage rule check created with status=fail
    - Details show which claim lacks citation
    """
    from citation_check import citation_check_activity
    from database import Artifact, ArtifactVersion
    from sqlalchemy import text
    
    fixtures = workspace_with_agent_and_artifacts
    ws = fixtures["workspace"]
    claim1 = fixtures["claim1"]
    
    # Create draft with claim but NO citation in same paragraph
    draft_id = str(uuid.uuid4())
    draft = Artifact(
        id=draft_id,
        workspace_id=ws.id,
        type="draft",
        short_id="D1",
        metadata=json.dumps({"title": "Test Draft"})
    )
    db_session.add(draft)
    
    # Markdown with claim but no citation
    markdown = f"""# Introduction

This is a paragraph with a claim [[claim:{claim1.id}]] but no citation.

This is another paragraph without claims or citations.
"""
    
    # Store Markdown
    storage = create_storage_from_env()
    storage_uri = f"s3://agora/{ws.id}/artifacts/{draft_id}/v1/draft.md"
    storage.put_object(storage_uri, markdown.encode("utf-8"))
    
    draft_version_id = str(uuid.uuid4())
    draft_version = ArtifactVersion(
        id=draft_version_id,
        artifact_id=draft_id,
        version=1,
        storage_uri=storage_uri,
        content_hash="def456"
    )
    db_session.add(draft_version)
    db_session.commit()
    
    # Create DB wrapper
    db_wrapper = db_session
    
    # Run citation check
    result = citation_check_activity(draft_version_id, db_wrapper)
    
    # Verify coverage failed
    assert result.coverage_pass is False
    assert len(result.coverage_failures) == 1
    assert result.coverage_failures[0]["claim_id"] == str(claim1.id)
    assert result.coverage_failures[0]["reason"] == "no_citation_in_paragraph"
    
    # Verify rule check created
    rule_check = db_session.execute(
        text("""
            SELECT rule_name, status, details
            FROM rule_checks
            WHERE workspace_id = :ws_id
              AND rule_name = 'citation_coverage'
              AND target_id = :target_id
        """),
        {"ws_id": ws.id, "target_id": draft_version_id}
    ).fetchone()
    
    assert rule_check is not None
    assert rule_check[0] == "citation_coverage"
    assert rule_check[1] == "fail"
    
    details = rule_check[2]
    if isinstance(details, str):
        details = json.loads(details)
    assert "failures" in details
    assert len(details["failures"]) == 1


def test_citation_check__bad_location__fails_resolves(db_session, workspace_with_agent_and_artifacts):
    """
    EXIT TEST 2: Bad location -> citation_resolves fail recorded.
    
    Success criteria:
    - Draft with claim and cite marker
    - Cite location is invalid (e.g., page out of range)
    - citation_resolves rule check created with status=fail
    - Details show which citation failed to resolve
    """
    from citation_check import citation_check_activity
    from database import Artifact, ArtifactVersion
    from sqlalchemy import text
    
    fixtures = workspace_with_agent_and_artifacts
    ws = fixtures["workspace"]
    claim1 = fixtures["claim1"]
    pdf_version = fixtures["pdf_version"]
    
    # Create draft with claim and INVALID citation
    draft_id = str(uuid.uuid4())
    draft = Artifact(
        id=draft_id,
        workspace_id=ws.id,
        type="draft",
        short_id="D1",
        metadata=json.dumps({"title": "Test Draft"})
    )
    db_session.add(draft)
    
    # Markdown with claim and citation with bad location (page 999)
    markdown = f"""# Introduction

This is a paragraph with a claim [[claim:{claim1.id}]] and a bad citation [[cite:{pdf_version.id}|pdf:p=999#char=0-10]].
"""
    
    # Store Markdown
    storage = create_storage_from_env()
    storage_uri = f"s3://agora/{ws.id}/artifacts/{draft_id}/v1/draft.md"
    storage.put_object(storage_uri, markdown.encode("utf-8"))
    
    draft_version_id = str(uuid.uuid4())
    draft_version = ArtifactVersion(
        id=draft_version_id,
        artifact_id=draft_id,
        version=1,
        storage_uri=storage_uri,
        content_hash="ghi789"
    )
    db_session.add(draft_version)
    db_session.commit()
    
    # Create DB wrapper
    db_wrapper = db_session
    
    # Run citation check
    result = citation_check_activity(draft_version_id, db_wrapper)
    
    # Verify resolves failed
    assert result.resolves_pass is False
    assert len(result.resolves_failures) == 1
    assert result.resolves_failures[0]["artifact_version_id"] == str(pdf_version.id)
    assert result.resolves_failures[0]["location"] == "pdf:p=999#char=0-10"
    assert "PAGE_OUT_OF_RANGE" in result.resolves_failures[0]["error_code"]
    
    # Verify rule check created
    rule_check = db_session.execute(
        text("""
            SELECT rule_name, status, details
            FROM rule_checks
            WHERE workspace_id = :ws_id
              AND rule_name = 'citation_resolves'
              AND target_id = :target_id
        """),
        {"ws_id": ws.id, "target_id": draft_version_id}
    ).fetchone()
    
    assert rule_check is not None
    assert rule_check[0] == "citation_resolves"
    assert rule_check[1] == "fail"
    
    details = rule_check[2]
    if isinstance(details, str):
        details = json.loads(details)
    assert "failures" in details
    assert len(details["failures"]) == 1


def test_citation_check__good_draft__passes_coverage_and_resolves(db_session, workspace_with_agent_and_artifacts):
    """
    EXIT TEST 3: Good draft -> both pass.
    
    Success criteria:
    - Draft with claim and valid cite marker in same paragraph
    - Citation location resolves successfully
    - citation_coverage rule check created with status=pass
    - citation_resolves rule check created with status=pass
    - Citations materialized in citations table
    """
    from citation_check import citation_check_activity
    from database import Artifact, ArtifactVersion
    from sqlalchemy import text
    
    fixtures = workspace_with_agent_and_artifacts
    ws = fixtures["workspace"]
    claim1 = fixtures["claim1"]
    claim2 = fixtures["claim2"]
    pdf_version = fixtures["pdf_version"]
    
    # Create draft with claims and VALID citations
    draft_id = str(uuid.uuid4())
    draft = Artifact(
        id=draft_id,
        workspace_id=ws.id,
        type="draft",
        short_id="D1",
        metadata=json.dumps({"title": "Test Draft"})
    )
    db_session.add(draft)
    
    # Markdown with claims and valid citations
    markdown = f"""# Introduction

This is a paragraph with claim 1 [[claim:{claim1.id}]] and a valid citation [[cite:{pdf_version.id}|pdf:p=1#char=0-10]].

This is another paragraph with claim 2 [[claim:{claim2.id}]] and another citation [[cite:{pdf_version.id}|pdf:p=2#char=0-15]].
"""
    
    # Store Markdown
    storage = create_storage_from_env()
    storage_uri = f"s3://agora/{ws.id}/artifacts/{draft_id}/v1/draft.md"
    storage.put_object(storage_uri, markdown.encode("utf-8"))
    
    draft_version_id = str(uuid.uuid4())
    draft_version = ArtifactVersion(
        id=draft_version_id,
        artifact_id=draft_id,
        version=1,
        storage_uri=storage_uri,
        content_hash="jkl012"
    )
    db_session.add(draft_version)
    db_session.commit()
    
    # Create DB wrapper
    db_wrapper = db_session
    
    # Run citation check
    result = citation_check_activity(draft_version_id, db_wrapper)
    
    # Verify both checks passed
    assert result.coverage_pass is True
    assert len(result.coverage_failures) == 0
    assert result.resolves_pass is True
    assert len(result.resolves_failures) == 0
    assert result.citations_materialized == 2  # 2 paragraphs × 1 claim × 1 cite each
    
    # Verify coverage rule check
    coverage_check = db_session.execute(
        text("""
            SELECT rule_name, status, details
            FROM rule_checks
            WHERE workspace_id = :ws_id
              AND rule_name = 'citation_coverage'
              AND target_id = :target_id
        """),
        {"ws_id": ws.id, "target_id": draft_version_id}
    ).fetchone()
    
    assert coverage_check is not None
    assert coverage_check[1] == "pass"
    
    # Verify resolves rule check
    resolves_check = db_session.execute(
        text("""
            SELECT rule_name, status, details
            FROM rule_checks
            WHERE workspace_id = :ws_id
              AND rule_name = 'citation_resolves'
              AND target_id = :target_id
        """),
        {"ws_id": ws.id, "target_id": draft_version_id}
    ).fetchone()
    
    assert resolves_check is not None
    assert resolves_check[1] == "pass"
    
    # Verify citations materialized
    citations = db_session.execute(
        text("""
            SELECT claim_id, source_artifact_version_id, source_location
            FROM citations
            WHERE draft_artifact_version_id = :draft_version_id
        """),
        {"draft_version_id": draft_version_id}
    ).fetchall()
    
    assert len(citations) == 2
    
    # Verify citations link to correct claims
    citation_claims = {str(c[0]) for c in citations}
    assert str(claim1.id) in citation_claims
    assert str(claim2.id) in citation_claims


def test_rule_check_request__agent_endpoint__creates_rule_check(db_session, workspace_with_agent_and_artifacts):
    """Test agent-facing POST /workspaces/{id}/requests/run_rulecheck endpoint."""
    from rulecheck_routes import request_run_rulecheck, RunRuleCheckRequest
    from database import Artifact, ArtifactVersion
    from sqlalchemy import text
    
    fixtures = workspace_with_agent_and_artifacts
    ws = fixtures["workspace"]
    agent = fixtures["agent"]
    claim1 = fixtures["claim1"]
    pdf_version = fixtures["pdf_version"]
    
    # Create valid draft
    draft_id = str(uuid.uuid4())
    draft = Artifact(
        id=draft_id,
        workspace_id=ws.id,
        type="draft",
        short_id="D1",
        metadata=json.dumps({"title": "Test Draft"})
    )
    db_session.add(draft)
    
    markdown = f"""# Test

Claim [[claim:{claim1.id}]] with citation [[cite:{pdf_version.id}|pdf:p=1#char=0-10]].
"""
    
    storage = create_storage_from_env()
    storage_uri = f"s3://agora/{ws.id}/artifacts/{draft_id}/v1/draft.md"
    storage.put_object(storage_uri, markdown.encode("utf-8"))
    
    draft_version_id = str(uuid.uuid4())
    draft_version = ArtifactVersion(
        id=draft_version_id,
        artifact_id=draft_id,
        version=1,
        storage_uri=storage_uri,
        content_hash="mno345"
    )
    db_session.add(draft_version)
    db_session.commit()

    critic_id = str(uuid.uuid4())
    db_session.execute(
        text(
            """
            INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
            VALUES (:id, :moltbook_id, :name, :reputation, NOW())
            """
        ),
        {
            "id": critic_id,
            "moltbook_id": f"critic-{critic_id}",
            "name": "Critic",
            "reputation": 50,
        },
    )
    db_session.execute(
        text(
            """
            INSERT INTO critiques (
                id, workspace_id, target_type, target_id, target_location,
                critic_agent_id, status, severity, message, resolution, created_at
            ) VALUES (
                :id, :workspace_id, 'artifact_version', :target_id, NULL,
                :critic_agent_id, 'resolved', 'medium', :message, :resolution, NOW()
            )
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "workspace_id": str(ws.id),
            "target_id": draft_version_id,
            "critic_agent_id": critic_id,
            "message": "Reviewed and accepted.",
            "resolution": json.dumps({"status": "accepted_fix"}),
        },
    )
    db_session.commit()

    # Create DB wrapper
    db_wrapper = db_session
    
    # Mock current_agent
    mock_agent = {"agent_id": agent.id}
    
    # Call endpoint
    request = RunRuleCheckRequest(draft_artifact_version_id=draft_version_id)
    response = request_run_rulecheck(
        workspace_id=uuid.UUID(str(ws.id)),
        request=request,
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    # Verify response
    assert response.draft_artifact_version_id == draft_version_id
    assert response.status == "passed"
    assert "passed" in response.message.lower()
    assert response.request_id is not None


def test_rule_checks_list__filters_applied__returns_matching(db_session, workspace_with_agent_and_artifacts):
    """Test GET /rule-checks with filters."""
    from rulecheck_routes import list_rule_checks
    from database import Artifact, ArtifactVersion
    from sqlalchemy import text
    
    fixtures = workspace_with_agent_and_artifacts
    ws = fixtures["workspace"]
    agent = fixtures["agent"]
    claim1 = fixtures["claim1"]
    pdf_version = fixtures["pdf_version"]
    
    # Create draft and run check
    draft_id = str(uuid.uuid4())
    draft = Artifact(
        id=draft_id,
        workspace_id=ws.id,
        type="draft",
        short_id="D1",
        metadata=json.dumps({"title": "Test Draft"})
    )
    db_session.add(draft)
    
    markdown = f"""# Test

Claim [[claim:{claim1.id}]] with citation [[cite:{pdf_version.id}|pdf:p=1#char=0-10]].
"""
    
    storage = create_storage_from_env()
    storage_uri = f"s3://agora/{ws.id}/artifacts/{draft_id}/v1/draft.md"
    storage.put_object(storage_uri, markdown.encode("utf-8"))
    
    draft_version_id = str(uuid.uuid4())
    draft_version = ArtifactVersion(
        id=draft_version_id,
        artifact_id=draft_id,
        version=1,
        storage_uri=storage_uri,
        content_hash="pqr678"
    )
    db_session.add(draft_version)
    db_session.commit()
    
    # Run citation check
    from citation_check import citation_check_activity
    
    db_wrapper = db_session
    citation_check_activity(draft_version_id, db_wrapper)
    
    # Mock current_agent
    mock_agent = {"agent_id": agent.id}
    
    # List rule checks with filters
    results = list_rule_checks(
        workspace_id=ws.id,
        rule_name="citation_coverage",
        target_type="draft_version",
        target_id=draft_version_id,
        status="pass",
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    # Verify results
    assert len(results) == 1
    assert results[0].workspace_id == str(ws.id)
    assert results[0].rule_name == "citation_coverage"
    assert results[0].target_id == draft_version_id
    assert results[0].status == "pass"
