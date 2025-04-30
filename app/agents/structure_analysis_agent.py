import os
import uuid
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

from app.agents.base_agent import BaseAgent
from app.databases import neo4j_manager
from app.config.settings import get_settings
from app.utils.constants import RelationshipType, NodeType

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
            
            # Process project structure
            result = await self._process_project_structure(project_dir)
            
            if not result["success"]:
                return result
            
            # Update project status
            self.update_project_status(
                status="structure_analyzed",
                progress=20.0,
                current_step="Project structure analyzed"
            )
            
            # Create a report
            self.create_report(
                report_type="structure_analysis",
                message=f"Analyzed {result['file_count']} files and {result['folder_count']} folders in project structure",
                details={
                    "file_count": result["file_count"],
                    "folder_count": result["folder_count"],
                    "project_dir": project_dir
                }
            )
            
            return {
                "success": True,
                "file_count": result["file_count"],
                "folder_count": result["folder_count"],
                "file_nodes": result["file_nodes"],
                "folder_nodes": result["folder_nodes"],
                "project_dir": project_dir
            }
            
        except Exception as e:
            error_message = f"Error in StructureAnalysisAgent: {str(e)}"
            self.log_error(error_message)
            return {"success": False, "error": error_message}
    
    async def _process_project_structure(self, project_dir: str) -> Dict[str, Any]:
        """
        Process project structure and create nodes/relationships in Neo4j.
        
        Args:
            project_dir: Path to the project directory
            
        Returns:
            Dictionary containing processing results
        """
        try:
            project_path = Path(project_dir)
            file_count = 0
            folder_count = 0
            file_nodes = []
            folder_nodes = []
            folder_map = {}  # Maps path to folder_id
            created_folders = set()  # Track created folders
            
            # Create root folder node
            root_folder_id = str(uuid.uuid4())
            root_folder = {
                "folder_id": root_folder_id,
                "project_id": self.project_id,
                "folder_path": str(project_path),
                "relative_path": ".",
                "name": project_path.name,
                "is_root": True,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            folder_node = self.db.create_node("Folder", root_folder)
            folder_nodes.append(folder_node)
            folder_map[str(project_path)] = root_folder_id
            created_folders.add(str(project_path))
            folder_count += 1
            
            # Create relationship from Project to root folder
            self.db.create_relationship(
                from_label=NodeType.PROJECT,
                from_property="project_id",
                from_value=self.project_id,
                to_label=NodeType.FOLDER,
                to_property="folder_id",
                to_value=root_folder_id,
                relationship_type=RelationshipType.CONTAINS
            )
            
            # Prepare file and folder nodes
            file_properties_list = []
            folder_properties_list = []
            relationships = []
            
            # Walk through the project directory
            for root, dirs, files in os.walk(project_dir):
                current_path = Path(root)
                relative_path = current_path.relative_to(project_path)
                relative_path_str = str(relative_path).replace('\\', '/') if str(relative_path) != '.' else '.'
                
                # Ensure parent folders are created
                parent_path = current_path.parent
                if str(current_path) != str(project_path) and str(current_path) not in created_folders:
                    # Create folder node
                    folder_id = str(uuid.uuid4())
                    folder_properties = {
                        "folder_id": folder_id,
                        "project_id": self.project_id,
                        "folder_path": str(current_path),
                        "relative_path": relative_path_str,
                        "name": current_path.name,
                        "is_root": False,
                        "created_at": datetime.utcnow().isoformat(),
                        "updated_at": datetime.utcnow().isoformat()
                    }
                    
                    folder_properties_list.append(folder_properties)
                    folder_map[str(current_path)] = folder_id
                    created_folders.add(str(current_path))
                    folder_count += 1
                    
                    # Add relationship to parent folder
                    parent_folder_id = folder_map.get(str(parent_path))
                    if parent_folder_id:
                        relationships.append({
                            "from_label": NodeType.FOLDER,
                            "from_property": "folder_id",
                            "from_value": parent_folder_id,
                            "to_label": NodeType.FOLDER,
                            "to_property": "folder_id",
                            "to_value": folder_id,
                            "relationship_type": RelationshipType.CONTAINS,
                            "properties": {}
                        })
                
                # Process files in the current directory
                for file in files:
                    file_path = os.path.join(root, file)
                    file_relative_path = str(Path(file_path).relative_to(project_path)).replace('\\', '/')
                    
                    # Skip hidden files and directories
                    if file.startswith('.') or '/.' in file_relative_path or '\\.' in file_relative_path:
                        continue
                    
                    # Get file metadata
                    file_type = self._get_file_type(file_path)
                    file_size = os.path.getsize(file_path)
                    file_id = str(uuid.uuid4())
                    
                    # Create file properties
                    file_properties = {
                        "file_id": file_id,
                        "project_id": self.project_id,
                        "file_path": file_path,
                        "relative_path": file_relative_path,
                        "name": file,
                        "file_type": file_type,
                        "size": file_size,
                        "created_at": datetime.utcnow().isoformat(),
                        "updated_at": datetime.utcnow().isoformat()
                    }
                    
                    file_properties_list.append(file_properties)
                    file_count += 1
                    
                    # Add relationship to parent folder
                    folder_id = folder_map.get(str(current_path))
                    if folder_id:
                        relationships.append({
                            "from_label": NodeType.FOLDER,
                            "from_property": "folder_id",
                            "from_value": folder_id,
                            "to_label": NodeType.FILE,
                            "to_property": "file_id",
                            "to_value": file_id,
                            "relationship_type": RelationshipType.CONTAINS,
                            "properties": {}
                        })
            
            # Batch create nodes and relationships
            if folder_properties_list:
                batch_size = 100  # Adjust based on performance testing
                for i in range(0, len(folder_properties_list), batch_size):
                    batch = folder_properties_list[i:i+batch_size]
                    folder_nodes.extend(self.db.create_nodes_batch("Folder", batch))
            
            if file_properties_list:
                batch_size = 100  # Adjust based on performance testing
                for i in range(0, len(file_properties_list), batch_size):
                    batch = file_properties_list[i:i+batch_size]
                    file_nodes.extend(self.db.create_nodes_batch("File", batch))
            
            if relationships:
                batch_size = 100  # Adjust based on performance testing
                for i in range(0, len(relationships), batch_size):
                    batch = relationships[i:i+batch_size]
                    self.db.create_relationships_batch(batch)
            
            # Create relationship from Project to all files
            project_file_relationships = []
            for file_props in file_properties_list:
                project_file_relationships.append({
                    "from_label": NodeType.PROJECT,
                    "from_property": "project_id",
                    "from_value": self.project_id,
                    "to_label": NodeType.FILE,
                    "to_property": "file_id",
                    "to_value": file_props["file_id"],
                    "relationship_type": RelationshipType.CONTAINS_FILE,
                    "properties": {}
                })
            
            # Batch create project-file relationships
            if project_file_relationships:
                batch_size = 100  # Adjust based on performance testing
                for i in range(0, len(project_file_relationships), batch_size):
                    batch = project_file_relationships[i:i+batch_size]
                    self.db.create_relationships_batch(batch)
            
            return {
                "success": True,
                "file_count": file_count,
                "folder_count": folder_count,
                "file_nodes": file_nodes,
                "folder_nodes": folder_nodes
            }
            
        except Exception as e:
            error_message = f"Error processing project structure: {str(e)}"
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