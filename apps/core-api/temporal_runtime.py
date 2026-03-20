"""Shared Temporal workflow start helpers for core-api routes."""

from __future__ import annotations

import uuid
from typing import Any

from temporalio.client import Client

from runtime_config import get_temporal_address, get_temporal_task_queue


async def execute_tracked_workflow(
    *,
    db,
    workspace_id: str,
    workflow_type: str,
    workflow_callable: Any,
    workflow_id: str,
    args: list[Any],
) -> tuple[str, Any]:
    workflow_run_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO workflow_runs (id, workspace_id, workflow_type, temporal_workflow_id, status)
        VALUES (:id, :workspace_id, :workflow_type, :temporal_workflow_id, :status)
        """,
        {
            "id": workflow_run_id,
            "workspace_id": workspace_id,
            "workflow_type": workflow_type,
            "temporal_workflow_id": workflow_id,
            "status": "running",
        },
    )
    db.commit()

    client = await Client.connect(get_temporal_address())
    resolved_args = list(args)
    if resolved_args and resolved_args[0] is None:
        resolved_args[0] = workflow_run_id

    handle = await client.start_workflow(
        workflow_callable,
        args=resolved_args,
        id=workflow_id,
        task_queue=get_temporal_task_queue(),
    )

    try:
        result = await handle.result()
    except Exception:
        db.execute(
            """
            UPDATE workflow_runs
            SET status = :status, completed_at = NOW()
            WHERE id = :id
            """,
            {"id": workflow_run_id, "status": "failed"},
        )
        db.commit()
        raise

    db.execute(
        """
        UPDATE workflow_runs
        SET status = :status, completed_at = NOW()
        WHERE id = :id
        """,
        {"id": workflow_run_id, "status": "completed"},
    )
    db.commit()
    return workflow_run_id, result
