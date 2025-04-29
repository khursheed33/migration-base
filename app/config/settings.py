import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""
    
    # Application settings
    APP_NAME: str = Field(default="Code Migration Framework", description="Application name")
    APP_ENV: str = Field(default="development", description="Application environment")
    DEBUG: bool = Field(default=True, description="Debug mode")
    SECRET_KEY: str = Field(default="your_secret_key_here", description="Secret key for JWT")
    
    # Neo4j settings
    NEO4J_URI: str = Field(default="bolt://localhost:7687", description="Neo4j URI")
    NEO4J_USER: str = Field(default="neo4j", description="Neo4j username")
    NEO4J_PASSWORD: str = Field(default="password", description="Neo4j password")
    
    # OpenAI settings
    OPENAI_API_KEY: str = Field(default="your_openai_api_key_here", description="OpenAI API key")
    OPENAI_MODEL: str = Field(default="gpt-4o", description="OpenAI model to use")
    
    # Celery settings
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0", description="Celery broker URL")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0", description="Celery result backend URL")
    
    # Storage settings
    STORAGE_DIR: str = Field(default="./storage", description="Storage directory for project files")
    TEMP_DIR: str = Field(default="./tmp", description="Temporary directory for extracted files")
    
    # S3 settings (optional)
    USE_S3: bool = Field(default=False, description="Whether to use S3 for storage")
    AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None, description="AWS access key ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(default=None, description="AWS secret access key")
    AWS_REGION: Optional[str] = Field(default=None, description="AWS region")
    AWS_BUCKET_NAME: Optional[str] = Field(default=None, description="AWS S3 bucket name")

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Returns:
        Settings: Application settings
    """
    return Settings() 