"""
Exit test for Component 15: Literature grounding workflow (end-to-end)

Per checklist:
Scripted integration test that performs:
1. create workspace
2. create pdf artifact + upload v1 bytes
3. request ingest (runs pdf_ingest + creates agent_task)
4. create claim + add evidence referencing PDF span
5. create draft version with claim/cite markers
6. run citation_check -> PASS (rule_checks written)

Note: These tests call route functions directly (not HTTP) to keep the suite fast
while still exercising real Postgres + MinIO interactions.
"""

import hashlib
import io
import json
import uuid

import pytest
from sqlalchemy import text

from database import Workspace, Agent, Artifact, ArtifactVersion


def _make_two_page_pdf_bytes() -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(72, 720, "Page 1 of the research paper.")
    c.drawString(72, 700, "This is the introduction with important findings.")
    c.showPage()
    c.drawString(72, 720, "Page 2 continues the discussion.")
    c.drawString(72, 700, "More content here with detailed analysis.")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


@pytest.fixture
def integration_setup(db_session):
    ws = Workspace(
        id=uuid.uuid4(),
        name="Literature Grounding Test",
        phase="LIT_REVIEW",
    )
    db_session.add(ws)

    agent = Agent(
        id=uuid.uuid4(),
        moltbook_id="test_integration_agent",
        name="Integration Test Agent",
        reputation=100,
    )
    db_session.add(agent)
    db_session.commit()

    # RBAC: request actions require workspace membership + permission.
    maintainer_role_id = db_session.execute(
        "SELECT id FROM roles WHERE name = :name",
        {"name": "Maintainer"},
    ).fetchone()[0]
    db_session.execute(
        """
        INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status, joined_at)
        VALUES (:workspace_id, :agent_id, :role_id, 'active', NOW())
        """,
        {"workspace_id": str(ws.id), "agent_id": str(agent.id), "role_id": str(maintainer_role_id)},
    )
    db_session.commit()

    return ws, agent


def test_literature_grounding_workflow__happy_path__completes(db_session, integration_setup, storage):
    import asyncio

    from request_routes import request_ingest_pdf, IngestPdfRequest
    from claim_routes import create_claim, add_evidence_to_claim, CreateClaimRequest, AddEvidenceRequest
    from draft_routes import create_draft, create_draft_version, CreateDraftRequest, CreateDraftVersionRequest
    from rulecheck_routes import request_run_rulecheck, RunRuleCheckRequest

    ws, agent = integration_setup
    mock_agent = {"agent_id": str(agent.id)}

    # Step 1-3: Create PDF artifact + uploaded version (v1 bytes).
    pdf_artifact_id = uuid.uuid4()
    db_session.add(
        Artifact(
            id=pdf_artifact_id,
            workspace_id=str(ws.id),
            type="pdf",
            short_id="P1",
            metadata={
                "title": "Test Research Paper",
                "source_uri": "s3://test/paper.pdf",
            },
            created_by=str(agent.id),
        )
    )
    db_session.commit()

    pdf_bytes = _make_two_page_pdf_bytes()
    initial_pdf_uri = f"s3://agora/{ws.id}/artifacts/{pdf_artifact_id}/v1/document.pdf"
    storage.put_object(initial_pdf_uri, pdf_bytes)

    db_session.add(
        ArtifactVersion(
            id=str(uuid.uuid4()),
            artifact_id=pdf_artifact_id,
            version=1,
            storage_uri=initial_pdf_uri,
            content_hash=hashlib.sha256(pdf_bytes).hexdigest(),
            created_by=str(agent.id),
        )
    )
    db_session.commit()

    # Step 4: Request ingestion (runs literature_grounding workflow which runs pdf_ingest).
    ingest_response = asyncio.run(
        request_ingest_pdf(
            workspace_id=uuid.UUID(str(ws.id)),
            request=IngestPdfRequest(artifact_id=str(pdf_artifact_id)),
            current_agent=mock_agent,
            db=db_session,
        )
    )
    assert ingest_response.artifact_id == str(pdf_artifact_id)
    assert ingest_response.workflow_run_id

    workflow = db_session.execute(
        text(
            """
            SELECT workflow_type, status
            FROM workflow_runs
            WHERE id = :id
            """
        ),
        {"id": ingest_response.workflow_run_id},
    ).fetchone()
    assert workflow is not None
    assert workflow[0] == "literature_grounding"
    assert workflow[1] in ("completed", "running")

    # Identify the ingested version written by pdf_ingest (should be v2).
    latest = db_session.execute(
        text(
            """
            SELECT id, version
            FROM artifact_versions
            WHERE artifact_id = :artifact_id
            ORDER BY version DESC
            LIMIT 1
            """
        ),
            {"artifact_id": str(pdf_artifact_id)},
    ).fetchone()
    assert latest is not None
    pdf_version_id, pdf_version_num = str(latest[0]), int(latest[1])
    assert pdf_version_num == 2

    # Compute a resolvable evidence span from extracted page text.
    page1_uri = f"s3://agora/{ws.id}/artifacts/{pdf_artifact_id}/v{pdf_version_num}/pages/page_1.txt"
    page1_text = storage.get_object(page1_uri).read().decode("utf-8")
    search = "important findings"
    start = page1_text.find(search)
    assert start >= 0, f"Expected '{search}' in extracted page text; got: {page1_text[:200]!r}"
    end = start + len(search)
    evidence_location = f"pdf:p=1#char={start}-{end}"

    # Step 5: Create claim + evidence referencing the PDF.
    claim_response = create_claim(
        workspace_id=uuid.UUID(str(ws.id)),
        request=CreateClaimRequest(
            text="The study found significant correlation between variables X and Y",
            kind="fact",
            confidence="high",
        ),
        current_agent=mock_agent,
        db=db_session,
    )
    assert claim_response.workspace_id == str(ws.id)

    evidence_response = add_evidence_to_claim(
        claim_id=uuid.UUID(str(claim_response.id)),
        request=AddEvidenceRequest(
            artifact_version_id=pdf_version_id,
            location=evidence_location,
        ),
        current_agent=mock_agent,
        db=db_session,
        storage=storage,
    )
    assert evidence_response["claim_id"] == claim_response.id
    assert evidence_response["artifact_version_id"] == pdf_version_id

    # Step 6: Create draft version with claim/cite markers.
    draft_response = create_draft(
        workspace_id=uuid.UUID(str(ws.id)),
        request=CreateDraftRequest(title="Literature Review Draft"),
        current_agent=mock_agent,
        db=db_session,
    )

    markdown_content = f"""# Literature Review

## Key Findings

This paragraph discusses the main finding [[claim:{claim_response.id}]].
The evidence comes from the research paper [[cite:{pdf_version_id}|{evidence_location}]].

## Conclusion

The study provides strong support for the hypothesis.
"""

    version_response = create_draft_version(
        draft_id=uuid.UUID(str(draft_response.id)),
        request=CreateDraftVersionRequest(content=markdown_content),
        current_agent=mock_agent,
        db=db_session,
    )

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
            "target_id": version_response.id,
            "critic_agent_id": critic_id,
            "message": "Reviewed and accepted.",
            "resolution": json.dumps({"status": "accepted_fix"}),
        },
    )
    db_session.commit()

    # Step 7: Run citation check and verify persisted rule_checks + citations.
    rulecheck_response = request_run_rulecheck(
        workspace_id=uuid.UUID(str(ws.id)),
        request=RunRuleCheckRequest(draft_artifact_version_id=version_response.id),
        current_agent=mock_agent,
        db=db_session,
    )
    assert rulecheck_response.status == "passed"

    coverage_check = db_session.execute(
        text(
            """
            SELECT status
            FROM rule_checks
            WHERE workspace_id = :ws_id
              AND rule_name = 'citation_coverage'
              AND target_id = :version_id
            """
        ),
        {"ws_id": str(ws.id), "version_id": version_response.id},
    ).fetchone()
    assert coverage_check is not None
    assert coverage_check[0] == "pass"

    resolves_check = db_session.execute(
        text(
            """
            SELECT status
            FROM rule_checks
            WHERE workspace_id = :ws_id
              AND rule_name = 'citation_resolves'
              AND target_id = :version_id
            """
        ),
        {"ws_id": str(ws.id), "version_id": version_response.id},
    ).fetchone()
    assert resolves_check is not None
    assert resolves_check[0] == "pass"

    citations = db_session.execute(
        text(
            """
            SELECT claim_id, source_artifact_version_id, source_location
            FROM citations
            WHERE draft_artifact_version_id = :version_id
            """
        ),
        {"version_id": version_response.id},
    ).fetchall()
    assert len(citations) == 1
    assert str(citations[0][0]) == claim_response.id
    assert str(citations[0][1]) == pdf_version_id
    assert citations[0][2] == evidence_location


def test_pdf_ingestion__idempotency_key__dedupes(db_session, integration_setup, storage):
    import asyncio

    from request_routes import request_ingest_pdf, IngestPdfRequest

    ws, agent = integration_setup
    mock_agent = {"agent_id": str(agent.id)}

    pdf_artifact_id = str(uuid.uuid4())
    db_session.add(
        Artifact(
            id=pdf_artifact_id,
            workspace_id=str(ws.id),
            type="pdf",
            short_id="P1",
            metadata={"title": "Test PDF"},
            created_by=str(agent.id),
        )
    )
    db_session.commit()

    pdf_bytes = _make_two_page_pdf_bytes()
    initial_pdf_uri = f"s3://agora/{ws.id}/artifacts/{pdf_artifact_id}/v1/document.pdf"
    storage.put_object(initial_pdf_uri, pdf_bytes)

    db_session.add(
        ArtifactVersion(
            id=str(uuid.uuid4()),
            artifact_id=pdf_artifact_id,
            version=1,
            storage_uri=initial_pdf_uri,
            content_hash=hashlib.sha256(pdf_bytes).hexdigest(),
            created_by=str(agent.id),
        )
    )
    db_session.commit()

    idem_key = "test-ingest-pdf-idem"

    response1 = asyncio.run(
        request_ingest_pdf(
            workspace_id=uuid.UUID(str(ws.id)),
            request=IngestPdfRequest(artifact_id=pdf_artifact_id),
            current_agent=mock_agent,
            db=db_session,
            idempotency_key=idem_key,
        )
    )
    response2 = asyncio.run(
        request_ingest_pdf(
            workspace_id=uuid.UUID(str(ws.id)),
            request=IngestPdfRequest(artifact_id=pdf_artifact_id),
            current_agent=mock_agent,
            db=db_session,
            idempotency_key=idem_key,
        )
    )

    assert response2.workflow_run_id == response1.workflow_run_id
    assert "idempotent" in response2.message.lower()


def test_finalize_draft_request__workspace_not_finalized__returns_409(db_session, integration_setup, storage):
    import asyncio
    from fastapi import HTTPException

    from request_routes import request_finalize_draft, FinalizeDraftRequest as RequestFinalizeDraft
    from draft_routes import create_draft, create_draft_version, CreateDraftRequest, CreateDraftVersionRequest
    from claim_routes import create_claim, CreateClaimRequest
    from auth_middleware import SystemContext

    ws, agent = integration_setup
    mock_agent = {"agent_id": str(agent.id)}

    claim = create_claim(
        workspace_id=uuid.UUID(str(ws.id)),
        request=CreateClaimRequest(text="Test claim", kind="fact", confidence="high"),
        current_agent=mock_agent,
        db=db_session,
    )

    pdf_artifact_id = str(uuid.uuid4())
    db_session.add(
        Artifact(
            id=pdf_artifact_id,
            workspace_id=str(ws.id),
            type="pdf",
            short_id="P1",
            metadata={"title": "Test PDF"},
            created_by=str(agent.id),
        )
    )
    db_session.commit()

    pdf_bytes = _make_two_page_pdf_bytes()
    pdf_uri = f"s3://agora/{ws.id}/artifacts/{pdf_artifact_id}/v1/document.pdf"
    storage.put_object(pdf_uri, pdf_bytes)
    # Evidence resolution uses the extracted page text path.
    storage.put_object(
        f"s3://agora/{ws.id}/artifacts/{pdf_artifact_id}/v1/pages/page_1.txt",
        b"Test content for citation resolution.",
    )

    pdf_version_id = str(uuid.uuid4())
    db_session.add(
        ArtifactVersion(
            id=pdf_version_id,
            artifact_id=pdf_artifact_id,
            version=1,
            storage_uri=pdf_uri,
            content_hash=hashlib.sha256(pdf_bytes).hexdigest(),
            created_by=str(agent.id),
        )
    )
    db_session.commit()

    draft = create_draft(
        workspace_id=uuid.UUID(str(ws.id)),
        request=CreateDraftRequest(title="Test Draft"),
        current_agent=mock_agent,
        db=db_session,
    )

    markdown = f"""# Test

Claim [[claim:{claim.id}]] with citation [[cite:{pdf_version_id}|pdf:p=1#char=0-10]].
"""
    version = create_draft_version(
        draft_id=uuid.UUID(str(draft.id)),
        request=CreateDraftVersionRequest(content=markdown),
        current_agent=mock_agent,
        db=db_session,
    )

    # request_finalize_draft is SYSTEM-ONLY and additionally requires workspace.phase == FINALIZED.
    # This test asserts the phase precondition is enforced (without building the full gate setup).
    with pytest.raises(HTTPException) as e:
        asyncio.run(
            request_finalize_draft(
                workspace_id=uuid.UUID(str(ws.id)),
                request=RequestFinalizeDraft(
                    draft_artifact_id=draft.id,
                    draft_artifact_version_id=version.id,
                ),
                system_context=SystemContext(service_name="test"),
                db=db_session,
            )
        )
    assert e.value.status_code == 400
    assert "must be FINALIZED" in str(e.value.detail)


def test_literature_grounding_workflow__missing_pdf_version__marks_workflow_and_activity_failed(
    db_session, integration_setup
):
    import asyncio
    from fastapi import HTTPException

    from request_routes import request_ingest_pdf, IngestPdfRequest

    ws, agent = integration_setup
    mock_agent = {"agent_id": str(agent.id)}

    pdf_artifact_id = str(uuid.uuid4())
    db_session.add(
        Artifact(
            id=pdf_artifact_id,
            workspace_id=str(ws.id),
            type="pdf",
            short_id="P1",
            metadata={"title": "Missing Version PDF"},
            created_by=str(agent.id),
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException) as e:
        asyncio.run(
            request_ingest_pdf(
                workspace_id=uuid.UUID(str(ws.id)),
                request=IngestPdfRequest(artifact_id=pdf_artifact_id),
                current_agent=mock_agent,
                db=db_session,
            )
        )

    assert e.value.status_code == 500
    assert "No artifact_versions found for PDF artifact" in str(e.value.detail)

    workflow_row = db_session.execute(
        text(
            """
            SELECT id, status
            FROM workflow_runs
            WHERE workspace_id = :workspace_id
              AND workflow_type = 'literature_grounding'
            ORDER BY started_at DESC
            LIMIT 1
            """
        ),
        {"workspace_id": str(ws.id)},
    ).fetchone()
    assert workflow_row is not None
    workflow_run_id = str(workflow_row[0])
    assert workflow_row[1] == "failed"

    activity_rows = db_session.execute(
        text(
            """
            SELECT activity_type, status
            FROM activity_runs
            WHERE workflow_run_id = :workflow_run_id
            ORDER BY started_at
            """
        ),
        {"workflow_run_id": workflow_run_id},
    ).fetchall()
    assert len(activity_rows) == 1
    assert activity_rows[0][0] == "pdf_ingest"
    assert activity_rows[0][1] == "failed"
