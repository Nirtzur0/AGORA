"""
Seed roles with canonical permissions.

Creates the 6 MVP roles with their permission keys exactly as specified in:
Docs/04-system-implementation-spec.md §4.0 Permission Keys (Canonical)
"""

import uuid


def upgrade(conn):
    """Seed roles with canonical permissions."""
    
    roles = [
        {
            "id": str(uuid.uuid4()),
            "name": "Maintainer",
            "description": "Workspace owner/admin agent with full access (except phase changes)",
            "permissions": {
                "allow": [
                    "workspace.create",
                    "workspace.read",
                    "workspace.update",
                    "join_request.review",
                    "artifact.create",
                    "artifact.read",
                    "artifact.version.create",
                    "artifact.request.ingest_pdf",
                    "artifact.request.ingest_repo",
                    "execution.request.run_sandbox",
                    "rulecheck.request",
                    "claim.create",
                    "claim.evidence.add",
                    "claim.read",
                    "critique.create",
                    "critique.resolve",
                    "critique.read",
                    "draft.create",
                    "draft.version.create",
                    "log.write",
                    "log.read",
                ]
            },
            "min_reputation": 0,
            "capacity": 1,  # One maintainer per workspace
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Literature Analyst",
            "description": "Focus on sourcing and claim extraction from literature",
            "permissions": {
                "allow": [
                    "workspace.read",
                    "join_request.create",
                    "artifact.read",
                    "artifact.request.ingest_pdf",
                    "claim.create",
                    "claim.evidence.add",
                    "claim.read",
                    "critique.create",
                    "critique.read",
                    "log.write",
                    "log.read",
                ]
            },
            "min_reputation": 100,
            "capacity": 3,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Experimentalist",
            "description": "Runs experiments and creates artifact versions",
            "permissions": {
                "allow": [
                    "workspace.read",
                    "join_request.create",
                    "artifact.read",
                    "artifact.request.ingest_repo",
                    "artifact.version.create",
                    "execution.request.run_sandbox",
                    "claim.create",
                    "claim.evidence.add",
                    "claim.read",
                    "critique.create",
                    "critique.read",
                    "log.write",
                    "log.read",
                ]
            },
            "min_reputation": 200,
            "capacity": 2,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Method Reviewer",
            "description": "Verifies methodology and results",
            "permissions": {
                "allow": [
                    "workspace.read",
                    "artifact.read",
                    "execution.request.run_sandbox",
                    "rulecheck.request",
                    "critique.create",
                    "critique.resolve",
                    "critique.read",
                    "claim.read",
                    "log.write",
                    "log.read",
                ]
            },
            "min_reputation": 300,
            "capacity": 2,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Skeptic",
            "description": "Proposes alternative hypotheses and creates blocking critiques",
            "permissions": {
                "allow": [
                    "workspace.read",
                    "artifact.read",
                    "rulecheck.request",
                    "critique.create",
                    "critique.resolve",
                    "critique.read",
                    "claim.create",
                    "claim.read",
                    "log.write",
                    "log.read",
                ]
            },
            "min_reputation": 250,
            "capacity": 2,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Synthesizer",
            "description": "Writes drafts and synthesizes findings",
            "permissions": {
                "allow": [
                    "workspace.read",
                    "artifact.read",
                    "claim.read",
                    "critique.read",
                    "draft.create",
                    "draft.version.create",
                    "log.write",
                    "log.read",
                ]
            },
            "min_reputation": 200,
            "capacity": 2,
        },
    ]
    
    cursor = conn.cursor()
    
    for role in roles:
        cursor.execute(
            """
            INSERT INTO roles (id, name, description, permissions, min_reputation, capacity)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE
            SET 
                description = EXCLUDED.description,
                permissions = EXCLUDED.permissions,
                min_reputation = EXCLUDED.min_reputation,
                capacity = EXCLUDED.capacity,
                updated_at = NOW()
            """,
            (
                role["id"],
                role["name"],
                role["description"],
                role["permissions"],
                role["min_reputation"],
                role["capacity"],
            ),
        )
    
    conn.commit()
    print(f"✓ Seeded {len(roles)} roles with canonical permissions")


def downgrade(conn):
    """Remove seeded roles."""
    cursor = conn.cursor()
    
    role_names = [
        "Maintainer",
        "Literature Analyst",
        "Experimentalist",
        "Method Reviewer",
        "Skeptic",
        "Synthesizer",
    ]
    
    for name in role_names:
        cursor.execute("DELETE FROM roles WHERE name = %s", (name,))
    
    conn.commit()
    print(f"✓ Removed seeded roles")
