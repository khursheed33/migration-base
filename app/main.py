from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys
import logging
from dotenv import load_dotenv

from app.api.routers import project_router, status_router, metadata_router, graph_router, download_router, feedback_router
from app.config.settings import get_settings
from app.config.dependencies import dependency_initializer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get settings
settings = get_settings()

# Initialize dependencies
logger.info("Initializing application dependencies")
if not dependency_initializer.initialize_all(exit_on_failure=True):
    logger.critical("Failed to initialize one or more critical dependencies. Exiting application.")
    sys.exit(1)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="A modular, agent-based migration framework for code migration.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(project_router.router, prefix="/projects", tags=["Projects"])
app.include_router(status_router.router, prefix="/projects", tags=["Status"])
app.include_router(metadata_router.router, prefix="/projects", tags=["Metadata"])
app.include_router(graph_router.router, prefix="/projects", tags=["Graph"])
app.include_router(download_router.router, prefix="/projects", tags=["Download"])
app.include_router(feedback_router.router, prefix="/projects", tags=["Feedback"])

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint to check if the API is running."""
    return {"message": "Code Migration Framework API is running", "version": "1.0.0"}

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

# Handle application shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler to clean up resources."""
    logger.info("Application shutting down, cleaning up resources")
    neo4j = dependency_initializer.get_service("neo4j")
    if neo4j:
        neo4j.close()
        logger.info("Neo4j connection closed")
    
    redis_client = dependency_initializer.get_service("redis")
    if redis_client:
        redis_client.close()
        logger.info("Redis connection closed")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=settings.DEBUG,
    ) 