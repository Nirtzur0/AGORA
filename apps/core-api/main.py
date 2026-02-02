"""
Core API main application.
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import logging

from config import settings
from auth_routes import router as auth_router
from agent_routes import router as agent_router

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
