from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any, Mapping


def new_uuid() -> str:
    return str(uuid.uuid4())


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True)


def make_artifact_prefix(workspace_id: str, artifact_id: str) -> str:
    return f"s3://agora/{workspace_id}/artifacts/{artifact_id}/"


def make_artifact_version_uri(workspace_id: str, artifact_id: str, version: int, filename: str) -> str:
    return f"s3://agora/{workspace_id}/artifacts/{artifact_id}/v{version}/{filename}"


@dataclass(frozen=True)
class Seeded:
    workspace_id: str
    agent_id: str
    moltbook_id: str


def insert_agent(
    db,
    *,
    agent_id: str | None = None,
    moltbook_id: str | None = None,
    name: str = "Test Agent",
    reputation: float | None = 0.0,
) -> Seeded:
    agent_id = agent_id or new_uuid()
    moltbook_id = moltbook_id or f"test-moltbook-{agent_id}"
    db.execute(
        """
        INSERT INTO agents (id, moltbook_id, name, reputation, created_at)
        VALUES (:id, :moltbook_id, :name, :reputation, NOW())
        ON CONFLICT (id) DO NOTHING
        """,
        {"id": agent_id, "moltbook_id": moltbook_id, "name": name, "reputation": reputation},
    )
    db.commit()
    # workspace_id is unknown here; set to empty and let callers ignore.
    return Seeded(workspace_id="", agent_id=agent_id, moltbook_id=moltbook_id)


def role_id(db, *, role_name: str) -> str:
    row = db.execute("SELECT id FROM roles WHERE name = :name", {"name": role_name}).fetchone()
    assert row, f"Role not seeded: {role_name}"
    return str(row[0])


def insert_workspace(
    db,
    *,
    workspace_id: str | None = None,
    name: str = "Test Workspace",
    phase: str = "INIT",
    created_by: str | None = None,
    description: str | None = None,
) -> str:
    workspace_id = workspace_id or new_uuid()
    db.execute(
        """
        INSERT INTO workspaces (id, name, description, phase, created_by, created_at)
        VALUES (:id, :name, :description, :phase, :created_by, NOW())
        """,
        {
            "id": workspace_id,
            "name": name,
            "description": description,
            "phase": phase,
            "created_by": created_by,
        },
    )
    db.commit()
    return workspace_id


def add_membership(
    db,
    *,
    workspace_id: str,
    agent_id: str,
    role_name: str = "Maintainer",
    status: str = "active",
) -> None:
    rid = role_id(db, role_name=role_name)
    db.execute(
        """
        INSERT INTO workspace_agents (workspace_id, agent_id, role_id, status, joined_at)
        VALUES (:workspace_id, :agent_id, :role_id, :status, NOW())
        ON CONFLICT (workspace_id, agent_id) DO UPDATE SET role_id = EXCLUDED.role_id, status = EXCLUDED.status
        """,
        {
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "role_id": rid,
            "status": status,
        },
    )
    db.commit()


def insert_artifact(
    db,
    *,
    artifact_id: str | None = None,
    workspace_id: str,
    short_id: str,
    type: str,
    created_by: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    storage_uri: str | None = None,
) -> str:
    artifact_id = artifact_id or new_uuid()
    storage_uri = storage_uri or make_artifact_prefix(workspace_id, artifact_id)
    db.execute(
        """
        INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
        VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
        """,
        {
            "id": artifact_id,
            "workspace_id": workspace_id,
            "short_id": short_id,
            "type": type,
            "metadata": dict(metadata) if metadata is not None else None,
            "storage_uri": storage_uri,
            "created_by": created_by,
        },
    )
    db.commit()
    return artifact_id


def insert_artifact_version(
    db,
    *,
    version_id: str | None = None,
    artifact_id: str,
    version: int,
    storage_uri: str,
    content_hash: str | None = None,
    created_by: str | None = None,
) -> str:
    version_id = version_id or new_uuid()
    db.execute(
        """
        INSERT INTO artifact_versions (id, artifact_id, version, storage_uri, content_hash, created_by, created_at)
        VALUES (:id, :artifact_id, :version, :storage_uri, :content_hash, :created_by, NOW())
        """,
        {
            "id": version_id,
            "artifact_id": artifact_id,
            "version": version,
            "storage_uri": storage_uri,
            "content_hash": content_hash,
            "created_by": created_by,
        },
    )
    db.commit()
    return version_id


def insert_claim(
    db,
    *,
    claim_id: str | None = None,
    workspace_id: str,
    kind: str = "fact",
    text: str = "Test claim",
    confidence: str | None = None,
    status: str = "active",
    created_by: str | None = None,
    is_key: bool = False,
) -> str:
    claim_id = claim_id or new_uuid()
    db.execute(
        """
        INSERT INTO claims (id, workspace_id, kind, text, confidence, is_key, status, created_by, created_at)
        VALUES (:id, :workspace_id, :kind, :text, :confidence, :is_key, :status, :created_by, NOW())
        """,
        {
            "id": claim_id,
            "workspace_id": workspace_id,
            "kind": kind,
            "text": text,
            "confidence": confidence,
            "is_key": is_key,
            "status": status,
            "created_by": created_by,
        },
    )
    db.commit()
    return claim_id

