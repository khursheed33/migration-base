from enum import Enum


class RelationshipType(str, Enum):
    """Enum for relationship types in the graph database."""
    
    # Project relationships
    CONTAINS = "CONTAINS"
    CONTAINS_FILE = "CONTAINS_FILE"
    
    # File relationships
    HAS_FUNCTION = "HAS_FUNCTION"
    HAS_CLASS = "HAS_CLASS" 
    HAS_ENUM = "HAS_ENUM"
    HAS_EXTENSION = "HAS_EXTENSION"
    HAS_FOLDER = "HAS_FOLDER"
    HAS_FILE = "HAS_FILE"
    
    # File to file relationships
    IMPORTS = "IMPORTS"
    REFERENCES = "REFERENCES"
    DEPENDS_ON = "DEPENDS_ON"
    
    # Component relationships
    CLASSIFIES_AS = "CLASSIFIES_AS"
    MAPS_TO = "MAPS_TO"
    TARGETS = "TARGETS"
    PLANNED_IN = "PLANNED_IN"
    
    # Migration-specific relationships
    MIGRATES_TO = "MIGRATES_TO"
    TRANSLATES_TO = "TRANSLATES_TO"
    EQUIVALENT_TO = "EQUIVALENT_TO"
    IMPLEMENTS_PATTERN = "IMPLEMENTS_PATTERN"
    CONVERTS_TO = "CONVERTS_TO"
    REPLACES = "REPLACES"
    
    # Report and feedback relationships
    REPORTED_IN = "REPORTED_IN"
    FEEDBACK_FOR = "FEEDBACK_FOR"


class NodeType(str, Enum):
    """Enum for node types in the graph database."""
    
    PROJECT = "Project"
    FILE = "File"
    FOLDER = "Folder"
    FUNCTION = "Function"
    CLASS = "Class"
    ENUM = "Enum"
    EXTENSION = "Extension"
    DEPENDENCY = "Dependency"
    COMPONENT = "Component"
    MAPPING = "Mapping"
    TARGET_COMPONENT = "TargetComponent"
    STRATEGY = "Strategy"
    REPORT = "Report"
    FEEDBACK = "Feedback" 