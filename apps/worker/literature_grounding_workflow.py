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
from agent_tasks import TaskPayload, TaskInput, RoleName, TaskStatus, TaskPriority
from queries.agent_tasks import insert_agent_task
from storage import create_storage_from_env
from pdf_ingest import PDFIngestActivity


async def literature_grounding_workflow(
    workspace_id: str,
    artifact_id: str,
    db: DBWrapper,
    created_by: str
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
        # Step 1: Execute pdf_ingest activity (synchronously for MVP)
        activity_id = f"pdf_ingest_{artifact_id}"
        activity_run_id = create_activity_run(
            db=db,
            workflow_run_id=workflow_run_id,
            activity_type="pdf_ingest",
            activity_id=activity_id,
            input_data={"artifact_id": artifact_id}
        )
        
        # Load latest PDF bytes from storage
        version_row = db.execute(
            """
            SELECT storage_uri
            FROM artifact_versions
            WHERE artifact_id = :artifact_id
            ORDER BY version DESC
            LIMIT 1
            """,
            {"artifact_id": artifact_id}
        ).fetchone()
        
        if not version_row:
            raise ValueError(f"No artifact_versions found for PDF artifact {artifact_id}")
        
        storage_uri = version_row[0]
        storage = create_storage_from_env()
        pdf_bytes = storage.get_object(storage_uri).read()
        
        pdf_activity = PDFIngestActivity(storage, db)
        ingest_result = pdf_activity.ingest_pdf(
            artifact_id=artifact_id,
            workspace_id=workspace_id,
            pdf_bytes=pdf_bytes,
            created_by=created_by,
            activity_run_id=activity_run_id
        )
        
        update_activity_run(
            db=db,
            activity_run_id=activity_run_id,
            status="completed",
            output={
                "artifact_version_id": ingest_result["artifact_version_id"],
                "pages_parsed": ingest_result.get("page_count")
            }
        )
        
        artifact_version_id = ingest_result["artifact_version_id"]
        
        # Step 2: Create agent_task for claim extraction (system-assigned)
        task_id = str(uuid.uuid4())
        
        task_payload = TaskPayload(
            objective="Extract claims from the PDF and add evidence.",
            inputs=[
                TaskInput(
                    artifact_version_id=artifact_version_id,
                    label="Parsed PDF"
                )
            ],
            required_outputs=[
                "claim.create",
                "claim.evidence.add",
                "draft.version.create"
            ],
            context_links=[
                {"type": "artifact", "id": artifact_id}
            ],
            acceptance_criteria=[
                "At least 2 claims created with evidence pointers",
                "A draft version created with citations"
            ],
            priority=TaskPriority.HIGH.value,
            workflow_run_id=workflow_run_id,
            assignee_role=RoleName.LITERATURE_ANALYST.value
        ).model_dump()

        insert_agent_task(
            db,
            task_id=task_id,
            workspace_id=workspace_id,
            assignee_agent_id=None,
            task_type="extract_claims",
            status=TaskStatus.OPEN.value,
            payload=task_payload,
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
