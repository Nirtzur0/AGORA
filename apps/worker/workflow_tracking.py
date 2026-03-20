"""Workflow/activity audit helpers shared by worker activities."""

from __future__ import annotations

import uuid
from typing import Optional


def create_activity_run(
    *,
    db,
    workflow_run_id: str,
    activity_type: str,
    activity_id: str,
) -> str:
    activity_run_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO activity_runs (
            id,
            workflow_run_id,
            activity_type,
            temporal_activity_id,
            status
        ) VALUES (
            :id,
            :workflow_run_id,
            :activity_type,
            :temporal_activity_id,
            :status
        )
        """,
        {
            "id": activity_run_id,
            "workflow_run_id": workflow_run_id,
            "activity_type": activity_type,
            "temporal_activity_id": activity_id,
            "status": "running",
        },
    )
    db.commit()
    return activity_run_id


def update_activity_run(*, db, activity_run_id: str, status: str, error: Optional[str] = None) -> None:
    db.execute(
        """
        UPDATE activity_runs
        SET status = :status,
            completed_at = NOW()
        WHERE id = :id
        """,
        {"id": activity_run_id, "status": status},
    )
    db.commit()

