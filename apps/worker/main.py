"""
AGORA Temporal Worker Main Entry Point.

Starts Temporal worker and registers activities:
- PDF ingestion
- Repo ingestion
- Sandbox execution
- Phase/gate/indexing/finalization activity bundle
"""
import asyncio
import logging
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, ContextManager, List

# Add packages to Python path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "packages" / "db"))
sys.path.insert(0, str(repo_root / "packages" / "shared-types"))

from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from agent_tasks import TaskInput, TaskPayload, TaskPriority, TaskStatus, RoleName
from pdf_ingest import PDFIngestActivity
from repo_ingest import RepoIngestActivity
from request_action_workflows import RepoIngestWorkflow, SandboxRunWorkflow
from sandbox_run import SandboxRunActivity
from literature_grounding_workflow import LiteratureGroundingWorkflow
from draft_finalization_workflow import DraftFinalizationWorkflow
from phase_advancement_workflow import PhaseAdvancementWorkflow
from queries.agent_tasks import insert_agent_task
from runtime_config import get_temporal_address, get_temporal_task_queue
from workflow_tracking import create_activity_run, update_activity_run

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Temporal configuration
TEMPORAL_HOST = get_temporal_address()
TASK_QUEUE = get_temporal_task_queue()


@dataclass(frozen=True)
class WorkerRuntimeDependencies:
    """Runtime dependencies shared by worker activity wrappers."""

    storage: Any
    get_db: Callable[[], ContextManager[Any]]


def _load_runtime_dependencies() -> WorkerRuntimeDependencies:
    """Load runtime dependencies once at process startup."""
    from storage import create_storage_from_env
    from database import get_db

    storage = create_storage_from_env()
    return WorkerRuntimeDependencies(storage=storage, get_db=get_db)


def _validate_runtime_dependencies(deps: WorkerRuntimeDependencies) -> None:
    """Fail fast if worker dependencies are not usable."""
    with deps.get_db() as db:
        db.execute("SELECT 1")


def _create_pdf_ingest_activity(deps: WorkerRuntimeDependencies, db: Any) -> PDFIngestActivity:
    """
    Create a fresh PDF activity for each invocation.

    This avoids sharing mutable DB state across concurrent activity executions.
    """
    return PDFIngestActivity(deps.storage, db)


def _create_repo_ingest_activity(deps: WorkerRuntimeDependencies, db: Any) -> RepoIngestActivity:
    """Create a fresh repo-ingest activity for each invocation."""
    return RepoIngestActivity(deps.storage, db)


def _create_sandbox_run_activity(deps: WorkerRuntimeDependencies, db: Any) -> SandboxRunActivity:
    """Create a fresh sandbox activity for each invocation."""
    return SandboxRunActivity(deps.storage, db)


def _build_registered_activities(deps: WorkerRuntimeDependencies) -> List[Any]:
    """
    Build the worker activity list.

    All wrapper-backed activities use the same per-invocation DB-scoped lifecycle.
    """
    from phase_activities import PHASE_ACTIVITIES

    async def _run_tracked_activity(
        *,
        params: dict,
        activity_type: str,
        runner: Callable[[Any, str], dict],
    ) -> dict:
        workflow_run_id = params["workflow_run_id"]
        with deps.get_db() as db:
            activity_run_id = create_activity_run(
                db=db,
                workflow_run_id=workflow_run_id,
                activity_type=activity_type,
                activity_id=activity.info().activity_id,
            )
            try:
                result = runner(db, activity_run_id)
            except Exception:
                update_activity_run(db=db, activity_run_id=activity_run_id, status="failed")
                raise
            update_activity_run(db=db, activity_run_id=activity_run_id, status="completed")
            return result

    @activity.defn(name="pdf_ingest")
    async def pdf_ingest_wrapper(params: dict) -> dict:
        def _runner(db: Any, activity_run_id: str) -> dict:
            pdf_activity = _create_pdf_ingest_activity(deps, db)
            pdf_bytes = params.get("pdf_bytes")
            if pdf_bytes is None:
                version_row = db.execute(
                    """
                    SELECT storage_uri
                    FROM artifact_versions
                    WHERE artifact_id = :artifact_id
                    ORDER BY version DESC
                    LIMIT 1
                    """,
                    {"artifact_id": params["artifact_id"]},
                ).fetchone()
                if not version_row:
                    raise ValueError(f"No artifact_versions found for PDF artifact {params['artifact_id']}")
                pdf_bytes = deps.storage.get_object(version_row[0]).read()

            return pdf_activity.ingest_pdf(
                artifact_id=params["artifact_id"],
                workspace_id=params["workspace_id"],
                pdf_bytes=pdf_bytes,
                created_by=params["created_by"],
                activity_run_id=activity_run_id,
            )

        return await _run_tracked_activity(
            params=params,
            activity_type="pdf_ingest",
            runner=_runner,
        )

    @activity.defn(name="repo_ingest")
    async def repo_ingest_wrapper(params: dict) -> dict:
        def _runner(db: Any, activity_run_id: str) -> dict:
            repo_activity = _create_repo_ingest_activity(deps, db)
            return repo_activity.ingest_repo(
                artifact_id=params["artifact_id"],
                workspace_id=params["workspace_id"],
                repo_url=params["repo_url"],
                created_by=params["created_by"],
                branch=params.get("branch"),
                commit_hash=params.get("commit_hash"),
                activity_run_id=activity_run_id,
            )

        return await _run_tracked_activity(
            params=params,
            activity_type="repo_ingest",
            runner=_runner,
        )

    @activity.defn(name="sandbox_run")
    async def sandbox_run_wrapper(params: dict) -> dict:
        def _runner(db: Any, activity_run_id: str) -> dict:
            sandbox_activity = _create_sandbox_run_activity(deps, db)
            return sandbox_activity.run_sandbox(
                artifact_id=params["artifact_id"],
                workspace_id=params["workspace_id"],
                script_artifact_id=params["script_artifact_id"],
                parameters=params.get("parameters"),
                created_by=params.get("created_by", "SYSTEM"),
                activity_run_id=activity_run_id,
                image=params.get("image", "python:3.11-slim"),
                timeout_seconds=params.get("timeout_seconds", 300),
                memory_limit=params.get("memory_limit", "512m"),
                cpu_limit=params.get("cpu_limit", "1.0"),
            )

        return await _run_tracked_activity(
            params=params,
            activity_type="sandbox_run",
            runner=_runner,
        )

    @activity.defn(name="create_literature_grounding_task")
    async def create_literature_grounding_task(params: dict) -> dict:
        def _runner(db: Any, activity_run_id: str) -> dict:
            task_id = str(uuid.uuid4())
            task_payload = TaskPayload(
                objective="Extract claims from the PDF and add evidence.",
                inputs=[
                    TaskInput(
                        artifact_version_id=params["artifact_version_id"],
                        label="Parsed PDF",
                    )
                ],
                required_outputs=[
                    "claim.create",
                    "claim.evidence.add",
                    "draft.version.create",
                ],
                context_links=[{"type": "artifact", "id": params["artifact_id"]}],
                acceptance_criteria=[
                    "At least 2 claims created with evidence pointers",
                    "A draft version created with citations",
                ],
                priority=TaskPriority.HIGH.value,
                workflow_run_id=params["workflow_run_id"],
                assignee_role=RoleName.LITERATURE_ANALYST.value,
            ).model_dump()
            insert_agent_task(
                db,
                task_id=task_id,
                workspace_id=params["workspace_id"],
                assignee_agent_id=None,
                task_type="extract_claims",
                status=TaskStatus.OPEN.value,
                payload=task_payload,
            )
            db.commit()
            return {"task_id": task_id}

        return await _run_tracked_activity(
            params=params,
            activity_type="assign_agent_task",
            runner=_runner,
        )

    return [
        pdf_ingest_wrapper,
        repo_ingest_wrapper,
        sandbox_run_wrapper,
        create_literature_grounding_task,
        *PHASE_ACTIVITIES,
    ]


def _build_registered_workflows() -> List[Any]:
    return [
        LiteratureGroundingWorkflow,
        RepoIngestWorkflow,
        SandboxRunWorkflow,
        PhaseAdvancementWorkflow,
        DraftFinalizationWorkflow,
    ]


async def main():
    """Start Temporal worker with registered activities."""
    # Connect to Temporal
    client = await Client.connect(TEMPORAL_HOST)
    logger.info(f"Connected to Temporal at {TEMPORAL_HOST}")

    deps = _load_runtime_dependencies()
    _validate_runtime_dependencies(deps)
    logger.info("Worker runtime dependencies initialized")
    activities = _build_registered_activities(deps)
    workflows = _build_registered_workflows()

    # Create and run worker
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        activities=activities,
        workflows=workflows,
    )

    logger.info(
        "Starting worker on task queue: %s (registered activities=%s registered workflows=%s)",
        TASK_QUEUE,
        len(activities),
        len(workflows),
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
