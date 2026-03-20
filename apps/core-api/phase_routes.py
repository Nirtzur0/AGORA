"""
Phase Management Routes

Endpoints for workspace phase transitions (orchestrator only).

Per spec §5.3: Only the orchestrator may advance phases.
Agents cannot directly change workspace.phase.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from database import get_db_session
from auth_middleware import require_system_token, SystemContext
import logging
from pathlib import Path
import sys
import uuid

from temporal_runtime import execute_tracked_workflow

router = APIRouter()
logger = logging.getLogger(__name__)


def _ensure_worker_path() -> None:
    worker_path = Path(__file__).resolve().parents[2] / "apps" / "worker"
    worker_path_str = str(worker_path)
    if worker_path_str not in sys.path:
        sys.path.insert(0, worker_path_str)


class PhaseAdvancementRequest(BaseModel):
    """Request to advance workspace phase."""
    target_phase: str
    reason: Optional[str] = None


class PhaseStatus(BaseModel):
    """Current phase status."""
    workspace_id: str
    current_phase: str
    allowed_next_phases: list[str]


@router.get("/workspaces/{workspace_id}/phase", response_model=PhaseStatus)
async def get_phase_status(
    workspace_id: str,
    db=Depends(get_db_session)
):
    """
    Get current phase and allowed transitions.
    
    This is a read-only endpoint accessible to all workspace members.
    """
    # Get workspace phase
    row = db.execute(
        "SELECT phase FROM workspaces WHERE id = :id",
        {"id": workspace_id}
    ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    current_phase = row[0]
    
    # Get allowed next phases
    _ensure_worker_path()
    from phase_machine import PhaseMachine
    allowed_next = PhaseMachine.get_allowed_next_phases(current_phase)
    
    return PhaseStatus(
        workspace_id=workspace_id,
        current_phase=current_phase,
        allowed_next_phases=allowed_next
    )


@router.post("/workspaces/{workspace_id}/advance-phase")
async def advance_phase(
    workspace_id: str,
    request: PhaseAdvancementRequest,
    system_context: SystemContext = Depends(require_system_token),
    db=Depends(get_db_session)
):
    """
    Trigger phase advancement workflow (system/orchestrator only).
    
    This endpoint is INTERNAL ONLY - called by orchestrator workflows.
    Regular agents MUST NOT call this endpoint.
    
    System-level authentication is required.
    """
    # Verify workspace exists
    row = db.execute(
        "SELECT phase FROM workspaces WHERE id = :id",
        {"id": workspace_id}
    ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    current_phase = row[0]
    
    # Validate transition is allowed
    _ensure_worker_path()
    from phase_machine import PhaseMachine
    
    if not PhaseMachine.is_valid_transition(current_phase, request.target_phase):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid phase transition: {current_phase} -> {request.target_phase}"
        )
    
    # Start phase advancement workflow
    try:
        _ensure_worker_path()
        from phase_advancement_workflow import PhaseAdvancementWorkflow
        workflow_id = f"phase-advancement-{workspace_id}-{request.target_phase}-{uuid.uuid4()}"
        workflow_run_id, result = await execute_tracked_workflow(
            db=db,
            workspace_id=workspace_id,
            workflow_type="phase_advancement",
            workflow_callable=PhaseAdvancementWorkflow.run,
            workflow_id=workflow_id,
            args=[workspace_id, request.target_phase, request.reason],
        )
        
        logger.info(
            f"Completed phase advancement workflow",
            extra={
                "workspace_id": workspace_id,
                "target_phase": request.target_phase,
                "workflow_id": workflow_id,
            }
        )
        
        return {
            "workflow_id": workflow_id,
            "workflow_run_id": workflow_run_id,
            "workspace_id": workspace_id,
            "current_phase": current_phase,
            "target_phase": request.target_phase,
            "status": "completed" if result.get("success") else "blocked",
            "gate_result": result.get("gate_result"),
        }
    
    except Exception as e:
        logger.error(f"Failed to start phase advancement workflow: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start phase advancement workflow: {str(e)}"
        )


@router.get("/workspaces/{workspace_id}/gate-status")
async def get_gate_status(
    workspace_id: str,
    db=Depends(get_db_session)
):
    """
    Get current gate evaluation status for workspace.
    
    Returns gate readiness for advancing to next phase.
    This is informational only - actual gate evaluation happens in workflow.
    """
    # Get workspace phase
    row = db.execute(
        "SELECT phase FROM workspaces WHERE id = :id",
        {"id": workspace_id}
    ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    current_phase = row[0]
    
    # Determine which gate snapshot to gather
    _ensure_worker_path()
    from gates import GateEvaluationActivity, GateEvaluator
    
    gate_activity = GateEvaluationActivity(db)
    
    gate_name = None
    snapshot = None
    gate_result = None
    
    if current_phase == "LIT_REVIEW":
        gate_name = "lit_review_exit"
        snapshot = gate_activity.gather_lit_review_exit_snapshot(workspace_id)
        gate_result = GateEvaluator.evaluate_lit_review_exit(snapshot)
    
    elif current_phase == "EXPERIMENTATION":
        gate_name = "experimentation_exit"
        snapshot = gate_activity.gather_experimentation_exit_snapshot(workspace_id)
        gate_result = GateEvaluator.evaluate_experimentation_exit(snapshot)
    
    elif current_phase == "INTERNAL_REVIEW":
        gate_name = "internal_review_exit"
        snapshot = gate_activity.gather_internal_review_exit_snapshot(workspace_id)
        gate_result = GateEvaluator.evaluate_internal_review_exit(snapshot)
    
    else:
        # No gate for this phase
        return {
            "workspace_id": workspace_id,
            "current_phase": current_phase,
            "gate_required": False,
            "can_advance": True
        }
    
    return {
        "workspace_id": workspace_id,
        "current_phase": current_phase,
        "gate_required": True,
        "gate_name": gate_name,
        "gate_status": gate_result["status"],
        "can_advance": gate_result["status"] == "PASS",
        "reasons": gate_result["reasons"],
        "required_actions": gate_result.get("required_actions", [])
    }
