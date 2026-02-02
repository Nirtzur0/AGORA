"""
Core API main application.
"""
import sys
from pathlib import Path

# Add packages to Python path
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "packages" / "db"))
sys.path.insert(0, str(repo_root / "packages" / "shared-types"))

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import logging

from config import settings
from auth_routes import router as auth_router
from agent_routes import router as agent_router
from workspace_routes import router as workspace_router
from artifact_routes import router as artifact_router
from log_event_routes import router as log_event_router
from evidence_routes import router as evidence_router
from claim_routes import router as claim_router
from draft_routes import router as draft_router
from rulecheck_routes import router as rulecheck_router
from task_routes import router as task_router
from request_routes import router as request_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    debug=settings.api_debug,
)

# Include routers
app.include_router(auth_router, tags=["Authentication"])
app.include_router(agent_router, tags=["Agents"])
app.include_router(workspace_router, tags=["Workspaces"])
app.include_router(artifact_router, tags=["Artifacts"])
app.include_router(log_event_routes, tags=["Logs & Events"])
app.include_router(evidence_router, tags=["Evidence Resolution"])
app.include_router(claim_router, tags=["Claims"])
app.include_router(draft_router, tags=["Drafts"])
app.include_router(rulecheck_router, tags=["Rule Checks"])
app.include_router(task_router, tags=["Agent Tasks"])
app.include_router(request_router, tags=["Request Actions"])


@app.get("/health")
async def health_check():
    """
    Health check endpoint for service monitoring and smoke tests.
    
    Returns:
        JSONResponse with status and version info
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "core-api",
            "version": settings.api_version,
        }
    )


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "AGORA Core API",
        "version": settings.api_version,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
