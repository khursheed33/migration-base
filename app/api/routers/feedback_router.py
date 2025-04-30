import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse

from app.schemas import FeedbackCreate, FeedbackResponse, SuccessResponse, ErrorResponse
from app.config.dependencies import dependency_initializer
from app.utils.constants import RelationshipType, NodeType

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
        
        # Create feedback
        feedback_id = f"feedback_{str(uuid.uuid4())}"
        now = datetime.utcnow().isoformat()
        
        feedback_properties = {
            "feedback_id": feedback_id,
            "project_id": project_id,
            "issue": feedback.issue,
            "suggestion": feedback.suggestion,
            "component": feedback.component,
            "resolution": None,
            "created_at": now,
            "updated_at": now,
            "status": "pending"  # Add status field
        }
        
        # Create Feedback node
        neo4j_manager.create_node("Feedback", feedback_properties)
        
        # Create relationship to Project
        neo4j_manager.create_relationship(
            from_label=NodeType.PROJECT,
            from_property="project_id",
            from_value=project_id,
            to_label=NodeType.FEEDBACK,
            to_property="feedback_id",
            to_value=feedback_id,
            relationship_type=RelationshipType.FEEDBACK_FOR
        )
        
        # Update project's updated_at timestamp
        neo4j_manager.update_node(
            label="Project",
            property_name="project_id",
            property_value=project_id,
            updates={"updated_at": now}
        )
        
        # Return success response with more detailed information
        return SuccessResponse(
            status="success",
            message="Feedback submitted successfully",
            data={
                "feedback": FeedbackResponse(**feedback_properties),
                "project_status": {
                    "project_id": project_id,
                    "last_updated": now
                }
            }
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
        
        # Get feedback
        query = """
        MATCH (p:Project {project_id: $project_id})-[:""" + RelationshipType.FEEDBACK_FOR + """]->(f:Feedback)
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