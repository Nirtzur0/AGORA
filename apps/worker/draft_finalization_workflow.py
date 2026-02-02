"""
Draft Finalization Workflow - Component 21

This module implements the Temporal workflow for finalizing draft artifacts.
It orchestrates the finalization gate check and, on success, finalizes the draft.

Per spec §5.6, §4.10, §12.4:
- Finalization is version-pinned (targets specific draft_artifact_version_id)
- Gate checks: citation coverage, citation resolves, critique sufficiency,
  role caps (Skeptic + Method Reviewer if needed), no open blocking critiques
- On success: set draft metadata status=final, emit draft.finalized + workspace.finalized events
- Only the orchestrator can finalize drafts (system authority)
"""

import logging
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from apps.worker.gates import GateEvaluationActivity, GateEvaluator, GateStatus

logger = logging.getLogger(__name__)


@workflow.defn
class DraftFinalizationWorkflow:
    """
    Temporal workflow for finalizing a draft artifact.
    
    This workflow:
    1. Gathers finalization gate snapshot via activity
    2. Evaluates the gate deterministically in the workflow
    3. On PASS: finalizes the draft (set metadata, emit events)
    4. On FAIL/BLOCK: returns error with gate response
    
    Authority: Only the orchestrator can run this workflow.
    """
    
    @workflow.run
    async def run(
        self,
        workspace_id: str,
        draft_artifact_id: str,
        draft_artifact_version_id: str
    ) -> dict:
        """
        Execute the draft finalization workflow.
        
        Args:
            workspace_id: Workspace containing the draft
            draft_artifact_id: ID of the draft artifact to finalize
            draft_artifact_version_id: Specific version to finalize (version-pinned)
        
        Returns:
            dict with:
                - success: bool
                - gate_response: dict with status, reasons, required_actions
                - finalized_version_id: str (if success=True)
        
        Raises:
            ValueError: If IDs don't match or artifact is not a draft
        """
        workflow.logger.info(
            f"Starting draft finalization workflow for workspace {workspace_id}, "
            f"draft {draft_artifact_id}, version {draft_artifact_version_id}"
        )
        
        # Activity retry policy
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=3,
        )
        
        # Step 1: Gather finalization gate snapshot via activity
        workflow.logger.info("Gathering finalization gate snapshot...")
        snapshot = await workflow.execute_activity(
            "gather_finalization_gate_snapshot",
            args=[workspace_id, draft_artifact_id, draft_artifact_version_id],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )
        
        # Step 2: Evaluate gate deterministically (in workflow)
        workflow.logger.info("Evaluating finalization gate...")
        gate_response = GateEvaluator.evaluate_finalization_gate(snapshot)
        
        workflow.logger.info(
            f"Gate evaluation complete: status={gate_response['status']}, "
            f"reasons={gate_response['reasons']}"
        )
        
        # Step 3: Handle gate result
        if gate_response["status"] == GateStatus.PASS.value:
            # Gate passed - finalize the draft
            workflow.logger.info("Gate passed - finalizing draft...")
            
            finalization_result = await workflow.execute_activity(
                "finalize_draft_artifact",
                args=[workspace_id, draft_artifact_id, draft_artifact_version_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )
            
            workflow.logger.info(
                f"Draft finalized successfully: version_id={draft_artifact_version_id}"
            )
            
            return {
                "success": True,
                "gate_response": gate_response,
                "finalized_version_id": draft_artifact_version_id,
                "finalization_timestamp": finalization_result["finalization_timestamp"]
            }
        
        else:
            # Gate failed or blocked
            workflow.logger.warning(
                f"Gate {gate_response['status']}: {gate_response['reasons']}"
            )
            
            return {
                "success": False,
                "gate_response": gate_response,
                "finalized_version_id": None
            }
