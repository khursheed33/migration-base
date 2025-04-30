import os
import uuid
import zipfile
import shutil
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.agents.base_agent import BaseAgent
from app.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class UploadAgent(BaseAgent):
    """
    Agent for handling file uploads, extracting ZIP files,
    and initializing project metadata in Neo4j.
    """
    
    async def execute(
        self, 
        zip_file_path: str, 
        project_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the upload agent's main functionality.
        
        Args:
            zip_file_path: Path to the uploaded ZIP file
            project_data: Project metadata
            
        Returns:
            Dictionary containing execution results
        """
        self.logger.info(f"Starting UploadAgent for project {self.project_id}")
        
        try:
            # Validate ZIP file
            if not os.path.exists(zip_file_path):
                error_message = f"ZIP file {zip_file_path} does not exist"
                self.log_error(error_message)
                return {"success": False, "error": error_message}
            
            # Extract ZIP file
            temp_dir = self._create_temp_directory()
            extract_result = self._extract_zip(zip_file_path, temp_dir)
            
            if not extract_result["success"]:
                return extract_result
                
            # Initialize project in Neo4j
            project = self._create_project_node(temp_dir, project_data)
            
            # Update project status
            self.update_project_status(
                status="uploaded",
                progress=10.0,
                current_step="Project uploaded and extracted"
            )
            
            return {
                "success": True,
                "project_id": self.project_id,
                "temp_dir": temp_dir,
                "project": project
            }
            
        except Exception as e:
            error_message = f"Error in UploadAgent: {str(e)}"
            self.log_error(error_message)
            return {"success": False, "error": error_message}
    
    def _create_temp_directory(self) -> str:
        """
        Create a temporary directory for the extracted files.
        
        Returns:
            Path to the temporary directory
        """
        # Ensure base temp directory exists
        os.makedirs(settings.TEMP_DIR, exist_ok=True)
        
        # Create project-specific temp directory
        temp_dir = os.path.join(
            settings.TEMP_DIR, 
            f"project_{self.project_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        )
        os.makedirs(temp_dir, exist_ok=True)
        self.logger.info(f"Created temporary directory: {temp_dir}")
        
        return temp_dir
    
    def _extract_zip(self, zip_file_path: str, extract_dir: str) -> Dict[str, Any]:
        """
        Extract a ZIP file to the specified directory.
        
        Args:
            zip_file_path: Path to the ZIP file
            extract_dir: Directory to extract the files to
            
        Returns:
            Dictionary containing extraction results
        """
        try:
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                # Check for malicious paths (path traversal)
                for zip_info in zip_ref.infolist():
                    if zip_info.filename.startswith('/') or '..' in zip_info.filename:
                        error_message = f"Potentially malicious path in ZIP: {zip_info.filename}"
                        self.log_error(error_message)
                        return {"success": False, "error": error_message}
                
                # Get total size for validation
                total_size = sum(zip_info.file_size for zip_info in zip_ref.infolist())
                max_size_mb = settings.MAX_UPLOAD_SIZE_MB
                if max_size_mb and total_size > max_size_mb * 1024 * 1024:
                    error_message = f"ZIP file too large. Maximum allowed size: {max_size_mb}MB"
                    self.log_error(error_message)
                    return {"success": False, "error": error_message}
                
                # Extract files
                zip_ref.extractall(extract_dir)
                
                # Gather file stats
                file_count = len(zip_ref.infolist())
                file_types = {}
                for zip_info in zip_ref.infolist():
                    if not zip_info.is_dir():
                        ext = os.path.splitext(zip_info.filename)[1].lower()
                        file_types[ext] = file_types.get(ext, 0) + 1
                
                self.logger.info(f"Extracted {file_count} files to {extract_dir}")
                
                return {
                    "success": True,
                    "extract_dir": extract_dir,
                    "file_count": file_count,
                    "file_types": file_types,
                    "total_size": total_size
                }
                
        except zipfile.BadZipFile:
            error_message = f"Invalid ZIP file: {zip_file_path}"
            self.log_error(error_message)
            return {"success": False, "error": error_message}
        
        except Exception as e:
            error_message = f"Error extracting ZIP file: {str(e)}"
            self.log_error(error_message)
            return {"success": False, "error": error_message}
    
    def _create_project_node(self, temp_dir: str, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a Project node in Neo4j.
        
        Args:
            temp_dir: Path to the temporary directory
            project_data: Project metadata
            
        Returns:
            Created Project node
        """
        import json
        now = datetime.utcnow().isoformat()
        
        # Create migrated directory
        storage_dir = settings.STORAGE_DIR
        os.makedirs(storage_dir, exist_ok=True)
        migrated_dir = os.path.join(storage_dir, f"migrated_{self.project_id}")
        os.makedirs(migrated_dir, exist_ok=True)
        
        # Get ZIP file metadata (from extraction step)
        file_stats = self._get_file_stats(temp_dir)
        
        # Prepare project properties
        project_properties = {
            "project_id": self.project_id,
            "user_id": project_data.get("user_id", "anonymous"),
            "temp_dir": temp_dir,
            "migrated_dir": migrated_dir,
            "status": "uploaded",
            "progress": 10.0,
            "current_step": "Project uploaded and extracted",
            "source_language": project_data.get("source_language"),
            "target_language": project_data.get("target_language"),
            "source_framework": project_data.get("source_framework"),
            "target_framework": project_data.get("target_framework"),
            "description": project_data.get("description"),
            "custom_mappings": json.dumps(project_data.get("custom_mappings", {})),  # Serialize to JSON string
            "file_count": file_stats["file_count"],
            "folder_count": file_stats["folder_count"],
            "largest_file_size": file_stats["largest_file_size"],
            "file_types": json.dumps(file_stats["file_types"]),
            "created_at": now,
            "updated_at": now
        }
        
        # Create Project node
        self.logger.info(f"Creating Project node for project {self.project_id}")
        project = self.db.create_node("Project", project_properties)
        
        return project
        
    def _get_file_stats(self, directory: str) -> Dict[str, Any]:
        """
        Get statistics about files in the extracted project.
        
        Args:
            directory: Path to the directory to analyze
            
        Returns:
            Dictionary containing file statistics
        """
        file_count = 0
        folder_count = 0
        largest_file_size = 0
        file_types = {}
        
        for root, dirs, files in os.walk(directory):
            folder_count += len(dirs)
            
            for file in files:
                file_path = os.path.join(root, file)
                
                # Skip hidden files
                if file.startswith('.'):
                    continue
                
                # Get file extension and update counts
                ext = os.path.splitext(file)[1].lower()
                file_types[ext] = file_types.get(ext, 0) + 1
                
                # Update counts
                file_count += 1
                
                # Check file size
                file_size = os.path.getsize(file_path)
                largest_file_size = max(largest_file_size, file_size)
        
        return {
            "file_count": file_count,
            "folder_count": folder_count,
            "largest_file_size": largest_file_size,
            "file_types": file_types
        }