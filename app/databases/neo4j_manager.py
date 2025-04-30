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

neo4j_manager = Neo4jManager()