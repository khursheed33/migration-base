from celery import Celery
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Create Celery instance
celery_app = Celery(
    "code_migration",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    include=[
        "app.agents.tasks",
    ],
)

# Optional configurations
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    worker_max_tasks_per_child=200,
    worker_prefetch_multiplier=1,
)

# Define periodic tasks if needed
# @celery_app.on_after_configure.connect
# def setup_periodic_tasks(sender, **kwargs):
#     # Executes every 10 minutes
#     sender.add_periodic_task(600.0, cleanup_temp_files.s(), name="cleanup temp files")


if __name__ == "__main__":
    celery_app.start() 