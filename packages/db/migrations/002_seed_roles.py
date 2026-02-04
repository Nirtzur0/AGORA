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
            "role_capacity": 1,  # One maintainer per workspace
            "is_unique": True,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Literature Analyst",
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
            "role_capacity": 3,
            "is_unique": False,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Experimentalist",
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
            "role_capacity": 2,
            "is_unique": False,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Method Reviewer",
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
            "role_capacity": 2,
            "is_unique": False,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Skeptic",
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
            "role_capacity": 2,
            "is_unique": False,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Synthesizer",
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
            "role_capacity": 2,
            "is_unique": False,
        },
    ]
    
    import json
    from psycopg.types.json import Jsonb
    cursor = conn.cursor()
    
    for role in roles:
        cursor.execute(
            """
            INSERT INTO roles (id, name, permissions, min_reputation, role_capacity, is_unique)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE
            SET 
                permissions = EXCLUDED.permissions,
                min_reputation = EXCLUDED.min_reputation,
                role_capacity = EXCLUDED.role_capacity,
                is_unique = EXCLUDED.is_unique
            """,
            (
                role["id"],
                role["name"],
                Jsonb(role["permissions"]),
                role["min_reputation"],
                role["role_capacity"],
                role["is_unique"],
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
