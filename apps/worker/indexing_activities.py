"""
Search Indexing Activities - Component 22

Per spec §6.5, §9:
- Index parsed PDF text
- Index repo file text
- Index logs (optional)
- Update Postgres FTS tables for efficient search
"""

import logging
from datetime import datetime, timezone
from temporalio import activity
from sqlalchemy import text
from apps.worker.database import get_db_connection

logger = logging.getLogger(__name__)


@activity.defn
async def index_artifact_content(
    workspace_id: str,
    artifact_id: str,
    artifact_version_id: str,
    artifact_type: str,
    content: str,
    metadata: dict = None
) -> dict:
    """
    Index artifact content for full-text search.
    
    Per spec §6.5:
    - Updates Postgres FTS tables (search_index)
    - Supports PDF text, repo file text, and logs
    
    Args:
        workspace_id: Workspace containing the artifact
        artifact_id: ID of the artifact
        artifact_version_id: Specific version to index
        artifact_type: Type of artifact (pdf, repo, log, etc.)
        content: Text content to index
        metadata: Optional metadata (file path, page number, etc.)
    
    Returns:
        dict with index_id and indexed_at timestamp
    
    Raises:
        RuntimeError: If indexing fails
    """
    logger.info(
        f"Indexing artifact {artifact_id} version {artifact_version_id} "
        f"in workspace {workspace_id} (type: {artifact_type})"
    )
    
    conn = get_db_connection()
    
    try:
        # Check if this version is already indexed
        existing = conn.execute(
            text("""
                SELECT id FROM search_index
                WHERE artifact_version_id = :version_id
            """),
            {"version_id": artifact_version_id}
        ).fetchone()
        
        if existing:
            # Update existing index entry
            logger.info(f"Updating existing index entry for version {artifact_version_id}")
            conn.execute(
                text("""
                    UPDATE search_index
                    SET content = :content,
                        metadata = :metadata,
                        indexed_at = NOW()
                    WHERE artifact_version_id = :version_id
                """),
                {
                    "version_id": artifact_version_id,
                    "content": content,
                    "metadata": metadata or {}
                }
            )
            index_id = existing[0]
        else:
            # Insert new index entry
            logger.info(f"Creating new index entry for version {artifact_version_id}")
            result = conn.execute(
                text("""
                    INSERT INTO search_index (
                        workspace_id,
                        artifact_id,
                        artifact_version_id,
                        artifact_type,
                        content,
                        metadata,
                        indexed_at
                    ) VALUES (
                        :workspace_id,
                        :artifact_id,
                        :version_id,
                        :artifact_type,
                        :content,
                        :metadata,
                        NOW()
                    )
                    RETURNING id
                """),
                {
                    "workspace_id": workspace_id,
                    "artifact_id": artifact_id,
                    "version_id": artifact_version_id,
                    "artifact_type": artifact_type,
                    "content": content,
                    "metadata": metadata or {}
                }
            )
            index_id = result.fetchone()[0]
        
        conn.commit()
        
        indexed_at = datetime.now(timezone.utc).isoformat()
        
        logger.info(
            f"Successfully indexed artifact version {artifact_version_id}: "
            f"index_id={index_id}, content_length={len(content)}"
        )
        
        return {
            "index_id": str(index_id),
            "indexed_at": indexed_at,
            "content_length": len(content),
            "artifact_version_id": artifact_version_id
        }
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to index artifact content: {e}")
        raise RuntimeError(f"Indexing failed: {e}")
    finally:
        conn.close()


@activity.defn
async def index_pdf_text(
    workspace_id: str,
    artifact_id: str,
    artifact_version_id: str,
    pdf_text: str,
    page_metadata: dict = None
) -> dict:
    """
    Index parsed PDF text content.
    
    Per spec §6.5:
    - Indexes parsed PDF text for full-text search
    
    Args:
        workspace_id: Workspace containing the PDF
        artifact_id: ID of the PDF artifact
        artifact_version_id: Specific version to index
        pdf_text: Extracted text from PDF
        page_metadata: Optional page-level metadata
    
    Returns:
        dict with indexing result
    """
    logger.info(f"Indexing PDF artifact {artifact_id} version {artifact_version_id}")
    
    return await index_artifact_content(
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        artifact_version_id=artifact_version_id,
        artifact_type="pdf",
        content=pdf_text,
        metadata=page_metadata
    )


@activity.defn
async def index_repo_file(
    workspace_id: str,
    artifact_id: str,
    artifact_version_id: str,
    file_content: str,
    file_path: str
) -> dict:
    """
    Index repository file content.
    
    Per spec §6.5:
    - Indexes repo file text for full-text search
    
    Args:
        workspace_id: Workspace containing the repo
        artifact_id: ID of the repo artifact
        artifact_version_id: Specific version to index
        file_content: Text content of the file
        file_path: Path of the file within the repo
    
    Returns:
        dict with indexing result
    """
    logger.info(f"Indexing repo file {file_path} in artifact {artifact_id}")
    
    return await index_artifact_content(
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        artifact_version_id=artifact_version_id,
        artifact_type="repo",
        content=file_content,
        metadata={"file_path": file_path}
    )


@activity.defn
async def index_log(
    workspace_id: str,
    artifact_id: str,
    artifact_version_id: str,
    log_content: str,
    log_metadata: dict = None
) -> dict:
    """
    Index log content (optional).
    
    Per spec §6.5:
    - Indexes logs for full-text search (optional feature)
    
    Args:
        workspace_id: Workspace containing the log
        artifact_id: ID of the log artifact
        artifact_version_id: Specific version to index
        log_content: Log text content
        log_metadata: Optional log metadata
    
    Returns:
        dict with indexing result
    """
    logger.info(f"Indexing log artifact {artifact_id} version {artifact_version_id}")
    
    return await index_artifact_content(
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        artifact_version_id=artifact_version_id,
        artifact_type="log",
        content=log_content,
        metadata=log_metadata
    )


# Activity list for worker registration
INDEXING_ACTIVITIES = [
    index_artifact_content,
    index_pdf_text,
    index_repo_file,
    index_log,
]
