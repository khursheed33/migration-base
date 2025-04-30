from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
import json

from app.schemas import MetadataResponse, ErrorResponse
from app.config.dependencies import dependency_initializer

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
            
        # Check if project exists and analysis is complete
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
            
        # Check if analysis is complete
        if project.get("status") not in ["analyzing_complete", "mapping_complete", "completed"]:
            return JSONResponse(
                status_code=400,
                content=ErrorResponse(
                    status="error",
                    message="Project analysis is not complete",
                    error_code="analysis_incomplete",
                    details={
                        "project_id": project_id,
                        "current_status": project.get("status"),
                        "progress": project.get("progress", 0),
                        "current_step": project.get("current_step", "")
                    }
                ).dict()
            )
        
        # Get file metadata with processing information
        files_query = """
        MATCH (p:Project {project_id: $project_id})-[:CONTAINS]->(f:File)
        RETURN f,
               size((f)<-[:CONTAINS]-(p)) as total_files,
               size((f)-[:HAS_FUNCTION]->()) as function_count,
               size((f)-[:HAS_CLASS]->()) as class_count,
               size((f)-[:HAS_ENUM]->()) as enum_count,
               size((f)-[:HAS_EXTENSION]->()) as extension_count,
               size((f)-[:IMPORTS]->()) as import_count,
               size((f)-[:REFERENCES]->()) as reference_count
        """
        files_result = neo4j_manager.run_query(files_query, {"project_id": project_id})
        # Process and serialize file metadata
        files = []
        for record in files_result:
            file_data = dict(record["f"])
            metadata = {
                "total_files": int(record["total_files"]),
                "function_count": int(record["function_count"]),
                "class_count": int(record["class_count"]),
                "enum_count": int(record["enum_count"]),
                "extension_count": int(record["extension_count"]),
                "import_count": int(record["import_count"]),
                "reference_count": int(record["reference_count"])
            }
            file_data["metadata"] = metadata
            files.append(file_data)
        
        # Get function metadata with relationship information
        functions_query = """
        MATCH (f:File {project_id: $project_id})-[:HAS_FUNCTION]->(fn:Function)
        OPTIONAL MATCH (fn)-[r]->(other)
        RETURN fn, collect(distinct type(r)) as relationships, collect(distinct labels(other)[0]) as related_types
        """
        functions_result = neo4j_manager.run_query(functions_query, {"project_id": project_id})
        # Process function metadata with relationship information
        functions = []
        for record in functions_result:
            function_data = dict(record["fn"])
            # Ensure proper serialization of function attributes
            for key in ["arguments", "decorators", "attributes"]:
                if isinstance(function_data.get(key), str):
                    try:
                        function_data[key] = json.loads(function_data[key])
                    except (json.JSONDecodeError, TypeError):
                        function_data[key] = []
            
            function_data.update({
                "relationships": record["relationships"] or [],
                "related_types": record["related_types"] or []
            })
            functions.append(function_data)
        
        # Get class metadata with inheritance information
        classes_query = """
        MATCH (f:File {project_id: $project_id})-[:HAS_CLASS]->(c:Class)
        OPTIONAL MATCH (c)-[r]->(other:Class)
        RETURN c, collect(distinct type(r)) as inheritance_types, collect(distinct other.name) as related_classes
        """
        classes_result = neo4j_manager.run_query(classes_query, {"project_id": project_id})
        # Process class metadata with inheritance information
        classes = []
        for record in classes_result:
            class_data = dict(record["c"])
            # Ensure proper serialization of class attributes
            for key in ["superclasses", "interfaces", "methods", "attributes"]:
                if isinstance(class_data.get(key), str):
                    try:
                        class_data[key] = json.loads(class_data[key])
                    except (json.JSONDecodeError, TypeError):
                        class_data[key] = []
            
            class_data.update({
                "inheritance_types": record["inheritance_types"] or [],
                "related_classes": record["related_classes"] or []
            })
            classes.append(class_data)
        
        # Get enum metadata
        enums_query = """
        MATCH (f:File {project_id: $project_id})-[:HAS_ENUM]->(e:Enum)
        RETURN e
        """
        enums_result = neo4j_manager.run_query(enums_query, {"project_id": project_id})
        # Process enum metadata
        enums = []
        for record in enums_result:
            enum_data = dict(record["e"])
            # Ensure values are properly serialized
            if isinstance(enum_data.get("values"), str):
                try:
                    enum_data["values"] = json.loads(enum_data["values"])
                except (json.JSONDecodeError, TypeError):
                    enum_data["values"] = []
            enums.append(enum_data)
        
        # Get extension metadata
        extensions_query = """
        MATCH (f:File {project_id: $project_id})-[:HAS_EXTENSION]->(e:Extension)
        RETURN e
        """
        extensions_result = neo4j_manager.run_query(extensions_query, {"project_id": project_id})
        # Process extension metadata
        extensions = []
        for record in extensions_result:
            extension_data = dict(record["e"])
            # Ensure methods and other attributes are properly serialized
            if isinstance(extension_data.get("methods"), str):
                try:
                    extension_data["methods"] = json.loads(extension_data["methods"])
                except (json.JSONDecodeError, TypeError):
                    extension_data["methods"] = []
            extensions.append(extension_data)
        
        # Get relationship metadata with file paths
        relationships_query = """
        MATCH (f1:File {project_id: $project_id})-[r:IMPORTS|REFERENCES]->(f2:File)
        RETURN f1.relative_path AS source,
               f2.relative_path AS target,
               type(r) AS relationship_type,
               r.imported_items as imported_items,
               r.reference_locations as reference_locations
        """
        relationships_result = neo4j_manager.run_query(relationships_query, {"project_id": project_id})
        # Process relationships with metadata
        relationships = []
        for record in relationships_result:
            rel_data = {
                "source": record["source"],
                "target": record["target"],
                "type": record["relationship_type"],
                "metadata": {
                    "imported_items": record.get("imported_items", []) or [],
                    "reference_locations": record.get("reference_locations", []) or []
                }
            }
            relationships.append(rel_data)
        
        # Prepare summary statistics
        summary = {
            "total_files": len(files),
            "total_functions": len(functions),
            "total_classes": len(classes),
            "total_enums": len(enums),
            "total_extensions": len(extensions),
            "total_relationships": len(relationships)
        }
        
        return MetadataResponse(
            project_id=project_id,
            files=files,
            functions=functions,
            classes=classes,
            enums=enums,
            extensions=extensions,
            relationships=relationships,
            summary=summary,
            last_updated=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                status="error",
                message=f"Error retrieving project metadata: {str(e)}",
                error_code="metadata_retrieval_failed",
                details={
                    "project_id": project_id,
                    "error": str(e)
                }
            ).dict()
        )