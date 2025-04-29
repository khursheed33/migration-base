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
        
        # Begin analysis
        analysis_task.delay(project_id)
        
        return upload_result
        
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
        # mapping_task.delay(project_id)
        
        return analysis_result
        
    except Exception as e:
        error_message = f"Error in analysis_task: {str(e)}"
        logger.error(error_message)
        return {"success": False, "error": error_message}


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