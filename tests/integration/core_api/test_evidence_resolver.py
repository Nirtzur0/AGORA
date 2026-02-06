"""
Exit tests for Component 10: Evidence Pointer Resolver

Per checklist:
- EXIT TEST 1: PDF resolution test
- EXIT TEST 2: Log char-range resolution test
- EXIT TEST 3: Bad grammar returns deterministic error

Tests run against real containers (Postgres, MinIO, not mocked).
"""
import io
import json
import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from evidence_resolver import create_resolver


@pytest.fixture
def evidence_resolver(storage, db_session):
    """Create evidence resolver with dependencies."""
    return create_resolver(storage, db_session)


@pytest.fixture
def sample_pdf_with_version(storage, db_session):
    """Create a test PDF and store it with artifact_version."""
    from database import Workspace, Artifact, ArtifactVersion
    import hashlib
    import uuid
    
    # Create workspace and artifact
    ws = Workspace(
        id=uuid.uuid4(),
        name="Evidence Test Workspace",
        phase="LIT_REVIEW"
    )
    db_session.add(ws)
    db_session.flush()
    
    art = Artifact(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        short_id="A1",
        content_type="application/pdf",
    )
    db_session.add(art)
    db_session.flush()
    
    # Generate PDF with known text
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawString(100, 750, "This is page 1 with some test content for evidence resolution.")
    c.showPage()
    c.drawString(100, 750, "Page 2 contains different text for testing multiple pages.")
    c.showPage()
    c.save()
    buffer.seek(0)
    pdf_bytes = buffer.read()
    
    # Store PDF binary
    binary_uri = f"s3://agora/{ws.id}/artifacts/{art.id}/v1/document.pdf"
    storage.put_object(binary_uri, pdf_bytes)
    
    # Store per-page extracted text (simulating PDF ingestion)
    page1_text = "This is page 1 with some test content for evidence resolution."
    page2_text = "Page 2 contains different text for testing multiple pages."
    
    page1_uri = f"s3://agora/{ws.id}/artifacts/{art.id}/v1/pages/page_1.txt"
    page2_uri = f"s3://agora/{ws.id}/artifacts/{art.id}/v1/pages/page_2.txt"
    
    storage.put_object(page1_uri, page1_text.encode("utf-8"))
    storage.put_object(page2_uri, page2_text.encode("utf-8"))
    
    # Store metadata
    metadata = {
        "page_count": 2,
        "total_chars": len(page1_text) + len(page2_text)
    }
    metadata_uri = f"s3://agora/{ws.id}/artifacts/{art.id}/v1/metadata.json"
    storage.put_object(metadata_uri, json.dumps(metadata).encode("utf-8"))
    
    # Create artifact_version
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()
    version = ArtifactVersion(
        id=uuid.uuid4(),
        artifact_id=art.id,
        version=1,
        content_hash=content_hash,
        storage_uri=binary_uri,
    )
    db_session.add(version)
    db_session.commit()
    
    return {
        "workspace_id": str(ws.id),
        "artifact_id": str(art.id),
        "artifact_version_id": str(version.id),
        "page1_text": page1_text,
        "page2_text": page2_text
    }


@pytest.fixture
def sample_log_with_version(storage, db_session):
    """Create a test log artifact."""
    from database import Workspace, Artifact, ArtifactVersion
    import hashlib
    import uuid
    
    # Create workspace and artifact
    ws = Workspace(
        id=uuid.uuid4(),
        name="Log Test Workspace",
        phase="LIT_REVIEW"
    )
    db_session.add(ws)
    db_session.flush()
    
    art = Artifact(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        short_id="L1",
        content_type="application/json",
    )
    db_session.add(art)
    db_session.flush()
    
    # Create log content (JSON)
    log_data = {
        "metrics": {
            "accuracy": 0.95,
            "loss": 0.12
        },
        "timestamp": "2026-02-02T10:00:00Z",
        "model": "gpt-4"
    }
    log_json = json.dumps(log_data, indent=2)
    
    # Store log
    log_uri = f"s3://agora/{ws.id}/artifacts/{art.id}/v1/log.json"
    storage.put_object(log_uri, log_json.encode("utf-8"))
    
    # Also create a plain-text log for char-range testing
    log_text = "This is a plain text log file with some content for char-range testing."
    log_txt_uri = f"s3://agora/{ws.id}/artifacts/{art.id}/v1/log.txt"
    storage.put_object(log_txt_uri, log_text.encode("utf-8"))
    
    # Create artifact_version
    # For char-range resolution, SandboxRunActivity pulls bytes from artifact_versions.storage_uri,
    # so we point the version at the plain-text file while still writing log.json for jsonpath.
    content_hash = hashlib.sha256(log_text.encode("utf-8")).hexdigest()
    version = ArtifactVersion(
        id=uuid.uuid4(),
        artifact_id=art.id,
        version=1,
        content_hash=content_hash,
        storage_uri=log_txt_uri,
    )
    db_session.add(version)
    db_session.commit()
    
    return {
        "workspace_id": str(ws.id),
        "artifact_id": str(art.id),
        "artifact_version_id": str(version.id),
        "log_data": log_data,
        "log_text": log_text
    }


def test_resolve_pdf__valid_locations__returns_snippet_and_metadata(evidence_resolver, sample_pdf_with_version):
    """
    EXIT TEST 1: PDF resolution test.
    
    Success criteria:
    - Resolves pdf:p={page}#char={start}-{end} format
    - Returns correct snippet from extracted text
    - Returns ok=True with all required fields
    """
    pdf_data = sample_pdf_with_version
    
    # Test 1: Resolve from page 1
    page1_text = pdf_data["page1_text"]
    search_str = "test content"
    start_idx = page1_text.find(search_str)
    end_idx = start_idx + len(search_str)
    
    location1 = f"pdf:p=1#char={start_idx}-{end_idx}"
    result1 = evidence_resolver.resolve(
        artifact_version_id=pdf_data["artifact_version_id"],
        location=location1
    )
    
    assert result1.ok is True
    assert result1.snippet == search_str
    assert result1.normalized_location == location1
    assert result1.mime == "text/plain"
    assert result1.source["type"] == "pdf"
    assert result1.source["version"] == 1
    
    # Test 2: Resolve from page 2
    page2_text = pdf_data["page2_text"]
    search_str2 = "different text"
    start_idx2 = page2_text.find(search_str2)
    end_idx2 = start_idx2 + len(search_str2)
    
    location2 = f"pdf:p=2#char={start_idx2}-{end_idx2}"
    result2 = evidence_resolver.resolve(
        artifact_version_id=pdf_data["artifact_version_id"],
        location=location2
    )
    
    assert result2.ok is True
    assert result2.snippet == search_str2
    
    # Test 3: Full page text
    location3 = f"pdf:p=1#char=0-{len(page1_text)}"
    result3 = evidence_resolver.resolve(
        artifact_version_id=pdf_data["artifact_version_id"],
        location=location3
    )
    
    assert result3.ok is True
    assert result3.snippet == page1_text


def test_resolve_log_char_range__valid_ranges__returns_substring(evidence_resolver, sample_log_with_version):
    """
    EXIT TEST 2: Log char-range resolution test.
    
    Success criteria:
    - Resolves log:char={start}-{end} format
    - Returns correct substring from plain-text log
    - Returns ok=True with all required fields
    """
    log_data = sample_log_with_version
    log_text = log_data["log_text"]
    
    # Test 1: Resolve substring "plain text log"
    search_str = "plain text log"
    start_idx = log_text.find(search_str)
    end_idx = start_idx + len(search_str)
    
    location = f"log:char={start_idx}-{end_idx}"
    result = evidence_resolver.resolve(
        artifact_version_id=log_data["artifact_version_id"],
        location=location
    )
    
    assert result.ok is True
    assert result.snippet == search_str
    assert result.normalized_location == location
    assert result.mime == "text/plain"
    assert result.source["type"] == "log"
    
    # Test 2: Resolve from start
    location2 = "log:char=0-7"
    result2 = evidence_resolver.resolve(
        artifact_version_id=log_data["artifact_version_id"],
        location=location2
    )
    
    assert result2.ok is True
    assert result2.snippet == log_text[0:7]
    
    # Test 3: Full log text
    location3 = f"log:char=0-{len(log_text)}"
    result3 = evidence_resolver.resolve(
        artifact_version_id=log_data["artifact_version_id"],
        location=location3
    )
    
    assert result3.ok is True
    assert result3.snippet == log_text


def test_resolve_log_jsonpath__valid_paths__returns_json_snippet(evidence_resolver, sample_log_with_version):
    """
    Test JSON log resolution with jsonpath.
    
    Success criteria:
    - Resolves log:jsonpath={jsonpath} format
    - Returns correct JSON value
    - Returns ok=True with mime=application/json
    """
    log_data = sample_log_with_version
    
    # Test 1: Resolve metrics.accuracy
    location1 = "log:jsonpath=$.metrics.accuracy"
    result1 = evidence_resolver.resolve(
        artifact_version_id=log_data["artifact_version_id"],
        location=location1
    )
    
    assert result1.ok is True
    assert "0.95" in result1.snippet
    assert result1.mime == "application/json"
    
    # Test 2: Resolve entire metrics object
    location2 = "log:jsonpath=$.metrics"
    result2 = evidence_resolver.resolve(
        artifact_version_id=log_data["artifact_version_id"],
        location=location2
    )
    
    assert result2.ok is True
    assert "accuracy" in result2.snippet
    assert "loss" in result2.snippet


def test_resolve__invalid_locations__returns_deterministic_errors(evidence_resolver, sample_pdf_with_version):
    """
    EXIT TEST 3: Bad grammar returns deterministic error.
    
    Success criteria:
    - Invalid formats return ok=False with error code
    - Error codes are deterministic (same input = same error)
    - Error messages are actionable
    """
    pdf_data = sample_pdf_with_version
    
    # Test 1: Invalid PDF format (missing char range)
    location1 = "pdf:p=1"
    result1 = evidence_resolver.resolve(
        artifact_version_id=pdf_data["artifact_version_id"],
        location=location1
    )
    
    assert result1.ok is False
    assert result1.code == "INVALID_LOCATION_FORMAT"
    assert "Expected: pdf:p={page}#char={start}-{end}" in result1.message
    
    # Test 2: Page out of range
    location2 = "pdf:p=999#char=0-10"
    result2 = evidence_resolver.resolve(
        artifact_version_id=pdf_data["artifact_version_id"],
        location=location2
    )
    
    assert result2.ok is False
    assert result2.code == "PAGE_OUT_OF_RANGE"
    
    # Test 3: Invalid char range (end < start)
    location3 = "pdf:p=1#char=100-50"
    result3 = evidence_resolver.resolve(
        artifact_version_id=pdf_data["artifact_version_id"],
        location=location3
    )
    
    assert result3.ok is False
    assert result3.code == "CHAR_RANGE_INVALID"
    
    # Test 4: Unsupported location format
    location4 = "invalid:format"
    result4 = evidence_resolver.resolve(
        artifact_version_id=pdf_data["artifact_version_id"],
        location=location4
    )
    
    assert result4.ok is False
    assert result4.code == "UNSUPPORTED_LOCATION"
    
    # Test 5: Invalid page (0-based instead of 1-based)
    location5 = "pdf:p=0#char=0-10"
    result5 = evidence_resolver.resolve(
        artifact_version_id=pdf_data["artifact_version_id"],
        location=location5
    )
    
    assert result5.ok is False
    assert result5.code == "PAGE_OUT_OF_RANGE"
    assert "1-based" in result5.message


def test_resolve__unknown_artifact_version__returns_not_found_error(evidence_resolver):
    """Test that non-existent artifact_version returns error."""
    import uuid
    result = evidence_resolver.resolve(
        artifact_version_id=str(uuid.uuid4()),
        location="pdf:p=1#char=0-10"
    )
    
    assert result.ok is False
    assert result.code == "ARTIFACT_VERSION_NOT_FOUND"


def test_resolve_pdf__char_range_exceeds_bounds__returns_char_range_invalid(evidence_resolver, sample_pdf_with_version):
    """Test that char ranges exceeding content bounds return error."""
    pdf_data = sample_pdf_with_version
    
    # Request char range beyond page text length
    location = "pdf:p=1#char=0-999999"
    result = evidence_resolver.resolve(
        artifact_version_id=pdf_data["artifact_version_id"],
        location=location
    )
    
    assert result.ok is False
    assert result.code == "CHAR_RANGE_INVALID"
    assert "invalid" in result.message.lower()


def test_resolve_log_jsonpath__path_missing__returns_jsonpath_not_found(evidence_resolver, sample_log_with_version):
    """Test that non-existent JSONPath returns error."""
    log_data = sample_log_with_version
    
    location = "log:jsonpath=$.nonexistent.field"
    result = evidence_resolver.resolve(
        artifact_version_id=log_data["artifact_version_id"],
        location=location
    )
    
    assert result.ok is False
    assert result.code == "JSONPATH_NOT_FOUND"


def test_resolve__same_input__returns_identical_output(evidence_resolver, sample_pdf_with_version):
    """
    Test that resolution is deterministic (same input = same output).
    
    Critical for citation validation and evidence verification.
    """
    pdf_data = sample_pdf_with_version
    
    # Resolve the same location multiple times
    location = "pdf:p=1#char=10-20"
    
    results = []
    for _ in range(3):
        result = evidence_resolver.resolve(
            artifact_version_id=pdf_data["artifact_version_id"],
            location=location
        )
        results.append(result)
    
    # All results should be identical
    assert all(r.ok == results[0].ok for r in results)
    assert all(r.snippet == results[0].snippet for r in results)
    assert all(r.normalized_location == results[0].normalized_location for r in results)
