"""
Exit tests for Component 16: Repo ingestion activity

Per checklist:
1. Ingest a small repo fixture
2. Resolve repo:path=...#Lx-Ly returns correct snippet

Tests repo ingestion end-to-end:
- Git clone (or fixture)
- File indexing
- Storage in MinIO
- Evidence resolution
"""
import pytest
import uuid
import json

from storage import create_storage_from_env
from database import Workspace, Agent, Artifact, ArtifactVersion, DBWrapper
from tests.helpers.git_repo import temporary_git_repo


@pytest.fixture
def repo_fixture():
    """Create a minimal test repository."""
    files = {
        "README.md": (
            "# Test Repository\n\n"
            "This is a test repository.\n"
            "Line 4\n"
            "Line 5\n"
        ),
        "src/main.py": (
            "#!/usr/bin/env python3\n"
            "# Main module\n"
            "\n"
            "def hello():\n"
            "    print('Hello, world!')\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    hello()\n"
        ),
        "src/utils.py": (
            "# Utility functions\n"
            "\n"
            "def add(a, b):\n"
            "    return a + b\n"
            "\n"
            "def multiply(a, b):\n"
            "    return a * b\n"
        ),
    }

    with temporary_git_repo(files, message="Initial commit") as fixture:
        yield fixture


@pytest.fixture
def repo_setup(db_session):
    """Set up workspace and agent for repo ingestion tests."""
    ws = Workspace(
        id=str(uuid.uuid4()),
        name="Repo Ingestion Test",
        phase="EXPERIMENTATION"
    )
    db_session.add(ws)

    agent = Agent(
        id=str(uuid.uuid4()),
        moltbook_identity="test_repo_agent",
        display_name="Repo Test Agent",
        reputation_score=100
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


def test_repo_ingest_activity__repo_fixture__creates_artifact_version_and_storage(db_session, repo_setup, repo_fixture):
    """
    EXIT TEST 1: Ingest a small repo fixture.

    Verifies:
    - Git clone works
    - Files are indexed
    - Snapshot stored in MinIO
    - artifact_versions row created
    - Metadata includes file list
    """
    from repo_ingest import RepoIngestActivity

    ws, agent = repo_setup
    repo_path, commit_hash = repo_fixture
    storage = create_storage_from_env()

    # Create code artifact
    artifact_id = str(uuid.uuid4())
    artifact = Artifact(
        id=artifact_id,
        workspace_id=ws.id,
        short_id="C001",
        type="code",
        metadata={"repo_url": f"file://{repo_path}"},
        storage_uri=f"s3://agora/{ws.id}/artifacts/{artifact_id}/",
        created_by=agent.id
    )
    db_session.add(artifact)
    db_session.commit()

    # Create DB wrapper
    db = DBWrapper(db_session)

    # Execute repo_ingest activity
    activity = RepoIngestActivity(storage, db)

    result = activity.ingest_repo(
        artifact_id=artifact_id,
        workspace_id=ws.id,
        repo_url=f"file://{repo_path}",
        created_by=agent.id
    )

    # Verify result
    assert result["artifact_version_id"]
    assert result["version"] == 1
    assert result["commit_hash"] == commit_hash
    assert result["file_count"] >= 3  # README.md, src/main.py, src/utils.py

    # Verify artifact_version created
    version = db_session.query(ArtifactVersion).filter_by(
        id=result["artifact_version_id"]
    ).first()

    assert version is not None
    assert str(version.artifact_id) == artifact_id
    assert version.version == 1
    assert version.content_hash == commit_hash

    # Verify metadata stored in MinIO
    metadata_bytes = storage.get_object(result["metadata_uri"]).read()
    metadata = json.loads(metadata_bytes.decode("utf-8"))

    assert metadata["repo_url"] == f"file://{repo_path}"
    assert metadata["commit_hash"] == commit_hash
    assert metadata["file_count"] == result["file_count"]
    assert len(metadata["files"]) == result["file_count"]

    # Verify expected files are indexed
    file_paths = [f["path"] for f in metadata["files"]]
    assert "README.md" in file_paths
    assert "src/main.py" in file_paths
    assert "src/utils.py" in file_paths

    # Verify file metadata
    main_py = next(f for f in metadata["files"] if f["path"] == "src/main.py")
    assert main_py["is_text"] is True
    assert main_py["lines"] == 8  # 8 lines in main.py


def test_repo_evidence_resolution__repo_location__returns_expected_snippet(db_session, repo_setup, repo_fixture):
    """
    EXIT TEST 2: Resolve repo:path=...#Lx-Ly returns correct snippet.

    Verifies:
    - Location grammar parses correctly
    - File content retrieves from MinIO
    - Line range extraction works
    - Snippet matches expected content
    """
    from repo_ingest import RepoIngestActivity
    from evidence_resolver import EvidenceResolver

    ws, agent = repo_setup
    repo_path, commit_hash = repo_fixture
    storage = create_storage_from_env()

    # Create and ingest repo artifact
    artifact_id = str(uuid.uuid4())
    artifact = Artifact(
        id=artifact_id,
        workspace_id=ws.id,
        short_id="C002",
        type="code",
        metadata={"repo_url": f"file://{repo_path}"},
        storage_uri=f"s3://agora/{ws.id}/artifacts/{artifact_id}/",
        created_by=agent.id
    )
    db_session.add(artifact)
    db_session.commit()

    db = DBWrapper(db_session)

    # Ingest repo
    activity = RepoIngestActivity(storage, db)
    result = activity.ingest_repo(
        artifact_id=artifact_id,
        workspace_id=ws.id,
        repo_url=f"file://{repo_path}",
        created_by=agent.id
    )

    artifact_version_id = result["artifact_version_id"]

    # Test 1: Resolve lines from main.py
    resolver = EvidenceResolver(storage, db_session)

    location1 = "repo:path=src/main.py#L4-L5"
    result1 = resolver.resolve(artifact_version_id, location1)

    assert result1.ok is True
    assert result1.snippet == "def hello():\n    print('Hello, world!')"
    assert result1.normalized_location == location1
    assert result1.mime == "text/plain"
    assert result1.source["file_path"] == "src/main.py"
    assert result1.source["start_line"] == 4
    assert result1.source["end_line"] == 5
    assert result1.source["commit_hash"] == commit_hash

    # Test 2: Resolve lines from utils.py
    location2 = "repo:path=src/utils.py#L3-L4"
    result2 = resolver.resolve(artifact_version_id, location2)

    assert result2.ok is True
    assert result2.snippet == "def add(a, b):\n    return a + b"

    # Test 3: Resolve single line from README
    location3 = "repo:path=README.md#L3-L3"
    result3 = resolver.resolve(artifact_version_id, location3)

    assert result3.ok is True
    assert result3.snippet == "This is a test repository."

    # Test 4: Invalid location format
    location4 = "repo:invalid_format"
    result4 = resolver.resolve(artifact_version_id, location4)

    assert result4.ok is False
    assert result4.code == "INVALID_LOCATION_FORMAT"

    # Test 5: File not found
    location5 = "repo:path=nonexistent.py#L1-L2"
    result5 = resolver.resolve(artifact_version_id, location5)

    assert result5.ok is False
    assert result5.code == "PATH_NOT_FOUND"

    # Test 6: Line out of range
    location6 = "repo:path=src/main.py#L100-L200"
    result6 = resolver.resolve(artifact_version_id, location6)

    assert result6.ok is False
    assert result6.code == "LINE_RANGE_INVALID"


def test_repo_ingest_endpoint__agent_request__creates_repo_artifact(db_session, repo_setup, repo_fixture):
    """
    Test POST /workspaces/{id}/requests/ingest_repo endpoint.

    Verifies:
    - Endpoint creates artifact
    - Starts repo_ingest activity
    - Returns tracking IDs
    - Activity completes successfully
    """
    from sqlalchemy import text
    from request_routes import request_ingest_repo, IngestRepoRequest

    ws, agent = repo_setup
    repo_path, commit_hash = repo_fixture

    # Mock agent token
    from auth_middleware import AgentContext
    mock_agent = AgentContext(
        agent_id=str(agent.id),
        moltbook_id=str(agent.moltbook_id),
        reputation=int(agent.reputation_score or 0),
        workspace_id=None,
    )

    # Call endpoint
    import asyncio

    async def run_test():
        response = await request_ingest_repo(
            workspace_id=uuid.UUID(str(ws.id)),
            request=IngestRepoRequest(
                repo_url=f"file://{repo_path}",
                branch=None,
                commit_hash=None
            ),
            current_agent=mock_agent,
            db=db_session
        )
        return response

    response = asyncio.run(run_test())

    # Verify response
    assert response.artifact_id
    assert response.activity_run_id
    assert commit_hash[:8] in response.message

    # Verify artifact created
    artifact = db_session.query(Artifact).filter_by(id=response.artifact_id).first()
    assert artifact is not None
    assert str(artifact.workspace_id) == str(ws.id)
    assert artifact.type == "code"

    # Verify artifact_version created
    version = db_session.query(ArtifactVersion).filter_by(artifact_id=response.artifact_id).first()
    assert version is not None
    assert version.content_hash == commit_hash

    # Verify activity_run completed
    activity_run = db_session.execute(
        "SELECT status FROM activity_runs WHERE id = :id",
        {"id": response.activity_run_id}
    ).fetchone()

    assert activity_run is not None
    assert activity_run[0] == "completed"


def test_repo_ingest_endpoint__idempotency_key__dedupes(db_session, repo_setup, repo_fixture):
    """
    Test repo ingestion idempotency.

    Verifies:
    - Second ingest with same commit_hash returns existing artifact
    - No duplicate artifacts/versions created
    """
    from sqlalchemy import text
    from request_routes import request_ingest_repo, IngestRepoRequest

    ws, agent = repo_setup
    repo_path, commit_hash = repo_fixture

    from auth_middleware import AgentContext
    mock_agent = AgentContext(
        agent_id=str(agent.id),
        moltbook_id=str(agent.moltbook_id),
        reputation=int(agent.reputation_score or 0),
        workspace_id=None,
    )

    import asyncio

    async def ingest():
        return await request_ingest_repo(
            workspace_id=uuid.UUID(str(ws.id)),
            request=IngestRepoRequest(
                repo_url=f"file://{repo_path}",
                commit_hash=commit_hash
            ),
            current_agent=mock_agent,
            db=db_session
        )

    # First ingest
    response1 = asyncio.run(ingest())
    artifact_id1 = response1.artifact_id

    # Second ingest with same commit
    response2 = asyncio.run(ingest())
    artifact_id2 = response2.artifact_id

    # Should return same artifact
    assert artifact_id1 == artifact_id2
    assert "already ingested" in response2.message.lower()

    # Verify only one artifact created
    count = db_session.execute(
        """
        SELECT COUNT(*) FROM artifacts
        WHERE workspace_id = :ws_id AND type = 'code'
        """,
        {"ws_id": ws.id}
    ).fetchone()[0]

    assert count == 1
