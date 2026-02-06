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

from agent_tasks import RoleName, TaskStatus


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
        - planned experiment tasks completed|blocked
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
              AND type IN ('experiment', 'sandbox_run')
            """,
            {"workspace_id": workspace_id}
        ).fetchone()[0]
        
        completed_experiment_tasks = self.db.execute(
            """
            SELECT COUNT(*)
            FROM agent_tasks
            WHERE workspace_id = :workspace_id
              AND type IN ('experiment', 'sandbox_run')
              AND status IN (:status_completed, :status_blocked)
            """,
            {
                "workspace_id": workspace_id,
                "status_completed": TaskStatus.COMPLETED.value,
                "status_blocked": TaskStatus.BLOCKED.value,
            }
        ).fetchone()[0]
        
        # Count workflow_runs with log artifacts (code_replication or sandbox_run)
        runs_with_logs = self.db.execute(
            """
            SELECT COUNT(DISTINCT wr.id)
            FROM workflow_runs wr
            WHERE wr.workspace_id = :workspace_id
              AND wr.workflow_type IN ('code_replication', 'sandbox_run')
              AND EXISTS (
                SELECT 1 FROM artifacts a
                WHERE a.workspace_id = wr.workspace_id
                  AND a.type = 'log'
                  AND (
                    a.metadata->>'workflow_run_id' = wr.id::text
                    OR a.metadata::text LIKE '%' || wr.id || '%'
                  )
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
              AND rule_name = 'citation_check'
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
              AND rule_name = 'critique_sufficiency'
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
            FROM activity_runs ar
            JOIN workflow_runs wr ON ar.workflow_run_id = wr.id
            WHERE wr.workspace_id = :workspace_id
              AND ar.activity_type = 'sandbox_run'
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

    def gather_finalization_gate_snapshot(
        self,
        workspace_id: str,
        draft_artifact_id: str,
        draft_artifact_version_id: str
    ) -> dict:
        """
        Gather snapshot for finalization gate.

        Per spec §5.6:
        - citation_check passes (coverage + resolves)
        - critique_sufficiency passes for the target draft version
        - no open blocking critiques for the target draft version
        - Skeptic present
        - Method Reviewer present if sandbox runs exist
        - finalization targets an explicit draft artifact version (version-pinned)
        """
        # Verify draft artifact and version match
        artifact_row = self.db.execute(
            """
            SELECT id, type, metadata
            FROM artifacts
            WHERE id = :id AND workspace_id = :workspace_id
            """,
            {"id": draft_artifact_id, "workspace_id": workspace_id}
        ).fetchone()

        if not artifact_row or artifact_row[1] != "draft":
            raise ValueError(f"Draft artifact not found or wrong type: {draft_artifact_id}")

        version_row = self.db.execute(
            """
            SELECT id, artifact_id, content_hash, created_by
            FROM artifact_versions
            WHERE id = :id AND artifact_id = :artifact_id
            """,
            {"id": draft_artifact_version_id, "artifact_id": draft_artifact_id}
        ).fetchone()

        if not version_row:
            raise ValueError(
                f"Draft version not found or doesn't match artifact: "
                f"{draft_artifact_version_id} vs {draft_artifact_id}"
            )

        content_hash = version_row[2]
        draft_author = version_row[3]

        # Latest citation_check rule_checks for this draft version
        citation_checks = self.db.execute(
            """
            SELECT status, details
            FROM rule_checks
            WHERE workspace_id = :workspace_id
              AND rule_name = 'citation_check'
              AND target_id = :version_id
            ORDER BY created_at DESC
            LIMIT 5
            """,
            {"workspace_id": workspace_id, "version_id": draft_artifact_version_id}
        ).fetchall()

        citation_coverage_pass = all(
            row[0] == 'pass' for row in citation_checks
        ) if citation_checks else False

        citation_resolves_pass = True
        if citation_checks:
            for row in citation_checks:
                details = row[1] or {}
                if isinstance(details, str):
                    details = json.loads(details)
                if not details.get("all_citations_resolve", True):
                    citation_resolves_pass = False
                    break

        # Latest critique_sufficiency checks for this draft version
        critique_sufficiency_checks = self.db.execute(
            """
            SELECT status, details
            FROM rule_checks
            WHERE workspace_id = :workspace_id
              AND rule_name = 'critique_sufficiency'
              AND target_id = :version_id
            ORDER BY created_at DESC
            LIMIT 5
            """,
            {"workspace_id": workspace_id, "version_id": draft_artifact_version_id}
        ).fetchall()

        critique_sufficiency_pass = all(
            row[0] == 'pass' for row in critique_sufficiency_checks
        ) if critique_sufficiency_checks else False

        # Open blocking critiques targeting the draft version
        open_blocking_critiques = self.db.execute(
            """
            SELECT COUNT(*)
            FROM critiques
            WHERE workspace_id = :workspace_id
              AND target_type = 'artifact_version'
              AND target_id = :version_id
              AND status = 'open'
              AND severity = 'blocking'
            """,
            {"workspace_id": workspace_id, "version_id": draft_artifact_version_id}
        ).fetchone()[0]

        # Skeptic required
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

        # If sandbox runs happened, Method Reviewer is required
        sandbox_runs_exist = self.db.execute(
            """
            SELECT COUNT(*)
            FROM activity_runs ar
            JOIN workflow_runs wr ON ar.workflow_run_id = wr.id
            WHERE wr.workspace_id = :workspace_id
              AND ar.activity_type = 'sandbox_run'
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
            "draft_artifact_id": draft_artifact_id,
            "draft_artifact_version_id": draft_artifact_version_id,
            "content_hash": content_hash,
            "draft_author": draft_author,
            "citation_coverage_pass": citation_coverage_pass,
            "citation_resolves_pass": citation_resolves_pass,
            "critique_sufficiency_pass": critique_sufficiency_pass,
            "open_blocking_critiques_count": open_blocking_critiques,
            "skeptic_present": skeptic_present,
            "sandbox_runs_exist": sandbox_runs_exist,
            "method_reviewer_present": method_reviewer_present,
            "citation_coverage_checks_count": len(citation_checks),
            "critique_sufficiency_checks_count": len(critique_sufficiency_checks),
            "snapshot_type": "finalization_gate"
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
                "role": RoleName.LITERATURE_ANALYST.value,
                "payload": {"task": "ingest_literature"}
            })
        
        # Check claims with evidence
        if snapshot["claims_with_evidence_count"] < 1:
            reasons.append("No claims with evidence yet")
            required_actions.append({
                "type": "assign_task",
                "role": RoleName.LITERATURE_ANALYST.value,
                "payload": {"task": "extract_claims"}
            })
        
        # Check claims with critiques
        if snapshot["claims_with_critiques_count"] < 1:
            reasons.append("Key claims need critique from another agent")
            required_actions.append({
                "type": "assign_task",
                "role": RoleName.SKEPTIC.value,
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
        - All experiment tasks completed or blocked
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
                "role": RoleName.EXPERIMENTALIST.value,
                "payload": {"task": "complete_experiments"}
            })
        
        # Check runs with logs
        if snapshot["runs_with_logs_count"] < 1:
            reasons.append("No experiment runs with log artifacts yet")
            required_actions.append({
                "type": "assign_task",
                "role": RoleName.EXPERIMENTALIST.value,
                "payload": {"task": "capture_experiment_logs"}
            })
        
        # Check critiques on runs (if runs exist)
        if snapshot["runs_with_logs_count"] > 0 and snapshot["runs_with_critiques_count"] < 1:
            reasons.append("Critical results need method review critique")
            required_actions.append({
                "type": "assign_task",
                "role": RoleName.METHOD_REVIEWER.value,
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
                "role": RoleName.SKEPTIC.value,
                "payload": {"task": "resolve_blocking_critiques"}
            })
        
        # Check citation coverage
        if not snapshot["citation_coverage_pass"]:
            reasons.append("Citation coverage checks not passing")
            required_actions.append({
                "type": "assign_task",
                "role": RoleName.SYNTHESIZER.value,
                "payload": {"task": "fix_citation_coverage"}
            })
        
        # Check critique sufficiency
        if not snapshot["critique_sufficiency_pass"]:
            reasons.append("Critique sufficiency checks not passing")
            required_actions.append({
                "type": "assign_task",
                "role": RoleName.SKEPTIC.value,
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
    
    @staticmethod
    def evaluate_finalization_gate(snapshot: dict) -> dict:
        """
        Deterministic evaluation of finalization gate per spec §5.6.
        
        Gate criteria (all must succeed):
        1. Citation coverage check passes
        2. Citation resolves check passes
        3. Critique sufficiency check passes
        4. No open blocking critiques
        5. Skeptic present
        6. Method Reviewer present (if sandbox runs exist)
        
        Returns gate response with status PASS/FAIL/BLOCK and reasons.
        """
        reasons = []
        required_actions = []
        status = GateStatus.PASS
        
        # Check citation coverage
        if not snapshot.get("citation_coverage_pass", False):
            reasons.append("Citation coverage check failed")
            required_actions.append({
                "type": "add_citations",
                "description": "Add citations to cover all claims in the draft"
            })
            status = GateStatus.FAIL
        
        # Check citation resolves
        if not snapshot.get("citation_resolves_pass", False):
            reasons.append("Citation resolve check failed")
            required_actions.append({
                "type": "fix_citations",
                "description": "Ensure all citations resolve to valid artifact versions"
            })
            status = GateStatus.FAIL
        
        # Check critique sufficiency
        if not snapshot.get("critique_sufficiency_pass", False):
            reasons.append("Critique sufficiency check failed")
            required_actions.append({
                "type": "address_critiques",
                "description": "Address or respond to all critiques"
            })
            status = GateStatus.FAIL
        
        # Check open blocking critiques
        blocking_count = snapshot.get("open_blocking_critiques_count", 0)
        if blocking_count > 0:
            reasons.append(f"{blocking_count} open blocking critique(s) remain")
            required_actions.append({
                "type": "resolve_blocking_critiques",
                "description": f"Resolve {blocking_count} open blocking critique(s)",
                "count": blocking_count
            })
            status = GateStatus.BLOCK
        
        # Check Skeptic presence (required)
        if not snapshot.get("skeptic_present", False):
            reasons.append("Skeptic role not assigned")
            required_actions.append({
                "type": "assign_skeptic",
                "description": "Assign a Skeptic to the workspace"
            })
            # Block because this is a structural requirement
            status = GateStatus.BLOCK
        
        # Check Method Reviewer presence (if sandbox runs exist)
        sandbox_runs_exist = snapshot.get("sandbox_runs_exist", False)
        method_reviewer_present = snapshot.get("method_reviewer_present", False)
        if sandbox_runs_exist and not method_reviewer_present:
            reasons.append("Method Reviewer required when sandbox runs exist")
            required_actions.append({
                "type": "assign_method_reviewer",
                "description": "Assign a Method Reviewer to review sandbox executions"
            })
            # Block because this is a structural requirement
            status = GateStatus.BLOCK
        
        # If all checks pass
        if not reasons:
            reasons.append("All finalization criteria met")
        
        return {
            "gate_name": "finalization",
            "status": status.value,
            "reasons": reasons,
            "required_actions": required_actions,
            "snapshot": snapshot
        }
