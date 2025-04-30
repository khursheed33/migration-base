import os
import logging
import asyncio
from typing import Any, Dict, Optional

from app.celery_app import celery_app
from app.agents.upload_agent import UploadAgent
from app.agents.analysis_agent import AnalysisAgent
from app.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


@celery_app.task
def process_upload(project_id: str, zip_file_path: str, project_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a project upload in the background.
    
    Args:
        project_id: Project ID
        zip_file_path: Path to the uploaded ZIP file
        project_data: Project metadata
        
    Returns:
        Upload processing results
    """
    try:
        logger.info(f"Starting upload processing for project {project_id}")
        
        # Create and execute upload agent
        upload_agent = UploadAgent(project_id)
        
        # Execute upload agent with full analysis including OpenAI-based file descriptions
        upload_result = asyncio.run(upload_agent.execute(zip_file_path, project_data))
        
        # Clean up temporary ZIP file
        try:
            os.unlink(zip_file_path)
            logger.info(f"Cleaned up temporary ZIP file: {zip_file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary ZIP file: {str(e)}")
        
        if not upload_result["success"]:
            logger.error(f"Upload processing failed: {upload_result.get('error', 'Unknown error')}")
            return upload_result
        
        # The upload agent now handles:
        # 1. Extracting files
        # 2. Analyzing project structure (creating File nodes)
        # 3. Analyzing file contents with OpenAI (generating descriptions, extracting components)
        # 4. Creating mappings for components
        # 5. Updating project status throughout the process
        
        # Begin deeper analysis if upload was successful
        logger.info(f"Upload and initial analysis successful, starting detailed analysis for project {project_id}")
        analysis_result = analysis_task(project_id)
        
        return {
            "success": True, 
            "project_id": project_id,
            "message": "Project uploaded, analyzed and ready for migration",
            "upload_result": upload_result,
            "analysis_started": True,
            "files_analyzed": upload_result.get("files_analyzed", 0),
            "components_mapped": upload_result.get("components_mapped", 0)
        }
        
    except Exception as e:
        error_message = f"Error in process_upload: {str(e)}"
        logger.error(error_message)
        return {"success": False, "error": error_message}


@celery_app.task
def analysis_task(project_id: str) -> Dict[str, Any]:
    """
    Run analysis on the project in the background.
    
    Args:
        project_id: Project ID
        
    Returns:
        Analysis results
    """
    try:
        logger.info(f"Starting analysis for project {project_id}")
        
        # Create and execute analysis agent
        analysis_agent = AnalysisAgent(project_id)
        analysis_result = asyncio.run(analysis_agent.execute())
        
        if not analysis_result["success"]:
            logger.error(f"Analysis failed: {analysis_result.get('error', 'Unknown error')}")
            return analysis_result
        
        # Begin mapping
        logger.info(f"Analysis successful, starting mapping for project {project_id}")
        # mapping_result = mapping_task(project_id)
        
        return {
            "success": True,
            "project_id": project_id,
            "message": "Project analysis completed successfully",
            "structure_analyzed": True,
            "content_analyzed": True,
            "components_classified": True
        }
        
    except Exception as e:
        error_message = f"Error in analysis_task: {str(e)}"
        logger.error(error_message)
        return {"success": False, "error": error_message, "project_id": project_id}


@celery_app.task
def start_migration(project_id: str) -> Dict[str, Any]:
    """
    Start or resume the migration process for a project.
    
    Args:
        project_id: Project ID
        
    Returns:
        Status of the migration start
    """
    try:
        logger.info(f"Starting/resuming migration for project {project_id}")
        
        from app.config.dependencies import dependency_initializer
        neo4j_manager = dependency_initializer.get_service("neo4j")
        
        # Get project status
        project = neo4j_manager.find_node("Project", "project_id", project_id)
        if not project:
            error_message = f"Project {project_id} not found"
            logger.error(error_message)
            return {"success": False, "error": error_message}
        
        status = project.get("status", "")
        
        # Determine next step based on status
        if status == "uploaded":
            # Start with analysis
            return analysis_task(project_id)
        elif status == "analyzed" or status == "structure_analyzed" or status == "content_analyzed":
            # Continue with mapping
            logger.info(f"Project {project_id} already analyzed, would start mapping here")
            # return mapping_task(project_id)
            return {"success": True, "message": "Project analysis already complete", "next_step": "mapping"}
        elif status == "mapped":
            # Continue with strategy
            logger.info(f"Project {project_id} already mapped, would start strategy here")
            # return strategy_task(project_id)
            return {"success": True, "message": "Project mapping already complete", "next_step": "strategy"}
        else:
            logger.info(f"Project {project_id} status is {status}, continuing migration")
            # Just restart the analysis for now
            return analysis_task(project_id)
            
    except Exception as e:
        error_message = f"Error starting migration: {str(e)}"
        logger.error(error_message)
        return {"success": False, "error": error_message, "project_id": project_id}


# Additional tasks will be added for subsequent steps:
# @celery_app.task
# def mapping_task(project_id: str) -> Dict[str, Any]:
#     pass
#
# @celery_app.task
# def strategy_task(project_id: str) -> Dict[str, Any]:
#     pass
#
# @celery_app.task
# def code_generation_task(project_id: str) -> Dict[str, Any]:
#     pass
#
# Etc. 