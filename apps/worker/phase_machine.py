"""
Workspace Phase State Machine

Implements spec §5.3 Workspace State Machine.

Defines workspace phases, allowed transitions, and transition validation.
Only the orchestrator may advance phases, emitting workspace.phase_changed events.
"""
from enum import Enum
from typing import Dict, List, Optional, Set


class WorkspacePhase(str, Enum):
    """Workspace lifecycle phases per spec §5.3."""
    INIT = "INIT"
    LIT_REVIEW = "LIT_REVIEW"
    CLAIM_VALIDATION = "CLAIM_VALIDATION"
    HYPOTHESIS_PLANNING = "HYPOTHESIS_PLANNING"
    EXPERIMENTATION = "EXPERIMENTATION"
    SYNTHESIS = "SYNTHESIS"
    INTERNAL_REVIEW = "INTERNAL_REVIEW"
    FINALIZED = "FINALIZED"
    ARCHIVED = "ARCHIVED"


# Allowed phase transitions per spec §5.3
ALLOWED_TRANSITIONS: Dict[WorkspacePhase, Set[WorkspacePhase]] = {
    WorkspacePhase.INIT: {
        WorkspacePhase.LIT_REVIEW
    },
    WorkspacePhase.LIT_REVIEW: {
        WorkspacePhase.CLAIM_VALIDATION
    },
    WorkspacePhase.CLAIM_VALIDATION: {
        WorkspacePhase.HYPOTHESIS_PLANNING,
        WorkspacePhase.LIT_REVIEW  # Loopback: missing sources required
    },
    WorkspacePhase.HYPOTHESIS_PLANNING: {
        WorkspacePhase.EXPERIMENTATION
    },
    WorkspacePhase.EXPERIMENTATION: {
        WorkspacePhase.SYNTHESIS
    },
    WorkspacePhase.SYNTHESIS: {
        WorkspacePhase.INTERNAL_REVIEW
    },
    WorkspacePhase.INTERNAL_REVIEW: {
        WorkspacePhase.FINALIZED,
        WorkspacePhase.EXPERIMENTATION  # Loopback: new evidence required
    },
    WorkspacePhase.FINALIZED: {
        WorkspacePhase.ARCHIVED
    },
    WorkspacePhase.ARCHIVED: set()  # Terminal state
}


class PhaseTransitionError(Exception):
    """Raised when an invalid phase transition is attempted."""
    
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class PhaseMachine:
    """
    Workspace phase state machine.
    
    Validates transitions and provides phase advancement logic.
    Only the orchestrator should use this class to advance phases.
    """
    
    @staticmethod
    def is_valid_transition(current_phase: str, next_phase: str) -> bool:
        """
        Check if transition from current_phase to next_phase is allowed.
        
        Args:
            current_phase: Current workspace phase
            next_phase: Target phase to transition to
            
        Returns:
            True if transition is allowed, False otherwise
        """
        try:
            current = WorkspacePhase(current_phase)
            target = WorkspacePhase(next_phase)
        except ValueError:
            return False
        
        return target in ALLOWED_TRANSITIONS.get(current, set())
    
    @staticmethod
    def validate_transition(current_phase: str, next_phase: str) -> None:
        """
        Validate transition and raise error if invalid.
        
        Args:
            current_phase: Current workspace phase
            next_phase: Target phase to transition to
            
        Raises:
            PhaseTransitionError: If transition is not allowed
        """
        if not PhaseMachine.is_valid_transition(current_phase, next_phase):
            raise PhaseTransitionError(
                f"Invalid phase transition: {current_phase} -> {next_phase}"
            )
    
    @staticmethod
    def get_allowed_next_phases(current_phase: str) -> List[str]:
        """
        Get list of allowed next phases from current phase.
        
        Args:
            current_phase: Current workspace phase
            
        Returns:
            List of allowed next phase names
        """
        try:
            current = WorkspacePhase(current_phase)
        except ValueError:
            return []
        
        return [phase.value for phase in ALLOWED_TRANSITIONS.get(current, set())]
    
    @staticmethod
    def is_loopback_transition(current_phase: str, next_phase: str) -> bool:
        """
        Check if transition is an explicit loopback (going backwards).
        
        Explicit loopbacks per spec §5.3:
        - INTERNAL_REVIEW -> EXPERIMENTATION (new evidence required)
        - CLAIM_VALIDATION -> LIT_REVIEW (missing sources required)
        
        Args:
            current_phase: Current workspace phase
            next_phase: Target phase to transition to
            
        Returns:
            True if transition is a loopback, False otherwise
        """
        loopbacks = [
            (WorkspacePhase.INTERNAL_REVIEW, WorkspacePhase.EXPERIMENTATION),
            (WorkspacePhase.CLAIM_VALIDATION, WorkspacePhase.LIT_REVIEW)
        ]
        
        try:
            current = WorkspacePhase(current_phase)
            target = WorkspacePhase(next_phase)
            return (current, target) in loopbacks
        except ValueError:
            return False
    
    @staticmethod
    def is_terminal_phase(phase: str) -> bool:
        """
        Check if phase is a terminal state (no allowed transitions).
        
        Args:
            phase: Workspace phase to check
            
        Returns:
            True if phase is terminal, False otherwise
        """
        try:
            phase_enum = WorkspacePhase(phase)
            return len(ALLOWED_TRANSITIONS.get(phase_enum, set())) == 0
        except ValueError:
            return False


class PhaseAdvancementActivity:
    """
    Temporal activity for advancing workspace phase.
    
    Performs the database update and event emission for phase transitions.
    Should only be called by orchestrator workflows.
    """
    
    def __init__(self, db):
        """
        Initialize activity with database connection.
        
        Args:
            db: Database connection wrapper
        """
        self.db = db
    
    def advance_phase(
        self,
        workspace_id: str,
        next_phase: str,
        gate_summary: dict,
        workflow_run_id: Optional[str] = None
    ) -> dict:
        """
        Advance workspace to next phase.
        
        This is the ONLY method that should change workspace.phase.
        Validates transition, updates database, and emits event.
        
        Args:
            workspace_id: Workspace ID
            next_phase: Target phase to transition to
            gate_summary: Gate evaluation results that triggered transition
            workflow_run_id: ID of orchestrator workflow run (for audit)
            
        Returns:
            Dict with transition details
            
        Raises:
            PhaseTransitionError: If transition is invalid
            ValueError: If workspace not found
        """
        # Get current phase
        row = self.db.execute(
            "SELECT phase FROM workspaces WHERE id = :id",
            {"id": workspace_id}
        ).fetchone()
        
        if not row:
            raise ValueError(f"Workspace not found: {workspace_id}")
        
        current_phase = row[0]
        
        # Validate transition
        PhaseMachine.validate_transition(current_phase, next_phase)
        
        # Update workspace phase
        self.db.execute(
            """
            UPDATE workspaces
            SET phase = :next_phase, updated_at = NOW()
            WHERE id = :workspace_id
            """,
            {"workspace_id": workspace_id, "next_phase": next_phase}
        )
        
        # Emit workspace.phase_changed event
        import json
        import uuid
        
        event_payload = {
            "previous_phase": current_phase,
            "next_phase": next_phase,
            "gate_summary": gate_summary,
            "workflow_run_id": workflow_run_id,
            "is_loopback": PhaseMachine.is_loopback_transition(current_phase, next_phase)
        }
        
        event_id = str(uuid.uuid4())
        self.db.execute(
            """
            INSERT INTO events (
                id, workspace_id, actor_type, actor_id,
                event_type, payload, created_at
            ) VALUES (
                :id, :workspace_id, :actor_type, :actor_id,
                :event_type, :payload, NOW()
            )
            """,
            {
                "id": event_id,
                "workspace_id": workspace_id,
                "actor_type": "system",
                "actor_id": workflow_run_id or "orchestrator",
                "event_type": "workspace.phase_changed",
                "payload": json.dumps(event_payload)
            }
        )
        
        self.db.commit()
        
        return {
            "success": True,
            "previous_phase": current_phase,
            "next_phase": next_phase,
            "event_id": event_id,
            "is_loopback": event_payload["is_loopback"]
        }
    
    def create_required_action_tasks(
        self,
        workspace_id: str,
        required_actions: List[dict],
        workflow_run_id: Optional[str] = None
    ) -> List[str]:
        """
        Create agent_tasks for required actions when gates fail/block.
        
        Args:
            workspace_id: Workspace ID
            required_actions: List of required action specs from gate evaluation
            workflow_run_id: ID of orchestrator workflow run
            
        Returns:
            List of created task IDs
        """
        import json
        import uuid
        
        created_task_ids = []
        
        for action in required_actions:
            action_type = action.get("type")
            if action_type != "assign_task":
                continue
            
            role = action.get("role")
            payload = action.get("payload", {})
            
            # Create agent_task
            task_id = str(uuid.uuid4())
            self.db.execute(
                """
                INSERT INTO agent_tasks (
                    id, workspace_id, role, status, task_type,
                    description, metadata, created_at
                ) VALUES (
                    :id, :workspace_id, :role, :status, :task_type,
                    :description, :metadata, NOW()
                )
                """,
                {
                    "id": task_id,
                    "workspace_id": workspace_id,
                    "role": role,
                    "status": "pending",
                    "task_type": "gate_required_action",
                    "description": f"Required action: {action_type}",
                    "metadata": json.dumps({
                        "action": action,
                        "workflow_run_id": workflow_run_id
                    })
                }
            )
            
            created_task_ids.append(task_id)
        
        self.db.commit()
        
        return created_task_ids
