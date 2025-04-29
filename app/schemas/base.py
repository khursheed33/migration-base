from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class BaseResponse(BaseModel):
    """Base response model for all API responses."""
    
    status: str = Field(..., description="Response status (success, error)")
    message: str = Field(..., description="Response message")


class SuccessResponse(BaseResponse):
    """Success response model."""
    
    status: str = Field("success", description="Response status")
    data: Optional[Any] = Field(None, description="Response data")


class ErrorResponse(BaseResponse):
    """Error response model."""
    
    status: str = Field("error", description="Response status")
    error_code: Optional[str] = Field(None, description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")


class ProjectBase(BaseModel):
    """Base project model."""
    
    user_id: str = Field(..., description="User ID")
    description: Optional[str] = Field(None, description="Project description")
    source_language: Optional[str] = Field(None, description="Source language")
    target_language: Optional[str] = Field(None, description="Target language")
    source_framework: Optional[str] = Field(None, description="Source framework")
    target_framework: Optional[str] = Field(None, description="Target framework")
    custom_mappings: Optional[Dict[str, Any]] = Field(None, description="Custom mappings")


class ProjectCreate(ProjectBase):
    """Project creation model."""
    
    pass


class ProjectResponse(ProjectBase):
    """Project response model."""
    
    project_id: str = Field(..., description="Project ID")
    status: str = Field(..., description="Project status")
    temp_dir: str = Field(..., description="Temporary directory")
    migrated_dir: Optional[str] = Field(None, description="Migrated directory")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")


class StatusResponse(BaseModel):
    """Project status response model."""
    
    project_id: str = Field(..., description="Project ID")
    status: str = Field(..., description="Project status")
    progress: float = Field(..., description="Progress percentage")
    current_step: str = Field(..., description="Current migration step")
    steps_completed: List[str] = Field(default_factory=list, description="Completed steps")
    steps_remaining: List[str] = Field(default_factory=list, description="Remaining steps")
    updated_at: datetime = Field(..., description="Update timestamp")


class MetadataResponse(BaseModel):
    """Project metadata response model."""
    
    project_id: str = Field(..., description="Project ID")
    files: List[Dict[str, Any]] = Field(default_factory=list, description="File metadata")
    functions: List[Dict[str, Any]] = Field(default_factory=list, description="Function metadata")
    classes: List[Dict[str, Any]] = Field(default_factory=list, description="Class metadata")
    enums: List[Dict[str, Any]] = Field(default_factory=list, description="Enum metadata")
    extensions: List[Dict[str, Any]] = Field(default_factory=list, description="Extension metadata")
    relationships: List[Dict[str, Any]] = Field(default_factory=list, description="Relationship metadata")


class GraphResponse(BaseModel):
    """Project graph response model."""
    
    project_id: str = Field(..., description="Project ID")
    nodes: List[Dict[str, Any]] = Field(default_factory=list, description="Graph nodes")
    relationships: List[Dict[str, Any]] = Field(default_factory=list, description="Graph relationships")


class FeedbackCreate(BaseModel):
    """Feedback creation model."""
    
    project_id: str = Field(..., description="Project ID")
    issue: str = Field(..., description="Issue description")
    suggestion: Optional[str] = Field(None, description="Suggested resolution")
    component: Optional[str] = Field(None, description="Component the feedback relates to")


class FeedbackResponse(FeedbackCreate):
    """Feedback response model."""
    
    feedback_id: str = Field(..., description="Feedback ID")
    resolution: Optional[str] = Field(None, description="Resolution status or details")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Update timestamp") 