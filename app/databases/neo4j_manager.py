from functools import wraps
import logging
from typing import Any, Callable, Dict, List, Optional, Union, TypeVar, cast

from neo4j import GraphDatabase, Session, Driver, Result
from neo4j.exceptions import ServiceUnavailable, AuthError

from app.config.settings import get_settings

settings = get_settings()

# Set up logger
logger = logging.getLogger(__name__)

T = TypeVar('T')

def _serialize_node(node_data: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize node data to ensure proper JSON conversion."""
    result = {}
    for key, value in node_data.items():
        if isinstance(value, (str, int, float, bool, type(None))):
            result[key] = value
        elif isinstance(value, (list, tuple)):
            result[key] = [_serialize_node(item) if isinstance(item, dict) else item for item in value]
        elif isinstance(value, dict):
            result[key] = _serialize_node(value)
        else:
            result[key] = str(value)  # Convert any other types to string
    return result

class Neo4jManager:
    """
    Neo4j database manager using the Singleton pattern.
    Handles connections, sessions, and transactions with Neo4j.
    """
    
    _instance = None
    _driver = None
    
    def __new__(cls) -> 'Neo4jManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_driver()
        return cls._instance
    
    def _init_driver(self) -> None:
        """Initialize the Neo4j driver with authentication."""
        try:
            self._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
        except (ServiceUnavailable, AuthError) as e:
            logger.error(f"Failed to initialize Neo4j driver: {str(e)}")
            raise
    
    @property
    def driver(self) -> Driver:
        """Get the Neo4j driver instance."""
        if not self._driver:
            self._init_driver()
        return self._driver
    
    def get_session(self) -> Session:
        """Get a new Neo4j session."""
        return self.driver.session()
    
    def close(self) -> None:
        """Close the Neo4j driver connection."""
        if self._driver:
            self._driver.close()
            self._driver = None
    
    def run_query(
        self, 
        query: str, 
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Run a Cypher query and return the result as a list of dictionaries.
        
        Args:
            query: Cypher query string
            parameters: Query parameters (optional)
            
        Returns:
            List of dictionaries containing the query results
        """
        with self.get_session() as session:
            result = session.run(query, parameters or {})
            # Serialize the records to ensure proper JSON conversion
            return [
                {key: _serialize_node(value) if isinstance(value, dict) else value 
                 for key, value in record.data().items()}
                for record in result
            ]
    
    def run_transaction(
        self, 
        tx_function: Callable[[Session], T], 
        *args: Any, 
        **kwargs: Any
    ) -> T:
        """
        Run a function in a transaction.
        
        Args:
            tx_function: Function to run in transaction
            args: Positional arguments for the function
            kwargs: Keyword arguments for the function
            
        Returns:
            Result of the transaction function
        """
        with self.get_session() as session:
            return session.execute_write(tx_function, *args, **kwargs)

    def find_node(
        self, 
        label: str, 
        property_name: str, 
        property_value: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Find a node by label and property.
        
        Args:
            label: Node label
            property_name: Property name
            property_value: Property value
            
        Returns:
            Dictionary representing the node, or None if not found
        """
        query = f"""
        MATCH (n:{label})
        WHERE n.{property_name} = $value
        RETURN n
        """
        result = self.run_query(query, {"value": property_value})
        if not result:
            return None
        
        # Ensure proper serialization of node data
        return _serialize_node(result[0]['n'])
        
    def create_node(
        self, 
        label: str, 
        properties: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a node with the given label and properties.
        
        Args:
            label: Node label
            properties: Node properties
            
        Returns:
            Dictionary representing the created node
        """
        query = f"""
        CREATE (n:{label} $properties)
        RETURN n
        """
        result = self.run_query(query, {"properties": properties})
        return _serialize_node(result[0]['n']) if result else {}
        
    def create_relationship(
        self, 
        from_label: str, 
        from_property: str, 
        from_value: Any,
        to_label: str, 
        to_property: str, 
        to_value: Any,
        relationship_type: str, 
        properties: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a relationship between two nodes.
        
        Args:
            from_label: Label of the source node
            from_property: Property name to identify the source node
            from_value: Property value to identify the source node
            to_label: Label of the target node
            to_property: Property name to identify the target node
            to_value: Property value to identify the target node
            relationship_type: Type of relationship
            properties: Relationship properties (optional)
            
        Returns:
            Dictionary representing the created relationship
        """
        query = f"""
        MATCH (a:{from_label}), (b:{to_label})
        WHERE a.{from_property} = $from_value AND b.{to_property} = $to_value
        CREATE (a)-[r:{relationship_type} $properties]->(b)
        RETURN r
        """
        result = self.run_query(
            query, 
            {
                "from_value": from_value,
                "to_value": to_value,
                "properties": properties or {}
            }
        )
        return result[0]['r'] if result else {}
    
    def create_nodes_batch(
        self,
        label: str,
        properties_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Create multiple nodes with the same label in a single transaction.
        
        Args:
            label: Node label
            properties_list: List of property dictionaries for each node
            
        Returns:
            List of dictionaries representing the created nodes
        """
        if not properties_list:
            return []
            
        def _create_nodes_tx(tx, props_list):
            query = f"""
            UNWIND $props_list AS props
            CREATE (n:{label}) SET n = props
            RETURN n
            """
            result = tx.run(query, props_list=props_list)
            return [_serialize_node(record["n"]) for record in result]
        
        return self.run_transaction(_create_nodes_tx, properties_list)
        
    def create_relationships_batch(
        self,
        relationships: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Create multiple relationships in a single transaction.
        
        Args:
            relationships: List of dictionaries containing relationship info:
                {
                    'from_label': str,
                    'from_property': str,
                    'from_value': Any,
                    'to_label': str,
                    'to_property': str,
                    'to_value': Any,
                    'relationship_type': str,
                    'properties': Optional[Dict[str, Any]]
                }
                
        Returns:
            List of dictionaries representing the created relationships
        """
        if not relationships:
            return []
            
        results = []
        # Process in batches of similar relationship types
        relationship_types = {}
        
        for rel in relationships:
            rel_type = rel['relationship_type']
            if rel_type not in relationship_types:
                relationship_types[rel_type] = []
            relationship_types[rel_type].append(rel)
        
        for rel_type, rels in relationship_types.items():
            def _create_relationships_tx(tx, rel_data, rel_type):
                query = f"""
                UNWIND $rels AS rel
                MATCH (a:{{}}) WHERE a[rel.from_property] = rel.from_value
                MATCH (b:{{}}) WHERE b[rel.to_property] = rel.to_value
                CREATE (a)-[r:{rel_type}]->(b)
                SET r = rel.properties
                RETURN r
                """
                # Substitute the labels dynamically
                query = query.format(rel_data[0]['from_label'], rel_data[0]['to_label'])
                
                # Prepare data
                data = []
                for rel in rel_data:
                    data.append({
                        'from_property': rel['from_property'],
                        'from_value': rel['from_value'],
                        'to_property': rel['to_property'],
                        'to_value': rel['to_value'],
                        'properties': rel.get('properties', {})
                    })
                
                result = tx.run(query, rels=data)
                return [record.data() for record in result]
            
            batch_results = self.run_transaction(_create_relationships_tx, rels, rel_type)
            results.extend(batch_results)
        
        return results

neo4j_manager = Neo4jManager()