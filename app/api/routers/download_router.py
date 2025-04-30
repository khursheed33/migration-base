import os
import zipfile
import tempfile
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from datetime import datetime

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
                    error_code="service_unavailable",
                    details={"component": "database"}
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
                    error_code="project_not_found",
                    details={"project_id": project_id}
                ).dict()
            )
        
        # Check if project has been migrated
        if project.get("status") != "completed":
            return JSONResponse(
                status_code=400,
                content=ErrorResponse(
                    status="error",
                    message=f"Project {project_id} migration is not complete",
                    error_code="migration_incomplete",
                    details={
                        "project_id": project_id,
                        "current_status": project.get("status"),
                        "progress": project.get("progress", 0),
                        "current_step": project.get("current_step", "")
                    }
                ).dict()
            )
        
        migrated_dir = project.get("migrated_dir")
        if not migrated_dir or not os.path.exists(migrated_dir):
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    status="error",
                    message=f"Migrated code not found for project {project_id}",
                    error_code="migrated_code_not_found",
                    details={
                        "project_id": project_id,
                        "migrated_dir": migrated_dir
                    }
                ).dict()
            )
        
        # Create ZIP file with progress tracking
        zip_filename = f"migrated_{project_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path = os.path.join(tempfile.gettempdir(), zip_filename)
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Get total files for progress calculation
                total_files = sum([len(files) for _, _, files in os.walk(migrated_dir)])
                files_processed = 0
                
                for root, _, files in os.walk(migrated_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, migrated_dir)
                        zipf.write(file_path, arcname)
                        
                        # Update progress in Neo4j
                        files_processed += 1
                        progress = (files_processed / total_files) * 100
                        neo4j_manager.update_node(
                            label="Project",
                            property_name="project_id",
                            property_value=project_id,
                            updates={
                                "download_progress": progress,
                                "files_processed": files_processed,
                                "total_files": total_files
                            }
                        )
            
            # Return ZIP file
            return FileResponse(
                zip_path,
                media_type="application/zip",
                filename=zip_filename,
                headers={"X-Total-Files": str(total_files)}
            )
            
        finally:
            # Clean up temp file
            if os.path.exists(zip_path):
                os.unlink(zip_path)
                
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                status="error",
                message=f"Error downloading migrated code: {str(e)}",
                error_code="download_failed",
                details={
                    "project_id": project_id,
                    "error": str(e)
                }
            ).dict()
        )