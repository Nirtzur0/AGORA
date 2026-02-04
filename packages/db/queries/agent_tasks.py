"""
Agent task query helpers.

These helpers centralize common SQL fragments for agent_tasks.
"""
from typing import Any, Dict, Optional


def insert_agent_task(
    db,
    *,
    task_id: str,
    workspace_id: str,
    task_type: str,
    status: str,
    payload: Dict[str, Any],
    assignee_agent_id: Optional[str] = None,
) -> None:
    db.execute(
        """
        INSERT INTO agent_tasks (
            id,
            workspace_id,
            assignee_agent_id,
            type,
            status,
            payload
        ) VALUES (
            :id,
            :workspace_id,
            :assignee_agent_id,
            :type,
            :status,
            :payload
        )
        """,
        {
            "id": task_id,
            "workspace_id": workspace_id,
            "assignee_agent_id": assignee_agent_id,
            "type": task_type,
            "status": status,
            "payload": payload,
        },
    )


def fetch_agent_task(
    db,
    *,
    task_id: str,
):
    return db.execute(
        """
        SELECT id, workspace_id, assignee_agent_id, type, status, payload, created_at, completed_at
        FROM agent_tasks
        WHERE id = :id
        """,
        {"id": task_id},
    ).fetchone()
