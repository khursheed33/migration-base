from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.schemas import MetadataResponse, ErrorResponse
from app.databases import neo4j_manager

router = APIRouter()


@router.get(
    "/{project_id}/metadata",
    response_model=MetadataResponse,
    responses={
        200: {"model": MetadataResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_project_metadata(project_id: str):
    """
    Get metadata for a project, including files, functions, classes, enums, extensions, and relationships.
    
    Args:
        project_id: Project ID
        
    Returns:
        Project metadata
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
        
        # Get file metadata
        files_query = """
        MATCH (p:Project {project_id: $project_id})-[:CONTAINS]->(f:File)
        RETURN f
        """
        files_result = neo4j_manager.run_query(files_query, {"project_id": project_id})
        files = [record["f"] for record in files_result]
        
        # Get function metadata
        functions_query = """
        MATCH (f:File {project_id: $project_id})-[:HAS_FUNCTION]->(fn:Function)
        RETURN fn
        """
        functions_result = neo4j_manager.run_query(functions_query, {"project_id": project_id})
        functions = [record["fn"] for record in functions_result]
        
        # Get class metadata
        classes_query = """
        MATCH (f:File {project_id: $project_id})-[:HAS_CLASS]->(c:Class)
        RETURN c
        """
        classes_result = neo4j_manager.run_query(classes_query, {"project_id": project_id})
        classes = [record["c"] for record in classes_result]
        
        # Get enum metadata
        enums_query = """
        MATCH (f:File {project_id: $project_id})-[:HAS_ENUM]->(e:Enum)
        RETURN e
        """
        enums_result = neo4j_manager.run_query(enums_query, {"project_id": project_id})
        enums = [record["e"] for record in enums_result]
        
        # Get extension metadata
        extensions_query = """
        MATCH (f:File {project_id: $project_id})-[:HAS_EXTENSION]->(e:Extension)
        RETURN e
        """
        extensions_result = neo4j_manager.run_query(extensions_query, {"project_id": project_id})
        extensions = [record["e"] for record in extensions_result]
        
        # Get relationship metadata
        relationships_query = """
        MATCH (f1:File {project_id: $project_id})-[r:IMPORTS|REFERENCES]->(f2:File)
        RETURN f1.relative_path AS source, f2.relative_path AS target, type(r) AS relationship_type
        """
        relationships_result = neo4j_manager.run_query(relationships_query, {"project_id": project_id})
        relationships = [
            {
                "source": record["source"],
                "target": record["target"],
                "type": record["relationship_type"]
            }
            for record in relationships_result
        ]
        
        # Return metadata response
        return MetadataResponse(
            project_id=project_id,
            files=files,
            functions=functions,
            classes=classes,
            enums=enums,
            extensions=extensions,
            relationships=relationships
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                status="error",
                message=f"Error retrieving project metadata: {str(e)}",
                error_code="metadata_retrieval_failed"
            ).dict()
        ) 