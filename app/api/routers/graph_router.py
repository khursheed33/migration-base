from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
import uuid
import json

from app.schemas import GraphResponse, ErrorResponse, GraphNode, GraphRelationship
from app.config.dependencies import dependency_initializer
from app.utils.constants import RelationshipType

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
    relationship_types: Optional[List[str]] = Query(None, description=f"Types of relationships to include (e.g., {RelationshipType.CONTAINS}, {RelationshipType.IMPORTS})"),
):
    """
    Get the Neo4j graph data for a project, including nodes and relationships.
    Optionally filter by node types and relationship types.
    
    Args:
        project_id: Project ID
        node_types: Optional list of node types to include (e.g., File, Function)
        relationship_types: Optional list of relationship types to include (e.g., {RelationshipType.CONTAINS}, {RelationshipType.IMPORTS})
        
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
            
            # Add node_type field and ensure node_id exists
            node_type = node_labels[0] if node_labels else "Unknown"
            node_data = dict(node)
            
            # Ensure node has an ID
            if "id" not in node_data:
                node_data["id"] = f"{node_type.lower()}_{str(uuid.uuid4())}"
            
            # Handle special property types
            if isinstance(node_data.get("custom_mappings"), str):
                try:
                    node_data["custom_mappings"] = json.loads(node_data["custom_mappings"])
                except json.JSONDecodeError:
                    node_data["custom_mappings"] = {}
            
            if isinstance(node_data.get("metadata"), str):
                try:
                    node_data["metadata"] = json.loads(node_data["metadata"])
                except json.JSONDecodeError:
                    node_data["metadata"] = {}
            
            # Create GraphNode instance
            graph_node = GraphNode(
                node_id=node_data["id"],
                node_type=node_type,
                properties=node_data
            )
            nodes.append(graph_node)
        
        # Process relationships
        relationships = []
        for record in relationships_result:
            source = record["n1"]
            target = record["n2"]
            relationship = record["r"]
            
            # Ensure source and target IDs exist
            source_id = source.get("id") or source.get("project_id") or source.get("file_id") or source.get("function_id") or source.get("class_id") or str(uuid.uuid4())
            target_id = target.get("id") or target.get("project_id") or target.get("file_id") or target.get("function_id") or target.get("class_id") or str(uuid.uuid4())
            
            # Get relationship properties and handle special types
            rel_props = dict(relationship)
            if isinstance(rel_props.get("metadata"), str):
                try:
                    rel_props["metadata"] = json.loads(rel_props["metadata"])
                except json.JSONDecodeError:
                    rel_props["metadata"] = {}
            
            # Create GraphRelationship instance
            rel_data = GraphRelationship(
                source_id=source_id,
                target_id=target_id,
                relationship_type=type(relationship).__name__,
                properties=rel_props
            )
            relationships.append(rel_data)
        
        # Return graph response with proper data types
        response_data = {
            "project_id": project_id,
            "nodes": [node.dict() for node in nodes],
            "relationships": [rel.dict() for rel in relationships]
        }
        return GraphResponse(**response_data)
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                status="error",
                message=f"Error retrieving project graph: {str(e)}",
                error_code="graph_retrieval_failed"
            ).dict()
        )

@router.get(
    "/{project_id}/nodes/{node_id}/expand",
    response_model=GraphResponse,
    responses={
        200: {"model": GraphResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def expand_node(
    project_id: str,
    node_id: str,
    depth: int = Query(1, description="Depth of expansion (default: 1)"),
    direction: str = Query("both", description="Direction of relationships to traverse: 'incoming', 'outgoing', or 'both'"),
    relationship_types: Optional[List[str]] = Query(None, description="Types of relationships to include"),
    node_types: Optional[List[str]] = Query(None, description="Types of nodes to include"),
):
    """
    Expand a node to see its connections up to a specified depth.
    
    Args:
        project_id: Project ID
        node_id: ID of the node to expand
        depth: How many levels to expand from the node (default: 1)
        direction: Direction of relationships to follow ('incoming', 'outgoing', or 'both')
        relationship_types: Optional list of relationship types to include
        node_types: Optional list of node types to include
        
    Returns:
        Subgraph containing the requested node and its connections
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
        
        # Build direction part of the query
        direction_query = "r"  # Default for 'both'
        if direction == "incoming":
            direction_query = "<-[r]-"
        elif direction == "outgoing":
            direction_query = "-[r]->"
        else:  # 'both'
            direction_query = "-[r]-"
        
        # Build relationship filter
        rel_filter = ""
        if relationship_types and len(relationship_types) > 0:
            rel_conditions = " OR ".join([f"type(r) = '{rel_type}'" for rel_type in relationship_types])
            rel_filter = f" WHERE {rel_conditions}"
        
        # Build node type filter
        node_filter = ""
        if node_types and len(node_types) > 0:
            node_conditions = " OR ".join([f"any(label IN labels(connected) WHERE label = '{node_type}')" for node_type in node_types])
            node_filter = f" AND ({node_conditions})" if rel_filter else f" WHERE {node_conditions}"
        
        # Query to get the starting node and all connected nodes up to specified depth
        query = f"""
        MATCH (start)
        WHERE start.id = $node_id AND start.project_id = $project_id
        OPTIONAL MATCH path = (start){direction_query}(connected)
        WHERE connected.project_id = $project_id{rel_filter}{node_filter}
        WITH collect(path) AS paths
        UNWIND paths AS p
        RETURN nodes(p) AS nodes, relationships(p) AS rels
        """
        
        # Execute query
        result = neo4j_manager.run_query(query, {"node_id": node_id, "project_id": project_id})
        
        # Process results
        all_nodes = {}
        all_relationships = {}
        
        for record in result:
            # Process nodes
            for node in record.get("nodes", []):
                if node is None:
                    continue
                
                node_data = dict(node)
                node_labels = list(node.labels)
                node_type = node_labels[0] if node_labels else "Unknown"
                
                # Ensure node has an ID
                if "id" not in node_data:
                    node_data["id"] = f"{node_type.lower()}_{str(uuid.uuid4())}"
                
                # Handle special property types
                if isinstance(node_data.get("custom_mappings"), str):
                    try:
                        node_data["custom_mappings"] = json.loads(node_data["custom_mappings"])
                    except json.JSONDecodeError:
                        node_data["custom_mappings"] = {}
                
                if isinstance(node_data.get("metadata"), str):
                    try:
                        node_data["metadata"] = json.loads(node_data["metadata"])
                    except json.JSONDecodeError:
                        node_data["metadata"] = {}
                
                # Add to collection if not already present
                node_id_val = node_data["id"]
                if node_id_val not in all_nodes:
                    all_nodes[node_id_val] = GraphNode(
                        node_id=node_id_val,
                        node_type=node_type,
                        properties=node_data
                    )
            
            # Process relationships
            for rel in record.get("rels", []):
                if rel is None:
                    continue
                
                # Get source and target node IDs
                source_id = dict(rel.start_node).get("id")
                target_id = dict(rel.end_node).get("id")
                
                if not source_id or not target_id:
                    continue
                
                # Get relationship properties and type
                rel_props = dict(rel)
                rel_type = type(rel).__name__
                rel_id = f"{source_id}_{rel_type}_{target_id}"
                
                # Handle special property types
                if isinstance(rel_props.get("metadata"), str):
                    try:
                        rel_props["metadata"] = json.loads(rel_props["metadata"])
                    except json.JSONDecodeError:
                        rel_props["metadata"] = {}
                
                # Add to collection if not already present
                if rel_id not in all_relationships:
                    all_relationships[rel_id] = GraphRelationship(
                        source_id=source_id,
                        target_id=target_id,
                        relationship_type=rel_type,
                        properties=rel_props
                    )
        
        # If node wasn't found, return 404
        if not all_nodes:
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    status="error",
                    message=f"Node {node_id} not found in project {project_id}",
                    error_code="node_not_found"
                ).dict()
            )
        
        # Return graph response
        response_data = {
            "project_id": project_id,
            "nodes": [node.dict() for node in all_nodes.values()],
            "relationships": [rel.dict() for rel in all_relationships.values()]
        }
        return GraphResponse(**response_data)
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                status="error",
                message=f"Error expanding node: {str(e)}",
                error_code="node_expansion_failed"
            ).dict()
        )