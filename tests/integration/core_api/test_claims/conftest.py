import hashlib
import io
import json
import uuid

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


@pytest.fixture
def workspace_with_agent(db_session):
    """Create a test workspace and agent."""
    from database import Agent, Workspace

    ws = Workspace(
        id=str(uuid.uuid4()),
        name="Claims Test Workspace",
        phase="LIT_REVIEW",
    )
    db_session.add(ws)

    agent = Agent(
        id=str(uuid.uuid4()),
        moltbook_identity="test_agent_claims",
        display_name="Test Agent",
        reputation_score=100,
    )
    db_session.add(agent)
    db_session.commit()

    return ws, agent


@pytest.fixture
def pdf_artifact_with_evidence(storage, db_session, workspace_with_agent):
    """Create a PDF artifact with resolvable page text evidence."""
    from database import Artifact, ArtifactVersion

    ws, agent = workspace_with_agent

    artifact = Artifact(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        short_id="A1",
        content_type="application/pdf",
        created_by=agent.id,
    )
    db_session.add(artifact)

    buffer = io.BytesIO()
    canvas_obj = canvas.Canvas(buffer, pagesize=letter)
    canvas_obj.drawString(100, 750, "This PDF contains evidence for claim validation testing.")
    canvas_obj.showPage()
    canvas_obj.save()
    buffer.seek(0)
    pdf_bytes = buffer.read()

    binary_uri = f"s3://agora/{ws.id}/artifacts/{artifact.id}/v1/document.pdf"
    storage.put_object(binary_uri, pdf_bytes)

    page1_text = "This PDF contains evidence for claim validation testing."
    page1_uri = f"s3://agora/{ws.id}/artifacts/{artifact.id}/v1/pages/page_1.txt"
    storage.put_object(page1_uri, page1_text.encode("utf-8"))

    metadata = {"page_count": 1, "total_chars": len(page1_text)}
    metadata_uri = f"s3://agora/{ws.id}/artifacts/{artifact.id}/v1/metadata.json"
    storage.put_object(metadata_uri, json.dumps(metadata).encode("utf-8"))

    version = ArtifactVersion(
        id=str(uuid.uuid4()),
        artifact_id=artifact.id,
        version=1,
        content_hash=hashlib.sha256(pdf_bytes).hexdigest(),
        storage_uri=binary_uri,
        created_by=agent.id,
    )
    db_session.add(version)
    db_session.commit()

    return {
        "workspace": ws,
        "agent": agent,
        "artifact": artifact,
        "version": version,
        "page1_text": page1_text,
    }


@pytest.fixture
def other_workspace_artifact(storage, db_session):
    """Create an artifact version in a different workspace."""
    from database import Agent, Artifact, ArtifactVersion, Workspace

    other_ws = Workspace(
        id=str(uuid.uuid4()),
        name="Other Workspace",
        phase="LIT_REVIEW",
    )
    db_session.add(other_ws)

    agent = Agent(
        id=str(uuid.uuid4()),
        moltbook_identity="other_agent",
        display_name="Other Agent",
        reputation_score=50,
    )
    db_session.add(agent)
    db_session.flush()

    artifact = Artifact(
        id=str(uuid.uuid4()),
        workspace_id=other_ws.id,
        short_id="B1",
        content_type="application/pdf",
        created_by=agent.id,
    )
    db_session.add(artifact)

    buffer = io.BytesIO()
    canvas_obj = canvas.Canvas(buffer, pagesize=letter)
    canvas_obj.drawString(100, 750, "This is from another workspace.")
    canvas_obj.showPage()
    canvas_obj.save()
    buffer.seek(0)
    pdf_bytes = buffer.read()

    binary_uri = f"s3://agora/{other_ws.id}/artifacts/{artifact.id}/v1/document.pdf"
    storage.put_object(binary_uri, pdf_bytes)

    page1_text = "This is from another workspace."
    page1_uri = f"s3://agora/{other_ws.id}/artifacts/{artifact.id}/v1/pages/page_1.txt"
    storage.put_object(page1_uri, page1_text.encode("utf-8"))

    metadata = {"page_count": 1, "total_chars": len(page1_text)}
    metadata_uri = f"s3://agora/{other_ws.id}/artifacts/{artifact.id}/v1/metadata.json"
    storage.put_object(metadata_uri, json.dumps(metadata).encode("utf-8"))

    version = ArtifactVersion(
        id=str(uuid.uuid4()),
        artifact_id=artifact.id,
        version=1,
        content_hash=hashlib.sha256(pdf_bytes).hexdigest(),
        storage_uri=binary_uri,
        created_by=agent.id,
    )
    db_session.add(version)
    db_session.commit()

    return {
        "workspace": other_ws,
        "artifact": artifact,
        "version": version,
    }
