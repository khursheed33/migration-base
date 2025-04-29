import os
import zipfile
import tempfile
import shutil
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, FileResponse

from app.schemas import ErrorResponse
from app.config.dependencies import dependency_initializer

router = APIRouter()


@router.get(
    "/{project_id}/download",
    responses={
        200: {"content": {"application/zip": {}}},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def download_migrated_code(project_id: str):
    """
    Download migrated code as a ZIP file.
    
    Args:
        project_id: Project ID
        
    Returns:
        ZIP file containing migrated code
    """
    try:
        # Get Neo4j manager from dependency initializer
        neo4j_manager = dependency_initializer.get_service("neo4j")
        if neo4j_manager is None:
            return JSONResponse(
                status_code=500,
                content=ErrorResponse(
                    status="error",
                    message="Database service not available",
                    error_code="service_unavailable"
                ).dict()
            )
            
        # Check if project exists
        project = neo4j_manager.find_node("Project", "project_id", project_id)
        if not project:
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    status="error",
                    message=f"Project {project_id} not found",
                    error_code="project_not_found"
                ).dict()
            )
        
        # Check if project has been migrated
        migrated_dir = project.get("migrated_dir")
        if not migrated_dir or not os.path.exists(migrated_dir):
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    status="error",
                    message=f"Migrated code not found for project {project_id}",
                    error_code="migrated_code_not_found"
                ).dict()
            )
        
        # Create ZIP file
        zip_filename = f"migrated_{project_id}.zip"
        zip_path = os.path.join(tempfile.gettempdir(), zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(migrated_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, migrated_dir)
                    zipf.write(file_path, arcname)
        
        # Return ZIP file
        return FileResponse(
            path=zip_path,
            filename=zip_filename,
            media_type="application/zip",
            background=lambda: os.unlink(zip_path)
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                status="error",
                message=f"Error downloading migrated code: {str(e)}",
                error_code="download_failed"
            ).dict()
        ) 