from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv

from app.api.routers import project_router, status_router, metadata_router, graph_router, download_router, feedback_router
from app.config.settings import get_settings

# Load environment variables
load_dotenv()

settings = get_settings()

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

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=settings.DEBUG,
    ) 