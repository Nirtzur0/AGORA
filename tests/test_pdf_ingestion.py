"""
Exit tests for Component 9: PDF Ingestion Worker Activity.

Per checklist:
- EXIT TEST 1: Ingest a real (generated) PDF
- EXIT TEST 2: Retrieve the parsed page text
- EXIT TEST 3: Evidence resolution returns correct substring for given char range

Tests run against real containers (Postgres, MinIO, not mocked).
"""
import io
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Assuming worker lives in apps/worker
import sys
sys.path.insert(0, "/Users/nirtzur/Documents/projects/AGORA/apps/worker")
from pdf_ingest import PDFIngestActivity, NoPDFTextError


@pytest.fixture
def pdf_activity(storage, db_session):
    """Create PDF ingestion activity with dependencies."""
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
    """Create test workspace and artifact."""
    from database import Workspace, Artifact
    
    ws = Workspace(
        id="ws_test_pdf",
        name="PDF Test Workspace",
        phase="ingestion"
    )
    db_session.add(ws)
    
    art = Artifact(
        id="art_pdf_001",
        workspace_id=ws.id,
        short_id="A1",
        content_type="application/pdf",
        created_by="agent_test"
    )
    db_session.add(art)
    db_session.commit()
    
    return ws, art


def test_exit_1_ingest_real_pdf(pdf_activity, sample_pdf_bytes, workspace_with_artifact, db_session):
    """
    EXIT TEST 1: Ingest a real (generated) PDF.
    
    Success criteria:
    - artifact_versions row created
    - Binary PDF stored in MinIO
    - Per-page text files stored
    - Metadata JSON stored
    - Logs written
    """
    ws, art = workspace_with_artifact
    
    # Ingest PDF
    result = pdf_activity.ingest_pdf(
        artifact_id=art.id,
        workspace_id=ws.id,
        pdf_bytes=sample_pdf_bytes,
        created_by="agent_test",
        activity_run_id="run_001"
    )
    
    # Check result structure
    assert result["artifact_id"] == art.id
    assert result["version"] == 1
    assert result["status"] == "success"
    assert result["page_count"] == 3
    assert result["total_chars"] > 0
    
    # Verify artifact_version in database
    from database import ArtifactVersion
    
    version = db_session.query(ArtifactVersion).filter_by(
        artifact_id=art.id,
        version=1
    ).first()
    
    assert version is not None
    assert version.content_hash is not None
    assert version.size_bytes == len(sample_pdf_bytes)
    assert version.location.startswith("s3://agora/")
    
    # Verify binary stored
    binary_key = f"{ws.id}/artifacts/{art.id}/v1/document.pdf"
    binary_data = pdf_activity.storage.get_object("agora", binary_key)
    assert binary_data == sample_pdf_bytes
    
    # Verify per-page text stored
    for page_num in range(1, 4):
        page_key = f"{ws.id}/artifacts/{art.id}/v1/pages/page_{page_num}.txt"
        page_text = pdf_activity.storage.get_object("agora", page_key).decode("utf-8")
        assert len(page_text) > 0
        assert f"Page {page_num}" in page_text
    
    # Verify metadata stored
    metadata_key = f"{ws.id}/artifacts/{art.id}/v1/metadata.json"
    metadata_bytes = pdf_activity.storage.get_object("agora", metadata_key)
    import json
    metadata = json.loads(metadata_bytes.decode("utf-8"))
    assert metadata["page_count"] == 3
    assert metadata["total_chars"] > 0
    
    # Verify logs written
    from database import Log
    logs = db_session.query(Log).filter_by(
        workspace_id=ws.id,
        artifact_id=art.id
    ).all()
    
    assert len(logs) >= 2  # At least ingestion_started and ingestion_completed
    assert any(log.message == "PDF ingestion started" for log in logs)
    assert any(log.message.startswith("PDF ingestion completed") for log in logs)


def test_exit_2_retrieve_parsed_page_text(pdf_activity, sample_pdf_bytes, workspace_with_artifact):
    """
    EXIT TEST 2: Retrieve the parsed page text.
    
    Success criteria:
    - Can retrieve text for specific page
    - Text matches expected content
    - All pages accessible
    """
    ws, art = workspace_with_artifact
    
    # Ingest PDF first
    result = pdf_activity.ingest_pdf(
        artifact_id=art.id,
        workspace_id=ws.id,
        pdf_bytes=sample_pdf_bytes,
        created_by="agent_test"
    )
    
    # Retrieve page 1 text
    page1_key = f"{ws.id}/artifacts/{art.id}/v1/pages/page_1.txt"
    page1_text = pdf_activity.storage.get_object("agora", page1_key).decode("utf-8")
    
    assert "Page 1: This is the first page" in page1_text
    assert "test document" in page1_text
    
    # Retrieve page 2 text
    page2_key = f"{ws.id}/artifacts/{art.id}/v1/pages/page_2.txt"
    page2_text = pdf_activity.storage.get_object("agora", page2_key).decode("utf-8")
    
    assert "Page 2: Here is some more text" in page2_text
    assert "Additional line on page 2" in page2_text
    
    # Retrieve page 3 text
    page3_key = f"{ws.id}/artifacts/{art.id}/v1/pages/page_3.txt"
    page3_text = pdf_activity.storage.get_object("agora", page3_key).decode("utf-8")
    
    assert "Page 3: Final page" in page3_text
    assert "conclusion text" in page3_text


def test_exit_3_evidence_resolution(pdf_activity, sample_pdf_bytes, workspace_with_artifact):
    """
    EXIT TEST 3: Evidence resolution returns correct substring for given char range.
    
    Success criteria:
    - Parses location format: pdf:p={page}#char={start}-{end}
    - Returns exact substring from page text
    - Works across different pages
    - Handles edge cases (start=0, end at boundary)
    """
    ws, art = workspace_with_artifact
    
    # Ingest PDF first
    result = pdf_activity.ingest_pdf(
        artifact_id=art.id,
        workspace_id=ws.id,
        pdf_bytes=sample_pdf_bytes,
        created_by="agent_test"
    )
    
    artifact_version_id = f"{art.id}_v1"
    
    # Test 1: Extract "first page" from page 1
    # First, get the page 1 text to find the exact char positions
    page1_key = f"{ws.id}/artifacts/{art.id}/v1/pages/page_1.txt"
    page1_text = pdf_activity.storage.get_object("agora", page1_key).decode("utf-8")
    
    # Find "first page" in the text
    search_str = "first page"
    start_idx = page1_text.find(search_str)
    assert start_idx != -1, "Test string not found in page text"
    end_idx = start_idx + len(search_str)
    
    location1 = f"pdf:p=1#char={start_idx}-{end_idx}"
    resolved1 = pdf_activity.resolve_pdf_evidence(
        workspace_id=ws.id,
        artifact_version_id=artifact_version_id,
        location=location1
    )
    
    assert resolved1 == search_str
    
    # Test 2: Extract from page 2
    page2_key = f"{ws.id}/artifacts/{art.id}/v1/pages/page_2.txt"
    page2_text = pdf_activity.storage.get_object("agora", page2_key).decode("utf-8")
    
    search_str2 = "specific content"
    start_idx2 = page2_text.find(search_str2)
    assert start_idx2 != -1
    end_idx2 = start_idx2 + len(search_str2)
    
    location2 = f"pdf:p=2#char={start_idx2}-{end_idx2}"
    resolved2 = pdf_activity.resolve_pdf_evidence(
        workspace_id=ws.id,
        artifact_version_id=artifact_version_id,
        location=location2
    )
    
    assert resolved2 == search_str2
    
    # Test 3: Extract from start of page 3 (char=0)
    page3_key = f"{ws.id}/artifacts/{art.id}/v1/pages/page_3.txt"
    page3_text = pdf_activity.storage.get_object("agora", page3_key).decode("utf-8")
    
    # Extract first 7 characters
    location3 = "pdf:p=3#char=0-7"
    resolved3 = pdf_activity.resolve_pdf_evidence(
        workspace_id=ws.id,
        artifact_version_id=artifact_version_id,
        location=location3
    )
    
    assert resolved3 == page3_text[0:7]
    
    # Test 4: Extract to end of text
    location4 = f"pdf:p=1#char=0-{len(page1_text)}"
    resolved4 = pdf_activity.resolve_pdf_evidence(
        workspace_id=ws.id,
        artifact_version_id=artifact_version_id,
        location=location4
    )
    
    assert resolved4 == page1_text


def test_no_text_pdf_fails(pdf_activity, workspace_with_artifact):
    """
    Test that PDFs with no extractable text fail with NoPDFTextError.
    No OCR fallback per spec.
    """
    ws, art = workspace_with_artifact
    
    # Create a PDF with just shapes, no text
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.circle(100, 100, 50)  # Just draw a circle
    c.showPage()
    c.save()
    buffer.seek(0)
    no_text_pdf = buffer.read()
    
    # Should raise NoPDFTextError
    with pytest.raises(NoPDFTextError, match="No text content extracted"):
        pdf_activity.ingest_pdf(
            artifact_id=art.id,
            workspace_id=ws.id,
            pdf_bytes=no_text_pdf,
            created_by="agent_test"
        )


def test_invalid_evidence_location_format(pdf_activity, sample_pdf_bytes, workspace_with_artifact):
    """Test that invalid location formats raise appropriate errors."""
    ws, art = workspace_with_artifact
    
    # Ingest PDF first
    pdf_activity.ingest_pdf(
        artifact_id=art.id,
        workspace_id=ws.id,
        pdf_bytes=sample_pdf_bytes,
        created_by="agent_test"
    )
    
    artifact_version_id = f"{art.id}_v1"
    
    # Invalid format (missing char range)
    with pytest.raises(ValueError, match="Invalid PDF location format"):
        pdf_activity.resolve_pdf_evidence(
            workspace_id=ws.id,
            artifact_version_id=artifact_version_id,
            location="pdf:p=1"
        )
    
    # Invalid page number (page 999 doesn't exist)
    with pytest.raises(FileNotFoundError, match="Page text not found"):
        pdf_activity.resolve_pdf_evidence(
            workspace_id=ws.id,
            artifact_version_id=artifact_version_id,
            location="pdf:p=999#char=0-10"
        )
    
    # Char range out of bounds
    with pytest.raises(ValueError, match="out of bounds"):
        pdf_activity.resolve_pdf_evidence(
            workspace_id=ws.id,
            artifact_version_id=artifact_version_id,
            location="pdf:p=1#char=0-999999"
        )
