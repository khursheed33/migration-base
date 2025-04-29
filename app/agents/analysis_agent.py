import os
from typing import Any, Dict, List, Optional, Tuple

from app.agents.base_agent import BaseAgent
from app.agents.structure_analysis_agent import StructureAnalysisAgent
from app.config.settings import get_settings

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
            
            # Step 2: Content Analysis (currently a placeholder)
            # content_agent = ContentAnalysisAgent(self.project_id)
            # content_result = await content_agent.execute(structure_result.get("file_nodes", []))
            
            # if not content_result.get("success", False):
            #     error_message = f"Content analysis failed: {content_result.get('error', 'Unknown error')}"
            #     self.log_error(error_message)
            #     return {"success": False, "error": error_message}
            
            # Placeholder for content analysis result
            content_result = {"success": True, "message": "Content analysis not implemented yet"}
            
            # Step 3: Classify components (currently a placeholder)
            classification_result = self._classify_components(structure_result.get("file_nodes", []))
            
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
                    "components": classification_result.get("components", [])
                }
            )
            
            return {
                "success": True,
                "structure": structure_result,
                "content": content_result,
                "classification": classification_result,
                "report": report
            }
            
        except Exception as e:
            error_message = f"Error in AnalysisAgent: {str(e)}"
            self.log_error(error_message)
            return {"success": False, "error": error_message}
    
    def _classify_components(self, file_nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Placeholder method for classifying project components.
        In the real implementation, this would analyze the files and classify them
        into UI, logic, data, or config components.
        
        Args:
            file_nodes: List of file nodes from structure analysis
            
        Returns:
            Dictionary with classification results
        """
        # This is a simple placeholder implementation that classifies components
        # based on file types and paths
        
        components = {
            "ui": [],
            "logic": [],
            "data": [],
            "config": []
        }
        
        for file_node in file_nodes:
            relative_path = file_node.get("relative_path", "")
            file_type = file_node.get("file_type", "unknown")
            
            # Simple classification rules
            if file_type in ["html", "css", "scss", "sass", "react"]:
                component_type = "ui"
            elif file_type in ["json", "yaml", "yml", "xml", "toml", "ini", "config"]:
                component_type = "config"
            elif file_type in ["sql", "csv"]:
                component_type = "data"
            else:
                component_type = "logic"
            
            # Path-based refinements
            if "/ui/" in relative_path or "\\ui\\" in relative_path:
                component_type = "ui"
            elif "/data/" in relative_path or "\\data\\" in relative_path:
                component_type = "data"
            elif "/config/" in relative_path or "\\config\\" in relative_path:
                component_type = "config"
            
            # Add to appropriate component list
            components[component_type].append(file_node)
            
            # Create Component node and relationship
            component_id = f"component_{file_node.get('file_id', '')}"
            component_properties = {
                "component_id": component_id,
                "project_id": self.project_id,
                "file_id": file_node.get("file_id"),
                "type": component_type
            }
            
            component_node = self.db.create_node("Component", component_properties)
            
            # Create relationship from File to Component
            self.db.create_relationship(
                from_label="File",
                from_property="file_id",
                from_value=file_node.get("file_id"),
                to_label="Component",
                to_property="component_id",
                to_value=component_id,
                relationship_type="CLASSIFIES_AS"
            )
        
        return {
            "success": True,
            "components": components
        } 