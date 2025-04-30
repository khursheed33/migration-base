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

class Neo4jManager:
    """
    Neo4j database manager using the Singleton pattern.
    Handles connections, sessions, and transactions with Neo4j.
    """
    
    _instance = None
    _driver = None
    
    def __new__(cls) -> 'Neo4jManager':
        """
        Create a new Neo4jManager instance using the Singleton pattern.
        
        Returns:
            Neo4jManager: The singleton instance
        """
        if cls._instance is None:
            cls._instance = super(Neo4jManager, cls).__new__(cls)
            # Don't initialize driver here, let the dependency initializer handle it
        return cls._instance
    
    def _init_driver(self) -> None:
        """Initialize the Neo4j driver with authentication."""
        try:
            self._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            # Verify the connection
            self._driver.verify_connectivity()
            logger.info("Connected to Neo4j database successfully")
        except (ServiceUnavailable, AuthError) as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            raise
    
    @property
    def driver(self) -> Driver:
        """
        Get the Neo4j driver instance.
        
        Returns:
            Driver: Neo4j driver
        """
        if self._driver is None:
            self._init_driver()
        return self._driver
    
    def get_session(self) -> Session:
        """
        Create a new Neo4j session.
        
        Returns:
            Session: Neo4j session
        """
        return self.driver.session()
    
    def close(self) -> None:
        """Close the Neo4j driver connection."""
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j connection closed")
    
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
            return [record.data() for record in result]
    
    def run_transaction(
        self, 
        tx_function: Callable[[Session], T], 
        *args: Any, 
        **kwargs: Any
    ) -> T:
        """
        Run a function within a transaction.
        
        Args:
            tx_function: Function to run within the transaction
            *args: Additional arguments for tx_function
            **kwargs: Additional keyword arguments for tx_function
            
        Returns:
            The result of tx_function
        """
        with self.get_session() as session:
            result = session.execute_write(tx_function, *args, **kwargs)
            return cast(T, result)

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
        return result[0]['n'] if result else {}
    
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
        return result[0]['n'] if result else None
        
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
        def _create_nodes_tx(tx, label, props_list):
            query = f"""
            UNWIND $props_list AS props
            CREATE (n:{label} props)
            RETURN n
            """
            result = tx.run(query, props_list=props_list)
            return [record["n"] for record in result]
        
        return self.run_transaction(_create_nodes_tx, label, properties_list)
        
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
        def _create_relationships_tx(tx, rels):
            query = """
            UNWIND $rels AS rel
            MATCH (a), (b)
            WHERE a[rel.from_property] = rel.from_value 
            AND b[rel.to_property] = rel.to_value
            AND labels(a)[0] = rel.from_label 
            AND labels(b)[0] = rel.to_label
            CREATE (a)-[r:PLACEHOLDER_REL]->(b)
            SET r = rel.properties
            RETURN type(r) as rel_type, id(r) as rel_id
            """
            # Neo4j doesn't allow parameterizing relationship types
            # So we'll do this in multiple steps
            results = []
            for rel in rels:
                rel_type = rel['relationship_type']
                custom_query = query.replace('PLACEHOLDER_REL', rel_type)
                result = tx.run(
                    custom_query,
                    rels=[{
                        'from_property': rel['from_property'],
                        'from_value': rel['from_value'],
                        'to_property': rel['to_property'],
                        'to_value': rel['to_value'],
                        'from_label': rel['from_label'],
                        'to_label': rel['to_label'],
                        'properties': rel.get('properties', {})
                    }]
                )
                results.extend(list(result))
            
            return results
        
        return self.run_transaction(_create_relationships_tx, relationships)

# Create a singleton instance but don't initialize yet
neo4j_manager = Neo4jManager() 