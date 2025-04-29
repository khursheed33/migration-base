import os
import uuid
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.agents.base_agent import BaseAgent
from app.databases import neo4j_manager
from app.config.settings import get_settings

settings = get_settings()


class StructureAnalysisAgent(BaseAgent):
    """
    Agent for analyzing project structure and storing file metadata.
    Acts as a sub-agent of the Analysis Agent.
    """
    
    async def execute(self, project_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the structure analysis agent's main functionality.
        
        Args:
            project_dir: Optional path to the project directory. If not provided, 
                         it will be retrieved from the database.
        
        Returns:
            Dictionary containing execution results
        """
        self.logger.info(f"Starting StructureAnalysisAgent for project {self.project_id}")
        
        try:
            # Get project directory if not provided
            if not project_dir:
                project = self.db.find_node("Project", "project_id", self.project_id)
                if not project:
                    error_message = f"Project {self.project_id} not found"
                    self.log_error(error_message)
                    return {"success": False, "error": error_message}
                
                project_dir = project.get("temp_dir")
            
            if not os.path.exists(project_dir):
                error_message = f"Project directory {project_dir} does not exist"
                self.log_error(error_message)
                return {"success": False, "error": error_message}
            
            # Update project status
            self.update_project_status(
                status="analyzing_structure",
                progress=15.0,
                current_step="Analyzing project structure"
            )
            
            # Analyze project structure
            file_count = 0
            file_nodes = []
            
            # Walk through the project directory
            for root, dirs, files in os.walk(project_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, project_dir)
                    
                    # Skip hidden files and directories
                    if file.startswith('.') or '/.' in relative_path or '\\.' in relative_path:
                        continue
                    
                    # Get file metadata
                    file_type = self._get_file_type(file_path)
                    file_size = os.path.getsize(file_path)
                    
                    # Create File node
                    file_node = self._create_file_node(
                        file_path=file_path,
                        relative_path=relative_path,
                        file_type=file_type,
                        file_size=file_size
                    )
                    
                    file_nodes.append(file_node)
                    file_count += 1
            
            # Update project status
            self.update_project_status(
                status="structure_analyzed",
                progress=20.0,
                current_step="Project structure analyzed"
            )
            
            # Create a report
            self.create_report(
                report_type="structure_analysis",
                message=f"Analyzed {file_count} files in project structure",
                details={
                    "file_count": file_count,
                    "project_dir": project_dir
                }
            )
            
            return {
                "success": True,
                "file_count": file_count,
                "file_nodes": file_nodes,
                "project_dir": project_dir
            }
            
        except Exception as e:
            error_message = f"Error in StructureAnalysisAgent: {str(e)}"
            self.log_error(error_message)
            return {"success": False, "error": error_message}
    
    def _get_file_type(self, file_path: str) -> str:
        """
        Determine the file type based on extension and content.
        
        Args:
            file_path: Path to the file
            
        Returns:
            File type
        """
        file_extension = os.path.splitext(file_path)[1].lower()
        
        # Map common extensions to language types
        extension_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'react',
            '.tsx': 'react',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.sass': 'sass',
            '.java': 'java',
            '.kt': 'kotlin',
            '.kts': 'kotlin',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c_header',
            '.hpp': 'cpp_header',
            '.cs': 'csharp',
            '.go': 'go',
            '.rs': 'rust',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.m': 'objective_c',
            '.mm': 'objective_cpp',
            '.sql': 'sql',
            '.json': 'json',
            '.xml': 'xml',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.md': 'markdown',
            '.cob': 'cobol',
            '.cbl': 'cobol',
            '.dpr': 'delphi',
            '.pas': 'pascal',
            '.f': 'fortran',
            '.f90': 'fortran',
            '.sh': 'shell',
            '.bat': 'batch',
            '.ps1': 'powershell',
            '.config': 'config',
            '.toml': 'toml',
            '.ini': 'ini',
            '.csv': 'csv',
            '.txt': 'text'
        }
        
        file_type = extension_map.get(file_extension, None)
        
        if file_type:
            return file_type
        
        # If extension not found in map, use MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type:
            return mime_type.split('/')[0]
        
        # Fallback to generic type
        return 'unknown'
    
    def _create_file_node(
        self, 
        file_path: str, 
        relative_path: str, 
        file_type: str, 
        file_size: int
    ) -> Dict[str, Any]:
        """
        Create a File node in Neo4j.
        
        Args:
            file_path: Absolute path to the file
            relative_path: Relative path from project root
            file_type: Type of file
            file_size: Size of file in bytes
            
        Returns:
            Created File node
        """
        # Create file properties
        file_properties = {
            "file_id": f"file_{uuid.uuid4().hex[:8]}",
            "project_id": self.project_id,
            "file_path": file_path,
            "relative_path": relative_path,
            "file_type": file_type,
            "size": file_size,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Create File node
        file_node = self.db.create_node("File", file_properties)
        
        # Create relationship to Project
        self.db.create_relationship(
            from_label="Project",
            from_property="project_id",
            from_value=self.project_id,
            to_label="File",
            to_property="file_id",
            to_value=file_properties["file_id"],
            relationship_type="CONTAINS"
        )
        
        return file_node 