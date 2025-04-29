# Code Migration Framework

A modular, agent-based migration framework in Python using FastAPI, LangGraph, and OpenAI to analyze, plan, migrate, test, and package software projects uploaded as ZIP files. The framework uses Neo4j as the primary database to store detailed metadata, mappings, and other data.

## Features

- Modular, agent-based architecture for code migration
- Detailed metadata extraction for functions, classes, enums, and more
- Graph-based analysis using Neo4j for understanding code relationships
- Comprehensive migration workflow from analysis to packaging
- API endpoints for monitoring and controlling the migration process

## Tech Stack

- Backend: Python 3.11+, FastAPI
- Agent Orchestration: LangGraph
- GenAI: OpenAI API (e.g., GPT-4o)
- Code Analysis: `tree-sitter`, OpenAI
- File Handling: `zipfile`, `shutil`
- Database: Neo4j for metadata storage
- Database Driver: `neo4j` Python driver
- Testing: `pytest`
- Task Queue: Celery, Redis
- Storage: Local filesystem, optional AWS S3
- Security: JWT, `python-multipart`
- Deployment: Docker

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/code-migration-framework.git
cd code-migration-framework
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On Unix or MacOS
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
# Copy the example environment file
cp env.example .env
# Edit the .env file with your configuration
```

5. Start the Neo4j database (using Docker):
```bash
docker run \
    --name neo4j \
    -p 7474:7474 -p 7687:7687 \
    -d \
    -e NEO4J_AUTH=neo4j/password \
    neo4j:latest
```

6. Start the Redis server (using Docker):
```bash
docker run --name redis -p 6379:6379 -d redis
```

7. Run the application:
```bash
uvicorn app.main:app --reload
```

## Usage

1. Upload a ZIP file containing the source code through the `/projects/upload` endpoint.
2. Monitor the migration process via the status endpoints.
3. Download the migrated code once the process is complete.

## API Endpoints

- `POST /projects/upload`: Upload a ZIP file for migration
- `GET /projects/{project_id}/status`: Check migration status
- `GET /projects/{project_id}/metadata`: Get project metadata
- `GET /projects/{project_id}/graph`: Export Neo4j subgraph for visualization
- `GET /projects/{project_id}/download`: Download migrated code
- `POST /projects/{project_id}/feedback`: Provide feedback on migration

## Development

1. Run tests:
```bash
pytest
```

2. Start Celery worker:
```bash
celery -A app.celery_app worker --loglevel=info
```

## License

MIT 