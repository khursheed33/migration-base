# Code Migration Framework

## 1. Framework Overview

- **Objective**: A modular, agent-based migration framework in Python using FastAPI, LangGraph, and OpenAI to analyze, plan, migrate, test, and package software projects uploaded as ZIP files. The framework now uses **Neo4j** as the primary database to store detailed metadata, mappings, and other data, with generic schemas to support comprehensive metadata extraction. Enhanced metadata includes detailed attributes for functions, classes, enums, decorators, and more to enable precise migration of legacy code.
- **Tech Stack** (Updated):
  - Backend: Python 3.11+, FastAPI
  - Agent Orchestration: LangGraph
  - GenAI: OpenAI API (e.g., GPT-4o)
  - Code Analysis: `tree-sitter`, OpenAI
  - File Handling: `zipfile`, `shutil`
  - Database: **Neo4j** (replacing SQLite) for metadata storage
  - Database Driver: `neo4j` Python driver
  - Testing: `pytest`
  - Task Queue: Celery, Redis
  - Storage: Local filesystem, optional AWS S3
  - Security: JWT, `python-multipart`
  - Deployment: Docker
- **New Features**:
  - Neo4j as the primary database with generic schemas for metadata, mappings, and project data.
  - Detailed metadata extraction for functions (return types, arguments, decorators), classes (singleton, static, inheritance), enums, extensions, and other code attributes.
  - Enhanced file content and relationship mappings to support legacy code migration.
  - Graph-based queries in Neo4j to leverage file relationships and dependencies.
  - Flexible schema design to accommodate future metadata requirements.

## 2. Updated Agents and Responsibilities

The framework retains the existing agents and enhances their functionality to interact with Neo4j and handle detailed metadata. The Analysis Agent’s sub-agents are updated to extract and store granular metadata.

1. **Upload Agent** (Unchanged):
   - Validates and extracts ZIP files, parses payload, stores project metadata in Neo4j.

2. **Analysis Agent** (Enhanced):
   - **Sub-Agent: Structure Analysis Agent**:
     - **Tasks**: Catalog project structure, store file paths and metadata in Neo4j.
     - **Inputs**: Extracted project directory.
     - **Outputs**: File structure nodes and relationships in Neo4j.
     - **Implementation**: Uses `pathlib` for traversal, `neo4j` driver for storage.
   - **Sub-Agent: Content Analysis Agent**:
     - **Tasks**: Extract detailed metadata for file contents (functions, classes, enums, decorators), identify relationships (imports, references).
     - **Inputs**: File structure metadata, project files.
     - **Outputs**: Content nodes (functions, classes, etc.) and relationships in Neo4j.
     - **Implementation**: Uses `tree-sitter` for AST parsing, OpenAI for semantic analysis.
   - **Tasks (Main Agent)**:
     - Coordinate sub-agents, detect languages/frameworks, classify components.
     - **Outputs**: Analysis report stored as Neo4j nodes/relationships.

3. **Mapping Agent** (Enhanced):
   - **Tasks**: Generate component, data type, and legacy code mappings, store in Neo4j.
   - **Inputs**: Analysis report, content metadata, custom mappings.
   - **Outputs**: Mapping nodes and relationships in Neo4j.
   - **Implementation**: Uses OpenAI to infer mappings, stores in Neo4j.

4. **Strategy Agent** (Enhanced):
   - **Tasks**: Design migration strategies using Neo4j queries to analyze metadata and relationships.
   - **Inputs**: Analysis report, mappings, content metadata.
   - **Outputs**: Strategy nodes in Neo4j.
   - **Implementation**: Uses Cypher queries to prioritize migrations.

5. **Dependency Agent** (Enhanced):
   - **Tasks**: Map dependencies and target framework components (libraries, data types), store in Neo4j.
   - **Outputs**: Dependency and component nodes in Neo4j.

6. **Code Generation Agent** (Enhanced):
   - **Tasks**: Generate target code using Neo4j metadata (file paths, relationships, detailed attributes).
   - **Outputs**: Migrated code, configuration files.

7. **Architecture Agent**, **Optimization Agent**, **Testing Agent**, **Error Resolution Agent**, **Packaging Agent**, **Audit Agent**, **Notification Agent**, **Feedback Agent** (Enhanced):
   - Updated to query Neo4j for metadata and store results as nodes/relationships.
   - Leverage detailed metadata (e.g., function arguments, class types) for precise tasks.

## 3. Neo4j Database Design
Neo4j’s graph database is used to store metadata, mappings, and project data as nodes and relationships. The schema is generic, allowing flexible addition of attributes to support detailed metadata and future requirements.

### 3.1. Node Types
1. **Project**:
   - **Properties**:
     - `project_id`: string (unique)
     - `user_id`: string
     - `temp_dir`: string
     - `migrated_dir`: string
     - `status`: string (e.g., uploaded, analyzing)
     - `created_at`: datetime
     - `updated_at`: datetime
   - **Description**: Represents a project being migrated.

2. **File**:
   - **Properties**:
     - `file_path`: string (unique per project)
     - `project_id`: string
     - `file_type`: string (e.g., python, java)
     - `size`: integer
     - `relative_path`: string
   - **Description**: Stores file structure metadata.

3. **Function**:
   - **Properties**:
     - `function_id`: string (unique per file)
     - `file_path`: string
     - `project_id`: string
     - `name`: string
     - `return_type`: string (e.g., int, void)
     - `arguments`: list of JSON objects (e.g., `[{ "name": "x", "type": "int" }]`)
     - `decorators`: list of strings (e.g., `["@staticmethod", "@deprecated"]`)
     - `is_static`: boolean
     - `is_async`: boolean
     - `docstring`: string
   - **Description**: Stores detailed function metadata.

4. **Class**:
   - **Properties**:
     - `class_id`: string (unique per file)
     - `file_path`: string
     - `project_id`: string
     - `name`: string
     - `type`: string (e.g., singleton, abstract, interface)
     - `is_static`: boolean
     - `is_final`: boolean
     - `superclasses`: list of strings (inheritance)
     - `interfaces`: list of strings
     - `methods`: list of JSON objects (referencing Function nodes)
     - `attributes`: list of JSON objects (e.g., `[{ "name": "id", "type": "int", "visibility": "private" }]`)
     - `docstring`: string
   - **Description**: Stores detailed class metadata.

5. **Enum**:
   - **Properties**:
     - `enum_id`: string (unique per file)
     - `file_path`: string
     - `project_id`: string
     - `name`: string
     - `values`: list of strings
     - `docstring`: string
   - **Description**: Stores enum metadata.

6. **Extension**:
   - **Properties**:
     - `extension_id`: string (unique per file)
     - `file_path`: string
     - `project_id`: string
     - `name`: string
     - `base_type`: string (e.g., class/interface being extended)
     - `methods`: list of JSON objects (referencing Function nodes)
   - **Description**: Stores extension metadata (e.g., Python `__init__` extensions, Kotlin extensions).

7. **Component**:
   - **Properties**:
     - `component_id`: string (unique per project)
     - `project_id`: string
     - `file_path`: string
     - `type`: string (e.g., ui, logic, data, config)
   - **Description**: Classifies files/components.

8. **Dependency**:
   - **Properties**:
     - `dependency_id`: string (unique per project)
     - `project_id`: string
     - `name`: string
     - `version`: string
     - `type`: string (e.g., library, internal)
   - **Description**: Stores dependencies (external libraries, internal modules).

9. **Mapping**:
   - **Properties**:
     - `mapping_id`: string (unique per project)
     - `project_id`: string
     - `source_component`: string
     - `target_component`: string
     - `data_type_mapping`: JSON (e.g., `{ "source": "list", "target": "ArrayList" }`)
     - `is_custom`: boolean
   - **Description**: Stores component and data type mappings.

10. **TargetComponent**:
    - **Properties**:
      - `component_id`: string (unique per project)
      - `project_id`: string
      - `name`: string
      - `version`: string
      - `type`: string (e.g., library, data_type)
    - **Description**: Stores target framework components.

11. **Strategy**:
    - **Properties**:
      - `strategy_id`: string (unique per project)
      - `project_id`: string
      - `component_id`: string
      - `priority`: integer
      - `actions`: list of strings
    - **Description**: Stores migration strategies.

12. **Report**:
    - **Properties**:
      - `report_id`: string (unique per project)
      - `project_id`: string
      - `type`: string (e.g., migration, audit)
      - `details`: JSON
    - **Description**: Stores migration reports and audit logs.

13. **Feedback**:
    - **Properties**:
      - `feedback_id`: string (unique per project)
      - `project_id`: string
      - `issue`: string
      - `resolution`: string
      - `created_at`: datetime
    - **Description**: Stores user feedback.

### 3.2. Relationship Types
1. **CONTAINS**:
   - **From**: Project → File
   - **Description**: Links a project to its files.
2. **HAS_FUNCTION**:
   - **From**: File → Function
   - **Description**: Links a file to its functions.
3. **HAS_CLASS**:
   - **From**: File → Class
   - **Description**: Links a file to its classes.
4. **HAS_ENUM**:
   - **From**: File → Enum
   - **Description**: Links a file to its enums.
5. **HAS_EXTENSION**:
   - **From**: File → Extension
   - **Description**: Links a file to its extensions.
6. **IMPORTS**:
   - **From**: File → File
   - **Description**: Indicates a file imports another.
7. **REFERENCES**:
   - **From**: File → File
   - **Description**: Indicates a file references another (e.g., function calls).
8. **DEPENDS_ON**:
   - **From**: File → Dependency
   - **Description**: Links a file to its dependencies.
9. **CLASSIFIES_AS**:
   - **From**: File → Component
   - **Description**: Links a file to its component type.
10. **MAPS_TO**:
    - **From**: Component/Function/Class → Mapping
    - **Description**: Links source components to their mappings.
11. **TARGETS**:
    - **From**: Mapping → TargetComponent
    - **Description**: Links mappings to target framework components.
12. **PLANNED_IN**:
    - **From**: Component → Strategy
    - **Description**: Links components to migration strategies.
13. **REPORTED_IN**:
    - **From**: Project → Report
    - **Description**: Links projects to reports.
14. **FEEDBACK_FOR**:
    - **From**: Project → Feedback
    - **Description**: Links projects to feedback.

### 3.3. Example Cypher Queries
- **Retrieve File Structure**:
  ```cypher
  MATCH (p:Project {project_id: $project_id})-[:CONTAINS]->(f:File)
  RETURN f.file_path, f.file_type, f.size, f.relative_path
  ```
- **Retrieve Function Details**:
  ```cypher
  MATCH (f:File {project_id: $project_id})-[:HAS_FUNCTION]->(fn:Function)
  RETURN fn.name, fn.return_type, fn.arguments, fn.decorators
  ```
- **Find File Relationships**:
  ```cypher
  MATCH (f1:File {project_id: $project_id})-[:IMPORTS|:REFERENCES]->(f2:File)
  RETURN f1.file_path, f2.file_path, type(relationship)
  ```
- **Get Migration Mappings**:
  ```cypher
  MATCH (c:Component)-[:MAPS_TO]->(m:Mapping)-[:TARGETS]->(tc:TargetComponent)
  WHERE c.project_id = $project_id
  RETURN c.component_id, m.source_component, m.target_component, tc.name
  ```

## 4. Updated Workflow
The workflow incorporates Neo4j and detailed metadata extraction, updating the previous 20 steps.

1. **Receive and Extract ZIP File** (Upload Agent):
   - Extract ZIP to `/tmp/project_<user_id>_<timestamp>`.
   - Parse payload, create `Project` node in Neo4j.

2. **Parse Payload** (Upload Agent):
   - Validate payload, store metadata in `Project` node properties.

3. **Analyze Project Structure** (Structure Analysis Agent):
   - Catalog files, create `File` nodes with properties (path, type, size).
   - Create `CONTAINS` relationships from `Project` to `File` nodes.

4. **Analyze File Contents and Relationships** (Content Analysis Agent):
   - Parse files using `tree-sitter` and OpenAI to extract:
     - **Functions**: Name, return type, arguments, decorators, static/async flags, docstring.
     - **Classes**: Name, type (singleton, abstract), static/final flags, superclasses, interfaces, methods, attributes, docstring.
     - **Enums**: Name, values, docstring.
     - **Extensions**: Name, base type, methods.
   - Create `Function`, `Class`, `Enum`, `Extension` nodes in Neo4j.
   - Create relationships: `HAS_FUNCTION`, `HAS_CLASS`, `HAS_ENUM`, `HAS_EXTENSION`.
   - Identify imports/references, create `IMPORTS` and `REFERENCES` relationships.
   - Store dependencies in `Dependency` nodes, link via `DEPENDS_ON`.
   - Example metadata for a Python file:
     ```json
     {
       "file_path": "src/main.py",
       "imports": ["src/utils.py"],
       "functions": [
         {
           "name": "main",
           "return_type": "None",
           "arguments": [{"name": "args", "type": "list"}],
           "decorators": ["@staticmethod"],
           "is_static": true,
           "is_async": false,
           "docstring": "Main entry point"
         }
       ],
       "classes": [
         {
           "name": "DataProcessor",
           "type": "singleton",
           "is_static": false,
           "is_final": false,
           "superclasses": [],
           "interfaces": [],
           "methods": [{"name": "process", "return_type": "dict"}],
           "attributes": [{"name": "id", "type": "int", "visibility": "private"}],
           "docstring": "Processes data"
         }
       ],
       "enums": [],
       "extensions": []
     }
     ```

5. **Classify Project Elements** (Analysis Agent):
   - Classify files as UI, logic, data, or configs, create `Component` nodes.
   - Create `CLASSIFIES_AS` relationships.

6. **Generate Component/Entity Mapping Plan** (Mapping Agent):
   - Create mappings for components, data types, and legacy constructs (e.g., COBOL `DIVISION` → Java `class`).
   - Store in `Mapping` nodes, link via `MAPS_TO`.

7. **Map Target Framework Components** (Dependency Agent):
   - Identify target libraries, data types, and components (e.g., Java `LocalDate` for date handling).
   - Create `TargetComponent` nodes, link via `TARGETS`.

8. **Create Intermediate Representations (IRs)** (Code Generation Agent):
   - Generate ASTs and metadata, store in `File` node properties or separate nodes.

9. **Design Target Application Architecture** (Architecture Agent):
   - Use Neo4j queries to analyze relationships, propose architecture.

10. **Plan Migration Strategies** (Strategy Agent):
    - Query Neo4j for metadata (e.g., `MATCH (f:File)-[:IMPORTS]->(f2:File)`) to prioritize migrations.
    - Create `Strategy` nodes, link via `PLANNED_IN`.

11. **Generate Target Code** (Code Generation Agent):
    - Query Neo4j for file paths and metadata to read source files.
    - Use detailed metadata (e.g., function arguments, class types) for precise translation.

12. **Generate Configuration Files** (Code Generation Agent):
    - Use `TargetComponent` nodes to create configs.

13. **Setup Routing/Navigation** (Architecture Agent):
    - Use `REFERENCES` relationships to recreate navigation.

14. **Handle API Design** (Architecture Agent):
    - Query `Function` and `Class` nodes for API endpoints.

15. **Create Testing Scripts** (Testing Agent):
    - Generate tests using detailed metadata (e.g., method signatures).

16. **Package Migrated Code** (Packaging Agent):
    - Create ZIP/Docker image, include Neo4j metadata as JSON/CSV exports.

17. **Generate Migration Reports and Audit Logs** (Audit Agent):
    - Create `Report` nodes, summarize metadata usage and unmigrated parts.

18. **Notify User** (Notification Agent):
    - Send WebSocket updates with Neo4j-driven progress.

19. **Feedback Loop and Re-run** (Feedback Agent):
    - Store feedback in `Feedback` nodes, update mappings in Neo4j.

20. **End: Provide Migrated Project** (Packaging Agent):
    - Deliver project with metadata artifacts, clean up temporary storage.

## 5. Updated API Endpoints
- **GET /projects/{project_id}/metadata** (Updated):
  - **Description**: Retrieve Neo4j metadata (file structure, content, relationships).
  - **Response**: `{ "project_id": string, "files": [], "functions": [], "classes": [], "relationships": [] }`.
- **GET /projects/{project_id}/graph** (New):
  - **Description**: Export Neo4j subgraph for visualization (e.g., file relationships).
  - **Response**: `{ "nodes": [], "relationships": [] }`.
- Other endpoints (`/migrate`, `/status`, `/tests`, `/feedback`, `/download`, `/audit`, WebSocket) remain unchanged.

## 6. Non-Functional Requirements (Updated)
- **Performance**:
  - Process metadata extraction for a 100 MB project in under 2 minutes.
  - Execute Neo4j queries in under 100 ms for projects with 10,000 files.
- **Storage**:
  - Use Neo4j’s graph structure to store millions of nodes/relationships.
  - Export metadata as JSON/CSV for user reference.
- **Scalability**:
  - Support projects with up to 50,000 files using Neo4j’s distributed capabilities.
  - Deploy Neo4j in a cluster for high availability (optional).
- **Security**:
  - Secure Neo4j with username/password or JWT authentication.
  - Encrypt sensitive metadata (e.g., API keys in configs).

## 7. Additional Features
1. **Graph-Based Analysis**:
   - Use Neo4j to query file dependencies (e.g., `MATCH (f:File)-[:IMPORTS*1..3]->(f2:File)` for transitive imports).
   - Visualize relationships for debugging or user inspection.
2. **Detailed Metadata**:
   - Capture granular attributes (e.g., function decorators, class singletons) to handle legacy code (e.g., COBOL, Delphi).
   - Support migration of complex constructs (e.g., static methods, enums).
3. **Generic Schemas**:
   - Neo4j schema allows dynamic addition of properties (e.g., new attributes for future languages).
   - Relationships enable flexible modeling of code dependencies.
4. **Legacy Code Support**:
   - Detailed metadata ensures accurate migration of legacy constructs (e.g., COBOL `PERFORM` → Java loops).
   - OpenAI infers mappings for unsupported languages using metadata context.
5. **Metadata Export**:
   - Export Neo4j subgraphs as JSON/CSV for inclusion in packaged project.

## 8. Dependencies (Updated)
- **New Libraries**: `neo4j` (Neo4j Python driver), `pandas` (for metadata export).
- **Existing Libraries**: `fastapi`, `langgraph`, `openai`, `tree-sitter`, `pytest`, `celery`, `redis`, `python-jwt`, `python-multipart`, `uvicorn`, `pylint`, `websockets`, `smtplib`.

## 9. Error Handling (Updated)
- **Neo4j Errors**: Connection failures, query timeouts → Retry with exponential backoff, return 500 if persistent.
- **Metadata Errors**: Missing attributes, invalid relationships → Log and flag in reports.
- **Legacy Code Errors**: Unmappable constructs → Store in `Feedback` nodes, suggest manual intervention.

## 10. Example Neo4j Data
- **File Node**:
  ```json
  {
    "file_path": "/tmp/project_123/src/main.py",
    "project_id": "proj_123",
    "file_type": "python",
    "size": 1024,
    "relative_path": "src/main.py"
  }
  ```
- **Function Node**:
  ```json
  {
    "function_id": "main_123",
    "file_path": "/tmp/project_123/src/main.py",
    "project_id": "proj_123",
    "name": "main",
    "return_type": "None",
    "arguments": [{"name": "args", "type": "list"}],
    "decorators": ["@staticmethod"],
    "is_static": true,
    "is_async": false,
    "docstring": "Main entry point"
  }
  ```
- **Class Node**:
  ```json
  {
    "class_id": "DataProcessor_123",
    "file_path": "/tmp/project_123/src/main.py",
    "project_id": "proj_123",
    "name": "DataProcessor",
    "type": "singleton",
    "is_static": false,
    "is_final": false,
    "superclasses": [],
    "interfaces": [],
    "methods": [{"name": "process", "return_type": "dict"}],
    "attributes": [{"name": "id", "type": "int", "visibility": "private"}],
    "docstring": "Processes data"
  }
  ```
- **Relationship**:
  ```cypher
  (:File {file_path: "src/main.py"})-[:IMPORTS]->(:File {file_path: "src/utils.py"})
  ```

## 11. Future Enhancements
- Integrate Neo4j with a visualization tool (e.g., Neo4j Bloom) for interactive graph exploration.
- Support hybrid storage (Neo4j for graphs, PostgreSQL for tabular data).
- Add machine learning to predict optimal mappings based on Neo4j data.

---

### Key Additions and Updates
1. **Neo4j as Primary Database**:
   - Replaced SQLite with Neo4j for graph-based storage.
   - Designed generic node and relationship schemas to capture project, file, content, and mapping metadata.
   - Enabled graph queries for relationship-driven migrations.
2. **Detailed Metadata Extraction**:
   - Enhanced function metadata (return types, arguments, decorators, static/async flags).
   - Enhanced class metadata (singleton, static, final, inheritance, interfaces, attributes).
   - Added support for enums and extensions.
   - Ensured compatibility with legacy code (e.g., COBOL, Delphi) via detailed attributes.
3. **Generic Schemas**:
   - Neo4j schema supports dynamic properties and relationships.
   - Flexible design accommodates future metadata needs (e.g., new language constructs).
4. **Relationship-Driven Migration**:
   - Leveraged `IMPORTS` and `REFERENCES` relationships to maintain code dependencies.
   - Used Cypher queries to prioritize migrations based on graph structure.
5. **Legacy Code Support**:
   - Detailed metadata enables precise migration of complex constructs (e.g., static methods, enums).
   - OpenAI uses metadata context to handle unsupported languages.

Additional Note:
 - While starting project development make sure to manage files in singleton pattern.
 - Database related files should be databases folder and should have database manager that has connnection and all related management.
 - Utilities should be in utils folder
 - models, llm, embedding (if required), schema, request and response models, enums, constants utilize these folder strcuture.
 - Agents (those interact with the llm), Tools (that used to complete any operation).
  Take care of other things that not mentioned.