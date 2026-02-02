"""
Literature Grounding Workflow (Component 15)

Per spec §5.2, §12.2:
- Workflow template: ingest (pdf_ingest activity) -> assign agent_task -> 
  agent writes claims/evidence + drafts -> citation_check on drafts
- First "prove it works" workflow
- Demonstrates full end-to-end collaboration flow
"""
from typing import Dict, Any
import uuid

from workflow_client import WorkflowClient, create_activity_run, update_activity_run
from database import DBWrapper


async def literature_grounding_workflow(
    workspace_id: str,
    artifact_id: str,
    db: DBWrapper
) -> Dict[str, Any]:
    """
    Execute literature grounding workflow.
    
    Per spec §5.2:
    1. pdf_ingest activity (parse PDF, store text, create artifact_version)
    2. Create agent_task for claim extraction
    3. Agent writes claims/evidence + draft versions (agent-driven)
    4. citation_check runs automatically on draft versions
    
    Args:
        workspace_id: Workspace UUID
        artifact_id: PDF artifact UUID
        db: Database wrapper
    
    Returns:
        Workflow output with artifact_version_id and task_id
    """
    workflow_id = f"literature_grounding_{artifact_id}"
    
    # Start workflow and persist workflow_runs
    client = WorkflowClient()
    workflow_run_id = await client.start_workflow(
        workflow_type="literature_grounding",
        workflow_id=workflow_id,
        task_queue="agora-tasks",
        args={"workspace_id": workspace_id, "artifact_id": artifact_id},
        db=db,
        workspace_id=workspace_id
    )
    
    try:
        # Step 1: Execute pdf_ingest activity
        from pdf_ingest_worker import pdf_ingest_activity
        
        activity_id = f"pdf_ingest_{artifact_id}"
        activity_run_id = create_activity_run(
            db=db,
            workflow_run_id=workflow_run_id,
            activity_type="pdf_ingest",
            activity_id=activity_id,
            input_data={"artifact_id": artifact_id}
        )
        
        # Run pdf_ingest
        ingest_result = await pdf_ingest_activity(artifact_id, db)
        
        update_activity_run(
            db=db,
            activity_run_id=activity_run_id,
            status="completed",
            output={
                "artifact_version_id": ingest_result["artifact_version_id"],
                "pages_parsed": ingest_result["pages_parsed"]
            }
        )
        
        artifact_version_id = ingest_result["artifact_version_id"]
        
        # Step 2: Create agent_task for claim extraction (system-assigned)
        task_id = str(uuid.uuid4())
        
        db.execute(
            """
            INSERT INTO agent_tasks (
                id,
                workspace_id,
                title,
                description,
                task_type,
                target_artifact_id,
                workflow_run_id,
                status
            ) VALUES (
                :id,
                :workspace_id,
                :title,
                :description,
                :task_type,
                :target_artifact_id,
                :workflow_run_id,
                :status
            )
            """,
            {
                "id": task_id,
                "workspace_id": workspace_id,
                "title": "Extract claims from PDF",
                "description": f"Review the parsed PDF (artifact_version {artifact_version_id}) and create claims with evidence",
                "task_type": "extract_claims",
                "target_artifact_id": artifact_id,
                "workflow_run_id": workflow_run_id,
                "status": "pending"
            }
        )
        
        db.commit()
        
        # Step 3 & 4: Agent-driven (agent creates claims/evidence/drafts, citation_check runs automatically)
        # This is handled asynchronously by agents via the API
        
        # Update workflow status
        await client.update_workflow_status(
            workflow_run_id=workflow_run_id,
            status="completed",
            output={
                "artifact_version_id": artifact_version_id,
                "task_id": task_id,
                "message": "PDF ingested and task assigned. Waiting for agent to extract claims."
            },
            db=db
        )
        
        return {
            "workflow_run_id": workflow_run_id,
            "artifact_version_id": artifact_version_id,
            "task_id": task_id
        }
    
    except Exception as e:
        # Update workflow to failed
        await client.update_workflow_status(
            workflow_run_id=workflow_run_id,
            status="failed",
            output={"error": str(e)},
            db=db
        )
        raise
