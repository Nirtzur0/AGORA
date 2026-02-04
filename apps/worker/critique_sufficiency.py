"""
Critique Sufficiency Rule Check Activity (Component 19)

Per spec §5.5 Critique Gate (Sufficiency):
- At least one critique by a different agent
- critique.status is `resolved`, OR status is `deferred` with `deferred_with_rationale`
- High-trust critics MUST resolve (not defer)
- High-trust = agent.reputation >= configured threshold

Generates rule_checks for target entities.
"""
import json
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CritiqueSufficiencyActivity:
    """
    Temporal activity for critique sufficiency rule checking.
    
    Validates that targets have sufficient critique review per spec §5.5.
    """
    
    # High-trust reputation threshold (configurable)
    HIGH_TRUST_REPUTATION = 80.0
    
    def __init__(self, db):
        """
        Initialize critique sufficiency activity.
        
        Args:
            db: Database connection wrapper
        """
        self.db = db
    
    def check_critique_sufficiency(
        self,
        workspace_id: str,
        target_type: str,
        target_id: str,
        target_location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check critique sufficiency for a target.
        
        Per spec §5.5:
        - At least one critique by a different agent
        - Critique is resolved OR deferred with rationale
        - High-trust critics cannot defer
        
        Args:
            workspace_id: Workspace UUID
            target_type: Target type (claim, workflow_run, artifact_version)
            target_id: Target UUID
            target_location: Optional location within target
            
        Returns:
            Dict with status, details, and rule_check_id
        """
        logger.info(f"Checking critique sufficiency for {target_type} {target_id}")
        
        # Get target author
        target_author_id = self._get_target_author(target_type, target_id)
        
        # Get all critiques for target
        critiques = self._get_critiques(
            workspace_id=workspace_id,
            target_type=target_type,
            target_id=target_id,
            target_location=target_location
        )
        
        # Filter critiques by different agents
        if target_author_id:
            critiques = [c for c in critiques if c["critic_agent_id"] != target_author_id]
        
        # Check sufficiency
        result = self._evaluate_sufficiency(critiques, workspace_id)
        
        # Write rule_check
        rule_check_id = self._write_rule_check(
            workspace_id=workspace_id,
            target_type=target_type,
            target_id=target_id,
            target_location=target_location,
            status=result["status"],
            details=result["details"]
        )
        
        return {
            "rule_check_id": rule_check_id,
            "status": result["status"],
            "details": result["details"],
            "critique_count": len(critiques),
            "high_trust_violations": result.get("high_trust_violations", [])
        }
    
    def _get_target_author(self, target_type: str, target_id: str) -> Optional[str]:
        """Get the author/creator of a target."""
        if target_type == "claim":
            result = self.db.execute(
                "SELECT created_by FROM claims WHERE id = :id",
                {"id": target_id}
            ).fetchone()
        elif target_type == "artifact_version":
            result = self.db.execute(
                "SELECT created_by FROM artifact_versions WHERE id = :id",
                {"id": target_id}
            ).fetchone()
        elif target_type == "workflow_run":
            # Workflow runs don't have a single author
            return None
        else:
            return None
        
        return result[0] if result else None
    
    def _get_critiques(
        self,
        workspace_id: str,
        target_type: str,
        target_id: str,
        target_location: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Get all critiques for a target."""
        query = """
            SELECT 
                c.id,
                c.critic_agent_id,
                c.status,
                c.severity,
                c.message,
                c.resolution,
                c.created_at,
                a.reputation
            FROM critiques c
            JOIN agents a ON c.critic_agent_id = a.id
            WHERE c.workspace_id = :workspace_id
              AND c.target_type = :target_type
              AND c.target_id = :target_id
        """
        
        params = {
            "workspace_id": workspace_id,
            "target_type": target_type,
            "target_id": target_id
        }
        
        if target_location:
            query += " AND c.target_location = :target_location"
            params["target_location"] = target_location
        
        rows = self.db.execute(query, params).fetchall()
        
        critiques = []
        for row in rows:
            resolution = row[5]
            if isinstance(resolution, str):
                resolution = json.loads(resolution)
            critiques.append(
                {
                    "id": row[0],
                    "critic_agent_id": row[1],
                    "status": row[2],
                    "severity": row[3],
                    "message": row[4],
                    "resolution": resolution if resolution else None,
                    "created_at": row[6],
                    "critic_reputation": row[7] or 0.0,
                }
            )
        return critiques
    
    def _evaluate_sufficiency(
        self,
        critiques: List[Dict[str, Any]],
        workspace_id: str
    ) -> Dict[str, Any]:
        """
        Evaluate critique sufficiency per spec §5.5.
        
        Returns:
            Dict with status ("pass"/"fail") and details
        """
        if not critiques:
            return {
                "status": "fail",
                "details": {
                    "reason": "no_critiques",
                    "message": "No critiques from other agents found"
                }
            }
        
        # Check each critique
        valid_critiques = []
        high_trust_violations = []
        
        for critique in critiques:
            status = critique["status"]
            resolution = critique["resolution"] or {}
            reputation = critique["critic_reputation"]
            is_high_trust = reputation >= self.HIGH_TRUST_REPUTATION
            
            # Check if critique is valid
            if status == "resolved":
                valid_critiques.append(critique)
            elif status == "deferred":
                # Check if high-trust critic deferred (violation)
                if is_high_trust:
                    high_trust_violations.append({
                        "critique_id": critique["id"],
                        "critic_reputation": reputation,
                        "reason": "High-trust critic cannot defer"
                    })
                # Check if deferred with rationale
                elif resolution.get("status") == "deferred_with_rationale":
                    valid_critiques.append(critique)
        
        # If high-trust violations exist, fail
        if high_trust_violations:
            return {
                "status": "fail",
                "details": {
                    "reason": "high_trust_deferral",
                    "message": f"High-trust critics cannot defer critiques ({len(high_trust_violations)} violations)",
                    "violations": high_trust_violations
                },
                "high_trust_violations": high_trust_violations
            }
        
        # Check if at least one valid critique exists
        if not valid_critiques:
            return {
                "status": "fail",
                "details": {
                    "reason": "no_valid_critiques",
                    "message": "No resolved or properly deferred critiques found",
                    "total_critiques": len(critiques),
                    "critique_statuses": [c["status"] for c in critiques]
                }
            }
        
        # Pass: at least one valid critique exists
        return {
            "status": "pass",
            "details": {
                "valid_critique_count": len(valid_critiques),
                "total_critique_count": len(critiques),
                "critique_ids": [c["id"] for c in valid_critiques]
            }
        }
    
    def _write_rule_check(
        self,
        workspace_id: str,
        target_type: str,
        target_id: str,
        target_location: Optional[str],
        status: str,
        details: Dict[str, Any]
    ) -> str:
        """Write rule_check record."""
        rule_check_id = str(uuid.uuid4())
        
        self.db.execute(
            """
            INSERT INTO rule_checks (
                id, workspace_id, rule_name, target_type, target_id, target_location,
                status, details, created_at
            ) VALUES (
                :id, :workspace_id, :rule_name, :target_type, :target_id, :target_location,
                :status, :details, NOW()
            )
            """,
            {
                "id": rule_check_id,
                "workspace_id": workspace_id,
                "rule_name": "critique_sufficiency",
                "target_type": target_type,
                "target_id": target_id,
                "target_location": target_location,
                "status": status,
                "details": json.dumps(details, default=str)
            }
        )
        
        self.db.commit()
        
        logger.info(f"Created rule_check {rule_check_id} with status {status}")
        
        return rule_check_id
    
    def check_workspace_critique_sufficiency(
        self,
        workspace_id: str,
        target_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check critique sufficiency for all targets in workspace.
        
        Args:
            workspace_id: Workspace UUID
            target_type: Optional filter for target type
            
        Returns:
            Dict with overall status and per-target results
        """
        # Get all unique targets that have critiques
        query = """
            SELECT DISTINCT target_type, target_id, target_location
            FROM critiques
            WHERE workspace_id = :workspace_id
        """
        
        params = {"workspace_id": workspace_id}
        
        if target_type:
            query += " AND target_type = :target_type"
            params["target_type"] = target_type
        
        targets = self.db.execute(query, params).fetchall()
        
        results = []
        fail_count = 0
        
        for target_row in targets:
            t_type, t_id, t_location = target_row
            
            result = self.check_critique_sufficiency(
                workspace_id=workspace_id,
                target_type=t_type,
                target_id=t_id,
                target_location=t_location
            )
            
            results.append({
                "target_type": t_type,
                "target_id": t_id,
                "target_location": t_location,
                "status": result["status"],
                "details": result["details"]
            })
            
            if result["status"] == "fail":
                fail_count += 1
        
        overall_status = "pass" if fail_count == 0 else "fail"
        
        return {
            "workspace_id": workspace_id,
            "overall_status": overall_status,
            "total_targets": len(results),
            "passed": len(results) - fail_count,
            "failed": fail_count,
            "results": results
        }
