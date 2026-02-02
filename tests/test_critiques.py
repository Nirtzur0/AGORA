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


def test_create_critique(test_client, test_db, mock_agent_token):
    """Test critique creation on a claim."""
    workspace_id = str(uuid.uuid4())
    agent_id = "test_agent_id"
    claim_id = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"}
    )
    
    # Create claim
    test_db.execute(
        """
        INSERT INTO claims (id, workspace_id, text, kind, confidence, created_by, created_at)
        VALUES (:id, :workspace_id, :text, :kind, :confidence, :created_by, NOW())
        """,
        {
            "id": claim_id,
            "workspace_id": workspace_id,
            "text": "Test claim",
            "kind": "fact",
            "confidence": 0.9,
            "created_by": agent_id
        }
    )
    
    test_db.commit()
    
    # Create critique
    response = test_client.post(
        f"/workspaces/{workspace_id}/critiques",
        headers={"Authorization": f"Bearer {mock_agent_token}"},
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
    author_id = "author_agent_id"
    critic_id = "critic_agent_id"
    claim_id = str(uuid.uuid4())
    critique_id = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"}
    )
    
    # Create claim by author
    test_db.execute(
        """
        INSERT INTO claims (id, workspace_id, text, kind, confidence, created_by, created_at)
        VALUES (:id, :workspace_id, :text, :kind, :confidence, :created_by, NOW())
        """,
        {
            "id": claim_id,
            "workspace_id": workspace_id,
            "text": "Author's claim",
            "kind": "fact",
            "confidence": 0.9,
            "created_by": author_id
        }
    )
    
    # Create critique by critic
    test_db.execute(
        """
        INSERT INTO critiques (
            id, workspace_id, target_type, target_id, critic_agent_id,
            status, severity, message, created_at
        ) VALUES (
            :id, :workspace_id, :target_type, :target_id, :critic_agent_id,
            :status, :severity, :message, NOW()
        )
        """,
        {
            "id": critique_id,
            "workspace_id": workspace_id,
            "target_type": "claim",
            "target_id": claim_id,
            "critic_agent_id": critic_id,
            "status": "open",
            "severity": "major",
            "message": "Needs revision"
        }
    )
    
    test_db.commit()
    
    # Author tries to resolve critique (should fail)
    # Mock token for author
    import jwt
    author_token = jwt.encode(
        {"agent_id": author_id, "moltbook_id": "author_moltbook"},
        "test_secret",
        algorithm="HS256"
    )
    
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
    critic_id = "critic_agent_id"
    other_id = "other_agent_id"
    claim_id = str(uuid.uuid4())
    critique_id = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"}
    )
    
    # Create claim
    test_db.execute(
        """
        INSERT INTO claims (id, workspace_id, text, kind, confidence, created_by, created_at)
        VALUES (:id, :workspace_id, :text, :kind, :confidence, :created_by, NOW())
        """,
        {
            "id": claim_id,
            "workspace_id": workspace_id,
            "text": "Test claim",
            "kind": "fact",
            "confidence": 0.9,
            "created_by": "some_author"
        }
    )
    
    # Create critique
    test_db.execute(
        """
        INSERT INTO critiques (
            id, workspace_id, target_type, target_id, critic_agent_id,
            status, severity, message, created_at
        ) VALUES (
            :id, :workspace_id, :target_type, :target_id, :critic_agent_id,
            :status, :severity, :message, NOW()
        )
        """,
        {
            "id": critique_id,
            "workspace_id": workspace_id,
            "target_type": "claim",
            "target_id": claim_id,
            "critic_agent_id": critic_id,
            "status": "open",
            "severity": "major",
            "message": "Needs work"
        }
    )
    
    test_db.commit()
    
    # Other agent tries to update (should fail)
    import jwt
    other_token = jwt.encode(
        {"agent_id": other_id, "moltbook_id": "other_moltbook"},
        "test_secret",
        algorithm="HS256"
    )
    
    response = test_client.patch(
        f"/critiques/{critique_id}",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"status": "resolved"}
    )
    
    assert response.status_code == 403
    assert "Only the critic or a Maintainer" in response.json()["detail"]
    
    # Critic updates successfully
    critic_token = jwt.encode(
        {"agent_id": critic_id, "moltbook_id": "critic_moltbook"},
        "test_secret",
        algorithm="HS256"
    )
    
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
    critic_id = "critic_agent_id"
    maintainer_id = "maintainer_agent_id"
    claim_id = str(uuid.uuid4())
    critique_id = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"}
    )
    
    # Create Maintainer role
    role_id = str(uuid.uuid4())
    test_db.execute(
        "INSERT INTO roles (id, name, description) VALUES (:id, :name, :description)",
        {"id": role_id, "name": "Maintainer", "description": "Maintainer role"}
    )
    
    # Assign maintainer
    test_db.execute(
        """
        INSERT INTO workspace_agents (id, workspace_id, agent_id, role_id, status, joined_at)
        VALUES (:id, :workspace_id, :agent_id, :role_id, :status, NOW())
        """,
        {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "agent_id": maintainer_id,
            "role_id": role_id,
            "status": "active"
        }
    )
    
    # Create claim by someone else
    test_db.execute(
        """
        INSERT INTO claims (id, workspace_id, text, kind, confidence, created_by, created_at)
        VALUES (:id, :workspace_id, :text, :kind, :confidence, :created_by, NOW())
        """,
        {
            "id": claim_id,
            "workspace_id": workspace_id,
            "text": "Test claim",
            "kind": "fact",
            "confidence": 0.9,
            "created_by": "other_author"
        }
    )
    
    # Create critique
    test_db.execute(
        """
        INSERT INTO critiques (
            id, workspace_id, target_type, target_id, critic_agent_id,
            status, severity, message, created_at
        ) VALUES (
            :id, :workspace_id, :target_type, :target_id, :critic_agent_id,
            :status, :severity, :message, NOW()
        )
        """,
        {
            "id": critique_id,
            "workspace_id": workspace_id,
            "target_type": "claim",
            "target_id": claim_id,
            "critic_agent_id": critic_id,
            "status": "open",
            "severity": "major",
            "message": "Needs work"
        }
    )
    
    test_db.commit()
    
    # Maintainer overrides
    import jwt
    maintainer_token = jwt.encode(
        {"agent_id": maintainer_id, "moltbook_id": "maintainer_moltbook"},
        "test_secret",
        algorithm="HS256"
    )
    
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
    payload = json.loads(event[1])
    assert payload["critique_id"] == critique_id


def test_list_critiques_with_filters(test_client, test_db, mock_agent_token):
    """Test listing critiques with filters."""
    workspace_id = str(uuid.uuid4())
    agent_id = "test_agent_id"
    claim_id1 = str(uuid.uuid4())
    claim_id2 = str(uuid.uuid4())
    
    # Create workspace
    test_db.execute(
        "INSERT INTO workspaces (id, name, phase) VALUES (:id, :name, :phase)",
        {"id": workspace_id, "name": "Test Workspace", "phase": "active"}
    )
    
    # Create claims
    for cid in [claim_id1, claim_id2]:
        test_db.execute(
            """
            INSERT INTO claims (id, workspace_id, text, kind, confidence, created_by, created_at)
            VALUES (:id, :workspace_id, :text, :kind, :confidence, :created_by, NOW())
            """,
            {
                "id": cid,
                "workspace_id": workspace_id,
                "text": f"Claim {cid}",
                "kind": "fact",
                "confidence": 0.9,
                "created_by": agent_id
            }
        )
    
    # Create critiques
    critique1 = str(uuid.uuid4())
    critique2 = str(uuid.uuid4())
    critique3 = str(uuid.uuid4())
    
    critiques_data = [
        (critique1, claim_id1, "open", "major"),
        (critique2, claim_id1, "resolved", "minor"),
        (critique3, claim_id2, "open", "blocking")
    ]
    
    for crit_id, target_id, status, severity in critiques_data:
        test_db.execute(
            """
            INSERT INTO critiques (
                id, workspace_id, target_type, target_id, critic_agent_id,
                status, severity, message, created_at
            ) VALUES (
                :id, :workspace_id, :target_type, :target_id, :critic_agent_id,
                :status, :severity, :message, NOW()
            )
            """,
            {
                "id": crit_id,
                "workspace_id": workspace_id,
                "target_type": "claim",
                "target_id": target_id,
                "critic_agent_id": agent_id,
                "status": status,
                "severity": severity,
                "message": "Test critique"
            }
        )
    
    test_db.commit()
    
    # List all critiques
    response = test_client.get(
        f"/workspaces/{workspace_id}/critiques",
        headers={"Authorization": f"Bearer {mock_agent_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    
    # Filter by target_id
    response = test_client.get(
        f"/workspaces/{workspace_id}/critiques?target_id={claim_id1}",
        headers={"Authorization": f"Bearer {mock_agent_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    # Filter by status
    response = test_client.get(
        f"/workspaces/{workspace_id}/critiques?status=open",
        headers={"Authorization": f"Bearer {mock_agent_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    # Filter by severity
    response = test_client.get(
        f"/workspaces/{workspace_id}/critiques?severity=blocking",
        headers={"Authorization": f"Bearer {mock_agent_token}"}
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
    test_db.execute(
        """
        INSERT INTO agents (id, moltbook_id, display_name, reputation)
        VALUES (:id, :moltbook_id, :display_name, :reputation)
        """,
        {
            "id": critic_id,
            "moltbook_id": "high_trust_moltbook",
            "display_name": "High Trust Critic",
            "reputation": 85.0
        }
    )
    
    # Create claim
    test_db.execute(
        """
        INSERT INTO claims (id, workspace_id, text, kind, confidence, created_by, created_at)
        VALUES (:id, :workspace_id, :text, :kind, :confidence, :created_by, NOW())
        """,
        {
            "id": claim_id,
            "workspace_id": workspace_id,
            "text": "Test claim",
            "kind": "fact",
            "confidence": 0.9,
            "created_by": "author_id"
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
    test_db.execute(
        """
        INSERT INTO agents (id, moltbook_id, display_name, reputation)
        VALUES (:id, :moltbook_id, :display_name, :reputation)
        """,
        {
            "id": critic_id,
            "moltbook_id": "low_trust_moltbook",
            "display_name": "Low Trust Critic",
            "reputation": 50.0
        }
    )
    
    # Create claim
    test_db.execute(
        """
        INSERT INTO claims (id, workspace_id, text, kind, confidence, created_by, created_at)
        VALUES (:id, :workspace_id, :text, :kind, :confidence, :created_by, NOW())
        """,
        {
            "id": claim_id,
            "workspace_id": workspace_id,
            "text": "Test claim",
            "kind": "fact",
            "confidence": 0.9,
            "created_by": "author_id"
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
    test_db.execute(
        """
        INSERT INTO agents (id, moltbook_id, display_name, reputation)
        VALUES (:id, :moltbook_id, :display_name, :reputation)
        """,
        {
            "id": critic_id,
            "moltbook_id": "critic_moltbook",
            "display_name": "Critic",
            "reputation": 85.0
        }
    )
    
    # Create claim
    test_db.execute(
        """
        INSERT INTO claims (id, workspace_id, text, kind, confidence, created_by, created_at)
        VALUES (:id, :workspace_id, :text, :kind, :confidence, :created_by, NOW())
        """,
        {
            "id": claim_id,
            "workspace_id": workspace_id,
            "text": "Test claim",
            "kind": "fact",
            "confidence": 0.9,
            "created_by": "author_id"
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
