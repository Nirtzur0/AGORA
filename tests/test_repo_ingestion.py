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
import os
import tempfile
import shutil
from pathlib import Path

from storage import create_storage_from_env
from database import Workspace, Agent, Artifact, ArtifactVersion, DBWrapper


@pytest.fixture
def test_repo_fixture():
    """Create a minimal test repository."""
    temp_dir = tempfile.mkdtemp(prefix="test_repo_")
    repo_path = Path(temp_dir)
    
    # Initialize git repo
    import subprocess
    subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, check=True, capture_output=True)
    
    # Create test files
    (repo_path / "README.md").write_text(
        "# Test Repository\n\n"
        "This is a test repository.\n"
        "Line 4\n"
        "Line 5\n"
    )
    
    src_dir = repo_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text(
        "#!/usr/bin/env python3\n"
        "# Main module\n"
        "\n"
        "def hello():\n"
        "    print('Hello, world!')\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    hello()\n"
    )
    
    (src_dir / "utils.py").write_text(
        "# Utility functions\n"
        "\n"
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "def multiply(a, b):\n"
        "    return a * b\n"
    )
    
    # Commit files
    subprocess.run(["git", "add", "."], cwd=temp_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_dir, check=True, capture_output=True)
    
    # Get commit hash
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=temp_dir,
        check=True,
        capture_output=True,
        text=True
    )
    commit_hash = result.stdout.strip()
    
    yield temp_dir, commit_hash
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def repo_setup(db_session):
    """Set up workspace and agent for repo ingestion tests."""
    ws = Workspace(
        id=str(uuid.uuid4()),
        name="Repo Ingestion Test",
        phase="code_replication"
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
    
    return ws, agent


def test_repo_ingest_activity(db_session, repo_setup, test_repo_fixture):
    """
    EXIT TEST 1: Ingest a small repo fixture.
    
    Verifies:
    - Git clone works
    - Files are indexed
    - Snapshot stored in MinIO
    - artifact_versions row created
    - Metadata includes file list
    """
    import sys
    sys.path.insert(0, "/Users/nirtzur/Documents/projects/AGORA/apps/worker")
    from repo_ingest import RepoIngestActivity
    
    ws, agent = repo_setup
    repo_path, commit_hash = test_repo_fixture
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
    
    print(f"✓ Repo ingested: {result['file_count']} files at commit {commit_hash[:8]}")


def test_repo_evidence_resolution(db_session, repo_setup, test_repo_fixture):
    """
    EXIT TEST 2: Resolve repo:path=...#Lx-Ly returns correct snippet.
    
    Verifies:
    - Location grammar parses correctly
    - File content retrieves from MinIO
    - Line range extraction works
    - Snippet matches expected content
    """
    import sys
    sys.path.insert(0, "/Users/nirtzur/Documents/projects/AGORA/apps/worker")
    sys.path.insert(0, "/Users/nirtzur/Documents/projects/AGORA/apps/core-api")
    from repo_ingest import RepoIngestActivity
    from evidence_resolver import EvidenceResolver
    
    ws, agent = repo_setup
    repo_path, commit_hash = test_repo_fixture
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
    
    print(f"✓ Resolved src/main.py#L4-L5: {repr(result1.snippet[:30])}")
    
    # Test 2: Resolve lines from utils.py
    location2 = "repo:path=src/utils.py#L3-L4"
    result2 = resolver.resolve(artifact_version_id, location2)
    
    assert result2.ok is True
    assert result2.snippet == "def add(a, b):\n    return a + b"
    
    print(f"✓ Resolved src/utils.py#L3-L4: {repr(result2.snippet)}")
    
    # Test 3: Resolve single line from README
    location3 = "repo:path=README.md#L3-L3"
    result3 = resolver.resolve(artifact_version_id, location3)
    
    assert result3.ok is True
    assert result3.snippet == "This is a test repository."
    
    print(f"✓ Resolved README.md#L3: {repr(result3.snippet)}")
    
    # Test 4: Invalid location format
    location4 = "repo:invalid_format"
    result4 = resolver.resolve(artifact_version_id, location4)
    
    assert result4.ok is False
    assert result4.code == "INVALID_LOCATION_FORMAT"
    
    print(f"✓ Invalid format rejected: {result4.code}")
    
    # Test 5: File not found
    location5 = "repo:path=nonexistent.py#L1-L2"
    result5 = resolver.resolve(artifact_version_id, location5)
    
    assert result5.ok is False
    assert result5.code == "FILE_NOT_FOUND"
    
    print(f"✓ Nonexistent file rejected: {result5.code}")
    
    # Test 6: Line out of range
    location6 = "repo:path=src/main.py#L100-L200"
    result6 = resolver.resolve(artifact_version_id, location6)
    
    assert result6.ok is False
    assert result6.code == "LINE_OUT_OF_RANGE"
    
    print(f"✓ Out of range lines rejected: {result6.code}")


def test_repo_ingest_endpoint(db_session, repo_setup, test_repo_fixture):
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
    repo_path, commit_hash = test_repo_fixture
    
    # Create DB wrapper
    db = DBWrapper(db_session)
    
    # Mock agent token
    from auth_middleware import AgentContext
    mock_agent = AgentContext(
        agent_id=str(agent.id),
        moltbook_identity=agent.moltbook_identity,
        is_system=False,
        reputation=agent.reputation_score,
        workspace_id=None
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
            db=db
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
    assert artifact.workspace_id == str(ws.id)
    assert artifact.type == "code"
    
    # Verify artifact_version created
    version = db_session.query(ArtifactVersion).filter_by(artifact_id=response.artifact_id).first()
    assert version is not None
    assert version.content_hash == commit_hash
    
    # Verify activity_run completed
    activity_run = db.execute(
        "SELECT status FROM activity_runs WHERE id = :id",
        {"id": response.activity_run_id}
    ).fetchone()
    
    assert activity_run is not None
    assert activity_run[0] == "completed"
    
    print(f"✓ Endpoint test passed: artifact {response.artifact_id[:8]}, activity {response.activity_run_id[:8]}")


def test_repo_ingest_idempotency(db_session, repo_setup, test_repo_fixture):
    """
    Test repo ingestion idempotency.
    
    Verifies:
    - Second ingest with same commit_hash returns existing artifact
    - No duplicate artifacts/versions created
    """
    from sqlalchemy import text
    from request_routes import request_ingest_repo, IngestRepoRequest
    
    ws, agent = repo_setup
    repo_path, commit_hash = test_repo_fixture
    
    db = DBWrapper(db_session)
    
    from auth_middleware import AgentContext
    mock_agent = AgentContext(
        agent_id=str(agent.id),
        moltbook_identity=agent.moltbook_identity,
        is_system=False,
        reputation=agent.reputation_score,
        workspace_id=None
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
            db=db
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
    count = db.execute(
        """
        SELECT COUNT(*) FROM artifacts
        WHERE workspace_id = :ws_id AND type = 'code'
        """,
        {"ws_id": ws.id}
    ).fetchone()[0]
    
    assert count == 1
    
    print(f"✓ Idempotency test passed: same artifact {artifact_id1[:8]} returned")
