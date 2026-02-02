"""
Gate Evaluation Logic

Implements spec §5.4 Gates (How Decisions Are Made).

Gates are deterministic predicates over persisted state.
Only the orchestrator evaluates gates.
Gate inputs MUST be gathered via activities (not direct DB queries in workflow code).
"""
from typing import Dict, List, Optional
from enum import Enum
import json


class GateStatus(str, Enum):
    """Gate evaluation status."""
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCK = "BLOCK"


class GateEvaluationActivity:
    """
    Temporal activity for gathering gate evaluation snapshots.
    
    Per spec §5.4: Orchestrator workflow code MUST NOT query Postgres directly.
    Gate inputs MUST be gathered via activities that return a "gate snapshot".
    Gate decisions are computed deterministically from that snapshot.
    """
    
    def __init__(self, db):
        """
        Initialize activity with database connection.
        
        Args:
            db: Database connection wrapper
        """
        self.db = db
    
    def gather_lit_review_exit_snapshot(self, workspace_id: str) -> dict:
        """
        Gather snapshot for LIT_REVIEW exit gate.
        
        Gate criteria per spec §5.4:
        - minimum artifacts ingested OR timebox reached
        - minimum claims extracted with evidence pointers
        - key claims have at least one critique from another agent
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Snapshot dict with all required state
        """
        # Count ingested artifacts
        artifact_count = self.db.execute(
            """
            SELECT COUNT(*)
            FROM artifacts
            WHERE workspace_id = :workspace_id
              AND type IN ('pdf', 'repo', 'dataset')
            """,
            {"workspace_id": workspace_id}
        ).fetchone()[0]
        
        # Count claims with evidence
        claims_with_evidence = self.db.execute(
            """
            SELECT COUNT(DISTINCT c.id)
            FROM claims c
            JOIN claim_evidence ce ON c.id = ce.claim_id
            WHERE c.workspace_id = :workspace_id
            """,
            {"workspace_id": workspace_id}
        ).fetchone()[0]
        
        # Count claims with critiques by different agent
        claims_with_critiques = self.db.execute(
            """
            SELECT COUNT(DISTINCT c.id)
            FROM claims c
            JOIN critiques cr ON cr.target_type = 'claim' AND cr.target_id = c.id
            WHERE c.workspace_id = :workspace_id
              AND cr.critic_agent_id != c.created_by
            """,
            {"workspace_id": workspace_id}
        ).fetchone()[0]
        
        # Get workspace created time for timebox check
        created_at = self.db.execute(
            "SELECT created_at FROM workspaces WHERE id = :id",
            {"id": workspace_id}
        ).fetchone()[0]
        
        return {
            "artifact_count": artifact_count,
            "claims_with_evidence_count": claims_with_evidence,
            "claims_with_critiques_count": claims_with_critiques,
            "workspace_created_at": created_at.isoformat(),
            "snapshot_type": "lit_review_exit"
        }
    
    def gather_experimentation_exit_snapshot(self, workspace_id: str) -> dict:
        """
        Gather snapshot for EXPERIMENTATION exit gate.
        
        Gate criteria per spec §5.4:
        - planned experiment tasks done|deferred
        - each run has log artifact + environment/config captured
        - critical results have method-review critique
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Snapshot dict with all required state
        """
        # Count planned experiment tasks
        total_experiment_tasks = self.db.execute(
            """
            SELECT COUNT(*)
            FROM agent_tasks
            WHERE workspace_id = :workspace_id
              AND task_type IN ('experiment', 'sandbox_run')
            """,
            {"workspace_id": workspace_id}
        ).fetchone()[0]
        
        completed_experiment_tasks = self.db.execute(
            """
            SELECT COUNT(*)
            FROM agent_tasks
            WHERE workspace_id = :workspace_id
              AND task_type IN ('experiment', 'sandbox_run')
              AND status IN ('completed', 'deferred')
            """,
            {"workspace_id": workspace_id}
        ).fetchone()[0]
        
        # Count workflow_runs with log artifacts
        runs_with_logs = self.db.execute(
            """
            SELECT COUNT(DISTINCT wr.id)
            FROM workflow_runs wr
            WHERE wr.workspace_id = :workspace_id
              AND wr.workflow_type = 'code_replication'
              AND EXISTS (
                SELECT 1 FROM artifacts a
                WHERE a.workspace_id = wr.workspace_id
                  AND a.type = 'log'
                  AND a.metadata::text LIKE '%' || wr.id || '%'
              )
            """,
            {"workspace_id": workspace_id}
        ).fetchone()[0]
        
        # Count workflow_runs with critiques
        runs_with_critiques = self.db.execute(
            """
            SELECT COUNT(DISTINCT cr.target_id)
            FROM critiques cr
            WHERE cr.workspace_id = :workspace_id
              AND cr.target_type = 'workflow_run'
            """,
            {"workspace_id": workspace_id}
        ).fetchone()[0]
        
        return {
            "total_experiment_tasks": total_experiment_tasks,
            "completed_experiment_tasks": completed_experiment_tasks,
            "runs_with_logs_count": runs_with_logs,
            "runs_with_critiques_count": runs_with_critiques,
            "snapshot_type": "experimentation_exit"
        }
    
    def gather_internal_review_exit_snapshot(self, workspace_id: str) -> dict:
        """
        Gather snapshot for INTERNAL_REVIEW exit gate (finalization gate).
        
        Gate criteria per spec §5.4, §5.6:
        - no open blocking objections
        - citation coverage PASS
        - critique sufficiency PASS for key claims and current draft version
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Snapshot dict with all required state
        """
        # Count open blocking critiques
        open_blocking_critiques = self.db.execute(
            """
            SELECT COUNT(*)
            FROM critiques
            WHERE workspace_id = :workspace_id
              AND status = 'open'
              AND severity = 'blocking'
            """,
            {"workspace_id": workspace_id}
        ).fetchone()[0]
        
        # Get latest citation_check rule_checks
        citation_checks = self.db.execute(
            """
            SELECT status, details
            FROM rule_checks
            WHERE workspace_id = :workspace_id
              AND rule_type = 'citation_check'
            ORDER BY created_at DESC
            LIMIT 10
            """,
            {"workspace_id": workspace_id}
        ).fetchall()
        
        citation_coverage_pass = all(
            row[0] == 'pass' for row in citation_checks
        ) if citation_checks else False
        
        # Get latest critique_sufficiency rule_checks
        critique_sufficiency_checks = self.db.execute(
            """
            SELECT status, details
            FROM rule_checks
            WHERE workspace_id = :workspace_id
              AND rule_type = 'critique_sufficiency'
            ORDER BY created_at DESC
            LIMIT 10
            """,
            {"workspace_id": workspace_id}
        ).fetchall()
        
        critique_sufficiency_pass = all(
            row[0] == 'pass' for row in critique_sufficiency_checks
        ) if critique_sufficiency_checks else False
        
        # Check role presence (Skeptic required)
        skeptic_present = self.db.execute(
            """
            SELECT COUNT(*)
            FROM workspace_agents wa
            JOIN roles r ON wa.role_id = r.id
            WHERE wa.workspace_id = :workspace_id
              AND wa.status = 'active'
              AND r.name = 'Skeptic'
            """,
            {"workspace_id": workspace_id}
        ).fetchone()[0] > 0
        
        # Check if sandbox runs happened (Method Reviewer required if true)
        sandbox_runs_exist = self.db.execute(
            """
            SELECT COUNT(*)
            FROM activity_runs
            WHERE workspace_id = :workspace_id
              AND activity_type = 'sandbox_run'
            """,
            {"workspace_id": workspace_id}
        ).fetchone()[0] > 0
        
        method_reviewer_present = False
        if sandbox_runs_exist:
            method_reviewer_present = self.db.execute(
                """
                SELECT COUNT(*)
                FROM workspace_agents wa
                JOIN roles r ON wa.role_id = r.id
                WHERE wa.workspace_id = :workspace_id
                  AND wa.status = 'active'
                  AND r.name = 'Method Reviewer'
                """,
                {"workspace_id": workspace_id}
            ).fetchone()[0] > 0
        
        return {
            "open_blocking_critiques_count": open_blocking_critiques,
            "citation_coverage_pass": citation_coverage_pass,
            "critique_sufficiency_pass": critique_sufficiency_pass,
            "skeptic_present": skeptic_present,
            "sandbox_runs_exist": sandbox_runs_exist,
            "method_reviewer_present": method_reviewer_present,
            "citation_checks_count": len(citation_checks),
            "critique_sufficiency_checks_count": len(critique_sufficiency_checks),
            "snapshot_type": "internal_review_exit"
        }


class GateEvaluator:
    """
    Pure functions for deterministic gate evaluation.
    
    These functions receive snapshots (gathered by activities) and return
    deterministic gate decisions. No database access here.
    """
    
    @staticmethod
    def evaluate_lit_review_exit(snapshot: dict) -> dict:
        """
        Evaluate LIT_REVIEW exit gate.
        
        Criteria (v1 minimum):
        - At least 1 artifact ingested
        - At least 1 claim with evidence
        - At least 1 claim with critique from different agent
        
        Args:
            snapshot: Snapshot from gather_lit_review_exit_snapshot
            
        Returns:
            Gate response with status, reasons, required_actions
        """
        reasons = []
        required_actions = []
        
        # Check minimum artifacts
        if snapshot["artifact_count"] < 1:
            reasons.append("No artifacts ingested yet")
            required_actions.append({
                "type": "assign_task",
                "role": "LITERATURE_ANALYST",
                "payload": {"task": "ingest_literature"}
            })
        
        # Check claims with evidence
        if snapshot["claims_with_evidence_count"] < 1:
            reasons.append("No claims with evidence yet")
            required_actions.append({
                "type": "assign_task",
                "role": "LITERATURE_ANALYST",
                "payload": {"task": "extract_claims"}
            })
        
        # Check claims with critiques
        if snapshot["claims_with_critiques_count"] < 1:
            reasons.append("Key claims need critique from another agent")
            required_actions.append({
                "type": "assign_task",
                "role": "SKEPTIC",
                "payload": {"task": "review_claims"}
            })
        
        # Determine status
        if len(reasons) == 0:
            status = GateStatus.PASS
            reasons.append("All LIT_REVIEW exit criteria met")
        else:
            status = GateStatus.FAIL
        
        return {
            "gate_name": "lit_review_exit",
            "status": status.value,
            "reasons": reasons,
            "required_actions": required_actions,
            "snapshot": snapshot
        }
    
    @staticmethod
    def evaluate_experimentation_exit(snapshot: dict) -> dict:
        """
        Evaluate EXPERIMENTATION exit gate.
        
        Criteria (v1 minimum):
        - All experiment tasks completed or deferred
        - At least one workflow run with log artifact
        - At least one run with critique (if critical results exist)
        
        Args:
            snapshot: Snapshot from gather_experimentation_exit_snapshot
            
        Returns:
            Gate response with status, reasons, required_actions
        """
        reasons = []
        required_actions = []
        
        # Check experiment tasks completion
        total = snapshot["total_experiment_tasks"]
        completed = snapshot["completed_experiment_tasks"]
        
        if total > 0 and completed < total:
            reasons.append(f"Experiment tasks incomplete: {completed}/{total}")
            required_actions.append({
                "type": "assign_task",
                "role": "EXPERIMENTALIST",
                "payload": {"task": "complete_experiments"}
            })
        
        # Check runs with logs
        if snapshot["runs_with_logs_count"] < 1:
            reasons.append("No experiment runs with log artifacts yet")
            required_actions.append({
                "type": "assign_task",
                "role": "EXPERIMENTALIST",
                "payload": {"task": "capture_experiment_logs"}
            })
        
        # Check critiques on runs (if runs exist)
        if snapshot["runs_with_logs_count"] > 0 and snapshot["runs_with_critiques_count"] < 1:
            reasons.append("Critical results need method review critique")
            required_actions.append({
                "type": "assign_task",
                "role": "METHOD_REVIEWER",
                "payload": {"task": "review_experiments"}
            })
        
        # Determine status
        if len(reasons) == 0:
            status = GateStatus.PASS
            reasons.append("All EXPERIMENTATION exit criteria met")
        else:
            status = GateStatus.FAIL
        
        return {
            "gate_name": "experimentation_exit",
            "status": status.value,
            "reasons": reasons,
            "required_actions": required_actions,
            "snapshot": snapshot
        }
    
    @staticmethod
    def evaluate_internal_review_exit(snapshot: dict) -> dict:
        """
        Evaluate INTERNAL_REVIEW exit gate (finalization gate).
        
        Criteria per spec §5.6:
        - no open blocking objections
        - citation coverage PASS
        - critique sufficiency PASS
        - role caps PASS (Skeptic + Method Reviewer if needed)
        
        Args:
            snapshot: Snapshot from gather_internal_review_exit_snapshot
            
        Returns:
            Gate response with status, reasons, required_actions
        """
        reasons = []
        required_actions = []
        
        # Check open blocking critiques
        if snapshot["open_blocking_critiques_count"] > 0:
            reasons.append(f"{snapshot['open_blocking_critiques_count']} open blocking critiques")
            required_actions.append({
                "type": "assign_task",
                "role": "SKEPTIC",
                "payload": {"task": "resolve_blocking_critiques"}
            })
        
        # Check citation coverage
        if not snapshot["citation_coverage_pass"]:
            reasons.append("Citation coverage checks not passing")
            required_actions.append({
                "type": "assign_task",
                "role": "SYNTHESIZER",
                "payload": {"task": "fix_citation_coverage"}
            })
        
        # Check critique sufficiency
        if not snapshot["critique_sufficiency_pass"]:
            reasons.append("Critique sufficiency checks not passing")
            required_actions.append({
                "type": "assign_task",
                "role": "SKEPTIC",
                "payload": {"task": "ensure_critique_sufficiency"}
            })
        
        # Check Skeptic presence
        if not snapshot["skeptic_present"]:
            reasons.append("Skeptic role required but not present")
            # This is a BLOCK condition - cannot proceed without role
            status = GateStatus.BLOCK
        
        # Check Method Reviewer presence (if sandbox runs exist)
        if snapshot["sandbox_runs_exist"] and not snapshot["method_reviewer_present"]:
            reasons.append("Method Reviewer required for sandbox runs but not present")
            status = GateStatus.BLOCK
        
        # Determine status (if not already blocked)
        if "status" not in locals():
            if len(reasons) == 0:
                status = GateStatus.PASS
                reasons.append("All INTERNAL_REVIEW exit criteria met - ready for finalization")
            else:
                status = GateStatus.FAIL
        
        return {
            "gate_name": "internal_review_exit",
            "status": status.value,
            "reasons": reasons,
            "required_actions": required_actions,
            "snapshot": snapshot
        }
