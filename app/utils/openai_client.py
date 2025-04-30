import os
import logging
from typing import Optional
from openai import AsyncOpenAI

from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Cache for the OpenAI client
_openai_client = None


def get_openai_client() -> Optional[AsyncOpenAI]:
    """
    Get or create an AsyncOpenAI client instance.
    
    Returns:
        AsyncOpenAI client or None if API key is not configured
    """
    global _openai_client
    
    if _openai_client is not None:
        return _openai_client
    
    # Check if API key is set
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        logger.warning("OpenAI API key not configured")
        return None
    
    try:
        # Create a new client instance
        _openai_client = AsyncOpenAI(
            api_key=api_key,
            timeout=settings.OPENAI_TIMEOUT
        )
        logger.info("OpenAI client initialized")
        return _openai_client
    except Exception as e:
        logger.error(f"Error initializing OpenAI client: {str(e)}")
        return None 