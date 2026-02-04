#!/usr/bin/env python3
"""
Setup test data for UI testing.
Creates a test agent, workspace, artifacts, claims, etc.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'db'))

from database import get_raw_db
import psycopg2
from datetime import datetime, timezone
import json
import uuid

def setup_test_agent(conn):
    """Create a test agent."""
    cur = conn.cursor()
    
    agent_id = str(uuid.uuid4())
    moltbook_id = "test_agent_001"
    
    # Check if agent exists
    cur.execute("SELECT id FROM agents WHERE moltbook_id = %s", (moltbook_id,))
    existing = cur.fetchone()
    
    if existing:
        print(f"✓ Test agent already exists: {existing[0]}")
        return existing[0]
    
    # Create agent
    cur.execute("""
        INSERT INTO agents (id, moltbook_id, name, reputation)
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """, (agent_id, moltbook_id, "Test Agent", 100))
    
    agent_id = cur.fetchone()[0]
    conn.commit()
    print(f"✓ Created test agent: {agent_id}")
    return agent_id

def setup_test_workspace(conn, agent_id):
    """Create a test workspace."""
    cur = conn.cursor()
    
    workspace_id = str(uuid.uuid4())
    
    cur.execute("""
        INSERT INTO workspaces (id, name, phase, description, created_by, tags)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        workspace_id,
        "Test Research Project",
        "drafting",
        "A test workspace for UI testing",
        agent_id,
        ['test', 'ui-testing']  # Use Python list, psycopg2 will convert
    ))
    
    workspace_id = cur.fetchone()[0]
    conn.commit()
    print(f"✓ Created test workspace: {workspace_id}")

    # Add agent as workspace member with Maintainer role
    cur.execute("SELECT id FROM roles WHERE name = %s", ("Maintainer",))
    role_row = cur.fetchone()
    if not role_row:
        raise RuntimeError("Maintainer role not found. Run role seeding first.")
    role_id = role_row[0]

    cur.execute(
        """
        INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status, joined_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT (workspace_id, agent_id) DO NOTHING
        """,
        (workspace_id, agent_id, role_id, "active")
    )
    conn.commit()
    print(f"✓ Added test agent to workspace with role Maintainer")
    return workspace_id

def setup_test_artifacts(conn, workspace_id):
    """Create test artifacts."""
    cur = conn.cursor()
    
    # Create a test artifact
    artifact_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO artifacts (id, workspace_id, short_id, type, storage_uri)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (artifact_id, workspace_id, "ART001", "pdf", f"/artifacts/{artifact_id}"))
    
    artifact_id = cur.fetchone()[0]
    
    # Create a version
    version_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO artifact_versions (id, artifact_id, version, storage_uri, content_hash)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (
        version_id,
        artifact_id,
        1,
        f"/artifacts/{artifact_id}/v1",
        "abc123"
    ))
    
    version_id = cur.fetchone()[0]
    conn.commit()
    print(f"✓ Created test artifact: {artifact_id} (version: {version_id})")
    return artifact_id, version_id

def setup_test_claims(conn, workspace_id, artifact_version_id):
    """Create test claims."""
    cur = conn.cursor()
    
    claims = [
        {
            "text": "Machine learning models show significant improvement when trained on larger datasets",
            "kind": "fact",
            "status": "pending",
            "confidence": "high"
        },
        {
            "text": "The proposed algorithm will outperform existing approaches",
            "kind": "hypothesis",
            "status": "pending",
            "confidence": "medium"
        }
    ]
    
    claim_ids = []
    for claim in claims:
        claim_id = str(uuid.uuid4())
        
        # Create claim
        cur.execute("""
            INSERT INTO claims (id, workspace_id, text, kind, status, confidence, is_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            claim_id,
            workspace_id,
            claim["text"],
            claim["kind"],
            claim["status"],
            claim["confidence"],
            False
        ))
        
        claim_id = cur.fetchone()[0]
        
        # Create evidence link
        evidence_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO claim_evidence (id, claim_id, artifact_version_id, location)
            VALUES (%s, %s, %s, %s)
        """, (
            evidence_id,
            claim_id,
            artifact_version_id,
            "page:3,para:2"
        ))
        
        claim_ids.append(claim_id)
        print(f"✓ Created test claim: {claim_id}")
    
    conn.commit()
    return claim_ids

def setup_test_critiques(conn, workspace_id, claim_ids):
    """Create test critiques."""
    cur = conn.cursor()
    
    # Get a critic agent id (use the test agent)
    cur.execute("SELECT id FROM agents LIMIT 1")
    critic_agent_id = cur.fetchone()[0]
    
    for claim_id in claim_ids:
        critique_id = str(uuid.uuid4())
        
        cur.execute("""
            INSERT INTO critiques (id, workspace_id, target_type, target_id, critic_agent_id, status, severity, message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            critique_id,
            workspace_id,
            "claim",
            claim_id,
            critic_agent_id,
            "pending",
            "medium",
            "This claim needs more supporting evidence from recent literature"
        ))
        
        critique_id = cur.fetchone()[0]
        print(f"✓ Created test critique: {critique_id}")
    
    conn.commit()

def setup_test_events(conn, workspace_id):
    """Create test events."""
    cur = conn.cursor()
    
    # Get a system actor id (use the test agent)
    cur.execute("SELECT id FROM agents LIMIT 1")
    actor_id = cur.fetchone()[0]
    
    events = [
        ("workspace_created", {"created_by": "system"}),
        ("phase_entered", {"phase": "drafting"}),
        ("claim_added", {"count": 2})
    ]
    
    for event_type, payload in events:
        cur.execute("""
            INSERT INTO events (id, workspace_id, actor_type, actor_id, event_type, payload)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (str(uuid.uuid4()), workspace_id, "agent", actor_id, event_type, json.dumps(payload)))
    
    conn.commit()
    print(f"✓ Created {len(events)} test events")

def setup_test_logs(conn, workspace_id):
    """Create test logs."""
    cur = conn.cursor()
    
    logs = [
        "Workspace initialized successfully",
        "Claims processing started",
        "Some evidence pointers need validation"
    ]
    
    for message in logs:
        cur.execute("""
            INSERT INTO logs (id, workspace_id, action, payload)
            VALUES (%s, %s, %s, %s)
        """, (str(uuid.uuid4()), workspace_id, message, json.dumps({})))
    
    conn.commit()
    print(f"✓ Created {len(logs)} test logs")

def main():
    print("=" * 60)
    print("Setting up test data for UI testing")
    print("=" * 60)
    
    with get_raw_db() as conn:
        try:
            agent_id = setup_test_agent(conn)
            workspace_id = setup_test_workspace(conn, agent_id)
            artifact_id, version_id = setup_test_artifacts(conn, workspace_id)
            claim_ids = setup_test_claims(conn, workspace_id, version_id)
            setup_test_critiques(conn, workspace_id, claim_ids)
            setup_test_events(conn, workspace_id)
            setup_test_logs(conn, workspace_id)
            
            print("\n" + "=" * 60)
            print("✓ Test data setup complete!")
            print("=" * 60)
            print(f"\nTest Agent ID: {agent_id}")
            print(f"Test Workspace ID: {workspace_id}")
            print(f"\nYou can use moltbook_id 'test_agent_001' to login")
            
        except Exception as e:
            print(f"\n✗ Error setting up test data: {e}")
            raise

if __name__ == "__main__":
    main()
