import os
import uuid
import zipfile
import shutil
import logging
import json
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from app.agents.base_agent import BaseAgent
from app.config.settings import get_settings
from app.utils.openai_client import get_openai_client
from app.utils.constants import RelationshipType, NodeType

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
                status="uploading",
                progress=10.0,
                current_step="Project extracted, analyzing structure"
            )
            
            # Analyze project structure and create file nodes
            structure_result = await self._analyze_project_structure(temp_dir)
            if not structure_result["success"]:
                return structure_result
                
            # Analyze file contents with OpenAI to generate descriptions
            self.update_project_status(
                status="analyzing",
                progress=30.0,
                current_step="Analyzing files and generating descriptions"
            )
            
            content_result = await self._analyze_file_contents(temp_dir, structure_result["files"])
            if not content_result["success"]:
                return content_result
                
            # Create component mappings
            self.update_project_status(
                status="mapping",
                progress=60.0,
                current_step="Creating component mappings"
            )
            
            mapping_result = await self._create_mappings(structure_result["files"], content_result["metadata"])
            if not mapping_result["success"]:
                return mapping_result
            
            # Update project status
            self.update_project_status(
                status="uploaded",
                progress=100.0,
                current_step="Project uploaded, analyzed and ready for migration"
            )
            
            return {
                "success": True,
                "project_id": self.project_id,
                "temp_dir": temp_dir,
                "project": project,
                "files_analyzed": structure_result["file_count"],
                "components_mapped": mapping_result["mapping_count"]
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
    
    async def _analyze_project_structure(self, directory: str) -> Dict[str, Any]:
        """
        Analyze project structure and create File nodes in Neo4j.
        
        Args:
            directory: Path to the project directory
            
        Returns:
            Dictionary containing analysis results
        """
        try:
            self.logger.info(f"Analyzing project structure for {self.project_id}")
            files = []
            file_count = 0
            
            # Get project node
            project_node = self.db.find_node("Project", "project_id", self.project_id)
            if not project_node:
                return {"success": False, "error": "Project node not found"}
            
            # Walk through directory
            for root, dirs, filenames in os.walk(directory):
                # Process files
                for filename in filenames:
                    # Skip hidden files and directories
                    if filename.startswith('.') or "/." in root:
                        continue
                    
                    file_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(file_path, directory)
                    
                    # Get file info
                    file_size = os.path.getsize(file_path)
                    file_ext = os.path.splitext(filename)[1].lower()
                    
                    # Determine file type
                    file_type = self._detect_file_type(filename, file_ext)
                    
                    # Create file node
                    file_id = str(uuid.uuid4())
                    file_properties = {
                        "id": file_id,
                        "file_id": file_id,
                        "project_id": self.project_id,
                        "file_path": file_path,
                        "relative_path": relative_path,
                        "file_name": filename,
                        "file_type": file_type,
                        "extension": file_ext,
                        "size": file_size,
                        "created_at": datetime.utcnow().isoformat()
                    }
                    
                    file_node = self.db.create_node("File", file_properties)
                    
                    # Create relationship to project
                    self.db.create_relationship(
                        "Project", "project_id", self.project_id,
                        "CONTAINS",
                        "File", "id", file_id
                    )
                    
                    files.append({
                        "id": file_id,
                        "path": file_path,
                        "relative_path": relative_path,
                        "name": filename,
                        "type": file_type,
                        "extension": file_ext,
                        "size": file_size
                    })
                    
                    file_count += 1
            
            self.logger.info(f"Created {file_count} File nodes for project {self.project_id}")
            
            return {
                "success": True,
                "file_count": file_count,
                "files": files
            }
            
        except Exception as e:
            error_message = f"Error analyzing project structure: {str(e)}"
            self.log_error(error_message)
            return {"success": False, "error": error_message}
    
    def _detect_file_type(self, filename: str, extension: str) -> str:
        """
        Detect file type based on filename and extension.
        
        Args:
            filename: Name of the file
            extension: File extension
            
        Returns:
            Detected file type
        """
        # Map common extensions to file types
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "react",
            ".tsx": "react",
            ".html": "html",
            ".css": "css",
            ".scss": "sass",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "header",
            ".cs": "csharp",
            ".php": "php",
            ".rb": "ruby",
            ".go": "go",
            ".rs": "rust",
            ".kt": "kotlin",
            ".swift": "swift",
            ".m": "objective-c",
            ".json": "json",
            ".xml": "xml",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".md": "markdown",
            ".sql": "sql",
            ".sh": "shell",
            ".bat": "batch",
            ".ps1": "powershell",
            ".gitignore": "git",
            ".dockerignore": "docker",
            ".env": "env",
            ".txt": "text",
            ".pdf": "pdf",
            ".doc": "doc",
            ".docx": "docx",
            ".xls": "excel",
            ".xlsx": "excel",
            ".csv": "csv",
            ".jpg": "image",
            ".jpeg": "image",
            ".png": "image",
            ".gif": "image",
            ".svg": "image",
            ".ico": "image"
        }
        
        # Handle special filenames
        if filename == "Dockerfile":
            return "docker"
        elif filename == "package.json":
            return "npm"
        elif filename == "requirements.txt":
            return "python-deps"
        elif filename == "Cargo.toml":
            return "rust-deps"
        elif filename == "pom.xml":
            return "maven"
        
        # Return file type based on extension
        return ext_map.get(extension, "unknown")
    
    async def _analyze_file_contents(self, directory: str, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze file contents and generate descriptions using OpenAI.
        Detects functions, classes, imports, etc. and creates nodes in Neo4j.
        
        Args:
            directory: Path to the project directory
            files: List of file dictionaries
            
        Returns:
            Dictionary containing analysis results
        """
        try:
            self.logger.info(f"Analyzing file contents for project {self.project_id}")
            
            # Get OpenAI client
            openai_client = get_openai_client()
            if not openai_client:
                self.logger.warning("OpenAI client not available, skipping content analysis")
                return {"success": True, "metadata": {}, "analyzed_files": 0}
            
            analyzed_files = 0
            metadata = {}
            
            # Process code files (skip binary and large files)
            code_files = [
                f for f in files 
                if self._is_code_file(f["type"]) and f["size"] < settings.MAX_FILE_SIZE_ANALYSIS
            ]
            
            # Group files by type for batch processing
            file_groups = {}
            for file in code_files:
                file_type = file["type"]
                if file_type not in file_groups:
                    file_groups[file_type] = []
                file_groups[file_type].append(file)
            
            # Analyze each file type group
            for file_type, group_files in file_groups.items():
                for file in group_files:
                    # Read file content
                    file_path = file["path"]
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                    except Exception as e:
                        self.logger.warning(f"Error reading file {file_path}: {str(e)}")
                        continue
                    
                    # Skip empty files
                    if not content.strip():
                        continue
                    
                    # Generate file description with OpenAI
                    file_metadata = await self._generate_file_description(
                        file["id"], 
                        file["relative_path"], 
                        file_type, 
                        content
                    )
                    
                    if file_metadata:
                        metadata[file["id"]] = file_metadata
                        analyzed_files += 1
                    
                    # Update progress periodically
                    if analyzed_files % 10 == 0:
                        progress = 30 + min(30, (analyzed_files / len(code_files)) * 30)
                        self.update_project_status(
                            progress=progress,
                            current_step=f"Analyzed {analyzed_files}/{len(code_files)} files"
                        )
            
            self.logger.info(f"Analyzed {analyzed_files} files for project {self.project_id}")
            
            return {
                "success": True,
                "metadata": metadata,
                "analyzed_files": analyzed_files
            }
            
        except Exception as e:
            error_message = f"Error analyzing file contents: {str(e)}"
            self.log_error(error_message)
            return {"success": False, "error": error_message}
    
    def _is_code_file(self, file_type: str) -> bool:
        """
        Check if file is a code file that should be analyzed.
        
        Args:
            file_type: File type
            
        Returns:
            True if file is a code file, False otherwise
        """
        code_file_types = [
            "python", "javascript", "typescript", "react", "java", "c", "cpp", 
            "csharp", "php", "ruby", "go", "rust", "kotlin", "swift", "objective-c",
            "html", "css", "sass", "shell", "sql"
        ]
        return file_type in code_file_types
    
    async def _generate_file_description(
        self, 
        file_id: str, 
        file_path: str, 
        file_type: str, 
        content: str
    ) -> Dict[str, Any]:
        """
        Generate file description using OpenAI.
        
        Args:
            file_id: File ID
            file_path: Relative file path
            file_type: File type
            content: File content
            
        Returns:
            File metadata including description and detected components
        """
        try:
            # Get OpenAI client
            openai_client = get_openai_client()
            if not openai_client:
                return {}
            
            # Truncate content if too long
            max_content_length = 8000  # Adjust based on token limits
            if len(content) > max_content_length:
                content = content[:max_content_length] + "\n... (truncated)"
            
            # Prepare prompt
            prompt = f"""
            Analyze this {file_type} file and provide:
            1. A brief description (max 2 sentences) explaining what this file does
            2. Key components (classes, functions, etc.) with their purpose
            3. Any dependencies or imports
            4. Potential migration challenges
            
            Format as JSON with fields: 
            - description (string)
            - components (array of objects with name, type, purpose)
            - dependencies (array of strings)
            - migration_notes (string)
            
            File: {file_path}
            
            Content:
            ```{file_type}
            {content}
            ```
            
            Response (JSON only):
            """
            
            # Call OpenAI
            response = await openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You analyze code files and extract metadata in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            
            # Parse response
            ai_response = response.choices[0].message.content
            metadata = json.loads(ai_response)
            
            # Update file node with description
            self.db.update_node_properties(
                "File", 
                "id", 
                file_id, 
                {
                    "description": metadata.get("description", ""),
                    "metadata": json.dumps(metadata)
                }
            )
            
            # Create component nodes for classes and functions
            if "components" in metadata:
                for component in metadata.get("components", []):
                    # Skip if no name
                    if not component.get("name"):
                        continue
                    
                    component_id = str(uuid.uuid4())
                    component_type = component.get("type", "unknown").lower()
                    
                    # Determine node label based on component type
                    node_label = "Component"
                    if "class" in component_type:
                        node_label = "Class"
                    elif "function" in component_type or "method" in component_type:
                        node_label = "Function"
                    elif "enum" in component_type:
                        node_label = "Enum"
                    
                    # Create component node
                    component_props = {
                        "id": component_id,
                        f"{node_label.lower()}_id": component_id,
                        "project_id": self.project_id,
                        "file_id": file_id,
                        "name": component.get("name"),
                        "type": component_type,
                        "purpose": component.get("purpose", ""),
                        "created_at": datetime.utcnow().isoformat()
                    }
                    
                    node = self.db.create_node(node_label, component_props)
                    
                    # Create relationship from file to component
                    relationship_type = f"HAS_{node_label.upper()}"
                    self.db.create_relationship(
                        NodeType.FILE, "id", file_id,
                        node_label, "id", component_id,
                        relationship_type
                    )
            
            return metadata
            
        except Exception as e:
            self.logger.warning(f"Error generating description for {file_path}: {str(e)}")
            return {}
            
    async def _create_mappings(
        self, 
        files: List[Dict[str, Any]], 
        metadata: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create component mappings based on file analysis.
        
        Args:
            files: List of file dictionaries
            metadata: File metadata
            
        Returns:
            Dictionary containing mapping results
        """
        try:
            self.logger.info(f"Creating component mappings for project {self.project_id}")
            
            # Load custom mappings from project
            project = self.db.find_node("Project", "project_id", self.project_id)
            custom_mappings = {}
            
            if project and "custom_mappings" in project:
                try:
                    if isinstance(project["custom_mappings"], str):
                        custom_mappings = json.loads(project["custom_mappings"])
                    else:
                        custom_mappings = project["custom_mappings"]
                except:
                    self.logger.warning("Failed to parse custom mappings")
            
            # Group files by type
            file_types = {}
            for file in files:
                file_type = file["type"]
                if file_type not in file_types:
                    file_types[file_type] = []
                file_types[file_type].append(file)
            
            # Get counts for each file type
            file_type_counts = {ft: len(files_list) for ft, files_list in file_types.items()}
            
            # Create mapping nodes for each major component type
            mapping_count = 0
            
            # Get source and target info from project
            source_language = project.get("source_language", "unknown")
            target_language = project.get("target_language", "unknown")
            source_framework = project.get("source_framework", "unknown")
            target_framework = project.get("target_framework", "unknown")
            
            # Create component classifications
            for file_type, count in file_type_counts.items():
                # Skip types with few files
                if count < 2:
                    continue
                
                # Create component node
                component_id = str(uuid.uuid4())
                component_props = {
                    "id": component_id,
                    "component_id": component_id,
                    "project_id": self.project_id,
                    "name": f"{file_type.capitalize()} Component",
                    "type": file_type,
                    "file_count": count,
                    "created_at": datetime.utcnow().isoformat()
                }
                
                component_node = self.db.create_node("Component", component_props)
                
                # Link files to component
                for file in file_types[file_type]:
                    self.db.create_relationship(
                        NodeType.COMPONENT, "id", component_id,
                        NodeType.FILE, "id", file["id"],
                        RelationshipType.CLASSIFIES_AS
                    )
                
                # Create mapping if we have target language/framework
                if target_language != "unknown":
                    # Check if we have a custom mapping for this type
                    target_component = None
                    if custom_mappings and file_type in custom_mappings:
                        target_component = custom_mappings[file_type]
                    else:
                        # Use default mapping based on file type and target language
                        target_component = self._get_default_mapping(
                            file_type, 
                            source_language, 
                            target_language,
                            source_framework,
                            target_framework
                        )
                    
                    if target_component:
                        # Create mapping node
                        mapping_id = str(uuid.uuid4())
                        mapping_props = {
                            "id": mapping_id,
                            "mapping_id": mapping_id,
                            "project_id": self.project_id,
                            "source_component": file_type,
                            "target_component": target_component,
                            "is_custom": file_type in custom_mappings,
                            "created_at": datetime.utcnow().isoformat()
                        }
                        
                        mapping_node = self.db.create_node("Mapping", mapping_props)
                        
                        # Create relationships
                        self.db.create_relationship(
                            NodeType.COMPONENT, "id", component_id,
                            NodeType.MAPPING, "id", mapping_id,
                            RelationshipType.MAPS_TO
                        )
                        
                        mapping_count += 1
            
            self.logger.info(f"Created {mapping_count} mappings for project {self.project_id}")
            
            return {
                "success": True,
                "mapping_count": mapping_count
            }
            
        except Exception as e:
            error_message = f"Error creating mappings: {str(e)}"
            self.log_error(error_message)
            return {"success": False, "error": error_message}
    
    def _get_default_mapping(
        self, 
        source_type: str, 
        source_language: str, 
        target_language: str,
        source_framework: str,
        target_framework: str
    ) -> Optional[str]:
        """
        Get default mapping for a source component type.
        
        Args:
            source_type: Source component type
            source_language: Source language
            target_language: Target language
            source_framework: Source framework
            target_framework: Target framework
            
        Returns:
            Target component type or None
        """
        # Common mappings between languages
        mappings = {
            # Python to Java mappings
            ("python", "java"): {
                "python": "java",
                "flask": "spring-boot",
                "django": "spring-mvc",
                "sqlalchemy": "hibernate",
                "pandas": "java-streams",
                "numpy": "commons-math"
            },
            # JavaScript to TypeScript mappings
            ("javascript", "typescript"): {
                "javascript": "typescript",
                "react": "react-typescript",
                "vue": "vue-typescript",
                "express": "nest",
                "mongodb": "mongodb-typescript"
            }
            # Add more language mappings as needed
        }
        
        # Check for specific language pair mappings
        lang_pair = (source_language, target_language)
        if lang_pair in mappings and source_type in mappings[lang_pair]:
            return mappings[lang_pair][source_type]
        
        # Default: return same type but for target language
        return f"{source_type}-{target_language}"