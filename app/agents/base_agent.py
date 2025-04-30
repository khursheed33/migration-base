import abc
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from app.config.dependencies import dependency_initializer
from app.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class BaseAgent(abc.ABC):
    """
    Base agent class that all agents will inherit from.
    Provides common functionality for agents.
    """
    
    def __init__(self, project_id: str):
        """
        Initialize the base agent.
        
        Args:
            project_id: The project ID
        """
        self.project_id = project_id
        # Get the Neo4j manager from the dependency initializer
        self.db = dependency_initializer.get_service("neo4j")
        if self.db is None:
            logger.error(f"Neo4j service not available for agent {self.__class__.__name__}")
            raise RuntimeError("Neo4j service not available")
            
        self.logger = logger
    
    @abc.abstractmethod
    async def execute(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """
        Execute the agent's main functionality.
        Must be implemented by all subclasses.
        
        Returns:
            Dictionary containing execution results
        """
        pass
    
    def update_project_status(self, status: str, progress: float = 0.0, current_step: str = "") -> None:
        """
        Update the project status in the database.
        
        Args:
            status: The project status
            progress: The progress percentage (0-100)
            current_step: The current migration step
        """
        self.logger.info(f"Updating project {self.project_id} status to {status}, progress: {progress}%")
        
        try:
            # Get the current project
            project = self.db.find_node("Project", "project_id", self.project_id)
            if not project:
                self.logger.error(f"Project {self.project_id} not found")
                return
            
            # Update the project status
            query = """
            MATCH (p:Project {project_id: $project_id})
            SET p.status = $status, 
                p.progress = $progress, 
                p.current_step = $current_step,
                p.updated_at = $updated_at
            RETURN p
            """
            parameters = {
                "project_id": self.project_id,
                "status": status,
                "progress": progress,
                "current_step": current_step,
                "updated_at": datetime.utcnow().isoformat()
            }
            self.db.run_query(query, parameters)
        except Exception as e:
            self.logger.error(f"Error updating project status: {str(e)}")
    
    def log_error(self, error_message: str, error_details: Optional[Dict[str, Any]] = None) -> None:
        """
        Log an error for the project.
        
        Args:
            error_message: The error message
            error_details: Additional error details
        """
        self.logger.error(f"Project {self.project_id} error: {error_message}")
        
        try:
            # Create an error report
            query = """
            MATCH (p:Project {project_id: $project_id})
            CREATE (r:Report {
                report_id: $report_id,
                project_id: $project_id,
                type: 'error',
                message: $message,
                details: $details,
                created_at: $created_at
            })
            CREATE (p)-[:REPORTED_IN]->(r)
            RETURN r
            """
            parameters = {
                "report_id": str(uuid.uuid4()),
                "project_id": self.project_id,
                "message": error_message,
                "details": error_details or {},
                "created_at": datetime.utcnow().isoformat()
            }
            self.db.run_query(query, parameters)
        except Exception as e:
            self.logger.error(f"Error logging error report: {str(e)}")
    
    def create_report(
        self,
        report_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a report node in Neo4j.
        
        Args:
            report_type: Type of report
            message: Report message
            details: Additional report details
            
        Returns:
            Created report node
        """
        try:
            # Ensure details are primitive types
            serialized_details = {}
            if details:
                for key, value in details.items():
                    # Convert non-primitive types to strings
                    if isinstance(value, (dict, list)):
                        serialized_details[key] = str(value)
                    else:
                        serialized_details[key] = value

            report_id = str(uuid.uuid4())
            report_properties = {
                "report_id": report_id,
                "project_id": self.project_id,
                "type": report_type,
                "message": message,
                "details": serialized_details,
                "created_at": datetime.utcnow().isoformat()
            }
            
            report_node = self.db.create_node("Report", report_properties)
            
            # Create relationship from Project to Report
            self.db.create_relationship(
                from_label="Project",
                from_property="project_id",
                from_value=self.project_id,
                to_label="Report",
                to_property="report_id",
                to_value=report_id,
                relationship_type="HAS_REPORT"
            )
            
            self.logger.info(f"Created {report_type} report for project {self.project_id}")
            return report_node
            
        except Exception as e:
            error_message = f"Error creating report: {str(e)}"
            self.logger.error(error_message)
            raise