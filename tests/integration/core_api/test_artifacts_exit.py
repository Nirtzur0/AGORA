"""
Integration tests for artifacts (Component 7 Exit Tests).

Critical exit tests per checklist:
1. Upload bytes as a version and retrieve exact bytes by artifact_version_id
2. Validate immutability (cannot "update version 1")
"""

import io
import hashlib
from uuid import uuid4

import pytest

from database import get_raw_db
import jwt_utils


@pytest.fixture
def workspace_ctx(migrated_db):
    """Create a workspace + member agent for artifact tests."""
    with get_raw_db() as conn:
        cursor = conn.cursor()
        
        # Create workspace
        workspace_id = uuid4()
        creator_id = uuid4()
        
        # Create agent
        cursor.execute(
            """
            INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (str(creator_id), f"test-moltbook-{creator_id}", "Test Agent", 100.0)
        )
        
        # Get Maintainer role
        cursor.execute("SELECT id FROM roles WHERE name = 'Maintainer'")
        role_id = cursor.fetchone()[0]
        
        # Create workspace
        cursor.execute(
            """
            INSERT INTO workspaces (id, name, description, phase, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            """,
            (str(workspace_id), "Test Workspace", "For artifact tests", "INIT", str(creator_id))
        )
        
        # Add agent to workspace
        cursor.execute(
            """
            INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status, joined_at)
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (str(workspace_id), str(creator_id), role_id, "active")
        )
        
        conn.commit()
        
        yield {
            "workspace_id": str(workspace_id),
            "agent_id": str(creator_id),
            "moltbook_id": f"test-moltbook-{creator_id}",
        }
        
        # Cleanup
        cursor.execute("DELETE FROM workspace_agents WHERE workspace_id = %s", (str(workspace_id),))
        cursor.execute("DELETE FROM events WHERE workspace_id = %s", (str(workspace_id),))
        cursor.execute("DELETE FROM artifact_versions WHERE artifact_id IN (SELECT id FROM artifacts WHERE workspace_id = %s)", (str(workspace_id),))
        cursor.execute("DELETE FROM artifacts WHERE workspace_id = %s", (str(workspace_id),))
        cursor.execute("DELETE FROM workspaces WHERE id = %s", (str(workspace_id),))
        cursor.execute("DELETE FROM agents WHERE id = %s", (str(creator_id),))
        conn.commit()


@pytest.fixture
def auth_headers(workspace_ctx):
    """Authorization header for the workspace agent."""
    token = jwt_utils.create_agent_token(
        agent_id=workspace_ctx["agent_id"],
        moltbook_id=workspace_ctx["moltbook_id"],
    )
    return {"Authorization": f"Bearer {token}"}


class TestArtifactExitCriteria:
    """Component 7 exit tests per checklist."""
    
    def test_artifact_version_content__uploaded_bytes__retrievable_by_version_id(self, workspace_ctx, auth_headers, test_client):
        """
        EXIT TEST 1: Upload bytes as a version and retrieve exact bytes by artifact_version_id.
        
        This test validates that:
        - Content can be uploaded as a new version
        - Content can be retrieved exactly using version ID
        - Content hash is correct
        - This is the mechanism required for citations
        """
        # Create artifact
        response = test_client.post(
            f"/workspaces/{workspace_ctx['workspace_id']}/artifacts",
            json={"type": "pdf"},
            headers=auth_headers,
        )
        assert response.status_code == 201, f"Failed to create artifact: {response.text}"
        artifact_id = response.json()["id"]
        
        # Upload version with specific test content
        test_content = b"This is the exact content that must be retrievable for citation resolution"
        expected_hash = hashlib.sha256(test_content).hexdigest()
        
        response = test_client.post(
            f"/artifacts/{artifact_id}/versions",
            files={"file": ("test.pdf", io.BytesIO(test_content), "application/pdf")},
            headers=auth_headers,
        )
        assert response.status_code == 201, f"Failed to create version: {response.text}"
        version_data = response.json()
        version_id = version_data["id"]
        assert version_data["content_hash"] == expected_hash
        
        # Retrieve exact version content
        response = test_client.get(
            f"/artifact-versions/{version_id}/content",
            headers=auth_headers,
        )
        assert response.status_code == 200, f"Failed to retrieve content: {response.text}"
        retrieved_content = response.content
        
        # Verify exact bytes match
        assert retrieved_content == test_content, "Retrieved content does not match uploaded content"
        assert response.headers["X-Content-Hash"] == expected_hash
    
    def test_artifact_versions__multiple_uploads__version_1_immutable(self, workspace_ctx, auth_headers, test_client):
        """
        EXIT TEST 2: Validate immutability (cannot "update version 1").
        
        This test validates that:
        - Each upload creates a new version (not an overwrite)
        - Version 1 content remains unchanged after subsequent uploads
        - Storage is append-only (versions are immutable)
        """
        # Create artifact
        response = test_client.post(
            f"/workspaces/{workspace_ctx['workspace_id']}/artifacts",
            json={"type": "dataset"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        artifact_id = response.json()["id"]
        
        # Upload version 1
        content_v1 = b"Version 1 original data that must never change"
        hash_v1 = hashlib.sha256(content_v1).hexdigest()
        
        response = test_client.post(
            f"/artifacts/{artifact_id}/versions",
            files={"file": ("data.csv", io.BytesIO(content_v1), "text/csv")},
            headers=auth_headers,
        )
        assert response.status_code == 201
        version_1_id = response.json()["id"]
        assert response.json()["version"] == 1
        assert response.json()["content_hash"] == hash_v1
        
        # Upload version 2 (different content)
        content_v2 = b"Version 2 different data"
        hash_v2 = hashlib.sha256(content_v2).hexdigest()
        
        response = test_client.post(
            f"/artifacts/{artifact_id}/versions",
            files={"file": ("data.csv", io.BytesIO(content_v2), "text/csv")},
            headers=auth_headers,
        )
        assert response.status_code == 201
        version_2_id = response.json()["id"]
        assert response.json()["version"] == 2, "Second upload should create version 2, not overwrite version 1"
        assert response.json()["content_hash"] == hash_v2
        assert version_2_id != version_1_id
        
        # Verify version 1 is unchanged (retrieve original content)
        response = test_client.get(
            f"/artifact-versions/{version_1_id}/content",
            headers=auth_headers,
        )
        assert response.status_code == 200
        retrieved_v1 = response.content
        assert retrieved_v1 == content_v1, "Version 1 content was modified (immutability violated)"
        assert response.headers["X-Content-Hash"] == hash_v1
        
        # Verify version 2 has different content
        response = test_client.get(
            f"/artifact-versions/{version_2_id}/content",
            headers=auth_headers,
        )
        assert response.status_code == 200
        retrieved_v2 = response.content
        assert retrieved_v2 == content_v2
        assert response.headers["X-Content-Hash"] == hash_v2
        
        # Verify both versions exist in database
        with get_raw_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT version, content_hash FROM artifact_versions
                WHERE artifact_id = %s
                ORDER BY version
                """,
                (artifact_id,)
            )
            rows = cursor.fetchall()
            assert len(rows) == 2, "Should have exactly 2 versions"
        assert rows[0][0] == 1 and rows[0][1] == hash_v1
        assert rows[1][0] == 2 and rows[1][1] == hash_v2
    
    def test_artifacts__create_multiple__short_ids_increment(self, workspace_ctx, auth_headers, test_client):
        """Test that short_ids are allocated correctly (A1, A2, A3...)."""
        for expected_num in range(1, 4):
            response = test_client.post(
                f"/workspaces/{workspace_ctx['workspace_id']}/artifacts",
                json={"type": "log"},
                headers=auth_headers,
            )
            assert response.status_code == 201
            assert response.json()["short_id"] == f"A{expected_num}"
    
    def test_artifacts__create_and_version__emits_expected_events(self, workspace_ctx, auth_headers, test_client):
        """Test that artifact.created and artifact.version_created events are emitted."""
        # Create artifact
        response = test_client.post(
            f"/workspaces/{workspace_ctx['workspace_id']}/artifacts",
            json={"type": "code"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        artifact_id = response.json()["id"]
        
        # Check artifact.created event
        with get_raw_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT event_type, actor_type, payload
                FROM events
                WHERE workspace_id = %s AND event_type = 'artifact.created'
                AND payload->>'artifact_id' = %s
                """,
                (workspace_ctx["workspace_id"], artifact_id)
            )
            row = cursor.fetchone()
            assert row is not None, "artifact.created event not found"
            assert row[1] == "agent"
        
        # Upload version
        response = test_client.post(
            f"/artifacts/{artifact_id}/versions",
            files={"file": ("code.py", io.BytesIO(b"print('test')"), "text/plain")},
            headers=auth_headers,
        )
        assert response.status_code == 201
        version_id = response.json()["id"]
        
        # Check artifact.version_created event
        with get_raw_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT event_type, actor_type, payload
                FROM events
                WHERE workspace_id = %s AND event_type = 'artifact.version_created'
                AND payload->>'artifact_version_id' = %s
                """,
                (workspace_ctx["workspace_id"], version_id)
            )
            row = cursor.fetchone()
            assert row is not None, "artifact.version_created event not found"
            assert row[1] == "agent"
