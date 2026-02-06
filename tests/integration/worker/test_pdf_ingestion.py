"""
Exit tests for Component 9: PDF Ingestion Worker Activity.

Per checklist:
- EXIT TEST 1: Ingest a real (generated) PDF
- EXIT TEST 2: Retrieve the parsed page text
- EXIT TEST 3: Evidence resolution returns correct substring for given char range

Tests run against real containers (Postgres, MinIO; not mocked).
"""

import hashlib
import io
import uuid

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


@pytest.fixture
def pdf_activity(storage, db_session):
    # Worker lives in apps/worker; tests/conftest.py already puts it on sys.path.
    from pdf_ingest import PDFIngestActivity

    return PDFIngestActivity(storage, db_session)


@pytest.fixture
def sample_pdf_bytes():
    """Generate a simple PDF with known text content."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    # Page 1
    c.drawString(100, 750, "Page 1: This is the first page of our test document.")
    c.showPage()

    # Page 2
    c.drawString(100, 750, "Page 2: Here is some more text on the second page.")
    c.drawString(100, 730, "Additional line on page 2 with specific content.")
    c.showPage()

    # Page 3
    c.drawString(100, 750, "Page 3: Final page with conclusion text.")
    c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.read()


@pytest.fixture
def workspace_with_artifact(db_session):
    """Create test workspace, agent, and a PDF artifact."""
    from database import Workspace, Agent, Artifact

    ws = Workspace(id=uuid.uuid4(), name="PDF Test Workspace", phase="LIT_REVIEW")
    db_session.add(ws)

    agent = Agent(id=uuid.uuid4(), moltbook_id="pdf_test_agent", name="PDF Test Agent", reputation=100)
    db_session.add(agent)
    db_session.flush()

    art = Artifact(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        short_id="P1",
        type="pdf",
        created_by=agent.id,
    )
    db_session.add(art)
    db_session.commit()

    return ws, art, agent


def test_pdf_ingest__real_pdf__creates_artifacts_and_versions(pdf_activity, sample_pdf_bytes, workspace_with_artifact, db_session):
    """
    EXIT TEST 1: Ingest a real (generated) PDF.

    Success criteria:
    - artifact_versions row created
    - Binary PDF stored in MinIO
    - Per-page text files stored
    - Metadata JSON stored
    - Logs written
    """
    ws, art, agent = workspace_with_artifact

    result = pdf_activity.ingest_pdf(
        artifact_id=str(art.id),
        workspace_id=str(ws.id),
        pdf_bytes=sample_pdf_bytes,
        created_by=str(agent.id),
        activity_run_id="run_001",
    )

    assert result["artifact_version_id"]
    assert result["version"] == 1
    assert result["page_count"] == 3
    assert result["binary_uri"].endswith("/v1/document.pdf")

    expected_hash = hashlib.sha256(sample_pdf_bytes).hexdigest()

    # Verify artifact_version persisted.
    row = db_session.execute(
        """
        SELECT id, version, storage_uri, content_hash
        FROM artifact_versions
        WHERE id = :id
        """,
        {"id": result["artifact_version_id"]},
    ).fetchone()
    assert row is not None
    assert str(row[0]) == result["artifact_version_id"]
    assert int(row[1]) == 1
    assert row[2] == result["binary_uri"]
    assert row[3] == expected_hash

    # Verify binary stored.
    binary_data = pdf_activity.storage.get_object(result["binary_uri"]).read()
    assert binary_data == sample_pdf_bytes

    # Verify per-page text stored.
    for page_num in range(1, 4):
        page_uri = f"s3://agora/{ws.id}/artifacts/{art.id}/v1/pages/page_{page_num}.txt"
        page_text = pdf_activity.storage.get_object(page_uri).read().decode("utf-8")
        assert f"Page {page_num}:" in page_text

    # Verify metadata stored.
    metadata_bytes = pdf_activity.storage.get_object(result["metadata_uri"]).read()
    import json

    metadata = json.loads(metadata_bytes.decode("utf-8"))
    assert metadata["page_count"] == 3
    assert str(metadata["binary_uri"]) == result["binary_uri"]

    # Verify logs written.
    logs = db_session.execute(
        """
        SELECT action
        FROM logs
        WHERE workspace_id = :ws_id
        ORDER BY created_at ASC
        """,
        {"ws_id": str(ws.id)},
    ).fetchall()
    actions = [r[0] for r in logs]
    assert "pdf.ingestion_completed" in actions


def test_pdf_ingest__after_ingest__page_text_retrievable(pdf_activity, sample_pdf_bytes, workspace_with_artifact):
    """
    EXIT TEST 2: Retrieve the parsed page text.

    Success criteria:
    - Can retrieve text for specific page
    - Text matches expected content
    - All pages accessible
    """
    ws, art, agent = workspace_with_artifact

    pdf_activity.ingest_pdf(
        artifact_id=str(art.id),
        workspace_id=str(ws.id),
        pdf_bytes=sample_pdf_bytes,
        created_by=str(agent.id),
    )

    page1_uri = f"s3://agora/{ws.id}/artifacts/{art.id}/v1/pages/page_1.txt"
    page1_text = pdf_activity.storage.get_object(page1_uri).read().decode("utf-8")
    assert "Page 1:" in page1_text
    assert "first page of our test document" in page1_text

    page2_uri = f"s3://agora/{ws.id}/artifacts/{art.id}/v1/pages/page_2.txt"
    page2_text = pdf_activity.storage.get_object(page2_uri).read().decode("utf-8")
    assert "Page 2:" in page2_text
    assert "Additional line on page 2" in page2_text

    page3_uri = f"s3://agora/{ws.id}/artifacts/{art.id}/v1/pages/page_3.txt"
    page3_text = pdf_activity.storage.get_object(page3_uri).read().decode("utf-8")
    assert "Page 3:" in page3_text
    assert "Final page" in page3_text


def test_pdf_evidence_resolution__pdf_location__returns_snippet(pdf_activity, sample_pdf_bytes, workspace_with_artifact):
    """
    EXIT TEST 3: Evidence resolution returns correct substring for given char range.
    """
    ws, art, agent = workspace_with_artifact

    ingest = pdf_activity.ingest_pdf(
        artifact_id=str(art.id),
        workspace_id=str(ws.id),
        pdf_bytes=sample_pdf_bytes,
        created_by=str(agent.id),
    )

    artifact_version_id = ingest["artifact_version_id"]

    page1_uri = f"s3://agora/{ws.id}/artifacts/{art.id}/v1/pages/page_1.txt"
    page1_text = pdf_activity.storage.get_object(page1_uri).read().decode("utf-8")

    search_str = "first page"
    start_idx = page1_text.find(search_str)
    assert start_idx != -1
    end_idx = start_idx + len(search_str)

    location1 = f"pdf:p=1#char={start_idx}-{end_idx}"
    resolved1 = pdf_activity.resolve_pdf_evidence(artifact_version_id=artifact_version_id, location=location1)
    assert resolved1 == search_str

    page2_uri = f"s3://agora/{ws.id}/artifacts/{art.id}/v1/pages/page_2.txt"
    page2_text = pdf_activity.storage.get_object(page2_uri).read().decode("utf-8")

    search_str2 = "specific content"
    start_idx2 = page2_text.find(search_str2)
    assert start_idx2 != -1
    end_idx2 = start_idx2 + len(search_str2)

    location2 = f"pdf:p=2#char={start_idx2}-{end_idx2}"
    resolved2 = pdf_activity.resolve_pdf_evidence(artifact_version_id=artifact_version_id, location=location2)
    assert resolved2 == search_str2


def test_pdf_ingest__no_text_pdf__returns_fail(pdf_activity, workspace_with_artifact):
    """
    PDFs with no extractable text fail with NoPDFTextError. No OCR fallback per spec.
    """
    from pdf_ingest import NoPDFTextError

    ws, art, agent = workspace_with_artifact

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.circle(100, 100, 50)  # shapes only
    c.showPage()
    c.save()
    buffer.seek(0)
    no_text_pdf = buffer.read()

    with pytest.raises(NoPDFTextError):
        pdf_activity.ingest_pdf(
            artifact_id=str(art.id),
            workspace_id=str(ws.id),
            pdf_bytes=no_text_pdf,
            created_by=str(agent.id),
        )


def test_evidence_resolver__invalid_pdf_location__returns_error(pdf_activity, sample_pdf_bytes, workspace_with_artifact):
    """Invalid location formats raise appropriate errors."""
    ws, art, agent = workspace_with_artifact

    ingest = pdf_activity.ingest_pdf(
        artifact_id=str(art.id),
        workspace_id=str(ws.id),
        pdf_bytes=sample_pdf_bytes,
        created_by=str(agent.id),
    )
    artifact_version_id = ingest["artifact_version_id"]

    with pytest.raises(ValueError, match="Invalid PDF location format"):
        pdf_activity.resolve_pdf_evidence(artifact_version_id=artifact_version_id, location="pdf:p=1")

    with pytest.raises(FileNotFoundError, match="Page 999"):
        pdf_activity.resolve_pdf_evidence(artifact_version_id=artifact_version_id, location="pdf:p=999#char=0-10")

    with pytest.raises(ValueError, match="Character range"):
        pdf_activity.resolve_pdf_evidence(artifact_version_id=artifact_version_id, location="pdf:p=1#char=0-999999")
