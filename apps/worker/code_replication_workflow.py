"""
Code Replication Workflow (Component 18)

Per spec §5.2, §12.3:
- Workflow template: repo_ingest -> sandbox_run -> assign agent_task -> 
  agent writes draft citing log -> citation_check on draft
- Second "prove it works" workflow (Workflow B)
- Demonstrates code execution + evidence capture + citation flow
"""
from typing import Dict, Any, Optional
import uuid
import json

from workflow_client import WorkflowClient, create_activity_run, update_activity_run
from database import DBWrapper
from agent_tasks import TaskPayload, TaskInput, RoleName, TaskStatus, TaskPriority
from queries.agent_tasks import insert_agent_task


async def code_replication_workflow(
    workspace_id: str,
    repo_url: str,
    script_path: str,
    branch: Optional[str] = None,
    commit_hash: Optional[str] = None,
    sandbox_parameters: Optional[Dict[str, Any]] = None,
    db: DBWrapper = None
) -> Dict[str, Any]:
    """
    Execute code replication workflow.
    
    Per spec §5.2 (Workflow B):
    1. repo_ingest activity (clone repo, index files, store snapshot)
    2. sandbox_run activity (execute script, capture logs)
    3. Create agent_task for result summarization
    4. Agent writes draft citing log artifact (agent-driven)
    5. citation_check runs automatically on draft versions
    
    Args:
        workspace_id: Workspace UUID
        repo_url: Git repository URL
        script_path: Path to script file within repo
        branch: Optional branch name
        commit_hash: Optional commit hash to pin
        sandbox_parameters: Optional execution parameters (env vars, args)
        db: Database wrapper
    
    Returns:
        Workflow output with repo_artifact_id, log_artifact_id, task_id
    """
    workflow_id = f"code_replication_{uuid.uuid4()}"
    
    # Start workflow and persist workflow_runs
    client = WorkflowClient()
    workflow_run_id = await client.start_workflow(
        workflow_type="code_replication",
        workflow_id=workflow_id,
        task_queue="agora-tasks",
        args={
            "workspace_id": workspace_id,
            "repo_url": repo_url,
            "script_path": script_path,
            "branch": branch,
            "commit_hash": commit_hash,
            "sandbox_parameters": sandbox_parameters
        },
        db=db,
        workspace_id=workspace_id
    )
    
    try:
        # Step 1: Execute repo_ingest activity
        from repo_ingest import RepoIngestActivity
        from storage import create_storage_from_env
        
        # Create repo artifact
        repo_artifact_id = str(uuid.uuid4())
        db.execute(
            """
            INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
            VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
            """,
            {
                "id": repo_artifact_id,
                "workspace_id": workspace_id,
                "short_id": f"R{abs(hash(repo_artifact_id)) % 10000}",
                "type": "code",
                "metadata": json.dumps({"repo_url": repo_url}),
                "storage_uri": f"s3://agora/{workspace_id}/artifacts/{repo_artifact_id}/",
                "created_by": None
            }
        )
        db.commit()
        
        activity_id = f"repo_ingest_{repo_artifact_id}"
        activity_run_id = create_activity_run(
            db=db,
            workflow_run_id=workflow_run_id,
            activity_type="repo_ingest",
            activity_id=activity_id,
            input_data={
                "artifact_id": repo_artifact_id,
                "workspace_id": workspace_id,
                "repo_url": repo_url,
                "branch": branch,
                "commit_hash": commit_hash
            }
        )
        
        # Run repo_ingest
        storage = create_storage_from_env()
        repo_activity = RepoIngestActivity(storage, db)
        
        ingest_result = repo_activity.ingest_repo(
            artifact_id=repo_artifact_id,
            workspace_id=workspace_id,
            repo_url=repo_url,
            created_by=None,
            branch=branch,
            commit_hash=commit_hash,
            activity_run_id=activity_run_id
        )
        
        update_activity_run(
            db=db,
            activity_run_id=activity_run_id,
            status="completed",
            output=ingest_result
        )
        
        # Step 2: Execute sandbox_run activity
        from sandbox_run import SandboxRunActivity
        
        # Extract script artifact from repo using the new helper method
        script_artifact_id = str(uuid.uuid4())
        
        # Get script content from repo
        script_content = repo_activity.read_file_from_repo(
            artifact_version_id=ingest_result["artifact_version_id"],
            file_path=script_path
        )
        
        # Create script artifact
        db.execute(
            """
            INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
            VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
            """,
            {
                "id": script_artifact_id,
                "workspace_id": workspace_id,
                "short_id": f"S{abs(hash(script_artifact_id)) % 10000}",
                "type": "code",
                "metadata": json.dumps({
                    "source": "repo_extract",
                    "repo_artifact_id": repo_artifact_id,
                    "script_path": script_path
                }),
                "storage_uri": f"s3://agora/{workspace_id}/artifacts/{script_artifact_id}/",
                "created_by": None
            }
        )
        
        # Store script in MinIO
        script_version_id = str(uuid.uuid4())
        script_version_number = 1
        script_storage_uri = (
            f"s3://agora/{workspace_id}/artifacts/{script_artifact_id}/"
            f"v{script_version_number}/script.py"
        )
        
        script_bytes = script_content.encode("utf-8")
        storage.put_object(script_storage_uri, script_bytes)
        
        # Create script artifact version
        import hashlib
        script_hash = hashlib.sha256(script_bytes).hexdigest()
        
        db.execute(
            """
            INSERT INTO artifact_versions (id, artifact_id, version, storage_uri, content_hash, created_by, created_at)
            VALUES (:id, :artifact_id, :version, :storage_uri, :content_hash, :created_by, NOW())
            """,
            {
                "id": script_version_id,
                "artifact_id": script_artifact_id,
                "version": script_version_number,
                "content_hash": script_hash,
                "storage_uri": script_storage_uri,
                "created_by": None
            }
        )
        db.commit()
        
        # Create log artifact
        log_artifact_id = str(uuid.uuid4())
        db.execute(
            """
            INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
            VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
            """,
            {
                "id": log_artifact_id,
                "workspace_id": workspace_id,
                "short_id": f"LOG{abs(hash(log_artifact_id)) % 10000}",
                "type": "log",
                "metadata": json.dumps({
                    "source": "code_replication_workflow",
                    "repo_artifact_id": repo_artifact_id,
                    "script_artifact_id": script_artifact_id
                }),
                "storage_uri": f"s3://agora/{workspace_id}/artifacts/{log_artifact_id}/",
                "created_by": None
            }
        )
        db.commit()
        
        sandbox_activity_id = f"sandbox_run_{script_artifact_id}"
        sandbox_run_id = create_activity_run(
            db=db,
            workflow_run_id=workflow_run_id,
            activity_type="sandbox_run",
            activity_id=sandbox_activity_id,
            input_data={
                "artifact_id": log_artifact_id,
                "workspace_id": workspace_id,
                "script_artifact_id": script_artifact_id,
                "parameters": sandbox_parameters
            }
        )
        
        # Run sandbox_run
        sandbox_activity = SandboxRunActivity(storage, db)
        
        sandbox_result = sandbox_activity.run_sandbox(
            artifact_id=log_artifact_id,
            workspace_id=workspace_id,
            script_artifact_id=script_artifact_id,
            parameters=sandbox_parameters or {},
            created_by=None,
            activity_run_id=sandbox_run_id
        )
        
        update_activity_run(
            db=db,
            activity_run_id=sandbox_run_id,
            status="completed",
            output=sandbox_result
        )
        
        # Step 3: Create agent_task for result summarization
        task_id = str(uuid.uuid4())

        task_payload = TaskPayload(
            objective="Summarize the execution results with evidence-backed claims.",
            inputs=[
                TaskInput(
                    artifact_version_id=sandbox_result["version_id"],
                    label="Execution log",
                    location="log:full"
                )
            ],
            required_outputs=[
                "draft.version.create",
                "claim.create",
                "claim.evidence.add"
            ],
            context_links=[
                {"type": "artifact", "id": repo_artifact_id},
                {"type": "artifact", "id": script_artifact_id},
                {"type": "artifact", "id": log_artifact_id}
            ],
            acceptance_criteria=[
                "Draft summary created with citations to the log",
                "At least 1 claim created with evidence"
            ],
            priority=TaskPriority.HIGH.value,
            workflow_run_id=workflow_run_id,
            assignee_role=RoleName.EXPERIMENTALIST.value,
            execution={
                "exit_code": sandbox_result["exit_code"],
                "execution_time_seconds": sandbox_result["execution_time_seconds"]
            }
        ).model_dump()

        insert_agent_task(
            db,
            task_id=task_id,
            workspace_id=workspace_id,
            assignee_agent_id=None,
            task_type="summarize_results",
            status=TaskStatus.OPEN.value,
            payload=task_payload,
        )
        
        db.commit()
        
        # Step 4 & 5: Agent-driven (agent creates draft citing log, citation_check runs automatically)
        # This is handled asynchronously by agents via the API
        
        # Update workflow status
        await client.update_workflow_status(
            workflow_run_id=workflow_run_id,
            status="completed",
            output={
                "repo_artifact_id": repo_artifact_id,
                "repo_artifact_version_id": ingest_result["artifact_version_id"],
                "script_artifact_id": script_artifact_id,
                "log_artifact_id": log_artifact_id,
                "log_artifact_version_id": sandbox_result["version_id"],
                "config_artifact_id": sandbox_result["config_artifact_id"],
                "task_id": task_id,
                "exit_code": sandbox_result["exit_code"],
                "message": f"Code replication workflow completed. Script executed with exit code {sandbox_result['exit_code']}. Task assigned for result summarization."
            },
            db=db
        )
        
        return {
            "workflow_run_id": workflow_run_id,
            "repo_artifact_id": repo_artifact_id,
            "repo_artifact_version_id": ingest_result["artifact_version_id"],
            "script_artifact_id": script_artifact_id,
            "log_artifact_id": log_artifact_id,
            "log_artifact_version_id": sandbox_result["version_id"],
            "config_artifact_id": sandbox_result["config_artifact_id"],
            "task_id": task_id,
            "exit_code": sandbox_result["exit_code"]
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
