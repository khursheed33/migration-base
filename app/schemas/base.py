from datetime import datetime
from typing import Any, Dict, List, Optional
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
    
    file_path: str = Field(..., description="Path to the uploaded file")
    temp_dir: Optional[str] = Field(None, description="Temporary directory for processing")
    status: str = Field("uploaded", description="Initial project status")
    progress: float = Field(0, description="Initial progress")
    current_step: str = Field("Project upload", description="Initial step")


class StepDetails(BaseModel):
    """Step details model."""
    
    name: str = Field(..., description="Step name")
    description: str = Field(..., description="Step description")
    estimated_duration: str = Field(..., description="Estimated duration")


class PerformanceMetrics(BaseModel):
    """Performance metrics model."""
    
    processing_speed: str = Field(..., description="Processing speed")
    memory_usage: str = Field(..., description="Memory usage")
    cpu_usage: str = Field(..., description="CPU usage")


class StatusDetails(BaseModel):
    """Status details model."""
    
    files_processed: int = Field(..., description="Number of files processed")
    total_files: int = Field(..., description="Total number of files")
    current_file: str = Field(..., description="Current file being processed")
    last_error: Optional[str] = Field(None, description="Last error message")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")
    performance_metrics: PerformanceMetrics = Field(..., description="Performance metrics")


class StatusResponse(BaseModel):
    """Project status response model."""
    
    project_id: str = Field(..., description="Project ID")
    status: str = Field(..., description="Project status")
    progress: float = Field(..., description="Progress percentage")
    current_step: str = Field(..., description="Current migration step")
    current_step_details: Optional[StepDetails] = Field(None, description="Details of current step")
    steps_completed: List[StepDetails] = Field(default_factory=list, description="Completed steps")
    steps_remaining: List[StepDetails] = Field(default_factory=list, description="Remaining steps")
    status_details: StatusDetails = Field(..., description="Detailed status information")
    updated_at: datetime = Field(..., description="Update timestamp")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")


class ProjectResponse(ProjectBase):
    """Project response model."""
    
    project_id: str = Field(..., description="Project ID")
    status: str = Field(..., description="Project status")
    temp_dir: str = Field(..., description="Temporary directory")
    migrated_dir: Optional[str] = Field(None, description="Migrated directory")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")


class FileMetadata(BaseModel):
    """File metadata model."""
    
    total_files: int = Field(..., description="Total number of files in project")
    function_count: int = Field(..., description="Number of functions in file")
    class_count: int = Field(..., description="Number of classes in file")
    enum_count: int = Field(..., description="Number of enums in file")
    extension_count: int = Field(..., description="Number of extensions in file")
    import_count: int = Field(..., description="Number of imports in file")
    reference_count: int = Field(..., description="Number of references in file")


class RelationshipMetadata(BaseModel):
    """Relationship metadata model."""
    
    imported_items: List[str] = Field(default_factory=list, description="Items imported from target file")
    reference_locations: List[Dict[str, Any]] = Field(default_factory=list, description="Locations of references in source file")


class ProjectSummary(BaseModel):
    """Project summary model."""
    
    total_files: int = Field(..., description="Total number of files")
    total_functions: int = Field(..., description="Total number of functions")
    total_classes: int = Field(..., description="Total number of classes")
    total_enums: int = Field(..., description="Total number of enums")
    total_extensions: int = Field(..., description="Total number of extensions")
    total_relationships: int = Field(..., description="Total number of relationships")


class MetadataResponse(BaseModel):
    """Project metadata response model."""
    
    project_id: str = Field(..., description="Project ID")
    files: List[Dict[str, Any]] = Field(default_factory=list, description="File metadata")
    functions: List[Dict[str, Any]] = Field(default_factory=list, description="Function metadata")
    classes: List[Dict[str, Any]] = Field(default_factory=list, description="Class metadata")
    enums: List[Dict[str, Any]] = Field(default_factory=list, description="Enum metadata")
    extensions: List[Dict[str, Any]] = Field(default_factory=list, description="Extension metadata")
    relationships: List[Dict[str, Any]] = Field(default_factory=list, description="Relationship metadata")
    summary: ProjectSummary = Field(..., description="Project summary statistics")
    last_updated: str = Field(..., description="Last update timestamp")


class GraphNode(BaseModel):
    """Graph node model."""
    
    node_id: str = Field(..., description="Node ID")
    node_type: str = Field(..., description="Node type")
    properties: Dict[str, Any] = Field(..., description="Node properties")


class GraphRelationship(BaseModel):
    """Graph relationship model."""
    
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    relationship_type: str = Field(..., description="Relationship type")
    properties: Dict[str, Any] = Field(..., description="Relationship properties")


class GraphResponse(BaseModel):
    """Project graph response model."""
    
    project_id: str = Field(..., description="Project ID")
    nodes: List[GraphNode] = Field(default_factory=list, description="Graph nodes")
    relationships: List[GraphRelationship] = Field(default_factory=list, description="Graph relationships")


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