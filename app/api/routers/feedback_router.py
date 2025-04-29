import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse

from app.schemas import FeedbackCreate, FeedbackResponse, SuccessResponse, ErrorResponse
from app.databases import neo4j_manager

router = APIRouter()


@router.post(
    "/{project_id}/feedback",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def create_feedback(
    project_id: str,
    feedback: FeedbackCreate = Body(...),
):
    """
    Create feedback for a migration project.
    
    Args:
        project_id: Project ID
        feedback: Feedback data
        
    Returns:
        Success response with created feedback
    """
    try:
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
        
        # Create feedback
        feedback_id = f"feedback_{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow().isoformat()
        
        feedback_properties = {
            "feedback_id": feedback_id,
            "project_id": project_id,
            "issue": feedback.issue,
            "suggestion": feedback.suggestion,
            "component": feedback.component,
            "resolution": None,
            "created_at": now,
            "updated_at": now
        }
        
        # Create Feedback node
        neo4j_manager.create_node("Feedback", feedback_properties)
        
        # Create relationship to Project
        neo4j_manager.create_relationship(
            from_label="Project",
            from_property="project_id",
            from_value=project_id,
            to_label="Feedback",
            to_property="feedback_id",
            to_value=feedback_id,
            relationship_type="FEEDBACK_FOR"
        )
        
        # Return success response
        return SuccessResponse(
            status="success",
            message="Feedback created successfully",
            data=FeedbackResponse(**feedback_properties)
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                status="error",
                message=f"Error creating feedback: {str(e)}",
                error_code="feedback_creation_failed"
            ).dict()
        )


@router.get(
    "/{project_id}/feedback",
    response_model=SuccessResponse,
    responses={
        200: {"model": SuccessResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_project_feedback(project_id: str):
    """
    Get all feedback for a migration project.
    
    Args:
        project_id: Project ID
        
    Returns:
        Success response with list of feedback
    """
    try:
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
        
        # Get feedback
        query = """
        MATCH (p:Project {project_id: $project_id})-[:FEEDBACK_FOR]->(f:Feedback)
        RETURN f
        ORDER BY f.created_at DESC
        """
        result = neo4j_manager.run_query(query, {"project_id": project_id})
        
        feedback_list = [FeedbackResponse(**record["f"]) for record in result]
        
        # Return success response
        return SuccessResponse(
            status="success",
            message=f"Found {len(feedback_list)} feedback items",
            data=feedback_list
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                status="error",
                message=f"Error retrieving feedback: {str(e)}",
                error_code="feedback_retrieval_failed"
            ).dict()
        ) 