"""Temporal workflow for PDF ingestion plus claim-extraction task assignment."""

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
class LiteratureGroundingWorkflow:
    @workflow.run
    async def run(
        self,
        workflow_run_id: str,
        workspace_id: str,
        artifact_id: str,
        created_by: str,
    ) -> dict:
        ingest_result = await workflow.execute_activity(
            "pdf_ingest",
            args=[
                {
                    "workflow_run_id": workflow_run_id,
                    "artifact_id": artifact_id,
                    "workspace_id": workspace_id,
                    "created_by": created_by,
                }
            ],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=REQUEST_RETRY_POLICY,
        )

        task_result = await workflow.execute_activity(
            "create_literature_grounding_task",
            args=[
                {
                    "workflow_run_id": workflow_run_id,
                    "workspace_id": workspace_id,
                    "artifact_id": artifact_id,
                    "artifact_version_id": ingest_result["artifact_version_id"],
                }
            ],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=REQUEST_RETRY_POLICY,
        )

        return {
            "artifact_version_id": ingest_result["artifact_version_id"],
            "page_count": ingest_result.get("page_count"),
            "task_id": task_result["task_id"],
        }
