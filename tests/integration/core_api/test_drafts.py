"""
Exit tests for Component 12: Drafts + Versioning

Per checklist:
- EXIT TEST: Draft version created -> content_hash present -> can fetch exact Markdown

Tests run against real containers (Postgres, MinIO, not mocked).
"""
import pytest
import uuid
import json
from sqlalchemy import text

from storage import create_storage_from_env


@pytest.fixture
def workspace_with_agent(db_session):
    """Create test workspace and agent."""
    from database import Workspace, Agent
    
    ws = Workspace(
        id=str(uuid.uuid4()),
        name="Drafts Test Workspace",
        phase="LIT_REVIEW"
    )
    db_session.add(ws)
    
    agent = Agent(
        id=str(uuid.uuid4()),
        moltbook_identity="test_agent_drafts",
        display_name="Test Agent",
        reputation_score=100
    )
    db_session.add(agent)
    db_session.commit()
    
    return ws, agent


def _seed_skeptic_membership(db_session, workspace_id: str) -> str:
    """Finalization gate requires an active Skeptic role assignment."""
    skeptic_id = str(uuid.uuid4())
    db_session.execute(
        text(
            """
            INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
            VALUES (:id, :moltbook_id, :name, :reputation, NOW())
            """
        ),
        {
            "id": skeptic_id,
            "moltbook_id": f"moltbook-{skeptic_id}",
            "name": "Skeptic Agent",
            "reputation": 100,
        },
    )
    skeptic_role_id = db_session.execute(
        text("SELECT id FROM roles WHERE name = 'Skeptic'")
    ).fetchone()[0]
    db_session.execute(
        text(
            """
            INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status, joined_at)
            VALUES (:workspace_id, :agent_id, :role_id, 'active', NOW())
            """
        ),
        {
            "workspace_id": str(workspace_id),
            "agent_id": skeptic_id,
            "role_id": str(skeptic_role_id),
        },
    )
    return skeptic_id


def _insert_rule_check(
    db_session,
    workspace_id: str,
    version_id: str,
    rule_name: str,
    status: str,
    details: dict,
) -> None:
    db_session.execute(
        text(
            """
            INSERT INTO rule_checks (
                id, workspace_id, target_type, target_id, rule_name, status, details, created_at
            )
            VALUES (
                :id, :workspace_id, 'artifact_version', :target_id, :rule_name, :status, :details, NOW()
            )
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "workspace_id": str(workspace_id),
            "target_id": str(version_id),
            "rule_name": rule_name,
            "status": status,
            "details": details,
        },
    )


def _seed_finalization_gate_pass(db_session, workspace_id: str, draft_version_id: str) -> None:
    db_session.execute(
        text("UPDATE workspaces SET phase = 'FINALIZED' WHERE id = :workspace_id"),
        {"workspace_id": str(workspace_id)},
    )
    _seed_skeptic_membership(db_session, str(workspace_id))
    _insert_rule_check(
        db_session,
        workspace_id=str(workspace_id),
        version_id=str(draft_version_id),
        rule_name="citation_check",
        status="pass",
        details={"all_citations_resolve": True},
    )
    _insert_rule_check(
        db_session,
        workspace_id=str(workspace_id),
        version_id=str(draft_version_id),
        rule_name="critique_sufficiency",
        status="pass",
        details={},
    )
    db_session.commit()


def test_draft_create__empty_workspace__allocates_short_id_and_persists_metadata(db_session, workspace_with_agent):
    """Test basic draft creation."""
    from draft_routes import create_draft, CreateDraftRequest
    
    ws, agent = workspace_with_agent
    
    # Mock current_agent
    mock_agent = {"agent_id": agent.id}
    
    # Create DB wrapper
    db_wrapper = db_session
    
    # Create draft
    request = CreateDraftRequest(title="Test Draft")
    
    result = create_draft(
        workspace_id=uuid.UUID(str(ws.id)),
        request=request,
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    # Verify draft created
    assert result.workspace_id == str(ws.id)
    assert result.short_id == "D1"
    assert result.title == "Test Draft"
    assert result.status is None
    assert result.final_version_id is None
    
    # Verify in database
    draft = db_session.execute(
        text("SELECT id, type, metadata FROM artifacts WHERE id = :id"),
        {"id": result.id}
    ).fetchone()
    assert draft is not None
    assert draft[1] == "draft"
    metadata = draft[2] if isinstance(draft[2], dict) else json.loads(draft[2])
    assert metadata["title"] == "Test Draft"


def test_draft_version_create__markdown_content__stores_hash_and_retrievable_bytes(db_session, workspace_with_agent):
    """
    EXIT TEST: Draft version created -> content_hash present -> can fetch exact Markdown.
    
    Success criteria:
    - Draft version created with Markdown content
    - content_hash is present and non-empty
    - Content can be fetched from storage
    - Fetched content matches original exactly
    """
    from draft_routes import create_draft, create_draft_version, CreateDraftRequest, CreateDraftVersionRequest
    from sqlalchemy import text
    
    ws, agent = workspace_with_agent
    storage = create_storage_from_env()
    
    # Mock agent
    mock_agent = {"agent_id": agent.id}
    
    # Create DB wrapper
    db_wrapper = db_session
    
    # Create draft
    draft_request = CreateDraftRequest(title="Exit Test Draft")
    draft = create_draft(
        workspace_id=uuid.UUID(str(ws.id)),
        request=draft_request,
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    # Create draft version with Markdown content
    markdown_content = """# Test Draft

This is a test draft with **bold** and *italic* text.

## Claims

[[claim:claim_id_1]] This is a claim.

## Citations

[[cite:artifact_version_id_1|pdf:p=1#char=0-10]]
"""
    
    version_request = CreateDraftVersionRequest(content=markdown_content)
    version = create_draft_version(
        draft_id=uuid.UUID(str(draft.id)),
        request=version_request,
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    # Verify content_hash is present
    assert version.content_hash is not None
    assert len(version.content_hash) == 64  # SHA256 hex length
    
    # Verify version in database
    db_version = db_session.execute(
        text("SELECT content_hash, storage_uri FROM artifact_versions WHERE id = :id"),
        {"id": version.id}
    ).fetchone()
    assert db_version is not None
    assert db_version[0] == version.content_hash
    
    # Fetch content from storage
    storage_uri = f"s3://agora/{ws.id}/artifacts/{draft.id}/v{version.version}/draft.md"
    fetched_content = storage.get_object(storage_uri).read().decode("utf-8")
    
    # Verify fetched content matches original exactly
    assert fetched_content == markdown_content
    
    # Verify content_hash matches computed hash
    import hashlib
    computed_hash = hashlib.sha256(markdown_content.encode("utf-8")).hexdigest()
    assert version.content_hash == computed_hash


def test_draft_version_create__multiple_versions__increments_and_hashes_unique(db_session, workspace_with_agent):
    """Test creating multiple versions of a draft."""
    from draft_routes import create_draft, create_draft_version, CreateDraftRequest, CreateDraftVersionRequest
    from sqlalchemy import text
    
    ws, agent = workspace_with_agent
    mock_agent = {"agent_id": agent.id}
    
    db_wrapper = db_session
    
    # Create draft
    draft = create_draft(
        workspace_id=uuid.UUID(str(ws.id)),
        request=CreateDraftRequest(title="Multi-Version Draft"),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    # Create version 1
    v1 = create_draft_version(
        draft_id=uuid.UUID(str(draft.id)),
        request=CreateDraftVersionRequest(content="Version 1 content"),
        current_agent=mock_agent,
        db=db_wrapper
    )
    assert v1.version == 1
    
    # Create version 2
    v2 = create_draft_version(
        draft_id=uuid.UUID(str(draft.id)),
        request=CreateDraftVersionRequest(content="Version 2 content - updated"),
        current_agent=mock_agent,
        db=db_wrapper
    )
    assert v2.version == 2
    
    # Create version 3
    v3 = create_draft_version(
        draft_id=uuid.UUID(str(draft.id)),
        request=CreateDraftVersionRequest(content="Version 3 content - final"),
        current_agent=mock_agent,
        db=db_wrapper
    )
    assert v3.version == 3
    
    # Each version has unique content_hash
    assert v1.content_hash != v2.content_hash
    assert v2.content_hash != v3.content_hash
    assert v1.content_hash != v3.content_hash


def test_draft_versions_list__multiple_versions__returns_descending(db_session, workspace_with_agent):
    """Test listing draft versions."""
    from draft_routes import create_draft, create_draft_version, list_draft_versions, CreateDraftRequest, CreateDraftVersionRequest
    from sqlalchemy import text
    
    ws, agent = workspace_with_agent
    mock_agent = {"agent_id": agent.id}
    
    db_wrapper = db_session
    
    # Create draft with multiple versions
    draft = create_draft(
        workspace_id=uuid.UUID(str(ws.id)),
        request=CreateDraftRequest(title="List Test Draft"),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    create_draft_version(
        draft_id=uuid.UUID(str(draft.id)),
        request=CreateDraftVersionRequest(content="V1"),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    create_draft_version(
        draft_id=uuid.UUID(str(draft.id)),
        request=CreateDraftVersionRequest(content="V2"),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    # List versions
    result = list_draft_versions(
        draft_id=uuid.UUID(str(draft.id)),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    # Verify results
    assert result["draft_id"] == draft.id
    assert result["total"] == 2
    assert len(result["versions"]) == 2
    
    # Versions should be in descending order (newest first)
    assert result["versions"][0]["version"] == 2
    assert result["versions"][1]["version"] == 1


def test_draft_version_create__after_finalization__returns_409(db_session, workspace_with_agent):
    """Test that creating a version for finalized draft fails."""
    from draft_routes import create_draft, create_draft_version, finalize_draft, CreateDraftRequest, CreateDraftVersionRequest, FinalizeDraftRequest
    from fastapi import HTTPException
    from sqlalchemy import text
    
    ws, agent = workspace_with_agent
    mock_agent = {"agent_id": agent.id}
    mock_system = {"token_type": "system"}
    
    db_wrapper = db_session
    
    # Create draft with version
    draft = create_draft(
        workspace_id=uuid.UUID(str(ws.id)),
        request=CreateDraftRequest(title="Finalize Test"),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    version = create_draft_version(
        draft_id=uuid.UUID(str(draft.id)),
        request=CreateDraftVersionRequest(content="Initial content"),
        current_agent=mock_agent,
        db=db_wrapper
    )

    _seed_finalization_gate_pass(
        db_session=db_session,
        workspace_id=str(ws.id),
        draft_version_id=version.id,
    )
    
    # Finalize draft
    finalize_draft(
        draft_id=uuid.UUID(str(draft.id)),
        request=FinalizeDraftRequest(draft_artifact_version_id=version.id),
        system_token=mock_system,
        db=db_wrapper
    )
    
    # Try to create another version (should fail)
    with pytest.raises(HTTPException) as exc_info:
        create_draft_version(
            draft_id=uuid.UUID(str(draft.id)),
            request=CreateDraftVersionRequest(content="New content after finalization"),
            current_agent=mock_agent,
            db=db_wrapper
        )
    
    assert exc_info.value.status_code == 409
    assert "already finalized" in exc_info.value.detail


def test_draft_create__multiple_drafts__short_ids_increment(db_session, workspace_with_agent):
    """Test that draft short_ids are allocated correctly (D1, D2, D3...)."""
    from draft_routes import create_draft, CreateDraftRequest
    from sqlalchemy import text
    
    ws, agent = workspace_with_agent
    mock_agent = {"agent_id": agent.id}
    
    db_wrapper = db_session
    
    # Create multiple drafts
    d1 = create_draft(
        workspace_id=uuid.UUID(str(ws.id)),
        request=CreateDraftRequest(title="Draft 1"),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    d2 = create_draft(
        workspace_id=uuid.UUID(str(ws.id)),
        request=CreateDraftRequest(title="Draft 2"),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    d3 = create_draft(
        workspace_id=uuid.UUID(str(ws.id)),
        request=CreateDraftRequest(title="Draft 3"),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    # Verify short_ids
    assert d1.short_id == "D1"
    assert d2.short_id == "D2"
    assert d3.short_id == "D3"


def test_draft_finalize__valid_version__emits_draft_finalized_event(db_session, workspace_with_agent):
    """Test that finalizing a draft emits draft.finalized event."""
    from draft_routes import create_draft, create_draft_version, finalize_draft, CreateDraftRequest, CreateDraftVersionRequest, FinalizeDraftRequest
    from sqlalchemy import text
    
    ws, agent = workspace_with_agent
    mock_agent = {"agent_id": agent.id}
    mock_system = {"token_type": "system"}
    
    db_wrapper = db_session
    
    # Create draft with version
    draft = create_draft(
        workspace_id=uuid.UUID(str(ws.id)),
        request=CreateDraftRequest(title="Event Test"),
        current_agent=mock_agent,
        db=db_wrapper
    )
    
    version = create_draft_version(
        draft_id=uuid.UUID(str(draft.id)),
        request=CreateDraftVersionRequest(content="Content"),
        current_agent=mock_agent,
        db=db_wrapper
    )

    _seed_finalization_gate_pass(
        db_session=db_session,
        workspace_id=str(ws.id),
        draft_version_id=version.id,
    )
    
    # Finalize draft
    finalize_draft(
        draft_id=uuid.UUID(str(draft.id)),
        request=FinalizeDraftRequest(draft_artifact_version_id=version.id),
        system_token=mock_system,
        db=db_wrapper
    )
    
    # Verify event was emitted
    event = db_session.execute(
        text("""
            SELECT event_type, actor_type, payload
            FROM events
            WHERE workspace_id = :ws_id AND event_type = 'draft.finalized'
        """),
        {"ws_id": ws.id}
    ).fetchone()
    
    assert event is not None
    assert event[0] == "draft.finalized"
    assert event[1] == "system"
    
    payload = event[2] if isinstance(event[2], dict) else json.loads(event[2])
    assert payload["draft_id"] == draft.id
    assert payload["final_version_id"] == version.id


def test_draft_finalize__gate_failure__persists_rule_check_and_log(db_session, workspace_with_agent):
    """Failed finalization attempts must persist explicit gate outcomes."""
    from draft_routes import (
        create_draft,
        create_draft_version,
        finalize_draft,
        CreateDraftRequest,
        CreateDraftVersionRequest,
        FinalizeDraftRequest,
    )
    from fastapi import HTTPException

    ws, agent = workspace_with_agent
    mock_agent = {"agent_id": agent.id}
    mock_system = {"token_type": "system"}

    draft = create_draft(
        workspace_id=uuid.UUID(str(ws.id)),
        request=CreateDraftRequest(title="Gate Failure Test"),
        current_agent=mock_agent,
        db=db_session,
    )
    version = create_draft_version(
        draft_id=uuid.UUID(str(draft.id)),
        request=CreateDraftVersionRequest(content="Version content"),
        current_agent=mock_agent,
        db=db_session,
    )

    _seed_skeptic_membership(db_session, str(ws.id))
    db_session.execute(
        text("UPDATE workspaces SET phase = 'FINALIZED' WHERE id = :workspace_id"),
        {"workspace_id": str(ws.id)},
    )
    _insert_rule_check(
        db_session,
        workspace_id=str(ws.id),
        version_id=version.id,
        rule_name="citation_check",
        status="fail",
        details={"all_citations_resolve": True},
    )
    _insert_rule_check(
        db_session,
        workspace_id=str(ws.id),
        version_id=version.id,
        rule_name="critique_sufficiency",
        status="pass",
        details={},
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        finalize_draft(
            draft_id=uuid.UUID(str(draft.id)),
            request=FinalizeDraftRequest(draft_artifact_version_id=version.id),
            system_token=mock_system,
            db=db_session,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"] == "FINALIZATION_GATE_BLOCKED"
    assert "Citation coverage check failed" in exc_info.value.detail["reasons"]

    gate_row = db_session.execute(
        text(
            """
            SELECT status, details
            FROM rule_checks
            WHERE workspace_id = :workspace_id
              AND target_type = 'artifact_version'
              AND target_id = :target_id
              AND rule_name = 'finalization_gate'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"workspace_id": str(ws.id), "target_id": version.id},
    ).fetchone()

    assert gate_row is not None
    assert gate_row[0] == "fail"
    gate_details = gate_row[1] if isinstance(gate_row[1], dict) else json.loads(gate_row[1])
    assert "Citation coverage check failed" in gate_details["reasons"]

    log_row = db_session.execute(
        text(
            """
            SELECT action, payload
            FROM logs
            WHERE workspace_id = :workspace_id
              AND action = 'draft.finalization_gate_evaluated'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"workspace_id": str(ws.id)},
    ).fetchone()

    assert log_row is not None
    assert log_row[0] == "draft.finalization_gate_evaluated"
    log_payload = log_row[1] if isinstance(log_row[1], dict) else json.loads(log_row[1])
    assert log_payload["status"] == "FAIL"
    assert "Citation coverage check failed" in log_payload["reasons"]


def test_draft_finalize_endpoint__agent_token__returns_403(test_client, mock_agent_token):
    """Finalize endpoint is system-only and must reject agent tokens."""
    response = test_client.post(
        f"/drafts/{uuid.uuid4()}/finalize",
        json={"draft_artifact_version_id": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {mock_agent_token}"},
    )
    assert response.status_code == 403
