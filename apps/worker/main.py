"""
AGORA Temporal Worker Main Entry Point.

Starts Temporal worker and registers activities:
- PDF ingestion
- (Future: Repo ingestion, sandbox execution, etc.)
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add packages to Python path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "packages" / "db"))
sys.path.insert(0, str(repo_root / "packages" / "shared-types"))

from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from pdf_ingest import PDFIngestActivity

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Temporal configuration
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "agora-worker")


async def main():
    """Start Temporal worker with registered activities."""
    # Connect to Temporal
    client = await Client.connect(TEMPORAL_HOST)
    logger.info(f"Connected to Temporal at {TEMPORAL_HOST}")
    
    # Initialize activity instances (with dependencies injected)
    # Note: In production, these would be properly dependency-injected
    from storage import create_storage_from_env
    from database import get_db
    
    storage = create_storage_from_env()
    # For worker, we'll use a simpler DB connection approach
    # This is a placeholder - actual implementation would use proper connection pooling
    
    pdf_activity = PDFIngestActivity(storage, None)
    
    # Register activities
    @activity.defn(name="pdf_ingest")
    async def pdf_ingest_wrapper(params: dict) -> dict:
        """Temporal activity wrapper for PDF ingestion."""
        # Get DB connection (in real implementation, use connection from context)
        from database import get_db
        
        with get_db() as db:
            pdf_activity.db = db
            return pdf_activity.ingest_pdf(
                artifact_id=params["artifact_id"],
                workspace_id=params["workspace_id"],
                pdf_bytes=params["pdf_bytes"],
                created_by=params["created_by"],
                activity_run_id=params.get("activity_run_id")
            )
    
    # Create and run worker
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        activities=[pdf_ingest_wrapper],
    )
    
    logger.info(f"Starting worker on task queue: {TASK_QUEUE}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
