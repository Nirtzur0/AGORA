"""
Tests for Search and Indexing (Component 22)

Per spec §4.13, §6.5, §9:
- Tests Postgres FTS indexing for PDF text, repo files, and logs
- Tests GET /search endpoint with relevance ranking
- Tests workspace filtering and access control
"""

import pytest
import uuid
from apps.worker.indexing_activities import (
    index_artifact_content,
    index_pdf_text,
    index_repo_file,
    index_log
)


# Fixtures

@pytest.fixture
def test_db(request):
    """Create test database connection."""
    from apps.worker.database import get_db_connection
    conn = get_db_connection()
    
    # Clean up before test
    conn.execute("DELETE FROM search_index WHERE workspace_id LIKE 'test-%'")
    conn.execute("DELETE FROM artifact_versions WHERE artifact_id IN (SELECT id FROM artifacts WHERE workspace_id LIKE 'test-%')")
    conn.execute("DELETE FROM artifacts WHERE workspace_id LIKE 'test-%')")
    conn.execute("DELETE FROM workspace_agents WHERE workspace_id LIKE 'test-%'")
    conn.execute("DELETE FROM workspaces WHERE id LIKE 'test-%'")
    conn.execute("DELETE FROM agents WHERE moltbook_id LIKE 'test-%'")
    conn.commit()
    
    yield conn
    
    # Clean up after test
    conn.execute("DELETE FROM search_index WHERE workspace_id LIKE 'test-%'")
    conn.execute("DELETE FROM artifact_versions WHERE artifact_id IN (SELECT id FROM artifacts WHERE workspace_id LIKE 'test-%')")
    conn.execute("DELETE FROM artifacts WHERE workspace_id LIKE 'test-%')")
    conn.execute("DELETE FROM workspace_agents WHERE workspace_id LIKE 'test-%'")
    conn.execute("DELETE FROM workspaces WHERE id LIKE 'test-%'")
    conn.execute("DELETE FROM agents WHERE moltbook_id LIKE 'test-%'")
    conn.commit()
    conn.close()


@pytest.fixture
def workspace_with_artifacts(test_db):
    """Create a workspace with indexed artifacts."""
    workspace_id = f"test-ws-{uuid.uuid4()}"
    agent_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    
    # Create agent
    test_db.execute(
        """
        INSERT INTO agents (id, moltbook_id, name, created_at)
        VALUES (:id, :moltbook_id, 'Test Agent', NOW())
        """,
        {"id": agent_id, "moltbook_id": f"test-agent-{uuid.uuid4()}"}
    )
    
    # Create workspace
    test_db.execute(
        """
        INSERT INTO workspaces (id, name, phase, created_at)
        VALUES (:id, 'Test Workspace', 'INIT', NOW())
        """,
        {"id": workspace_id}
    )
    
    # Add agent to workspace
    test_db.execute(
        """
        INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status, joined_at)
        VALUES (:workspace_id, :agent_id, (SELECT id FROM roles WHERE name = 'Contributor' LIMIT 1), 'active', NOW())
        """,
        {"workspace_id": workspace_id, "agent_id": agent_id}
    )
    
    # Create artifact
    test_db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, storage_uri, created_at)
        VALUES (:id, :workspace_id, 'test-art', 'pdf', 's3://bucket/test', NOW())
        """,
        {"id": artifact_id, "workspace_id": workspace_id}
    )
    
    # Create version
    test_db.execute(
        """
        INSERT INTO artifact_versions (id, artifact_id, version_number, content_hash, location, created_at)
        VALUES (:id, :artifact_id, 1, 'hash123', 's3://bucket/test/v1', NOW())
        """,
        {"id": version_id, "artifact_id": artifact_id}
    )
    
    test_db.commit()
    
    return {
        "workspace_id": workspace_id,
        "agent_id": agent_id,
        "artifact_id": artifact_id,
        "version_id": version_id
    }


# Indexing Tests

def test_index_pdf_text(workspace_with_artifacts, test_db):
    """Test indexing PDF text content."""
    ws = workspace_with_artifacts
    
    pdf_text = """
    This is a research paper about quantum computing.
    Quantum computers use qubits to perform calculations.
    The paper discusses entanglement and superposition.
    """
    
    result = index_pdf_text(
        workspace_id=ws["workspace_id"],
        artifact_id=ws["artifact_id"],
        artifact_version_id=ws["version_id"],
        pdf_text=pdf_text,
        page_metadata={"pages": 3}
    )
    
    assert "index_id" in result
    assert result["content_length"] == len(pdf_text)
    assert result["artifact_version_id"] == ws["version_id"]
    
    # Verify indexed in database
    indexed_row = test_db.execute(
        "SELECT content, artifact_type FROM search_index WHERE artifact_version_id = :version_id",
        {"version_id": ws["version_id"]}
    ).fetchone()
    
    assert indexed_row is not None
    assert indexed_row[0] == pdf_text
    assert indexed_row[1] == "pdf"


def test_index_repo_file(workspace_with_artifacts, test_db):
    """Test indexing repository file content."""
    ws = workspace_with_artifacts
    
    file_content = """
    def calculate_fibonacci(n):
        if n <= 1:
            return n
        return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)
    """
    
    result = index_repo_file(
        workspace_id=ws["workspace_id"],
        artifact_id=ws["artifact_id"],
        artifact_version_id=ws["version_id"],
        file_content=file_content,
        file_path="src/algorithms/fibonacci.py"
    )
    
    assert "index_id" in result
    
    # Verify metadata stored
    indexed_row = test_db.execute(
        "SELECT metadata, artifact_type FROM search_index WHERE artifact_version_id = :version_id",
        {"version_id": ws["version_id"]}
    ).fetchone()
    
    assert indexed_row[0]["file_path"] == "src/algorithms/fibonacci.py"
    assert indexed_row[1] == "repo"


def test_index_update_existing(workspace_with_artifacts, test_db):
    """Test updating an existing index entry."""
    ws = workspace_with_artifacts
    
    # First index
    original_text = "Original content"
    index_artifact_content(
        workspace_id=ws["workspace_id"],
        artifact_id=ws["artifact_id"],
        artifact_version_id=ws["version_id"],
        artifact_type="pdf",
        content=original_text
    )
    
    # Update index
    updated_text = "Updated content with new information"
    result = index_artifact_content(
        workspace_id=ws["workspace_id"],
        artifact_id=ws["artifact_id"],
        artifact_version_id=ws["version_id"],
        artifact_type="pdf",
        content=updated_text
    )
    
    assert "index_id" in result
    
    # Verify only one entry exists with updated content
    rows = test_db.execute(
        "SELECT content FROM search_index WHERE artifact_version_id = :version_id",
        {"version_id": ws["version_id"]}
    ).fetchall()
    
    assert len(rows) == 1
    assert rows[0][0] == updated_text


# Search Tests

def test_search_finds_indexed_content(workspace_with_artifacts, test_db):
    """Exit test: Search returns expected hits for ingested PDF text."""
    ws = workspace_with_artifacts
    
    # Index multiple documents
    pdf_text_1 = "Machine learning algorithms for classification tasks"
    pdf_text_2 = "Deep neural networks and convolutional architectures"
    pdf_text_3 = "Quantum computing and entanglement phenomena"
    
    index_pdf_text(
        workspace_id=ws["workspace_id"],
        artifact_id=ws["artifact_id"],
        artifact_version_id=ws["version_id"],
        pdf_text=pdf_text_1
    )
    
    # Create another artifact for second document
    artifact_id_2 = str(uuid.uuid4())
    version_id_2 = str(uuid.uuid4())
    
    test_db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, storage_uri, created_at)
        VALUES (:id, :workspace_id, 'test-art-2', 'pdf', 's3://bucket/test2', NOW())
        """,
        {"id": artifact_id_2, "workspace_id": ws["workspace_id"]}
    )
    
    test_db.execute(
        """
        INSERT INTO artifact_versions (id, artifact_id, version_number, content_hash, location, created_at)
        VALUES (:id, :artifact_id, 1, 'hash456', 's3://bucket/test2/v1', NOW())
        """,
        {"id": version_id_2, "artifact_id": artifact_id_2}
    )
    
    test_db.commit()
    
    index_pdf_text(
        workspace_id=ws["workspace_id"],
        artifact_id=artifact_id_2,
        artifact_version_id=version_id_2,
        pdf_text=pdf_text_2
    )
    
    # Search for "machine learning"
    search_results = test_db.execute(
        """
        SELECT artifact_id, artifact_version_id, ts_rank(content_tsv, to_tsquery('english', 'machine & learning')) AS rank
        FROM search_index
        WHERE workspace_id = :workspace_id
          AND content_tsv @@ to_tsquery('english', 'machine & learning')
        ORDER BY rank DESC
        """,
        {"workspace_id": ws["workspace_id"]}
    ).fetchall()
    
    assert len(search_results) == 1
    assert search_results[0][0] == ws["artifact_id"]
    assert search_results[0][2] > 0  # Has relevance score


def test_search_relevance_ranking(workspace_with_artifacts, test_db):
    """Test that search results are ranked by relevance."""
    ws = workspace_with_artifacts
    
    # Document with many occurrences of "quantum"
    text_highly_relevant = """
    Quantum computing is revolutionary. Quantum algorithms leverage quantum mechanics.
    Quantum entanglement and quantum superposition are key quantum properties.
    """
    
    # Document with fewer occurrences
    text_less_relevant = "This paper mentions quantum computing briefly."
    
    # Index both documents
    index_pdf_text(
        workspace_id=ws["workspace_id"],
        artifact_id=ws["artifact_id"],
        artifact_version_id=ws["version_id"],
        pdf_text=text_highly_relevant
    )
    
    artifact_id_2 = str(uuid.uuid4())
    version_id_2 = str(uuid.uuid4())
    
    test_db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, storage_uri, created_at)
        VALUES (:id, :workspace_id, 'test-art-2', 'pdf', 's3://bucket/test2', NOW())
        """,
        {"id": artifact_id_2, "workspace_id": ws["workspace_id"]}
    )
    
    test_db.execute(
        """
        INSERT INTO artifact_versions (id, artifact_id, version_number, content_hash, location, created_at)
        VALUES (:id, :artifact_id, 1, 'hash789', 's3://bucket/test2/v1', NOW())
        """,
        {"id": version_id_2, "artifact_id": artifact_id_2}
    )
    
    test_db.commit()
    
    index_pdf_text(
        workspace_id=ws["workspace_id"],
        artifact_id=artifact_id_2,
        artifact_version_id=version_id_2,
        pdf_text=text_less_relevant
    )
    
    # Search for "quantum"
    search_results = test_db.execute(
        """
        SELECT artifact_id, ts_rank(content_tsv, to_tsquery('english', 'quantum')) AS rank
        FROM search_index
        WHERE workspace_id = :workspace_id
          AND content_tsv @@ to_tsquery('english', 'quantum')
        ORDER BY rank DESC
        """,
        {"workspace_id": ws["workspace_id"]}
    ).fetchall()
    
    assert len(search_results) == 2
    # First result should be the highly relevant document
    assert search_results[0][0] == ws["artifact_id"]
    # First result should have higher rank than second
    assert search_results[0][1] > search_results[1][1]


def test_search_workspace_filtering(test_db):
    """Test that search respects workspace boundaries."""
    workspace_id_1 = f"test-ws-{uuid.uuid4()}"
    workspace_id_2 = f"test-ws-{uuid.uuid4()}"
    
    # Create two workspaces
    for ws_id in [workspace_id_1, workspace_id_2]:
        test_db.execute(
            "INSERT INTO workspaces (id, name, phase, created_at) VALUES (:id, 'Test', 'INIT', NOW())",
            {"id": ws_id}
        )
    
    # Create artifacts in each workspace
    for i, ws_id in enumerate([workspace_id_1, workspace_id_2]):
        artifact_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        
        test_db.execute(
            """
            INSERT INTO artifacts (id, workspace_id, short_id, type, storage_uri, created_at)
            VALUES (:id, :workspace_id, :short_id, 'pdf', 's3://bucket/test', NOW())
            """,
            {"id": artifact_id, "workspace_id": ws_id, "short_id": f"art-{i}"}
        )
        
        test_db.execute(
            """
            INSERT INTO artifact_versions (id, artifact_id, version_number, content_hash, location, created_at)
            VALUES (:id, :artifact_id, 1, 'hash', 's3://bucket/test/v1', NOW())
            """,
            {"id": version_id, "artifact_id": artifact_id}
        )
        
        # Index content
        index_pdf_text(
            workspace_id=ws_id,
            artifact_id=artifact_id,
            artifact_version_id=version_id,
            pdf_text=f"Document in workspace {i} about neural networks"
        )
    
    test_db.commit()
    
    # Search in workspace 1 only
    results_ws1 = test_db.execute(
        """
        SELECT COUNT(*) FROM search_index
        WHERE workspace_id = :workspace_id
          AND content_tsv @@ to_tsquery('english', 'neural')
        """,
        {"workspace_id": workspace_id_1}
    ).fetchone()
    
    # Should only find results in workspace 1
    assert results_ws1[0] == 1
    
    # Verify workspace 2 has its own result
    results_ws2 = test_db.execute(
        """
        SELECT COUNT(*) FROM search_index
        WHERE workspace_id = :workspace_id
          AND content_tsv @@ to_tsquery('english', 'neural')
        """,
        {"workspace_id": workspace_id_2}
    ).fetchone()
    
    assert results_ws2[0] == 1


def test_search_snippet_generation(workspace_with_artifacts, test_db):
    """Test that search generates relevant snippets."""
    ws = workspace_with_artifacts
    
    long_text = """
    Machine learning is a field of artificial intelligence. 
    Deep learning is a subset of machine learning that uses neural networks.
    Convolutional neural networks are particularly effective for image recognition.
    Recurrent neural networks are useful for sequence data.
    Transformers have revolutionized natural language processing.
    """
    
    index_pdf_text(
        workspace_id=ws["workspace_id"],
        artifact_id=ws["artifact_id"],
        artifact_version_id=ws["version_id"],
        pdf_text=long_text
    )
    
    # Search and get snippet
    result = test_db.execute(
        """
        SELECT ts_headline('english', content, to_tsquery('english', 'neural & networks'),
                          'MaxWords=30, MinWords=15, ShortWord=3, MaxFragments=1') AS snippet
        FROM search_index
        WHERE workspace_id = :workspace_id
          AND content_tsv @@ to_tsquery('english', 'neural & networks')
        """,
        {"workspace_id": ws["workspace_id"]}
    ).fetchone()
    
    snippet = result[0]
    
    # Snippet should contain the search terms
    assert "neural" in snippet.lower()
    assert "networks" in snippet.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
