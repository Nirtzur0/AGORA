"""Temporal workflows for agent-facing request actions."""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


REQUEST_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(seconds=5),
    maximum_attempts=3,
)


@workflow.defn
class RepoIngestWorkflow:
    @workflow.run
    async def run(
        self,
        workflow_run_id: str,
        workspace_id: str,
        artifact_id: str,
        repo_url: str,
        created_by: str,
        branch: str | None = None,
        commit_hash: str | None = None,
    ) -> dict:
        return await workflow.execute_activity(
            "repo_ingest",
            args=[
                {
                    "workflow_run_id": workflow_run_id,
                    "artifact_id": artifact_id,
                    "workspace_id": workspace_id,
                    "repo_url": repo_url,
                    "created_by": created_by,
                    "branch": branch,
                    "commit_hash": commit_hash,
                }
            ],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=REQUEST_RETRY_POLICY,
        )


@workflow.defn
class SandboxRunWorkflow:
    @workflow.run
    async def run(
        self,
        workflow_run_id: str,
        workspace_id: str,
        log_artifact_id: str,
        script_artifact_id: str,
        created_by: str,
        parameters: dict | None,
        image: str,
        timeout_seconds: int,
        memory_limit: str,
        cpu_limit: str,
    ) -> dict:
        return await workflow.execute_activity(
            "sandbox_run",
            args=[
                {
                    "workflow_run_id": workflow_run_id,
                    "artifact_id": log_artifact_id,
                    "workspace_id": workspace_id,
                    "script_artifact_id": script_artifact_id,
                    "parameters": parameters or {},
                    "created_by": created_by,
                    "image": image,
                    "timeout_seconds": timeout_seconds,
                    "memory_limit": memory_limit,
                    "cpu_limit": cpu_limit,
                }
            ],
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=REQUEST_RETRY_POLICY,
        )
