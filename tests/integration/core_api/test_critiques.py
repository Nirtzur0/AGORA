"""
Integration tests for Component 19: Critiques + Critique Sufficiency

Tests per Docs/06 exit criteria:
- High-trust critic cannot defer -> fails sufficiency
- Low-trust deferral with rationale passes
- Target author cannot resolve critique

Tests critique system per spec §4.7, §5.5:
- Critique creation and authorization
- Resolution authority rules
- Critique sufficiency rule checks
- High-trust reputation enforcement
"""
import pytest
import uuid
import json

from database import get_raw_db

TEST_AGENT_ID = "00000000-0000-0000-0000-000000000001"


def _insert_agent(test_db, agent_id, moltbook_id, name="Test Agent", reputation=None):
    test_db.execute(
        """
        INSERT INTO agents (id, moltbook_id, name, reputation)
        VALUES (:id, :moltbook_id, :name, :reputation)
        ON CONFLICT (id) DO NOTHING
        """,
        {
            "id": agent_id,
            "moltbook_id": moltbook_id,
            "name": name,
            "reputation": reputation
        }
    )


def _make_agent_token(agent_id, moltbook_id, reputation=0):
    from jwt_utils import create_agent_token
    return create_agent_token(
        agent_id=agent_id,
        moltbook_id=moltbook_id,
        reputation=reputation
    )


def test_create_critique(test_client, test_db):
    """Test critique creation on a claim."""
    workspace_id = str(uuid.uuid4())
    agent_id = TEST_AGENT_ID
    claim_id = str(uuid.uuid4())
    
    with get_raw_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO NOTHING
            """,
            (agent_id, "test_moltbook_id", "Test Agent", 0.0)
        )
        cursor.execute(
            "INSERT INTO workspaces (id, name, phase) VALUES (%s, %s, %s)",
            (workspace_id, "Test Workspace", "active")
        )
        cursor.execute(
            """
            INSERT INTO claims (id, workspace_id, text, kind, confidence, status, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (claim_id, workspace_id, "Test claim", "fact", 0.9, "active", agent_id)
        )
        conn.commit()
    
    # Generate token manually to avoid deadlock with fixture
    token = _make_agent_token(agent_id, "test_moltbook_id")

    # Create critique
    response = test_client.post(
        f"/workspaces/{workspace_id}/critiques",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "severity": "major",
            "message": "This claim needs more evidence"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["workspace_id"] == workspace_id
    assert data["target_type"] == "claim"
    assert data["target_id"] == claim_id
    assert data["critic_agent_id"] == agent_id
    assert data["status"] == "open"
    assert data["severity"] == "major"
    assert data["message"] == "This claim needs more evidence"
    
    # Verify critique in database
    critique = test_db.execute(
        "SELECT id, status FROM critiques WHERE id = :id",
        {"id": data["id"]}
    ).fetchone()
    
    assert critique is not None
    assert critique[1] == "open"
    
    # Verify event created
    event = test_db.execute(
        "SELECT event_type FROM events WHERE workspace_id = :id ORDER BY created_at DESC LIMIT 1",
        {"id": workspace_id}
    ).fetchone()
    
    assert event is not None
    assert event[0] == "critique.created"


def test_target_author_cannot_resolve_own_critique(test_client, test_db, mock_agent_token):
    """Test that target author cannot resolve their own critique."""
    workspace_id = str(uuid.uuid4())
    author_id = str(uuid.uuid4())
    critic_id = str(uuid.uuid4())
    claim_id = str(uuid.uuid4())
    critique_id = str(uuid.uuid4())

    author_moltbook = f"author_moltbook_{author_id}"
    critic_moltbook = f"critic_moltbook_{critic_id}"
    
    with get_raw_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO NOTHING
            """,
            (author_id, author_moltbook, "Author", 0.0)
        )
        cursor.execute(
            """
            INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO NOTHING
            """,
            (critic_id, critic_moltbook, "Critic", 0.0)
        )
        cursor.execute(
            "INSERT INTO workspaces (id, name, phase) VALUES (%s, %s, %s)",
            (workspace_id, "Test Workspace", "active")
        )
        cursor.execute(
            """
            INSERT INTO claims (id, workspace_id, text, kind, confidence, status, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (claim_id, workspace_id, "Author's claim", "fact", 0.9, "active", author_id)
        )
        cursor.execute(
            """
            INSERT INTO critiques (
                id, workspace_id, target_type, target_id, critic_agent_id,
                status, severity, message, created_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, NOW()
            )
            """,
            (critique_id, workspace_id, "claim", claim_id, critic_id, "open", "major", "Needs revision")
        )
        conn.commit()
    
    # Author tries to resolve critique (should fail)
    # Mock token for author
    author_token = _make_agent_token(author_id, author_moltbook)
    
    response = test_client.patch(
        f"/critiques/{critique_id}",
        headers={"Authorization": f"Bearer {author_token}"},
        json={
            "status": "resolved",
            "resolution": {
                "status": "accepted_fix",
                "rationale": "Fixed it"
            }
        }
    )
    
    assert response.status_code == 403
    assert "cannot resolve their own critique" in response.json()["detail"]


def test_only_critic_can_update_critique(test_client, test_db, mock_agent_token):
    """Test that only the critic can update their critique."""
    workspace_id = str(uuid.uuid4())
    critic_id = str(uuid.uuid4())
    other_id = str(uuid.uuid4())
    claim_id = str(uuid.uuid4())
    critique_id = str(uuid.uuid4())
    
    critic_moltbook = f"critic_moltbook_{critic_id}"
    other_moltbook = f"other_moltbook_{other_id}"
    with get_raw_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO NOTHING
            """,
            (critic_id, critic_moltbook, "Critic", 0.0)
        )
        cursor.execute(
            """
            INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO NOTHING
            """,
            (other_id, other_moltbook, "Other", 0.0)
        )
        cursor.execute(
            "INSERT INTO workspaces (id, name, phase) VALUES (%s, %s, %s)",
            (workspace_id, "Test Workspace", "active")
        )
        cursor.execute(
            """
            INSERT INTO claims (id, workspace_id, text, kind, confidence, status, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (claim_id, workspace_id, "Test claim", "fact", 0.9, "active", None)
        )
        cursor.execute(
            """
            INSERT INTO critiques (
                id, workspace_id, target_type, target_id, critic_agent_id,
                status, severity, message, created_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, NOW()
            )
            """,
            (critique_id, workspace_id, "claim", claim_id, critic_id, "open", "major", "Needs work")
        )
        conn.commit()
    
    # Other agent tries to update (should fail)
    other_token = _make_agent_token(other_id, other_moltbook)
    
    response = test_client.patch(
        f"/critiques/{critique_id}",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"status": "resolved"}
    )
    
    assert response.status_code == 403
    assert "Only the critic or a Maintainer" in response.json()["detail"]
    
    # Critic updates successfully
    critic_token = _make_agent_token(critic_id, critic_moltbook)
    
    response = test_client.patch(
        f"/critiques/{critique_id}",
        headers={"Authorization": f"Bearer {critic_token}"},
        json={
            "status": "resolved",
            "resolution": {
                "status": "accepted_fix",
                "rationale": "Issue addressed"
            }
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "resolved"


def test_maintainer_can_override_critique(test_client, test_db):
    """Test that Maintainer can override critique (if not target author)."""
    workspace_id = str(uuid.uuid4())
    critic_id = str(uuid.uuid4())
    maintainer_id = str(uuid.uuid4())
    claim_id = str(uuid.uuid4())
    critique_id = str(uuid.uuid4())
    
    maintainer_moltbook = f"maintainer_moltbook_{maintainer_id}"
    critic_moltbook = f"critic_moltbook_{critic_id}"
    with get_raw_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO NOTHING
            """,
            (maintainer_id, maintainer_moltbook, "Maintainer", 0.0)
        )
        cursor.execute(
            """
            INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO NOTHING
            """,
            (critic_id, critic_moltbook, "Critic", 0.0)
        )
        cursor.execute(
            "SELECT id FROM roles WHERE name = 'Maintainer'"
        )
        role_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO workspaces (id, name, phase) VALUES (%s, %s, %s)",
            (workspace_id, "Test Workspace", "active")
        )
        cursor.execute(
            """
            INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status, joined_at)
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (workspace_id, maintainer_id, role_id, "active")
        )
        cursor.execute(
            """
            INSERT INTO claims (id, workspace_id, text, kind, confidence, status, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (claim_id, workspace_id, "Test claim", "fact", 0.9, "active", None)
        )
        cursor.execute(
            """
            INSERT INTO critiques (
                id, workspace_id, target_type, target_id, critic_agent_id,
                status, severity, message, created_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, NOW()
            )
            """,
            (critique_id, workspace_id, "claim", claim_id, critic_id, "open", "major", "Needs work")
        )
        conn.commit()
    
    # Maintainer overrides
    maintainer_token = _make_agent_token(maintainer_id, maintainer_moltbook)
    
    response = test_client.patch(
        f"/critiques/{critique_id}",
        headers={"Authorization": f"Bearer {maintainer_token}"},
        json={"status": "resolved"}
    )
    
    assert response.status_code == 200
    
    # Verify override event created
    event = test_db.execute(
        """
        SELECT event_type, payload
        FROM events
        WHERE workspace_id = :workspace_id
          AND event_type = 'critique.maintainer_override'
        """,
        {"workspace_id": workspace_id}
    ).fetchone()
    
    assert event is not None
    payload = event[1]
    if isinstance(payload, str):
        payload = json.loads(payload)
    assert payload["critique_id"] == critique_id


def test_list_critiques_with_filters(test_client, test_db):
    """Test listing critiques with filters."""
    workspace_id = str(uuid.uuid4())
    agent_id = TEST_AGENT_ID
    claim_id1 = str(uuid.uuid4())
    claim_id2 = str(uuid.uuid4())
    
    with get_raw_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO NOTHING
            """,
            (agent_id, "test_moltbook_id", "Test Agent", 0.0)
        )
        cursor.execute(
            "INSERT INTO workspaces (id, name, phase) VALUES (%s, %s, %s)",
            (workspace_id, "Test Workspace", "active")
        )
        for cid in [claim_id1, claim_id2]:
            cursor.execute(
                """
                INSERT INTO claims (id, workspace_id, text, kind, confidence, status, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (cid, workspace_id, f"Claim {cid}", "fact", 0.9, "active", agent_id)
            )
        critique1 = str(uuid.uuid4())
        critique2 = str(uuid.uuid4())
        critique3 = str(uuid.uuid4())
        critiques_data = [
            (critique1, claim_id1, "open", "major"),
            (critique2, claim_id1, "resolved", "minor"),
            (critique3, claim_id2, "open", "blocking"),
        ]
        for crit_id, target_id, status, severity in critiques_data:
            cursor.execute(
                """
                INSERT INTO critiques (
                    id, workspace_id, target_type, target_id, critic_agent_id,
                    status, severity, message, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, NOW()
                )
                """,
                (crit_id, workspace_id, "claim", target_id, agent_id, status, severity, "Test critique")
            )
        conn.commit()
    
    token = _make_agent_token(agent_id, "test_moltbook_id")

    # List all critiques
    response = test_client.get(
        f"/workspaces/{workspace_id}/critiques",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    
    # Filter by target_id
    response = test_client.get(
        f"/workspaces/{workspace_id}/critiques?target_id={claim_id1}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    # Filter by status
    response = test_client.get(
        f"/workspaces/{workspace_id}/critiques?status=open",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    # Filter by severity
    response = test_client.get(
        f"/workspaces/{workspace_id}/critiques?severity=blocking",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


def test_critique_sufficiency_high_trust_cannot_defer(test_db):
    """Test that high-trust critic cannot defer (fails sufficiency)."""
    from apps.worker.critique_sufficiency import CritiqueSufficiencyActivity
    
    workspace_id = str(uuid.uuid4())
    claim_id = str(uuid.uuid4())
    critic_id = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"}
    )
    
    # Create high-trust agent (reputation >= 80)
    _insert_agent(
        test_db,
        critic_id,
        f"high_trust_moltbook_{critic_id}",
        name="High Trust Critic",
        reputation=85.0
    )
    
    # Create claim
    test_db.execute(
        """
        INSERT INTO claims (id, workspace_id, text, kind, confidence, status, created_by, created_at)
        VALUES (:id, :workspace_id, :text, :kind, :confidence, :status, :created_by, NOW())
        """,
        {
            "id": claim_id,
            "workspace_id": workspace_id,
            "text": "Test claim",
            "kind": "fact",
            "confidence": 0.9,
            "status": "active",
            "created_by": None
        }
    )
    
    # Create deferred critique by high-trust agent
    test_db.execute(
        """
        INSERT INTO critiques (
            id, workspace_id, target_type, target_id, critic_agent_id,
            status, severity, message, resolution, created_at
        ) VALUES (
            :id, :workspace_id, :target_type, :target_id, :critic_agent_id,
            :status, :severity, :message, :resolution, NOW()
        )
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "target_type": "claim",
            "target_id": claim_id,
            "critic_agent_id": critic_id,
            "status": "deferred",
            "severity": "major",
            "message": "Will review later",
            "resolution": json.dumps({"status": "deferred_with_rationale", "rationale": "Need more time"})
        }
    )
    
    test_db.commit()
    
    # Check sufficiency
    activity = CritiqueSufficiencyActivity(test_db)
    result = activity.check_critique_sufficiency(
        workspace_id=workspace_id,
        target_type="claim",
        target_id=claim_id
    )
    
    # Should fail due to high-trust deferral
    assert result["status"] == "fail"
    assert len(result["high_trust_violations"]) > 0
    assert "high_trust" in result["details"]["reason"]


def test_critique_sufficiency_low_trust_deferral_passes(test_db):
    """Test that low-trust deferral with rationale passes sufficiency."""
    from apps.worker.critique_sufficiency import CritiqueSufficiencyActivity
    
    workspace_id = str(uuid.uuid4())
    claim_id = str(uuid.uuid4())
    critic_id = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"}
    )
    
    # Create low-trust agent (reputation < 80)
    _insert_agent(
        test_db,
        critic_id,
        f"low_trust_moltbook_{critic_id}",
        name="Low Trust Critic",
        reputation=50.0
    )
    
    # Create claim
    test_db.execute(
        """
        INSERT INTO claims (id, workspace_id, text, kind, confidence, status, created_by, created_at)
        VALUES (:id, :workspace_id, :text, :kind, :confidence, :status, :created_by, NOW())
        """,
        {
            "id": claim_id,
            "workspace_id": workspace_id,
            "text": "Test claim",
            "kind": "fact",
            "confidence": 0.9,
            "status": "active",
            "created_by": None
        }
    )
    
    # Create deferred critique with rationale
    test_db.execute(
        """
        INSERT INTO critiques (
            id, workspace_id, target_type, target_id, critic_agent_id,
            status, severity, message, resolution, created_at
        ) VALUES (
            :id, :workspace_id, :target_type, :target_id, :critic_agent_id,
            :status, :severity, :message, :resolution, NOW()
        )
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "target_type": "claim",
            "target_id": claim_id,
            "critic_agent_id": critic_id,
            "status": "deferred",
            "severity": "minor",
            "message": "Minor issue",
            "resolution": json.dumps({"status": "deferred_with_rationale", "rationale": "Low priority, can address later"})
        }
    )
    
    test_db.commit()
    
    # Check sufficiency
    activity = CritiqueSufficiencyActivity(test_db)
    result = activity.check_critique_sufficiency(
        workspace_id=workspace_id,
        target_type="claim",
        target_id=claim_id
    )
    
    # Should pass - low trust can defer with rationale
    assert result["status"] == "pass"
    assert result["details"]["valid_critique_count"] == 1


def test_critique_sufficiency_resolved_passes(test_db):
    """Test that resolved critiques pass sufficiency check."""
    from apps.worker.critique_sufficiency import CritiqueSufficiencyActivity
    
    workspace_id = str(uuid.uuid4())
    claim_id = str(uuid.uuid4())
    critic_id = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"}
    )
    
    # Create agent
    _insert_agent(
        test_db,
        critic_id,
        f"critic_moltbook_{critic_id}",
        name="Critic",
        reputation=85.0
    )
    
    # Create claim
    test_db.execute(
        """
        INSERT INTO claims (id, workspace_id, text, kind, confidence, status, created_by, created_at)
        VALUES (:id, :workspace_id, :text, :kind, :confidence, :status, :created_by, NOW())
        """,
        {
            "id": claim_id,
            "workspace_id": workspace_id,
            "text": "Test claim",
            "kind": "fact",
            "confidence": 0.9,
            "status": "active",
            "created_by": None
        }
    )
    
    # Create resolved critique
    test_db.execute(
        """
        INSERT INTO critiques (
            id, workspace_id, target_type, target_id, critic_agent_id,
            status, severity, message, resolution, created_at
        ) VALUES (
            :id, :workspace_id, :target_type, :target_id, :critic_agent_id,
            :status, :severity, :message, :resolution, NOW()
        )
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "target_type": "claim",
            "target_id": claim_id,
            "critic_agent_id": critic_id,
            "status": "resolved",
            "severity": "major",
            "message": "Fixed",
            "resolution": json.dumps({"status": "accepted_fix"})
        }
    )
    
    test_db.commit()
    
    # Check sufficiency
    activity = CritiqueSufficiencyActivity(test_db)
    result = activity.check_critique_sufficiency(
        workspace_id=workspace_id,
        target_type="claim",
        target_id=claim_id
    )
    
    # Should pass - resolved critique
    assert result["status"] == "pass"
    assert result["details"]["valid_critique_count"] == 1
