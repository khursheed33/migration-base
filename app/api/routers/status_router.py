from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.schemas import StatusResponse, ErrorResponse
from app.databases import neo4j_manager

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
        
        # Define all possible steps
        all_steps = [
            "Project upload",
            "Structure analysis",
            "Content analysis",
            "Component classification",
            "Mapping generation",
            "Target component identification",
            "Intermediate representation",
            "Architecture design",
            "Migration strategy",
            "Code generation",
            "Configuration generation",
            "Testing",
            "Packaging"
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
        
        # Prepare response
        return StatusResponse(
            project_id=project_id,
            status=project.get("status", "unknown"),
            progress=progress,
            current_step=current_step,
            steps_completed=steps_completed,
            steps_remaining=steps_remaining,
            updated_at=project.get("updated_at")
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