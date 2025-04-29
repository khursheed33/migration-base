from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Optional

from app.schemas import GraphResponse, ErrorResponse
from app.config.dependencies import dependency_initializer

router = APIRouter()


@router.get(
    "/{project_id}/graph",
    response_model=GraphResponse,
    responses={
        200: {"model": GraphResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_project_graph(
    project_id: str,
    node_types: Optional[List[str]] = Query(None, description="Types of nodes to include (e.g., File, Function)"),
    relationship_types: Optional[List[str]] = Query(None, description="Types of relationships to include (e.g., CONTAINS, IMPORTS)"),
):
    """
    Get the Neo4j graph data for a project, including nodes and relationships.
    Optionally filter by node types and relationship types.
    
    Args:
        project_id: Project ID
        node_types: Optional list of node types to include (e.g., File, Function)
        relationship_types: Optional list of relationship types to include (e.g., CONTAINS, IMPORTS)
        
    Returns:
        Project graph data
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
        
        # Build node query
        node_type_filter = ""
        if node_types and len(node_types) > 0:
            node_type_filter = " WHERE " + " OR ".join([f"labels(n) CONTAINS '{node_type}'" for node_type in node_types])
        
        nodes_query = f"""
        MATCH (n)
        WHERE n.project_id = $project_id
        {node_type_filter}
        RETURN n, labels(n) AS node_labels
        """
        
        # Get nodes
        nodes_result = neo4j_manager.run_query(nodes_query, {"project_id": project_id})
        
        # Build relationship query
        rel_type_filter = ""
        if relationship_types and len(relationship_types) > 0:
            rel_type_filter = " WHERE " + " OR ".join([f"type(r) = '{rel_type}'" for rel_type in relationship_types])
        
        relationships_query = f"""
        MATCH (n1)-[r]->(n2)
        WHERE n1.project_id = $project_id AND n2.project_id = $project_id
        {rel_type_filter}
        RETURN n1, r, n2
        """
        
        # Get relationships
        relationships_result = neo4j_manager.run_query(relationships_query, {"project_id": project_id})
        
        # Process nodes
        nodes = []
        for record in nodes_result:
            node = record["n"]
            node_labels = record["node_labels"]
            
            # Add node_type field
            node_type = node_labels[0] if node_labels else "Unknown"
            node_data = dict(node)
            node_data["node_type"] = node_type
            
            nodes.append(node_data)
        
        # Process relationships
        relationships = []
        for record in relationships_result:
            source = record["n1"]
            target = record["n2"]
            relationship = record["r"]
            
            # Create relationship data
            rel_data = {
                "source_id": source.get("file_id") or source.get("project_id") or source.get("function_id") or source.get("class_id"),
                "target_id": target.get("file_id") or target.get("project_id") or target.get("function_id") or target.get("class_id"),
                "relationship_type": type(relationship).__name__,
                "properties": dict(relationship)
            }
            
            relationships.append(rel_data)
        
        # Return graph response
        return GraphResponse(
            project_id=project_id,
            nodes=nodes,
            relationships=relationships
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                status="error",
                message=f"Error retrieving project graph: {str(e)}",
                error_code="graph_retrieval_failed"
            ).dict()
        ) 