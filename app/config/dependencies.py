import sys
import logging
from typing import Optional, Dict, Any

from neo4j.exceptions import ServiceUnavailable, AuthError
import redis.exceptions

from app.config.settings import get_settings
from app.databases.neo4j_manager import Neo4jManager

# Set up logger
logger = logging.getLogger(__name__)
settings = get_settings()


class DependencyInitializer:
    """
    Dependency initializer class using the Singleton pattern.
    Handles initialization of all application dependencies.
    """
    
    _instance = None
    _initialized = False
    _services: Dict[str, Any] = {}
    
    def __new__(cls) -> 'DependencyInitializer':
        """
        Create a new DependencyInitializer instance using the Singleton pattern.
        
        Returns:
            DependencyInitializer: The singleton instance
        """
        if cls._instance is None:
            cls._instance = super(DependencyInitializer, cls).__new__(cls)
        return cls._instance
    
    def initialize_all(self, exit_on_failure: bool = True) -> bool:
        """
        Initialize all application dependencies.
        
        Args:
            exit_on_failure: Whether to exit the application on initialization failure
            
        Returns:
            bool: True if all dependencies initialized successfully, False otherwise
        """
        if self._initialized:
            logger.info("Dependencies already initialized")
            return True
        
        logger.info("Initializing application dependencies")
        
        # Initialize Neo4j
        if not self.initialize_neo4j(exit_on_failure):
            return False
            
        # Initialize Redis
        if not self.initialize_redis(exit_on_failure):
            return False
            
        # Initialize storage directories
        if not self.initialize_storage(exit_on_failure):
            return False
        
        self._initialized = True
        logger.info("All dependencies initialized successfully")
        return True
    
    def initialize_neo4j(self, exit_on_failure: bool = True) -> bool:
        """
        Initialize Neo4j connection.
        
        Args:
            exit_on_failure: Whether to exit the application on initialization failure
            
        Returns:
            bool: True if Neo4j initialized successfully, False otherwise
        """
        try:
            logger.info("Initializing Neo4j connection")
            
            # Neo4jManager is already a singleton, we just need to trigger initialization
            neo4j_manager = Neo4jManager()
            
            # Test connectivity
            neo4j_manager.driver.verify_connectivity()
            
            self._services["neo4j"] = neo4j_manager
            logger.info("Neo4j connection initialized successfully")
            return True
            
        except (ServiceUnavailable, AuthError) as e:
            error_message = f"Failed to initialize Neo4j: {str(e)}"
            logger.error(error_message)
            
            if exit_on_failure:
                logger.critical("Critical dependency Neo4j failed to initialize. Exiting application.")
                sys.exit(1)
                
            return False
    
    def initialize_redis(self, exit_on_failure: bool = True) -> bool:
        """
        Initialize Redis connection.
        
        Args:
            exit_on_failure: Whether to exit the application on initialization failure
            
        Returns:
            bool: True if Redis initialized successfully, False otherwise
        """
        try:
            logger.info("Initializing Redis connection")
            
            # Import Redis here to avoid circular imports
            import redis
            
            # Create Redis connection
            redis_client = redis.from_url(
                settings.CELERY_BROKER_URL,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # Test connection
            redis_client.ping()
            
            self._services["redis"] = redis_client
            logger.info("Redis connection initialized successfully")
            return True
            
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            error_message = f"Failed to initialize Redis: {str(e)}"
            logger.error(error_message)
            
            if exit_on_failure:
                logger.critical("Critical dependency Redis failed to initialize. Exiting application.")
                sys.exit(1)
                
            return False
        except ImportError as e:
            error_message = f"Failed to import Redis: {str(e)}"
            logger.error(error_message)
            
            if exit_on_failure:
                logger.critical("Critical dependency Redis failed to initialize. Exiting application.")
                sys.exit(1)
                
            return False
    
    def initialize_storage(self, exit_on_failure: bool = True) -> bool:
        """
        Initialize storage directories.
        
        Args:
            exit_on_failure: Whether to exit the application on initialization failure
            
        Returns:
            bool: True if storage directories initialized successfully, False otherwise
        """
        try:
            import os
            
            logger.info("Initializing storage directories")
            
            # Create temp directory
            os.makedirs(settings.TEMP_DIR, exist_ok=True)
            logger.info(f"Temporary directory initialized: {settings.TEMP_DIR}")
            
            # Create storage directory
            os.makedirs(settings.STORAGE_DIR, exist_ok=True)
            logger.info(f"Storage directory initialized: {settings.STORAGE_DIR}")
            
            return True
            
        except PermissionError as e:
            error_message = f"Failed to initialize storage directories due to permission error: {str(e)}"
            logger.error(error_message)
            
            if exit_on_failure:
                logger.critical("Critical dependency storage directories failed to initialize. Exiting application.")
                sys.exit(1)
                
            return False
        except Exception as e:
            error_message = f"Failed to initialize storage directories: {str(e)}"
            logger.error(error_message)
            
            if exit_on_failure:
                logger.critical("Critical dependency storage directories failed to initialize. Exiting application.")
                sys.exit(1)
                
            return False
    
    def get_service(self, service_name: str) -> Optional[Any]:
        """
        Get a service by name.
        
        Args:
            service_name: Name of the service to get
            
        Returns:
            The service instance or None if not found
        """
        return self._services.get(service_name)


# Create a singleton instance
dependency_initializer = DependencyInitializer() 