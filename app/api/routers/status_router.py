from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.schemas import StatusResponse, ErrorResponse
from app.config.dependencies import dependency_initializer

router = APIRouter()


@router.get(
    "/{project_id}/status",
    response_model=StatusResponse,
    responses={
        200: {"model": StatusResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_project_status(project_id: str):
    """
    Get the current status of a migration project.
    
    Args:
        project_id: Project ID
        
    Returns:
        Project status information
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
            
        # Retrieve project from database
        query = """
        MATCH (p:Project {project_id: $project_id})
        RETURN p
        """
        result = neo4j_manager.run_query(query, {"project_id": project_id})
        
        if not result:
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    status="error",
                    message=f"Project {project_id} not found",
                    error_code="project_not_found"
                ).dict()
            )
        
        project = result[0]["p"]
        
        # Get project steps (completed and remaining)
        steps_completed = []
        steps_remaining = []
        current_step_details = {}
        
        # Define all possible steps with details
        all_steps = [
            {
                "name": "Project upload",
                "description": "Uploading and validating project files",
                "estimated_duration": "1-2 minutes"
            },
            {
                "name": "Structure analysis",
                "description": "Analyzing project structure and file organization",
                "estimated_duration": "2-5 minutes"
            },
            {
                "name": "Content analysis",
                "description": "Analyzing code content and dependencies",
                "estimated_duration": "5-10 minutes"
            },
            {
                "name": "Component classification",
                "description": "Classifying project components and modules",
                "estimated_duration": "3-5 minutes"
            },
            {
                "name": "Mapping generation",
                "description": "Generating mappings for code migration",
                "estimated_duration": "5-10 minutes"
            },
            {
                "name": "Target component identification",
                "description": "Identifying target framework components",
                "estimated_duration": "2-4 minutes"
            },
            {
                "name": "Intermediate representation",
                "description": "Creating intermediate code representation",
                "estimated_duration": "5-8 minutes"
            },
            {
                "name": "Architecture design",
                "description": "Designing target application architecture",
                "estimated_duration": "4-7 minutes"
            },
            {
                "name": "Migration strategy",
                "description": "Planning migration strategies",
                "estimated_duration": "3-5 minutes"
            },
            {
                "name": "Code generation",
                "description": "Generating target code",
                "estimated_duration": "10-15 minutes"
            },
            {
                "name": "Configuration generation",
                "description": "Generating configuration files",
                "estimated_duration": "2-3 minutes"
            },
            {
                "name": "Testing",
                "description": "Running automated tests",
                "estimated_duration": "5-10 minutes"
            },
            {
                "name": "Packaging",
                "description": "Packaging migrated code",
                "estimated_duration": "2-3 minutes"
            }
        ]
        
        # Determine which steps are completed based on progress
        progress = project.get("progress", 0)
        step_value = 100 / len(all_steps)
        current_step = project.get("current_step", "")
        
        # Calculate completed and remaining steps
        for i, step in enumerate(all_steps):
            if progress >= (i + 1) * step_value:
                steps_completed.append(step)
            else:
                steps_remaining.append(step)
                if step["name"] == current_step:
                    current_step_details = step
        
        # Get additional status details
        status_details = {
            "files_processed": project.get("files_processed", 0),
            "total_files": project.get("total_files", 0),
            "current_file": project.get("current_file", ""),
            "last_error": project.get("last_error", None),
            "warnings": project.get("warnings", []),
            "performance_metrics": {
                "processing_speed": project.get("processing_speed", "0 files/sec"),
                "memory_usage": project.get("memory_usage", "0 MB"),
                "cpu_usage": project.get("cpu_usage", "0%")
            }
        }
        
        # Prepare response
        return StatusResponse(
            project_id=project_id,
            status=project.get("status", "unknown"),
            progress=progress,
            current_step=current_step,
            current_step_details=current_step_details,
            steps_completed=steps_completed,
            steps_remaining=steps_remaining,
            status_details=status_details,
            updated_at=project.get("updated_at"),
            estimated_completion=project.get("estimated_completion")
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                status="error",
                message=f"Error retrieving project status: {str(e)}",
                error_code="status_retrieval_failed"
            ).dict()
        )