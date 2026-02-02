"""
Temporal Workflow Client (Component 14)

Per spec §4.12, §5.1:
- Core API can start workflows and persist workflow_runs
- Workflow states: running -> completed|failed|canceled
- Workflow types: literature_grounding, code_replication, draft_finalization
- Activity retries handled by Temporal retry policies
"""
from temporalio.client import Client
from typing import Optional, Dict, Any
import uuid
from datetime import datetime

from database import DBWrapper


class WorkflowClient:
    """Client for starting and managing Temporal workflows."""
    
    def __init__(self, temporal_address: str = "localhost:7233"):
        """
        Initialize Temporal client.
        
        Args:
            temporal_address: Temporal server address
        """
        self.temporal_address = temporal_address
        self._client: Optional[Client] = None
    
    async def connect(self):
        """Connect to Temporal server."""
        if not self._client:
            self._client = await Client.connect(self.temporal_address)
    
    async def start_workflow(
        self,
        workflow_type: str,
        workflow_id: str,
        task_queue: str,
        args: Dict[str, Any],
        db: DBWrapper,
        workspace_id: str
    ) -> str:
        """
        Start a Temporal workflow and persist workflow_runs record.
        
        Per spec §4.12: POST /workflows (internal only)
        
        Args:
            workflow_type: Type of workflow (literature_grounding, code_replication, etc.)
            workflow_id: Unique workflow ID
            task_queue: Temporal task queue name
            args: Workflow arguments
            db: Database wrapper
            workspace_id: Workspace ID
        
        Returns:
            workflow_run_id: UUID of created workflow_run record
        """
        await self.connect()
        
        # Create workflow_runs record
        workflow_run_id = str(uuid.uuid4())
        
        import json
        db.execute(
            """
            INSERT INTO workflow_runs (
                id,
                workspace_id,
                workflow_type,
                workflow_id,
                status,
                input
            ) VALUES (
                :id,
                :workspace_id,
                :workflow_type,
                :workflow_id,
                :status,
                :input
            )
            """,
            {
                "id": workflow_run_id,
                "workspace_id": workspace_id,
                "workflow_type": workflow_type,
                "workflow_id": workflow_id,
                "status": "running",
                "input": json.dumps(args)
            }
        )
        
        db.commit()
        
        # Start Temporal workflow (would call actual Temporal API in production)
        # For MVP, we record the workflow_run and return
        # In production: await self._client.start_workflow(...)
        
        return workflow_run_id
    
    async def update_workflow_status(
        self,
        workflow_run_id: str,
        status: str,
        output: Optional[Dict[str, Any]],
        db: DBWrapper
    ):
        """
        Update workflow_runs status.
        
        Args:
            workflow_run_id: UUID of workflow_run
            status: New status (completed, failed, canceled)
            output: Optional workflow output
            db: Database wrapper
        """
        import json
        output_json = json.dumps(output) if output else None
        
        db.execute(
            """
            UPDATE workflow_runs
            SET status = :status,
                output = :output,
                completed_at = CURRENT_TIMESTAMP
            WHERE id = :id
            """,
            {
                "id": workflow_run_id,
                "status": status,
                "output": output_json
            }
        )
        
        db.commit()


def create_activity_run(
    db: DBWrapper,
    workflow_run_id: str,
    activity_type: str,
    activity_id: str,
    input_data: Dict[str, Any]
) -> str:
    """
    Create activity_runs record when activity starts.
    
    Per spec §4.12: Worker persists activity_runs as activities execute.
    
    Args:
        db: Database wrapper
        workflow_run_id: Parent workflow_run ID
        activity_type: Type of activity (pdf_ingest, citation_check, etc.)
        activity_id: Unique activity ID
        input_data: Activity input
    
    Returns:
        activity_run_id: UUID of created activity_run record
    """
    activity_run_id = str(uuid.uuid4())
    
    import json
    db.execute(
        """
        INSERT INTO activity_runs (
            id,
            workflow_run_id,
            activity_type,
            activity_id,
            status,
            input
        ) VALUES (
            :id,
            :workflow_run_id,
            :activity_type,
            :activity_id,
            :status,
            :input
        )
        """,
        {
            "id": activity_run_id,
            "workflow_run_id": workflow_run_id,
            "activity_type": activity_type,
            "activity_id": activity_id,
            "status": "running",
            "input": json.dumps(input_data)
        }
    )
    
    db.commit()
    return activity_run_id


def update_activity_run(
    db: DBWrapper,
    activity_run_id: str,
    status: str,
    output: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None
):
    """
    Update activity_runs status when activity completes.
    
    Args:
        db: Database wrapper
        activity_run_id: UUID of activity_run
        status: New status (completed, failed)
        output: Optional activity output
        error: Optional error message if failed
    """
    import json
    output_json = json.dumps(output) if output else None
    
    db.execute(
        """
        UPDATE activity_runs
        SET status = :status,
            output = :output,
            error = :error,
            completed_at = CURRENT_TIMESTAMP
        WHERE id = :id
        """,
        {
            "id": activity_run_id,
            "status": status,
            "output": output_json,
            "error": error
        }
    )
    
    db.commit()
