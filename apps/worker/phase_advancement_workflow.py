"""
Phase Advancement Workflow

Implements orchestrator-driven phase transitions per spec §5.3, §5.4.

This is a Temporal workflow that:
1. Gathers gate evaluation snapshot via activity
2. Evaluates gate deterministically
3. If PASS: advances phase via activity and emits event
4. If FAIL: creates required action tasks
5. If BLOCK: creates required action tasks and blocks progression
"""
from temporalio import workflow
from temporalio.common import RetryPolicy
from datetime import timedelta
from typing import Optional


@workflow.defn
class PhaseAdvancementWorkflow:
    """
    Orchestrator workflow for workspace phase advancement.
    
    Only this workflow (system authority) may advance workspace phases.
    Agents cannot directly change phases.
    """
    
    @workflow.run
    async def run(
        self,
        workspace_id: str,
        target_phase: str,
        reason: Optional[str] = None
    ) -> dict:
        """
        Attempt to advance workspace to target phase.
        
        Args:
            workspace_id: Workspace ID
            target_phase: Desired target phase
            reason: Optional reason for advancement (e.g., "user request", "timebox reached")
            
        Returns:
            Dict with advancement result:
            {
                "success": bool,
                "current_phase": str,
                "target_phase": str,
                "gate_result": dict,
                "event_id": str (if success)
            }
        """
        workflow.logger.info(
            f"Phase advancement workflow started",
            extra={
                "workspace_id": workspace_id,
                "target_phase": target_phase,
                "reason": reason
            }
        )
        
        # Get current phase via activity
        current_phase_result = await workflow.execute_activity(
            "get_workspace_phase",
            args=[workspace_id],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1)
            )
        )
        
        current_phase = current_phase_result["phase"]
        
        # Validate transition
        transition_valid = await workflow.execute_activity(
            "validate_phase_transition",
            args=[current_phase, target_phase],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1)
        )
        
        if not transition_valid["valid"]:
            workflow.logger.error(
                f"Invalid phase transition: {current_phase} -> {target_phase}",
                extra={"error": transition_valid.get("error")}
            )
            return {
                "success": False,
                "current_phase": current_phase,
                "target_phase": target_phase,
                "error": transition_valid.get("error")
            }
        
        # Determine which gate to evaluate based on current phase
        gate_name = self._get_exit_gate_name(current_phase)
        
        if gate_name:
            # Gather gate snapshot via activity
            workflow.logger.info(f"Gathering snapshot for gate: {gate_name}")
            
            snapshot = await workflow.execute_activity(
                f"gather_{gate_name}_snapshot",
                args=[workspace_id],
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1)
                )
            )
            
            # Evaluate gate deterministically (in workflow, not activity)
            workflow.logger.info(f"Evaluating gate: {gate_name}")
            gate_result = self._evaluate_gate(gate_name, snapshot)
            
            workflow.logger.info(
                f"Gate evaluation result: {gate_result['status']}",
                extra={"reasons": gate_result["reasons"]}
            )
            
            # Handle gate result
            if gate_result["status"] == "PASS":
                # Advance phase via activity
                advancement_result = await workflow.execute_activity(
                    "advance_workspace_phase",
                    args=[workspace_id, target_phase, gate_result, workflow.info().run_id],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(
                        maximum_attempts=3,
                        initial_interval=timedelta(seconds=1)
                    )
                )
                
                workflow.logger.info(
                    f"Phase advanced successfully",
                    extra={
                        "previous_phase": advancement_result["previous_phase"],
                        "next_phase": advancement_result["next_phase"],
                        "event_id": advancement_result["event_id"]
                    }
                )
                
                return {
                    "success": True,
                    "current_phase": current_phase,
                    "target_phase": target_phase,
                    "gate_result": gate_result,
                    "event_id": advancement_result["event_id"]
                }
            
            else:
                # Gate failed or blocked - create required action tasks
                if gate_result.get("required_actions"):
                    workflow.logger.info(
                        f"Creating required action tasks",
                        extra={"count": len(gate_result["required_actions"])}
                    )
                    
                    task_ids = await workflow.execute_activity(
                        "create_required_action_tasks",
                        args=[
                            workspace_id,
                            gate_result["required_actions"],
                            workflow.info().run_id
                        ],
                        start_to_close_timeout=timedelta(seconds=60),
                        retry_policy=RetryPolicy(
                            maximum_attempts=3,
                            initial_interval=timedelta(seconds=1)
                        )
                    )
                    
                    gate_result["created_task_ids"] = task_ids
                
                workflow.logger.warning(
                    f"Phase advancement blocked by gate",
                    extra={
                        "gate_status": gate_result["status"],
                        "reasons": gate_result["reasons"]
                    }
                )
                
                return {
                    "success": False,
                    "current_phase": current_phase,
                    "target_phase": target_phase,
                    "gate_result": gate_result,
                    "blocked": True
                }
        
        else:
            # No gate required for this transition (e.g., INIT -> LIT_REVIEW)
            workflow.logger.info("No gate evaluation required for this transition")
            
            gate_result = {
                "gate_name": "no_gate",
                "status": "PASS",
                "reasons": ["No gate required for this transition"]
            }
            
            # Advance phase via activity
            advancement_result = await workflow.execute_activity(
                "advance_workspace_phase",
                args=[workspace_id, target_phase, gate_result, workflow.info().run_id],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1)
                )
            )
            
            return {
                "success": True,
                "current_phase": current_phase,
                "target_phase": target_phase,
                "gate_result": gate_result,
                "event_id": advancement_result["event_id"]
            }
    
    def _get_exit_gate_name(self, phase: str) -> Optional[str]:
        """
        Get exit gate name for a phase.
        
        Args:
            phase: Current workspace phase
            
        Returns:
            Gate name or None if no gate required
        """
        gate_map = {
            "LIT_REVIEW": "lit_review_exit",
            "EXPERIMENTATION": "experimentation_exit",
            "INTERNAL_REVIEW": "internal_review_exit"
        }
        return gate_map.get(phase)
    
    def _evaluate_gate(self, gate_name: str, snapshot: dict) -> dict:
        """
        Evaluate gate deterministically from snapshot.
        
        This runs in the workflow (not an activity) so it's deterministic
        and replayable.
        
        Args:
            gate_name: Name of gate to evaluate
            snapshot: Snapshot gathered by activity
            
        Returns:
            Gate evaluation result
        """
        # Import evaluator (import in workflow is deterministic)
        from gates import GateEvaluator
        
        if gate_name == "lit_review_exit":
            return GateEvaluator.evaluate_lit_review_exit(snapshot)
        elif gate_name == "experimentation_exit":
            return GateEvaluator.evaluate_experimentation_exit(snapshot)
        elif gate_name == "internal_review_exit":
            return GateEvaluator.evaluate_internal_review_exit(snapshot)
        else:
            return {
                "gate_name": gate_name,
                "status": "FAIL",
                "reasons": [f"Unknown gate: {gate_name}"],
                "required_actions": []
            }
