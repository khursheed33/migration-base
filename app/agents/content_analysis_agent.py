import os
import uuid
import ast
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime

# Try to import Tree-sitter, but provide fallback
try:
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    # Create mock classes
    class Parser:
        def parse(self, *args, **kwargs):
            return None
    
    class Language:
        def __init__(self, *args, **kwargs):
            pass

from openai import OpenAI

from app.agents.base_agent import BaseAgent
from app.config.settings import get_settings

settings = get_settings()


class ContentAnalysisAgent(BaseAgent):
    """
    Agent for analyzing file contents and extracting detailed metadata.
    Acts as a sub-agent of the Analysis Agent.
    """
    
    def __init__(self, project_id: str):
        """Initialize the content analysis agent."""
        super().__init__(project_id)
        # Initialize OpenAI client without proxies parameter
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.parser = self._initialize_parser()
        self._processed_files: Set[str] = set()
        self._file_id_map: Dict[str, str] = {}  # Maps relative_path to file_id
    
    def _initialize_parser(self) -> Parser:
        """Initialize tree-sitter parser with supported languages."""
        parser = Parser()
        
        if TREE_SITTER_AVAILABLE:
            try:
                # Check if language file exists
                languages_path = os.path.join(settings.STORAGE_DIR, 'build', 'languages.so')
                if os.path.exists(languages_path):
                    python_language = Language(languages_path, 'python')
                    parser.set_language(python_language)
                    self.logger.info("Tree-sitter parser initialized with Python language")
                else:
                    self.logger.warning("Tree-sitter language file not found, using AST parser only")
            except Exception as e:
                self.logger.error(f"Error initializing tree-sitter: {str(e)}")
        else:
            self.logger.warning("Tree-sitter not available, using AST parser only")
        
        return parser
    
    async def execute(self, file_nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute the content analysis agent's main functionality.
        
        Args:
            file_nodes: List of File nodes from structure analysis
            
        Returns:
            Dictionary containing execution results
        """
        self.logger.info(f"Starting ContentAnalysisAgent for project {self.project_id}")
        
        try:
            # Update project status
            self.update_project_status(
                status="analyzing_content",
                progress=20.0,
                current_step="Analyzing file contents"
            )
            
            # Build a map of relative paths to file IDs for quick lookups
            for file_node in file_nodes:
                relative_path = file_node.get("relative_path")
                file_id = file_node.get("file_id")
                if relative_path and file_id:
                    self._file_id_map[relative_path] = file_id
            
            # Track metadata counts
            metadata_counts = {
                "functions": 0,
                "classes": 0,
                "enums": 0,
                "extensions": 0,
                "imports": 0,
                "references": 0
            }
            
            # Prepare batches for metadata storage
            function_batch = []
            class_batch = []
            enum_batch = []
            extension_batch = []
            relationships_batch = []
            
            # Process each file
            for file_node in file_nodes:
                file_path = file_node.get("file_path")
                file_type = file_node.get("file_type")
                file_id = file_node.get("file_id")
                relative_path = file_node.get("relative_path")
                
                if not file_path or not os.path.exists(file_path):
                    continue
                
                if file_path in self._processed_files:
                    continue
                    
                # Process file based on type
                if file_type == "python":
                    metadata = await self._analyze_python_file(file_path, file_id, relative_path)
                else:
                    # Use OpenAI to analyze other file types
                    metadata = await self._analyze_with_openai(file_path, file_type, file_id, relative_path)
                
                # Collect metadata for batch processing
                if metadata:
                    # Extend batches
                    function_batch.extend(metadata.get("functions", []))
                    class_batch.extend(metadata.get("classes", []))
                    enum_batch.extend(metadata.get("enums", []))
                    extension_batch.extend(metadata.get("extensions", []))
                    
                    # Process imports and create relationships
                    for import_meta in metadata.get("imports", []):
                        target_file_id = self._file_id_map.get(import_meta.get("module_path"))
                        if target_file_id:
                            relationships_batch.append({
                                "from_label": "File",
                                "from_property": "file_id",
                                "from_value": file_id,
                                "to_label": "File",
                                "to_property": "file_id",
                                "to_value": target_file_id,
                                "relationship_type": "IMPORTS",
                                "properties": {
                                    "created_at": datetime.utcnow().isoformat()
                                }
                            })
                            metadata_counts["imports"] += 1
                    
                    # Process references and create relationships
                    for ref_meta in metadata.get("references", []):
                        target_file_id = self._file_id_map.get(ref_meta.get("target_path"))
                        if target_file_id:
                            relationships_batch.append({
                                "from_label": "File",
                                "from_property": "file_id",
                                "from_value": file_id,
                                "to_label": "File",
                                "to_property": "file_id",
                                "to_value": target_file_id,
                                "relationship_type": "REFERENCES",
                                "properties": {
                                    "reference_type": ref_meta.get("type", "unknown"),
                                    "created_at": datetime.utcnow().isoformat()
                                }
                            })
                            metadata_counts["references"] += 1
                    
                    # Update counts
                    metadata_counts["functions"] += len(metadata.get("functions", []))
                    metadata_counts["classes"] += len(metadata.get("classes", []))
                    metadata_counts["enums"] += len(metadata.get("enums", []))
                    metadata_counts["extensions"] += len(metadata.get("extensions", []))
                
                self._processed_files.add(file_path)
            
            # Batch create nodes
            function_relationships = []
            if function_batch:
                # Process in batches of 100
                batch_size = 100
                for i in range(0, len(function_batch), batch_size):
                    batch = function_batch[i:i+batch_size]
                    created_functions = self.db.create_nodes_batch("Function", batch)
                    
                    # Create function relationships
                    for function in batch:
                        file_id = function.get("file_id")
                        function_id = function.get("function_id")
                        function_relationships.append({
                            "from_label": "File",
                            "from_property": "file_id",
                            "from_value": file_id,
                            "to_label": "Function",
                            "to_property": "function_id",
                            "to_value": function_id,
                            "relationship_type": "HAS_FUNCTION",
                            "properties": {
                                "created_at": datetime.utcnow().isoformat()
                            }
                        })
            
            class_relationships = []
            if class_batch:
                # Process in batches of 100
                batch_size = 100
                for i in range(0, len(class_batch), batch_size):
                    batch = class_batch[i:i+batch_size]
                    created_classes = self.db.create_nodes_batch("Class", batch)
                    
                    # Create class relationships
                    for class_meta in batch:
                        file_id = class_meta.get("file_id")
                        class_id = class_meta.get("class_id")
                        class_relationships.append({
                            "from_label": "File",
                            "from_property": "file_id",
                            "from_value": file_id,
                            "to_label": "Class",
                            "to_property": "class_id",
                            "to_value": class_id,
                            "relationship_type": "HAS_CLASS",
                            "properties": {
                                "created_at": datetime.utcnow().isoformat()
                            }
                        })
            
            enum_relationships = []
            if enum_batch:
                # Process in batches of 100
                batch_size = 100
                for i in range(0, len(enum_batch), batch_size):
                    batch = enum_batch[i:i+batch_size]
                    created_enums = self.db.create_nodes_batch("Enum", batch)
                    
                    # Create enum relationships
                    for enum in batch:
                        file_id = enum.get("file_id")
                        enum_id = enum.get("enum_id")
                        enum_relationships.append({
                            "from_label": "File",
                            "from_property": "file_id",
                            "from_value": file_id,
                            "to_label": "Enum",
                            "to_property": "enum_id",
                            "to_value": enum_id,
                            "relationship_type": "HAS_ENUM",
                            "properties": {
                                "created_at": datetime.utcnow().isoformat()
                            }
                        })
            
            extension_relationships = []
            if extension_batch:
                # Process in batches of 100
                batch_size = 100
                for i in range(0, len(extension_batch), batch_size):
                    batch = extension_batch[i:i+batch_size]
                    created_extensions = self.db.create_nodes_batch("Extension", batch)
                    
                    # Create extension relationships
                    for extension in batch:
                        file_id = extension.get("file_id")
                        extension_id = extension.get("extension_id")
                        extension_relationships.append({
                            "from_label": "File",
                            "from_property": "file_id",
                            "from_value": file_id,
                            "to_label": "Extension",
                            "to_property": "extension_id",
                            "to_value": extension_id,
                            "relationship_type": "HAS_EXTENSION",
                            "properties": {
                                "created_at": datetime.utcnow().isoformat()
                            }
                        })
            
            # Combine all relationship batches
            all_relationships = (
                function_relationships + 
                class_relationships + 
                enum_relationships + 
                extension_relationships + 
                relationships_batch
            )
            
            # Create all relationships in batches
            if all_relationships:
                batch_size = 100
                for i in range(0, len(all_relationships), batch_size):
                    batch = all_relationships[i:i+batch_size]
                    self.db.create_relationships_batch(batch)
            
            # Update project status
            self.update_project_status(
                status="content_analyzed",
                progress=25.0,
                current_step="File contents analyzed"
            )
            
            # Create analysis report
            report = self.create_report(
                report_type="content_analysis",
                message="Content analysis completed",
                details=metadata_counts
            )
            
            return {
                "success": True,
                "metadata_counts": metadata_counts,
                "report": report
            }
            
        except Exception as e:
            error_message = f"Error in ContentAnalysisAgent: {str(e)}"
            self.log_error(error_message)
            return {"success": False, "error": error_message}
    
    async def _analyze_python_file(
        self, 
        file_path: str, 
        file_id: str, 
        relative_path: str
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a Python file using ast module.
        
        Args:
            file_path: Path to the Python file
            file_id: ID of the File node
            relative_path: Relative path from project root
            
        Returns:
            Extracted metadata
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            metadata = {
                "file_id": file_id,
                "functions": [],
                "classes": [],
                "enums": [],
                "extensions": [],
                "imports": [],
                "references": []
            }
            
            # Extract imports first to build a map of imported module names
            imported_modules = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        imported_modules[name.asname or name.name] = name.name
                elif isinstance(node, ast.ImportFrom):
                    module_prefix = node.module + "." if node.module else ""
                    for name in node.names:
                        full_name = module_prefix + name.name
                        imported_modules[name.asname or name.name] = full_name
            
            # Extract functions, classes, etc.
            for node in ast.walk(tree):
                # Extract functions
                if isinstance(node, ast.FunctionDef):
                    function_meta = {
                        "function_id": str(uuid.uuid4()),
                        "file_id": file_id,
                        "project_id": self.project_id,
                        "name": node.name,
                        "return_type": self._infer_return_type(node),
                        "arguments": self._extract_arguments(node),
                        "decorators": self._extract_decorators(node),
                        "is_static": any(d.id == 'staticmethod' for d in node.decorator_list if isinstance(d, ast.Name)),
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                        "docstring": ast.get_docstring(node) or "",
                        "lineno": node.lineno,
                        "end_lineno": getattr(node, 'end_lineno', node.lineno),
                        "created_at": datetime.utcnow().isoformat()
                    }
                    metadata["functions"].append(function_meta)
                
                # Extract classes
                elif isinstance(node, ast.ClassDef):
                    methods = []
                    # Extract class methods
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            method_id = str(uuid.uuid4())
                            methods.append({
                                "method_id": method_id,
                                "name": item.name,
                                "return_type": self._infer_return_type(item),
                                "arguments": self._extract_arguments(item),
                                "decorators": self._extract_decorators(item),
                                "is_static": any(d.id == 'staticmethod' for d in item.decorator_list if isinstance(d, ast.Name)),
                                "is_async": isinstance(item, ast.AsyncFunctionDef),
                                "docstring": ast.get_docstring(item) or "",
                                "lineno": item.lineno,
                                "end_lineno": getattr(item, 'end_lineno', item.lineno)
                            })
                    
                    class_meta = {
                        "class_id": str(uuid.uuid4()),
                        "file_id": file_id,
                        "project_id": self.project_id,
                        "name": node.name,
                        "type": self._infer_class_type(node),
                        "is_static": False,  # Determined by class decorator or metaclass
                        "is_final": any(d.id == 'final' for d in node.decorator_list if isinstance(d, ast.Name)),
                        "superclasses": [base.id for base in node.bases if isinstance(base, ast.Name)],
                        "interfaces": [],  # Python doesn't have explicit interfaces
                        "methods": methods,
                        "attributes": self._extract_class_attributes(node),
                        "docstring": ast.get_docstring(node) or "",
                        "lineno": node.lineno,
                        "end_lineno": getattr(node, 'end_lineno', node.lineno),
                        "created_at": datetime.utcnow().isoformat()
                    }
                    metadata["classes"].append(class_meta)
                
                # Extract imports
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    import_meta = self._extract_import(node, relative_path)
                    if import_meta:
                        metadata["imports"].append(import_meta)
                
                # Extract references to other modules/files
                elif isinstance(node, ast.Name) and node.id in imported_modules:
                    module_name = imported_modules[node.id]
                    # Convert module name to file path (e.g., "app.models" -> "app/models.py")
                    target_path = module_name.replace('.', '/') + '.py'
                    if target_path in self._file_id_map:
                        reference_meta = {
                            "type": "module_reference",
                            "name": node.id,
                            "target_path": target_path,
                            "lineno": node.lineno,
                            "target_name": module_name,
                            "created_at": datetime.utcnow().isoformat()
                        }
                        metadata["references"].append(reference_meta)
            
            # Look for enums (typically classes inheriting from Enum)
            for class_meta in metadata["classes"]:
                if "Enum" in class_meta["superclasses"]:
                    # Extract enum values from class attributes
                    enum_values = []
                    for attr in class_meta["attributes"]:
                        enum_values.append(attr["name"])
                    
                    enum_meta = {
                        "enum_id": str(uuid.uuid4()),
                        "file_id": file_id,
                        "project_id": self.project_id,
                        "name": class_meta["name"],
                        "values": enum_values,
                        "docstring": class_meta["docstring"],
                        "lineno": class_meta["lineno"],
                        "end_lineno": class_meta["end_lineno"],
                        "created_at": datetime.utcnow().isoformat()
                    }
                    metadata["enums"].append(enum_meta)
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error analyzing Python file {file_path}: {str(e)}")
            return None
    
    async def _analyze_with_openai(
        self, 
        file_path: str, 
        file_type: str, 
        file_id: str,
        relative_path: str
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a file using OpenAI's language model.
        
        Args:
            file_path: Path to the file
            file_type: Type of file
            file_id: ID of the File node
            relative_path: Relative path from project root
            
        Returns:
            Extracted metadata
        """
        try:
            # Check if file size is too large
            file_size = os.path.getsize(file_path)
            max_size_mb = 0.1  # 100KB limit for analysis
            if file_size > max_size_mb * 1024 * 1024:
                self.logger.warning(f"File {file_path} is too large ({file_size} bytes) for OpenAI analysis, skipping")
                return {
                    "file_id": file_id,
                    "functions": [],
                    "classes": [],
                    "enums": [],
                    "extensions": [],
                    "imports": [],
                    "references": []
                }
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Check if content is too large for OpenAI
            if len(content) > 25000:  # Conservative limit for token count
                content = content[:25000] + "\n... (content truncated for analysis)"
            
            # Prepare prompt for OpenAI
            prompt = f"""Analyze this {file_type} code and extract the following metadata in JSON format:
            - Functions (name, arguments, return type, decorators)
            - Classes (name, type, superclasses, methods, attributes)
            - Imports and dependencies
            - Any special constructs (enums, extensions, etc.)

            Respond with valid JSON only.

            Code:
            {content}"""
            
            # Prepare response format based on OpenAI model capabilities
            try:
                # Try with response_format
                response = self.openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    max_tokens=4000
                )
            except Exception as format_error:
                self.logger.warning(f"OpenAI JSON response format not supported: {str(format_error)}, using standard response")
                # Fallback without specifying response format for older models
                response = self.openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a code analyzer. Always respond with valid JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0,
                    max_tokens=4000
                )
            
            # Parse response and structure metadata
            metadata = {
                "file_id": file_id,
                "functions": [],
                "classes": [],
                "enums": [],
                "extensions": [],
                "imports": [],
                "references": []
            }
            
            # Process OpenAI response
            response_content = response.choices[0].message.content
            try:
                import json
                # Try to find and extract JSON if it's wrapped in markdown code blocks or other text
                json_start = response_content.find('{')
                json_end = response_content.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_content = response_content[json_start:json_end]
                    parsed_data = json.loads(json_content)
                else:
                    parsed_data = json.loads(response_content)
                
                # Process functions
                for func in parsed_data.get("functions", []):
                    function_meta = {
                        "function_id": str(uuid.uuid4()),
                        "file_id": file_id,
                        "project_id": self.project_id,
                        "name": func.get("name", ""),
                        "return_type": func.get("return_type", "Any"),
                        "arguments": func.get("arguments", []),
                        "decorators": func.get("decorators", []),
                        "is_static": func.get("is_static", False),
                        "is_async": func.get("is_async", False),
                        "docstring": func.get("docstring", ""),
                        "created_at": datetime.utcnow().isoformat()
                    }
                    metadata["functions"].append(function_meta)
                
                # Process classes
                for cls in parsed_data.get("classes", []):
                    class_meta = {
                        "class_id": str(uuid.uuid4()),
                        "file_id": file_id,
                        "project_id": self.project_id,
                        "name": cls.get("name", ""),
                        "type": cls.get("type", "regular"),
                        "is_static": cls.get("is_static", False),
                        "is_final": cls.get("is_final", False),
                        "superclasses": cls.get("superclasses", []),
                        "interfaces": cls.get("interfaces", []),
                        "methods": cls.get("methods", []),
                        "attributes": cls.get("attributes", []),
                        "docstring": cls.get("docstring", ""),
                        "created_at": datetime.utcnow().isoformat()
                    }
                    metadata["classes"].append(class_meta)
                
                # Process enums
                for enum in parsed_data.get("enums", []):
                    enum_meta = {
                        "enum_id": str(uuid.uuid4()),
                        "file_id": file_id,
                        "project_id": self.project_id,
                        "name": enum.get("name", ""),
                        "values": enum.get("values", []),
                        "docstring": enum.get("docstring", ""),
                        "created_at": datetime.utcnow().isoformat()
                    }
                    metadata["enums"].append(enum_meta)
                
                # Process imports
                for imp in parsed_data.get("imports", []):
                    module_path = imp.get("module", "")
                    if module_path:
                        # Convert module name to file path
                        module_file_path = module_path.replace('.', '/') + '.py'
                        import_meta = {
                            "module_path": module_file_path,
                            "created_at": datetime.utcnow().isoformat()
                        }
                        metadata["imports"].append(import_meta)
            
            except Exception as parse_error:
                self.logger.error(f"Error parsing OpenAI response for {file_path}: {str(parse_error)}")
                self.logger.debug(f"Response content: {response_content[:200]}...")
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error analyzing file {file_path} with OpenAI: {str(e)}")
            return None
    
    def _infer_return_type(self, node: ast.FunctionDef) -> str:
        """Infer function return type from annotations or docstring."""
        if node.returns:
            return self._get_annotation_name(node.returns)
        return "Any"  # Default return type
    
    def _extract_arguments(self, node: ast.FunctionDef) -> List[Dict[str, str]]:
        """Extract function arguments with types."""
        args = []
        for arg in node.args.args:
            arg_type = "Any"
            if arg.annotation:
                arg_type = self._get_annotation_name(arg.annotation)
            args.append({"name": arg.arg, "type": arg_type})
        return args
    
    def _extract_decorators(self, node: ast.FunctionDef) -> List[str]:
        """Extract function decorators."""
        decorators = []
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                decorators.append(f"@{decorator.id}")
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name):
                    decorators.append(f"@{decorator.func.id}")
        return decorators
    
    def _infer_class_type(self, node: ast.ClassDef) -> str:
        """Infer class type (regular, abstract, singleton, etc.)."""
        # Check for singleton pattern
        if any(base.id == 'metaclass' for base in node.bases if isinstance(base, ast.Name)):
            return "singleton"
        # Check for abstract class
        if any(d.id == 'abstractmethod' for d in node.decorator_list if isinstance(d, ast.Name)):
            return "abstract"
        return "regular"
    
    def _extract_class_attributes(self, node: ast.ClassDef) -> List[Dict[str, str]]:
        """Extract class attributes with types."""
        attributes = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                attr_type = "Any"
                if item.annotation:
                    attr_type = self._get_annotation_name(item.annotation)
                attributes.append({
                    "name": item.target.id,
                    "type": attr_type,
                    "visibility": "public"  # Default visibility
                })
        return attributes
    
    def _extract_import(self, node: ast.AST, relative_path: str) -> Optional[Dict[str, str]]:
        """
        Extract import information.
        
        Args:
            node: AST node
            relative_path: Relative path of the file being analyzed
        
        Returns:
            Import metadata
        """
        if isinstance(node, ast.Import):
            for name in node.names:
                module_path = name.name.replace('.', '/') + '.py'
                return {"module_path": module_path}
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                # Handle relative imports
                if node.level > 0:
                    # Get directory path of current file
                    current_dir = os.path.dirname(relative_path)
                    # Go up by node.level directories
                    for _ in range(node.level):
                        current_dir = os.path.dirname(current_dir) if current_dir else ""
                    
                    # Construct the module path
                    if node.module:
                        module_path = os.path.join(current_dir, node.module.replace('.', '/'))
                    else:
                        module_path = current_dir
                    
                    module_path = module_path.replace('\\', '/') + '.py'
                else:
                    module_path = node.module.replace('.', '/') + '.py'
                
                return {"module_path": module_path}
        return None
    
    def _get_annotation_name(self, node: ast.AST) -> str:
        """Get the string representation of a type annotation."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            # Handle generic types like List[str], Dict[str, int]
            return f"{node.value.id}[...]"
        return "Any"