import os
import uuid
import ast
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime

from tree_sitter import Language, Parser
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
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.parser = self._initialize_parser()
        self._processed_files: Set[str] = set()
    
    def _initialize_parser(self) -> Parser:
        """Initialize tree-sitter parser with supported languages."""
        # TODO: Build and load language parsers
        parser = Parser()
        # parser.set_language(Language('build/languages.so', 'python'))
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
            
            # Track metadata counts
            metadata_counts = {
                "functions": 0,
                "classes": 0,
                "enums": 0,
                "extensions": 0,
                "imports": 0,
                "references": 0
            }
            
            # Process each file
            for file_node in file_nodes:
                file_path = file_node.get("file_path")
                file_type = file_node.get("file_type")
                file_id = file_node.get("file_id")
                
                if not file_path or not os.path.exists(file_path):
                    continue
                
                if file_path in self._processed_files:
                    continue
                    
                # Process file based on type
                if file_type == "python":
                    metadata = await self._analyze_python_file(file_path, file_id)
                else:
                    # Use OpenAI to analyze other file types
                    metadata = await self._analyze_with_openai(file_path, file_type, file_id)
                
                # Create nodes and relationships
                if metadata:
                    await self._store_metadata(metadata, file_id)
                    self._update_counts(metadata_counts, metadata)
                
                self._processed_files.add(file_path)
            
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
    
    async def _analyze_python_file(self, file_path: str, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a Python file using ast module.
        
        Args:
            file_path: Path to the Python file
            file_id: ID of the File node
            
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
                "imports": [],
                "references": []
            }
            
            for node in ast.walk(tree):
                # Extract functions
                if isinstance(node, ast.FunctionDef):
                    function_meta = {
                        "function_id": f"function_{uuid.uuid4().hex[:8]}",
                        "name": node.name,
                        "return_type": self._infer_return_type(node),
                        "arguments": self._extract_arguments(node),
                        "decorators": self._extract_decorators(node),
                        "is_static": any(d.id == 'staticmethod' for d in node.decorator_list if isinstance(d, ast.Name)),
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                        "docstring": ast.get_docstring(node) or "",
                        "created_at": datetime.utcnow().isoformat()
                    }
                    metadata["functions"].append(function_meta)
                
                # Extract classes
                elif isinstance(node, ast.ClassDef):
                    class_meta = {
                        "class_id": f"class_{uuid.uuid4().hex[:8]}",
                        "name": node.name,
                        "type": self._infer_class_type(node),
                        "superclasses": [base.id for base in node.bases if isinstance(base, ast.Name)],
                        "methods": [],
                        "attributes": self._extract_class_attributes(node),
                        "docstring": ast.get_docstring(node) or "",
                        "created_at": datetime.utcnow().isoformat()
                    }
                    metadata["classes"].append(class_meta)
                
                # Extract imports
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    import_meta = self._extract_import(node)
                    if import_meta:
                        metadata["imports"].append(import_meta)
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error analyzing Python file {file_path}: {str(e)}")
            return None
    
    async def _analyze_with_openai(
        self, 
        file_path: str, 
        file_type: str, 
        file_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a file using OpenAI's language model.
        
        Args:
            file_path: Path to the file
            file_type: Type of file
            file_id: ID of the File node
            
        Returns:
            Extracted metadata
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Prepare prompt for OpenAI
            prompt = f"""Analyze this {file_type} code and extract the following metadata in JSON format:
            - Functions (name, arguments, return type, decorators)
            - Classes (name, type, superclasses, methods, attributes)
            - Imports and dependencies
            - Any special constructs (enums, extensions, etc.)

            Code:
            {content}"""
            
            # Call OpenAI API
            response = await self.openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse response and structure metadata
            metadata = {
                "file_id": file_id,
                "functions": [],
                "classes": [],
                "imports": [],
                "references": []
            }
            
            # TODO: Parse OpenAI response and populate metadata
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error analyzing file {file_path} with OpenAI: {str(e)}")
            return None
    
    async def _store_metadata(self, metadata: Dict[str, Any], file_id: str) -> None:
        """
        Store extracted metadata in Neo4j.
        
        Args:
            metadata: Extracted metadata
            file_id: ID of the File node
        """
        # Store functions
        for function in metadata.get("functions", []):
            function_node = self.db.create_node("Function", function)
            self.db.create_relationship(
                from_label="File",
                from_property="file_id",
                from_value=file_id,
                to_label="Function",
                to_property="function_id",
                to_value=function["function_id"],
                relationship_type="HAS_FUNCTION"
            )
        
        # Store classes
        for class_meta in metadata.get("classes", []):
            class_node = self.db.create_node("Class", class_meta)
            self.db.create_relationship(
                from_label="File",
                from_property="file_id",
                from_value=file_id,
                to_label="Class",
                to_property="class_id",
                to_value=class_meta["class_id"],
                relationship_type="HAS_CLASS"
            )
        
        # Store imports and references
        for import_meta in metadata.get("imports", []):
            self.db.create_relationship(
                from_label="File",
                from_property="file_id",
                from_value=file_id,
                to_label="File",
                to_property="relative_path",
                to_value=import_meta["module_path"],
                relationship_type="IMPORTS"
            )
    
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
    
    def _extract_import(self, node: ast.AST) -> Optional[Dict[str, str]]:
        """Extract import information."""
        if isinstance(node, ast.Import):
            for name in node.names:
                return {"module_path": name.name}
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                return {"module_path": f"{node.module}"}
        return None
    
    def _get_annotation_name(self, node: ast.AST) -> str:
        """Get the string representation of a type annotation."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return str(node.value)
        return "Any"
    
    def _update_counts(self, counts: Dict[str, int], metadata: Dict[str, Any]) -> None:
        """Update metadata counts."""
        counts["functions"] += len(metadata.get("functions", []))
        counts["classes"] += len(metadata.get("classes", []))
        counts["enums"] += len(metadata.get("enums", []))
        counts["extensions"] += len(metadata.get("extensions", []))
        counts["imports"] += len(metadata.get("imports", []))
        counts["references"] += len(metadata.get("references", []))