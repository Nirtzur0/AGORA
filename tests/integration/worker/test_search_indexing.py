"""
Tests for Search and Indexing (Component 22)

Per spec §4.13, §6.5, §9:
- Tests Postgres FTS indexing for PDF text, repo files, and logs
- Tests GET /search endpoint with relevance ranking
- Tests workspace filtering and access control
"""

import asyncio
import pytest
import uuid
from sqlalchemy import text

from apps.worker.indexing_activities import index_artifact_content, index_pdf_text, index_repo_file


# Fixtures

@pytest.fixture
def worker_db(migrated_db):
    """
    Create a worker-style DB connection.

    Note: indexing activities create their own DB sessions and commit, so these
    tests must perform explicit cleanup (they cannot rely on db_session rollback).
    """
    from apps.worker.database import get_db_connection
    conn = get_db_connection()

    created = {
        "agent_ids": set(),
        "workspace_ids": set(),
        "artifact_ids": set(),
        "version_ids": set(),
    }

    try:
        yield conn, created
    finally:
        # Cleanup in FK-safe order.
        for version_id in list(created["version_ids"]):
            conn.execute(
                text("DELETE FROM search_index WHERE artifact_version_id = :id"),
                {"id": version_id},
            )
        for version_id in list(created["version_ids"]):
            conn.execute(text("DELETE FROM artifact_versions WHERE id = :id"), {"id": version_id})
        for artifact_id in list(created["artifact_ids"]):
            conn.execute(text("DELETE FROM artifacts WHERE id = :id"), {"id": artifact_id})
        for workspace_id in list(created["workspace_ids"]):
            conn.execute(
                text("DELETE FROM workspace_agents WHERE workspace_id = :id"),
                {"id": workspace_id},
            )
            conn.execute(text("DELETE FROM workspaces WHERE id = :id"), {"id": workspace_id})
        for agent_id in list(created["agent_ids"]):
            conn.execute(text("DELETE FROM agents WHERE id = :id"), {"id": agent_id})

        conn.commit()
        conn.close()


@pytest.fixture
def workspace_with_artifacts(worker_db):
    """Create a workspace with indexed artifacts."""
    conn, created = worker_db

    workspace_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())

    # Create agent
    conn.execute(
        text(
            """
            INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
            VALUES (:id, :moltbook_id, :name, :reputation, NOW())
            """
        ),
        {
            "id": agent_id,
            "moltbook_id": f"test-agent-{uuid.uuid4()}",
            "name": "Test Agent",
            "reputation": 0,
        },
    )

    # Create workspace
    conn.execute(
        text(
            """
            INSERT INTO workspaces (id, name, phase, created_by, created_at)
            VALUES (:id, :name, :phase, :created_by, NOW())
            """
        ),
        {"id": workspace_id, "name": "Test Workspace", "phase": "INIT", "created_by": agent_id},
    )

    # Add agent to workspace
    role_id = conn.execute(
        text("SELECT id FROM roles WHERE name = :name LIMIT 1"),
        {"name": "Maintainer"},
    ).fetchone()[0]

    conn.execute(
        text(
            """
            INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status, joined_at)
            VALUES (:workspace_id, :agent_id, :role_id, :status, NOW())
            """
        ),
        {"workspace_id": workspace_id, "agent_id": agent_id, "role_id": str(role_id), "status": "active"},
    )

    # Create artifact
    conn.execute(
        text(
            """
            INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
            VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
            """
        ),
        {
            "id": artifact_id,
            "workspace_id": workspace_id,
            "short_id": f"A{uuid.uuid4().hex[:6]}",
            "type": "pdf",
            "metadata": {"source": "test"},
            "storage_uri": f"s3://bucket/{workspace_id}/{artifact_id}",
            "created_by": agent_id,
        },
    )

    # Create version
    conn.execute(
        text(
            """
            INSERT INTO artifact_versions (id, artifact_id, version, storage_uri, content_hash, created_by, created_at)
            VALUES (:id, :artifact_id, :version, :storage_uri, :content_hash, :created_by, NOW())
            """
        ),
        {
            "id": version_id,
            "artifact_id": artifact_id,
            "version": 1,
            "storage_uri": f"s3://bucket/{workspace_id}/{artifact_id}/v1.pdf",
            "content_hash": "hash123",
            "created_by": agent_id,
        },
    )

    conn.commit()

    created["agent_ids"].add(agent_id)
    created["workspace_ids"].add(workspace_id)
    created["artifact_ids"].add(artifact_id)
    created["version_ids"].add(version_id)

    return {
        "workspace_id": workspace_id,
        "agent_id": agent_id,
        "artifact_id": artifact_id,
        "version_id": version_id
    }


# Indexing Tests

def test_index_pdf_text__artifact_version__creates_search_index_row(workspace_with_artifacts, worker_db):
    """Test indexing PDF text content."""
    ws = workspace_with_artifacts
    conn, _created = worker_db

    pdf_text = """
    This is a research paper about quantum computing.
    Quantum computers use qubits to perform calculations.
    The paper discusses entanglement and superposition.
    """

    result = asyncio.run(index_pdf_text(
        workspace_id=ws["workspace_id"],
        artifact_id=ws["artifact_id"],
        artifact_version_id=ws["version_id"],
        pdf_text=pdf_text,
        page_metadata={"pages": 3}
    ))

    assert "index_id" in result
    assert result["content_length"] == len(pdf_text)
    assert result["artifact_version_id"] == ws["version_id"]

    # Verify indexed in database
    indexed_row = conn.execute(
        text("SELECT content, artifact_type FROM search_index WHERE artifact_version_id = :version_id"),
        {"version_id": ws["version_id"]}
    ).fetchone()

    assert indexed_row is not None
    assert indexed_row[0] == pdf_text
    assert indexed_row[1] == "pdf"


def test_index_repo_file__artifact_version__creates_search_index_row(workspace_with_artifacts, worker_db):
    """Test indexing repository file content."""
    ws = workspace_with_artifacts
    conn, _created = worker_db

    file_content = """
    def calculate_fibonacci(n):
        if n <= 1:
            return n
        return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)
    """

    result = asyncio.run(index_repo_file(
        workspace_id=ws["workspace_id"],
        artifact_id=ws["artifact_id"],
        artifact_version_id=ws["version_id"],
        file_content=file_content,
        file_path="src/algorithms/fibonacci.py"
    ))

    assert "index_id" in result

    # Verify metadata stored
    indexed_row = conn.execute(
        text("SELECT metadata, artifact_type FROM search_index WHERE artifact_version_id = :version_id"),
        {"version_id": ws["version_id"]}
    ).fetchone()

    assert indexed_row[0]["file_path"] == "src/algorithms/fibonacci.py"
    assert indexed_row[1] == "repo"


def test_index__reindex__updates_existing_row(workspace_with_artifacts, worker_db):
    """Test updating an existing index entry."""
    ws = workspace_with_artifacts
    conn, _created = worker_db

    # First index
    original_text = "Original content"
    asyncio.run(index_artifact_content(
        workspace_id=ws["workspace_id"],
        artifact_id=ws["artifact_id"],
        artifact_version_id=ws["version_id"],
        artifact_type="pdf",
        content=original_text
    ))

    # Update index
    updated_text = "Updated content with new information"
    result = asyncio.run(index_artifact_content(
        workspace_id=ws["workspace_id"],
        artifact_id=ws["artifact_id"],
        artifact_version_id=ws["version_id"],
        artifact_type="pdf",
        content=updated_text
    ))

    assert "index_id" in result

    # Verify only one entry exists with updated content
    rows = conn.execute(
        text("SELECT content FROM search_index WHERE artifact_version_id = :version_id"),
        {"version_id": ws["version_id"]}
    ).fetchall()

    assert len(rows) == 1
    assert rows[0][0] == updated_text


# Search Tests

def test_search__query_matches_indexed_content__returns_hits(workspace_with_artifacts, worker_db):
    """Exit test: Search returns expected hits for ingested PDF text."""
    ws = workspace_with_artifacts
    conn, created = worker_db

    # Index multiple documents
    pdf_text_1 = "Machine learning algorithms for classification tasks"
    pdf_text_2 = "Deep neural networks and convolutional architectures"
    pdf_text_3 = "Quantum computing and entanglement phenomena"

    asyncio.run(index_pdf_text(
        workspace_id=ws["workspace_id"],
        artifact_id=ws["artifact_id"],
        artifact_version_id=ws["version_id"],
        pdf_text=pdf_text_1
    ))

    # Create another artifact for second document
    artifact_id_2 = str(uuid.uuid4())
    version_id_2 = str(uuid.uuid4())

    conn.execute(
        text(
            """
            INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
            VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            "id": artifact_id_2,
            "workspace_id": ws["workspace_id"],
            "short_id": f"A{uuid.uuid4().hex[:6]}",
            "type": "pdf",
            "metadata": {"source": "test"},
            "storage_uri": f"s3://bucket/{ws['workspace_id']}/{artifact_id_2}",
            "created_by": ws["agent_id"],
        },
    )

    conn.execute(
        text(
            """
            INSERT INTO artifact_versions (id, artifact_id, version, storage_uri, content_hash, created_by, created_at)
            VALUES (:id, :artifact_id, :version, :storage_uri, :content_hash, :created_by, NOW())
            """
        ),
        {
            "id": version_id_2,
            "artifact_id": artifact_id_2,
            "version": 1,
            "storage_uri": f"s3://bucket/{ws['workspace_id']}/{artifact_id_2}/v1.pdf",
            "content_hash": "hash456",
            "created_by": ws["agent_id"],
        },
    )

    conn.commit()

    created["artifact_ids"].add(artifact_id_2)
    created["version_ids"].add(version_id_2)

    asyncio.run(index_pdf_text(
        workspace_id=ws["workspace_id"],
        artifact_id=artifact_id_2,
        artifact_version_id=version_id_2,
        pdf_text=pdf_text_2
    ))

    # Search for "machine learning"
    search_results = conn.execute(
        text(
            """
            SELECT artifact_id, artifact_version_id, ts_rank(content_tsv, to_tsquery('english', 'machine & learning')) AS rank
            FROM search_index
            WHERE workspace_id = :workspace_id
              AND content_tsv @@ to_tsquery('english', 'machine & learning')
            ORDER BY rank DESC
            """
        ),
        {"workspace_id": ws["workspace_id"]}
    ).fetchall()

    assert len(search_results) == 1
    assert str(search_results[0][0]) == ws["artifact_id"]
    assert search_results[0][2] > 0  # Has relevance score


def test_search__multiple_hits__orders_by_relevance(workspace_with_artifacts, worker_db):
    """Test that search results are ranked by relevance."""
    ws = workspace_with_artifacts
    conn, created = worker_db

    # Document with many occurrences of "quantum"
    text_highly_relevant = """
    Quantum computing is revolutionary. Quantum algorithms leverage quantum mechanics.
    Quantum entanglement and quantum superposition are key quantum properties.
    """

    # Document with fewer occurrences
    text_less_relevant = "This paper mentions quantum computing briefly."

    # Index both documents
    asyncio.run(index_pdf_text(
        workspace_id=ws["workspace_id"],
        artifact_id=ws["artifact_id"],
        artifact_version_id=ws["version_id"],
        pdf_text=text_highly_relevant
    ))

    artifact_id_2 = str(uuid.uuid4())
    version_id_2 = str(uuid.uuid4())

    conn.execute(
        text(
            """
            INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
            VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
            """
        ),
        {
            "id": artifact_id_2,
            "workspace_id": ws["workspace_id"],
            "short_id": f"A{uuid.uuid4().hex[:6]}",
            "type": "pdf",
            "metadata": {"source": "test"},
            "storage_uri": f"s3://bucket/{ws['workspace_id']}/{artifact_id_2}",
            "created_by": ws["agent_id"],
        },
    )

    conn.execute(
        text(
            """
            INSERT INTO artifact_versions (id, artifact_id, version, storage_uri, content_hash, created_by, created_at)
            VALUES (:id, :artifact_id, :version, :storage_uri, :content_hash, :created_by, NOW())
            """
        ),
        {
            "id": version_id_2,
            "artifact_id": artifact_id_2,
            "version": 1,
            "storage_uri": f"s3://bucket/{ws['workspace_id']}/{artifact_id_2}/v1.pdf",
            "content_hash": "hash789",
            "created_by": ws["agent_id"],
        },
    )

    conn.commit()

    created["artifact_ids"].add(artifact_id_2)
    created["version_ids"].add(version_id_2)

    asyncio.run(index_pdf_text(
        workspace_id=ws["workspace_id"],
        artifact_id=artifact_id_2,
        artifact_version_id=version_id_2,
        pdf_text=text_less_relevant
    ))

    # Search for "quantum"
    search_results = conn.execute(
        text(
            """
            SELECT artifact_id, ts_rank(content_tsv, to_tsquery('english', 'quantum')) AS rank
            FROM search_index
            WHERE workspace_id = :workspace_id
              AND content_tsv @@ to_tsquery('english', 'quantum')
            ORDER BY rank DESC
            """
        ),
        {"workspace_id": ws["workspace_id"]}
    ).fetchall()

    assert len(search_results) == 2
    # First result should be the highly relevant document
    assert str(search_results[0][0]) == ws["artifact_id"]
    # First result should have higher rank than second
    assert search_results[0][1] > search_results[1][1]


def test_search__workspace_filter__restricts_results(worker_db):
    """Test that search respects workspace boundaries."""
    conn, created = worker_db

    workspace_id_1 = str(uuid.uuid4())
    workspace_id_2 = str(uuid.uuid4())

    # Create two workspaces
    for ws_id in [workspace_id_1, workspace_id_2]:
        conn.execute(
            text("INSERT INTO workspaces (id, name, phase, created_at) VALUES (:id, :name, :phase, NOW())"),
            {"id": ws_id, "name": f"Test {ws_id[:8]}", "phase": "INIT"}
        )
        created["workspace_ids"].add(ws_id)

    # Create artifacts in each workspace
    for i, ws_id in enumerate([workspace_id_1, workspace_id_2]):
        artifact_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())

        conn.execute(
            text(
                """
                INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_at)
                VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, NOW())
                """
            ),
            {
                "id": artifact_id,
                "workspace_id": ws_id,
                "short_id": f"A{uuid.uuid4().hex[:6]}",
                "type": "pdf",
                "metadata": {"source": "test"},
                "storage_uri": f"s3://bucket/{ws_id}/{artifact_id}",
            },
        )
        created["artifact_ids"].add(artifact_id)

        conn.execute(
            text(
                """
                INSERT INTO artifact_versions (id, artifact_id, version, storage_uri, content_hash, created_at)
                VALUES (:id, :artifact_id, :version, :storage_uri, :content_hash, NOW())
                """
            ),
            {
                "id": version_id,
                "artifact_id": artifact_id,
                "version": 1,
                "storage_uri": f"s3://bucket/{ws_id}/{artifact_id}/v1.pdf",
                "content_hash": "hash",
            },
        )
        created["version_ids"].add(version_id)

        # Indexing activities run in a separate DB session, so the rows above
        # must be committed before invoking them.
        conn.commit()

        # Index content
        asyncio.run(index_pdf_text(
            workspace_id=ws_id,
            artifact_id=artifact_id,
            artifact_version_id=version_id,
            pdf_text=f"Document in workspace {i} about neural networks"
        ))

    # Search in workspace 1 only
    results_ws1 = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM search_index
            WHERE workspace_id = :workspace_id
              AND content_tsv @@ to_tsquery('english', 'neural')
            """
        ),
        {"workspace_id": workspace_id_1}
    ).fetchone()

    # Should only find results in workspace 1
    assert results_ws1[0] == 1

    # Verify workspace 2 has its own result
    results_ws2 = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM search_index
            WHERE workspace_id = :workspace_id
              AND content_tsv @@ to_tsquery('english', 'neural')
            """
        ),
        {"workspace_id": workspace_id_2}
    ).fetchone()

    assert results_ws2[0] == 1


def test_search__hit__includes_snippet(workspace_with_artifacts, worker_db):
    """Test that search generates relevant snippets."""
    ws = workspace_with_artifacts
    conn, _created = worker_db

    long_text = """
    Machine learning is a field of artificial intelligence.
    Deep learning is a subset of machine learning that uses neural networks.
    Convolutional neural networks are particularly effective for image recognition.
    Recurrent neural networks are useful for sequence data.
    Transformers have revolutionized natural language processing.
    """

    asyncio.run(index_pdf_text(
        workspace_id=ws["workspace_id"],
        artifact_id=ws["artifact_id"],
        artifact_version_id=ws["version_id"],
        pdf_text=long_text
    ))

    # Search and get snippet
    result = conn.execute(
        text(
            """
            SELECT ts_headline('english', content, to_tsquery('english', 'neural & networks'),
                              'MaxWords=30, MinWords=15, ShortWord=3, MaxFragments=1') AS snippet
            FROM search_index
            WHERE workspace_id = :workspace_id
              AND content_tsv @@ to_tsquery('english', 'neural & networks')
            """
        ),
        {"workspace_id": ws["workspace_id"]}
    ).fetchone()

    snippet = result[0]

    # Snippet should contain the search terms
    assert "neural" in snippet.lower()
    assert "networks" in snippet.lower()

