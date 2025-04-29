import os
import uuid
import tempfile
import shutil
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import ValidationError
import json

from app.config.settings import get_settings
from app.schemas import (
    ProjectCreate,
    ProjectResponse,
    SuccessResponse,
    ErrorResponse,
)
from app.agents.tasks import process_upload
from app.databases import neo4j_manager

settings = get_settings()
router = APIRouter()


@router.post(
    "/upload",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def upload_project(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Form(...),
    description: Optional[str] = Form(None),
    source_language: Optional[str] = Form(None),
    target_language: Optional[str] = Form(None),
    source_framework: Optional[str] = Form(None),
    target_framework: Optional[str] = Form(None),
    custom_mappings: Optional[str] = Form(None),
):
    """
    Upload a ZIP file containing the source code for migration.
    
    Args:
        file: ZIP file containing the source code
        user_id: User ID
        description: Project description
        source_language: Source programming language
        target_language: Target programming language
        source_framework: Source framework
        target_framework: Target framework
        custom_mappings: Custom mappings as JSON string
        
    Returns:
        Success response with project ID
    """
    # Validate file
    if not file.filename.endswith('.zip'):
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                status="error",
                message="Uploaded file must be a ZIP file",
                error_code="invalid_file_type"
            ).dict()
        )
    
    # Parse custom mappings if provided
    mappings_dict = {}
    if custom_mappings:
        try:
            mappings_dict = json.loads(custom_mappings)
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=400,
                content=ErrorResponse(
                    status="error",
                    message="Invalid JSON format for custom_mappings",
                    error_code="invalid_json"
                ).dict()
            )
    
    try:
        # Create project data
        project_id = f"proj_{uuid.uuid4().hex[:8]}"
        project_data = {
            "user_id": user_id,
            "description": description,
            "source_language": source_language,
            "target_language": target_language,
            "source_framework": source_framework,
            "target_framework": target_framework,
            "custom_mappings": mappings_dict,
        }
        
        # Save file to temporary location
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        try:
            # Save uploaded file to temporary file
            with open(temp_file.name, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Process upload in background
            background_tasks.add_task(
                process_upload,
                project_id=project_id,
                zip_file_path=temp_file.name,
                project_data=project_data
            )
            
        except Exception as e:
            # Clean up temp file on error
            os.unlink(temp_file.name)
            raise e
        
        return SuccessResponse(
            status="success",
            message="Project upload initiated",
            data={"project_id": project_id}
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                status="error",
                message=f"Error processing upload: {str(e)}",
                error_code="upload_failed"
            ).dict()
        )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={
        200: {"model": ProjectResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_project(project_id: str):
    """
    Get project details.
    
    Args:
        project_id: Project ID
        
    Returns:
        Project details
    """
    try:
        # Retrieve project from database
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
        
        # Convert Neo4j node to ProjectResponse
        return ProjectResponse(**project)
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                status="error",
                message=f"Error retrieving project: {str(e)}",
                error_code="retrieval_failed"
            ).dict()
        ) 