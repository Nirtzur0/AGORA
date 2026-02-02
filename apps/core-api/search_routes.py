"""
Search Routes (Component 22)

Per spec §4.13, §9:
- GET /search?workspace_id=...&query=...
- Returns artifact/version pointers with FTS ranking
- Postgres full-text search on indexed artifacts
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid

from database import DBWrapper, get_db
from auth_middleware import require_agent_token


router = APIRouter()


# Response Models

class SearchHit(BaseModel):
    """A single search result hit."""
    artifact_id: str
    artifact_version_id: str
    artifact_type: str
    relevance_rank: float = Field(..., description="FTS relevance score (higher = more relevant)")
    snippet: str = Field(..., description="Text snippet showing match context")
    metadata: Optional[dict] = Field(None, description="Optional metadata (file path, page number, etc.)")


class SearchResponse(BaseModel):
    """Search results response."""
    query: str
    workspace_id: str
    hits: List[SearchHit]
    total_hits: int
    message: str


# Endpoints

@router.get("/search", response_model=SearchResponse, tags=["Search"])
async def search(
    query: str = Query(..., description="Search query text"),
    workspace_id: Optional[str] = Query(None, description="Filter to specific workspace"),
    limit: int = Query(50, description="Maximum number of results", ge=1, le=500),
    current_agent: dict = Depends(require_agent_token),
    db: DBWrapper = Depends(get_db)
):
    """
    Full-text search across indexed artifacts.
    
    Per spec §4.13, §9:
    - Searches indexed PDF text, repo files, and logs
    - Uses Postgres FTS with relevance ranking
    - Returns artifact/version pointers with snippets
    
    Args:
        query: Search query text
        workspace_id: Optional workspace filter
        limit: Maximum results to return
    
    Returns:
        Search results with ranked hits
    
    Raises:
        400: If query is empty or invalid
        403: If agent doesn't have access to workspace
        404: If workspace not found
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # If workspace_id provided, validate agent has access
    if workspace_id:
        # Check workspace exists
        workspace_row = db.execute(
            "SELECT id FROM workspaces WHERE id = :workspace_id",
            {"workspace_id": workspace_id}
        ).fetchone()
        
        if not workspace_row:
            raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
        
        # Check agent has access (is member of workspace)
        agent_id = current_agent.get("agent_id")
        if agent_id:
            member_row = db.execute(
                """
                SELECT 1 FROM workspace_agents
                WHERE workspace_id = :workspace_id
                  AND agent_id = :agent_id
                  AND status = 'active'
                """,
                {"workspace_id": workspace_id, "agent_id": agent_id}
            ).fetchone()
            
            if not member_row:
                raise HTTPException(
                    status_code=403,
                    detail=f"Agent does not have access to workspace {workspace_id}"
                )
    
    # Build FTS query using to_tsquery
    # Convert simple query to tsquery format (handle multi-word queries)
    query_words = query.strip().split()
    tsquery = " & ".join(query_words)  # AND all words together
    
    # Execute FTS search with ranking
    if workspace_id:
        # Search within specific workspace
        search_query = """
            SELECT 
                si.artifact_id,
                si.artifact_version_id,
                si.artifact_type,
                ts_rank(si.content_tsv, to_tsquery('english', :tsquery)) AS rank,
                ts_headline('english', si.content, to_tsquery('english', :tsquery), 
                    'MaxWords=30, MinWords=15, ShortWord=3, MaxFragments=1') AS snippet,
                si.metadata
            FROM search_index si
            WHERE si.workspace_id = :workspace_id
              AND si.content_tsv @@ to_tsquery('english', :tsquery)
            ORDER BY rank DESC
            LIMIT :limit
        """
        params = {"workspace_id": workspace_id, "tsquery": tsquery, "limit": limit}
    else:
        # Search across all workspaces agent has access to
        agent_id = current_agent.get("agent_id")
        if not agent_id:
            raise HTTPException(
                status_code=403,
                detail="Agent must be authenticated to search across workspaces"
            )
        
        search_query = """
            SELECT 
                si.artifact_id,
                si.artifact_version_id,
                si.artifact_type,
                ts_rank(si.content_tsv, to_tsquery('english', :tsquery)) AS rank,
                ts_headline('english', si.content, to_tsquery('english', :tsquery), 
                    'MaxWords=30, MinWords=15, ShortWord=3, MaxFragments=1') AS snippet,
                si.metadata
            FROM search_index si
            INNER JOIN workspace_agents wa ON wa.workspace_id = si.workspace_id
            WHERE wa.agent_id = :agent_id
              AND wa.status = 'active'
              AND si.content_tsv @@ to_tsquery('english', :tsquery)
            ORDER BY rank DESC
            LIMIT :limit
        """
        params = {"agent_id": agent_id, "tsquery": tsquery, "limit": limit}
    
    try:
        results = db.execute(search_query, params).fetchall()
    except Exception as e:
        # Handle tsquery syntax errors gracefully
        raise HTTPException(
            status_code=400,
            detail=f"Invalid search query syntax: {str(e)}"
        )
    
    # Convert to response format
    hits = [
        SearchHit(
            artifact_id=str(row[0]),
            artifact_version_id=str(row[1]),
            artifact_type=row[2],
            relevance_rank=float(row[3]),
            snippet=row[4],
            metadata=row[5] if row[5] else {}
        )
        for row in results
    ]
    
    workspace_filter = f" in workspace {workspace_id}" if workspace_id else " across all accessible workspaces"
    
    return SearchResponse(
        query=query,
        workspace_id=workspace_id or "all",
        hits=hits,
        total_hits=len(hits),
        message=f"Found {len(hits)} result(s) for '{query}'{workspace_filter}"
    )
