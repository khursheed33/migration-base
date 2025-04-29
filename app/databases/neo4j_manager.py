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

# Create a singleton instance but don't initialize yet
neo4j_manager = Neo4jManager() 