"""
Draft Finalization Activities - Component 21

This module implements Temporal activities for draft finalization.
Activities are non-deterministic and interact with the database and external systems.

Per spec §5.6, §4.10, §12.4:
    - finalize_draft_artifact: Sets draft artifact metadata status=final, emits events
- Must validate workspace.phase == FINALIZED before allowing finalization
"""

import logging
from datetime import datetime, timezone
from temporalio import activity
from sqlalchemy import text
from apps.worker.database import get_db_connection

logger = logging.getLogger(__name__)


@activity.defn
async def finalize_draft_artifact(
    workspace_id: str,
    draft_artifact_id: str,
    draft_artifact_version_id: str
) -> dict:
    """
    Finalize a draft artifact by setting its metadata and emitting events.
    
    Per spec §5.6:
    - Set draft artifact metadata status=final
    - Emit draft.finalized event
    - Emit workspace.finalized event
    - Validate workspace.phase == FINALIZED
    
    Args:
        workspace_id: Workspace containing the draft
        draft_artifact_id: ID of the draft artifact
        draft_artifact_version_id: Specific version to finalize
    
    Returns:
        dict with finalization_timestamp
    
    Raises:
        ValueError: If workspace phase is not FINALIZED
        RuntimeError: If finalization fails
    """
    logger.info(
        f"Finalizing draft artifact {draft_artifact_id} version {draft_artifact_version_id} "
        f"in workspace {workspace_id}"
    )
    
    conn = get_db_connection()
    
    try:
        # Validate workspace phase is FINALIZED
        workspace_phase = conn.execute(
            text("SELECT phase FROM workspaces WHERE id = :workspace_id"),
            {"workspace_id": workspace_id}
        ).fetchone()
        
        if not workspace_phase:
            raise ValueError(f"Workspace {workspace_id} not found")
        
        if workspace_phase[0] != "FINALIZED":
            raise ValueError(
                f"Cannot finalize draft: workspace phase is {workspace_phase[0]}, "
                f"must be FINALIZED"
            )
        
        # Get current draft metadata
        artifact_row = conn.execute(
            text("""
                SELECT metadata
                FROM artifacts
                WHERE id = :artifact_id
            """),
            {"artifact_id": draft_artifact_id}
        ).fetchone()
        
        if not artifact_row:
            raise ValueError(f"Draft artifact {draft_artifact_id} not found")
        
        current_metadata = artifact_row[0] or {}
        finalization_timestamp = datetime.now(timezone.utc).isoformat()
        
        # Update metadata with finalization status
        new_metadata = {
            **current_metadata,
            "status": "final",
            "final_version_id": draft_artifact_version_id,
            "finalization_timestamp": finalization_timestamp
        }
        
        # Update draft artifact metadata
        conn.execute(
            text("""
                UPDATE artifacts
                SET metadata = :metadata
                WHERE id = :artifact_id
            """),
            {
                "artifact_id": draft_artifact_id,
                "metadata": new_metadata
            }
        )
        
        # Emit draft.finalized event
        conn.execute(
            text("""
                INSERT INTO events (id, workspace_id, actor_type, actor_id, event_type, payload, created_at)
                VALUES (gen_random_uuid(), :workspace_id, 'system', :actor_id, 'draft.finalized', :payload, NOW())
            """),
            {
                "workspace_id": workspace_id,
                "actor_id": workspace_id,
                "payload": {
                    "draft_artifact_id": draft_artifact_id,
                    "draft_artifact_version_id": draft_artifact_version_id,
                    "finalization_timestamp": finalization_timestamp
                }
            }
        )
        
        # Emit workspace.finalized event
        conn.execute(
            text("""
                INSERT INTO events (id, workspace_id, actor_type, actor_id, event_type, payload, created_at)
                VALUES (gen_random_uuid(), :workspace_id, 'system', :actor_id, 'workspace.finalized', :payload, NOW())
            """),
            {
                "workspace_id": workspace_id,
                "actor_id": workspace_id,
                "payload": {
                    "draft_artifact_id": draft_artifact_id,
                    "draft_artifact_version_id": draft_artifact_version_id,
                    "finalization_timestamp": finalization_timestamp
                }
            }
        )
        
        conn.commit()
        
        logger.info(
            f"Draft finalized successfully: {draft_artifact_version_id} "
            f"at {finalization_timestamp}"
        )
        
        return {
            "finalization_timestamp": finalization_timestamp,
            "final_version_id": draft_artifact_version_id
        }
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to finalize draft: {e}")
        raise RuntimeError(f"Draft finalization failed: {e}")
    finally:
        conn.close()


# Activity list for worker registration
FINALIZATION_ACTIVITIES = [
    finalize_draft_artifact,
]
