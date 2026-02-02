"""
Phase Management Activities Registration

Activities for phase advancement workflows.
These must be registered with Temporal workers.
"""
from temporalio import activity
from database import get_db
from apps.worker.phase_machine import PhaseAdvancementActivity, PhaseMachine
from apps.worker.gates import GateEvaluationActivity
from apps.worker.finalization_activities import finalize_draft_artifact
from apps.worker.indexing_activities import (
    index_artifact_content,
    index_pdf_text,
    index_repo_file,
    index_log
)
import logging

logger = logging.getLogger(__name__)


@activity.defn(name="get_workspace_phase")
async def get_workspace_phase(workspace_id: str) -> dict:
    """
    Get current workspace phase.
    
    Args:
        workspace_id: Workspace ID
        
    Returns:
        Dict with phase info
    """
    with get_db() as db:
        row = db.execute(
            "SELECT phase, updated_at FROM workspaces WHERE id = :id",
            {"id": workspace_id}
        ).fetchone()
        
        if not row:
            raise ValueError(f"Workspace not found: {workspace_id}")
        
        return {
            "workspace_id": workspace_id,
            "phase": row[0],
            "updated_at": row[1].isoformat() if row[1] else None
        }


@activity.defn(name="validate_phase_transition")
async def validate_phase_transition(current_phase: str, next_phase: str) -> dict:
    """
    Validate if phase transition is allowed.
    
    Args:
        current_phase: Current phase
        next_phase: Target phase
        
    Returns:
        Dict with validation result
    """
    try:
        PhaseMachine.validate_transition(current_phase, next_phase)
        return {
            "valid": True,
            "current_phase": current_phase,
            "next_phase": next_phase
        }
    except Exception as e:
        return {
            "valid": False,
            "current_phase": current_phase,
            "next_phase": next_phase,
            "error": str(e)
        }


@activity.defn(name="advance_workspace_phase")
async def advance_workspace_phase(
    workspace_id: str,
    next_phase: str,
    gate_summary: dict,
    workflow_run_id: str
) -> dict:
    """
    Advance workspace phase and emit event.
    
    Args:
        workspace_id: Workspace ID
        next_phase: Target phase
        gate_summary: Gate evaluation results
        workflow_run_id: Workflow run ID for audit
        
    Returns:
        Dict with advancement result
    """
    with get_db() as db:
        activity_impl = PhaseAdvancementActivity(db)
        return activity_impl.advance_phase(
            workspace_id=workspace_id,
            next_phase=next_phase,
            gate_summary=gate_summary,
            workflow_run_id=workflow_run_id
        )


@activity.defn(name="create_required_action_tasks")
async def create_required_action_tasks(
    workspace_id: str,
    required_actions: list,
    workflow_run_id: str
) -> list:
    """
    Create agent_tasks for required actions when gates fail.
    
    Args:
        workspace_id: Workspace ID
        required_actions: List of required actions from gate evaluation
        workflow_run_id: Workflow run ID for audit
        
    Returns:
        List of created task IDs
    """
    with get_db() as db:
        activity_impl = PhaseAdvancementActivity(db)
        return activity_impl.create_required_action_tasks(
            workspace_id=workspace_id,
            required_actions=required_actions,
            workflow_run_id=workflow_run_id
        )


@activity.defn(name="gather_lit_review_exit_snapshot")
async def gather_lit_review_exit_snapshot(workspace_id: str) -> dict:
    """
    Gather snapshot for LIT_REVIEW exit gate.
    
    Args:
        workspace_id: Workspace ID
        
    Returns:
        Snapshot dict
    """
    with get_db() as db:
        activity_impl = GateEvaluationActivity(db)
        return activity_impl.gather_lit_review_exit_snapshot(workspace_id)


@activity.defn(name="gather_experimentation_exit_snapshot")
async def gather_experimentation_exit_snapshot(workspace_id: str) -> dict:
    """
    Gather snapshot for EXPERIMENTATION exit gate.
    
    Args:
        workspace_id: Workspace ID
        
    Returns:
        Snapshot dict
    """
    with get_db() as db:
        activity_impl = GateEvaluationActivity(db)
        return activity_impl.gather_experimentation_exit_snapshot(workspace_id)


@activity.defn(name="gather_internal_review_exit_snapshot")
async def gather_internal_review_exit_snapshot(workspace_id: str) -> dict:
    """
    Gather snapshot for INTERNAL_REVIEW exit gate.
    
    Args:
        workspace_id: Workspace ID
        
    Returns:
        Snapshot dict
    """
    with get_db() as db:
        activity_impl = GateEvaluationActivity(db)
        return activity_impl.gather_internal_review_exit_snapshot(workspace_id)


@activity.defn(name="gather_finalization_gate_snapshot")
async def gather_finalization_gate_snapshot(
    workspace_id: str,
    draft_artifact_id: str,
    draft_artifact_version_id: str
) -> dict:
    """
    Gather snapshot for finalization gate.
    
    Args:
        workspace_id: Workspace ID
        draft_artifact_id: Draft artifact ID
        draft_artifact_version_id: Draft artifact version ID
        
    Returns:
        Snapshot dict
    """
    with get_db() as db:
        activity_impl = GateEvaluationActivity(db)
        return activity_impl.gather_finalization_gate_snapshot(
            workspace_id,
            draft_artifact_id,
            draft_artifact_version_id
        )


# List of all phase management activities to register with worker
PHASE_ACTIVITIES = [
    get_workspace_phase,
    validate_phase_transition,
    advance_workspace_phase,
    create_required_action_tasks,
    gather_lit_review_exit_snapshot,
    gather_experimentation_exit_snapshot,
    gather_internal_review_exit_snapshot,
    gather_finalization_gate_snapshot,
    finalize_draft_artifact,
    index_artifact_content,
    index_pdf_text,
    index_repo_file,
    index_log
]
