import os
import uuid
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from app.agents.base_agent import BaseAgent
from app.agents.structure_analysis_agent import StructureAnalysisAgent
from app.agents.content_analysis_agent import ContentAnalysisAgent
from app.config.settings import get_settings
from app.utils.constants import RelationshipType, NodeType

settings = get_settings()


class AnalysisAgent(BaseAgent):
    """
    Main Analysis Agent that coordinates Structure Analysis and Content Analysis.
    Responsible for detecting languages/frameworks and classifying components.
    """
    
    async def execute(self) -> Dict[str, Any]:
        """
        Execute the analysis agent's main functionality.
        
        Returns:
            Dictionary containing execution results
        """
        self.logger.info(f"Starting AnalysisAgent for project {self.project_id}")
        
        try:
            # Get project from database
            project = self.db.find_node("Project", "project_id", self.project_id)
            if not project:
                error_message = f"Project {self.project_id} not found"
                self.log_error(error_message)
                return {"success": False, "error": error_message}
            
            # Get project directory
            project_dir = project.get("temp_dir")
            
            # Update project status
            self.update_project_status(
                status="analyzing",
                progress=15.0,
                current_step="Beginning project analysis"
            )
            
            # Step 1: Structure Analysis
            structure_agent = StructureAnalysisAgent(self.project_id)
            structure_result = await structure_agent.execute(project_dir)
            
            if not structure_result.get("success", False):
                error_message = f"Structure analysis failed: {structure_result.get('error', 'Unknown error')}"
                self.log_error(error_message)
                return {"success": False, "error": error_message}
            
            # Step 2: Content Analysis
            content_agent = ContentAnalysisAgent(self.project_id)
            content_result = await content_agent.execute(structure_result.get("file_nodes", []))
            
            if not content_result.get("success", False):
                error_message = f"Content analysis failed: {content_result.get('error', 'Unknown error')}"
                self.log_error(error_message)
                return {"success": False, "error": error_message}
            
            # Step 3: Classify components
            classification_result = await self._classify_components(structure_result.get("file_nodes", []))
            
            # Step 4: Detect primary languages and frameworks
            language_detection = await self._detect_languages_and_frameworks(
                structure_result.get("file_nodes", []),
                content_result.get("metadata_counts", {})
            )
            
            # Update project with detected languages/frameworks if not provided initially
            await self._update_project_languages(language_detection)
            
            # Update project status
            self.update_project_status(
                status="analyzed",
                progress=30.0,
                current_step="Project analysis completed"
            )
            
            # Create analysis report
            report = self.create_report(
                report_type="analysis",
                message="Project analysis completed",
                details={
                    "file_count": structure_result.get("file_count", 0),
                    "folder_count": structure_result.get("folder_count", 0),
                    "metadata": content_result.get("metadata_counts", {}),
                    "components": classification_result.get("component_counts", {}),
                    "languages": language_detection.get("languages", {}),
                    "frameworks": language_detection.get("frameworks", {})
                }
            )
            
            return {
                "success": True,
                "structure": structure_result,
                "content": content_result,
                "classification": classification_result,
                "languages": language_detection,
                "report": report
            }
            
        except Exception as e:
            error_message = f"Error in AnalysisAgent: {str(e)}"
            self.log_error(error_message)
            return {"success": False, "error": error_message}
    
    async def _classify_components(self, file_nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Classify project components based on file types and content.
        
        Args:
            file_nodes: List of file nodes from structure analysis
            
        Returns:
            Dictionary with classification results
        """
        components = {
            "ui": [],
            "logic": [],
            "data": [],
            "config": [],
            "tests": [],
            "documentation": []
        }
        
        component_properties_list = []
        component_relationships = []
        
        for file_node in file_nodes:
            relative_path = file_node.get("relative_path", "")
            file_type = file_node.get("file_type", "unknown")
            file_id = file_node.get("file_id")
            
            # Skip if file_id is missing
            if not file_id:
                continue
            
            # Enhanced classification rules
            if file_type in ["html", "css", "scss", "sass", "react", "tsx", "jsx"]:
                component_type = "ui"
            elif file_type in ["json", "yaml", "yml", "xml", "toml", "ini", "config"]:
                component_type = "config"
            elif file_type in ["sql", "csv", "db", "sqlite"]:
                component_type = "data"
            elif file_type in ["md", "markdown", "txt", "rst", "adoc"]:
                component_type = "documentation"
            else:
                component_type = "logic"
            
            # Path-based refinements
            if any(ui_dir in relative_path.lower() for ui_dir in ["/ui/", "\\ui\\", "/view", "\\view", "/template", "\\template", "/components", "\\components"]):
                component_type = "ui"
            elif any(data_dir in relative_path.lower() for data_dir in ["/data/", "\\data\\", "/model", "\\model", "/entity", "\\entity", "/schema", "\\schema"]):
                component_type = "data"
            elif any(config_dir in relative_path.lower() for config_dir in ["/config/", "\\config\\", "/setting", "\\setting"]):
                component_type = "config"
            elif any(test_dir in relative_path.lower() for test_dir in ["/test", "\\test", "_test", "spec.ts", "spec.js", "/tests/", "\\tests\\"]):
                component_type = "tests"
            elif any(doc_dir in relative_path.lower() for doc_dir in ["/doc", "\\doc", "/docs/", "\\docs\\"]):
                component_type = "documentation"
            
            # Add to appropriate component list
            components[component_type].append(file_node)
            
            # Prepare Component node properties
            component_id = str(uuid.uuid4())
            component_properties = {
                "component_id": component_id,
                "project_id": self.project_id,
                "file_id": file_id,
                "type": component_type,
                "created_at": datetime.utcnow().isoformat()
            }
            
            component_properties_list.append(component_properties)
            
            # Prepare relationship from File to Component
            component_relationships.append({
                "from_label": NodeType.FILE,
                "from_property": "file_id",
                "from_value": file_id,
                "to_label": NodeType.COMPONENT,
                "to_property": "component_id",
                "to_value": component_id,
                "relationship_type": RelationshipType.CLASSIFIES_AS,
                "properties": {}
            })
        
        # Batch create Component nodes
        if component_properties_list:
            batch_size = 100
            for i in range(0, len(component_properties_list), batch_size):
                batch = component_properties_list[i:i+batch_size]
                self.db.create_nodes_batch("Component", batch)
        
        # Batch create File->Component relationships
        if component_relationships:
            batch_size = 100
            for i in range(0, len(component_relationships), batch_size):
                batch = component_relationships[i:i+batch_size]
                self.db.create_relationships_batch(batch)
        
        # Count components by type
        component_counts = {component_type: len(files) for component_type, files in components.items()}
        
        return {
            "success": True,
            "components": components,
            "component_counts": component_counts
        }
    
    async def _detect_languages_and_frameworks(
        self, 
        file_nodes: List[Dict[str, Any]],
        metadata_counts: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Detect primary languages and frameworks used in the project.
        
        Args:
            file_nodes: List of file nodes from structure analysis
            metadata_counts: Metadata counts from content analysis
            
        Returns:
            Dictionary with language and framework detection results
        """
        # Count file types to determine primary languages
        language_counts = {}
        for file_node in file_nodes:
            file_type = file_node.get("file_type", "unknown")
            if file_type != "unknown":
                language_counts[file_type] = language_counts.get(file_type, 0) + 1
        
        # Sort languages by count
        languages = sorted(
            [{"name": lang, "count": count} for lang, count in language_counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )
        
        # Primary language is the most common
        primary_language = languages[0]["name"] if languages else "unknown"
        
        # Detect frameworks based on files and dependencies
        frameworks = []
        
        # Check for common framework indicators in file paths
        framework_indicators = {
            "react": ["/react", "\\react", "jsx", "tsx", "react.js"],
            "angular": ["/angular", "\\angular", "component.ts", "module.ts"],
            "vue": ["/vue", "\\vue", ".vue"],
            "django": ["/django", "\\django", "urls.py", "views.py", "models.py", "admin.py"],
            "flask": ["app.py", "flask", "routes.py"],
            "express": ["express", "app.js", "routes.js"],
            "spring": ["SpringApplication", "application.properties", "application.yml"],
            "dotnet": [".csproj", ".cs", "Program.cs"],
        }
        
        for framework, indicators in framework_indicators.items():
            for file_node in file_nodes:
                relative_path = file_node.get("relative_path", "").lower()
                if any(indicator.lower() in relative_path for indicator in indicators):
                    frameworks.append(framework)
                    break
        
        # Remove duplicates
        frameworks = list(set(frameworks))
        
        # Count frameworks by files
        framework_counts = {}
        for framework in frameworks:
            count = sum(1 for file_node in file_nodes 
                       if any(indicator.lower() in file_node.get("relative_path", "").lower() 
                              for indicator in framework_indicators[framework]))
            framework_counts[framework] = count
        
        return {
            "success": True,
            "languages": language_counts,
            "primary_language": primary_language,
            "frameworks": framework_counts,
            "metadata_counts": metadata_counts
        }
    
    async def _update_project_languages(self, language_detection: Dict[str, Any]) -> None:
        """
        Update project with detected languages and frameworks if not provided initially.
        
        Args:
            language_detection: Detection results
        """
        # Get current project
        project = self.db.find_node("Project", "project_id", self.project_id)
        if not project:
            return
        
        updates_needed = False
        properties_to_update = {}
        
        # Update source language if not provided
        if not project.get("source_language") and language_detection.get("primary_language"):
            properties_to_update["source_language"] = language_detection.get("primary_language")
            updates_needed = True
        
        # Update source framework if not provided
        if not project.get("source_framework") and language_detection.get("frameworks"):
            frameworks = language_detection.get("frameworks", {})
            if frameworks:
                # Get most common framework
                primary_framework = max(frameworks.items(), key=lambda x: x[1])[0]
                properties_to_update["source_framework"] = primary_framework
                updates_needed = True
        
        # Update project if needed
        if updates_needed:
            properties_to_update["updated_at"] = datetime.utcnow().isoformat()
            
            # Update project node
            update_query = """
            MATCH (p:Project {project_id: $project_id})
            SET p += $properties
            RETURN p
            """
            self.db.run_query(
                update_query,
                {
                    "project_id": self.project_id,
                    "properties": properties_to_update
                }
            )